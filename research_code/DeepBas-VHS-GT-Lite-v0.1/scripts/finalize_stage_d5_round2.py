"""Freeze the final Stage D5 round-2 deliverables with SHA-256 hashes."""

from __future__ import print_function

import datetime
import hashlib
import json
import os


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
OUT = os.path.join(
    ROOT, "outputs", "diagnosis_2005_snapshot", "stage_d5_round2"
)
MANIFEST = os.path.join(OUT, "stage_d5_round2_manifest.json")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    files = []
    for base, dirs, names in os.walk(OUT):
        dirs.sort()
        for name in sorted(names):
            path = os.path.join(base, name)
            if os.path.abspath(path) == os.path.abspath(MANIFEST):
                continue
            if name.endswith(".inspect.ndjson"):
                continue
            files.append({
                "path": os.path.relpath(path, ROOT).replace(os.sep, "/"),
                "sha256": sha256(path),
                "bytes": os.path.getsize(path),
            })

    upstream = os.path.join(
        ROOT, "outputs", "diagnosis_2005_snapshot", "stage_d5",
        "stage_d5_freeze_manifest.json"
    )
    payload = {
        "stage": "D5_round2",
        "status": "complete_and_frozen",
        "created_at_local": datetime.datetime.now().isoformat(),
        "scope": "1978-1983 source audit and nested LOYO comparison of M0/M1/M2",
        "constraints_confirmed": {
            "stage_d3_d4a_d4b_d5_round1_not_overwritten": True,
            "2011_not_read_or_scored": True,
            "m3_not_developed": True,
            "mq_not_used": True,
            "era5_not_used": True,
            "gnn_not_used": True,
        },
        "promotion_result": "reject_current_single_upstream_model_family",
        "upstream_stage_d5_round1_manifest": {
            "path": os.path.relpath(upstream, ROOT).replace(os.sep, "/"),
            "exists": os.path.exists(upstream),
            "sha256": sha256(upstream) if os.path.exists(upstream) else None,
        },
        "file_count": len(files),
        "files": files,
    }
    with open(MANIFEST, "w") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(MANIFEST)
    print(sha256(MANIFEST))


if __name__ == "__main__":
    main()
