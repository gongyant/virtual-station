"""
tests/test_api.py  --  VHS v0.3 HTTP integration tests

Runs the real server as a subprocess on a free local port and exercises the
public API with urllib. No network egress beyond 127.0.0.1.

    python tests/test_api.py
    python tests/test_api.py --base http://127.0.0.1:8771
"""

import argparse
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
LOGDIR = os.path.join(APP, "logs")
os.makedirs(LOGDIR, exist_ok=True)

RESULTS = []


def _get(base, path, expect=200, method="GET"):
    url = base.rstrip("/") + path
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            status = r.status
            ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raw, status, ctype = e.read(), e.code, e.headers.get(
            "Content-Type", "")
    body = None
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:                                   # noqa: BLE001
        body = raw.decode("utf-8", "replace")
    return status, body, ctype


def n_eval_pool_is_consistent(pool, no_cand, has_cand):
    return pool is not None and pool == no_cand + has_cand


def check(name, cond, detail=""):
    RESULTS.append({"test": name, "passed": bool(cond), "detail": str(detail)})
    print("  %-64s %s %s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else detail))
    return bool(cond)


def run(base):
    t0 = time.time()

    # ---- version / health (v0.3 new) ---------------------------------
    st, h, _ = _get(base, "/api/vhs/health")
    check("T01 health 200 + status ok", st == 200 and h.get("status") == "ok",
          (st, h))
    check("T02 health carries app_version 0.6.0",
          h.get("app_version") == "0.6.0", h.get("app_version"))
    check("T03 health carries build_id", bool(h.get("build_id")),
          h.get("build_id"))
    check("T04 health carries dataset_version + manifest sha",
          bool(h.get("dataset_version")) and
          bool(h.get("dataset_manifest_sha256")), h.get("dataset_version"))
    check("T05 health carries server_started_at + data_mode",
          bool(h.get("server_started_at")) and
          h.get("data_mode") == "STATIC_METADATA_ONLY",
          (h.get("server_started_at"), h.get("data_mode")))

    # ---- meta --------------------------------------------------------
    st, m, _ = _get(base, "/api/vhs/meta")
    c = (m or {}).get("counts", {})
    check("T06 meta: 882 stations / 834 edges",
          st == 200 and c.get("stations_total") == 882 and
          c.get("directed_edges") == 834, c)
    check("T07 meta: components 48 / 16 / 25",
          c.get("weak_components_all_882_nodes") == 48 and
          c.get("weak_components_in_graph_850") == 16 and
          c.get("weak_components_basin_stations_859") == 25, c)
    check("T08 meta: snap counters 43 / 42",
          c.get("stations_snap_over_500m") == 43 and
          c.get("stations_snap_not_testable") == 42, c)
    a = (m or {}).get("authorization", {})
    check("T09 meta: NO_GO / NOT_AUTHORIZED / GEOMETRY_VERIFIED=0",
          a.get("MULTISYSTEM_BENCHMARK") == "NO_GO" and
          a.get("MODEL_EXECUTION") == "NOT_AUTHORIZED" and
          a.get("GEOMETRY_VERIFIED") == 0 and a.get("FULLY_ADMITTED") == 0, a)
    check("T10 meta: CRS EPSG:3035 metre",
          (m or {}).get("coordinate_reference", {}).get("epsg") == 3035 and
          (m or {}).get("coordinate_reference", {}).get("unit") == "metre")
    check("T11 meta: app_version 0.6.0 + regions list present",
          m.get("app_version") == "0.6.0" and isinstance(m.get("regions"), list)
          and len(m.get("regions")) > 0, len(m.get("regions", [])))
    n_graph = c.get("stations_in_graph")
    n_not_eval = c.get("stations_not_evaluated")
    n_no_cand = c.get("stations_no_graph_candidate")
    n_cand = c.get("targets_with_candidates")
    check("T11b meta: 4-state counts sum to 882 (87/5/758/32)",
          (882 - n_graph) + n_not_eval + n_no_cand + n_cand == 882 and
          n_cand == 87 and n_no_cand == 5 and
          (882 - n_graph) == 32 and n_not_eval == 758,
          {"not_in_graph": 882 - n_graph, "not_evaluated": n_not_eval,
           "no_graph_candidate": n_no_cand, "has_candidates": n_cand})
    check("T11c meta: qualified tentative pool == 92 (87 W + 5 no-W)",
          c.get("qualified_tentative_targets") == 92 and
          c.get("qualified_tentative_targets") == n_cand + n_no_cand,
          c.get("qualified_tentative_targets"))

    # ---- search / filters (v0.3 new) ---------------------------------
    st, b, _ = _get(base, "/api/vhs/stations?limit=25")
    check("T12 empty search <=25", st == 200 and
          0 < len(b.get("results", [])) <= 25, len(b.get("results", [])))
    st, b, _ = _get(base, "/api/vhs/stations?q=Huben")
    check("T13 search Huben finds 58",
          st == 200 and 58 in [r["id"] for r in b.get("results", [])])
    st, b, _ = _get(base, "/api/vhs/stations?q=&targets_only=1&limit=200")
    check("T14 targets_only=1 returns only stations with candidates",
          st == 200 and all(r["n_candidates"] > 0
                            for r in b.get("results", [])),
          len(b.get("results", [])))
    st, b, _ = _get(base, "/api/vhs/stations?q=&region=Rhine&limit=200")
    check("T15 region filter returns only Rhine",
          st == 200 and all(r["region"] == "Rhine"
                            for r in b.get("results", [])),
          len(b.get("results", [])))
    st, b, _ = _get(base, "/api/vhs/regions")
    check("T16 /regions returns non-empty list",
          st == 200 and len(b.get("regions", [])) > 0)

    # ---- station records --------------------------------------------
    st, s58, _ = _get(base, "/api/vhs/stations/58")
    check("T17 station 58 Huben / Oetztaler Ache / in graph",
          st == 200 and s58.get("name") == "Huben" and
          s58.get("river") == "Oetztaler Ache" and s58.get("in_graph") is True,
          (s58 or {}).get("name"))
    check("T18 station 58 evidence graph TENTATIVE / geometry NOT_RUN",
          s58.get("evidence", {}).get("graph_relations") == "TENTATIVE" and
          s58.get("evidence", {}).get("geometry") == "NOT_RUN")
    check("T19 station 58 candidate_status HAS_CANDIDATES + n=573",
          s58.get("candidate_status") == "HAS_CANDIDATES" and
          s58.get("n_candidates") == 573, s58.get("n_candidates"))
    st, b, _ = _get(base, "/api/vhs/stations/999999", expect=404)
    check("T20 unknown station 404 STATION_NOT_FOUND",
          st == 404 and b.get("error") == "STATION_NOT_FOUND", (st, b))

    # ---- candidate status differentiation ----------------------------
    st, b, _ = _get(base, "/api/vhs/stations?q=523&limit=5")
    s523 = [r for r in b.get("results", []) if r["id"] == 523]
    check("T21 523 candidate_status NOT_IN_GRAPH",
          s523 and s523[0].get("candidate_status") == "NOT_IN_GRAPH",
          s523[0].get("candidate_status") if s523 else "missing")
    st, b, _ = _get(base, "/api/vhs/stations?q=Schruns&limit=10")
    s2 = [r for r in b.get("results", []) if r["id"] == 2]
    check("T22 2 (Schruns) candidate_status NOT_EVALUATED",
          s2 and s2[0].get("candidate_status") == "NOT_EVALUATED",
          s2[0].get("candidate_status") if s2 else "missing")
    st, cd429, _ = _get(base, "/api/vhs/stations/429/candidates")
    check("T23 429 candidate_status NO_GRAPH_CANDIDATE (evaluated, 0 W)",
          cd429.get("candidate_status") == "NO_GRAPH_CANDIDATE",
          cd429.get("candidate_status"))
    st, cd1, _ = _get(base, "/api/vhs/stations/1/candidates")
    check("T23b 1 (Bangs) NOT_EVALUATED (ordinary station, not a target)",
          cd1.get("candidate_status") == "NOT_EVALUATED",
          cd1.get("candidate_status"))
    st, cd432, _ = _get(base, "/api/vhs/stations/432/candidates")
    check("T23c 432 NO_GRAPH_CANDIDATE (qualified tentative target, no W)",
          cd432.get("candidate_status") == "NO_GRAPH_CANDIDATE",
          cd432.get("candidate_status"))

    # ---- network -----------------------------------------------------
    st, n, _ = _get(base, "/api/vhs/stations/58/network")
    check("T24 network 58: up 3 / down 21 / comp 608",
          st == 200 and n.get("upstream_count") == 3 and
          n.get("downstream_count") == 21 and n.get("component_size") == 608,
          (n.get("upstream_count"), n.get("downstream_count")))
    check("T25 network 58 immediate downstream [60]",
          n.get("immediate_downstream") == [60], n.get("immediate_downstream"))
    check("T26 network upstream nodes carry name/x/y (v0.3)",
          all(("name" in x and "x" in x and "y" in x)
              for x in n.get("upstream", [])))
    st, n1, _ = _get(base, "/api/vhs/stations/58/network?depth=1")
    check("T27 depth=1 truncates upstream <=1 hop",
          all(x["hops"] <= 1 for x in n1.get("upstream", [])))
    st, n0, _ = _get(base, "/api/vhs/stations/58/network?depth=0")
    check("T28 depth=0 gives 0 within depth",
          n0.get("upstream_within_depth") == 0 and
          n0.get("downstream_within_depth") == 0)

    # ---- U-T-W linkage (v0.3 new) ------------------------------------
    st, utw58, _ = _get(base, "/api/vhs/stations/58/utw")
    check("T29 utw 58: target + n_upstream=3 + n_w=573",
          utw58.get("target") == 58 and utw58.get("n_upstream") == 3 and
          utw58.get("n_w_candidates") == 573,
          (utw58.get("n_upstream"), utw58.get("n_w_candidates")))
    check("T30 utw 58: upstream entries carry is_direct + coords",
          len(utw58.get("upstream_stations", [])) == 3 and
          all(("is_direct" in u and "x" in u and "y" in u)
              for u in utw58["upstream_stations"]))
    check("T31 utw 58: evidence_grade TENTATIVE",
          utw58.get("evidence_grade") == "TENTATIVE")
    st, utw58w, _ = _get(base, "/api/vhs/stations/58/utw?w=59")
    selw = utw58w.get("selected_w", {})
    check("T32 utw 58?w=59: selected W 59 with name + path info",
          st == 200 and selw.get("w_id") == 59 and
          "common_downstream_nodes" in selw and "w_x" in selw,
          selw.get("w_name"))
    st, utw523, _ = _get(base, "/api/vhs/stations/523/utw")
    check("T33 utw 523: NOT_IN_GRAPH, 0 upstream, 0 W",
          utw523.get("candidate_status") == "NOT_IN_GRAPH" and
          utw523.get("n_upstream") == 0 and utw523.get("n_w_candidates") == 0)
    st, utw1, _ = _get(base, "/api/vhs/stations/1/utw")
    check("T34 utw 1: NOT_EVALUATED (ordinary station)",
          utw1.get("candidate_status") == "NOT_EVALUATED" and
          utw1.get("n_w_candidates") == 0,
          (utw1.get("candidate_status"), utw1.get("n_upstream")))
    st, utw429, _ = _get(base, "/api/vhs/stations/429/utw")
    check("T35 utw 429: NO_GRAPH_CANDIDATE (qualified target, no W)",
          utw429.get("n_w_candidates") == 0 and
          utw429.get("candidate_status") == "NO_GRAPH_CANDIDATE",
          utw429.get("candidate_status"))
    st, utw2, _ = _get(base, "/api/vhs/stations/2/utw")
    check("T35b utw 2: NOT_EVALUATED (in graph, never a target)",
          utw2.get("candidate_status") == "NOT_EVALUATED",
          utw2.get("candidate_status"))

    # ---- audit -------------------------------------------------------
    st, au, _ = _get(base, "/api/vhs/stations/58/audit")
    check("T36 audit 58: 9 PASS / 0 FAIL / 4 NOT_RUN",
          st == 200 and au["counts"]["pass"] == 9 and
          au["counts"]["fail"] == 0 and au["counts"]["not_run"] == 4,
          au["counts"])
    check("T37 audit checks carry Chinese explanation (zh)",
          all("zh" in c for c in au["checks"]) and
          any(c["zh"] for c in au["checks"]))
    check("T38 audit summary_note warns not-certified",
          "do NOT imply scientific certification" in au.get("summary_note", ""))
    geo = [x for x in au["checks"] if x["check"].startswith("geometry")]
    check("T39 audit 4 geometry checks NOT_RUN",
          len(geo) == 4 and all(x["status"] == "NOT_RUN" for x in geo))
    st, a523, _ = _get(base, "/api/vhs/stations/523/audit")
    check("T40 523 audit ISOLATED_OR_UNMAPPED",
          a523.get("audit_state") == "ISOLATED_OR_UNMAPPED")
    st, a758, _ = _get(base, "/api/vhs/stations/758/audit")
    f = set(a758.get("flags", []))
    check("T41 758 flags include group+reach+snap",
          {"GROUP_NATURAL_UNKNOWN", "GROUP_OPERATIONAL_UNKNOWN",
           "REACH_KEY_RIVAT_MISSING", "SNAP_DISTANCE_NOT_TESTABLE"} <= f,
          sorted(f))

    # ---- sentinel year handling (v0.3 fix) ---------------------------
    st, s758, _ = _get(base, "/api/vhs/stations/758")
    check("T42 758 obsend_day is None (sentinel -> UNKNOWN)",
          s758.get("obsend_day") is None, s758.get("obsend_day"))

    # ---- candidates detail -------------------------------------------
    st, cd, _ = _get(base, "/api/vhs/stations/58/candidates")
    check("T43 58 candidates: 573 over 18 confluences",
          cd.get("n_candidates") == 573 and
          cd.get("distinct_confluence_nodes") == 18,
          (cd.get("n_candidates"), cd.get("distinct_confluence_nodes")))
    check("T44 candidate rows TENTATIVE with confluence + coords",
          all(x["evidence"] == "TENTATIVE" and isinstance(x["confluence_node"], int)
              for x in cd["candidates"][:50]) and
          "w_x" in cd["candidates"][0])

    # ---- prediction gate --------------------------------------------
    st, pr, _ = _get(base, "/api/vhs/predict", expect=403)
    check("T45 GET /predict -> 403 NOT_AUTHORIZED prediction null",
          st == 403 and pr.get("status") == "NOT_AUTHORIZED" and
          pr.get("prediction") is None, (st, pr))
    st, pr2, _ = _get(base, "/api/vhs/predict", expect=403, method="POST")
    check("T46 POST /predict -> 403", st == 403 and
          pr2.get("status") == "NOT_AUTHORIZED", st)
    st, ms, _ = _get(base, "/api/vhs/model-status")
    check("T47 /model-status 200 with blocking reasons, no run",
          st == 200 and ms.get("prediction") is None and
          len(ms.get("blocking_reasons", [])) >= 4 and
          ms.get("model_version") is None)

    # ---- value prediction guard (security) ---------------------------
    st, b, _ = _get(base, "/api/vhs/predict?run=1&q=1", expect=403)
    check("T48 /predict ignores query params, stays 403",
          st == 403 and b.get("prediction") is None)

    # ---- export / map / static ---------------------------------------
    st, csv_txt, ctype = _get(base, "/api/vhs/export?what=stations&format=csv")
    lines = [x for x in str(csv_txt).splitlines() if x.strip()]
    check("T49 stations CSV: header + 882 rows",
          st == 200 and len(lines) == 883 and "text/csv" in ctype,
          (len(lines), ctype))
    st, csv2, _ = _get(base, "/api/vhs/export?what=candidates&format=csv")
    check("T50 candidates CSV: header + 36190 rows",
          st == 200 and len([x for x in str(csv2).splitlines()
                             if x.strip()]) == 36191)
    st, mp, _ = _get(base, "/api/vhs/map")
    check("T51 map 882 points EPSG:3035 with candidate_status",
          st == 200 and mp.get("n") == 882 and mp.get("crs") == "EPSG:3035" and
          "candidate_status" in mp["points"][0])
    check("T52 map note mentions no basemap / EPSG metres",
          "no basemap" in (mp.get("note") or "").lower() and
          "metres" in (mp.get("note") or "").lower())
    st, html, ctype = _get(base, "/")
    check("T53 UI served as text/html with v0.6 title",
          st == 200 and "text/html" in ctype and "v0.6" in str(html), ctype)

    # ---- boundary ----------------------------------------------------
    st, b, _ = _get(base, "/api/vhs/stations/0")
    check("T54 station 0 -> 404 sentinel", st == 404, st)
    st, b, _ = _get(base, "/api/vhs/stations/58/nonsense")
    check("T55 unknown subresource 404", st == 404 and
          b.get("error") == "UNKNOWN_SUBRESOURCE", (st, b))
    st, b, _ = _get(base, "/api/vhs/export?what=flows")
    check("T56 export bad what -> 400", st == 400 and
          b.get("error") == "BAD_EXPORT", (st, b))
    st, b, _ = _get(base, "/api/vhs/stations?limit=1&q=Inn")
    check("T57 limit=1 returns exactly 1", len(b.get("results", [])) == 1)
    st, _, _ = _get(base, "/api/vhs/health", method="HEAD")
    check("T58 HEAD /health 200", st == 200, st)

    # ---- five/six station end-to-end ---------------------------------
    used = [58, 21, 429, 523, 758, 1]
    ok = True
    detail = []
    for sid in used:
        s1s, st1, _ = _get(base, "/api/vhs/stations/%d" % sid)
        s2s, st2, _ = _get(base, "/api/vhs/stations/%d/network" % sid)
        s3s, st3, _ = _get(base, "/api/vhs/stations/%d/audit" % sid)
        s4s, st4, _ = _get(base, "/api/vhs/stations/%d/candidates" % sid)
        s5s, st5, _ = _get(base, "/api/vhs/stations/%d/utw" % sid)
        good = (s1s == 200 and s2s == 200 and s3s == 200 and s4s == 200 and
                s5s == 200 and st1.get("id") == sid and st5.get("target") == sid)
        ok = ok and good
        detail.append("%d:%s" % (sid, "ok" if good else "bad"))
    check("T59 six stations 5-endpoint end-to-end", ok, detail)

    # ---- access log --------------------------------------------------
    logp = os.path.join(LOGDIR, "access.log")
    n_lines = sum(1 for _ in open(logp, encoding="utf-8")) \
        if os.path.exists(logp) else 0
    check("T60 access log written", n_lines > 0, n_lines)

    # ==================================================================
    # V0.4 GIS Stage-A tests
    # ==================================================================
    st, g, _ = _get(base, "/api/vhs/gis/status")
    check("T61 gis/status 200, 0/14 staged, STAGE_A_NO_GIS",
          st == 200 and g.get("layers_staged") == 0 and
          g.get("layers_total") == 14 and
          g.get("data_mode") == "STAGE_A_NO_GIS", g.get("data_mode"))
    check("T62 gis/status geometry_checks NOT_RUN + CRS 3035",
          g.get("geometry_checks") == "NOT_RUN" and
          g.get("expected_crs_epsg") == 3035)
    check("T63 gis/status rules_version present",
          bool(g.get("rules_version")), g.get("rules_version"))
    st, gl, _ = _get(base, "/api/vhs/gis/layers")
    names = {l["layer"] for l in gl.get("layers", [])}
    check("T64 gis/layers lists Gauges/Basins_A/Basins_B/RiverATLAS/Impacts",
          st == 200 and {"Gauges", "Basins_A", "Basins_B", "RiverATLAS",
                         "Impacts"} <= names, names)
    riv = [l for l in gl["layers"] if l["layer"] == "RiverATLAS" and
           l["kind"] == "topo_csv"]
    check("T65 RiverATLAS topo CSV whitelist is the 6 approved columns",
          riv and riv[0]["field_whitelist"] ==
          ["HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM", "DIST_DN_KM",
           "UPLAND_SKM"], riv[0]["field_whitelist"] if riv else None)
    check("T66 all declared layers NOT_STAGED in Stage A",
          all(l["status"] == "NOT_STAGED" for l in gl["layers"]))
    check("T67 Basins_A role != Basins_B role (kept distinct)",
          any(l["layer"] == "Basins_A" and
              l["role"] == "total_upstream_catchment" for l in gl["layers"]) and
          any(l["layer"] == "Basins_B" and
              l["role"] == "intermediate_catchment" for l in gl["layers"]))
    st, pl, _ = _get(base, "/api/vhs/pilot")
    check("T68 pilot returns 20 pairs, all geometry verdicts UNKNOWN",
          st == 200 and pl.get("n") == 20 and
          all(p["verdict"] == "UNKNOWN" for p in pl["pairs"]))
    check("T69 pilot covers the C1-S2B strata",
          len({p["stratum"] for p in pl["pairs"]}) >= 5,
          sorted({p["stratum"] for p in pl["pairs"]}))
    st, h2, _ = _get(base, "/api/vhs/health")
    check("T70 health carries gis_mode + app_version 0.6.0",
          h2.get("app_version") == "0.6.0" and
          h2.get("gis_mode") == "STAGE_A_NO_GIS",
          (h2.get("app_version"), h2.get("gis_mode")))

    # ---- five/six-station end-to-end (v0.4 incl. 432) -----------------
    used = [58, 21, 429, 432, 523, 758, 1]
    ok = True
    detail = []
    for sid in used:
        s1s, st1, _ = _get(base, "/api/vhs/stations/%d" % sid)
        s5s, st5, _ = _get(base, "/api/vhs/stations/%d/utw" % sid)
        good = (s1s == 200 and s5s == 200 and st1.get("id") == sid and
                st5.get("target") == sid and
                st1.get("candidate_status") is not None)
        ok = ok and good
        detail.append("%d:%s" % (sid, st1.get("candidate_status")))
    check("T71 seven-station end-to-end with distinct statuses", ok, detail)

    st, sy, _ = _get(base, "/api/vhs/gis/synthetic")
    names = {l["layer"] for l in sy.get("layers", [])}
    check("T72 synthetic preview: RiverATLAS/Basins_A/Basins_B present",
          st == 200 and sy.get("synthetic") is True and
          {"RiverATLAS", "Basins_A", "Basins_B"} <= names, names)
    check("T73 synthetic preview labels every layer source=SYNTHETIC",
          all(l["source"] == "SYNTHETIC" and l.get("sha256")
              for l in sy["layers"]))
    check("T74 synthetic preview carries reach paths + evidence reasons",
          "T_to_J" in sy.get("reach_paths", {}) and
          len(sy.get("evidence_rows", [])) >= 4)
    check("T75 synthetic preview is not real geography (note says so)",
          "NOT real geography" in (sy.get("note") or ""))

    return time.time() - t0


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None)
    args = ap.parse_args()

    proc = None
    base = args.base
    if not base:
        port = free_port()
        base = "http://127.0.0.1:%d" % port
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(
            [sys.executable, "-B", os.path.join(APP, "server.py"),
             "--port", str(port), "--sandbox",
             os.path.dirname(os.path.dirname(os.path.dirname(APP)))],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
            cwd=APP, text=True)
        for _ in range(120):
            try:
                with urllib.request.urlopen(base + "/api/vhs/health",
                                            timeout=1):
                    break
            except Exception:                       # noqa: BLE001
                if proc.poll() is not None:
                    print("server died:\n" + (proc.stdout.read() or ""))
                    return 2
                time.sleep(0.15)
        else:
            print("server did not become ready")
            proc.kill()
            return 2

    print("== VHS v0.5 LamaH-CE regression tests against %s ==" % base)
    try:
        elapsed = run(base)
    finally:
        if proc:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    passed = sum(1 for r in RESULTS if r["passed"])
    total = len(RESULTS)
    print("\n%d/%d passed in %.2fs" % (passed, total, elapsed))
    out = {"base": base, "n_tests": total, "passed": passed,
           "failed": total - passed, "elapsed_s": round(elapsed, 2),
           "tests": RESULTS,
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
    with open(os.path.join(LOGDIR, "test_results.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    with open(os.path.join(LOGDIR, "test_run.log"), "a", encoding="utf-8") as f:
        f.write("\n== run %s base=%s ==\n"
                % (time.strftime("%Y-%m-%dT%H:%M:%S"), base))
        for r in RESULTS:
            f.write("%-64s %s %s\n" % (r["test"],
                                       "PASS" if r["passed"] else "FAIL",
                                       "" if r["passed"] else r["detail"]))
        f.write("%d/%d passed in %.2fs\n" % (passed, total, elapsed))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
