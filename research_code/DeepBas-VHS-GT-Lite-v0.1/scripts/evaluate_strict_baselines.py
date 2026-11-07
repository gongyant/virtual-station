from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.data import TensorBundle, split_window_indices
from vhs.metrics import regression_metrics


def _ridge_fit(x: np.ndarray, y: np.ndarray, alpha: float = 1.0) -> np.ndarray:
    """Small ridge solver with an unpenalized intercept."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    valid = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    x, y = x[valid], y[valid]
    design = np.column_stack([np.ones(len(x)), x])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y)


def _ridge_predict(coef: np.ndarray, x: np.ndarray) -> np.ndarray:
    design = np.column_stack([np.ones(len(x)), np.asarray(x, dtype=float)])
    return design @ coef


def _seasonal_features(dates: np.ndarray) -> np.ndarray:
    ts = pd.DatetimeIndex(pd.to_datetime(dates))
    angle = 2.0 * np.pi * (ts.dayofyear.to_numpy() - 1.0) / 365.25
    return np.column_stack([np.sin(angle), np.cos(angle)])


def _read_monthly_sheet(path: Path, sheet_name: str) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, usecols=[0, 1])
    raw.columns = ["month", "provided_monthly_observed"]
    text = (
        raw["month"]
        .astype(str)
        .str.strip()
        .str.replace("年", "-", regex=False)
        .str.replace("月", "", regex=False)
        .str.replace("/", "-", regex=False)
    )
    raw["month"] = pd.to_datetime(text, format="%Y-%m", errors="coerce")
    raw["provided_monthly_observed"] = pd.to_numeric(
        raw["provided_monthly_observed"], errors="coerce"
    )
    return (
        raw.dropna()
        .drop_duplicates("month")
        .sort_values("month")
        .reset_index(drop=True)
    )


def _metrics_table(observed: np.ndarray, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    rows = []
    for name, predicted in predictions.items():
        rows.append({"model": name, **regression_metrics(observed, predicted)})
    return pd.DataFrame(rows).sort_values(["nse", "kge"], ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate leakage-free DSK baselines using no DSK training labels."
    )
    parser.add_argument("--bundle", default="data/processed/real_bundle.npz")
    parser.add_argument("--nodes", default="data/processed/nodes.csv")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--history", type=int, default=30)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--train-end-date")
    parser.add_argument("--validation-end-date")
    parser.add_argument(
        "--diagnostic-lags",
        default="1,3,5,7,14,30",
        help="Predefined upstream-flow lags for sensitivity analysis; not for test-set tuning.",
    )
    parser.add_argument(
        "--gnn-predictions",
        default="outputs/holdout_dsk_strict_v2/test_predictions.csv",
    )
    parser.add_argument(
        "--extra-prediction",
        action="append",
        default=[],
        metavar="NAME=CSV",
        help="Additional model prediction CSV with date/station_id/predicted columns.",
    )
    parser.add_argument(
        "--monthly-excel", default="data/raw/runoff/Q-dsk-byblk.xlsx"
    )
    parser.add_argument("--output-dir", default="outputs/strict_baselines")
    args = parser.parse_args()

    bundle = TensorBundle.load(args.bundle)
    station_ids = list(map(str, bundle.station_ids))
    target_idx = station_ids.index(str(args.target))
    upstream_idx = station_ids.index(str(args.upstream))
    wg_idx = list(map(str, bundle.feature_names)).index("wg_dis")
    obs_idx = list(map(str, bundle.feature_names)).index("obs_q")

    if args.train_end_date and args.validation_end_date:
        bundle_dates = pd.DatetimeIndex(bundle.dates)
        all_idx = np.arange(args.history, len(bundle.dates))
        train_end_date = pd.Timestamp(args.train_end_date)
        validation_end_date = pd.Timestamp(args.validation_end_date)
        train_idx = all_idx[bundle_dates[all_idx] <= train_end_date]
        test_idx = all_idx[bundle_dates[all_idx] > validation_end_date]
    else:
        train_idx, _, test_idx, _, _ = split_window_indices(
            len(bundle.dates), args.history, args.train_fraction, args.val_fraction
        )
    target_valid = bundle.y_mask[test_idx, target_idx]
    eval_idx = test_idx[target_valid]
    dates = bundle.dates[eval_idx]
    observed = bundle.y[eval_idx, target_idx].astype(float)

    lag_idx = eval_idx - 1
    target_wg_lag1 = bundle.x[lag_idx, target_idx, wg_idx].astype(float)
    upstream_wg_lag1 = bundle.x[lag_idx, upstream_idx, wg_idx].astype(float)
    upstream_obs_lag1 = bundle.x[lag_idx, upstream_idx, obs_idx].astype(float)

    nodes = pd.read_csv(args.nodes, dtype={"station_id": str})
    area = nodes.set_index("station_id")["UP_AREA"].astype(float)
    area_ratio = float(area.loc[str(args.target)] / area.loc[str(args.upstream)])

    predictions: dict[str, np.ndarray] = {
        "watergap_target_lag1": target_wg_lag1,
        "upstream_observed_lag1": upstream_obs_lag1,
        "upstream_area_scaled_lag1": upstream_obs_lag1 * area_ratio,
    }
    diagnostic_lags = sorted({int(v) for v in args.diagnostic_lags.split(",") if v.strip()})
    for lag in diagnostic_lags:
        if lag == 1:
            continue
        predictions[f"upstream_area_scaled_lag{lag}"] = (
            bundle.x[eval_idx - lag, upstream_idx, obs_idx].astype(float) * area_ratio
        )

    # Train only on the donor (BYBLK) station, then transfer the learned
    # WaterGAP/season relationship to DSK. DSK labels never enter the fit.
    donor_valid = bundle.y_mask[train_idx, upstream_idx]
    donor_t = train_idx[donor_valid]
    donor_season = _seasonal_features(bundle.dates[donor_t])
    donor_x = np.column_stack(
        [bundle.x[donor_t - 1, upstream_idx, wg_idx], donor_season]
    )
    donor_y = bundle.y[donor_t, upstream_idx]
    donor_coef = _ridge_fit(donor_x, donor_y, alpha=1.0)
    target_x = np.column_stack([target_wg_lag1, _seasonal_features(dates)])
    predictions["donor_transfer_ridge"] = _ridge_predict(donor_coef, target_x)

    # A second donor-transfer diagnostic uses the observed upstream hydrograph
    # as the lagged-flow input. It remains strict because DSK observations are
    # used only after prediction for scoring.
    donor_flow_x = np.column_stack(
        [
            bundle.x[donor_t - 1, upstream_idx, obs_idx],
            bundle.x[donor_t - 1, upstream_idx, wg_idx],
            donor_season,
        ]
    )
    donor_flow_coef = _ridge_fit(donor_flow_x, donor_y, alpha=1.0)
    target_flow_x = np.column_stack(
        [upstream_obs_lag1, target_wg_lag1, _seasonal_features(dates)]
    )
    predictions["donor_transfer_with_upstream_flow"] = _ridge_predict(
        donor_flow_coef, target_flow_x
    )

    gnn_path = Path(args.gnn_predictions)
    if gnn_path.exists():
        gnn = pd.read_csv(gnn_path, dtype={"station_id": str})
        gnn["date"] = pd.to_datetime(gnn["date"])
        gnn = gnn[gnn["station_id"] == str(args.target)].set_index("date")
        predictions["directed_stgnn"] = (
            pd.Series(index=pd.to_datetime(dates), dtype=float)
            .to_frame("placeholder")
            .join(gnn[["predicted"]])
            ["predicted"]
            .to_numpy()
        )

    for item in args.extra_prediction:
        if "=" not in item:
            raise ValueError(f"Expected NAME=CSV for --extra-prediction, got: {item}")
        name, csv_path = item.split("=", 1)
        extra = pd.read_csv(csv_path, dtype={"station_id": str})
        extra["date"] = pd.to_datetime(extra["date"])
        extra = extra[extra["station_id"] == str(args.target)].set_index("date")
        predictions[name] = (
            pd.Series(index=pd.to_datetime(dates), dtype=float)
            .to_frame("placeholder")
            .join(extra[["predicted"]])
            ["predicted"]
            .to_numpy()
        )

    predictions = {name: np.maximum(values, 0.0) for name, values in predictions.items()}
    daily = pd.DataFrame(
        {"date": pd.to_datetime(dates), "station_id": str(args.target), "observed": observed}
    )
    for name, values in predictions.items():
        daily[name] = values

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    daily.to_csv(output_dir / "daily_predictions.csv", index=False)
    daily_metrics = _metrics_table(observed, predictions)
    daily_metrics.to_csv(output_dir / "daily_metrics.csv", index=False)
    (output_dir / "daily_metrics.json").write_text(
        json.dumps(daily_metrics.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    daily["month"] = daily["date"].dt.to_period("M").dt.to_timestamp()
    aggregation = {"observed": "mean", **{name: "mean" for name in predictions}}
    monthly = daily.groupby("month", as_index=False).agg(aggregation)
    counts = daily.groupby("month")["date"].count().rename("valid_days")
    monthly = monthly.join(counts, on="month")
    monthly["coverage"] = monthly["valid_days"] / monthly["month"].dt.days_in_month
    monthly = monthly[monthly["coverage"] >= 0.95].copy()

    monthly_excel = Path(args.monthly_excel)
    if monthly_excel.exists():
        provided = _read_monthly_sheet(monthly_excel, "DSK")
        monthly = monthly.merge(provided, on="month", how="left")
        monthly_observed = monthly["provided_monthly_observed"].to_numpy(float)
    else:
        monthly_observed = monthly["observed"].to_numpy(float)

    monthly_predictions = {name: monthly[name].to_numpy(float) for name in predictions}
    monthly_metrics = _metrics_table(monthly_observed, monthly_predictions)
    monthly.to_csv(output_dir / "monthly_predictions.csv", index=False)
    monthly_metrics.to_csv(output_dir / "monthly_metrics.csv", index=False)
    (output_dir / "monthly_metrics.json").write_text(
        json.dumps(monthly_metrics.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata = {
        "target_station": str(args.target),
        "upstream_station": str(args.upstream),
        "target_upstream_area_ratio": area_ratio,
        "test_start": str(pd.Timestamp(dates[0]).date()),
        "test_end": str(pd.Timestamp(dates[-1]).date()),
        "strict_protocol": "No target-station observations are used for fitting any baseline.",
        "diagnostic_lags": diagnostic_lags,
        "lag_note": "Lag sensitivity is diagnostic only; selecting a lag on this test period would be leakage.",
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Daily metrics")
    print(daily_metrics.to_string(index=False))
    print("\nMonthly metrics (against provided DSK monthly observations when available)")
    print(monthly_metrics.to_string(index=False))
    print(f"\nSaved to: {output_dir}")


if __name__ == "__main__":
    main()
