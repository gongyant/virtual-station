from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

from scripts.run_stage_d12a1_verification import (
    D11,
    EXPECTED_D11_HASHES,
    EXTRAPOLATION_ALLOWED,
    OPEN_MONTHS,
    OUT,
    assign_regime,
    exclude_held_calendar_month,
    sha256,
)


def test_d11_frozen_hashes_gate_and_records_unchanged() -> None:
    for name, expected in EXPECTED_D11_HASHES.items():
        assert sha256(D11 / name) == expected
    result = json.loads((D11 / "result.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(D11 / "outer_month_predictions.csv")
    assert result["gate_passed"] is False
    assert result["common_support_rows"] == 12
    assert len(predictions) == 24
    assert int(predictions.common_support.sum()) == 12


def test_stage_conflict_is_resolved_without_auto_merge() -> None:
    reconciliation = pd.read_csv(OUT / "stage_value_reconciliation.csv")
    september = reconciliation.loc[reconciliation.date.eq("2011-09-21")].iloc[0]
    assert september.section_survey_stage_m == 3.85
    assert september.daily_mean_stage_m == 3.87
    assert september.stage_for_section_geometry_m == 3.85
    assert not bool(september.same_gauge_datum_verified)
    assert not bool(september.verified_geometry_computation_allowed)


def test_no_verified_geometry_without_datum_evidence() -> None:
    for token in ("20110521", "20110921"):
        geometry = pd.read_csv(OUT / f"section_geometry_{token}.csv")
        points = pd.read_csv(OUT / f"pointwise_depths_{token}.csv")
        assert not geometry.vertical_datum_verified.any()
        assert geometry.area_m2.isna().all()
        assert geometry.top_width_m.isna().all()
        assert geometry.hydraulic_radius_m.isna().all()
        assert points.depth_m.isna().all()
        assert not points.verified.any()


def test_unverified_section_does_not_enter_training() -> None:
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    scenarios = pd.read_csv(OUT / "conditional_coverage_simulation.csv")
    decision = pd.read_csv(OUT / "auxiliary_mergeability_decision.csv").iloc[0]
    assert result["september_verified_auxiliary_geometry"] is False
    assert result["september_verified_mergeable"] is False
    assert result["verified_auxiliary_training_rows_added"] == 0
    assert not bool(decision.verified_mergeable)
    assert decision.training_pool_admission == "rejected"
    assert result["actual_common_support_after_verification"] == "12/24"
    assert not scenarios.admissible_training_now.any()
    assert set(scenarios.decision) == {
        "conditional_only_not_applied",
        "counterfactual_rejected_wrong_stage_semantics",
    }


def test_conditional_385_coverage_obeys_calendar_month_exclusion() -> None:
    scenarios = pd.read_csv(OUT / "conditional_coverage_simulation.csv")
    recovered = pd.read_csv(OUT / "conditional_recovered_records.csv")
    selected = scenarios.loc[scenarios.scenario_stage_m.eq(3.85)].iloc[0]
    selected_rows = recovered.loc[recovered.scenario_stage_m.eq(3.85)]
    assert selected.conditional_common_support_rows == 16
    assert set(selected_rows.date) == {
        "2011-05-10", "2011-05-15", "2011-05-25", "2011-05-26",
    }
    assert set(selected_rows.held_month) == {5}
    assert not selected_rows.admissible_now.any()
    assert scenarios.leave_one_calendar_month_out.all()


def test_held_calendar_month_is_excluded_across_all_years() -> None:
    records = pd.DataFrame({
        "date": ["2010-05-01", "2011-05-31", "2010-04-30", "2011-06-01"],
        "stage_m": [3.0, 3.1, 3.2, 3.3],
    })
    training = exclude_held_calendar_month(records, 5)
    assert set(pd.to_datetime(training.date).dt.month) == {4, 6}
    assert len(training) == 2


def test_daily_stage_is_description_not_geometry_label() -> None:
    audit = pd.read_csv(OUT / "daily_stage_support_audit.csv")
    assert len(audit) == 365
    assert not audit.geometry_label_available.any()
    assert not audit.used_as_geometry_test_label.any()
    assert not audit.used_to_change_d11_gate.any()
    assert set(audit.analysis_role) == {"descriptive_operational_support_only"}


def test_no_extrapolation_and_frozen_season_definition() -> None:
    assert EXTRAPOLATION_ALLOWED is False
    assert OPEN_MONTHS == frozenset({4, 5, 6, 7, 8, 9, 10})
    assert [assign_regime(m) for m in range(1, 13)] == [
        "cold_season", "cold_season", "cold_season", "open_water",
        "open_water", "open_water", "open_water", "open_water",
        "open_water", "open_water", "cold_season", "cold_season",
    ]


def test_no_forbidden_inputs_in_stage_script() -> None:
    source = (Path(__file__).parents[1] / "scripts/run_stage_d12a1_verification.py").read_text(encoding="utf-8").lower()
    forbidden = ["daily_discharge", "q_observed", "residual_parameters", "residual_blend"]
    assert all(token not in source for token in forbidden)


def test_bed_change_is_blocked_without_alignment_evidence() -> None:
    audit = pd.read_csv(OUT / "bed_stability_audit.csv").iloc[0]
    assert audit.stability_judgment == "insufficient_evidence"
    assert pd.isna(audit.bed_elevation_mae_m)
    assert pd.isna(audit.approximate_scour_fill_cross_sectional_area_m2)
    assert not bool(audit.horizontal_shift_optimized)
    assert not bool(audit.vertical_shift_optimized)


def test_svgs_valid_and_d12b_not_started() -> None:
    for token in ("20110521", "20110921"):
        root = ET.parse(OUT / f"section_profile_{token}.svg").getroot()
        assert root.tag.endswith("svg")
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    assert result["d12b_started"] is False
