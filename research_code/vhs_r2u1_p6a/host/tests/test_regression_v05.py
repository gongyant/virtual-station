"""
tests/test_regression_v05.py  --  v0.5 -> v0.5.1 regression (LamaH-CE + Syr Darya)

v0.5 answers are produced by the UNMODIFIED v0.5 code in a child process
(tests/_v05_query.py, in-process dispatch, no HTTP: port 8773 and the v0.5
directory are not touched). v0.5.1 answers come over HTTP from a private
v0.5.1 server. Rule: every key/value v0.5 returned must be returned
identically by v0.5.1 (v0.5.1 may only ADD fields), except an explicit,
documented list of intentional changes. Runs on the user's PC.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import _server  # noqa: E402

V05 = os.path.join(os.path.dirname(APP), "v0.5_syrdarya_integration")
T = Suite("test_regression_v05")
D = "/api/vhs/datasets/SYRDARYA"
PATHS = [
    "/api/vhs/health", "/api/vhs/meta", "/api/vhs/regions",
    "/api/vhs/stations?q=&limit=25", "/api/vhs/stations?q=a&limit=200",
    "/api/vhs/stations?targets_only=1&limit=200",
    "/api/vhs/stations/58", "/api/vhs/stations/58/network?depth=4",
    "/api/vhs/stations/58/audit", "/api/vhs/stations/58/candidates",
    "/api/vhs/stations/58/served-targets", "/api/vhs/stations/58/utw",
    "/api/vhs/stations/1", "/api/vhs/stations/1/network?depth=30",
    "/api/vhs/stations/99999", "/api/vhs/map", "/api/vhs/model-status",
    "/api/vhs/gis/status", "/api/vhs/gis/layers", "/api/vhs/pilot",
    "/api/vhs/predict", "/api/vhs/export?what=stations&format=json",
    "/api/vhs/export?what=candidates&format=json",
    "/api/vhs/datasets", "/api/vhs/datasets/LAMAHCE",
    "/api/vhs/datasets/LAMAHCE/stations",
    D, D + "/stations", D + "/timeline", D + "/research", D + "/gis",
    D + "/discharge?station=SYRDARYA:16037&year=2008",
    D + "/discharge?station=SYRDARYA:16039&year=2010",
    D + "/discharge?station=SYRDARYA:16037&year=2005",
    D + "/discharge?station=SYRDARYA:16037&view=annual",
    D + "/discharge?station=SYRDARYA:16039&view=annual",
    D + "/discharge?station=LAMAHCE:58&year=2008",
    D + "/meteorology?year=2010",
    D + "/meteorology?year=2010&granularity=daily",
    D + "/remote-sensing?year=2010&month=6",
    D + "/water-balance?year=2010&width_km=3&alpha=0.75",
    D + "/water-balance?year=2010&width_km=3&alpha=0.6",
    D + "/water-balance?year=2003&width_km=1&alpha=0.9",
    D + "/data-quality?limit=50", D + "/data-quality?limit=40&offset=40",
    D + "/availability?year=2010", D + "/predict",
]
# intentional, documented v0.5.1 changes. Ignored keys are listed per
# route; nothing else may differ (v0.5.1 may only ADD fields).
CHANGED_KEYS = {
    "app_version": "0.5.0 -> 0.6.0 (health / meta)",
    "build_id": "new build id",
    "service": "v0.5 workbench title -> v0.6 four-layer platform title (meta only)",
    "uptime_s": "volatile",
    "server_started_at": "volatile timestamp",
    "seconds": "volatile load timing under /loaded",
}
PATH_CHANGED = {
    "/water-balance": {"disclaimer": "wording neutral (Codex Q7); still "
                                     "contains 不是实测取水量"},
    "/research": {"tasks": "task blurbs expanded for recursive DAG (Codex D)"},
}


def subset(old, new, path, diffs, depth=0, skip=()):
    if isinstance(old, dict):
        if not isinstance(new, dict):
            diffs.append((path, "type"))
            return
        for k, v in old.items():
            if k in CHANGED_KEYS or (depth == 0 and k in skip):
                continue
            if k not in new:
                diffs.append((path + "/" + k, "missing in v0.6"))
                continue
            subset(v, new[k], path + "/" + k, diffs, depth + 1)
    elif isinstance(old, list):
        if not isinstance(new, list) or len(old) != len(new):
            diffs.append((path, "list length %s vs %s" % (
                len(old), len(new) if isinstance(new, list) else "-")))
            return
        for i, (a, b) in enumerate(zip(old, new)):
            subset(a, b, "%s[%d]" % (path, i), diffs, depth + 1)
    elif isinstance(old, float) and isinstance(new, (int, float)):
        if not (old == new or abs(old - new) <= 1e-12 * max(1, abs(old))):
            diffs.append((path, "value"))
    elif old != new:
        diffs.append((path, "value"))


def main():
    if not os.path.isfile(os.path.join(V05, "server.py")):
        T.skip("G00", "v0.5 regression", "v0.5 not found")
        return T.save()
    tmp = os.path.join(APP, "tmp")
    os.makedirs(tmp, exist_ok=True)
    pf, of = os.path.join(tmp, "reg_paths.json"), os.path.join(
        tmp, "reg_v05.json")
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(PATHS, f)
    r = subprocess.run([sys.executable, "-B", os.path.join(
        HERE, "_v05_query.py"), V05, APP, pf, of], capture_output=True,
        text=True, encoding="utf-8", env=_server.env(), cwd=tmp,
        timeout=900)
    T.check("G00", "v0.5 reference child ran (in-process, no HTTP)",
            r.returncode == 0, r.stderr[-400:])
    if r.returncode != 0:
        return T.save()
    with open(of, encoding="utf-8") as f:
        ref = json.load(f)
    T.check("G01", "v0.5 child attempted no write outside W/tmp",
            ref["refused_writes"] == [], ref["refused_writes"][:3])
    T.check("G02", "v0.5 Syr store OK in reference run",
            ref["syr_status"] == "OK", ref["syr_status"])
    proc, base, port = _server.start()
    summary = []
    try:
        for i, p in enumerate(PATHS, 1):
            st, body, _ = _server.get(base, p)
            o = ref["results"][p]
            diffs = []
            if o["status"] != st:
                diffs.append(("status", "%s -> %s" % (o["status"], st)))
            else:
                skip = [k for frag, ks in PATH_CHANGED.items() if frag in p
                        for k in ks]
                subset(o["body"], body, "", diffs, skip=skip)
            added = sorted(set(body) - set(o["body"])) if isinstance(
                body, dict) and isinstance(o["body"], dict) else []
            summary.append({"path": p, "status_v05": o["status"],
                            "status_v051": st, "diffs": diffs[:10],
                            "added_top_level_keys": added})
            ds = "SYR" if "/SYRDARYA" in p else "LAMAH"
            T.check("G%02d" % (i + 2), "%s %s: v0.5 subset-of v0.6" % (ds, p[:52]),
                    not diffs, diffs[:3])
    finally:
        _server.stop(proc)
    os.remove(pf)
    os.remove(of)
    with open(os.path.join(APP, "logs", "regression_v05_detail.json"), "w",
              encoding="utf-8") as f:
        json.dump({"rule": "v0.5 response subset-of v0.5.1 response",
                   "intentional_changes": CHANGED_KEYS,
                   "intentional_changes_by_route": PATH_CHANGED,
                   "paths": summary},
                  f, ensure_ascii=False, indent=1)
    return T.save()


if __name__ == "__main__":
    raise SystemExit(main())
