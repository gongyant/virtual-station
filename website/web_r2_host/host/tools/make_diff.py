"""Unified diff v0.5 -> v0.5.1 (code + docs) and SHA-256 list of new/changed
files.   python -B tools/make_diff.py
Walks only W and the v0.5 directory, pruning sealed/quarantine and the
generated directories."""
import difflib
import hashlib
import os
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V05 = os.path.join(os.path.dirname(W), "v0.5_syrdarya_integration")
PRUNE = {"logs", "tmp", "screenshots", "diff", "research_ready", "_fixtures",
         "__pycache__"}
TEXT = {".py", ".js", ".html", ".css", ".md", ".json", ".ps1", ".txt",
        ".csv", ".svg"}


def walk(root):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in PRUNE and "sealed" not in
                   x.lower() and "quarantine" not in x.lower()]
        for f in files:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root).replace("\\", "/")] = p
    return out


def sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def lines(p):
    with open(p, "rb") as f:
        return f.read().decode("utf-8-sig", "replace").splitlines(True)


def main():
    a, b = walk(V05), walk(W)
    chunks, rows = [], []
    for rel in sorted(set(a) | set(b)):
        pa, pb = a.get(rel), b.get(rel)
        if pa and pb and sha(pa) == sha(pb):
            rows.append(("UNCHANGED", rel, sha(pb)))
            continue
        state = "ADDED" if not pa else ("REMOVED" if not pb else "MODIFIED")
        rows.append((state, rel, sha(pb) if pb else "-"))
        if os.path.splitext(rel)[1].lower() in TEXT:
            d = difflib.unified_diff(lines(pa) if pa else [],
                                     lines(pb) if pb else [],
                                     "a/v0.5/" + rel if pa else "/dev/null",
                                     "b/v0.5.1/" + rel if pb else "/dev/null",
                                     n=3)
            chunks.append("".join(x if x.endswith("\n") else x + "\n"
                                  for x in d))
        else:
            chunks.append("Binary files differ: %s\n" % rel)
    os.makedirs(os.path.join(W, "diff"), exist_ok=True)
    dp = os.path.join(W, "diff", "v0.5_to_v0.5.1.diff")
    with open(dp, "w", encoding="utf-8", newline="\n") as f:
        f.write("# unified diff v0.5_syrdarya_integration -> "
                "v0.5.1_codex_fixes, generated %s\n" % time.strftime(
                    "%Y-%m-%dT%H:%M:%S%z"))
        f.write("".join(chunks))
    sp = os.path.join(W, "diff", "file_status.tsv")
    with open(sp, "w", encoding="utf-8", newline="\n") as f:
        f.write("status\tpath\tsha256_v0.5.1\n")
        for r in rows:
            f.write("\t".join(r) + "\n")
    n = {}
    for r in rows:
        n[r[0]] = n.get(r[0], 0) + 1
    print("diff written:", os.path.relpath(dp, W), n)


if __name__ == "__main__":
    main()
