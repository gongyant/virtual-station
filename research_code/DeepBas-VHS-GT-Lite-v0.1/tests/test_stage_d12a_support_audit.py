from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pandas as pd

from scripts.run_stage_d12a_support_audit import (
    D11,
    EXPECTED_D11_HASHES,
    OPEN_MONTHS,
    OUT,
    assign_regime,
    base_measurements,
    build_fold_support_domains,
    eligible_auxiliary,
    sha256,
)


def test_original_d11_artifacts_and_failed_gate_are_unchanged() -> None:
    for name, expected in EXPECTED_D11_HASHES.items():
        assert sha256(D11 / name) == expected
    result = json.loads((D11 / "result.json").read_text(encoding="utf-8"))
    assert result["gate_passed"] is False
    assert result["common_support_rows"] == 12
    assert result["measurement_rows"] == 24


def test_no_extrapolation_and_original_support_remain_fixed() -> None:
    gaps = pd.read_csv(OUT / "d12_support_gap_audit.csv")
    predictions = pd.read_csv(D11 / "outer_month_predictions.csv")
    assert len(gaps) == 12
    assert not gaps.extrapolation_allowed.any()
    assert int(predictions.common_support.sum()) == 12


def test_leave_calendar_month_out_excludes_all_years() -> None:
    base = base_measurements()
    synthetic_may = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2010-05-01"),
                "year": 2010,
                "month": 5,
                "regime": "open_water",
                "stage_m": 3.00,
                "area_m2": 1.0,
                "width_m": 1.0,
                "mean_depth_m": 1.0,
            }
        ]
    )
    domains = build_fold_support_domains(base, synthetic_may).set_index("held_month")
    assert domains.loc[5, "training_regime_stage_min"] == 3.93


def test_unverified_auxiliary_never_enters_training_pool() -> None:
    inventory = pd.DataFrame(
        [
            {
                "auxiliary_geometry_candidate": True,
                "verified_mergeable": False,
                "stage_m": 3.5,
                "area_m2": 20.0,
                "width_m": 40.0,
                "mean_depth_m": 0.5,
                "date": "2010-09-01",
            }
        ]
    )
    assert eligible_auxiliary(inventory).empty


def test_inventory_contract_and_no_unverified_merge() -> None:
    inventory = pd.read_csv(OUT / "measurement_inventory.csv")
    required = {
        "source_path",
        "station_id",
        "station_name",
        "date",
        "year",
        "month",
        "stage_m",
        "area_m2",
        "width_m",
        "mean_depth_m",
        "gauge_datum_information",
        "cross_section_information",
        "quality_status",
        "mergeable_with_2011",
        "reason",
    }
    assert required.issubset(inventory.columns)
    assert len(inventory) == 572
    assert not (
        inventory.quality_status.str.startswith("unverified", na=False)
        & inventory.mergeable_with_2011
    ).any()
    assert int(inventory.verified_mergeable.sum()) == 24
    assert eligible_auxiliary(inventory).empty


def test_season_definition_is_frozen() -> None:
    assert OPEN_MONTHS == frozenset({4, 5, 6, 7, 8, 9, 10})
    assert [assign_regime(month) for month in range(1, 13)] == [
        "cold_season",
        "cold_season",
        "cold_season",
        "open_water",
        "open_water",
        "open_water",
        "open_water",
        "open_water",
        "open_water",
        "open_water",
        "cold_season",
        "cold_season",
    ]


def test_d12a_does_not_read_forbidden_labels_or_parameters() -> None:
    source = (Path(__file__).parents[1] / "scripts/run_stage_d12a_support_audit.py").read_text(encoding="utf-8")
    assert "daily_discharge_2011_canonical" not in source
    assert "q_observed_m3s" not in source
    assert "D9B_PARAMETERS" not in source
    assert "residual_blend" not in source


def test_all_requested_svg_audits_are_well_formed() -> None:
    names = [
        "h_vs_area_by_regime.svg",
        "h_vs_width_by_regime.svg",
        "h_vs_mean_depth_by_regime.svg",
        "fold_training_stage_domains.svg",
        "common_support_status_by_month.svg",
    ]
    for name in names:
        root = ET.parse(OUT / name).getroot()
        assert root.tag.endswith("svg")
        assert int(root.attrib["width"]) >= 900
        assert int(root.attrib["height"]) >= 500


def test_d12a_stops_without_starting_d12b() -> None:
    result = json.loads((OUT / "result.json").read_text(encoding="utf-8"))
    assert result["verified_auxiliary_geometry_rows"] == 0
    assert result["coverage_after_all_current_verified_auxiliary"] == "12/24"
    assert result["extrapolation_allowed"] is False
    assert result["d12b_started"] is False
