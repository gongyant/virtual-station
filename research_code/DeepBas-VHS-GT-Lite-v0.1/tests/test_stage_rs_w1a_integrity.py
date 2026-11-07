import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/rs_w1a"


def load_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_required_outputs_exist():
    required = [
        "dsk_unique_usable_scenes.csv",
        "dsk_candidate_transects.geojson",
        "dsk_width_estimates.csv",
        "dsk_width_validation_by_tier.csv",
        "dsk_transect_sensitivity.csv",
        "surface_reflectance_scaling_audit.json",
        "stage_rs_w1a_report_zh.md",
    ]
    assert all((OUT / name).is_file() for name in required)


def test_rs_w0_frozen_hashes_unchanged():
    audit = load_json("scientific_integrity_audit.json")
    assert audit["rs_w0_unchanged"]
    for rel, expected in audit["rs_w0_hashes_before"].items():
        path = ROOT / rel
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected


def test_unique_scene_independence_and_same_day_cases():
    scenes = pd.read_csv(OUT / "dsk_unique_usable_scenes.csv", dtype={"station_id": str})
    assert not scenes.duplicated(["station_id", "satellite_date", "landsat_product_id"]).any()
    assert scenes.unique_satellite_scene.astype(bool).all()
    same = set(scenes.loc[scenes.same_day_scene.astype(bool), "satellite_date"])
    assert same == {"2011-04-24", "2011-09-07"}


def test_threshold_and_transect_were_frozen_without_q_or_w():
    protocol = load_json("frozen_method_protocol.json")
    audit = load_json("scientific_integrity_audit.json")
    assert protocol["primary_threshold_method"] == "mndwi_fixed_0"
    assert protocol["primary_transect"] == "T0"
    assert protocol["fixed_thresholds"] == {"ndwi_fixed_0": 0.0, "mndwi_fixed_0": 0.0}
    assert not audit["q_used_for_threshold_scene_or_transect_selection"]
    assert not audit["ground_w_used_for_threshold_or_transect_selection"]


def test_tier_d_never_enters_primary_metrics():
    validation = pd.read_csv(OUT / "dsk_width_validation_by_tier.csv")
    assert not validation.tier_D_included.astype(bool).any()
    assert set(validation.tier_scope) == {"Tier A", "Tier A+B", "Tier A+B+C"}


def test_subpixel_label_and_failures_are_retained():
    widths = pd.read_csv(OUT / "dsk_width_estimates.csv")
    assert set(widths.subpixel_estimate_label) == {"subpixel edge-interpolated width estimate"}
    assert "measurement_status" in widths
    assert "failure_reason" in widths


def test_daily_hq_are_diagnostic_only():
    daily = pd.read_csv(OUT / "dsk_time_mismatch_hq_audit.csv")
    assert set(daily.use) == {"time_mismatch_diagnostic_only_not_scene_selection_or_thresholding"}


def test_pan_never_classifies_water():
    pan = pd.read_csv(OUT / "dsk_landsat7_pan_audit.csv")
    assert not pan.used_for_water_classification.astype(bool).any()


def test_no_downstream_stage_started():
    result = load_json("result.json")
    audit = load_json("scientific_integrity_audit.json")
    assert result["status"] == "completed_and_stopped"
    assert not result["rs_w1b_started"] and not result["rs_w2_started"]
    assert not audit["q_prediction_performed"]
    assert not audit["gnn_or_transformer_trained"]
    assert not audit["d9_to_d12_modified"]
