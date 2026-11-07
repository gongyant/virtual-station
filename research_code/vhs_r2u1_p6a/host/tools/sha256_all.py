"""SHA256SUMS of every file in W that is new or changed vs v0.5, plus all
generated evidence (logs, screenshots, diff, research_ready).
    python -B tools/sha256_all.py      -> W/SHA256SUMS_v0.5.1.txt"""
import hashlib
import os

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V05 = os.path.join(os.path.dirname(W), "v0.5_syrdarya_integration")
SKIP = {"tmp", "__pycache__", "_fixtures"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def main():
    out = []
    for d, dirs, files in os.walk(W):
        dirs[:] = sorted(x for x in dirs if x not in SKIP and "sealed" not in
                         x.lower() and "quarantine" not in x.lower())
        for f in sorted(files):
            p = os.path.join(d, f)
            rel = os.path.relpath(p, W)
            if rel == "SHA256SUMS_v0.5.1.txt":
                continue
            old = os.path.join(V05, rel)
            h = sha(p)
            if os.path.isfile(old) and sha(old) == h:
                continue                         # unchanged copy of v0.5
            out.append("%s  %s" % (h, rel.replace("\\", "/")))
    with open(os.path.join(W, "SHA256SUMS_v0.5.1.txt"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print("SHA256SUMS_v0.5.1.txt:", len(out), "files")


if __name__ == "__main__":
    main()
