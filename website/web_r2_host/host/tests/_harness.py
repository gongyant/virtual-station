"""Tiny shared test harness for VHS v0.5.1 tests (stdlib only).

Results are written only to <APP>/logs/<suite>.json. PASS/FAIL/SKIP are
recorded honestly; a SKIP carries its reason.
"""
import json
import os
import platform
import sys
import time
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
LOGDIR = os.path.join(APP, "logs")
TMPDIR = os.path.join(APP, "tmp")


class Suite:
    def __init__(self, name):
        self.name = name
        self.rows = []
        self.t0 = time.time()

    def check(self, tid, title, cond, detail=""):
        st = "PASS" if cond else "FAIL"
        self.rows.append({"id": tid, "title": title, "status": st,
                          "detail": "" if cond else str(detail)[:600]})
        print("  %-8s %-62s %s %s" % (tid, title[:62], st,
                                      "" if cond else str(detail)[:200]))
        return bool(cond)

    def skip(self, tid, title, reason):
        self.rows.append({"id": tid, "title": title, "status": "SKIP",
                          "detail": reason})
        print("  %-8s %-62s SKIP %s" % (tid, title[:62], reason[:200]))

    def counts(self):
        c = {"PASS": 0, "FAIL": 0, "SKIP": 0}
        for r in self.rows:
            c[r["status"]] += 1
        return c

    def save(self, extra=None):
        c = self.counts()
        out = {"suite": self.name, "total": len(self.rows), **c,
               "run_on": "%s %s / Python %s" % (platform.node(),
                                                 platform.system(),
                                                 sys.version.split()[0]),
               "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "elapsed_s": round(time.time() - self.t0, 2),
               "tests": self.rows}
        if extra:
            out.update(extra)
        os.makedirs(LOGDIR, exist_ok=True)
        with open(os.path.join(LOGDIR, self.name + ".json"), "w",
                  encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print("\n[%s] total=%d pass=%d fail=%d skip=%d" % (
            self.name, len(self.rows), c["PASS"], c["FAIL"], c["SKIP"]))
        return 0 if c["FAIL"] == 0 else 1
