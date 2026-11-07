"""
tests/test_science_views.py  --  Codex P1-03..P1-05 / Q1-Q9 research correctness

Runs ONLY on the user's PC (needs the teacher CSVs, read-only, at their
original path). For every item the test
  (a) recomputes the quantity independently from the raw CSV bytes with code
      in this file (not the adapter), after checking the bytes against the
      frozen manifest pin;
  (b) compares with what the v0.5.1 API returns;
  (c) compares with the Codex review artefacts / report values.
Nothing is copied; logs contain only counts and PASS/FAIL.
"""
import calendar
import csv
import hashlib
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import _server  # noqa: E402

REVIEW = os.path.join(os.path.dirname(os.path.dirname(APP)),
                      "v0.5_codex_review_20261022")
T = Suite("test_science_views")
DS = "/api/vhs/datasets/SYRDARYA"
TOL = 0.05


def num(x):
    x = (x or "").strip()
    if x == "":
        return None
    try:
        return float(x)
    except ValueError:
        return None


def load_pinned():
    import syrdarya_adapter as SA
    src = os.environ.get("VHS_SYR_SOURCE", SA.DEFAULT_SOURCE)
    with open(os.path.join(APP, "manifest", "source_manifest.json"),
              "rb") as f:
        mraw = f.read()
    assert hashlib.sha256(mraw).hexdigest() == SA.PINNED_MANIFEST_SHA256
    pins = {e["file"]: e for e in json.loads(mraw.decode("utf-8"))["files"]}
    rows = {}
    for key, name in SA.FILES.items():
        with open(os.path.join(src, name), "rb") as f:     # read-only
            raw = f.read()
        if hashlib.sha256(raw).hexdigest() != pins[name]["sha256"]:
            raise SystemExit("teacher file %s does not match pin" % name)
        txt = raw.decode("utf-8-sig")
        rows[key] = list(csv.reader(io.StringIO(txt, newline="")))
    return SA, rows


def classify(rows):
    out = {}
    for r in rows[1:]:
        y, code = int(r[0]), r[1].strip()
        w = num(r[3])
        q = [num(r[4 + m]) for m in range(12)]
        if any(v is None for v in q):
            cat, wq = "NOT_CHECKABLE_MISSING_MONTHS", None
        else:
            wq = sum(v * calendar.monthrange(y, m + 1)[1] * 86400
                     for m, v in enumerate(q)) / 1e6
            if w is None:
                cat = "W_MISSING_IN_SOURCE"
            elif w == 0:
                cat = "W_ZERO"
            elif abs(wq - w) / w <= TOL:
                cat = "CONSISTENT"
            elif 900 <= wq / w <= 1100:
                cat = "W_UNIT_SCALE_SUSPECT"
            else:
                cat = "W_INCONSISTENT"
        key = ("SYRDARYA:" + code, y)
        assert key not in out, "duplicate station-year"
        out[key] = {"cat": cat, "W_source": w, "W_Q": wq, "q": q}
    return out


def seq_runs(rows):
    runs, eq = [], {"mean": 0, "max": 0, "min": 0}
    for r in rows[1:]:
        y, code = int(r[0]), r[1].strip()
        for stat, off in (("mean", 4), ("max", 16), ("min", 28)):
            run = []
            for m in range(1, 13):
                v = num(r[off + m - 1])
                if v is not None and abs(v - m) < 1e-6:
                    eq[stat] += 1
                    run.append(m)
                else:
                    if len(run) >= 3:
                        runs.append(("SYRDARYA:" + code, y, stat, run))
                    run = []
            if len(run) >= 3:
                runs.append(("SYRDARYA:" + code, y, stat, run))
    return runs, eq


def main():
    SA, rows = load_pinned()
    own = classify(rows["discharge"])
    runs, eq = seq_runs(rows["discharge"])
    proc, base, port = _server.start()
    try:
        g = lambda p: _server.get(base, p)                    # noqa: E731
        st, sci, _ = g(DS + "/science")
        T.check("C00", "science endpoint 200 + snapshot id", st == 200 and
                sci.get("snapshot", {}).get("snapshot_id"), st)
        # ---- C1 classification --------------------------------------
        cnt = {}
        for v in own.values():
            cnt[v["cat"]] = cnt.get(v["cat"], 0) + 1
        qc = sci["qc_classification"]
        T.check("C1a", "independent recompute: 259/80/7/18/2, total 366",
                cnt == {"CONSISTENT": 259, "W_INCONSISTENT": 80,
                        "W_MISSING_IN_SOURCE": 7,
                        "NOT_CHECKABLE_MISSING_MONTHS": 18,
                        "W_UNIT_SCALE_SUSPECT": 2} and len(own) == 366, cnt)
        T.check("C1b", "API counts == independent counts",
                {k: v for k, v in qc["counts"].items() if v} == cnt,
                qc["counts"])
        T.check("C1c", "closed: categories sum == station-years == records",
                qc["closed"] and qc["n_station_years"] == 366 ==
                qc["n_discharge_records"] == len(rows["discharge"]) - 1,
                (qc["n_station_years"], qc["n_discharge_records"]))
        api_rows = {(r["station"], r["year"]): r["category"]
                    for r in qc["rows"]}
        T.check("C1d", "API row-level categories == independent (366/366)",
                all(api_rows.get(k) == v["cat"] for k, v in own.items()) and
                len(api_rows) == 366)
        rv = os.path.join(REVIEW, "station_year_unique_classification.csv")
        with open(rv, encoding="utf-8-sig", newline="") as f:
            rrows = list(csv.DictReader(f))
        def rk(r):
            s = r["station"].strip()
            return (s if s.startswith("SYRDARYA:") else "SYRDARYA:" + s,
                    int(r["year"]))
        rmap = {rk(r): r["category"] for r in rrows}
        mism = [k for k, v in own.items() if rmap.get(k) != v["cat"]]
        T.check("C1e", "row-level == Codex review CSV (366 rows)",
                len(rmap) == 366 and not mism, mism[:5])
        T.check("C1f", "no W_ZERO present; 16326/2003 & 16497/2003 unit "
                "suspect", "W_ZERO" not in cnt and
                own[("SYRDARYA:16326", 2003)]["cat"] ==
                own[("SYRDARYA:16497", 2003)]["cat"] ==
                "W_UNIT_SCALE_SUSPECT")
        # ---- C2 / C3 sequence index ----------------------------------
        si = sci["sequence_index"]
        cells = {"mean": 0, "max": 0, "min": 0}
        for r in runs:
            cells[r[2]] += len(r[3])
        T.check("C2a", "independent: 391 runs, 2671 flagged cells "
                "(min1475/max1077/mean119)", len(runs) == 391 and cells ==
                {"min": 1475, "max": 1077, "mean": 119}, (len(runs), cells))
        T.check("C2b", "independent: 2831 equal-month cells, 160 outside "
                "runs", sum(eq.values()) == 2831 and
                sum(eq.values()) - sum(cells.values()) == 160, eq)
        T.check("C2c", "API runs/cells/equal-month == independent",
                si["runs_total"] == len(runs) and
                si["flagged_cells_total"] == sum(cells.values()) and
                si["equal_month_cells_total"] == sum(eq.values()) and
                all(si["by_stat"][s]["flagged_cells"] == cells[s]
                    for s in cells), (si["runs_total"],
                                      si["flagged_cells_total"]))
        with open(os.path.join(REVIEW, "sequence_index_evidence.json"),
                  encoding="utf-8") as f:
            ev = json.load(f)
        T.check("C2d", "== review sequence_index_evidence.json "
                "(flagged_by_stat, equals_month)", ev["flagged_by_stat"] ==
                cells and len(ev["equals_month"]) == sum(eq.values()))
        T.check("C2e", "API keeps run and cell semantics separate",
                "run" in si["semantics"] and "cell" in si["semantics"] and
                si["runs_total"] != si["flagged_cells_total"])
        mean_sy = sorted({(r[0], r[1]) for r in runs if r[2] == "mean"})
        cats = {}
        for k in mean_sy:
            cats[own[k]["cat"]] = cats.get(own[k]["cat"], 0) + 1
        T.check("C3a", "mean-affected station-years: 25 (23 W_INCONSISTENT"
                " + 2 W_MISSING)", len(mean_sy) == 25 and cats == {
                    "W_INCONSISTENT": 23, "W_MISSING_IN_SOURCE": 2}, cats)
        T.check("C3b", "API mean station-year scope == independent",
                si["by_stat"]["mean"]["station_years"] == len(mean_sy) and
                si["by_stat"]["mean"]["w_category_of_affected_station_years"]
                == cats)
        # ---- C4 / C5 16037/2008 dual denominator, no overwrite -------
        c = own[("SYRDARYA:16037", 2008)]
        p_src = (c["W_Q"] - c["W_source"]) / c["W_source"] * 100
        p_q = (c["W_source"] - c["W_Q"]) / c["W_Q"] * 100
        T.check("C4a", "independent 16037/2008: +20.3106877% (÷W_源), "
                "-16.8818649% (÷W_Q)", abs(p_src - 20.3106877) < 1e-6 and
                abs(p_q + 16.8818649) < 1e-6, (p_src, p_q))
        ca = sci["case_16037_2008"]
        T.check("C4b", "API case values == independent, both labelled",
                abs(ca["pct_denominator_W_source"] - p_src) < 1e-9 and
                abs(ca["pct_denominator_W_from_Q"] - p_q) < 1e-9 and
                "分母" in ca["pct_denominator_W_source_label"] and
                "分母" in ca["pct_denominator_W_from_Q_label"])
        allow = True
        for code in ("16037", "16039"):
            st, an, _ = g(DS + "/discharge?station=SYRDARYA:%s&view=annual"
                          % code)
            for r in an["years"]:
                o = own[(r["station"], r["year"])]
                allow &= r["W_source"] == o["W_source"]
                allow &= r["source_value_overwritten"] is False
                if o["W_Q"] is not None and o["W_source"]:
                    allow &= abs(r["dual_pct"]["pct_denominator_W_source"] -
                                 (o["W_Q"] - o["W_source"]) / o["W_source"]
                                 * 100) < 1e-9
            if code == "16037":
                r08 = [r for r in an["years"] if r["year"] == 2008][0]
        T.check("C5a", "annual view: source W never overwritten; dual pct "
                "per row == independent", allow)
        T.check("C5b", "annual view 2008 shows W_源 and W_Q side by side + "
                "definition", r08["W_source"] == c["W_source"] and
                abs(r08["W_from_Q"] - c["W_Q"]) < 1e-9 and
                "分母" in an["rel_diff_definition"])
        # ---- C6 balance-W formula ------------------------------------
        wb = rows["water_balance"][1:]
        worst = 0.0
        n = 0
        for r in wb:
            y = int(r[0])
            for code, col in (("16037", 3), ("16039", 4)):
                q = own.get(("SYRDARYA:" + code, y), {}).get("q")
                wv = num(r[col])
                if not q or any(v is None for v in q) or wv is None:
                    continue
                n += 1
                f = sum(q) / 12 * 365 * 86400 / 1e9
                worst = max(worst, abs(f - wv) / abs(wv))
        wf = sci["water_balance_w_formula"]
        T.check("C6a", "independent: W上/W下 == (ΣQ/12)·365·86400/1e9 "
                "(max rel err ≤1e-6)", n > 0 and worst <= 1e-6, (n, worst))
        T.check("C6b", "API detects exactly EQUAL_MONTH_FIXED_365",
                wf["detected"] == ["EQUAL_MONTH_FIXED_365"] and
                "365" in wf["formula_in_use"], wf["detected"])
        T.check("C6c", "actual-days formula rejected (differs from source)",
                wf["candidates"]["ACTUAL_MONTH_DAYS"]["max_rel_error"] > 1e-6)
        # ---- C7 alpha residuals --------------------------------------
        intake = {int(r[0]): {0.6: num(r[5]), 0.75: num(r[6]),
                              0.9: num(r[7])}
                  for r in rows["intakes"][1:]}
        ok_all, n7 = True, 0
        for r in wb:
            y, wd = int(r[0]), num(r[1])
            dW, Pv, ETv, Iw, Rf = (num(r[5]), num(r[8]), num(r[9]),
                                   num(r[10]), num(r[11]))
            fixed = []
            for a in (0.6, 0.75, 0.9):
                st, b, _ = g(DS + "/water-balance?year=%d&width_km=%s&alpha=%s"
                             % (y, r[1].strip(), a))
                if st != 200:
                    ok_all = False
                    continue
                rs = b["residuals"]
                fixed.append(rs["fixed_source_record"]["residual_file_value"])
                ia = intake.get(y, {}).get(a)
                if ia is not None:
                    sel = dW - Pv + ETv - ia
                    ok_all &= abs(rs["selected_scenario"][
                        "residual_file_formula_with_selected_intake"] -
                        sel) < 1e-9
                    ok_all &= abs(rs["selected_scenario"][
                        "residual_control_volume_diagnostic"] -
                        (dW + Pv - ETv - ia)) < 1e-9
                n7 += 1
            ok_all &= len(set(fixed)) == 1 and abs(fixed[0] - Rf) < 1e-12
        T.check("C7a", "all years×widths×α: selected residual == "
                "independent; fixed source residual invariant to α",
                ok_all and n7 > 0, n7)
        st, b, _ = g(DS + "/water-balance?year=2010&width_km=3&alpha=0.6")
        rs = b["residuals"]
        T.check("C7b", "2010/3km α=.60: residuals ≈1.229 (file formula) / "
                "≈0.987 (control volume), review values",
                abs(rs["selected_scenario"][
                    "residual_file_formula_with_selected_intake"] - 1.229)
                < 5e-4 and abs(rs["selected_scenario"][
                    "residual_control_volume_diagnostic"] - 0.987) < 5e-4,
                rs["selected_scenario"])
        fx = rs["fixed_source_record"]
        T.check("C7c", "2010/3km fixed: R=.768291144, intake 2.304 ↔ α=.75,"
                " control-volume .526197", abs(fx["residual_file_value"] -
                                               0.768291144) < 1e-8 and
                fx["source_alpha_detected"] == 0.75 and
                abs(fx["residual_control_volume_diagnostic"] - 0.526197)
                < 1e-6, fx)
        T.check("C7d", "disclaimer neutral, still says not measured intake",
                "不是实测取水量" in b["disclaimer"] and
                "相反" not in b["disclaimer"], b["disclaimer"])
        # ---- C8 units ------------------------------------------------
        T.check("C8a", "unconfirmed units stay UNKNOWN (Q, P/T, KZDAM, "
                "intake, balance volumes)",
                sci["units"]["unconfirmed_kept_unknown"] is True,
                sci["units"])
        st, mo, _ = g(DS + "/discharge?station=SYRDARYA:16037&year=2008")
        T.check("C8b", "monthly Q: unit UNKNOWN + statistics_basis "
                "mean/max/min/suspect", mo["unit"] == "UNKNOWN" and
                set(mo["statistics_basis"]) == {"mean", "max", "min",
                                                "suspect"})
        T.check("C8c", "circle area keeps header unit km2 (only confirmed "
                "one)", sci["units"]["circle_area"] == ["km2"],
                sci["units"]["circle_area"])
        # ---- C9 target-Q labels --------------------------------------
        tq = sci["target_q_derived"]
        feats = {f["diagnostic"] for f in tq["features"]}
        T.check("C9a", "target-Q-derived diagnostics labelled (dW, "
                "residual, intake)", {"dW_reach", "wb_residual",
                                      "intake_alpha"} <= feats, feats)
        T.check("C9b", "water-balance + annual responses carry the "
                "target-Q notice", "零目标" in b["target_q_notice"] and
                "零目标" in an["target_q_notice"])
        st, res, _ = g(DS + "/research")
        tab = {f["feature"]: f for f in res["features"]}
        T.check("C9c", "research feature table: target_q_derived true for "
                "those, false for upstream Q / met",
                all(tab[f]["target_q_derived"] for f in ("dW_reach",
                                                         "wb_residual")) and
                not tab["Q_up_monthly_mean"]["target_q_derived"] and
                not tab["P_monthly_sum"]["target_q_derived"])
        T.check("C9d", "research badge = lineage-check only, not certified",
                "≠ 已执行实验" in res.get("badge_meaning", "") and
                res.get("model_execution") == "NOT_AUTHORIZED",
                res.get("badge_meaning"))
        st, dq, _ = g(DS + "/data-quality?limit=40&offset=40")
        T.check("E01", "data-quality paging metadata (offset/limit/total)",
                dq["flags_offset"] == 40 and dq["flags_limit"] == 40 and
                len(dq["flags"]) <= 40 and dq["flags_total"] >= 80)
    finally:
        _server.stop(proc)
    return T.save({"server": base, "review_dir": REVIEW})


if __name__ == "__main__":
    raise SystemExit(main())
