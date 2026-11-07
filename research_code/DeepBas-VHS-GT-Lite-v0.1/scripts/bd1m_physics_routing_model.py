"""Low-capacity sequential linear-reservoir routing skeleton for BD1M."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RoutingParameters:
    tau0_days: float
    a: float = 1.0
    b: float = -0.5
    c: float = 0.0

    def validate(self) -> None:
        if not np.isfinite(self.tau0_days) or self.tau0_days <= 0:
            raise ValueError("tau0_days must be positive and finite")
        if not 0.0 <= self.a <= 2.0:
            raise ValueError("a must be in [0, 2]")
        if not -2.0 <= self.b <= 2.0:
            raise ValueError("b must be in [-2, 2]")
        if not -2.0 <= self.c <= 2.0:
            raise ValueError("c must be in [-2, 2]")


def ordered_reaches(nodes: pd.DataFrame, edges: pd.DataFrame) -> pd.DataFrame:
    ordered = nodes.sort_values("reach_order").reset_index(drop=True)
    if len(ordered) != 68:
        raise ValueError(f"Expected 68 reaches; got {len(ordered)}")
    if ordered["reach_order"].tolist() != list(range(1, 69)):
        raise ValueError("Reach order must be contiguous 1..68")
    if len(edges) != 67:
        raise ValueError(f"Expected 67 edges; got {len(edges)}")
    edge_order = edges.sort_values("source_order").reset_index(drop=True)
    for index, edge in edge_order.iterrows():
        if edge["source_reach_id"] != ordered.loc[index, "reach_id"]:
            raise ValueError("Edge source does not match frozen reach order")
        if edge["target_reach_id"] != ordered.loc[index + 1, "reach_id"]:
            raise ValueError("Edge target does not match frozen reach order")
        if int(edge["target_order"]) != int(edge["source_order"]) + 1:
            raise ValueError("Edge order is not sequential")
    return ordered


def residence_times(
    nodes: pd.DataFrame,
    params: RoutingParameters,
    epsilon_slope_m_per_km: float = 0.01,
) -> np.ndarray:
    params.validate()
    if epsilon_slope_m_per_km <= 0:
        raise ValueError("epsilon_slope_m_per_km must be positive")
    length = nodes["length_km"].to_numpy(dtype=float)
    slope = np.maximum(np.abs(nodes["median_slope_m_per_m"].to_numpy(dtype=float)) * 1000.0, epsilon_slope_m_per_km)
    width = nodes["width_m"].to_numpy(dtype=float)
    if np.any(length <= 0) or np.any(width <= 0) or not np.isfinite(length).all() or not np.isfinite(slope).all() or not np.isfinite(width).all():
        raise ValueError("Physical variables must be finite and positive after slope transform")
    med_l, med_s, med_w = np.median(length), np.median(slope), np.median(width)
    tau = params.tau0_days * (length / med_l) ** params.a * (slope / med_s) ** params.b * (width / med_w) ** params.c
    if not np.isfinite(tau).all() or np.any(tau <= 0):
        raise ValueError("All residence times must be positive and finite")
    return tau


def substep_count(tau_days: np.ndarray, safety_fraction: float = 0.5) -> int:
    if not 0 < safety_fraction <= 0.5:
        raise ValueError("safety_fraction must be in (0, 0.5]")
    minimum_tau = float(np.min(tau_days))
    if not np.isfinite(minimum_tau) or minimum_tau <= 0:
        raise ValueError("tau must be positive and finite")
    return max(1, int(np.ceil(1.0 / (safety_fraction * minimum_tau))))


def route_daily(
    inflow: np.ndarray,
    tau_days: np.ndarray,
    substeps: int,
    initial_storage: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Route daily inflow through sequential reaches using explicit Euler substeps.

    Inflow and output units are discharge per day; storage units are discharge-days.
    The exact discrete update conserves storage + outflow over every substep.
    """
    forcing = np.asarray(inflow, dtype=float)
    tau = np.asarray(tau_days, dtype=float)
    if forcing.ndim != 1 or tau.ndim != 1 or len(tau) != 68:
        raise ValueError("Expected a one-dimensional forcing and 68 reach residence times")
    if not np.isfinite(forcing).all() or np.any(forcing < 0):
        raise ValueError("Inflow must be finite and nonnegative")
    if not np.isfinite(tau).all() or np.any(tau <= 0):
        raise ValueError("Residence times must be positive and finite")
    if substeps < 1:
        raise ValueError("substeps must be at least one")
    dt = 1.0 / substeps
    if np.any(dt / tau > 0.5 + 1e-12):
        raise ValueError("Numerical stability rule violated: dt/tau must be <= 0.5")

    storage = np.zeros(68, dtype=float) if initial_storage is None else np.asarray(initial_storage, dtype=float).copy()
    if storage.shape != (68,) or not np.isfinite(storage).all() or np.any(storage < 0):
        raise ValueError("initial_storage must be a nonnegative finite vector of length 68")

    outputs = np.zeros(len(forcing), dtype=float)
    total_mass_error = np.zeros(len(forcing), dtype=float)
    for day, boundary_flow in enumerate(forcing):
        start_storage = float(storage.sum())
        terminal_volume = 0.0
        for _ in range(substeps):
            reach_inflow = boundary_flow
            for reach in range(68):
                old_storage = storage[reach]
                outflow = old_storage / tau[reach]
                storage[reach] = old_storage + (reach_inflow - outflow) * dt
                reach_inflow = outflow
            terminal_volume += reach_inflow * dt
        outputs[day] = terminal_volume
        total_mass_error[day] = start_storage + boundary_flow - float(storage.sum()) - terminal_volume
    return outputs, storage, total_mass_error


def initialize_steady_state(inflow: float, tau_days: np.ndarray) -> np.ndarray:
    if not np.isfinite(inflow) or inflow < 0:
        raise ValueError("inflow must be finite and nonnegative")
    return np.asarray(tau_days, dtype=float) * inflow


try:
    from numba import njit as _njit
    _NUMBA_AVAILABLE = True
except ImportError:
    _njit = None  # type: ignore[assignment]
    _NUMBA_AVAILABLE = False


def numba_available() -> bool:
    return _NUMBA_AVAILABLE


if _NUMBA_AVAILABLE:
    @_njit(cache=True, fastmath=False)  # type: ignore[misc]
    def _route_kernel(
        forcing: np.ndarray,
        tau: np.ndarray,
        dt: float,
        substeps: int,
        storage: np.ndarray,
        outputs: np.ndarray,
        total_mass_error: np.ndarray,
    ) -> None:
        n_days = forcing.shape[0]
        n_reach = tau.shape[0]
        for day in range(n_days):
            boundary_flow = forcing[day]
            start_storage = 0.0
            for reach in range(n_reach):
                start_storage += storage[reach]
            terminal_volume = 0.0
            for _ in range(substeps):
                reach_inflow = boundary_flow
                for reach in range(n_reach):
                    old_storage = storage[reach]
                    outflow = old_storage / tau[reach]
                    storage[reach] = old_storage + (reach_inflow - outflow) * dt
                    reach_inflow = outflow
                terminal_volume += reach_inflow * dt
            outputs[day] = terminal_volume
            end_storage = 0.0
            for reach in range(n_reach):
                end_storage += storage[reach]
            total_mass_error[day] = start_storage + boundary_flow - end_storage - terminal_volume
else:
    _route_kernel = None  # type: ignore[assignment]


def route_daily_fast(
    inflow: np.ndarray,
    tau_days: np.ndarray,
    substeps: int,
    initial_storage: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """JIT fast path of route_daily: identical validation, equations, loop order.

    Only the triple loop body is compiled; all guards (68 reaches, nonnegativity,
    dt/tau <= 0.5 stability rule) are byte-identical to the reference implementation.
    """
    if not _NUMBA_AVAILABLE or _route_kernel is None:
        raise RuntimeError("numba is not available; cannot use the JIT fast path")
    forcing = np.asarray(inflow, dtype=float)
    tau = np.asarray(tau_days, dtype=float)
    if forcing.ndim != 1 or tau.ndim != 1 or len(tau) != 68:
        raise ValueError("Expected a one-dimensional forcing and 68 reach residence times")
    if not np.isfinite(forcing).all() or np.any(forcing < 0):
        raise ValueError("Inflow must be finite and nonnegative")
    if not np.isfinite(tau).all() or np.any(tau <= 0):
        raise ValueError("Residence times must be positive and finite")
    if substeps < 1:
        raise ValueError("substeps must be at least one")
    dt = 1.0 / substeps
    if np.any(dt / tau > 0.5 + 1e-12):
        raise ValueError("Numerical stability rule violated: dt/tau must be <= 0.5")

    storage = np.zeros(68, dtype=float) if initial_storage is None else np.asarray(initial_storage, dtype=float).copy()
    if storage.shape != (68,) or not np.isfinite(storage).all() or np.any(storage < 0):
        raise ValueError("initial_storage must be a nonnegative finite vector of length 68")

    outputs = np.zeros(len(forcing), dtype=float)
    total_mass_error = np.zeros(len(forcing), dtype=float)
    _route_kernel(forcing, tau, dt, int(substeps), storage, outputs, total_mass_error)
    return outputs, storage, total_mass_error


def verify_fast_parity(
    inflow: np.ndarray,
    tau_days: np.ndarray,
    substeps: int,
    initial_storage: np.ndarray | None = None,
    rtol: float = 1e-12,
    atol: float = 1e-12,
    mass_atol: float = 1e-10,
) -> dict[str, float]:
    """Gate the JIT router on prediction, state, mass, and stability parity."""
    ref_out, ref_store, ref_err = route_daily(inflow, tau_days, substeps, initial_storage)
    fast_out, fast_store, fast_err = route_daily_fast(inflow, tau_days, substeps, initial_storage)
    mass_scale = max(
        1.0,
        float(np.max(np.abs(np.asarray(inflow, dtype=float)))),
        float(np.sum(np.asarray(initial_storage, dtype=float))) if initial_storage is not None else 0.0,
    )
    diffs = {
        "max_abs_prediction_diff": float(np.max(np.abs(ref_out - fast_out))),
        "max_abs_storage_diff": float(np.max(np.abs(ref_store - fast_store))),
        "max_abs_mass_error_diff": float(np.max(np.abs(ref_err - fast_err))),
        "max_abs_reference_mass_error": float(np.max(np.abs(ref_err))),
        "max_abs_fast_mass_error": float(np.max(np.abs(fast_err))),
    }
    if not (
        np.allclose(ref_out, fast_out, rtol=rtol, atol=atol)
        and np.allclose(ref_store, fast_store, rtol=rtol, atol=atol)
        and np.allclose(ref_err, fast_err, rtol=rtol, atol=mass_atol)
        and np.max(np.abs(ref_err)) <= 1e-10 * mass_scale
        and np.max(np.abs(fast_err)) <= 1e-10 * mass_scale
    ):
        raise AssertionError(f"fast-path parity check failed: {diffs}")

    # When one fewer substep is genuinely unstable, both implementations must
    # reject it through the same public numerical-stability guard.
    unstable_steps = int(substeps) - 1
    if unstable_steps >= 1 and np.any((1.0 / unstable_steps) / np.asarray(tau_days, dtype=float) > 0.5 + 1e-12):
        rejected = []
        for router in (route_daily, route_daily_fast):
            try:
                router(inflow, tau_days, unstable_steps, initial_storage)
            except ValueError as exc:
                rejected.append("Numerical stability rule violated" in str(exc))
            else:
                rejected.append(False)
        if rejected != [True, True]:
            raise AssertionError(f"fast-path stability parity check failed: {rejected}")
        diffs["numerical_stability_rejection_consistent"] = 1.0
    return diffs
