"""
tests/test_gis_synthetic.py  --  VHS v0.4 GIS adapter synthetic tests
=====================================================================

Pure synthetic tests (no real GIS file, no network, no Q). They validate:
  * the EPSG:3035 <-> EPSG:4326 transform (origin + round-trip + monotonic)
  * the geometry primitives (point-in-polygon, area, length, distance)
  * the field-safety screener (hard-reject of Q-like columns)
  * the layer registry / staging status logic

Run:
    python tests/test_gis_synthetic.py
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)

import gis_adapter as G  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("  %-58s %s %s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else detail))
    return bool(cond)


def main():
    # ---- transform: projection origin --------------------------------
    x, y = G.laea_forward(10.0, 52.0)
    check("G01 forward(10,52) == projection origin (4321000,3210000)",
          abs(x - 4321000.0) < 0.5 and abs(y - 3210000.0) < 0.5, (x, y))

    lon, lat = G.laea_inverse(4321000.0, 3210000.0)
    check("G02 inverse(origin) == (10,52)",
          abs(lon - 10.0) < 1e-6 and abs(lat - 52.0) < 1e-6, (lon, lat))

    # ---- transform: round-trip over European extent ------------------
    worst = 0.0
    for lon0 in range(-10, 41, 5):
        for lat0 in range(35, 71, 5):
            X, Y = G.laea_forward(lon0, lat0)
            lo, la = G.laea_inverse(X, Y)
            worst = max(worst, abs(lo - lon0), abs(la - lat0))
    check("G03 round-trip lon/lat over Europe within 1e-6 deg",
          worst < 1e-6, "worst=%.3e" % worst)

    # ---- transform: metre round-trip on the real gauge extent --------
    worst_m = 0.0
    for (gx, gy) in [(4394910.0, 2659401.0), (4318987.0, 2690449.0),
                     (4768980.0, 2644942.0), (4192433.0, 2596838.0),
                     (4917967.0, 3021806.0)]:
        lo, la = G.laea_inverse(gx, gy)
        X, Y = G.laea_forward(lo, la)
        worst_m = max(worst_m, math.hypot(X - gx, Y - gy))
    check("G04 metre round-trip on real gauge coords < 1 mm",
          worst_m < 1e-3, "worst=%.3e m" % worst_m)

    # ---- transform: monotonic sanity (east -> larger x) --------------
    xa, _ = G.laea_forward(5.0, 50.0)
    xb, _ = G.laea_forward(15.0, 50.0)
    _, ya = G.laea_forward(10.0, 45.0)
    _, yb = G.laea_forward(10.0, 55.0)
    check("G05 east->+x and north->+y (locally monotonic)",
          xb > xa and yb > ya, (xb - xa, yb - ya))

    # ---- geometry primitives -----------------------------------------
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    check("G06 point_in_polygon inside/outside",
          G.point_in_polygon(5, 5, sq) and not G.point_in_polygon(15, 5, sq))
    check("G07 polygon_area square == 100", abs(G.polygon_area(sq) - 100) < 1e-9,
          G.polygon_area(sq))
    check("G08 polyline_length 3-4-5 == 5",
          abs(G.polyline_length([(0, 0), (3, 4)]) - 5) < 1e-9)
    check("G09 seg_distance point-to-segment",
          abs(G.seg_distance(5, 3, 0, 0, 10, 0) - 3) < 1e-9)
    check("G10 point_to_polyline_distance picks nearest segment",
          abs(G.point_to_polyline_distance(5, 2, [(0, 0), (10, 0), (10, 10)])
              - 2) < 1e-9)
    check("G11 bbox", G.bbox([(1, 2), (5, -1), (3, 9)]) == (1, -1, 5, 9))

    # ---- overlap diagnostic ------------------------------------------
    a = [(0, 0), (10, 0), (10, 10), (0, 10)]
    b = [(5, 5), (15, 5), (15, 15), (5, 15)]
    ov = G.overlap_ratio(a, b, samples=200)
    check("G12 overlap_ratio of two half-overlapping squares ~0.25",
          0.20 < ov < 0.30, "ov=%.3f" % ov)
    check("G13 overlap_ratio disjoint == 0",
          G.overlap_ratio(a, [(20, 20), (30, 20), (30, 30), (20, 30)], 64) == 0)

    # ---- field safety ------------------------------------------------
    ad = G.GISAdapter(r"E:\VHS_WorkBuddy_S1T_Sandbox")
    ok, bad = ad.screen_dbf_header("RiverATLAS",
                                   ["HYRIV_ID", "NEXT_DOWN", "DIS_AV_CMS"])
    check("G14 field screener rejects DIS_AV_CMS (Q-derived)",
          (not ok) and "dis_av_cms" in bad, bad)
    ok2, bad2 = ad.screen_dbf_header(
        "RiverATLAS", ["HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM",
                       "DIST_DN_KM", "UPLAND_SKM"])
    check("G15 field screener accepts the 6-column whitelist", ok2, bad2)
    ok3, bad3 = ad.screen_dbf_header("Gauges", ["ID", "govnr", "Q5", "q_mean"])
    check("G16 field screener rejects Q5 / q_mean", not ok3 and len(bad3) == 2,
          bad3)

    # ---- layer registry / staging ------------------------------------
    st = ad.status()
    check("G17 adapter reports 0/14 layers staged in Stage A",
          st["layers_staged"] == 0 and st["layers_total"] == 14,
          (st["layers_staged"], st["layers_total"]))
    check("G18 adapter data_mode == STAGE_A_NO_GIS, checks NOT_RUN",
          st["data_mode"] == "STAGE_A_NO_GIS" and
          st["geometry_checks"] == "NOT_RUN")
    check("G19 expected CRS is EPSG:3035",
          st["expected_crs_epsg"] == 3035)
    check("G20 RiverATLAS whitelist is exactly the 6 approved columns",
          G.FIELD_WHITELIST["RiverATLAS"] ==
          ["HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM", "DIST_DN_KM",
           "UPLAND_SKM"])
    check("G21 Basins_A != Basins_B (roles kept distinct)",
          G.FIELD_WHITELIST.get("Basins_A") is not None and
          any(l[0] == "Basins_A" and l[1] == "total_upstream_catchment"
              for l in G.LAYERS) and
          any(l[0] == "Basins_B" and l[1] == "intermediate_catchment"
              for l in G.LAYERS))
    check("G22 every declared layer path is sandbox-relative (no abs path)",
          all(not os.path.isabs(l[2]) for l in G.LAYERS))

    # ---- shapefile reader must refuse when not staged ----------------
    try:
        ad.read_layer("RiverATLAS")
        raised = False
    except G.LayerNotStagedError:
        raised = True
    check("G23 read_layer raises LayerNotStagedError when unstaged", raised)

    n = len(RESULTS)
    passed = sum(1 for _, ok in RESULTS if ok)
    print("\n%d/%d synthetic GIS tests passed" % (passed, n))
    import json, time, platform, sys
    from pathlib import Path as _P
    _log = _P(__file__).resolve().parent.parent / "logs"
    _log.mkdir(exist_ok=True)
    (_log / "test_gis_synthetic.json").write_text(json.dumps({
        "suite": "test_gis_synthetic", "total": n, "PASS": passed,
        "FAIL": n - passed, "SKIP": 0,
        "run_on": "%s %s / Python %s" % (platform.node(), platform.system(),
                                          sys.version.split()[0]),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "tests": [{"id": "G%02d" % (i+1), "status": "PASS" if ok else "FAIL"}
                   for i, (_, ok) in enumerate(RESULTS)]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return 0 if passed == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
