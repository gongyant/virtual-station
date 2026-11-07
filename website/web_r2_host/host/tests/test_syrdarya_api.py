"""
tests/test_syrdarya_api.py -- real-data HTTP tests for VHS v0.5 (flows A-H).
Starts its own server on a free 127.0.0.1 port, or use --base.
"""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
RESULTS = []


def call(base, path, method="GET"):
    req = urllib.request.Request(base + path, method=method,
                                 data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw, st, ct = r.read(), r.status, r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw, st, ct = e.read(), e.code, e.headers.get("Content-Type", "")
    try:
        return st, json.loads(raw.decode("utf-8")), ct
    except Exception:                                   # noqa: BLE001
        return st, raw.decode("utf-8", "replace"), ct


def check(name, cond, detail=""):
    RESULTS.append({"test": name, "passed": bool(cond),
                    "detail": "" if cond else str(detail)[:300]})
    print("  %-70s %s %s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else str(detail)[:160]))


def run(b):
    D = "/api/vhs/datasets"
    S = D + "/SYRDARYA"
    st, h, _ = call(b, "/api/vhs/health")
    check("H01 health app_version 0.6.0, both datasets OK",
          h.get("app_version") == "0.6.0" and
          h.get("datasets") == {"LAMAHCE": "OK", "SYRDARYA": "OK"}, h)

    # A: LamaH-CE unchanged
    st, s58, _ = call(b, "/api/vhs/stations/58")
    check("A01 LAMAHCE station 58 Huben, HAS_CANDIDATES 573",
          st == 200 and s58.get("name") == "Huben" and
          s58.get("n_candidates") == 573)
    st, a58, _ = call(b, "/api/vhs/stations/58/audit")
    check("A02 LAMAHCE audit still GEOMETRY_VERIFIED=0",
          a58["authorization"]["GEOMETRY_VERIFIED"] == 0)
    st, ls, _ = call(b, D + "/LAMAHCE/stations?q=Huben")
    check("A03 namespaced LAMAHCE search -> LAMAHCE:58",
          "LAMAHCE:58" in [r["uid"] for r in ls.get("results", [])])

    # B: dataset switch + stations
    st, ds, _ = call(b, D)
    ids = [d["id"] for d in ds.get("datasets", [])]
    check("B01 /datasets lists LAMAHCE and SYRDARYA", ids == ["LAMAHCE",
                                                             "SYRDARYA"], ids)
    check("B02 cross-dataset matching disabled",
          "DISABLED" in ds.get("cross_dataset_matching", ""))
    syr = ds["datasets"][1]
    check("B03 SYRDARYA crs GIS_PENDING (EPSG:3035 not applied)",
          syr["crs"] == "GIS_PENDING")
    st, sl, _ = call(b, S + "/stations")
    stations = {x["code"]: x for x in sl.get("stations", [])}
    check("B04 40 Syr Darya stations, recomputed", len(stations) == 40,
          len(stations))
    check("B05 16037/16039 flagged as teacher case reach",
          stations["16037"]["is_case_reach"] and
          stations["16039"]["is_case_reach"] and
          "老师" in sl["case_reach"]["label"])
    check("B06 every station uid namespaced, coords GIS_PENDING",
          all(x["uid"].startswith("SYRDARYA:") and
              x["coordinate_status"] == "GIS_PENDING"
              for x in stations.values()))

    # C: real monthly flow
    st, q, _ = call(b, S + "/discharge?station=SYRDARYA:16037&year=2003")
    check("C01 16037/2003 monthly discharge 200, 12 months",
          st == 200 and len(q["months"]) == 12)
    check("C02 16037/2003 Jan mean = 546.0 (source value)",
          q["months"][0]["mean"] == 546.0)
    check("C03 discharge unit reported UNKNOWN", q["unit"] == "UNKNOWN")
    man = json.load(open(os.path.join(APP, "manifest",
                                      "source_manifest.json"),
                         encoding="utf-8"))
    pins = {f["file"]: f["sha256"] for f in man["files"]}
    check("C04 response provenance sha256 equals pinned manifest",
          all(p["sha256"] == pins[p["file"]] for p in q["provenance"]))
    st, q2, _ = call(b, S + "/discharge?station=16039&year=2014")
    check("C05 2014 min placeholders marked SUSPECT, means OBSERVED",
          all(m["min_status"] == "SUSPECT" for m in q2["months"]) and
          all(m["mean_status"] == "OBSERVED" for m in q2["months"]))
    st, an, _ = call(b, S + "/discharge?station=16037&view=annual")
    yr = {y["year"]: y for y in an["years"]}
    check("C06 16037 annual: 11 years, 2003 W missing, 2008 +20% flagged",
          len(yr) == 11 and yr[2003]["status"] == "W_MISSING_IN_SOURCE" and
          yr[2008]["status"] == "W_INCONSISTENT")
    check("C07 annual W source value not overwritten",
          yr[2008]["W_source"] == 8230.0)

    # D: synced month
    st, av, _ = call(b, S + "/availability?year=2016&month=7")
    check("D01 availability 2016-07: Q both AVAILABLE, met COMPLETE",
          av["discharge_mean"] == {"16037": "AVAILABLE",
                                   "16039": "AVAILABLE"} and
          av["meteorology"] == "COMPLETE")
    check("D02 availability 2016-07 lists circles + KZDAM sites",
          av["circles_observed"] == list("ABCDEFG") and
          av["kzdam_observed"] == ["KC", "KD", "KS", "KU"])
    st, mm, _ = call(b, S + "/meteorology?year=2016")
    check("D03 met monthly Feb 2016 = 29 days (leap year)",
          mm["months"][1]["days_in_month"] == 29 and mm["months"][1]["complete"])
    st, md, _ = call(b, S + "/meteorology?year=2016&granularity=daily&month=7")
    check("D04 met daily July has 31 rows", len(md["days"]) == 31)
    st, rs, _ = call(b, S + "/remote-sensing?year=2016&month=7")
    check("D05 RS 2016-07: 7 circles km2, KZDAM unit UNKNOWN",
          len(rs["circles"]) == 7 and
          all(c["unit"] == "km2" for c in rs["circles"]) and
          all(k["unit"] == "UNKNOWN" for k in rs["kzdam"]))
    st, rs2, _ = call(b, S + "/remote-sensing?year=2003&month=2")
    check("D06 empty circle month -> NO_ROW/NO_OBSERVATION, value null",
          all(c["value"] is None and c["value_status"] in
              ("NO_ROW", "NO_OBSERVATION") for c in rs2["circles"]))
    st, av5, _ = call(b, S + "/availability?year=2005&month=7")
    check("D07 2005-07: discharge NO_RECORD_YEAR (no interpolation)",
          set(av5["discharge_mean"].values()) == {"NO_RECORD_YEAR"})

    # E: water balance + intake scenario
    st, wb, _ = call(b, S + "/water-balance?year=2010&alpha=0.75")
    check("E01 WB 2010 alpha 0.75 selected scenario 2.304",
          st == 200 and abs(wb["selected_scenario"]["value"] - 2.30421835802231)
          < 1e-9)
    check("E02 scenario is Q-derived, not a measurement",
          wb["selected_scenario"]["q_derived"] and
          not wb["selected_scenario"]["is_measurement"] and
          "SYRDARYA:16037" in wb["selected_scenario"]["derived_from"])
    check("E03 disclaimer states inversion / not measured",
          "不是实测取水量" in wb["disclaimer"])
    check("E04 three alpha scenarios returned",
          sorted(s["alpha"] for s in wb["intake_scenarios"]) ==
          [0.6, 0.75, 0.9])
    st, wb5, _ = call(b, S + "/water-balance?year=2010&width_km=5&alpha=0.9")
    check("E05 width 5 km -> area 2680 km2", wb5["balance"]["area_km2"] == 2680)
    check("E06 residual sign convention exposed in checks",
          wb["checks"]["residual_matches_file_convention"] is True)

    # F: errors, no fake data
    errs = [
        ("F01 year without record -> 404 DATA_NOT_FOUND",
         S + "/discharge?station=16037&year=2005", 404, "DATA_NOT_FOUND"),
        ("F02 LAMAHCE id on SYRDARYA -> 400 NAMESPACE_MISMATCH",
         S + "/discharge?station=LAMAHCE:58&year=2003", 400,
         "NAMESPACE_MISMATCH"),
        ("F03 missing station -> 400 MISSING_PARAM",
         S + "/discharge?year=2003", 400, "MISSING_PARAM"),
        ("F04 unknown station -> 404 STATION_NOT_FOUND",
         S + "/discharge?station=99999&year=2003", 404, "STATION_NOT_FOUND"),
        ("F05 non-integer year -> 400 BAD_PARAM",
         S + "/discharge?station=16037&year=abc", 400, "BAD_PARAM"),
        ("F06 year out of range -> 400 OUT_OF_RANGE",
         S + "/discharge?station=16037&year=5000", 400, "OUT_OF_RANGE"),
        ("F07 met outside 2003-2024 -> 404",
         S + "/meteorology?year=1990", 404, "DATA_NOT_FOUND"),
        ("F08 daily met without month -> 400",
         S + "/meteorology?year=2010&granularity=daily", 400, "MISSING_PARAM"),
        ("F09 alpha not in {0.6,0.75,0.9} -> 400",
         S + "/water-balance?year=2010&alpha=0.5", 400, "OUT_OF_RANGE"),
        ("F10 WB year absent -> 404",
         S + "/water-balance?year=2005", 404, "DATA_NOT_FOUND"),
        ("F11 flag page > 200 -> 400",
         S + "/data-quality?limit=500", 400, "OUT_OF_RANGE"),
        ("F12 unknown dataset -> 404",
         D + "/FOO/stations", 404, "DATASET_NOT_FOUND"),
        ("F13 no raw/bulk route -> 404", S + "/raw", 404, "NOT_FOUND"),
        ("F14 duplicate param -> 400",
         S + "/discharge?station=16037&station=16039&year=2003", 400,
         "BAD_PARAM"),
    ]
    for name, path, code, err in errs:
        st, body, _ = call(b, path)
        check(name, st == code and isinstance(body, dict) and
              body.get("error") == err and body.get("prediction") is None,
              (st, body))
    st, body, _ = call(b, S + "/discharge?station=16037&year=2005")
    check("F15 404 body carries no month values",
          "months" not in body and body.get("available_years"))
    st, body, _ = call(b, "/static/..%2F..%2Fmanifest%2Fsource_manifest.json")
    check("F16 static path traversal blocked", st in (400, 404), st)

    # G: prediction gate
    for name, path, m in [
            ("G01 GET SYRDARYA/predict -> 403", S + "/predict", "GET"),
            ("G02 POST SYRDARYA/predict -> 403", S + "/predict", "POST"),
            ("G03 POST legacy /api/vhs/predict -> 403", "/api/vhs/predict",
             "POST"),
            ("G04 GET LAMAHCE/predict -> 403", D + "/LAMAHCE/predict", "GET")]:
        st, body, _ = call(b, path, m)
        check(name, st == 403 and body.get("prediction") is None and
              body.get("status") == "NOT_AUTHORIZED", (st, body))
    st, rr, _ = call(b, S + "/research")
    check("G05 research: 3 baselines, execution NOT_AUTHORIZED",
          [x["baseline"] for x in rr["baselines"]] ==
          ["SYR-B0", "SYR-B1", "SYR-B2"] and
          all(x["prediction"] is None and x["execution"] == "NOT_AUTHORIZED"
              for x in rr["baselines"]))
    st, dq, _ = call(b, S + "/data-quality?limit=5")
    check("G06 permissions: bulk_export DISABLED, prediction null",
          dq["permissions"]["bulk_export"] == "DISABLED" and
          dq["permissions"]["prediction"] is None)
    check("G07 data-quality pages flags (5 of many)",
          len(dq["flags"]) == 5 and dq["flags_total"] > 5)

    # H: provenance + hashes
    check("H02 data-quality lists 6 read-only files",
          len(dq["files"]) == 6 and
          all(f["access"] == "READ_ONLY" for f in dq["files"]))
    src = man["source_dir"]
    same = all(hashlib.sha256(open(os.path.join(src, f["file"]), "rb")
                              .read()).hexdigest() == f["sha256"]
               for f in man["files"])
    check("H03 teacher CSV SHA-256 unchanged vs pinned manifest", same)
    st, g, _ = call(b, S + "/gis")
    check("H04 GIS_PENDING, no coordinates, verification list given",
          g["gis_status"] == "GIS_PENDING" and
          g["station_coordinates"] == "NOT_AVAILABLE" and
          len(g["next_inputs_to_verify"]) >= 4)
    st, html, ct = call(b, "/")
    check("H05 index serves v0.6 four-layer shell with dataset switch",
          st == 200 and "dsSwitch" in html and "v0.6" in html)
    st, js, ct = call(b, "/static/app.js")
    check("H06 app.js served", st == 200 and "VHS" in js)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    a = ap.parse_args()
    proc, base = None, a.base
    if not base:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        base = "http://127.0.0.1:%d" % port
        proc = subprocess.Popen([sys.executable, "-B",
                                 os.path.join(APP, "server.py"),
                                 "--port", str(port)], cwd=APP,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.STDOUT)
        for _ in range(150):
            try:
                urllib.request.urlopen(base + "/api/vhs/health", timeout=1)
                break
            except Exception:                           # noqa: BLE001
                time.sleep(0.2)
    print("== VHS v0.5 Syr Darya API tests against %s ==" % base)
    t0 = time.time()
    try:
        run(base)
    finally:
        if proc:
            proc.terminate()
            proc.wait(timeout=10)
    p = sum(r["passed"] for r in RESULTS)
    print("\n%d/%d passed in %.2fs" % (p, len(RESULTS), time.time() - t0))
    with open(os.path.join(APP, "logs", "test_syrdarya_api.json"), "w",
              encoding="utf-8") as f:
        json.dump({"base": base, "passed": p, "total": len(RESULTS),
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "tests": RESULTS}, f, ensure_ascii=False, indent=1)
    return 0 if p == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
