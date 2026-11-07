"""
tests/test_v06_api.py -- VHS v0.6 four-layer API contract + safety suite

Checks the real product, not a mock:
  * five first-level entries exist and every layer answers;
  * observed-only results (qsim / prediction / PI are null; no fake numbers);
  * MODEL_EXECUTION gates answer 403 on GET and POST;
  * dataset namespaces never mix (SYRDARYA vs LAMAHCE);
  * spatial status separation (GIS_DISPLAY_READY vs HYDROLOGICALLY_CERTIFIED);
  * missing values are never rendered as zero; alpha scenarios keep fixed vs
    scenario residuals apart;
  * parameter configs save as JSON and reject lineage violations.

Uses a PRIVATE server started by tests/_server.py (never 8772-8775).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import _server  # noqa: E402

T = Suite("test_v06_api")
V6 = "/api/v6"


def main():
    proc, base, port = _server.start()
    try:
        def get(p):
            return _server.get(base, p)

        # ---------------- health / manifest -----------------------------
        st, h, _ = get("/api/vhs/health")
        T.check("V01", "health: platform 0.6.0 + four layers + gate",
                st == 200 and h.get("app_version") == "0.6.0" and
                h.get("four_layer") == ["overview", "layers", "data", "model",
                                        "results"] and
                h.get("model_execution") == "NOT_AUTHORIZED" and
                h.get("prediction") is None, h.get("app_version"))

        st, idx, _ = get(V6)
        routes = {r["path"] for r in idx.get("routes", [])}
        T.check("V02", "v0.6 route index lists all four layers",
                st == 200 and len(routes) >= 16 and
                any(r.startswith(V6 + "/layers") for r in routes) and
                any(r.startswith(V6 + "/results") for r in routes), len(routes))

        # ---------------- overview --------------------------------------
        st, ov, _ = get(V6 + "/overview?dataset=SYRDARYA")
        case = ov["research"]["case_reach"]
        browse = ov["browse"]
        T.check("V03", "overview: fixed reach 16037->16039 shown separately "
                       "from the browsed station",
                st == 200 and case["upstream"] == "SYRDARYA:16037" and
                case["downstream"] == "SYRDARYA:16039" and
                "固定研究河段" in case["role"] and
                "当前浏览测站" in browse["role"] and
                browse["station"] != case["id"], (case["id"], browse["station"]))
        hg = ov["hydrograph"]
        T.check("V04", "overview hydrograph: observed only, qsim null",
                hg["kind"] == "OBSERVED_ONLY" and hg["qsim"] is None and
                hg["qsim_status"] == "NOT_GENERATED" and
                hg["n_observed"] > 0 and "尚未生成" in hg["notice"],
                hg["kind"])
        T.check("V05", "overview model block: NOT_AUTHORIZED / NOT_EVALUATED / "
                       "0 trained",
                ov["model"]["model_execution"] == "NOT_AUTHORIZED" and
                ov["model"]["evaluation_status"] == "NOT_EVALUATED" and
                ov["model"]["trained_models"] == 0 and
                ov["model"]["qsim_available"] is False)
        T.check("V06", "overview lists five entries (overview+four layers)",
                [e["key"] for e in ov["entries"]] ==
                ["overview", "layers", "data", "model", "results"])

        st, oml, _ = get(V6 + "/overview?dataset=LAMAHCE&station=LAMAHCE:58")
        T.check("V07", "LamaH overview: no authorized series, metadata only",
                st == 200 and oml["hydrograph"]["kind"] == "NOT_AVAILABLE" and
                oml["hydrograph"]["qsim"] is None and
                oml["data_summary"]["stations_total"] == 882)

        # dataset isolation
        st, er, _ = get(V6 + "/overview?dataset=SYRDARYA&station=LAMAHCE:58")
        T.check("V08", "dataset namespaces never mix (SYR + LAMAHCE id -> 400)",
                st == 400, st)
        st, er2, _ = get(V6 + "/overview?dataset=LAMAHCE&station=SYRDARYA:16037")
        T.check("V09", "dataset namespaces never mix (LAMAHCE + SYR id -> 404)",
                st == 404, st)

        # ---------------- spatial layers --------------------------------
        st, ly, _ = get(V6 + "/layers?dataset=LAMAHCE")
        groups = {g["key"] for g in ly["groups"]}
        T.check("V10", "layer tree has the five required groups",
                st == 200 and groups == {"river_network", "dem",
                                         "hydro_stations", "met_stations",
                                         "admin"}, groups)
        s = ly["summary"]
        T.check("V11", "display-ready and hydrologically-certified are separate",
                s["display_ready"] >= 1 and s["hydrologically_certified"] == 0 and
                "不可混为一谈" in ly["rule_note"], s)
        gauges = [l for g in ly["groups"] for l in g["layers"]
                  if l["id"] == "hs_gauges"][0]
        T.check("V12", "real station points: GIS_DISPLAY_READY but only "
                       "GRAPH_TENTATIVE hydrology",
                gauges["display_status"] == "GIS_DISPLAY_READY" and
                gauges["hydrologic_status"] == "GRAPH_TENTATIVE" and
                gauges["feature_count"] == 882)

        st, lf, _ = get(V6 + "/layers/features?dataset=LAMAHCE&layer=hs_gauges")
        T.check("V13", "station layer returns real projected points (882)",
                st == 200 and lf["n_features"] == 882 and
                lf["collection"]["crs"]["properties"]["name"] == "EPSG:3035" and
                len(lf["collection"]["features"][0]["geometry"]["coordinates"]) == 2)

        st, lys, _ = get(V6 + "/layers?dataset=SYRDARYA")
        ss = lys["summary"]
        T.check("V14", "Syr Darya: nothing drawable, CRS pending, no fake geometry",
                ss["display_ready"] == 0 and ss["not_available"] ==
                ss["layers_total"] and lys["crs"] == "GIS_PENDING")
        st, lfs, _ = get(V6 + "/layers/features?dataset=SYRDARYA&layer=sr_gauges")
        T.check("V15", "unavailable layer returns empty FeatureCollection + reason",
                st == 200 and lfs["collection"]["features"] == [] and
                lfs["display_status"] == "GIS_DISPLAY_NOT_AVAILABLE" and
                "invent" in lfs["reason"])

        # ---------------- data layer ------------------------------------
        st, cat, _ = get(V6 + "/data/catalog?dataset=SYRDARYA")
        mods = {m["id"]: m for m in cat["modules"]}
        T.check("V16", "four data modules with real availability states",
                st == 200 and set(mods) == {"station_history", "remote_sensing",
                                            "yearbook", "literature"} and
                mods["station_history"]["status"] == "AVAILABLE" and
                mods["yearbook"]["status"] == "INTERFACE_ONLY" and
                mods["literature"]["status"] == "INTERFACE_ONLY")

        st, yb, _ = get(V6 + "/data/yearbooks")
        T.check("V17", "yearbook: interface only, zero invented entries",
                st == 200 and yb["entries"] == [] and
                yb["availability"] == "NOT_READ" and yb["status"] ==
                "INTERFACE_ONLY")
        st, lit, _ = get(V6 + "/data/literature")
        T.check("V18", "literature: no unverifiable paper entries generated",
                st == 200 and lit["entries"] == [] and
                lit["verified_entries"] == 0 and "不生成论文信息" in lit["policy"])

        st, cov, _ = get(V6 + "/data/coverage?dataset=SYRDARYA")
        statuses = set()
        for r in cov["station_rows"]:
            for c in r["cells"]:
                statuses.add(c["status"])
        T.check("V19", "coverage matrix: 40 stations x 11 discrete years, gaps "
                       "explicit",
                st == 200 and len(cov["station_rows"]) == 40 and
                len(cov["years"]) == 11 and
                {"NO_RECORD_YEAR"} <= statuses and len(statuses) >= 2, statuses)
        T.check("V20", "coverage: no record year has present == 0 (no fill)",
                all(c["present"] == 0 for r in cov["station_rows"]
                    for c in r["cells"] if c["status"] == "NO_RECORD_YEAR"))

        st, rs, _ = get(V6 + "/data/remote-sensing?dataset=SYRDARYA&year=2010")
        T.check("V21", "remote sensing: 7 circles, missing months listed, "
                       "no zero substitution",
                st == 200 and len(rs["circles"]) == 7 and
                all("missing_months" in c for c in rs["circles"]) and
                "不是 0" in rs["missing_policy"])

        # ---------------- model layer -----------------------------------
        st, reg, _ = get(V6 + "/model/registry")
        T.check("V22", "model registry: 3 defined baselines, none implemented/"
                       "trained/evaluated",
                st == 200 and len(reg["registry"]) == 3 and
                all(not m["implemented"] and not m["trained"] and
                    not m["evaluated"] for m in reg["registry"]) and
                all(m["status"] == "DEFINED_ONLY" for m in reg["registry"]))
        T.check("V23", "roadmap models are NOT_IMPLEMENTED (no fake architecture)",
                all(r["status"] == "NOT_IMPLEMENTED"
                    for r in reg["roadmap"]) and len(reg["roadmap"]) >= 6)

        st, cf, _ = get(V6 + "/model/config?model=SYR-B1")
        T.check("V24", "model config exposes reproducible parameters",
                st == 200 and cf["config"]["model"] == "SYR-B1" and
                cf["config"]["time_scale"] == "MONTH" and
                "regularization" in cf["config"] and
                "random_seed" in cf["config"] and
                cf["config"]["train_years"])

        cfg = {"config": {
            "model": "SYR-B1", "dataset": "SYRDARYA",
            "target": "SYRDARYA:16039", "inputs": ["Q_up_monthly_mean"],
            "output": "SYRDARYA:16039", "time_scale": "MONTH",
            "lag_months": 1, "train_years": [2003, 2004, 2005],
            "test_years": [2007], "regularization": 0.1, "random_seed": 7,
            "data_version": "SYR-DQ-0.5.0", "feature_version": "v0.6",
            "task": "MISSING_RECONSTRUCTION", "notes": "suite"}}
        st, saved, _ = _server.get(base, V6 + "/model/configs", "POST",
                                   {"Content-Type": "application/json"},
                                   json.dumps(cfg).encode())
        T.check("V25", "config JSON saved (not executed)",
                st == 200 and saved.get("saved") is True and
                saved.get("executed") is False and
                os.path.isfile(os.path.join(APP, "var", "model_configs",
                                            saved.get("file", ""))),
                saved.get("file"))

        bad = json.loads(json.dumps(cfg))
        bad["config"]["inputs"] = ["Q_down_monthly_mean"]
        bad["config"]["task"] = "ZERO_TARGET_Q_CALIBRATION"
        st, lv, _ = _server.get(base, V6 + "/model/configs", "POST",
                                {"Content-Type": "application/json"},
                                json.dumps(bad).encode())
        T.check("V26", "lineage violation rejected (target-Q derived feature)",
                st == 400 and lv.get("error") == "LEAKAGE_VIOLATION", st)

        bad2 = json.loads(json.dumps(cfg))
        bad2["config"]["evil"] = 1
        st, _, _ = _server.get(base, V6 + "/model/configs", "POST",
                               {"Content-Type": "application/json"},
                               json.dumps(bad2).encode())
        T.check("V27", "unknown config field rejected", st == 400, st)

        st, ex, _ = get(V6 + "/model/execute")
        T.check("V28", "GET model/execute refused 403 + prediction null",
                st == 403 and ex.get("prediction") is None and
                ex.get("error") == "NOT_AUTHORIZED", st)
        st, ex2, _ = _server.get(base, V6 + "/model/execute", "POST", {}, b"{}")
        T.check("V29", "POST model/execute refused 403 (frontend cannot bypass)",
                st == 403 and ex2.get("prediction") is None, st)
        st, ex3, _ = get("/api/vhs/predict")
        T.check("V30", "legacy /api/vhs/predict still 403", st == 403, st)

        st, wf, _ = get(V6 + "/model/workflow")
        run_step = [s for s in wf["steps"] if s["key"] == "run"][0]
        T.check("V31", "workflow: run step is BLOCKED by the API gate",
                st == 200 and len(wf["steps"]) == 8 and
                run_step["status"] == "BLOCKED", run_step["status"])

        # ---------------- results layer ---------------------------------
        st, res, _ = get(V6 + "/results/station?station=SYRDARYA:16037")
        T.check("V32", "results station: Qobs only, qsim/PI/model_run null",
                st == 200 and res["qsim"] is None and
                res["prediction_interval"] is None and
                res["model_run"] is None and
                res["qobs"]["n_defined"] > 0)
        T.check("V33", "missing cells are null (never 0) and keep status codes",
                all(p["value"] is None for p in res["observations"]
                    if p["status"] in ("MISSING", "NO_RECORD_YEAR")) and
                {"MISSING", "NO_RECORD_YEAR"} & {p["status"] for p in
                                                 res["observations"]})

        st, ev, _ = get(V6 + "/results/evaluation?station=SYRDARYA:16039")
        T.check("V34", "evaluation: NSE/KGE/RMSE/MAE/PBIAS all null + "
                       "NOT_EVALUATED",
                st == 200 and [m["key"] for m in ev["metrics"]] ==
                ["NSE", "KGE", "RMSE", "MAE", "PBIAS"] and
                all(m["value"] is None and m["status"] == "NOT_EVALUATED"
                    for m in ev["metrics"]) and
                ev["status"] == "NOT_EVALUATED")
        T.check("V35", "evaluation records required provenance fields (all null "
                       "but present)",
                all(k in ev["provenance_requirements"] for k in
                    ("model_version", "dataset_version", "period",
                     "common_sample_ids")))
        raw = json.dumps(ev)
        T.check("V36", "no numeric fake metric anywhere in evaluation payload",
                '"value": null' in raw and '"n_samples": null' in raw)

        st, sp, _ = get(V6 + "/results/spatial?dataset=SYRDARYA")
        T.check("V37", "spatial results: prediction layers empty, contract given",
                st == 200 and sp["prediction_layers"] == [] and
                sp["status"] == "PREDICTION_LAYER_NOT_AVAILABLE" and
                "qsim" in sp["contract"]["properties"])

        st, rpt, _ = get(V6 + "/results/report?station=SYRDARYA:16037")
        md = rpt["markdown"]
        T.check("V38", "report: real observations + explicit not-executed model",
                st == 200 and "NOT_AUTHORIZED" in md and
                "模拟序列：未生成" in md and "NOT_EVALUATED" in md and
                "SHA-256" in md and
                set(rpt["not_executed_sections"]) ==
                {"training", "evaluation", "simulation", "uncertainty"})
        T.check("V39", "report hash/version section present",
                rpt["sections"]["snapshot_id"].startswith("syr-snap-") and
                rpt["sections"]["model"]["prediction"] is None)

        st, evd, _ = get(V6 + "/evidence?size=5&severity=ERROR")
        T.check("V40", "evidence page: filterable QC flags + file hashes",
                st == 200 and len(evd["flags"]) == 5 and
                all(f["severity"] == "ERROR" for f in evd["flags"]) and
                len(evd["files"]) == 6 and
                all(len(f["sha256"]) == 64 for f in evd["files"]))

        # ---------------- alpha scenarios (fixed vs scenario residual) ---
        st, w1, _ = get("/api/vhs/datasets/SYRDARYA/water-balance?year=2010"
                        "&width_km=3&alpha=0.6")
        st2, w2, _ = get("/api/vhs/datasets/SYRDARYA/water-balance?year=2010"
                         "&width_km=3&alpha=0.9")
        r1, r2 = w1["residuals"], w2["residuals"]
        T.check("V41", "alpha switch: fixed source residual unchanged, scenario "
                       "residual moves",
                abs(r1["fixed_source_record"]["residual_file_value"] -
                    r2["fixed_source_record"]["residual_file_value"]) < 1e-12 and
                abs(r1["selected_scenario"]["residual_file_formula_with_"
                    "selected_intake"] -
                    r2["selected_scenario"]["residual_file_formula_with_"
                    "selected_intake"]) > 1e-9 and
                "固定" in r1["fixed_source_record"]["label"])

        # ---------------- static security (no regression) ---------------
        probes = [("/static/../server.py", 400), ("/static/E:../server.py", 400),
                  ("/static/%2e%2e/server.py", 400), ("/static/nope.js", 404),
                  ("/static/styles.css", 200)]
        for i, (probe, need) in enumerate(probes):
            st, _, _ = get(probe)
            T.check("V4%d" % (2 + i), "static guard: %s -> %d" % (probe, need),
                    st == need, st)
    finally:
        _server.stop(proc)
    return T.save()


if __name__ == "__main__":
    raise SystemExit(main())
