from __future__ import annotations

import numpy as np


def regression_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    mask = np.isfinite(observed) & np.isfinite(predicted)
    observed, predicted = observed[mask], predicted[mask]
    if observed.size == 0:
        return {k: float("nan") for k in ["n", "rmse", "mae", "pbias", "nse", "kge", "corr"]}
    error = predicted - observed
    rmse = float(np.sqrt(np.mean(error**2)))
    mae = float(np.mean(np.abs(error)))
    obs_sum = float(np.sum(observed))
    pbias = float(100.0 * np.sum(error) / obs_sum) if abs(obs_sum) > 1e-12 else float("nan")
    denom = float(np.sum((observed - observed.mean()) ** 2))
    nse = float(1.0 - np.sum(error**2) / denom) if denom > 1e-12 else float("nan")
    if observed.size > 1 and observed.std() > 0 and predicted.std() > 0:
        corr = float(np.corrcoef(observed, predicted)[0, 1])
        alpha = float(predicted.std() / observed.std())
        beta = float(predicted.mean() / observed.mean()) if abs(observed.mean()) > 1e-12 else float("nan")
        kge = float(1.0 - np.sqrt((corr - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))
    else:
        corr = kge = float("nan")
    return {"n": int(observed.size), "rmse": rmse, "mae": mae, "pbias": pbias, "nse": nse, "kge": kge, "corr": corr}

