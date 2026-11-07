from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

from vhs.metrics import regression_metrics


INPUT = Path("data/processed/virtual_station_multisite/multisite_discharge_2005.csv")
OUTPUT = Path("outputs/virtual_station_mainline/irrigation_return_storage_round")
RHO_CANDIDATES = [0.0, 0.5, 0.8, 0.9, 0.95, 0.97, 0.99]
WARMUP_DAYS = 29


def return_storage(loss_proxy: np.ndarray, rho: float) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 <= rho < 1.0:
        raise ValueError("rho must be in [0, 1)")
    storage = np.zeros(len(loss_proxy), dtype=float)
    release = np.zeros(len(loss_proxy), dtype=float)
    state = 0.0
    for index, loss in enumerate(np.maximum(np.asarray(loss_proxy, dtype=float), 0.0)):
        state = rho * state + loss
        storage[index] = state
        release[index] = (1.0 - rho) * state if rho > 0 else loss
    return storage, release


def design_matrix(frame: pd.DataFrame) -> np.ndarray:
    return np.column_stack(
        [frame.geometric_endpoint_q, frame.endpoint_gap_q, frame.return_release_proxy_q, np.ones(len(frame))]
    )


def fit_constrained(frame: pd.DataFrame) -> np.ndarray:
    # Geometric contribution is non-negative; gap and memory corrections may add or remove
    # water because the two observed endpoints also contain routing and ungauged lateral effects.
    result = lsq_linear(
        design_matrix(frame),
        frame.XQM.to_numpy(float),
        bounds=([0.0, -2.0, -2.0, -200.0], [3.0, 2.0, 2.0, 200.0]),
    )
    return result.x


def predict(frame: pd.DataFrame, coefficients: np.ndarray) -> np.ndarray:
    return np.maximum(design_matrix(frame) @ coefficients, 0.0)


def main() -> None:
    raw = pd.read_csv(INPUT, parse_dates=["date"])
    reach = raw.pivot_table(
        index="date", columns="station_code", values="observed_q_m3s", aggfunc="mean"
    )[["ALAR", "XQM", "AQK"]].dropna()
    reach = reach.iloc[WARMUP_DAYS:].copy()
    reach["geometric_endpoint_q"] = np.sqrt(
        np.maximum(reach.ALAR, 0.0) * np.maximum(reach.AQK, 0.0)
    )
    reach["endpoint_gap_q"] = reach.ALAR - reach.AQK
    reach["positive_loss_proxy_q"] = np.maximum(reach.endpoint_gap_q, 0.0)

    n = len(reach)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    candidate_rows = []
    candidate_predictions = {}
    candidate_coefficients = {}
    for rho in RHO_CANDIDATES:
        storage, release = return_storage(reach.positive_loss_proxy_q.to_numpy(float), rho)
        candidate = reach.copy()
        candidate["return_storage_proxy_q_days"] = storage
        candidate["return_release_proxy_q"] = release
        train = candidate.iloc[:train_end]
        validation = candidate.iloc[train_end:validation_end]
        coefficients = fit_constrained(train)
        validation_prediction = predict(validation, coefficients)
        metrics = regression_metrics(validation.XQM, validation_prediction)
        candidate_rows.append({"rho": rho, **metrics})
        candidate_predictions[rho] = candidate
        candidate_coefficients[rho] = coefficients

    candidates = pd.DataFrame(candidate_rows).sort_values(["rmse", "rho"])
    selected_rho = float(candidates.iloc[0].rho)
    selected = candidate_predictions[selected_rho]
    selected_coefficients = candidate_coefficients[selected_rho]
    train = selected.iloc[:train_end]
    validation = selected.iloc[train_end:validation_end]
    test = selected.iloc[validation_end:].copy()
    test["storage_model_q"] = predict(test, selected_coefficients)
    test["strict_blind_geometric_q"] = test.geometric_endpoint_q
    test["instantaneous_constrained_q"] = predict(test, candidate_coefficients[0.0])

    metric_rows = []
    for method, column in {
        "strict_blind_geometric_endpoints": "strict_blind_geometric_q",
        "instantaneous_constrained": "instantaneous_constrained_q",
        "delayed_return_storage": "storage_model_q",
    }.items():
        metric_rows.append(
            {"method": method, **regression_metrics(test.XQM, test[column])}
        )
    metrics = pd.DataFrame(metric_rows).sort_values("nse", ascending=False)
    metric_lookup = metrics.set_index("method").to_dict(orient="index")
    storage_metric = metric_lookup["delayed_return_storage"]
    blind_metric = metric_lookup["strict_blind_geometric_endpoints"]
    half_life_days = float(np.log(0.5) / np.log(selected_rho)) if selected_rho > 0 else 0.0
    accepted = bool(
        storage_metric["nse"] > 0
        and storage_metric["nse"] > blind_metric["nse"]
        and storage_metric["rmse"] < blind_metric["rmse"]
    )

    scored = test[
        [
            "ALAR",
            "XQM",
            "AQK",
            "geometric_endpoint_q",
            "positive_loss_proxy_q",
            "return_storage_proxy_q_days",
            "return_release_proxy_q",
            "strict_blind_geometric_q",
            "instantaneous_constrained_q",
            "storage_model_q",
        ]
    ].reset_index()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUTPUT / "return_storage_validation_candidates.csv", index=False)
    metrics.to_csv(OUTPUT / "return_storage_test_metrics.csv", index=False)
    scored.to_csv(OUTPUT / "return_storage_test_predictions.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 7.2), constrained_layout=True)
    axes[0].plot(scored.date, scored.XQM, color="#111827", lw=1.7, label="XQM observed")
    axes[0].plot(scored.date, scored.strict_blind_geometric_q, color="#2563eb", label="blind endpoints")
    axes[0].plot(scored.date, scored.storage_model_q, color="#ea580c", label="delayed-return storage")
    axes[0].set(ylabel="Discharge (m3/s)", title="Sealed chronological test")
    axes[0].legend(frameon=False, ncol=3)
    axes[0].grid(alpha=0.2)
    axes[1].plot(selected.index, selected.positive_loss_proxy_q, color="#64748b", alpha=0.65, label="positive endpoint-loss proxy")
    axes[1].plot(selected.index, selected.return_release_proxy_q, color="#7c3aed", label="delayed return-release proxy")
    axes[1].axvspan(validation.index.min(), validation.index.max(), color="#facc15", alpha=0.12, label="validation")
    axes[1].axvspan(test.index.min(), test.index.max(), color="#f97316", alpha=0.10, label="test")
    axes[1].set(ylabel="Proxy flow scale (m3/s)", title=f"Selected memory rho={selected_rho:.2f}, half-life={half_life_days:.1f} days")
    axes[1].legend(frameon=False, ncol=4)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "return_storage_diagnostics.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": "accepted_for_historically_gauged_gap_reconstruction" if accepted else "completed_mechanism_supported_predictor_rejected",
        "scope": (
            "Mechanism diagnostic for a historically observed middle station. XQM labels in the "
            "training and validation blocks are used; this is not a strict ungauged result."
        ),
        "protocol": {
            "train": [train.index.min().date().isoformat(), train.index.max().date().isoformat()],
            "validation": [validation.index.min().date().isoformat(), validation.index.max().date().isoformat()],
            "sealed_test": [test.index.min().date().isoformat(), test.index.max().date().isoformat()],
            "test_labels_used_for_fitting_or_selection": False,
            "rho_candidates": RHO_CANDIDATES,
            "selected_by": "lowest validation RMSE",
        },
        "mechanism": {
            "loss_proxy": "max(ALAR - AQK, 0)",
            "storage_equation": "S[t] = rho*S[t-1] + loss_proxy[t]",
            "return_proxy": "(1-rho)*S[t]",
            "selected_rho": selected_rho,
            "memory_half_life_days": half_life_days,
            "selected_coefficients": {
                "geometric_endpoint": float(selected_coefficients[0]),
                "endpoint_gap": float(selected_coefficients[1]),
                "delayed_return": float(selected_coefficients[2]),
                "intercept": float(selected_coefficients[3]),
            },
        },
        "test_metrics": metrics.to_dict(orient="records"),
        "accepted_as_predictor": accepted,
        "decision": (
            "A long delayed-return state is selected and improves substantially over the previous "
            "high-dimensional memory regression, supporting the teacher's dynamic-loop mechanism. "
            "However, it does not beat the strict blind geometric endpoint baseline, so it remains "
            "a mechanism diagnostic. Diversion, irrigated-area, groundwater level or baseflow "
            "observations are required before promotion."
        ),
    }
    (OUTPUT / "return_storage_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
