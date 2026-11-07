from __future__ import annotations

import json

import pandas as pd

from scripts.run_stage_d11_geometry_cross_validation import OUT, PROTOCOL, sha256


def test_d11_holds_out_complete_months_and_uses_common_support() -> None:
    predictions = pd.read_csv(OUT / "outer_month_predictions.csv", parse_dates=["date"])
    assert len(predictions) == 24
    assert predictions.held_month.eq(predictions.date.dt.month).all()
    assert predictions.common_support.equals(
        predictions.M0_global_inside_domain & predictions.M1_regime_inside_domain
    )
    assert int(predictions.common_support.sum()) == 12


def test_d11_result_obeys_frozen_gate_without_posthoc_relaxation() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    assert result["protocol_sha256"] == sha256(PROTOCOL)
    assert protocol["gate"]["common_support_coverage_min"] == 0.6
    assert result["common_support_coverage"] == 0.5
    assert result["primary_area_mae_relative_improvement"] > 0.8
    assert result["gate_passed"] is False
    assert result["gate_failure_reasons"] == [
        "common_support_coverage_below_frozen_0.60_threshold"
    ]


def test_d11_script_does_not_read_daily_discharge_or_d9_parameters() -> None:
    source = (
        OUT.parents[2] / "scripts/run_stage_d11_geometry_cross_validation.py"
    ).read_text(encoding="utf-8")
    assert "daily_discharge" not in source
    assert "D9B_PARAMETERS" not in source
    assert "run_stage_d9_physics_increment" not in source
