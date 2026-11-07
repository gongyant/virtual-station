from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from vhs.metrics import regression_metrics


MODEL_OUTPUTS = {
    "nograph_gru": "nograph_gru/test_predictions.csv",
    "directed_stgnn": "directed_stgnn/test_predictions.csv",
    "directed_stgnn_climate": "directed_stgnn_climate/test_predictions.csv",
    "routed_stgnn": "routed_stgnn/test_predictions.csv",
    "physics_stgnn": "physics_stgnn/test_predictions.csv",
}


def metric_table(frame: pd.DataFrame, model_columns: list[str]) -> pd.DataFrame:
    rows = []
    for name in model_columns:
        valid = frame[["observed", name]].notna().all(axis=1)
        rows.append(
            {"model": name, **regression_metrics(frame.loc[valid, "observed"], frame.loc[valid, name])}
        )
    return pd.DataFrame(rows).sort_values(["nse", "kge"], ascending=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, default=Path("outputs/virtual_station_mainline/preliminary")
    )
    parser.add_argument("--train-start", default="1978-01-31")
    parser.add_argument("--train-end", default="1979-12-31")
    parser.add_argument("--validation-start", default="1980-01-01")
    parser.add_argument("--validation-end", default="1980-12-31")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    baseline_path = args.root / "strict_physical_baselines" / "daily_predictions.csv"
    comparison = pd.read_csv(baseline_path, parse_dates=["date"])
    keep_baselines = [
        "upstream_area_scaled_lag1",
        "upstream_area_scaled_lag3",
    ]
    comparison = comparison[["date", "station_id", "observed", *keep_baselines]]
    for name, relative_path in MODEL_OUTPUTS.items():
        prediction = pd.read_csv(args.root / relative_path, parse_dates=["date"])
        prediction = prediction[["date", "predicted"]].rename(columns={"predicted": name})
        comparison = comparison.merge(prediction, on="date", how="left", validate="one_to_one")
    model_columns = keep_baselines + list(MODEL_OUTPUTS)
    donor_physical_path = args.root / "donor_physical_model" / "test_predictions.csv"
    if donor_physical_path.exists():
        donor_physical = pd.read_csv(donor_physical_path, parse_dates=["date"])[
            ["date", "donor_physical_q"]
        ]
        comparison = comparison.merge(
            donor_physical, on="date", how="left", validate="one_to_one"
        )
        model_columns.append("donor_physical_q")
        if "physics_stgnn" in comparison:
            comparison["hybrid_75donor_25physics"] = (
                0.75 * comparison["donor_physical_q"]
                + 0.25 * comparison["physics_stgnn"]
            )
            model_columns.append("hybrid_75donor_25physics")
    daily_metrics = metric_table(comparison, model_columns)

    monthly = (
        comparison.set_index("date")[["observed", *model_columns]]
        .resample("MS")
        .mean()
        .reset_index()
    )
    monthly_metrics = metric_table(monthly, model_columns)
    high_threshold = float(comparison["observed"].quantile(0.90))
    low_threshold = float(comparison["observed"].quantile(0.10))
    regime_masks = {
        "all_days": pd.Series(True, index=comparison.index),
        "high_flow_top10pct": comparison["observed"] >= high_threshold,
        "low_flow_bottom10pct": comparison["observed"] <= low_threshold,
        "core_snowmelt_apr_jun": comparison["date"].dt.month.isin([4, 5, 6]),
        "warm_apr_oct": comparison["date"].dt.month.isin([4, 5, 6, 7, 8, 9, 10]),
    }
    regime_rows = []
    for regime, regime_mask in regime_masks.items():
        for name in model_columns:
            valid = regime_mask & comparison[["observed", name]].notna().all(axis=1)
            regime_rows.append(
                {
                    "regime": regime,
                    "model": name,
                    "observed_threshold_low": low_threshold,
                    "observed_threshold_high": high_threshold,
                    **regression_metrics(
                        comparison.loc[valid, "observed"], comparison.loc[valid, name]
                    ),
                }
            )
    regime_metrics = pd.DataFrame(regime_rows)
    observed_peak_index = comparison["observed"].idxmax()
    observed_peak_date = comparison.loc[observed_peak_index, "date"]
    diagnostic_rows = []
    for name in model_columns:
        predicted_peak_index = comparison[name].idxmax()
        predicted_peak_date = comparison.loc[predicted_peak_index, "date"]
        diagnostic_rows.append(
            {
                "model": name,
                "negative_prediction_count": int((comparison[name] < 0).sum()),
                "observed_peak_date": str(observed_peak_date.date()),
                "predicted_peak_date": str(predicted_peak_date.date()),
                "peak_timing_error_days": int(
                    (predicted_peak_date - observed_peak_date).days
                ),
                "observed_peak_q": float(comparison.loc[observed_peak_index, "observed"]),
                "predicted_peak_q": float(comparison.loc[predicted_peak_index, name]),
                "peak_magnitude_bias_percent": float(
                    100.0
                    * (
                        comparison.loc[predicted_peak_index, name]
                        - comparison.loc[observed_peak_index, "observed"]
                    )
                    / comparison.loc[observed_peak_index, "observed"]
                ),
            }
        )
    diagnostics = pd.DataFrame(diagnostic_rows)
    comparison.to_csv(args.root / "mainline_daily_predictions.csv", index=False)
    daily_metrics.to_csv(args.root / "mainline_daily_metrics.csv", index=False)
    monthly.to_csv(args.root / "mainline_monthly_predictions.csv", index=False)
    monthly_metrics.to_csv(args.root / "mainline_monthly_metrics.csv", index=False)
    regime_metrics.to_csv(args.root / "mainline_regime_metrics.csv", index=False)
    diagnostics.to_csv(args.root / "mainline_peak_diagnostics.csv", index=False)
    summary = {
        "protocol": {
            "target_station": "00705700",
            "target_flow_in_inputs": False,
            "target_labels_in_training": False,
            "train": [args.train_start, args.train_end],
            "validation": [args.validation_start, args.validation_end],
            "test": [
                str(comparison["date"].min().date()),
                str(comparison["date"].max().date()),
            ],
            "model_selection_uses_target_station": False,
        },
        "physical_assumptions": {
            "upstream_station": "00705600",
            "river_distance_km": 212.61,
            "predefined_routing_lag_days": 3,
            "upstream_area_km2": 6773.1,
            "target_area_km2": 18641.1,
            "incremental_area_km2": 11868.0,
            "target_to_upstream_area_ratio": 2.752225716437082,
            "reservoir_relaxation": "soft physics loss weight 0.05",
            "preregistered_hybrid_diagnostic": (
                "75% donor physical model + 25% physics STGNN; fixed before the formal 1983 test"
            ),
        },
        "daily_best_model": daily_metrics.iloc[0].to_dict(),
        "monthly_best_model": monthly_metrics.iloc[0].to_dict(),
        "peak_diagnostics": diagnostics.to_dict(orient="records"),
        "warning": (
            "Preliminary experiment; final conclusions require the 1978-1983 protocol."
            if "preliminary" in str(args.root)
            else "Formal 1978-1983 strict virtual-station protocol."
        ),
    }
    (args.root / "mainline_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Daily metrics")
    print(daily_metrics.to_string(index=False))
    print("\nMonthly metrics")
    print(monthly_metrics.to_string(index=False))


if __name__ == "__main__":
    main()
