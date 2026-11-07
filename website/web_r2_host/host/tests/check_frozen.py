"""Verify frozen v0.4 deliverables and the teacher CSVs are byte-identical."""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
V04 = os.path.join(os.path.dirname(APP), "v0.4")


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def main():
    out = {"v0.4": [], "teacher_csv": []}
    for line in open(os.path.join(V04, "SHA256SUMS.txt"), encoding="ascii"):
        h, rel = line.strip().split("  ", 1)
        p = os.path.join(V04, rel)
        out["v0.4"].append({"file": rel, "expected": h,
                            "match": os.path.isfile(p) and sha(p) == h})
    man = json.load(open(os.path.join(APP, "manifest", "source_manifest.json"),
                         encoding="utf-8"))
    for f in man["files"]:
        p = os.path.join(man["source_dir"], f["file"])
        out["teacher_csv"].append({"file": f["file"], "expected": f["sha256"],
                                   "match": sha(p) == f["sha256"]})
    for k, rows in out.items():
        ok = sum(r["match"] for r in rows)
        print("%-12s %d/%d unchanged" % (k, ok, len(rows)))
        for r in rows:
            if not r["match"]:
                print("   CHANGED:", r["file"])
    with open(os.path.join(APP, "logs", "frozen_check.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    return 0 if all(r["match"] for rows in out.values() for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
