import math

import numpy as np
import pandas as pd
import pytest

from vhs.hydraulics import (
    HydraulicScenarioInterpolator,
    ReachHydraulics,
    approximate_section_geometry,
    add_hydraulic_lookup_features,
    build_hydraulic_scenario_library,
    steady_reach_discharge,
)


def _state(water_surface_elevation_m: float, width_m: float = 30.0, depth_m: float = 2.0):
    geometry = approximate_section_geometry(width_m, depth_m)
    return {"water_surface_elevation_m": water_surface_elevation_m, **geometry}


def test_steady_reach_solution_closes_mass_and_energy_balances():
    result = steady_reach_discharge(
        _state(101.0),
        _state(100.0, width_m=35.0, depth_m=2.2),
        ReachHydraulics(10_000.0, 0.035, 0.035),
    )
    assert result["physics_valid"]
    assert result["discharge_m3s"] > 0
    assert result["mass_residual_m3s"] == 0
    assert abs(result["energy_residual_m"]) < 1e-8


def test_nonpositive_head_drop_is_rejected():
    result = steady_reach_discharge(
        _state(100.0), _state(100.1), ReachHydraulics(1000.0, 0.04, 0.04)
    )
    assert not result["physics_valid"]
    assert math.isnan(result["discharge_m3s"])
    assert result["rejection_reason"] == "nonpositive_water_surface_head_drop"


def test_scenario_library_enumerates_cartesian_state_pairs():
    upstream = pd.DataFrame(
        {"stage_m": [1.0, 1.2], "width_m": [20.0, 22.0], "mean_depth_m": [1.0, 1.1]}
    )
    downstream = pd.DataFrame(
        {"stage_m": [0.7, 0.9], "width_m": [24.0, 25.0], "mean_depth_m": [1.2, 1.3]}
    )
    scenarios = build_hydraulic_scenario_library(
        upstream,
        downstream,
        ReachHydraulics(5000.0, 0.04, 0.04),
        upstream_stage_datum_m=100.0,
        downstream_stage_datum_m=99.0,
    )
    assert len(scenarios) == 4
    assert scenarios.scenario_id.is_unique
    assert scenarios.physics_valid.all()
    assert np.allclose(scenarios.mass_residual_m3s, 0.0)


def test_relative_stages_without_common_vertical_datum_are_blocked():
    states = pd.DataFrame({"stage_m": [1.0], "width_m": [20.0], "mean_depth_m": [1.0]})
    with pytest.raises(ValueError, match="confirmed stage datum is required"):
        build_hydraulic_scenario_library(
            states, states, ReachHydraulics(1000.0, 0.04, 0.04)
        )


def test_interpolator_returns_exact_match_and_rejects_extrapolation():
    upstream = pd.DataFrame(
        {"stage_m": [1.0, 1.2], "width_m": [20.0, 22.0], "mean_depth_m": [1.0, 1.1]}
    )
    downstream = pd.DataFrame(
        {"stage_m": [0.7, 0.9], "width_m": [24.0, 25.0], "mean_depth_m": [1.2, 1.3]}
    )
    scenarios = build_hydraulic_scenario_library(
        upstream,
        downstream,
        ReachHydraulics(5000.0, 0.04, 0.04),
        upstream_stage_datum_m=100.0,
        downstream_stage_datum_m=99.0,
    )
    interpolator = HydraulicScenarioInterpolator(scenarios)
    row = scenarios.iloc[0]
    query = {name: float(row[name]) for name in interpolator.feature_names}
    exact = interpolator.query(query)
    assert exact["lookup_status"] == "exact_scenario_match"
    assert exact["discharge_m3s"] == pytest.approx(row.discharge_m3s)

    query["upstream_stage_m"] = 99.0
    outside = interpolator.query(query)
    assert outside["lookup_status"] == "outside_scenario_domain"
    assert math.isnan(outside["discharge_m3s"])


def test_lookup_features_preserve_missing_and_out_of_domain_states():
    upstream = pd.DataFrame(
        {"stage_m": [1.0, 1.2], "width_m": [20.0, 22.0], "mean_depth_m": [1.0, 1.1]}
    )
    downstream = pd.DataFrame(
        {"stage_m": [0.7, 0.9], "width_m": [24.0, 25.0], "mean_depth_m": [1.2, 1.3]}
    )
    scenarios = build_hydraulic_scenario_library(
        upstream,
        downstream,
        ReachHydraulics(5000.0, 0.04, 0.04),
        upstream_stage_datum_m=100.0,
        downstream_stage_datum_m=99.0,
    )
    interpolator = HydraulicScenarioInterpolator(scenarios)
    exact = {name: float(scenarios.iloc[0][name]) for name in interpolator.feature_names}
    rows = pd.DataFrame([exact, {**exact, "upstream_stage_m": np.nan}, {**exact, "upstream_stage_m": 99.0}])
    augmented = add_hydraulic_lookup_features(rows, interpolator)
    assert augmented.loc[0, "hydraulic_reference_available"]
    assert augmented.loc[1, "hydraulic_lookup_status"] == "missing_hydraulic_inputs"
    assert augmented.loc[2, "hydraulic_lookup_status"] == "outside_scenario_domain"
    assert augmented.loc[1:, "hydraulic_reference_q_m3s"].isna().all()
