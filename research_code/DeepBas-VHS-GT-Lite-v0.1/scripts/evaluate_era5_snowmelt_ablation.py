from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]


def metrics(observed: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    residual = predicted - observed
    denominator = float(np.sum((observed - observed.mean()) ** 2))
    nse = 1.0 - float(np.sum(residual**2)) / denominator if denominator else np.nan
    observed_std = float(np.std(observed, ddof=1))
    predicted_std = float(np.std(predicted, ddof=1))
    correlation = (
        float(np.corrcoef(observed, predicted)[0, 1])
        if observed_std > 0 and predicted_std > 0
        else np.nan
    )
    variability = predicted_std / observed_std if observed_std > 0 else np.nan
    bias_ratio = float(np.mean(predicted) / np.mean(observed))
    kge = (
        1.0
        - np.sqrt(
            (correlation - 1.0) ** 2
            + (variability - 1.0) ** 2
            + (bias_ratio - 1.0) ** 2
        )
        if np.isfinite(correlation) and np.isfinite(variability)
        else np.nan
    )
    return {
        "nse": nse,
        "kge": float(kge),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "mae": float(np.mean(np.abs(residual))),
        "r2": float(correlation**2),
        "bias": float(np.mean(residual)),
    }


def load_table(era5_path: Path, flow_path: Path, station_id: str) -> pd.DataFrame:
    with xr.open_dataset(era5_path) as source:
        station = source.sel(station=station_id).load()
    climate = station.to_dataframe()[list(station.data_vars)].reset_index()
    climate["date"] = pd.to_datetime(climate["time"])
    climate = climate.drop(columns=["time"])

    flow = pd.read_csv(flow_path, dtype={"station_id": str})
    flow["station_id"] = flow["station_id"].str.zfill(8)
    flow["date"] = pd.to_datetime(flow["date"])
    flow = flow.loc[flow["station_id"].eq(station_id), ["date", "obs_q"]]
    table = climate.merge(flow, on="date", how="inner").sort_values("date")
    if table["obs_q"].isna().any():
        raise ValueError("Target flow contains missing values")
    return table.set_index("date")


def add_features(table: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=table.index)
    day_angle = 2.0 * np.pi * (table.index.dayofyear - 1) / 365.25
    features["doy_sin"] = np.sin(day_angle)
    features["doy_cos"] = np.cos(day_angle)

    rolling_sums = [
        "precipitation_mm",
        "snowmelt_mm",
        "evaporation_loss_mm",
    ]
    rolling_means = ["temperature_c", "swe_mm", "soil_water_layer1"]
    for name in rolling_sums:
        for window in [1, 3, 7, 14, 30]:
            features[f"{name}_sum{window}"] = table[name].rolling(window).sum()
    for name in rolling_means:
        for window in [1, 3, 7, 14, 30]:
            features[f"{name}_mean{window}"] = table[name].rolling(window).mean()
    for lag in [1, 2, 7]:
        features[f"q_lag{lag}"] = table["obs_q"].shift(lag)
    features["obs_q"] = table["obs_q"]
    return features


def fit_ridge(
    data: pd.DataFrame,
    columns: list[str],
    train_mask: pd.Series,
    validation_mask: pd.Series,
    test_mask: pd.Series,
) -> tuple[np.ndarray, float, dict[str, float]]:
    valid = data[columns + ["obs_q"]].notna().all(axis=1)
    train = train_mask & valid
    validation = validation_mask & valid
    test = test_mask & valid
    if min(int(train.sum()), int(validation.sum()), int(test.sum())) < 2:
        raise ValueError("Each split needs at least two valid rows")

    best_alpha = None
    best_rmse = np.inf
    for alpha in ALPHAS:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(data.loc[train, columns], data.loc[train, "obs_q"])
        prediction = model.predict(data.loc[validation, columns])
        score = metrics(data.loc[validation, "obs_q"].values, prediction)["rmse"]
        if score < best_rmse:
            best_alpha, best_rmse = alpha, score

    development = (train_mask | validation_mask) & valid
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(data.loc[development, columns], data.loc[development, "obs_q"])
    prediction = model.predict(data.loc[test, columns])
    return test.to_numpy(), float(best_alpha), metrics(
        data.loc[test, "obs_q"].values, prediction
    ) | {"prediction": prediction}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate strict statistical baselines and snowmelt ablations."
    )
    parser.add_argument(
        "--era5",
        type=Path,
        default=Path(
            "data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc"
        ),
    )
    parser.add_argument(
        "--flows", type=Path, default=Path("data/processed/timeseries.csv")
    )
    parser.add_argument("--station-id", default="00705700")
    parser.add_argument("--train-end", default="1981-12-31")
    parser.add_argument("--validation-end", default="1982-12-31")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("outputs/era5_snowmelt_ablation")
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    table = load_table(args.era5, args.flows, args.station_id)
    data = add_features(table)
    train_end = pd.Timestamp(args.train_end)
    validation_end = pd.Timestamp(args.validation_end)
    train_mask = pd.Series(data.index <= train_end, index=data.index)
    validation_mask = pd.Series(
        (data.index > train_end) & (data.index <= validation_end), index=data.index
    )
    test_mask = pd.Series(data.index > validation_end, index=data.index)
    if not test_mask.any():
        raise ValueError("No test rows occur after --validation-end")

    prediction_table = pd.DataFrame(
        {"date": data.index[test_mask], "observed_q": data.loc[test_mask, "obs_q"]}
    ).set_index("date")
    records: list[dict[str, float | str]] = []

    persistence = data.loc[test_mask, "q_lag1"]
    persistence_valid = persistence.notna()
    persistence_metrics = metrics(
        data.loc[test_mask, "obs_q"].loc[persistence_valid].values,
        persistence.loc[persistence_valid].values,
    )
    prediction_table["persistence"] = persistence
    records.append({"model": "persistence", "alpha": np.nan} | persistence_metrics)

    train_climatology = table.loc[table.index <= train_end].copy()
    climatology = train_climatology.groupby(train_climatology.index.dayofyear)[
        "obs_q"
    ].mean()
    climatology_prediction = pd.Series(
        [climatology.get(day, train_climatology.obs_q.mean()) for day in prediction_table.index.dayofyear],
        index=prediction_table.index,
    )
    prediction_table["seasonal_climatology"] = climatology_prediction
    records.append(
        {"model": "seasonal_climatology", "alpha": np.nan}
        | metrics(prediction_table.observed_q.values, climatology_prediction.values)
    )

    all_columns = [column for column in data.columns if column != "obs_q"]
    climate_columns = [column for column in all_columns if not column.startswith("q_lag")]
    experiment_columns = {
        "climate_full": climate_columns,
        "climate_no_snowmelt": [
            column for column in climate_columns if "snowmelt" not in column
        ],
        "autoregressive_full": all_columns,
        "autoregressive_no_snowmelt": [
            column for column in all_columns if "snowmelt" not in column
        ],
    }
    for model_name, columns in experiment_columns.items():
        test_valid, alpha, result = fit_ridge(
            data, columns, train_mask, validation_mask, test_mask
        )
        prediction = result.pop("prediction")
        test_dates = data.index[test_valid]
        prediction_table.loc[test_dates, model_name] = prediction
        records.append({"model": model_name, "alpha": alpha} | result)

    metric_table = pd.DataFrame(records)
    season_months = {
        "annual": set(range(1, 13)),
        "core_snowmelt_apr_jun": {4, 5, 6},
        "warm_apr_oct": {4, 5, 6, 7, 8, 9, 10},
        "cold_nov_mar": {11, 12, 1, 2, 3},
    }
    seasonal_records = []
    for season, months in season_months.items():
        season_mask = prediction_table.index.month.isin(months)
        for model_name in prediction_table.columns.drop("observed_q"):
            valid = season_mask & prediction_table[model_name].notna()
            seasonal_records.append(
                {"season": season, "model": model_name, "days": int(valid.sum())}
                | metrics(
                    prediction_table.loc[valid, "observed_q"].values,
                    prediction_table.loc[valid, model_name].values,
                )
            )
    seasonal_metric_table = pd.DataFrame(seasonal_records)
    indexed = metric_table.set_index("model")
    ablation = {
        "climate": {
            metric: float(indexed.loc["climate_full", metric] - indexed.loc["climate_no_snowmelt", metric])
            for metric in ["nse", "kge", "r2"]
        },
        "autoregressive": {
            metric: float(indexed.loc["autoregressive_full", metric] - indexed.loc["autoregressive_no_snowmelt", metric])
            for metric in ["nse", "kge", "r2"]
        },
    }
    summary = {
        "station_id": args.station_id,
        "train": [str(data.index.min().date()), str(train_end.date())],
        "validation": [
            str((train_end + pd.Timedelta(days=1)).date()),
            str(validation_end.date()),
        ],
        "test": [
            str((validation_end + pd.Timedelta(days=1)).date()),
            str(data.index.max().date()),
        ],
        "snowmelt_contribution_full_minus_ablation": ablation,
        "core_snowmelt_apr_jun_contribution": {},
    }
    core = seasonal_metric_table.loc[
        seasonal_metric_table["season"].eq("core_snowmelt_apr_jun")
    ].set_index("model")
    for family in ["climate", "autoregressive"]:
        summary["core_snowmelt_apr_jun_contribution"][family] = {
            metric: float(
                core.loc[f"{family}_full", metric]
                - core.loc[f"{family}_no_snowmelt", metric]
            )
            for metric in ["nse", "kge", "r2"]
        }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metric_table.to_csv(args.output_dir / "metrics.csv", index=False)
    seasonal_metric_table.to_csv(
        args.output_dir / "seasonal_metrics.csv", index=False
    )
    prediction_table.reset_index().to_csv(
        args.output_dir / "test_predictions.csv", index=False
    )
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(metric_table.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
