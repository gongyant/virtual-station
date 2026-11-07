import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round2"


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(name):
    with (OUT / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_frozen_dataset_hash_and_year_scope():
    manifest = json.loads((OUT / "multiyear_dataset_manifest.json").read_text(encoding="utf-8"))
    canonical = OUT / "multiyear_byblk_dsk_daily_canonical.csv"
    assert sha256(canonical) == manifest["canonical_sha256"]
    rows = read_csv("multiyear_byblk_dsk_daily_canonical.csv")
    assert len(rows) == 4382
    assert {row["year"] for row in rows} == {str(year) for year in range(1978, 1984)}
    assert {row["station_id"] for row in rows} == {"00705600", "00705700"}
    assert not any(row["is_imputed"].lower() == "true" for row in rows)
    assert not any(row["is_model_generated"].lower() == "true" for row in rows)


def test_all_raw_processed_values_were_compared():
    rows = read_csv("source_audit/raw_processed_value_comparison.csv")
    assert len(rows) == 4382
    assert all(row["all_stages_match"].lower() == "true" for row in rows)


def test_m0_official_parameter_hash_is_unchanged():
    protocol = json.loads((OUT / "model_protocol_frozen.json").read_text(encoding="utf-8"))
    path = ROOT / protocol["M0_parameter_file"]
    assert sha256(path) == protocol["M0_expected_sha256"]


def test_model_input_access_excludes_revealed_years_and_forbidden_features():
    audit = json.loads((OUT / "model_input_access_audit.json").read_text(encoding="utf-8"))
    assert audit["year_min"] == 1978 and audit["year_max"] == 1983
    assert not audit["contains_2000"] and not audit["contains_2001"] and not audit["contains_2011"]
    assert not audit["stage_d4b_files_read"]
    assert not audit["DSK_used_as_predictor"]
    assert not audit["ERA5_used"] and not audit["MQ_used"] and not audit["stage_used"] and not audit["Yanqi_used"]
    assert not any("stage_d4b" in path.lower() for path in audit["files_read"])
    source = (ROOT / "scripts/run_stage_d5_round2_nested_loyo.py").read_text(encoding="utf-8")
    assert "outputs/diagnosis_2005_snapshot/stage_d4b" not in source.replace("\\", "/").lower()


def test_common_scoring_windows_are_frozen():
    rows = read_csv("outer_year_predictions.csv")
    common_counts = {}
    for row in rows:
        if row["scoring_common"].lower() == "true":
            common_counts[row["year"]] = common_counts.get(row["year"], 0) + 1
    assert common_counts == {"1978": 305, "1979": 335, "1980": 336, "1981": 335, "1982": 335, "1983": 335}


def test_nested_selection_never_uses_outer_year():
    metrics = [row for row in read_csv("outer_year_metrics.csv") if row["row_type"] == "year"]
    assert len(metrics) == 18
    for row in metrics:
        assert row["year"] not in row["outer_train_years"].split("|")
    selected = [row for row in read_csv("inner_selection_records.csv") if row["record_type"] == "candidate_summary" and row["selected"].lower() == "true"]
    assert len(selected) == 6
    assert {row["outer_year"] for row in selected} == {str(year) for year in range(1978, 1984)}


def test_round_stops_without_m3():
    decision = json.loads((OUT / "model_promotion_decision.json").read_text(encoding="utf-8"))
    assert not decision["M3_development_authorized"]
    assert set(decision["models"]) == {"M1", "M2"}
