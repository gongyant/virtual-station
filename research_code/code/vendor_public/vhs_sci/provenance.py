"""Exclusive-create immutable run bundles and strict offline validation."""
import csv
import hashlib
import json
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from .contracts import ScienceError, canonical, digest, ids_hash, TASK, GROUP_A, GROUP_B, MODELS_A, MODELS_B
from .folds import FoldSpec, validate_fold, support


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def code_hash(root):
    return digest({str(p.relative_to(root)).replace("\\", "/"): sha_file(p)
                   for p in sorted(Path(root).rglob("*.py")) if "__pycache__" not in p.parts})


def write_json(path, data):
    with Path(path).open("x", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=1, allow_nan=False) + "\n")


def write_csv(path, rows):
    if not rows:
        raise ScienceError("EMPTY_ARTIFACT_ROWS")
    with Path(path).open("x", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


def write_run(root, run_id, manifest, payload, prediction_rows, yearly_rows, observations, inputs, report):
    target = Path(root) / run_id
    if target.exists():
        raise ScienceError("IMMUTABLE_RUN_ALREADY_EXISTS")
    target.mkdir(parents=True, exist_ok=False)
    for name, obj in payload.items():
        write_json(target / name, obj)
    write_csv(target / "predictions.csv", prediction_rows)
    write_csv(target / "yearly_metrics.csv", yearly_rows)
    write_csv(target / "synthetic_observations.csv", observations)
    write_csv(target / "synthetic_inputs.csv", inputs)
    with (target / "report.md").open("x", encoding="utf-8") as f:
        f.write(report)
    files = {p.name: sha_file(p) for p in sorted(target.iterdir()) if p.is_file()}
    manifest = {**manifest, "run_id": run_id, "created_UTC": datetime.now(timezone.utc).isoformat(), "artifact_file_hashes": files}
    write_json(target / "manifest.json", manifest)
    files["manifest.json"] = sha_file(target / "manifest.json")
    with (target / "SHA256SUMS.txt").open("x", encoding="utf-8") as f:
        f.write("".join(f"{h}  {n}\n" for n, h in sorted(files.items())))
    return target


def validate_run_artifact(path, registry, target_view="synthetic"):
    path = Path(path).resolve()
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    mandatory = {"run_id", "dataset_id", "snapshot_id", "task_class", "quality_scheme", "model_id", "model_version",
                 "train_ids_hash", "test_ids_hash", "protocol_hash", "code_hash", "seed", "synthetic", "authorization_status", "unit_status"}
    if not mandatory <= set(manifest):
        raise ScienceError("INCOMPLETE_RUN_MANIFEST")
    ds, snap = manifest["dataset_id"], manifest["snapshot_id"]
    if registry.get(ds) != snap:
        raise ScienceError("DATASET_SNAPSHOT_MISMATCH")
    if not manifest["synthetic"] or not ds.startswith("SYNTHETIC_") or manifest["authorization_status"] != "SYNTHETIC_ONLY":
        raise ScienceError("REAL_IMPORT_NOT_AUTHORIZED", status=403)
    if target_view != "synthetic":
        raise ScienceError("SYNTHETIC_CANNOT_ENTER_REAL_VIEW", status=403)
    group = manifest.get("experiment_group")
    allowed = MODELS_A if group == GROUP_A else MODELS_B if group == GROUP_B else ()
    if manifest["task_class"] != TASK or not allowed or not set(manifest["model_id"]) <= set(allowed):
        raise ScienceError("MODEL_TASK_GROUP_MISMATCH")
    for name, expected in manifest["artifact_file_hashes"].items():
        file = (path / name).resolve()
        if not file.is_relative_to(path) or not file.is_file() or sha_file(file) != expected:
            raise ScienceError("ARTIFACT_HASH_MISMATCH", name)
    recorded = {}
    for line in (path / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        h, name = line.split("  ", 1)
        if name in recorded:
            raise ScienceError("DUPLICATE_HASH_ENTRY")
        file = (path / name).resolve()
        if not file.is_relative_to(path) or not file.is_file() or sha_file(file) != h:
            raise ScienceError("ARTIFACT_HASH_MISMATCH", name)
        recorded[name] = h
    if recorded != {**manifest["artifact_file_hashes"], "manifest.json": sha_file(path / "manifest.json")}:
        raise ScienceError("INCOMPLETE_ARTIFACT_HASH_LIST")
    actual = {p.name for p in path.iterdir() if p.is_file()}
    if actual != set(recorded) | {"SHA256SUMS.txt"}:
        raise ScienceError("UNMANIFESTED_ARTIFACT_FILE")
    ledger = json.loads((path / "sample_ledger.json").read_text(encoding="utf-8"))
    legal = support(ledger, manifest["experiment_group"], manifest["quality_scheme"])
    folds = json.loads((path / "folds.json").read_text(encoding="utf-8"))
    names = {f.name for f in fields(FoldSpec)}
    fold_index = {}
    for rec in folds:
        if rec["fold_id"] in fold_index:
            raise ScienceError("DUPLICATE_FOLD_ID")
        body = {k: v for k, v in rec.items() if k != "fold_hash"}
        if digest(body) != rec["fold_hash"] or ids_hash(rec["train_ids"]) != rec["train_ids_hash"] or ids_hash(rec["test_ids"]) != rec["test_ids_hash"]:
            raise ScienceError("FOLD_HASH_MISMATCH")
        f = FoldSpec(**{k: tuple(v) if isinstance(v, list) else v for k, v in rec.items() if k in names})
        validate_fold(f, legal)
        if f.dataset_id != ds or f.snapshot_id != snap or f.ledger_hash != digest(legal):
            raise ScienceError("FOLD_BINDING_MISMATCH")
        fold_index[f.fold_id] = f
    with (path / "predictions.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    seen = set()
    for r in rows:
        if any(n in r for n in ("y_obs", "Qobs", "observed")):
            raise ScienceError("LABEL_IN_PREDICTION_RECORD")
        if r["fold_id"] not in fold_index or r["sample_id"] not in fold_index[r["fold_id"]].test_ids or r["model_id"] not in manifest["model_id"]:
            raise ScienceError("PREDICTION_NOT_HELD_OUT")
        key = (r["model_id"], r["fold_id"], r["sample_id"])
        if key in seen:
            raise ScienceError("DUPLICATE_PREDICTION")
        seen.add(key)
    expected = {(m, f.fold_id, sid) for m in manifest["model_id"] for f in fold_index.values() for sid in f.test_ids}
    if seen != expected:
        raise ScienceError("INCOMPLETE_OOF_ARTIFACT")
    if manifest["train_ids_hash"] != digest({f.fold_id: ids_hash(f.train_ids) for f in fold_index.values()}) or manifest["test_ids_hash"] != digest({f.fold_id: ids_hash(f.test_ids) for f in fold_index.values()}):
        raise ScienceError("MANIFEST_FOLD_HASH_MISMATCH")
    return {"status": "VALID_SYNTHETIC_ARTIFACT_ONLY", "files_verified": len(recorded), "predictions_verified": len(rows),
            "run_id": manifest["run_id"], "real_import_performed": False}
