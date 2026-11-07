from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from vhs.data import TensorBundle
from vhs.metrics import regression_metrics


BUNDLE_PATH = Path("data/processed/virtual_station/virtual_station_bundle_1978_1983.npz")
TEACHER_MONTHLY_PATH = Path(
    "outputs/holdout_dsk_strict_v2/monthly_validation/monthly_observations_clean.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/reservoir_regulation_head_round")
TARGET_STATION = "00705700"
PHYSICAL_FEATURE = "physics_area_scaled_q_lag3"
FEATURES = ["log_physical", "sin1", "cos1", "sin2", "cos2", "anomaly_7d", "anomaly_30d", "anomaly_90d"]
RIDGE_CANDIDATES = [0.1, 1.0, 10.0, 100.0, 300.0, 1000.0, 3000.0]


def add_causal_features(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("date").copy()
    day = result.date.dt.dayofyear
    result["sin1"] = np.sin(2.0 * np.pi * day / 365.25)
    result["cos1"] = np.cos(2.0 * np.pi * day / 365.25)
    result["sin2"] = np.sin(4.0 * np.pi * day / 365.25)
    result["cos2"] = np.cos(4.0 * np.pi * day / 365.25)
    result["log_physical"] = np.log(np.maximum(result.physical_q_m3s, 1e-3))
    for window in [7, 30, 90]:
        rolling = result.physical_q_m3s.rolling(window, min_periods=1).mean()
        result[f"anomaly_{window}d"] = np.log(
            np.maximum(result.physical_q_m3s, 1e-3) / np.maximum(rolling, 1e-3)
        )
    return result


def predict_bounded_ratio(
    model: Ridge,
    scaler: StandardScaler,
    frame: pd.DataFrame,
    lower_ratio: float,
    upper_ratio: float,
) -> tuple[np.ndarray, np.ndarray]:
    ratio = np.exp(model.predict(scaler.transform(frame[FEATURES])))
    ratio = np.clip(ratio, lower_ratio, upper_ratio)
    prediction = np.maximum(frame.physical_q_m3s.to_numpy(float) * ratio, 0.0)
    return prediction, ratio


def finite_metrics(observed: pd.Series, predicted: pd.Series) -> dict[str, float]:
    keep = np.isfinite(observed) & np.isfinite(predicted)
    return regression_metrics(observed.loc[keep], predicted.loc[keep])


def main() -> None:
    bundle = TensorBundle.load(BUNDLE_PATH)
    station_index = list(bundle.station_ids).index(TARGET_STATION)
    feature_index = list(bundle.feature_names).index(PHYSICAL_FEATURE)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(bundle.dates),
            "observed_q_m3s": bundle.y[:, station_index].astype(float),
            "physical_q_m3s": bundle.x[:, station_index, feature_index].astype(float),
        }
    )
    frame = add_causal_features(frame).replace([np.inf, -np.inf], np.nan)
    frame = frame.dropna(subset=["observed_q_m3s", "physical_q_m3s", *FEATURES])
    train = frame.loc[frame.date.lt("1982-01-01")].copy()
    validation = frame.loc[frame.date.between("1982-01-01", "1982-12-31")].copy()
    test = frame.loc[frame.date.between("1983-01-01", "1983-12-31")].copy()

    scaler = StandardScaler().fit(train[FEATURES])
    train_log_ratio = np.log(train.observed_q_m3s / train.physical_q_m3s)
    lower_ratio, upper_ratio = np.quantile(np.exp(train_log_ratio), [0.01, 0.99])
    selection_rows = []
    fitted_models = {}
    for alpha in RIDGE_CANDIDATES:
        model = Ridge(alpha=alpha).fit(scaler.transform(train[FEATURES]), train_log_ratio)
        prediction, _ = predict_bounded_ratio(
            model, scaler, validation, float(lower_ratio), float(upper_ratio)
        )
        metrics = regression_metrics(validation.observed_q_m3s, prediction)
        selection_rows.append({"alpha": alpha, **metrics})
        fitted_models[alpha] = model
    selection = pd.DataFrame(selection_rows).sort_values(["rmse", "alpha"])
    selected_alpha = float(selection.iloc[0].alpha)
    selected_model = fitted_models[selected_alpha]

    global_ratio = float(train.observed_q_m3s.sum() / train.physical_q_m3s.sum())
    scored_parts = []
    metric_rows = []
    for split, subset in [("train", train), ("validation", validation), ("test", test)]:
        scored = subset[["date", "observed_q_m3s", "physical_q_m3s"]].copy()
        scored["global_ratio_q_m3s"] = np.maximum(subset.physical_q_m3s * global_ratio, 0.0)
        scored["bounded_regulation_q_m3s"], scored["predicted_release_ratio"] = predict_bounded_ratio(
            selected_model, scaler, subset, float(lower_ratio), float(upper_ratio)
        )
        scored["split"] = split
        scored_parts.append(scored)
        for method, column in {
            "physical_baseline": "physical_q_m3s",
            "global_ratio": "global_ratio_q_m3s",
            "bounded_regulation_head": "bounded_regulation_q_m3s",
        }.items():
            metric_rows.append(
                {
                    "split": split,
                    "method": method,
                    **regression_metrics(scored.observed_q_m3s, scored[column]),
                }
            )
    scored = pd.concat(scored_parts, ignore_index=True)
    metrics = pd.DataFrame(metric_rows)

    test_scored = scored.loc[scored.split.eq("test")].copy()
    test_scored["month"] = test_scored.date.dt.to_period("M").dt.to_timestamp()
    monthly = test_scored.groupby("month", as_index=False)[
        ["observed_q_m3s", "physical_q_m3s", "global_ratio_q_m3s", "bounded_regulation_q_m3s"]
    ].mean()
    teacher = pd.read_csv(TEACHER_MONTHLY_PATH, dtype={"station_id": str}, parse_dates=["month"])
    teacher["station_id"] = teacher.station_id.str.zfill(8)
    teacher = teacher.loc[
        teacher.station_id.eq(TARGET_STATION) & teacher.month.dt.year.eq(1983),
        ["month", "monthly_q"],
    ].rename(columns={"monthly_q": "teacher_monthly_q_m3s"})
    monthly = teacher.merge(monthly, on="month", how="inner", validate="one_to_one")
    teacher_metric_rows = []
    for method, column in {
        "physical_baseline": "physical_q_m3s",
        "global_ratio": "global_ratio_q_m3s",
        "bounded_regulation_head": "bounded_regulation_q_m3s",
    }.items():
        teacher_metric_rows.append(
            {
                "method": method,
                **finite_metrics(monthly.teacher_monthly_q_m3s, monthly[column]),
            }
        )
    teacher_metrics = pd.DataFrame(teacher_metric_rows)

    seconds = 86400.0
    annual_volumes = {
        column: float(test_scored[column].sum() * seconds / 1e8)
        for column in ["observed_q_m3s", "physical_q_m3s", "global_ratio_q_m3s", "bounded_regulation_q_m3s"]
    }
    test_head = metrics.loc[
        metrics.split.eq("test") & metrics.method.eq("bounded_regulation_head")
    ].iloc[0]
    test_physical = metrics.loc[
        metrics.split.eq("test") & metrics.method.eq("physical_baseline")
    ].iloc[0]
    accepted_for_historical_gap = bool(
        test_head.nse > test_physical.nse
        and test_head.rmse < test_physical.rmse
        and (test_scored.bounded_regulation_q_m3s >= 0).all()
        and test_scored.predicted_release_ratio.between(lower_ratio, upper_ratio).all()
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    scored.to_csv(OUTPUT / "reservoir_regulation_daily_predictions.csv", index=False)
    metrics.to_csv(OUTPUT / "reservoir_regulation_daily_metrics.csv", index=False)
    selection.to_csv(OUTPUT / "reservoir_regulation_validation_selection.csv", index=False)
    monthly.to_csv(OUTPUT / "reservoir_regulation_1983_monthly.csv", index=False)
    teacher_metrics.to_csv(OUTPUT / "reservoir_regulation_teacher_monthly_metrics.csv", index=False)

    figure, axes = plt.subplots(2, 1, figsize=(12, 7.5), constrained_layout=True)
    axes[0].plot(test_scored.date, test_scored.observed_q_m3s, color="#111827", lw=1.5, label="observed")
    axes[0].plot(test_scored.date, test_scored.physical_q_m3s, color="#2563eb", alpha=0.8, label="physical")
    axes[0].plot(test_scored.date, test_scored.bounded_regulation_q_m3s, color="#ea580c", lw=1.4, label="bounded regulation head")
    axes[0].set(ylabel="Daily discharge (m3/s)", title="1983 sealed test")
    axes[0].legend(frameon=False, ncol=3)
    axes[0].grid(alpha=0.2)
    axes[1].plot(monthly.month, monthly.teacher_monthly_q_m3s, "o-", color="#111827", label="teacher monthly")
    axes[1].plot(monthly.month, monthly.physical_q_m3s, "o-", color="#2563eb", label="physical")
    axes[1].plot(monthly.month, monthly.bounded_regulation_q_m3s, "o-", color="#ea580c", label="bounded regulation head")
    axes[1].set(ylabel="Monthly discharge (m3/s)", title="Teacher-provided monthly comparison")
    axes[1].tick_params(axis="x", rotation=30)
    axes[1].legend(frameon=False, ncol=3)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "reservoir_regulation_diagnostics.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": "accepted_for_historically_gauged_gap_reconstruction"
        if accepted_for_historical_gap
        else "rejected",
        "scope": (
            "Historically gauged reservoir/structure gap reconstruction only; not a fully ungauged "
            "virtual station because 1978-1982 target-station labels are used."
        ),
        "protocol": {
            "train": "1978-01-01/1981-12-31",
            "validation": "1982-01-01/1982-12-31",
            "sealed_test": "1983-01-01/1983-12-31",
            "test_labels_used_for_model_selection": False,
            "target_flow_lags_used_as_inputs": False,
            "features": FEATURES,
            "ridge_candidates": RIDGE_CANDIDATES,
            "selected_alpha": selected_alpha,
        },
        "constraints": {
            "nonnegative_discharge": True,
            "release_ratio_bounds_from_training_1st_99th_percentiles": [
                float(lower_ratio),
                float(upper_ratio),
            ],
            "all_rolling_features_are_causal": True,
        },
        "daily_metrics": metrics.to_dict(orient="records"),
        "teacher_monthly_metrics": teacher_metrics.to_dict(orient="records"),
        "test_annual_volume_1e8m3": annual_volumes,
        "accepted_for_historical_gap_reconstruction": accepted_for_historical_gap,
        "decision": (
            "The regime-specific bounded head is retained for gaps at a historically gauged "
            "hydraulic structure. It must not be transferred to a fully ungauged structure or "
            "described as recovered reservoir releases without level/release/storage observations."
        ),
    }
    (OUTPUT / "reservoir_regulation_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
