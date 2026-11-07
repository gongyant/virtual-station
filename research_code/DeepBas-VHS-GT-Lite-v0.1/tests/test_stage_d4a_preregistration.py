import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a"


def test_qingshui_is_river_not_station():
    aliases = pd.read_csv(OUT / "station_aliases_v2.csv")
    row = aliases[aliases.alias == "清水河"].iloc[0]
    assert row.alias_type == "river_name_not_station"
    assert str(row.automatic_mapping_allowed).lower() == "false"
    coords = pd.read_csv(OUT / "station_coordinate_audit_2011.csv")
    assert "清水河" not in set(coords.station_name)
    assert coords.loc[coords.station_name == "克尔古提", "river_name_expected"].iloc[0] == "清水河"


def test_station_alias_mappings():
    aliases = pd.read_csv(OUT / "station_aliases_v2.csv").set_index("alias")
    assert aliases.loc["新曲满", "canonical_name"] == "新渠满（三）"
    assert aliases.loc["塔什店", "canonical_name"] == "他什店（五）"


def test_degree_minute_geographic_parse_does_not_require_gauss_zone():
    df = pd.read_csv(OUT / "station_coordinate_audit_2011.csv")
    assert (df.coordinate_form == "geographic_degree_minute").all()
    assert (~df.projection_zone_required_for_parsing.astype(bool)).all()
    assert (~df.central_meridian_required_for_parsing.astype(bool)).all()
    assert df.decimal_longitude_under_source_datum.notna().all()


def test_raw_coordinates_are_preserved_and_wgs84_not_assumed():
    df = pd.read_csv(OUT / "station_coordinate_audit_2011.csv")
    assert df.raw_longitude.str.contains("°").all()
    assert df.raw_latitude.str.contains("°").all()
    assert df.raw_coordinate_preserved.astype(bool).all()
    assert (~df.wgs84_assumed.astype(bool)).all()
    assert (df.selected_candidate == "none_pending_manual_review").all()


def test_reviewed_values_have_manual_confirmation_record():
    audit = pd.read_csv(OUT / "manual_transcription_audit_2011.csv")
    confirmed = audit[audit.confirmation_status == "manual_visual_confirmed"]
    assert len(confirmed) == 783
    assert confirmed.confirmed_value.notna().all()
    assert confirmed.reviewer.notna().all()
    assert confirmed.source_page.notna().all()
    assert not confirmed.extraction_method.str.contains("ocr", case=False, na=False).any()


def test_instantaneous_extremes_are_not_in_daily_mean_layer():
    daily = pd.read_csv(OUT / "daily_discharge_2011_reviewed_v2.csv")
    forbidden = {"instantaneous_max", "instantaneous_min", "瞬时最大", "瞬时最小"}
    for col in daily.columns:
        if col in {"variable", "value_type", "statistic_type"}:
            assert not set(daily[col].dropna().astype(str)) & forbidden
    assert "instantaneous_extreme" not in " ".join(daily.columns).lower()


def test_boundary_parameters_do_not_use_2011_labels():
    p = json.loads((OUT / "boundary_only_frozen_parameters_2005.json").read_text(encoding="utf-8"))
    assert p["K"] == 10
    assert p["coefficient_constraint"] == "w_k >= 0"
    assert p["used_2011_labels"] is False
    assert p["used_2011_dsk_q"] is False
    assert p["used_2011_dsk_mq"] is False
    assert p["training_period"]["end"] < "2005-09-01"
    assert p["used_2005_legacy_sep_oct"] is False


def test_scoring_protocol_requires_matching_parameter_hash():
    param = OUT / "boundary_only_frozen_parameters_2005.json"
    protocol = json.loads((OUT / "boundary_only_frozen_predictions_protocol.json").read_text(encoding="utf-8"))
    actual = hashlib.sha256(param.read_bytes()).hexdigest()
    assert protocol["hash_required_before_scoring"] is True
    assert protocol["parameter_file_sha256"] == actual
    assert protocol["score_2011_now"] is False


def test_main_stage_c_external_protocol_is_blocked_without_mq():
    text = (OUT / "boundary_only_external_preregistration_zh.md").read_text(encoding="utf-8")
    assert "blocked_missing_2011_DSK_MQ" in text
    assert "2011 DSK MQ reference不存在" in text


def test_boundary_only_name_is_not_stage_c_main_and_not_called_blind_test():
    p = json.loads((OUT / "boundary_only_frozen_parameters_2005.json").read_text(encoding="utf-8"))
    protocol = json.loads((OUT / "boundary_only_frozen_predictions_protocol.json").read_text(encoding="utf-8"))
    assert p["model_name"] == "C_EXT_boundary_only_K10"
    assert "not_stage_c_main_model" in p["model_role"]
    assert protocol["scoring_contract"]["reported_term"] == "预注册跨年份评估"
    assert protocol["scoring_contract"]["forbidden_term"] == "完全盲测"
