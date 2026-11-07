from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bd1m_physics_routing_model import (  # noqa: E402
    RoutingParameters,
    initialize_steady_state,
    numba_available,
    ordered_reaches,
    residence_times,
    route_daily,
    route_daily_fast,
    substep_count,
)


NODES_PATH = ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv"
EDGES_PATH = ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_edges.csv"


def graph() -> tuple[pd.DataFrame, pd.DataFrame]:
    return pd.read_csv(NODES_PATH, dtype={"reach_id": str}), pd.read_csv(EDGES_PATH, dtype={"source_reach_id": str, "target_reach_id": str})


def test_graph_order_and_continuity() -> None:
    nodes, edges = graph()
    ordered = ordered_reaches(nodes, edges)
    assert len(ordered) == 68
    assert len(edges) == 67
    assert (edges["topology_check"] == "PASS").all()


def test_tau_positive_with_robust_positive_slope() -> None:
    nodes, edges = graph()
    ordered = ordered_reaches(nodes, edges)
    tau = residence_times(ordered, RoutingParameters(tau0_days=0.2))
    assert len(tau) == 68
    assert np.isfinite(tau).all()
    assert (tau > 0).all()


def test_substep_numerical_stability() -> None:
    tau = np.array([0.003] * 68)
    steps = substep_count(tau)
    assert 1.0 / steps / tau.min() <= 0.5
    with np.testing.assert_raises(ValueError):
        route_daily(np.ones(2), tau, 1)


def test_mass_conservation() -> None:
    nodes, edges = graph()
    ordered = ordered_reaches(nodes, edges)
    tau = residence_times(ordered, RoutingParameters(tau0_days=2.0))
    steps = substep_count(tau)
    initial = initialize_steady_state(3.0, tau)
    forcing = np.array([3.0, 4.0, 2.0])
    _, final_storage, mass_error = route_daily(forcing, tau, steps, initial)
    cumulative_error = initial.sum() + forcing.sum() - final_storage.sum() - np.sum(
        route_daily(forcing, tau, steps, initial)[0]
    )
    assert np.max(np.abs(mass_error)) < 1e-8
    assert abs(cumulative_error) < 1e-7


def test_constant_inflow_steady_state() -> None:
    tau = np.ones(68, dtype=float) * 0.5
    initial = initialize_steady_state(5.0, tau)
    output, final_storage, mass_error = route_daily(np.full(5, 5.0), tau, 4, initial)
    assert np.allclose(output, 5.0, atol=1e-10)
    assert np.allclose(final_storage, initial, atol=1e-10)
    assert np.max(np.abs(mass_error)) < 1e-10


def test_identical_reaches_have_equal_residence_times() -> None:
    nodes, edges = graph()
    ordered = ordered_reaches(nodes, edges)
    identical = ordered.copy()
    identical["length_km"] = 1.0
    identical["median_slope_m_per_m"] = 0.001
    identical["width_m"] = 50.0
    tau = residence_times(identical, RoutingParameters(tau0_days=1.25))
    assert np.allclose(tau, 1.25)


def test_no_future_target_leakage() -> None:
    data = pd.read_csv(ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv", parse_dates=["date"])
    assert data["future_information_leakage"].astype(str).str.lower().eq("false").all()
    assert "Q_target_dsk" not in {
        "Q_input_byblk",
        "P_antecedent_3d",
        "P_antecedent_7d",
        "P_antecedent_30d",
        "T_antecedent_7d",
        "T_antecedent_30d",
    }


def test_state_continuity_across_splits() -> None:
    nodes, edges = graph()
    ordered = ordered_reaches(nodes, edges)
    tau = residence_times(ordered, RoutingParameters(tau0_days=2.0))
    steps = substep_count(tau)
    forcing = np.linspace(2.0, 5.0, 12)
    initial = initialize_steady_state(forcing[0], tau)
    _, continuous_storage, _ = route_daily(forcing, tau, steps, initial)
    state = initial.copy()
    for segment in (forcing[:4], forcing[4:8], forcing[8:]):
        _, state, _ = route_daily(segment, tau, steps, state)
    assert np.allclose(state, continuous_storage, atol=1e-10)


def test_numerical_feasibility_gate() -> None:
    feasibility = pd.read_csv(ROOT / "outputs/vhs_bd1m/experiments/e4a1_numerical_feasibility.csv")
    assert set(feasibility["max_substeps_per_day"]) == {144, 288, 576}
    assert (feasibility["numerically_admissible"] == (feasibility["required_substeps_per_day"] <= feasibility["max_substeps_per_day"])).all()
    assert (feasibility["required_substeps_per_day"] > 0).all()


def test_deterministic_multistart_configuration() -> None:
    protocol = (ROOT / "outputs/vhs_bd1m/experiments/e4a1_optimizer_protocol.yaml").read_text(encoding="utf-8")
    assert "multi_start_count: 20" in protocol
    assert "multi_start_seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]" in protocol
    assert "test_used_for_selection: false" in protocol


@pytest.mark.skipif(not numba_available(), reason="numba is not available")
def test_fast_path_prediction_parity() -> None:
    tau = np.linspace(0.2, 5.0, 68)
    steps = substep_count(tau)
    forcing = np.linspace(2.0, 12.0, 31)
    initial = initialize_steady_state(forcing[0], tau)
    reference, _, _ = route_daily(forcing, tau, steps, initial)
    fast, _, _ = route_daily_fast(forcing, tau, steps, initial)
    np.testing.assert_allclose(fast, reference, rtol=1e-12, atol=1e-12)


@pytest.mark.skipif(not numba_available(), reason="numba is not available")
def test_fast_path_final_storage_parity() -> None:
    tau = np.geomspace(0.05, 8.0, 68)
    steps = substep_count(tau)
    forcing = np.array([3.0, 8.0, 1.0, 11.0, 4.0])
    initial = initialize_steady_state(forcing[0], tau)
    _, reference, _ = route_daily(forcing, tau, steps, initial)
    _, fast, _ = route_daily_fast(forcing, tau, steps, initial)
    np.testing.assert_allclose(fast, reference, rtol=1e-12, atol=1e-12)


@pytest.mark.skipif(not numba_available(), reason="numba is not available")
def test_fast_path_mass_conservation_parity() -> None:
    tau = np.linspace(0.1, 3.0, 68)
    steps = substep_count(tau)
    forcing = np.array([3.0, 4.0, 2.0, 7.0, 1.0])
    initial = initialize_steady_state(forcing[0], tau)
    ref_out, ref_storage, ref_error = route_daily(forcing, tau, steps, initial)
    fast_out, fast_storage, fast_error = route_daily_fast(forcing, tau, steps, initial)
    np.testing.assert_allclose(fast_error, ref_error, rtol=1e-12, atol=1e-10)
    ref_cumulative = initial.sum() + forcing.sum() - ref_storage.sum() - ref_out.sum()
    fast_cumulative = initial.sum() + forcing.sum() - fast_storage.sum() - fast_out.sum()
    assert abs(ref_cumulative) < 1e-7
    assert abs(fast_cumulative) < 1e-7


@pytest.mark.skipif(not numba_available(), reason="numba is not available")
def test_fast_path_numerical_stability_parity() -> None:
    tau = np.full(68, 0.003)
    stable_steps = substep_count(tau)
    route_daily(np.ones(2), tau, stable_steps)
    route_daily_fast(np.ones(2), tau, stable_steps)
    with pytest.raises(ValueError, match="Numerical stability rule violated"):
        route_daily(np.ones(2), tau, stable_steps - 1)
    with pytest.raises(ValueError, match="Numerical stability rule violated"):
        route_daily_fast(np.ones(2), tau, stable_steps - 1)
