from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(r"E:\CodexProject\DeepBas-VHS-GT-Lite-v0.1")
D4A = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b"
EXPECTED_PARAMETER_SHA256 = "a24e946ae16b3ebb72f2f0765d1562f9c945a18692bd48471ec1300231f1a838"
EXPECTED_STATIONS = {"00705600": "巴音布鲁克", "00705700": "大山口", "00705850": "焉耆"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def require_8_digit_id(value: str) -> str:
    value = str(value)
    if not re.fullmatch(r"\d{8}", value):
        raise ValueError(f"station_id is not an 8-digit string: {value!r}")
    return value


def canonicalize_discharge() -> tuple[Path, Path, dict]:
    src = D4A / "daily_discharge_2011_reviewed_v2.csv"
    source_rows = read_csv(src)
    fields = ["station_id", "station_name", "date", "discharge_m3s", "unit", "confirmation_status", "source_file", "source_page", "source_cell", "reviewer", "review_date"]
    rows = []
    mapping_counts = Counter()
    for r in source_rows:
        sid = require_8_digit_id(r["station_id"])
        if sid not in EXPECTED_STATIONS:
            continue
        if sid in {"00705600", "00705700"}:
            q = r.get("value", "")
            mapping_counts["value->discharge_m3s"] += 1
        else:
            q = r.get("discharge", "")
            mapping_counts["discharge->discharge_m3s"] += 1
        if q == "":
            raise ValueError(f"missing discharge_m3s for {sid} {r['date']}")
        rows.append({
            "station_id": sid,
            "station_name": r["station_name"],
            "date": r["date"],
            "discharge_m3s": q,
            "unit": "m3/s",
            "confirmation_status": r.get("confirmation_status", ""),
            "source_file": r.get("source_file", ""),
            "source_page": r.get("source_page", ""),
            "source_cell": r.get("source_cell", "") or r.get("source_cell_or_row", ""),
            "reviewer": r.get("reviewer", ""),
            "review_date": r.get("review_date", ""),
        })
    rows.sort(key=lambda x: (x["station_id"], x["date"]))
    per_station = Counter(r["station_id"] for r in rows)
    unique_pairs = len({(r["station_id"], r["date"]) for r in rows})
    checks = {
        "row_count_1095": len(rows) == 1095,
        "each_station_365": per_station == Counter({sid: 365 for sid in EXPECTED_STATIONS}),
        "station_date_unique": unique_pairs == len(rows),
        "no_missing_discharge_m3s": all(r["discharge_m3s"] != "" for r in rows),
        "all_station_ids_8_digit_strings": all(re.fullmatch(r"\d{8}", r["station_id"]) is not None for r in rows),
        "only_expected_stations": set(per_station) == set(EXPECTED_STATIONS),
    }
    if not all(checks.values()):
        raise RuntimeError(f"canonical discharge checks failed: {checks}")
    out = OUT / "daily_discharge_2011_canonical.csv"
    write_csv(out, fields, rows)
    by_rows = [{"station_id": r["station_id"], "date": r["date"], "discharge_m3s": r["discharge_m3s"]} for r in rows if r["station_id"] == "00705600"]
    by_input = OUT / "boundary_only_2011_byblk_input_frozen.csv"
    write_csv(by_input, ["station_id", "date", "discharge_m3s"], by_rows)
    return out, by_input, {
        "source_file": str(src.relative_to(ROOT)).replace("\\", "/"),
        "source_sha256": sha256(src),
        "canonical_file": str(out.relative_to(ROOT)).replace("\\", "/"),
        "canonical_sha256": sha256(out),
        "byblk_prediction_input_file": str(by_input.relative_to(ROOT)).replace("\\", "/"),
        "byblk_prediction_input_sha256": sha256(by_input),
        "field_mapping": {"00705600": "value -> discharge_m3s", "00705700": "value -> discharge_m3s", "00705850": "discharge -> discharge_m3s"},
        "mapping_counts": dict(mapping_counts),
        "station_row_counts": dict(per_station),
        "checks": checks,
    }


def canonicalize_stage() -> tuple[Path, dict]:
    src = D4A / "daily_stage_2011_reviewed_v2.csv"
    rows = []
    for r in read_csv(src):
        sid = require_8_digit_id(r["station_id"])
        if r.get("stage", "") == "":
            raise ValueError(f"missing stage for {sid} {r['date']}")
        rows.append({
            "station_id": sid, "station_name": r["station_name"], "date": r["date"], "stage_m": r["stage"], "unit": "m",
            "confirmation_status": r.get("confirmation_status", ""), "source_file": r.get("source_file", ""), "source_page": r.get("source_page", ""),
            "source_cell": r.get("source_cell", ""), "reviewer": r.get("reviewer", ""), "review_date": r.get("review_date", ""),
        })
    rows.sort(key=lambda x: (x["station_id"], x["date"]))
    if len(rows) != 365 or len({(r["station_id"], r["date"]) for r in rows}) != len(rows):
        raise RuntimeError("canonical stage requires 365 unique Yanqi dates")
    out = OUT / "daily_stage_2011_canonical.csv"
    fields = ["station_id", "station_name", "date", "stage_m", "unit", "confirmation_status", "source_file", "source_page", "source_cell", "reviewer", "review_date"]
    write_csv(out, fields, rows)
    return out, {"source_file": str(src.relative_to(ROOT)).replace("\\", "/"), "source_sha256": sha256(src), "canonical_sha256": sha256(out), "row_count": len(rows), "field_mapping": {"stage": "stage_m"}}


def canonicalize_measurements() -> tuple[Path, dict]:
    src = D4A / "discharge_measurements_2011_reviewed_v2.csv"
    source_rows = read_csv(src)
    counters = defaultdict(int)
    rows = []
    for r in source_rows:
        sid = require_8_digit_id(r["station_id"])
        key = (sid, r["date"])
        counters[key] += 1
        seq = counters[key]
        qav = r.get("qav_check", "")
        rel = r.get("relative_error", "")
        q_derived = r.get("q_derived", "")
        note = r.get("confirmation_note", "")
        if sid == "00705850" and r["date"] == "2011-02-28":
            if not (r.get("discharge") == "37.2" and r.get("cross_section_area") in {"182", "182.0"} and r.get("mean_velocity") in {"0.2", "0.20"}):
                raise RuntimeError("Yanqi 2011-02-28 source values differ from frozen review values")
            qav = "review_rounding"
            q_derived = "36.4"
            rel = "0.021505"
            note = (note + "；" if note else "") + "Q、A、V保持原值；2.1505%差异标记为舍入复核。"
        rows.append({
            "measurement_id": f"{sid}_{r['date']}_{seq:02d}", "station_id": sid, "station_name": r["station_name"], "date": r["date"], "sequence": str(seq),
            "stage_m": r.get("stage", ""), "discharge_m3s": r.get("discharge", ""), "area_m2": r.get("cross_section_area", ""),
            "mean_velocity_ms": r.get("mean_velocity", ""), "max_velocity_ms": r.get("max_velocity", ""), "width_m": r.get("surface_width", ""),
            "mean_depth_m": r.get("mean_depth", ""), "max_depth_m": r.get("max_depth", ""), "q_derived_m3s": q_derived, "relative_error": rel,
            "qav_check": qav, "measurement_method": r.get("measurement_method", ""), "control_note": r.get("control_note", ""), "condition_code": r.get("condition_code", ""),
            "confirmation_status": r.get("confirmation_status", ""), "confirmation_note": note, "source_file": r.get("source_file", ""), "source_page": r.get("source_page", ""),
            "source_cell": r.get("source_cell", "") or r.get("source_cell_or_row", ""), "reviewer": r.get("reviewer", ""), "review_date": r.get("review_date", ""),
        })
    if len(rows) != 125 or len({r["measurement_id"] for r in rows}) != len(rows):
        raise RuntimeError("measurement canonicalization lost rows or produced duplicate IDs")
    stats = defaultdict(Counter)
    for r in rows:
        stats[r["station_id"]][r["qav_check"]] += 1
    expected = {
        "00705600": Counter({"pass": 24}),
        "00705700": Counter({"pass": 48}),
        "00705850": Counter({"pass": 52, "review_rounding": 1}),
    }
    if {k: v for k, v in stats.items()} != expected:
        raise RuntimeError(f"unexpected QAV summary: {stats}")
    out = OUT / "discharge_measurements_2011_canonical.csv"
    fields = ["measurement_id", "station_id", "station_name", "date", "sequence", "stage_m", "discharge_m3s", "area_m2", "mean_velocity_ms", "max_velocity_ms", "width_m", "mean_depth_m", "max_depth_m", "q_derived_m3s", "relative_error", "qav_check", "measurement_method", "control_note", "condition_code", "confirmation_status", "confirmation_note", "source_file", "source_page", "source_cell", "reviewer", "review_date"]
    write_csv(out, fields, rows)
    return out, {
        "source_file": str(src.relative_to(ROOT)).replace("\\", "/"), "source_sha256": sha256(src), "canonical_sha256": sha256(out), "row_count": len(rows),
        "field_mapping": {"stage": "stage_m", "discharge": "discharge_m3s", "cross_section_area": "area_m2", "mean_velocity": "mean_velocity_ms", "surface_width": "width_m"},
        "measurement_id_rule": "station_id + '_' + date + '_' + two-digit within-station-date source-order sequence",
        "qav_summary": {sid: dict(counts) for sid, counts in stats.items()},
        "yanqi_2011_02_28": {"Q": "37.2", "A": "182", "V": "0.20", "Q_derived": "36.4", "relative_error": "0.021505", "qav_check": "review_rounding", "numeric_values_modified": False},
    }


def parameter_integrity() -> dict:
    path = D4A / "boundary_only_frozen_parameters_2005.json"
    actual = sha256(path)
    p = json.loads(path.read_text(encoding="utf-8"))
    weights = p.get("weights", [])
    lags = [x.get("lag_day") for x in weights]
    values = [x.get("weight") for x in weights]
    checks = {
        "sha256_matches_expected": actual == EXPECTED_PARAMETER_SHA256,
        "model_name": p.get("model_name") == "C_EXT_boundary_only_K10",
        "intercept_b_present": isinstance(p.get("intercept_b"), (int, float)),
        "lag0_to_lag10_exactly_once": lags == list(range(11)),
        "all_weights_nonnegative": len(values) == 11 and all(isinstance(x, (int, float)) and x >= 0 for x in values),
        "training_row_count_113": p.get("training_period", {}).get("row_count") == 113,
        "training_date_range": p.get("training_period", {}).get("start") == "2005-05-11" and p.get("training_period", {}).get("end") == "2005-08-31",
        "no_2011_dsk_labels": p.get("used_2011_labels") is False and p.get("used_2011_dsk_q") is False and p.get("used_2011_dsk_mq") is False,
        "no_2005_sep_oct_legacy": p.get("used_2005_legacy_sep_oct") is False and p.get("training_period", {}).get("legacy_2005_sep_oct_used") is False,
    }
    audit = {
        "parameter_file": str(path.relative_to(ROOT)).replace("\\", "/"), "expected_sha256": EXPECTED_PARAMETER_SHA256, "actual_sha256": actual,
        "checks": checks, "passed": all(checks.values()), "prediction_authorized": all(checks.values()),
        "verified_model_summary": {"model_name": p.get("model_name"), "intercept_b": p.get("intercept_b"), "weight_count": len(weights), "lags": lags, "training_period": p.get("training_period")},
    }
    (OUT / "boundary_only_parameter_integrity_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protocol = OUT / "boundary_only_2011_evaluation_protocol_frozen.json"
    if not protocol.exists():
        raise RuntimeError("evaluation protocol must be frozen before canonicalization and prediction")
    q_path, by_input, q_audit = canonicalize_discharge()
    h_path, h_audit = canonicalize_stage()
    m_path, m_audit = canonicalize_measurements()
    integrity = parameter_integrity()
    schema = {
        "schema_version": "1.0", "created_after_protocol_freeze": True, "protocol_sha256": sha256(protocol),
        "daily_discharge": q_audit, "daily_stage": h_audit, "discharge_measurements": m_audit,
        "canonical_files": {q_path.name: sha256(q_path), h_path.name: sha256(h_path), m_path.name: sha256(m_path), by_input.name: sha256(by_input)},
        "numeric_confirmation_values_modified": False,
    }
    (OUT / "daily_discharge_2011_schema_audit.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not integrity["passed"]:
        raise SystemExit("parameter integrity gate failed; 2011 prediction is forbidden")
    print(json.dumps({"status": "canonical_ready", "parameter_gate": "pass", "rows": {"discharge": 1095, "stage": 365, "measurements": 125}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
