"""Reuse frozen S1 QC on synthetic values; real access is metadata only."""
import calendar
import csv
import hashlib
import json
from pathlib import Path
import numpy as np
from .admission import station_year, public_month, VERSION
from .contracts import ScienceError, digest

S1 = Path(r"E:\VHS_WorkBuddy_S1T_Sandbox\output\vhs_sci_s1_sample_admission")


def synthetic_ledger(features, labels, upstream=None):
    features.require_synthetic()
    rows, decisions = [], {}
    for y in sorted(set(features.years.tolist())):
        mask = features.years == y
        for station, values in (("up", None if upstream is None else np.asarray(upstream)[mask]), ("down", np.asarray(labels)[mask])):
            raw = None
            if values is not None:
                if len(values) != 12:
                    raise ScienceError("SYNTHETIC_YEAR_NOT_COMPLETE")
                w = sum(v * calendar.monthrange(y, m)[1] * 86400 for m, v in enumerate(values, 1)) / 1e6
                # Synthetic auxiliary-only conflict reproduces the GROUP A support shape.
                if station == "up" and y == 2008:
                    w *= 0.5
                raw = {"mean": values.tolist(), "min": (values * 0.2).tolist(), "max": (values * 2).tolist(), "W": w}
            decisions[(station, y)] = station_year(y, raw)
    for k in features.keys:
        r = {"sample_id": k.sample_id, "dataset_id": k.dataset_id, "data_snapshot_id": k.snapshot_id,
             "station_id": k.station_id, "year": k.year, "month": k.month, "quality_rule_version": VERSION,
             "meteorology_valid": bool(features.columns.get("met_complete", np.ones(len(features.keys), bool))[len(rows)]),
             "synthetic": True}
        for prefix in ("up", "down"):
            r.update({prefix + "_" + name: value for name, value in public_month(decisions[(prefix, k.year)], k.month).items()})
        for scheme in ("claude_core", "strict", "mean_first", "stress"):
            r["common_pair_" + scheme] = r["up_" + scheme + "_usable"] and r["down_" + scheme + "_usable"]
        rows.append(r)
    return rows


def load_S1_metadata(path=S1):
    path = Path(path)
    manifest = json.loads((path / "DELIVERY_SHA256.json").read_text(encoding="utf-8"))
    mismatches = []
    for item in manifest["files"]:
        p = (path / item["file"]).resolve()
        if not p.is_relative_to(path.resolve()) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != item["sha256"]:
            mismatches.append(item["file"])
    if mismatches:
        raise ScienceError("S1_DELIVERY_HASH_MISMATCH", str(mismatches))
    doc = json.loads((path / "sample_ledger_16037_16039.json").read_text(encoding="utf-8"))
    source = json.loads((path / "source_snapshot.json").read_text(encoding="utf-8"))
    if doc["dataset_id"] != source["dataset_id"] or doc["snapshot_id"] != source["snapshot_id"]:
        raise ScienceError("S1_SNAPSHOT_BINDING_MISMATCH")
    rows = doc["samples"]
    with (path / "sample_ledger_16037_16039.csv").open(encoding="utf-8-sig", newline="") as f:
        csvrows = list(csv.DictReader(f))
    if csvrows != [{k: str(v) for k, v in r.items()} for r in rows]:
        raise ScienceError("S1_CSV_JSON_MISMATCH")
    for r in rows:
        if r["dataset_id"] != doc["dataset_id"] or r["data_snapshot_id"] != doc["snapshot_id"]:
            raise ScienceError("S1_ROW_BINDING_MISMATCH")
        if any(k in r for k in ("value", "Qd", "Qu", "W_source", "W_from_Q")):
            raise ScienceError("REAL_VALUES_NOT_ALLOWED_IN_S1_METADATA_PATH")
    return rows, {"S1_files_verified": len(manifest["files"]), "dataset_id": doc["dataset_id"],
                  "snapshot_id": doc["snapshot_id"], "ledger_hash": digest(rows),
                  "ledger_file_sha256": hashlib.sha256((path / "sample_ledger_16037_16039.json").read_bytes()).hexdigest(),
                  "S1_manifest_sha256": hashlib.sha256((path / "DELIVERY_SHA256.json").read_bytes()).hexdigest(),
                  "teacher_Q_values_opened": False}
