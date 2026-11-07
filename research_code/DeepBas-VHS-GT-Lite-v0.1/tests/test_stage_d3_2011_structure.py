from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "diagnosis_2005_snapshot" / "stage_d3"


def read(name):
    return pd.read_csv(OUT / name, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def true_values(series):
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def test_year_is_2011_for_all_dated_stage_d3_tables():
    for name in ["daily_discharge_2011_ocr_draft.csv", "daily_stage_2011_ocr_draft.csv", "meteorology_2011_ocr_draft.csv", "instantaneous_extremes_2011.csv", "discharge_measurements_2011.csv"]:
        df = read(name)
        assert set(df["year"]) == {"2011"}


def test_each_station_has_at_most_365_natural_days_per_daily_variable():
    for name in ["daily_discharge_2011_ocr_draft.csv", "daily_stage_2011_ocr_draft.csv", "meteorology_2011_ocr_draft.csv"]:
        df = read(name)
        counts = df.groupby(["station_id", "variable"])["date"].nunique()
        assert (counts <= 365).all()
        assert not df.duplicated(["station_id", "variable", "date"]).any()


def test_instantaneous_extremes_are_not_daily_discharge_rows():
    daily = read("daily_discharge_2011_ocr_draft.csv")
    extremes = read("instantaneous_extremes_2011.csv")
    assert "extreme_type" not in daily.columns
    assert set(extremes["extreme_type"]) == {"instantaneous_max", "instantaneous_min"}
    assert not daily["source_table"].str.contains("瞬时极值").any()


def test_relative_section_position_does_not_modify_bed_elevation():
    points = read("cross_section_points_2011_reviewed.csv")
    assert set(points["relative_section_position"]) == {"基上", "基下"}
    assert (pd.to_numeric(points["elevation_offset_applied_m"]) == 0).all()


def test_xian_coordinates_are_not_silently_converted_to_wgs84():
    stations = read("station_inventory_2011.csv")
    assert stations["horizontal_coordinate_system"].str.contains("西安坐标系").all()
    assert set(stations["projection_zone"]) == {"unknown"}
    assert set(stations["central_meridian"]) == {"unknown"}
    assert not true_values(stations["coordinate_conversion_performed"]).any()
    assert not true_values(stations["wgs84_conversion_allowed"]).any()


def test_missing_vertical_datum_blocks_manning_and_geometry():
    geometry = read("cross_section_geometry_2011.csv")
    assert geometry["geometry_status"].eq("blocked_vertical_datum_not_confirmed").all()
    assert not true_values(geometry["manning_allowed"]).any()
    assert geometry[["area_A_m2", "wetted_perimeter_P_m", "hydraulic_radius_R_m", "surface_width_W_m"]].eq("").all().all()


def test_dem_slope_requires_along_river_sampling():
    slopes = read("dem_reach_slopes_2011.csv")
    assert true_values(slopes["along_river_sampling"]).all()
    assert slopes["dem_derived_slope_proxy"].eq("").all()
    assert slopes["status"].eq("blocked_no_dem_raster").all()


def test_dsk_is_controlled_downstream():
    text = (OUT / "dsk_mechanism_classification_2011_zh.md").read_text(encoding="utf-8")
    assert "mechanism_type = controlled_downstream" in text
    assert "station_relative_to_gate = downstream" in text
    assert "gate_operation_data_available = false" in text


def test_gate_opening_feature_is_absent_without_gate_data():
    for name in ["daily_discharge_2011_ocr_draft.csv", "daily_stage_2011_ocr_draft.csv", "meteorology_2011_ocr_draft.csv", "discharge_measurements_2011.csv"]:
        assert "gate_opening" not in read(name).columns


def test_2011_labels_are_excluded_from_stage_c_reselection():
    audit = read("stage_c_2011_external_input_audit.csv")
    row = audit[audit["item"] == "2011_label_excluded_from_reselection"].iloc[0]
    assert row["pass"].lower() == "true"
    protocol = (OUT / "stage_c_2011_external_protocol_zh.md").read_text(encoding="utf-8")
    assert "不得参与重新选择" in protocol


def test_p1b_is_not_presented_as_p2():
    protocol = (OUT / "stage_c_2011_external_protocol_zh.md").read_text(encoding="utf-8")
    assert "D-P1B" in protocol
    assert "不是P2" in protocol


def test_ocr_changes_require_an_audit_log():
    audit = read("ocr_revision_audit_2011.csv")
    required = {"audit_id", "station_id", "date", "variable", "old_value", "new_value", "reason", "source_page", "reviewer", "review_date", "status"}
    assert required.issubset(audit.columns)


def test_ocr_draft_and_reviewed_daily_discharge_are_separate():
    draft = read("daily_discharge_2011_ocr_draft.csv")
    reviewed = read("daily_discharge_2011_reviewed.csv")
    assert not draft["extraction_method"].str.contains("frozen_stage_d2", na=False).any()
    assert reviewed["extraction_method"].str.contains("frozen_stage_d2", na=False).all()
    assert len(reviewed) == 730
