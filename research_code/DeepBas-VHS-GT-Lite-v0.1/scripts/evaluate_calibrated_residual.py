from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.data import TensorBundle, split_window_indices
from vhs.metrics import regression_metrics


def _standardized_ridge_fit(
    x: np.ndarray, y: np.ndarray, alpha: float = 10.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    valid = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    x, y = x[valid], y[valid]
    mean = x.mean(axis=0)
    std = x.std(axis=0)
    std = np.where(std > 1e-8, std, 1.0)
    z = (x - mean) / std
    design = np.column_stack([np.ones(len(z)), z])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0.0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return coef, mean, std


def _ridge_predict(
    model: tuple[np.ndarray, np.ndarray, np.ndarray], x: np.ndarray
) -> np.ndarray:
    coef, mean, std = model
    z = (np.asarray(x, dtype=float) - mean) / std
    return np.column_stack([np.ones(len(z)), z]) @ coef


def _season(dates: np.ndarray) -> np.ndarray:
    ts = pd.DatetimeIndex(pd.to_datetime(dates))
    angle = 2.0 * np.pi * (ts.dayofyear.to_numpy() - 1.0) / 365.25
    return np.column_stack([np.sin(angle), np.cos(angle)])


def _read_monthly_dsk(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="DSK", header=None, usecols=[0, 1])
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
    return raw.dropna().drop_duplicates("month").sort_values("month")


def _metrics(observed: np.ndarray, predictions: dict[str, np.ndarray]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"model": name, **regression_metrics(observed, values)} for name, values in predictions.items()]
    ).sort_values(["nse", "kge"], ascending=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DSK historical-calibration diagnostic, separate from strict zero-shot evaluation."
    )
    parser.add_argument("--bundle", default="data/processed/real_bundle.npz")
    parser.add_argument("--nodes", default="data/processed/nodes.csv")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--history", type=int, default=30)
    parser.add_argument("--train-fraction", type=float, default=0.70)
    parser.add_argument("--val-fraction", type=float, default=0.15)
    parser.add_argument("--physical-lag", type=int, default=3)
    parser.add_argument("--ridge-alpha", type=float, default=10.0)
    parser.add_argument("--monthly-excel", default="data/raw/runoff/Q-dsk-byblk.xlsx")
    parser.add_argument("--output-dir", default="outputs/calibrated_residual")
    args = parser.parse_args()

    bundle = TensorBundle.load(args.bundle)
    station_ids = list(map(str, bundle.station_ids))
    target_idx = station_ids.index(str(args.target))
    upstream_idx = station_ids.index(str(args.upstream))
    feature_names = list(map(str, bundle.feature_names))
    obs_idx = feature_names.index("obs_q")
    wg_idx = feature_names.index("wg_dis")

    train_idx, _, test_idx, _, _ = split_window_indices(
        len(bundle.dates), args.history, args.train_fraction, args.val_fraction
    )
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    area_ratio = float(
        float(nodes.loc[str(args.target), "UP_AREA"])
        / float(nodes.loc[str(args.upstream), "UP_AREA"])
    )

    lags = [1, 3, 7, 14]

    def make_features(indices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        upstream_lags = [
            bundle.x[indices - lag, upstream_idx, obs_idx].astype(float) for lag in lags
        ]
        baseline = (
            bundle.x[indices - args.physical_lag, upstream_idx, obs_idx].astype(float)
            * area_ratio
        )
        x = np.column_stack(
            [
                baseline,
                *upstream_lags,
                bundle.x[indices - 1, upstream_idx, wg_idx].astype(float),
                bundle.x[indices - 1, target_idx, wg_idx].astype(float),
                _season(bundle.dates[indices]),
            ]
        )
        return x, baseline

    train_valid = bundle.y_mask[train_idx, target_idx]
    train_t = train_idx[train_valid]
    train_x, train_baseline = make_features(train_t)
    train_y = bundle.y[train_t, target_idx].astype(float)

    residual_model = _standardized_ridge_fit(
        train_x, train_y - train_baseline, alpha=args.ridge_alpha
    )
    direct_model = _standardized_ridge_fit(train_x, train_y, alpha=args.ridge_alpha)

    test_valid = bundle.y_mask[test_idx, target_idx]
    test_t = test_idx[test_valid]
    test_x, test_baseline = make_features(test_t)
    observed = bundle.y[test_t, target_idx].astype(float)
    dates = bundle.dates[test_t]

    train_months = pd.DatetimeIndex(pd.to_datetime(bundle.dates[train_t])).month
    climatology = pd.Series(train_y).groupby(train_months).mean()
    test_months = pd.DatetimeIndex(pd.to_datetime(dates)).month

    predictions = {
        f"physical_area_lag{args.physical_lag}": test_baseline,
        "physical_plus_calibrated_residual": np.maximum(
            test_baseline + _ridge_predict(residual_model, test_x), 0.0
        ),
        "calibrated_direct_ridge": np.maximum(_ridge_predict(direct_model, test_x), 0.0),
        "target_persistence_lag1": bundle.x[test_t - 1, target_idx, obs_idx].astype(float),
        "target_monthly_climatology": np.asarray([climatology.loc[m] for m in test_months]),
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    daily = pd.DataFrame(
        {"date": pd.to_datetime(dates), "station_id": str(args.target), "observed": observed}
    )
    for name, values in predictions.items():
        daily[name] = values
    daily.to_csv(output_dir / "daily_predictions.csv", index=False)
    daily_metrics = _metrics(observed, predictions)
    daily_metrics.to_csv(output_dir / "daily_metrics.csv", index=False)

    daily["month"] = daily["date"].dt.to_period("M").dt.to_timestamp()
    monthly = daily.groupby("month", as_index=False).agg(
        {"observed": "mean", **{name: "mean" for name in predictions}}
    )
    counts = daily.groupby("month")["date"].count().rename("valid_days")
    monthly = monthly.join(counts, on="month")
    monthly["coverage"] = monthly["valid_days"] / monthly["month"].dt.days_in_month
    monthly = monthly[monthly["coverage"] >= 0.95].copy()
    monthly_excel = Path(args.monthly_excel)
    if monthly_excel.exists():
        monthly = monthly.merge(_read_monthly_dsk(monthly_excel), on="month", how="left")
        monthly_observed = monthly["provided_monthly_observed"].to_numpy(float)
    else:
        monthly_observed = monthly["observed"].to_numpy(float)
    monthly_metrics = _metrics(
        monthly_observed,
        {name: monthly[name].to_numpy(float) for name in predictions},
    )
    monthly.to_csv(output_dir / "monthly_predictions.csv", index=False)
    monthly_metrics.to_csv(output_dir / "monthly_metrics.csv", index=False)

    metadata = {
        "protocol": "historical_calibration_diagnostic",
        "warning": "DSK training observations are used. Do not compare as a strict zero-shot model.",
        "target_station": str(args.target),
        "upstream_station": str(args.upstream),
        "physical_lag_days": args.physical_lag,
        "ridge_alpha": args.ridge_alpha,
        "calibration_start": str(pd.Timestamp(bundle.dates[train_t[0]]).date()),
        "calibration_end": str(pd.Timestamp(bundle.dates[train_t[-1]]).date()),
        "test_start": str(pd.Timestamp(dates[0]).date()),
        "test_end": str(pd.Timestamp(dates[-1]).date()),
    }
    (output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "daily_metrics.json").write_text(
        json.dumps(daily_metrics.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "monthly_metrics.json").write_text(
        json.dumps(monthly_metrics.to_dict(orient="records"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("Daily metrics (historical calibration protocol)")
    print(daily_metrics.to_string(index=False))
    print("\nMonthly metrics")
    print(monthly_metrics.to_string(index=False))
    print(f"\nSaved to: {output_dir}")


if __name__ == "__main__":
    main()
