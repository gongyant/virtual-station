"""Apply the v0.5.1 changes to W/syrdarya_adapter.py (exact-match patches)."""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(W, "syrdarya_adapter.py")
NL = "\r\n" if b"\r\n" in open(P, "rb").read() else "\n"
s = open(P, encoding="utf-8").read()
if "provenance_snapshot" in s:
    sys.exit("already patched")


def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit("patch failed (%d matches): %r" % (n, old[:80]))
    s = s.replace(old, new)


rep('''* The source files are pinned by SHA-256; if a file changes, the dataset is
  refused (SOURCE_CHANGED) instead of being served.
"""''', '''* The source files are pinned by SHA-256; if a file changes, the dataset is
  refused (SOURCE_CHANGED) instead of being served.
* v0.5.1 (Codex P1-02): fail closed. A complete pinned manifest (exactly the
  six files, itself pinned by SHA-256 in production) is REQUIRED; each file
  is read once into an immutable snapshot and the same verified bytes are
  parsed (provenance_snapshot.py). Missing manifest / entry, extra entry,
  wrong size or hash, or a missing file refuses the whole dataset.
"""''')
rep('''import calendar
import csv
import hashlib
import json
import os
''', '''import calendar
import csv
import hashlib
import io
import json
import os
''')
rep('''from typing import List, Optional
''', '''from typing import List, Optional

from provenance_snapshot import Snapshot, SnapshotRefused, now_iso
''')
rep('''DEFAULT_SOURCE = r"D:\\VHS_交接包_2026-10-19\\VHS\\03_原始数据"
''', '''DEFAULT_SOURCE = r"D:\\VHS_交接包_2026-10-19\\VHS\\03_原始数据"
# SHA-256 of manifest/source_manifest.json as frozen in v0.5 and recorded by
# the Codex review (source_hashes_before.json). Never updated from disk.
PINNED_MANIFEST_SHA256 = (
    "65721f8d0d1b81482ce554ade9456703fa028965ad14f80a00a3318359a8100f")
''')
rep('''    def __init__(self, source_dir=None, pinned_manifest=None):
        self.source_dir = source_dir or os.environ.get(
            "VHS_SYR_SOURCE", DEFAULT_SOURCE)
        self.pinned = {}
        if pinned_manifest and os.path.isfile(pinned_manifest):
            with open(pinned_manifest, encoding="utf-8") as f:
                self.pinned = {r["file"]: r for r in json.load(f)["files"]}
        self.files = {}
''', '''    def __init__(self, source_dir=None, pinned_manifest=None,
                 expected_manifest_sha256=None):
        self.source_dir = source_dir or os.environ.get(
            "VHS_SYR_SOURCE", DEFAULT_SOURCE)
        self.pinned_manifest = pinned_manifest
        self.expected_manifest_sha256 = expected_manifest_sha256
        self.snapshot = None
        self.refusal = None
        self.seq_runs = []             # one record per flagged run
        self.files = {}
''')
rep('''    def _rows(self, key):
        meta = self.files[key]
        with open(meta["path"], encoding=meta["encoding"], newline="") as f:
            return list(csv.reader(f))
''', '''    def _rows(self, key):
        """Parse the SAME bytes that were hashed at load (no second open)."""
        meta = self.files[key]
        text = self.snapshot.raw(meta["file"]).decode(meta["encoding"])
        return list(csv.reader(io.StringIO(text, newline="")))
''')
rep('''    def _load(self):
        for key, name in FILES.items():
            p = os.path.join(self.source_dir, name)
            if not os.path.isfile(p):
                self.files[key] = {"file": name, "status": "MISSING"}
                self.status = "SOURCE_MISSING"
                continue
            raw = open(p, "rb").read()
            enc = "utf-8-sig" if raw.startswith(b"\\xef\\xbb\\xbf") else "utf-8"
            sha = hashlib.sha256(raw).hexdigest()
            rec = {"file": name, "path": p, "bytes": len(raw), "sha256": sha,
                   "encoding": enc, "line_endings":
                   "CRLF" if b"\\r\\n" in raw else "LF", "status": "OK"}
            pin = self.pinned.get(name)
            if pin and pin["sha256"] != sha:
                rec["status"] = "SOURCE_CHANGED"
                self.status = "SOURCE_CHANGED"
            self.files[key] = rec
        if self.status != "OK":
            return
''', '''    def _load(self):
        try:
            snap = Snapshot(self.source_dir, self.pinned_manifest,
                            list(FILES.values()),
                            self.expected_manifest_sha256)
        except SnapshotRefused as exc:
            self.status = exc.status
            self.refusal = {"status": exc.status, "errors": exc.errors,
                            "checked_at": now_iso()}
            per = {e.get("file"): e.get("status") for e in exc.errors
                   if isinstance(e, dict)}
            for key, name in FILES.items():
                self.files[key] = {"file": name, "status": per.get(
                    name, exc.status if not per else "NOT_LOADED"),
                    "sha256": None}
            return
        self.snapshot = snap
        for key, name in FILES.items():
            raw = snap.raw(name)
            enc = "utf-8-sig" if raw.startswith(b"\\xef\\xbb\\xbf") else "utf-8"
            self.files[key] = {
                "file": name, "path": os.path.join(self.source_dir, name),
                "bytes": len(raw), "sha256": snap.sha256(name),
                "encoding": enc, "line_endings":
                "CRLF" if b"\\r\\n" in raw else "LF", "status": "OK"}
''')
rep('''    def _seq_flag(self, code, year, stat, months):
        for ob in self.discharge:''', '''    def _seq_flag(self, code, year, stat, months):
        self.seq_runs.append({"station": uid(code), "year": year,
                              "stat": stat, "months": list(months)})
        for ob in self.discharge:''')
rep('''    def provenance(self):
        out = []
        for key, rec in self.files.items():
            r = {k: v for k, v in rec.items() if k != "path"}''', '''    def snapshot_public(self):
        if self.snapshot is None:
            return {"snapshot_id": None, "source_status": self.status,
                    "refusal": self.refusal}
        return self.snapshot.info()

    def provenance(self):
        out = []
        for key, rec in self.files.items():
            r = {k: v for k, v in rec.items() if k != "path"}''')
open(P, "w", encoding="utf-8", newline=NL).write(s)
print("patched", P)
