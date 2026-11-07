from __future__ import annotations

import calendar
import json

import pandas as pd

from scripts.prepare_stage_d10_byblk_stage import (
    OUT as STAGE_OUT,
    PRINTED_MONTHLY_MEAN,
    TOKENS,
    expand_month,
)
from scripts.run_stage_d10b_regime_aware_geometry import OUT as D10B_OUT


def test_transcribed_stage_is_complete_and_retains_summary_discrepancy() -> None:
    values = []
    rounded_matches = []
    for month in range(1, 13):
        month_values = expand_month(TOKENS[month])
        assert len(month_values) == calendar.monthrange(2011, month)[1]
        values.extend(month_values)
        rounded_matches.append(
            round(sum(month_values) / len(month_values) + 1e-12, 2)
            == PRINTED_MONTHLY_MEAN[month]
        )

    assert len(values) == 365
    assert sum(rounded_matches) == 11
    assert rounded_matches[11] is False
    assert abs(sum(expand_month(TOKENS[12])) / 31 - 3.9919354839) < 1e-9

    manifest = json.loads((STAGE_OUT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["monthly_summary_discrepancy_months"] == [12]
    assert manifest["rows"] == 365


def test_d10b_keeps_posthoc_scope_and_frozen_improvement() -> None:
    manifest = json.loads((D10B_OUT / "manifest.json").read_text(encoding="utf-8"))
    metrics = pd.read_csv(D10B_OUT / "regime_aware_stage_physics_metrics.csv")
    primary = metrics.loc[metrics.window.eq("primary")].set_index("model")

    baseline = primary.loc["M0_frozen_K10"]
    frozen = primary.loc["M2_frozen_D9B_residual"]
    assert manifest["initiated_after_d10_primary_was_observed"] is True
    assert manifest["scientific_scope"] == "post-D10 root-cause diagnostic only"
    assert manifest["frozen_parameters"]["manning_n"] == 0.02
    assert manifest["frozen_parameters"]["side_slope_h_to_v"] == 1.0
    assert manifest["primary_physics_coverage"] >= 0.90
    assert frozen.nse > baseline.nse
    assert frozen.rmse < baseline.rmse
    assert manifest["frozen_incremental_gate_passed"] is True
