from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from scripts.run_stage_rs_w0_landsat_audit import (
    CANONICAL_ASSETS,
    FROZEN_D11_HASHES,
    MAX_TIME_DIFFERENCE_DAYS,
    OUT,
    ROOT,
    sha256,
    validate_tiff,
)


def test_frozen_d11_is_unchanged() -> None:
    d11 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d11_geometry_cross_validation"
    for name, expected in FROZEN_D11_HASHES.items():
        assert sha256(d11 / name) == expected


def test_ground_measurement_contract_and_counts() -> None:
    ground = pd.read_csv(OUT / "ground_measurement_dates_for_remote_sensing.csv", dtype={"station_id": str})
    ground.station_id = ground.station_id.str.zfill(8)
    assert len(ground) == 72
    assert ground.groupby("station_id").size().to_dict() == {"00705600": 24, "00705700": 48}
    assert {"date", "H", "Q", "A", "W", "D", "V", "source_file", "measurement_quality"}.issubset(ground.columns)


def test_canonical_coordinates_are_kmz_verified() -> None:
    coordinates = pd.read_csv(OUT / "canonical_station_coordinates.csv", dtype={"station_id": str})
    coordinates.station_id = coordinates.station_id.str.zfill(8)
    assert coordinates.coordinate_status.eq("verified_KMZ_Point_canonical_station_coordinate").all()
    byblk = coordinates.set_index("station_id").loc["00705600"]
    dsk = coordinates.set_index("station_id").loc["00705700"]
    assert abs(byblk.longitude - 84.13580555555552) < 1e-10
    assert abs(dsk.longitude - 85.7349722222222) < 1e-10
    assert coordinates.candidate_section_coordinate_status.str.contains("not_georeferenced").all()


def test_measurement_and_satellite_dates_are_not_conflated() -> None:
    inventory = pd.read_csv(OUT / "remote_sensing_scene_inventory.csv")
    assert {"measurement_date", "satellite_date", "time_difference_days", "date_difference_days"}.issubset(inventory.columns)
    paired = inventory.loc[inventory.satellite_date.notna() & inventory.satellite_date.ne("")].copy()
    calculated = (pd.to_datetime(paired.satellite_date) - pd.to_datetime(paired.measurement_date)).dt.days
    assert (calculated == paired.time_difference_days).all()
    assert (paired.date_difference_days == paired.time_difference_days).all()
    assert paired.absolute_time_difference_days.le(MAX_TIME_DIFFERENCE_DAYS).all()


def test_selected_scenes_pass_cloud_local_qa_and_no_extrapolated_dates() -> None:
    inventory = pd.read_csv(OUT / "remote_sensing_scene_inventory.csv")
    selected = inventory.loc[inventory.selected_for_measurement]
    assert selected.cloud_cover_scene.le(40).all()
    assert selected.absolute_time_difference_days.le(8).all()
    assert selected.usable_for_width.all()
    assert not selected.target_local_cloud_flag.any()
    assert not selected.target_cloud_shadow_flag.any()
    assert not selected.snow_ice_flag.any()
    assert not selected.fill_or_zero_flag.any()
    assert not selected.landsat7_slc_off_target_gap.any()


def test_downloaded_geotiffs_are_complete_and_georeferenced() -> None:
    inventory = pd.read_csv(OUT / "remote_sensing_scene_inventory.csv")
    scenes = inventory.loc[inventory.download_status.isin(["downloaded_complete", "resumed_complete"]), "scene_directory"].dropna().drop_duplicates()
    assert len(scenes) > 0
    for relative in scenes:
        scene = ROOT / relative
        assert (scene / "complete.json").exists()
        for canonical_name in CANONICAL_ASSETS:
            validation = validate_tiff(scene / "cropped" / f"{canonical_name}.tif")
            assert validation["valid"], (relative, canonical_name, validation)


def test_all_unselected_candidates_have_a_reason() -> None:
    inventory = pd.read_csv(OUT / "remote_sensing_scene_inventory.csv")
    unselected = inventory.loc[~inventory.selected_for_measurement]
    assert unselected.rejection_reason.fillna("").str.len().gt(0).all()


def test_scientific_integrity_and_stop_boundary() -> None:
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    assert result["scene_selection_used_ground_q"] is False
    assert result["width_threshold_fitted"] is False
    assert result["discharge_model_fitted"] is False
    assert result["sentinel2_used_for_2011"] is False
    assert result["rs_w1_started"] is False
    assert result["d9_to_d12_modified"] is False


def test_script_has_no_model_training_or_q_based_scene_selection() -> None:
    source = (ROOT / "scripts/run_stage_rs_w0_landsat_audit.py").read_text(encoding="utf-8").lower()
    forbidden = ["import torch", "from torch", "fit_predict", "q_target", "observed_q"]
    assert all(token not in source for token in forbidden)
