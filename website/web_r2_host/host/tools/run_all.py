"""Run every v0.5.1 test suite on this machine; write logs/test_summary.json.

    python -B tools/run_all.py [suite ...]
"""
import json
import os
import platform
import subprocess
import sys
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITES = [
    # inherited v0.5.1 regression suites (backend / contracts / security)
    "test_feature_lineage", "test_syrdarya_synthetic", "test_gis_synthetic",
    "test_provenance_snapshots", "test_http_boundaries", "test_lamahce_regression",
    "test_syrdarya_api", "test_science_views", "test_regression_v05",
    "test_research_ready",
    # new v0.6 four-layer suites
    "test_v06_api", "test_v06_ui",
]


def counts(name):
    p = os.path.join(W, "logs", name + ".json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    if "PASS" in d:
        return {"total": d["total"], "pass": d["PASS"], "fail": d["FAIL"],
                "skip": d["SKIP"], "run_on": d.get("run_on")}
    if "passed" in d:                       # inherited v0.5 log format
        return {"total": d["total"], "pass": d["passed"],
                "fail": d["total"] - d["passed"], "skip": 0,
                "run_on": None}
    return None


def main():
    sel = sys.argv[1:] or SUITES
    env = dict(os.environ)
    env["TEMP"] = env["TMP"] = os.path.join(W, "tmp")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    os.makedirs(env["TEMP"], exist_ok=True)
    out = []
    for s in sel:
        t0 = time.time()
        p = os.path.join(W, "tests", s + ".py")
        logp = os.path.join(W, "logs", s + ".stdout.txt")
        lj = os.path.join(W, "logs", s + ".json")
        if os.path.isfile(lj):
            os.remove(lj)
        with open(logp, "w", encoding="utf-8") as lf:
            rc = subprocess.call([sys.executable, "-B", p], cwd=W, env=env,
                                 stdout=lf, stderr=subprocess.STDOUT,
                                 timeout=1800)
        c = counts(s)
        if c is None:
            import re
            txt = open(logp, encoding="utf-8", errors="replace").read()
            m = re.search(r"(\d+)/(\d+)\s+.*passed", txt)
            if m and rc == 0:
                p_, n_ = int(m.group(1)), int(m.group(2))
                c = {"total": n_, "pass": p_, "fail": n_ - p_, "skip": 0,
                     "run_on": None, "legacy_from_stdout": True}
            else:
                c = {"total": 0, "pass": 0, "fail": 1, "skip": 0}
        c.update(suite=s, rc=rc, elapsed_s=round(time.time() - t0, 1))
        out.append(c)
        print("%-28s rc=%d total=%d pass=%d fail=%d skip=%d" % (
            s, rc, c["total"], c["pass"], c["fail"], c["skip"]))
    tot = {k: sum(x[k] for x in out) for k in ("total", "pass", "fail",
                                                "skip")}
    summ = {"run_on": "%s %s / Python %s" % (platform.node(),
                                             platform.system(),
                                             sys.version.split()[0]),
            "python": sys.executable,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "totals": tot, "suites": out}
    name = "test_summary.json" if not sys.argv[1:] else \
        "test_summary_partial.json"
    with open(os.path.join(W, "logs", name), "w", encoding="utf-8") as f:
        json.dump(summ, f, ensure_ascii=False, indent=1)
    print("TOTAL total=%(total)d pass=%(pass)d fail=%(fail)d skip=%(skip)d"
          % tot)
    return 0 if tot["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
