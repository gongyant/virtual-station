from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


INPUT = Path(
    "data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
)
OUTPUT = Path(
    "outputs/virtual_station_mainline/three_regime_round/agricultural_memory_ablation"
)
ALPHAS = [0.0, 0.01, 0.1, 1.0, 10.0, 100.0, 1000.0, 10000.0]


def make_features(reach: pd.DataFrame) -> dict[str, list[str]]:
    reach["ALAR_lag0"] = reach["ALAR"]
    reach["AQK_lag0"] = reach["AQK"]
    for lag in range(1, 16):
        reach[f"ALAR_lag{lag}"] = reach["ALAR"].shift(lag)
    for window in [3, 7, 15, 30]:
        reach[f"ALAR_mean{window}"] = reach["ALAR"].rolling(window).mean()
        reach[f"AQK_mean{window}"] = reach["AQK"].rolling(window).mean()
        # A slowly changing endpoint imbalance is an observable proxy for
        # reach storage/loss memory, not a claimed groundwater measurement.
        reach[f"endpoint_gap_mean{window}"] = (
            reach["AQK"] - reach["ALAR"]
        ).rolling(window).mean()
    return {
        "instantaneous_endpoints": ["ALAR_lag0", "AQK_lag0"],
        "routed_upstream": [
            "AQK_lag0",
            *[f"ALAR_lag{lag}" for lag in range(16)],
        ],
        "routing_plus_memory": [
            "AQK_lag0",
            *[f"ALAR_lag{lag}" for lag in range(16)],
            *[f"ALAR_mean{window}" for window in [3, 7, 15, 30]],
            *[f"AQK_mean{window}" for window in [3, 7, 15, 30]],
            *[f"endpoint_gap_mean{window}" for window in [3, 7, 15, 30]],
        ],
    }


def fit_ridge(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_eval: np.ndarray,
    alpha: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std = np.where(std > 1e-8, std, 1.0)
    x_train_scaled = (x_train - mean) / std
    x_eval_scaled = (x_eval - mean) / std
    design = np.column_stack([np.ones(len(x_train_scaled)), x_train_scaled])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    if alpha == 0.0:
        coefficients = np.linalg.lstsq(design, y_train, rcond=None)[0]
    else:
        coefficients = np.linalg.solve(
            design.T @ design + penalty, design.T @ y_train
        )
    eval_design = np.column_stack([np.ones(len(x_eval_scaled)), x_eval_scaled])
    prediction = np.maximum(eval_design @ coefficients, 0.0)
    return prediction, coefficients, mean, std


def main() -> None:
    raw = pd.read_csv(INPUT, parse_dates=["date"])
    reach = raw.pivot_table(
        index="date", columns="station_code", values="observed_q_m3s", aggfunc="mean"
    )[["ALAR", "XQM", "AQK"]].dropna()
    feature_sets = make_features(reach)
    all_features = sorted({name for names in feature_sets.values() for name in names})
    data = reach.dropna(subset=all_features + ["XQM"]).copy()

    n = len(data)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    split = np.full(n, "test", dtype=object)
    split[:train_end] = "train"
    split[train_end:validation_end] = "validation"
    data["split"] = split
    train = data.iloc[:train_end]
    validation = data.iloc[train_end:validation_end]
    test = data.iloc[validation_end:]

    result_rows = []
    prediction_frame = test[["ALAR", "XQM", "AQK"]].copy()
    coefficient_records = []
    for model_name, features in feature_sets.items():
        best = None
        for alpha in ALPHAS:
            validation_prediction, _, _, _ = fit_ridge(
                train[features].to_numpy(float),
                train["XQM"].to_numpy(float),
                validation[features].to_numpy(float),
                alpha,
            )
            validation_metrics = regression_metrics(
                validation["XQM"].to_numpy(float), validation_prediction
            )
            candidate = {
                "alpha": alpha,
                "validation_rmse": validation_metrics["rmse"],
                "validation_nse": validation_metrics["nse"],
            }
            if best is None or candidate["validation_rmse"] < best["validation_rmse"]:
                best = candidate
        development = data.iloc[:validation_end]
        test_prediction, coefficients, mean, std = fit_ridge(
            development[features].to_numpy(float),
            development["XQM"].to_numpy(float),
            test[features].to_numpy(float),
            float(best["alpha"]),
        )
        metrics = regression_metrics(test["XQM"].to_numpy(float), test_prediction)
        result_rows.append(
            {
                "model": model_name,
                "selected_alpha": best["alpha"],
                "validation_rmse": best["validation_rmse"],
                "validation_nse": best["validation_nse"],
                **metrics,
            }
        )
        prediction_frame[model_name] = test_prediction
        coefficient_records.extend(
            {
                "model": model_name,
                "feature": feature,
                "standardized_coefficient": float(coefficient),
                "training_mean": float(feature_mean),
                "training_std": float(feature_std),
            }
            for feature, coefficient, feature_mean, feature_std in zip(
                features, coefficients[1:], mean, std
            )
        )

    # The blind geometric endpoint baseline remains label-free and is included
    # to separate mechanism diagnosis from strict ungauged performance.
    blind_prediction = np.sqrt(
        np.maximum(test["ALAR"].to_numpy(float), 0.0)
        * np.maximum(test["AQK"].to_numpy(float), 0.0)
    )
    blind_metrics = regression_metrics(test["XQM"].to_numpy(float), blind_prediction)
    result_rows.append(
        {
            "model": "strict_blind_geometric_endpoints",
            "selected_alpha": np.nan,
            "validation_rmse": np.nan,
            "validation_nse": np.nan,
            **blind_metrics,
        }
    )
    prediction_frame["strict_blind_geometric_endpoints"] = blind_prediction

    results = pd.DataFrame(result_rows).sort_values("nse", ascending=False)
    result_lookup = results.set_index("model").to_dict(orient="index")
    instant = result_lookup["instantaneous_endpoints"]
    routed = result_lookup["routed_upstream"]
    memory = result_lookup["routing_plus_memory"]
    summary = {
        "status": "completed_mechanism_diagnostic",
        "protocol": {
            "target_station": "XQM",
            "usable_days_after_30_day_warmup": n,
            "train": [str(train.index.min().date()), str(train.index.max().date())],
            "validation": [
                str(validation.index.min().date()),
                str(validation.index.max().date()),
            ],
            "test": [str(test.index.min().date()), str(test.index.max().date())],
            "test_labels_used_for_training_or_selection": False,
            "xqm_training_labels_used": True,
            "strict_ungauged_claim_allowed": False,
        },
        "test_metrics": result_lookup,
        "observed_regime_shift": {
            name: {
                "xqm_mean": float(frame["XQM"].mean()),
                "xqm_std": float(frame["XQM"].std()),
                "xqm_max": float(frame["XQM"].max()),
                "alar_mean": float(frame["ALAR"].mean()),
                "aqk_mean": float(frame["AQK"].mean()),
            }
            for name, frame in {
                "train": train,
                "validation": validation,
                "test": test,
            }.items()
        },
        "ablation": {
            "routing_vs_instantaneous_nse_gain": routed["nse"] - instant["nse"],
            "memory_vs_routing_nse_gain": memory["nse"] - routed["nse"],
            "memory_vs_instantaneous_rmse_reduction": instant["rmse"] - memory["rmse"],
        },
        "interpretation": (
            "This is a chronological mechanism diagnostic, not a strict ungauged virtual-"
            "station result, because historical XQM labels calibrate the coefficients. A "
            "positive routing/memory gain supports the teacher's delayed-return hypothesis; "
            "a non-positive gain means the available endpoint flows do not identify it "
            "reliably and irrigation/groundwater proxy data are still required."
        ),
        "decision": (
            "The delayed-memory features improve the learned ablation relative to the "
            "instantaneous and routing-only learned models, but the absolute test NSE remains "
            "negative and the strict blind geometric endpoint baseline is better. Therefore "
            "the memory model is retained only as mechanism evidence, not accepted as the "
            "virtual-station predictor. Irrigation withdrawal, irrigated-area, and groundwater "
            "or baseflow proxy inputs are required before this branch is upgraded."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT / "memory_ablation_metrics.csv", index=False)
    prediction_frame.reset_index().to_csv(
        OUTPUT / "memory_ablation_test_predictions.csv", index=False
    )
    pd.DataFrame(coefficient_records).to_csv(
        OUTPUT / "memory_ablation_coefficients.csv", index=False
    )
    (OUTPUT / "memory_ablation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
