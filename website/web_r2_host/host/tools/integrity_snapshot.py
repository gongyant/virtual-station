"""tools/integrity_snapshot.py -- VHS v0.5.1 before/after integrity snapshot.

Hashes (read-only) the frozen v0.4 and v0.5 directories in full and the six
teacher CSVs named in W/manifest/source_manifest.json. Directory walks prune
any directory whose name contains 'sealed' or 'quarantine' (case-insensitive)
and never follow links. Output is written only inside W.

    python -B tools/integrity_snapshot.py snap  --out logs/integrity_before.json
    python -B tools/integrity_snapshot.py diff  logs/integrity_before.json logs/integrity_after.json --out logs/integrity_diff.json
"""
import hashlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HERE)
APPS = os.path.dirname(W)
ROOTS = {"v0.4": os.path.join(APPS, "v0.4"),
         "v0.5": os.path.join(APPS, "v0.5_syrdarya_integration")}
PRUNE = ("sealed", "quarantine")


def safe_out(p):
    if not p:
        raise SystemExit("empty output path refused")
    full = os.path.realpath(os.path.join(W, p) if not os.path.isabs(p) else p)
    if os.path.commonpath([full, os.path.realpath(W)]) != os.path.realpath(W):
        raise SystemExit("output outside W refused: %s" % full)
    return full


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def walk(root):
    out, pruned = {}, []
    for dp, dns, fns in os.walk(root, followlinks=False):
        keep = []
        for d in dns:
            full = os.path.join(dp, d)
            if any(k in d.lower() for k in PRUNE) or os.path.islink(full):
                pruned.append(os.path.relpath(full, root))
            else:
                keep.append(d)
        dns[:] = keep
        for fn in fns:
            full = os.path.join(dp, fn)
            if os.path.islink(full):
                continue
            st = os.stat(full)
            out[os.path.relpath(full, root).replace("\\", "/")] = {
                "sha256": sha(full), "bytes": st.st_size,
                "mtime": round(st.st_mtime, 3)}
    return out, pruned


def snap(out_path):
    res = {"created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "roots": {},
           "pruned": {}, "teacher_csv": {}}
    for k, r in ROOTS.items():
        res["roots"][k], res["pruned"][k] = walk(r)
    man = json.load(open(os.path.join(W, "manifest", "source_manifest.json"),
                         encoding="utf-8"))
    for f in man["files"]:
        p = os.path.join(man["source_dir"], f["file"])
        ok = os.path.isfile(p)
        res["teacher_csv"][f["file"]] = {
            "sha256": sha(p) if ok else None,
            "bytes": os.path.getsize(p) if ok else None,
            "pinned_sha256": f["sha256"], "pinned_bytes": f["bytes"]}
    with open(safe_out(out_path), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1)
    n = {k: len(v) for k, v in res["roots"].items()}
    tm = sum(v["sha256"] == v["pinned_sha256"]
             for v in res["teacher_csv"].values())
    print("snapshot files=%s teacher_pinned_match=%d/6" % (n, tm))


def diff(a, b, out_path):
    A = json.load(open(a, encoding="utf-8"))
    B = json.load(open(b, encoding="utf-8"))
    rep = {"before": a, "after": b, "roots": {}, "teacher_csv": {}}
    for k in A["roots"]:
        fa, fb = A["roots"][k], B["roots"].get(k, {})
        rep["roots"][k] = {
            "n_before": len(fa), "n_after": len(fb),
            "added": sorted(set(fb) - set(fa)),
            "removed": sorted(set(fa) - set(fb)),
            "changed": sorted(p for p in fa if p in fb and
                              fa[p]["sha256"] != fb[p]["sha256"])}
    for f, v in A["teacher_csv"].items():
        w = B["teacher_csv"].get(f, {})
        rep["teacher_csv"][f] = {
            "unchanged": v["sha256"] == w.get("sha256"),
            "matches_pin_after": w.get("sha256") == v["pinned_sha256"]}
    with open(safe_out(out_path), "w", encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    for k, r in rep["roots"].items():
        print("%s: before=%d after=%d added=%d removed=%d changed=%d %s" % (
            k, r["n_before"], r["n_after"], len(r["added"]),
            len(r["removed"]), len(r["changed"]), r["changed"][:5]))
    print("teacher unchanged=%d/6 pin_match_after=%d/6" % (
        sum(v["unchanged"] for v in rep["teacher_csv"].values()),
        sum(v["matches_pin_after"] for v in rep["teacher_csv"].values())))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["snap"] and a[1:2] == ["--out"]:
        snap(a[2])
    elif a[:1] == ["diff"] and a[3:4] == ["--out"]:
        diff(a[1], a[2], a[4])
    else:
        raise SystemExit(__doc__)
