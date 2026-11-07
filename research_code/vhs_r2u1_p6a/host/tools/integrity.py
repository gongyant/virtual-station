"""
tools/integrity.py -- prove v0.6 wrote nothing outside its own directory.

1. Recompute SHA-256 for every file of v0.4 and v0.5 (recorded by the v0.5.1
   integrity snapshot) and for the six teacher CSVs pinned in the manifest.
2. Verify the frozen v0.5.1 baseline against its own SHA256SUMS_v0.5.1.txt.
3. Write SHA256SUMS_v0.6.txt for this release (code, docs, tests, screenshots).

Read-only outside this directory.  Writes only logs/integrity_v06.json and
SHA256SUMS_v0.6.txt inside v0.6.
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
OUTPUT = os.path.dirname(APP)
V051 = os.path.join(OUTPUT, "v0.5.1_codex_fixes")
BASELINE_JSON = os.path.join(V051, "logs", "integrity_after.json")
BASELINE_SHA = os.path.join(V051, "SHA256SUMS_v0.5.1.txt")
SKIP_DIRS = {"tmp", "__pycache__", ".git", "logs"}
SKIP_FILES = {"SHA256SUMS_v0.6.txt"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def walk(root):
    out = []
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name in SKIP_FILES:
                continue
            out.append(os.path.join(base, name))
    return out


def main():
    # first model-visible timestamp of this work session (Asia/Singapore)
    import datetime
    SESSION_START = "2026-10-24T23:49:55+08:00"
    session_start = datetime.datetime.fromisoformat(
        SESSION_START).timestamp()
    res = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "session_start_epoch": session_start,
           "session_start": SESSION_START,
           "baseline": {}, "teacher_csv": {}, "v051_self": {},
           "v06_file_count": 0, "problems": [], "pre_existing": []}
    if not os.path.isfile(BASELINE_JSON):
        print("baseline integrity json missing:", BASELINE_JSON)
        return 2
    with open(BASELINE_JSON, encoding="utf-8") as f:
        base = json.load(f)
    # --- v0.4 / v0.5 ------------------------------------------------------
    DIRS = {"v0.4": "v0.4", "v0.5": "v0.5_syrdarya_integration"}
    for key, files in base["roots"].items():
        root = os.path.join(OUTPUT, DIRS.get(key, key))
        changed = []
        for rel, rec in files.items():
            p = os.path.join(root, rel)
            if not os.path.isfile(p):
                changed.append([rel, "MISSING"])
                continue
            h = sha256_file(p)
            if h != rec["sha256"]:
                cls = ("CHANGED_AFTER_SESSION"
                       if os.path.getmtime(p) >= session_start else
                       "PRE_EXISTING_CHANGE")
                changed.append([rel, cls])
        new = [c for c in changed if c[1] == "CHANGED_AFTER_SESSION"]
        old = [c for c in changed if c[1] != "CHANGED_AFTER_SESSION"]
        res["baseline"][key] = {"root": root, "files": len(files),
                                "changed": changed,
                                "pre_existing": old,
                                "untouched": not new}
        res["pre_existing"].extend(["%s: %s %s" % (key, c[1], c[0])
                                    for c in old])
        if new:
            res["problems"].extend(["%s: %s %s" % (key, c[1], c[0])
                                    for c in new])
    # --- teacher CSVs -----------------------------------------------------
    tdir = os.path.join(r"D:\VHS_交接包_2026-10-19", "VHS", "03_原始数据")
    bad = []
    for name, rec in base["teacher_csv"].items():
        p = os.path.join(tdir, name)
        if not os.path.isfile(p):
            bad.append([name, "MISSING"])
        elif sha256_file(p) != rec["sha256"]:
            bad.append([name, "CHANGED"])
    res["teacher_csv"] = {"dir": tdir, "files": len(base["teacher_csv"]),
                          "changed": bad, "untouched": not bad}
    if bad:
        res["problems"].extend(["teacher: %s %s" % (b[1], b[0]) for b in bad])
    # --- v0.5.1 self-check -------------------------------------------------
    changed = []
    if os.path.isfile(BASELINE_SHA):
        for line in open(BASELINE_SHA, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            h, rel = line.split("  ", 1)
            p = os.path.join(V051, rel.replace("/", os.sep))
            if not os.path.isfile(p):
                changed.append([rel, "MISSING"])
            elif sha256_file(p) != h:
                changed.append([rel, "CHANGED_AFTER_SESSION"
                                if os.path.getmtime(p) >= session_start
                                else "PRE_EXISTING_CHANGE"])
    new = [c for c in changed if c[1] == "CHANGED_AFTER_SESSION"]
    old = [c for c in changed if c[1] != "CHANGED_AFTER_SESSION"]
    res["v051_self"] = {"root": V051, "files": "see SHA256SUMS_v0.5.1.txt",
                        "changed": changed, "pre_existing": old,
                        "untouched": not new}
    res["pre_existing"].extend(["v0.5.1: %s %s" % (c[1], c[0]) for c in old])
    if new:
        res["problems"].extend(["v0.5.1: %s %s" % (c[1], c[0]) for c in new])
    # --- v0.6 inventory ----------------------------------------------------
    rows = []
    for p in sorted(walk(APP)):
        rel = os.path.relpath(p, APP).replace(os.sep, "/")
        rows.append("%s  %s" % (sha256_file(p), rel))
    with open(os.path.join(APP, "SHA256SUMS_v0.6.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(rows) + "\n")
    res["v06_file_count"] = len(rows)
    os.makedirs(os.path.join(APP, "logs"), exist_ok=True)
    with open(os.path.join(APP, "logs", "integrity_v06.json"), "w",
              encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for k, v in res["baseline"].items():
        print("%-6s files=%-4d untouched=%s" % (k, v["files"], v["untouched"]))
    print("teacher files=%d untouched=%s"
          % (res["teacher_csv"]["files"], res["teacher_csv"]["untouched"]))
    print("v0.5.1 untouched=%s" % res["v051_self"]["untouched"])
    print("v0.6 files hashed=%d -> SHA256SUMS_v0.6.txt" % len(rows))
    print("pre-existing differences:", len(res["pre_existing"]))
    print("problems caused by this session:", len(res["problems"]))
    for p in res["problems"][:10]:
        print("  -", p)
    return 0 if not res["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
