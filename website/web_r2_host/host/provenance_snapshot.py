"""
provenance_snapshot.py  --  VHS v0.5.1 immutable load snapshot (Codex P1-02)

Policy: IMMUTABLE_LOAD_SNAPSHOT.

* A pinned manifest must list exactly the expected six files (no missing,
  no extra, no duplicate entry, each with a 64-hex sha256 and byte size).
  In production the manifest file itself is also pinned by SHA-256.
* Each source file is opened ONCE; its raw bytes are hashed and the very
  same bytes object is later decoded and parsed (no second open, no
  check/parse race).
* Any missing file, size or hash mismatch, or manifest defect refuses the
  whole dataset (all-or-nothing, fail closed). A current on-disk value is
  never written back over the pinned value.
* Semantics: "snapshot verified" means the in-memory bytes equal the disk
  content AT LOAD TIME and equal the pin. It does NOT mean the disk files
  are still unchanged now. ``recheck()`` re-hashes the files on demand and
  reports the result with its own timestamp; it never modifies the
  snapshot.
"""
import hashlib
import json
import os
import re
import time

POLICY = "IMMUTABLE_LOAD_SNAPSHOT"
SEMANTICS_ZH = ("快照校验通过 = 加载时磁盘字节与冻结清单一致，且内存中解析的就是这同一份"
                "字节；这不等于“磁盘原文件当前仍未改变”。需要当前状态请调用按需复核"
                "（只做哈希比较，不改快照）。")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SnapshotRefused(Exception):
    def __init__(self, status, errors):
        super().__init__("%s: %s" % (status, errors))
        self.status, self.errors = status, errors


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def load_manifest(path, expected_names, expected_manifest_sha256=None):
    """Validate the pinned manifest. Returns (dict name->entry, manifest_sha)."""
    if not path or not os.path.isfile(path):
        raise SnapshotRefused("MANIFEST_MISSING", ["pinned manifest not found"])
    with open(path, "rb") as f:
        raw = f.read()
    msha = sha256_bytes(raw)
    errs = []
    if expected_manifest_sha256 and msha != expected_manifest_sha256:
        raise SnapshotRefused("MANIFEST_INVALID", [
            "manifest sha256 %s != frozen %s" % (msha,
                                                 expected_manifest_sha256)])
    try:
        doc = json.loads(raw.decode("utf-8"))
        entries = doc["files"]
        assert isinstance(entries, list)
    except Exception as exc:                          # noqa: BLE001
        raise SnapshotRefused("MANIFEST_INVALID", ["unreadable: %s" % exc])
    pins = {}
    for e in entries:
        name = e.get("file") if isinstance(e, dict) else None
        if not name:
            errs.append("entry without file name")
            continue
        if name in pins:
            errs.append("duplicate entry %s" % name)
            continue
        sha = e.get("sha256")
        size = e.get("bytes")
        if not isinstance(sha, str) or not _HEX64.match(sha):
            errs.append("%s: sha256 missing or malformed" % name)
        if not isinstance(size, int) or size < 0:
            errs.append("%s: bytes missing or malformed" % name)
        pins[name] = e
    expected = set(expected_names)
    for n in sorted(expected - set(pins)):
        errs.append("manifest lacks %s" % n)
    for n in sorted(set(pins) - expected):
        errs.append("unexpected manifest entry %s" % n)
    if errs:
        raise SnapshotRefused("MANIFEST_INVALID", errs)
    return pins, msha, doc


class Snapshot:
    """Immutable verified bytes of the pinned source files."""

    def __init__(self, source_dir, manifest_path, expected_names,
                 expected_manifest_sha256=None):
        self.source_dir = source_dir
        self.manifest_path = manifest_path
        self.policy = POLICY
        pins, msha, doc = load_manifest(manifest_path, expected_names,
                                        expected_manifest_sha256)
        self.manifest_sha256 = msha
        self.manifest_doc = doc
        self.pins = pins
        data, errs, status = {}, [], None
        for name in expected_names:
            p = os.path.join(source_dir, name)
            pin = pins[name]
            if not os.path.isfile(p):
                errs.append({"file": name, "status": "SOURCE_MISSING"})
                status = status or "SOURCE_MISSING"
                continue
            with open(p, "rb") as f:          # the ONLY read of this file
                raw = f.read()
            sha = sha256_bytes(raw)
            if len(raw) != pin["bytes"] or sha != pin["sha256"]:
                errs.append({"file": name, "status": "SOURCE_CHANGED",
                             "observed_bytes": len(raw),
                             "pinned_bytes": pin["bytes"],
                             "observed_sha256": sha,
                             "pinned_sha256": pin["sha256"]})
                status = status or "SOURCE_CHANGED"
                continue
            data[name] = raw
        if errs:
            raise SnapshotRefused(status, errs)
        self._data = data                      # name -> bytes (immutable)
        self.loaded_at = now_iso()
        self.snapshot_id = "syr-snap-" + sha256_bytes(
            (msha + "\n" + "\n".join("%s:%s" % (n, pins[n]["sha256"])
                                     for n in sorted(pins))).encode())[:20]
        self.last_recheck = None

    def raw(self, name):
        return self._data[name]

    def sha256(self, name):
        return self.pins[name]["sha256"]

    def info(self):
        return {"snapshot_id": self.snapshot_id, "policy": self.policy,
                "loaded_at": self.loaded_at,
                "manifest_sha256": self.manifest_sha256,
                "source_status": "VERIFIED_AT_LOAD",
                "files": [{"file": n, "bytes": self.pins[n]["bytes"],
                           "sha256": self.pins[n]["sha256"]}
                          for n in self.pins],
                "semantics": SEMANTICS_ZH,
                "disk_currently_unchanged": "NOT_ASSERTED (see recheck)",
                "last_recheck": self.last_recheck}

    def recheck(self):
        """Re-hash the disk files now; compare only. Never alters the snapshot."""
        res = []
        for n, pin in self.pins.items():
            p = os.path.join(self.source_dir, n)
            if not os.path.isfile(p):
                res.append({"file": n, "result": "MISSING"})
                continue
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for c in iter(lambda: f.read(1 << 16), b""):
                    h.update(c)
            res.append({"file": n, "result": "MATCH" if h.hexdigest() ==
                        pin["sha256"] else "CHANGED"})
        ok = all(r["result"] == "MATCH" for r in res)
        self.last_recheck = {
            "rechecked_at": now_iso(), "disk_matches_snapshot": ok,
            "files": res,
            "effect": "NONE: the in-memory snapshot (verified at %s) is "
                      "unchanged; this result is reported only"
                      % self.loaded_at}
        return dict(self.last_recheck, snapshot_id=self.snapshot_id)
