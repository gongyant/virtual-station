from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SPECS = [
    ("D6", "outputs/diagnosis_2005_snapshot/stage_d6/stage_d6_manifest.json", 18),
    ("D5_round4", "outputs/diagnosis_2005_snapshot/stage_d5_round4/stage_d5_round4_manifest.json", 29),
    ("D5_round3", "outputs/diagnosis_2005_snapshot/stage_d5_round3/stage_d5_round3_manifest.json", 28),
    ("D5_round2", "outputs/diagnosis_2005_snapshot/stage_d5_round2/stage_d5_round2_manifest.json", 34),
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def verify(name: str, manifest_rel: str, required_count: int) -> dict:
    manifest_path = ROOT / manifest_rel
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = []
    for item in manifest["files"]:
        rel = item.get("file_path", item.get("path"))
        expected_size = item.get("file_size", item.get("bytes"))
        path = ROOT / rel
        actual_hash = digest(path) if path.exists() else None
        actual_size = path.stat().st_size if path.exists() else None
        checks.append({
            "path": rel,
            "exists": path.exists(),
            "expected_sha256": item["sha256"],
            "actual_sha256": actual_hash,
            "hash_match": actual_hash == item["sha256"],
            "expected_size": expected_size,
            "actual_size": actual_size,
            "size_match": expected_size in (None, actual_size),
        })
    count_ok = manifest.get("file_count") == required_count == len(manifest["files"])
    return {
        "name": name,
        "manifest_path": manifest_rel,
        "manifest_sha256": digest(manifest_path),
        "required_count": required_count,
        "declared_count": manifest.get("file_count"),
        "listed_count": len(manifest["files"]),
        "count_ok": count_ok,
        "all_hashes_match": all(x["hash_match"] for x in checks),
        "all_sizes_match": all(x["size_match"] for x in checks),
        "checks": checks,
    }


def main() -> None:
    audits = [verify(*spec) for spec in SPECS]
    result = {
        "all_passed": all(a["count_ok"] and a["all_hashes_match"] and a["all_sizes_match"] for a in audits),
        "audits": audits,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
