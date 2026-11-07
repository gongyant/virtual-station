from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AgricultureHeadPolicy:
    measured_proxies_available: bool
    seasonal_specificity_supported: bool
    correction_beats_blind_baseline: bool

    @property
    def correction_enabled(self) -> bool:
        return bool(
            self.measured_proxies_available
            and self.seasonal_specificity_supported
            and self.correction_beats_blind_baseline
        )


def smooth_warm_gate(index: pd.DatetimeIndex) -> np.ndarray:
    phase = 2.0 * np.pi * (index.dayofyear.to_numpy(float) - 91.0) / 365.25
    return np.maximum(np.sin(phase), 0.0)


def storage_release(loss_proxy: np.ndarray, rho: float) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 <= rho < 1.0:
        raise ValueError("rho must be in [0, 1)")
    loss = np.maximum(np.asarray(loss_proxy, dtype=float), 0.0)
    storage = np.zeros_like(loss)
    release = np.zeros_like(loss)
    state = 0.0
    for position, value in enumerate(loss):
        state = rho * state + value
        storage[position] = state
        release[position] = (1.0 - rho) * state if rho > 0 else value
    return storage, release


def build_agriculture_features(
    index: pd.DatetimeIndex,
    upstream_q: np.ndarray,
    downstream_q: np.ndarray,
    slow_rho: float = 0.99,
) -> pd.DataFrame:
    upstream = np.maximum(np.asarray(upstream_q, dtype=float), 0.0)
    downstream = np.maximum(np.asarray(downstream_q, dtype=float), 0.0)
    if len(index) != len(upstream) or len(upstream) != len(downstream):
        raise ValueError("index, upstream_q and downstream_q must have equal lengths")
    baseline = np.sqrt(upstream * downstream)
    gap = upstream - downstream
    loss = np.maximum(gap, 0.0)
    gate = smooth_warm_gate(index)
    gated_loss = loss * gate
    _, fast_return = storage_release(gated_loss, 0.0)
    slow_storage, slow_return = storage_release(gated_loss, slow_rho)
    scale = upstream + downstream + 1e-6
    risk = np.clip(np.abs(gap) / scale, 0.0, 1.0)
    return pd.DataFrame(
        {
            "agri_endpoint_geometric_q": baseline,
            "agri_endpoint_gap_q": gap,
            "agri_positive_loss_proxy_q": loss,
            "agri_smooth_warm_gate": gate,
            "agri_gated_loss_proxy_q": gated_loss,
            "agri_fast_return_proxy_q": fast_return,
            "agri_slow_storage_proxy_q_days": slow_storage,
            "agri_slow_return_proxy_q": slow_return,
            "agri_endpoint_imbalance_risk": risk,
        },
        index=index,
    )


def apply_agriculture_head(
    baseline_q: np.ndarray,
    candidate_correction_q: np.ndarray,
    policy: AgricultureHeadPolicy,
) -> np.ndarray:
    baseline = np.maximum(np.asarray(baseline_q, dtype=float), 0.0)
    correction = np.asarray(candidate_correction_q, dtype=float)
    if baseline.shape != correction.shape:
        raise ValueError("baseline_q and candidate_correction_q must have equal shapes")
    if not policy.correction_enabled:
        return baseline.copy()
    return np.maximum(baseline + correction, 0.0)


def split_conformal_radius(
    absolute_residuals: np.ndarray, coverage: float = 0.90
) -> float:
    residuals = np.asarray(absolute_residuals, dtype=float)
    residuals = residuals[np.isfinite(residuals)]
    if len(residuals) == 0:
        raise ValueError("at least one finite calibration residual is required")
    if not 0.0 < coverage < 1.0:
        raise ValueError("coverage must be between 0 and 1")
    rank = min(int(np.ceil((len(residuals) + 1) * coverage)), len(residuals))
    return float(np.sort(residuals)[rank - 1])
