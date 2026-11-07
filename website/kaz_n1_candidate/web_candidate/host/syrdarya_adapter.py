"""
syrdarya_adapter.py  --  VHS v0.5 Syr Darya (锡尔河下游) dataset adapter
=======================================================================

Independent of the LamaH-CE store. Reads ONLY the six teacher-provided CSVs,
read-only, from the source directory. Nothing is copied or rewritten.

Rules enforced here
-------------------
* Every identifier is namespaced: ``SYRDARYA:16037``. A bare number is never
  matched against another dataset (``LAMAHCE:58`` is a different station).
* Time resolution is explicit: YEAR / MONTH / DAY.
* Units are taken from the source header only. A column without a unit in
  its header is ``UNKNOWN``; no speculative conversion is applied to values
  that are displayed. Consistency tests that need a unit state the
  hypothesis they test (e.g. "Q in m3/s") and report the outcome as
  evidence, not as a confirmed unit.
* Quality problems are flagged, never silently corrected.
* Every statistic reported by the API is recomputed here from the files.
* The source files are pinned by SHA-256; if a file changes, the dataset is
  refused (SOURCE_CHANGED) instead of being served.
* v0.5.1 (Codex P1-02): fail closed. A complete pinned manifest (exactly the
  six files, itself pinned by SHA-256 in production) is REQUIRED; each file
  is read once into an immutable snapshot and the same verified bytes are
  parsed (provenance_snapshot.py). Missing manifest / entry, extra entry,
  wrong size or hash, or a missing file refuses the whole dataset.
"""

import os
import calendar
import csv
import hashlib
import io
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from provenance_snapshot import Snapshot, SnapshotRefused, now_iso

DATASET = "SYRDARYA"
RULES_VERSION = "SYR-DQ-0.5.0"
DEFAULT_SOURCE = os.environ.get("VHS_SYR_SOURCE", "")  # restricted handoff default empty
# SHA-256 of manifest/source_manifest.json as frozen in v0.5 and recorded by
# the Codex review (source_hashes_before.json). Never updated from disk.
PINNED_MANIFEST_SHA256 = (
    "65721f8d0d1b81482ce554ade9456703fa028965ad14f80a00a3318359a8100f")

FILES = {
    "discharge": "discharge_syr_darya_monthly_all.csv",
    "water_balance": "reach268_water_balance.csv",
    "intakes": "reach268_intakes_yearly.csv",
    "circles": "circle_water_monthly.csv",
    "kzdam": "kzdam_monthly.csv",
    "meteorology": "met_midreach_268_daily.csv",
}

# Pre-registered thresholds (fixed before looking at results of this run).
W_REL_TOL = 0.05            # |W_from_Q - W| / W above this -> W_INCONSISTENT
SEQ_RUN_MIN = 3             # >= 3 consecutive months with value == month
FLOAT_TOL = 1e-6

UNKNOWN = "UNKNOWN"

# Reach studied in the teacher's case.
REACH_ID = "SYRDARYA:REACH268"
REACH_UP = "16037"
REACH_DOWN = "16039"


def uid(code):
    return "%s:%s" % (DATASET, str(code).strip())


def parse_uid(text):
    """Return the bare station code, or raise ValueError for other datasets."""
    t = str(text or "").strip()
    if ":" in t:
        ns, code = t.split(":", 1)
        if ns.upper() != DATASET:
            raise ValueError("NAMESPACE_MISMATCH: %s is not a %s id"
                             % (t, DATASET))
        t = code
    if not t.isdigit():
        raise ValueError("BAD_STATION_CODE: %r" % text)
    return t


def _num(v):
    v = (v or "").strip()
    if v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Normalised objects
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ProvenanceRecord:
    source_file: str
    sha256: str
    row: Optional[int] = None          # 1-based data row (header excluded)
    column: Optional[str] = None
    transform: str = "AS_IS"


@dataclass
class DataQualityFlag:
    code: str
    severity: str                      # INFO / WARN / ERROR
    scope: str
    message: str
    source_file: str
    rule_version: str = RULES_VERSION


@dataclass
class Station:
    uid: str
    dataset: str
    code: str
    name: Optional[str]
    name_status: str
    years: List[int]
    coordinates: Optional[list] = None
    coordinate_status: str = "GIS_PENDING"
    role: str = "OBSERVED_GAUGE"


@dataclass
class DischargeObservation:
    station_uid: str
    year: int
    month: int
    stat: str                          # mean / max / min
    value: Optional[float]
    unit: str
    unit_status: str
    time_resolution: str
    provenance: ProvenanceRecord
    flags: List[str] = field(default_factory=list)


@dataclass
class MeteorologyObservation:
    date: str
    year: int
    month: int
    day: int
    variable: str                      # P / T
    value: Optional[float]
    unit: str
    unit_status: str
    time_resolution: str
    provenance: ProvenanceRecord


@dataclass
class RemoteSensingObservation:
    product: str                       # CIRCLE / KZDAM
    site: str                          # A..G / KC KD KS KU
    year: int
    month: int
    value: Optional[float]
    value_status: str                  # OBSERVED / ZERO / NO_OBSERVATION
    unit: str
    unit_status: str
    n_images: Optional[float]
    time_resolution: str
    provenance: ProvenanceRecord


@dataclass
class ReachWaterBalance:
    reach_id: str
    year: int
    half_width_km: float
    area_km2: Optional[float]
    W_up: Optional[float]
    W_down: Optional[float]
    dW: Optional[float]
    P_mm: Optional[float]
    ET_mm: Optional[float]
    P_vol: Optional[float]
    ET_vol: Optional[float]
    W_intake: Optional[float]
    residual_file: Optional[float]
    units: dict
    q_derived: bool
    provenance: ProvenanceRecord


@dataclass
class IntakeScenario:
    year: int
    alpha: float
    value: Optional[float]
    unit: str
    unit_status: str
    method: str
    confidence: str
    is_measurement: bool
    q_derived: bool
    derived_from: List[str]
    provenance: ProvenanceRecord


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class SyrDaryaStore:
    def __init__(self, source_dir=None, pinned_manifest=None,
                 expected_manifest_sha256=None):
        self.source_dir = source_dir or os.environ.get(
            "VHS_SYR_SOURCE", DEFAULT_SOURCE)
        self.pinned_manifest = pinned_manifest
        self.expected_manifest_sha256 = expected_manifest_sha256
        self.snapshot = None
        self.refusal = None
        self.seq_runs = []             # one record per flagged run
        self.files = {}
        self.status = "OK"
        self.flags: List[DataQualityFlag] = []
        self.stations = {}
        self.discharge = []            # DischargeObservation
        self.annual_w = {}             # (code, year) -> (value, prov)
        self.discharge_rows = {}       # (code, year) -> True
        self.met = []
        self.rs = []
        self.wb = []
        self.intakes = []
        self.w_checks = []
        self.wb_checks = []
        self._load()

    # -- helpers ---------------------------------------------------------
    def flag(self, code, severity, scope, message, key):
        self.flags.append(DataQualityFlag(code, severity, scope, message,
                                          FILES[key]))

    def _rows(self, key):
        """Parse the SAME bytes that were hashed at load (no second open)."""
        meta = self.files[key]
        text = self.snapshot.raw(meta["file"]).decode(meta["encoding"])
        return list(csv.reader(io.StringIO(text, newline="")))

    def _prov(self, key, row=None, column=None, transform="AS_IS"):
        return ProvenanceRecord(FILES[key], self.files[key]["sha256"], row,
                                column, transform)

    # -- load ------------------------------------------------------------
    def _load(self):
        try:
            snap = Snapshot(self.source_dir, self.pinned_manifest,
                            list(FILES.values()),
                            self.expected_manifest_sha256)
        except SnapshotRefused as exc:
            self.status = exc.status
            self.refusal = {"status": exc.status, "errors": exc.errors,
                            "checked_at": now_iso()}
            per = {e.get("file"): e.get("status") for e in exc.errors
                   if isinstance(e, dict)}
            for key, name in FILES.items():
                self.files[key] = {"file": name, "status": per.get(
                    name, exc.status if not per else "NOT_LOADED"),
                    "sha256": None}
            return
        self.snapshot = snap
        for key, name in FILES.items():
            raw = snap.raw(name)
            enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
            self.files[key] = {
                "file": name, "path": os.path.join(self.source_dir, name),
                "bytes": len(raw), "sha256": snap.sha256(name),
                "encoding": enc, "line_endings":
                "CRLF" if b"\r\n" in raw else "LF", "status": "OK"}
        self._load_discharge()
        self._load_met()
        self._load_circles()
        self._load_kzdam()
        self._load_wb()
        self._load_intakes()
        self._check_w_consistency()
        self._check_wb()

    # -- discharge -------------------------------------------------------
    def _load_discharge(self):
        rows = self._rows("discharge")
        header, data = rows[0], rows[1:]
        self.files["discharge"]["header"] = header
        self.files["discharge"]["records"] = len(data)
        names = defaultdict(set)
        years = defaultdict(set)
        for i, r in enumerate(data, start=1):
            year, code, name = int(r[0]), r[1].strip(), r[2].strip()
            if name:
                names[code].add(name)
            years[code].add(year)
            self.discharge_rows[(code, year)] = True
            w = _num(r[3])
            self.annual_w[(code, year)] = (w, self._prov("discharge", i,
                                                         header[3]))
            for stat, off in (("mean", 4), ("max", 16), ("min", 28)):
                vals = [_num(r[off + m]) for m in range(12)]
                for m in range(12):
                    self.discharge.append(DischargeObservation(
                        uid(code), year, m + 1, stat, vals[m], UNKNOWN,
                        "UNKNOWN_IN_SOURCE_HEADER", "MONTH",
                        self._prov("discharge", i, header[off + m])))
                self._check_sequence_index(code, year, stat, vals)
            self._check_ordering(code, year, r)
        for code in years:
            nm = sorted(names.get(code, []))
            self.stations[code] = Station(
                uid(code), DATASET, code, nm[0] if len(nm) == 1 else
                (" / ".join(nm) if nm else None),
                "SOURCE" if len(nm) == 1 else
                ("MULTIPLE_NAMES" if nm else "NAME_MISSING_IN_SOURCE"),
                sorted(years[code]))
            if not nm:
                self.flag("STATION_NAME_MISSING", "INFO", uid(code),
                          "station name empty in every row", "discharge")
        all_years = sorted({y for ys in years.values() for y in ys})
        self.discharge_years = all_years
        self.flag("DISCRETE_YEARS", "INFO", DATASET,
                  "discharge exists only for %d discrete years %s; gaps "
                  "are NOT interpolated" % (len(all_years), all_years),
                  "discharge")

    def _check_sequence_index(self, code, year, stat, vals):
        run = []
        for m, v in enumerate(vals, start=1):
            if v is not None and abs(v - m) < FLOAT_TOL:
                run.append(m)
            else:
                if len(run) >= SEQ_RUN_MIN:
                    self._seq_flag(code, year, stat, run)
                run = []
        if len(run) >= SEQ_RUN_MIN:
            self._seq_flag(code, year, stat, run)

    def _seq_flag(self, code, year, stat, months):
        self.seq_runs.append({"station": uid(code), "year": year,
                              "stat": stat, "months": list(months)})
        for ob in self.discharge:
            if (ob.station_uid == uid(code) and ob.year == year and
                    ob.stat == stat and ob.month in months):
                ob.flags.append("SEQUENCE_INDEX_SUSPECT")
        self.flag("SEQUENCE_INDEX_SUSPECT", "ERROR",
                  "%s/%d/%s/months %s" % (uid(code), year, stat, months),
                  "values equal their month number for %d consecutive "
                  "months; likely placeholder, not an observation"
                  % len(months), "discharge")

    def _check_ordering(self, code, year, r):
        for m in range(12):
            mean, mx, mn = _num(r[4 + m]), _num(r[16 + m]), _num(r[28 + m])
            scope = "%s/%d/%02d" % (uid(code), year, m + 1)
            if mean is not None and mx is not None and mx + FLOAT_TOL < mean:
                self.flag("MAX_LT_MEAN", "WARN", scope,
                          "monthly max %.3f < mean %.3f" % (mx, mean),
                          "discharge")
            if mean is not None and mn is not None and mn > mean + FLOAT_TOL:
                self.flag("MIN_GT_MEAN", "WARN", scope,
                          "monthly min %.3f > mean %.3f" % (mn, mean),
                          "discharge")
            for v in (mean, mx, mn):
                if v is not None and v < 0:
                    self.flag("NEGATIVE_VALUE", "ERROR", scope,
                              "negative discharge value", "discharge")

    # -- annual W consistency -------------------------------------------
    def _check_w_consistency(self):
        means = defaultdict(dict)
        for ob in self.discharge:
            if ob.stat == "mean":
                means[(ob.station_uid, ob.year)][ob.month] = ob
        for (code, year), (w, prov) in sorted(self.annual_w.items()):
            key = (uid(code), year)
            mm = means.get(key, {})
            vals = [mm[m].value if m in mm else None for m in range(1, 13)]
            suspect = any("SEQUENCE_INDEX_SUSPECT" in mm[m].flags
                          for m in mm)
            rec = {"station": uid(code), "year": year, "W_source": w,
                   "W_source_unit": "10^6 m3",
                   "months_present": sum(v is not None for v in vals),
                   "sequence_suspect": suspect}
            if any(v is None for v in vals):
                rec.update(status="NOT_CHECKABLE_MISSING_MONTHS",
                           W_from_Q=None, rel_diff=None)
            else:
                # Hypothesis under test: monthly mean Q is in m3/s.
                wq = sum(v * calendar.monthrange(year, m)[1] * 86400.0
                         for m, v in zip(range(1, 13), vals)) / 1e6
                rec["W_from_Q"] = wq
                if w is None:
                    rec.update(status="W_MISSING_IN_SOURCE", rel_diff=None)
                    self.flag("W_MISSING", "WARN", "%s/%d" % key,
                              "annual W empty in source; W_from_Q=%.1f "
                              "(10^6 m3, if Q in m3/s)" % wq, "discharge")
                elif w == 0:
                    rec.update(status="W_ZERO", rel_diff=None)
                else:
                    rel = (wq - w) / w
                    rec["rel_diff"] = rel
                    rec["ratio"] = wq / w
                    if abs(rel) <= W_REL_TOL:
                        rec["status"] = "CONSISTENT"
                    elif 900 <= wq / w <= 1100:
                        rec["status"] = "W_UNIT_SCALE_SUSPECT"
                        self.flag("W_UNIT_SCALE_SUSPECT", "ERROR",
                                  "%s/%d" % key,
                                  "W_source=%.3f is ~1000x smaller than "
                                  "W_from_Q=%.1f; source W probably in 10^9 "
                                  "m3 instead of 10^6 m3. NOT rescaled"
                                  % (w, wq), "discharge")
                    else:
                        rec["status"] = "W_INCONSISTENT"
                        self.flag("W_INCONSISTENT", "WARN", "%s/%d" % key,
                                  "W_source=%.2f vs W_from_Q=%.2f "
                                  "(10^6 m3), rel diff %+.1f%% > %.0f%%; "
                                  "source value NOT overwritten"
                                  % (w, wq, rel * 100, W_REL_TOL * 100),
                                  "discharge")
            self.w_checks.append(rec)

    # -- meteorology -----------------------------------------------------
    def _load_met(self):
        rows = self._rows("meteorology")
        header, data = rows[0], rows[1:]
        self.files["meteorology"]["header"] = header
        self.files["meteorology"]["records"] = len(data)
        dates = set()
        for i, r in enumerate(data, start=1):
            d = r[0].strip()
            y, m, dd = (int(x) for x in d.split("-"))
            dates.add((y, m, dd))
            if r[3].strip() and int(r[3]) != y:
                self.flag("YEAR_COLUMN_MISMATCH", "ERROR", d,
                          "year column %s != date year" % r[3], "meteorology")
            for var, col in (("P", 1), ("T", 2)):
                v = _num(r[col])
                self.met.append(MeteorologyObservation(
                    d, y, m, dd, var, v, UNKNOWN, "UNKNOWN_IN_SOURCE_HEADER",
                    "DAY", self._prov("meteorology", i, header[col])))
                if var == "P" and v is not None and v < 0:
                    self.flag("NEGATIVE_PRECIP", "ERROR", d, "p < 0",
                              "meteorology")
        ys = sorted({d[0] for d in dates})
        missing = []
        for y in range(ys[0], ys[-1] + 1):
            for m in range(1, 13):
                for dd in range(1, calendar.monthrange(y, m)[1] + 1):
                    if (y, m, dd) not in dates:
                        missing.append("%04d-%02d-%02d" % (y, m, dd))
        self.met_missing_days = missing
        self.met_range = ("%04d-01-01" % ys[0], "%04d-12-31" % ys[-1])
        if missing:
            self.flag("MET_MISSING_DAYS", "WARN", "meteorology",
                      "%d calendar days absent" % len(missing),
                      "meteorology")
        self._met_index = defaultdict(list)
        for ob in self.met:
            self._met_index[(ob.year, ob.month)].append(ob)

    def met_monthly(self, year):
        out = []
        for m in range(1, 13):
            obs = self._met_index.get((year, m), [])
            p = [o.value for o in obs if o.variable == "P" and
                 o.value is not None]
            t = [o.value for o in obs if o.variable == "T" and
                 o.value is not None]
            ndays = calendar.monthrange(year, m)[1]
            out.append({
                "year": year, "month": m, "days_in_month": ndays,
                "days_with_P": len(p), "days_with_T": len(t),
                "complete": len(p) == ndays and len(t) == ndays,
                "P_sum": round(sum(p), 3) if len(p) == ndays else None,
                "T_mean": round(sum(t) / len(t), 3) if len(t) == ndays
                else None,
                "aggregation": "P: sum of daily values; T: mean of daily "
                               "values; only when all %d days present"
                               % ndays,
            })
        return out

    # -- remote sensing --------------------------------------------------
    def _load_circles(self):
        rows = self._rows("circles")
        header, data = rows[0], rows[1:]
        self.files["circles"]["header"] = header
        self.files["circles"]["records"] = len(data)
        sites = "ABCDEFG"
        self.circle_cov = {s: {"months_with_area": 0, "months_zero": 0,
                               "images_total": 0.0, "first": None,
                               "last": None, "area_without_count": 0,
                               "count_without_area": 0} for s in sites}
        for i, r in enumerate(data, start=1):
            y, m = int(r[0]), int(r[1])
            for k, s in enumerate(sites):
                a, n = _num(r[2 + k]), _num(r[9 + k])
                status = ("NO_OBSERVATION" if a is None else
                          ("ZERO" if a == 0 else "OBSERVED"))
                cov = self.circle_cov[s]
                if a is not None:
                    cov["months_with_area"] += 1
                    cov["first"] = cov["first"] or "%04d-%02d" % (y, m)
                    cov["last"] = "%04d-%02d" % (y, m)
                    if a == 0:
                        cov["months_zero"] += 1
                if n is not None:
                    cov["images_total"] += n
                if a is not None and n is None:
                    cov["area_without_count"] += 1
                    self.flag("AREA_WITHOUT_IMAGE_COUNT", "WARN",
                              "circle %s %04d-%02d" % (s, y, m),
                              "area present but n empty", "circles")
                if a is None and n is not None and n > 0:
                    cov["count_without_area"] += 1
                    self.flag("IMAGE_COUNT_WITHOUT_AREA", "WARN",
                              "circle %s %04d-%02d" % (s, y, m),
                              "n=%g but area empty" % n, "circles")
                self.rs.append(RemoteSensingObservation(
                    "CIRCLE", s, y, m, a, status, "km2",
                    "SOURCE_HEADER (area_%s_km2)" % s, n, "MONTH",
                    self._prov("circles", i, header[2 + k])))

    def _load_kzdam(self):
        rows = self._rows("kzdam")
        header, data = rows[0], rows[1:]
        self.files["kzdam"]["header"] = header
        self.files["kzdam"]["records"] = len(data)
        self.kz_months = []
        for i, r in enumerate(data, start=1):
            y, m = (int(x) for x in r[0].split("-"))
            self.kz_months.append("%04d-%02d" % (y, m))
            n = _num(r[5])
            for k, s in enumerate(("KC", "KD", "KS", "KU")):
                v = _num(r[1 + k])
                self.rs.append(RemoteSensingObservation(
                    "KZDAM", s, y, m, v,
                    "NO_OBSERVATION" if v is None else
                    ("ZERO" if v == 0 else "OBSERVED"),
                    UNKNOWN, "UNKNOWN_IN_SOURCE_HEADER (not assumed km2)",
                    n, "MONTH", self._prov("kzdam", i, header[1 + k])))
        self.flag("KZDAM_UNIT_UNKNOWN", "WARN", "kzdam KC/KD/KS/KU",
                  "source header gives no unit; values are NOT labelled km2",
                  "kzdam")

    def rs_month(self, year, month):
        return [asdict(o) for o in self.rs
                if o.year == year and o.month == month]

    # -- water balance & intakes ----------------------------------------
    def _load_wb(self):
        rows = self._rows("water_balance")
        header, data = rows[0], rows[1:]
        self.files["water_balance"]["header"] = header
        self.files["water_balance"]["records"] = len(data)
        units = {"half_width_km": "km (header)", "area_km2": "km2 (header)",
                 "W_up": UNKNOWN, "W_down": UNKNOWN, "dW": UNKNOWN,
                 "P_mm": "mm (header)", "ET_mm": "mm (header)",
                 "P_vol": UNKNOWN, "ET_vol": UNKNOWN, "W_intake": UNKNOWN,
                 "residual": UNKNOWN}
        for i, r in enumerate(data, start=1):
            v = [_num(x) for x in r]
            self.wb.append(ReachWaterBalance(
                REACH_ID, int(r[0]), v[1], v[2], v[3], v[4], v[5], v[6],
                v[7], v[8], v[9], v[10], v[11], units, True,
                self._prov("water_balance", i)))

    def _load_intakes(self):
        rows = self._rows("intakes")
        header, data = rows[0], rows[1:]
        self.files["intakes"]["header"] = header
        self.files["intakes"]["records"] = len(data)
        self.intake_rows = {}
        for i, r in enumerate(data, start=1):
            y = int(r[0])
            self.intake_rows[y] = {"dW": _num(r[1]), "P_vol": _num(r[2]),
                                   "ET_vol": _num(r[3]), "R": _num(r[4]),
                                   "W_km3": _num(r[8]), "row": i}
            for a, col in ((0.60, 5), (0.75, 6), (0.90, 7)):
                self.intakes.append(IntakeScenario(
                    y, a, _num(r[col]), UNKNOWN,
                    "UNKNOWN_IN_SOURCE_HEADER (W_km3 column name suggests "
                    "km3; not confirmed)", r[9], r[10] or UNKNOWN, False,
                    True, [uid(REACH_UP), uid(REACH_DOWN), "meteorology P",
                           "ET (method not in source)"],
                    self._prov("intakes", i, header[col])))
        self.flag("INTAKE_Q_DERIVED", "WARN", "reach268 intakes",
                  "intake scenarios are inverted from upstream/downstream Q "
                  "(dW); they are not measured withdrawals", "intakes")

    def _check_wb(self):
        wmap = {k: v[0] for k, v in self.annual_w.items()}
        for b in self.wb:
            rec = {"year": b.year, "half_width_km": b.half_width_km}
            wu = wmap.get((REACH_UP, b.year))
            wd = wmap.get((REACH_DOWN, b.year))
            fromq = {c["station"]: c.get("W_from_Q") for c in self.w_checks
                     if c["year"] == b.year}
            rec["W_up_vs_disch_W"] = _ratio(b.W_up, wu, 1e-3)
            rec["W_down_vs_disch_W"] = _ratio(b.W_down, wd, 1e-3)
            rec["W_up_vs_W_from_Q"] = _ratio(b.W_up,
                                             fromq.get(uid(REACH_UP)), 1e-3)
            rec["W_down_vs_W_from_Q"] = _ratio(b.W_down,
                                               fromq.get(uid(REACH_DOWN)),
                                               1e-3)
            rec["dW_ok"] = _close(b.dW, (b.W_up or 0) - (b.W_down or 0))
            rec["P_vol_ok"] = _close(b.P_vol, (b.P_mm or 0) *
                                     (b.area_km2 or 0) / 1e6)
            rec["ET_vol_ok"] = _close(b.ET_vol, (b.ET_mm or 0) *
                                      (b.area_km2 or 0) / 1e6)
            file_conv = (b.dW - b.P_vol + b.ET_vol - b.W_intake)
            standard = (b.dW + b.P_vol - b.ET_vol - b.W_intake)
            rec["residual_file"] = b.residual_file
            rec["residual_recomputed_file_convention"] = file_conv
            rec["residual_recomputed_standard_balance"] = standard
            rec["residual_matches_file_convention"] = _close(b.residual_file,
                                                             file_conv)
            it = self.intake_rows.get(b.year)
            rec["intake_matches_wb"] = bool(it) and _close(
                it["W_km3"], b.W_intake)
            self.wb_checks.append(rec)
        if all(c["residual_matches_file_convention"] for c in self.wb_checks):
            self.flag("RESIDUAL_SIGN_CONVENTION", "WARN",
                      "reach268_water_balance.csv",
                      "residual = dW - P_vol + ET_vol - W_intake in all %d "
                      "rows; a standard reach balance would use "
                      "dW + P_vol - ET_vol - W_intake. Kept as in source; "
                      "needs confirmation" % len(self.wb_checks),
                      "water_balance")
        bad = [c for c in self.wb_checks
               if c["W_up_vs_disch_W"] not in (None,) and
               abs(c["W_up_vs_disch_W"] - 1) > W_REL_TOL]
        for c in bad:
            self.flag("WB_UPSTREAM_W_MISMATCH", "WARN",
                      "%d/%skm" % (c["year"], c["half_width_km"]),
                      "W_up / (16037 W in 10^6 m3 /1000) = %.3f"
                      % c["W_up_vs_disch_W"], "water_balance")
        widths = sorted({b.half_width_km for b in self.wb})
        self.flag("WB_MULTI_WIDTH", "INFO", "reach268_water_balance.csv",
                  "each year appears once per half-width %s; W_up/W_down/dW "
                  "identical across widths, P_vol/ET_vol scale with area"
                  % widths, "water_balance")

    # -- public views ----------------------------------------------------
    def reach_validity(self):
        """Per-year validity of the 16037 -> 16039 reach (recomputed)."""
        out = []
        wc = {(c["station"], c["year"]): c for c in self.w_checks}
        wbmap = {(b.year, b.half_width_km): b for b in self.wb}
        for y in self.discharge_years:
            row = {"year": y}
            for role, code in (("up", REACH_UP), ("down", REACH_DOWN)):
                obs = [o for o in self.discharge
                       if o.station_uid == uid(code) and o.year == y]
                means = [o for o in obs if o.stat == "mean"]
                mins = [o for o in obs if o.stat == "min"]
                row[role] = {
                    "station": uid(code),
                    "present": bool(obs),
                    "mean_months": sum(o.value is not None for o in means),
                    "mean_suspect": sum("SEQUENCE_INDEX_SUSPECT" in o.flags
                                        for o in means),
                    "min_suspect": sum("SEQUENCE_INDEX_SUSPECT" in o.flags
                                       for o in mins),
                    "W_status": wc.get((uid(code), y), {}).get("status"),
                    "W_rel_diff": wc.get((uid(code), y), {}).get("rel_diff"),
                }
            row["water_balance_row"] = (y, 3.0) in wbmap
            ok_means = (row["up"]["mean_months"] == 12 and
                        row["down"]["mean_months"] == 12 and
                        row["up"]["mean_suspect"] == 0 and
                        row["down"]["mean_suspect"] == 0)
            row["monthly_mean_usable"] = ok_means
            row["monthly_min_usable"] = (row["up"]["min_suspect"] == 0 and
                                         row["down"]["min_suspect"] == 0)
            out.append(row)
        return out

    def snapshot_public(self):
        if self.snapshot is None:
            return {"snapshot_id": None, "source_status": self.status,
                    "refusal": self.refusal}
        return self.snapshot.info()

    def provenance(self):
        out = []
        for key, rec in self.files.items():
            r = {k: v for k, v in rec.items() if k != "path"}
            r["dataset_key"] = key
            r["source_dir"] = self.source_dir
            r["access"] = "READ_ONLY"
            r["license"] = ("TEACHER_PROVIDED; license terms not documented "
                            "in the file; local research display only")
            out.append(r)
        return out


def _ratio(a, b, scale):
    if a is None or b is None or b == 0:
        return None
    return a / (b * scale)


def _close(a, b, tol=1e-6):
    if a is None or b is None:
        return False
    return abs(a - b) <= tol * max(1.0, abs(a), abs(b))


def write_manifest(store, path):
    files = [{"file": r["file"], "bytes": r["bytes"], "sha256": r["sha256"],
              "encoding": r["encoding"], "records": r.get("records"),
              "header": r.get("header")} for r in store.files.values()]
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"dataset": DATASET, "source_dir": store.source_dir,
                   "rules_version": RULES_VERSION, "files": files}, f,
                  ensure_ascii=False, indent=1)
