"""
syr_api.py  --  /api/vhs/datasets/* routes for VHS v0.5

Returns (status, body) tuples; server.py serialises them. Every response
carries dataset, data_mode, rules_version and the provenance of the files
used. Raw values are only served per station / per year / per month; there
is no bulk-export route for the teacher's CSVs.

v0.5.1: every response carries the immutable snapshot id / load time;
new routes provenance, provenance-recheck (hash comparison only) and
science (QC closure, run vs cell counts, dual denominators, balance-W
formula, alpha residuals, units, target-Q labels). Data export, future model
input and prediction remain NOT_AUTHORIZED (http_policy.PERMISSIONS).
"""

from dataclasses import asdict

import http_policy
import syrdarya_adapter as SA
from research import baselines as RB
from science_views import ScienceViews, TARGET_Q_NOTICE, dual_pct

DATA_MODE = "TEACHER_CSV_READ_ONLY_LOCAL_DISPLAY"
YEAR_MIN, YEAR_MAX = 1900, 2100
MAX_FLAG_PAGE = 200
WIDTHS = (3.0, 5.0, 8.0)
ALPHAS = (0.60, 0.75, 0.90)


class ApiError(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = \
            status, code, message, extra


def _err(e):
    body = {"error": e.code, "message": e.message, "status": e.status,
            "dataset": SA.DATASET, "prediction": None}
    body.update(e.extra)
    return e.status, body


def _one(qs, name, required=False):
    v = qs.get(name)
    if v is None or v == [""]:
        if required:
            raise ApiError(400, "MISSING_PARAM",
                           "query parameter '%s' is required" % name)
        return None
    if len(v) > 1:
        raise ApiError(400, "BAD_PARAM", "parameter '%s' given twice" % name)
    return v[0]


def _int(qs, name, lo, hi, required=False):
    v = _one(qs, name, required)
    if v is None:
        return None
    try:
        iv = int(v)
    except ValueError:
        raise ApiError(400, "BAD_PARAM", "'%s' must be an integer" % name)
    if not lo <= iv <= hi:
        raise ApiError(400, "OUT_OF_RANGE",
                       "'%s' must be in [%d, %d]" % (name, lo, hi))
    return iv


def _choice(qs, name, choices, default):
    v = _one(qs, name)
    if v is None:
        return default
    try:
        fv = float(v)
    except ValueError:
        raise ApiError(400, "BAD_PARAM", "'%s' must be numeric" % name)
    for c in choices:
        if abs(fv - c) < 1e-9:
            return c
    raise ApiError(400, "OUT_OF_RANGE", "'%s' must be one of %s"
                   % (name, list(choices)))


class SyrApi:
    def __init__(self, store, lamah_store=None):
        self.s = store
        self.lamah = lamah_store
        self.sci = ScienceViews(store)

    # -- envelope --------------------------------------------------------
    def env(self, keys, **body):
        prov = [p for p in self.s.provenance() if p["dataset_key"] in keys]
        base = {"dataset": SA.DATASET, "data_mode": DATA_MODE,
                "rules_version": SA.RULES_VERSION,
                "provenance": [{"file": p["file"], "sha256": p["sha256"],
                                "access": p["access"], "license": p["license"]}
                               for p in prov]}
        snap = self.s.snapshot
        base["snapshot"] = {
            "snapshot_id": snap.snapshot_id if snap else None,
            "loaded_at": snap.loaded_at if snap else None,
            "source_status": "VERIFIED_AT_LOAD" if snap else self.s.status,
            "policy": snap.policy if snap else None}
        base.update(body)
        return 200, base

    def _station(self, qs):
        raw = _one(qs, "station", required=True)
        try:
            code = SA.parse_uid(raw)
        except ValueError as e:
            msg = str(e)
            raise ApiError(400, msg.split(":")[0], msg)
        if code not in self.s.stations:
            raise ApiError(404, "STATION_NOT_FOUND",
                           "%s has no record in the teacher's discharge file"
                           % SA.uid(code))
        return code

    # -- dispatch --------------------------------------------------------
    def handle(self, path, qs):
        try:
            return self._route(path, qs)
        except ApiError as e:
            return _err(e)

    def _route(self, path, qs):
        parts = [p for p in path.split("/") if p][3:]   # after api/vhs/datasets
        if not parts:
            return 200, self.datasets()
        ds = parts[0].upper()
        sub = parts[1] if len(parts) > 1 else None
        if len(parts) > 2:
            raise ApiError(404, "NOT_FOUND", "no such route")
        if ds == "LAMAHCE":
            return self._lamah(sub, qs)
        if ds != SA.DATASET:
            raise ApiError(404, "DATASET_NOT_FOUND", "unknown dataset %s"
                           % parts[0])
        if sub == "predict":
            return 403, {"status": "NOT_AUTHORIZED", "prediction": None,
                         "dataset": SA.DATASET,
                         "model_execution": RB.MODEL_EXECUTION,
                         "reason": "historical observation display is not a "
                                   "model-input authorisation",
                         "permissions": {k: v["status"] for k, v in
                                         http_policy.PERMISSIONS.items()}}
        if self.s.status != "OK":
            raise ApiError(503, self.s.status,
                           "source files missing or changed, or pinned "
                           "manifest invalid; refusing to serve values",
                           files=[{k: v for k, v in r.items() if k != "path"}
                                  for r in self.s.files.values()],
                           refusal=self.s.refusal)
        routes = {None: self.overview, "stations": self.stations,
                  "discharge": self.discharge, "meteorology": self.meteorology,
                  "remote-sensing": self.remote_sensing,
                  "water-balance": self.water_balance,
                  "data-quality": self.data_quality,
                  "timeline": self.timeline, "research": self.research,
                  "availability": self.availability, "gis": self.gis,
                  "provenance": self.provenance,
                  "provenance-recheck": self.provenance_recheck,
                  "science": self.science}
        fn = routes.get(sub)
        if fn is None:
            raise ApiError(404, "NOT_FOUND", "no route %s" % sub)
        return fn(qs) if sub else fn()

    # -- datasets --------------------------------------------------------
    def datasets(self):
        syr_ok = self.s.status == "OK"
        lam = None
        if self.lamah:
            m = self.lamah.meta()["counts"]
            lam = {"id": "LAMAHCE", "title": "LamaH-CE 欧洲河网",
                   "stations": m["stations_total"],
                   "directed_edges": m["directed_edges"],
                   "uid_example": "LAMAHCE:58",
                   "crs": "EPSG:3035", "endpoints": "/api/vhs/stations ...",
                   "status": "OK"}
        return {"datasets": [d for d in [lam, {
            "id": SA.DATASET, "title": "Syr Darya 锡尔河下游",
            "status": self.s.status,
            "stations": len(self.s.stations) if syr_ok else None,
            "discharge_years": self.s.discharge_years if syr_ok else None,
            "meteorology_range": list(self.s.met_range) if syr_ok else None,
            "uid_example": "SYRDARYA:16037", "crs": "GIS_PENDING",
            "case_reach": "SYRDARYA:16037 -> SYRDARYA:16039 "
                          "(teacher-provided case)",
            "data_mode": DATA_MODE}] if d],
            "cross_dataset_matching": "DISABLED (ids are namespaced; equal "
                                      "numbers are never matched)"}

    def _lamah(self, sub, qs):
        if not self.lamah:
            raise ApiError(503, "DATASET_UNAVAILABLE", "LAMAHCE not loaded")
        if sub is None:
            return 200, [d for d in self.datasets()["datasets"]
                         if d["id"] == "LAMAHCE"][0]
        if sub == "stations":
            q = _one(qs, "q") or ""
            lim = _int(qs, "limit", 1, 200) or 25
            res = self.lamah.search(q, lim)
            for r in res:
                r["uid"] = "LAMAHCE:%d" % r["id"]
            return 200, {"dataset": "LAMAHCE", "results": res}
        if sub == "predict":
            return 403, {"status": "NOT_AUTHORIZED", "prediction": None}
        raise ApiError(404, "NOT_FOUND", "LAMAHCE uses the legacy "
                       "/api/vhs/* routes for %s" % sub)

    def overview(self):
        return self.env(list(SA.FILES), **self.datasets()["datasets"][-1])

    def stations(self, qs):
        rows = []
        for code, st in sorted(self.s.stations.items()):
            d = asdict(st)
            d["n_years"] = len(st.years)
            d["is_case_reach"] = code in (SA.REACH_UP, SA.REACH_DOWN)
            rows.append(d)
        return self.env(["discharge"], stations=rows,
                        case_reach={"id": SA.REACH_ID,
                                    "upstream": SA.uid(SA.REACH_UP),
                                    "downstream": SA.uid(SA.REACH_DOWN),
                                    "label": "16037 → 16039 · 268 km 河段"
                                             "（老师提供的案例）"})

    # -- discharge -------------------------------------------------------
    def discharge(self, qs):
        code = self._station(qs)
        view = _one(qs, "view") or "monthly"
        if view == "annual":
            rows = []
            for c in self.s.w_checks:
                if c["station"] != SA.uid(code):
                    continue
                r = dict(c)
                r["dual_pct"] = dual_pct(c.get("W_from_Q"), c.get("W_source"))
                r["source_value_overwritten"] = False
                rows.append(r)
            return self.env(["discharge"], station=SA.uid(code),
                            view="annual", years=rows,
                            unit_W="10^6 m3 (source header)",
                            W_from_Q_note="Σ Q_month·days·86400/1e6 under the "
                                          "hypothesis Q is m3/s",
                            rel_diff_definition="rel_diff = (W_Q − W_源)/W_源"
                                                "（分母为源 W）",
                            tolerance=SA.W_REL_TOL,
                            target_q_notice="W_from_Q 由该站 Q 派生；该站作目标站时"
                                            + TARGET_Q_NOTICE)
        if view != "monthly":
            raise ApiError(400, "BAD_PARAM", "view must be monthly|annual")
        year = _int(qs, "year", YEAR_MIN, YEAR_MAX, required=True)
        st = self.s.stations[code]
        if year not in st.years:
            raise ApiError(404, "DATA_NOT_FOUND",
                           "%s has no discharge record for %d; years are "
                           "discrete and are not interpolated"
                           % (SA.uid(code), year),
                           available_years=st.years)
        months = {m: {"month": m} for m in range(1, 13)}
        for o in self.s.discharge:
            if o.station_uid == SA.uid(code) and o.year == year:
                cell = months[o.month]
                cell[o.stat] = o.value
                cell[o.stat + "_flags"] = o.flags
                cell[o.stat + "_status"] = (
                    "MISSING" if o.value is None else
                    ("SUSPECT" if o.flags else "OBSERVED"))
        w = [c for c in self.s.w_checks
             if c["station"] == SA.uid(code) and c["year"] == year]
        return self.env(["discharge"], station=SA.uid(code), name=st.name,
                        year=year, time_resolution="MONTH",
                        unit="UNKNOWN", unit_status="UNKNOWN_IN_SOURCE_HEADER;"
                        " annual-volume cross-check supports m3/s",
                        statistics_basis={
                            "mean": "源表“N月平均”原值", "max": "源表“N月最大”原值",
                            "min": "源表“N月最小”原值",
                            "suspect": "连续≥3月等于月序号→SUSPECT，保留原值，不绘制"},
                        months=[months[m] for m in range(1, 13)],
                        annual=w[0] if w else None)

    # -- meteorology -----------------------------------------------------
    def meteorology(self, qs):
        year = _int(qs, "year", YEAR_MIN, YEAR_MAX, required=True)
        gran = _one(qs, "granularity") or "monthly"
        y0, y1 = int(self.s.met_range[0][:4]), int(self.s.met_range[1][:4])
        if not y0 <= year <= y1:
            raise ApiError(404, "DATA_NOT_FOUND", "meteorology covers %d-%d"
                           % (y0, y1), available_range=[y0, y1])
        if gran == "monthly":
            return self.env(["meteorology"], year=year, granularity="MONTH",
                            units={"P": "UNKNOWN", "T": "UNKNOWN"},
                            months=self.s.met_monthly(year))
        if gran != "daily":
            raise ApiError(400, "BAD_PARAM", "granularity must be "
                           "monthly|daily")
        month = _int(qs, "month", 1, 12, required=True)
        days = {}
        for o in self.s._met_index.get((year, month), []):
            days.setdefault(o.date, {"date": o.date})[o.variable] = o.value
        return self.env(["meteorology"], year=year, month=month,
                        granularity="DAY",
                        units={"P": "UNKNOWN", "T": "UNKNOWN"},
                        days=sorted(days.values(), key=lambda d: d["date"]))

    # -- remote sensing --------------------------------------------------
    def remote_sensing(self, qs):
        year = _int(qs, "year", YEAR_MIN, YEAR_MAX, required=True)
        month = _int(qs, "month", 1, 12)
        obs = [o for o in self.s.rs if o.year == year and
               (month is None or o.month == month)]
        if month is None:
            grid = {}
            for o in obs:
                g = grid.setdefault(o.month, {"month": o.month,
                                              "circles": {}, "kzdam": None})
                if o.product == "CIRCLE":
                    g["circles"][o.site] = {"status": o.value_status,
                                            "n_images": o.n_images}
                else:
                    g["kzdam"] = {"n_scene": o.n_images}
            return self.env(["circles", "kzdam"], year=year,
                            view="availability",
                            months=[grid.get(m, {"month": m, "circles": {},
                                                 "kzdam": None,
                                                 "status": "NO_ROW"})
                                    for m in range(1, 13)])
        circles = []
        for s in "ABCDEFG":
            o = [x for x in obs if x.product == "CIRCLE" and x.site == s]
            circles.append(asdict(o[0]) if o else {
                "product": "CIRCLE", "site": s, "year": year, "month": month,
                "value": None, "value_status": "NO_ROW", "unit": "km2",
                "n_images": None})
        kz = [asdict(o) for o in obs if o.product == "KZDAM"]
        kz_first = self.s.kz_months[0]
        return self.env(["circles", "kzdam"], year=year, month=month,
                        circles=circles, kzdam=kz,
                        kzdam_note=("no KZDAM row for this month; product "
                                    "rows span %s..%s with gaps"
                                    % (kz_first, self.s.kz_months[-1]))
                        if not kz else None,
                        semantics={"circle_area": "water-surface area, km2 "
                                   "(source header)",
                                   "n_images": "image count (count)",
                                   "kzdam": "unit UNKNOWN (not km2, not Q)"})

    # -- water balance ---------------------------------------------------
    def water_balance(self, qs):
        year = _int(qs, "year", YEAR_MIN, YEAR_MAX, required=True)
        width = _choice(qs, "width_km", WIDTHS, 3.0)
        alpha = _choice(qs, "alpha", ALPHAS, 0.75)
        rows = [b for b in self.s.wb if b.year == year and
                abs(b.half_width_km - width) < 1e-9]
        if not rows:
            raise ApiError(404, "DATA_NOT_FOUND",
                           "no water-balance record for %d" % year,
                           available_years=sorted({b.year for b in self.s.wb}))
        b = rows[0]
        chk = [c for c in self.s.wb_checks if c["year"] == year and
               abs(c["half_width_km"] - width) < 1e-9][0]
        scen = [asdict(i) for i in self.s.intakes if i.year == year]
        sel = [s for s in scen if abs(s["alpha"] - alpha) < 1e-9]
        return self.env(["water_balance", "intakes"], year=year,
                        half_width_km=width, alpha=alpha,
                        balance=asdict(b), checks=chk,
                        intake_scenarios=scen,
                        selected_scenario=sel[0] if sel else None,
                        residuals=self.sci.alpha_view(year, width, alpha),
                        balance_w_formula=self.sci.build()[
                            "water_balance_w_formula"]["formula_in_use"],
                        disclaimer="引水量为由 16037/16039 上下游 Q 反演的低置信度"
                                   "情景，不是实测取水量；源残余按源文件公式 "
                                   "dW − P_vol + ET_vol − W引水 给出（对应源文件"
                                   "取水），与所选 α 情景残余分列；源文件未给出控制体"
                                   "定义，不判定其符号对错，待老师确认。",
                        target_q_notice=TARGET_Q_NOTICE,
                        units_note="W_up/W_down/dW/P_vol/ET_vol 源表未标单位；"
                                   "与流量文件交叉核对支持 km3（推断，非确认）")

    # -- data quality ----------------------------------------------------
    def data_quality(self, qs):
        code = _one(qs, "code")
        limit = _int(qs, "limit", 1, MAX_FLAG_PAGE) or 50
        offset = _int(qs, "offset", 0, 10 ** 6) or 0
        flags = [f for f in self.s.flags if code is None or f.code == code]
        counts = {}
        for f in self.s.flags:
            counts[f.code] = counts.get(f.code, 0) + 1
        wstat = {}
        for c in self.s.w_checks:
            wstat[c["status"]] = wstat.get(c["status"], 0) + 1
        miss = {}
        for o in self.s.discharge:
            k = o.stat
            t = miss.setdefault(k, [0, 0])
            t[0] += 1
            t[1] += o.value is None
        return self.env(list(SA.FILES),
                        source_status=self.s.status,
                        files=self.s.provenance(),
                        units=_UNITS,
                        flag_counts=counts,
                        flags_total=len(flags),
                        flags=[asdict(f) for f in
                               flags[offset:offset + limit]],
                        w_check_status=wstat,
                        discharge_missing_rate={k: {"cells": v[0],
                                                    "missing": v[1],
                                                    "rate": v[1] / v[0]}
                                                for k, v in miss.items()},
                        circle_coverage=self.s.circle_cov,
                        kzdam_months=len(self.s.kz_months),
                        met_missing_days=len(self.s.met_missing_days),
                        reach_validity=self.s.reach_validity(),
                        q_derived=["reach268_water_balance.csv: W上/W下/dW/残余",
                                   "reach268_intakes_yearly.csv: 全部 α 情景"],
                        flags_offset=offset, flags_limit=limit,
                        permissions={"display": "LOCAL_READ_ONLY",
                                     "bulk_export": "DISABLED",
                                     "model_execution": RB.MODEL_EXECUTION,
                                     "prediction": None,
                                     "domains": {k: v["status"] for k, v in
                                                 http_policy.PERMISSIONS
                                                 .items()}})

    def timeline(self, qs):
        st = {}
        for code in (SA.REACH_UP, SA.REACH_DOWN):
            st[SA.uid(code)] = self.s.stations[code].years
        circ = sorted({"%04d-%02d" % (o.year, o.month) for o in self.s.rs
                       if o.product == "CIRCLE" and o.value is not None})
        return self.env(list(SA.FILES), discharge_years=self.s.discharge_years,
                        reach_station_years=st,
                        meteorology_range=list(self.s.met_range),
                        circle_months=circ, kzdam_months=self.s.kz_months,
                        water_balance_years=sorted({b.year for b in
                                                    self.s.wb}))

    def availability(self, qs):
        year = _int(qs, "year", YEAR_MIN, YEAR_MAX, required=True)
        month = _int(qs, "month", 1, 12, required=True)
        return self.env(list(SA.FILES),
                        **RB.availability_clock(self.s, year, month))

    def research(self, qs):
        return self.env(list(SA.FILES), **RB.summary())

    def provenance(self, qs):
        return self.env(list(SA.FILES), **self.s.snapshot.info())

    def provenance_recheck(self, qs):
        return self.env(list(SA.FILES), recheck=self.s.snapshot.recheck(),
                        semantics=self.s.snapshot.info()["semantics"])

    def science(self, qs):
        return self.env(list(SA.FILES), **self.sci.build())

    def gis(self, qs):
        return self.env([], gis_status="GIS_PENDING",
                        crs="UNKNOWN (EPSG:3035 of LamaH-CE is NOT applied)",
                        station_coordinates="NOT_AVAILABLE",
                        next_inputs_to_verify=[
                            {"item": "03_原始数据/vectors/*", "check":
                             "CRS (.prj or embedded), geometry type, feature "
                             "count, bounding box"},
                            {"item": "verified gauge coordinate file",
                             "check": "join field to SYRDARYA:<code>, "
                                      "coordinate CRS, provenance"},
                            {"item": "reach268 line", "check":
                             "start/end vs 16037/16039, length ≈ 268 km"},
                            {"item": "circles A–G", "check": "centre, radius,"
                             " CRS; consistent with area_*_km2"},
                            {"item": "KZDAM KC/KD/KS/KU", "check":
                             "unit and footprint definition"}],
                        note="no vector file was read in v0.5")


_UNITS = [
    {"field": "monthly mean/max/min Q", "unit": "UNKNOWN",
     "evidence": "header has none; Σ Q·t with m3/s matches W for most "
                 "station-years"},
    {"field": "年径流W_百万m3", "unit": "10^6 m3", "evidence": "source header"},
    {"field": "met p", "unit": "UNKNOWN", "evidence": "header 'p'"},
    {"field": "met t", "unit": "UNKNOWN", "evidence": "header 't'"},
    {"field": "circle area_X_km2", "unit": "km2", "evidence": "source header"},
    {"field": "circle n_X", "unit": "count", "evidence": "header prefix n_"},
    {"field": "kzdam KC/KD/KS/KU", "unit": "UNKNOWN",
     "evidence": "header has none; NOT km2"},
    {"field": "kzdam n_scene", "unit": "count", "evidence": "header"},
    {"field": "WB W上/W下/dW/P_vol/ET_vol/W引水/残余", "unit": "UNKNOWN",
     "evidence": "header has none; cross-check consistent with km3"},
    {"field": "WB P_mm / ET_mm", "unit": "mm", "evidence": "source header"},
    {"field": "WB 半宽km / 面积km2", "unit": "km / km2",
     "evidence": "source header"},
]
