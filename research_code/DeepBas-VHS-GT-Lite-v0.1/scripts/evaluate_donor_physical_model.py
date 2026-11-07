from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from scipy.optimize import differential_evolution

from vhs.metrics import regression_metrics


def simulate_runoff_mm(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    snowmelt: np.ndarray,
    evaporation: np.ndarray,
    parameters: np.ndarray,
) -> np.ndarray:
    runoff_coefficient, recession, baseflow, temperature_threshold = parameters
    liquid_precipitation = precipitation * (temperature > temperature_threshold)
    effective_water = np.maximum(liquid_precipitation + snowmelt - evaporation, 0.0)
    storage = 0.0
    runoff = np.zeros_like(effective_water, dtype=float)
    for index, water in enumerate(effective_water):
        storage = recession * storage + runoff_coefficient * water
        release = (1.0 - recession) * storage
        runoff[index] = max(release + baseflow, 0.0)
    return runoff


def simulate_dual_runoff_mm(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    snowmelt: np.ndarray,
    evaporation: np.ndarray,
    parameters: np.ndarray,
) -> np.ndarray:
    (
        runoff_coefficient,
        fast_fraction,
        fast_recession,
        slow_recession,
        baseflow,
        temperature_threshold,
    ) = parameters
    liquid_precipitation = precipitation * (temperature > temperature_threshold)
    effective_water = np.maximum(liquid_precipitation + snowmelt - evaporation, 0.0)
    fast_storage = 0.0
    slow_storage = 0.0
    runoff = np.zeros_like(effective_water, dtype=float)
    for index, water in enumerate(effective_water):
        fast_storage = (
            fast_recession * fast_storage
            + runoff_coefficient * fast_fraction * water
        )
        slow_storage = (
            slow_recession * slow_storage
            + runoff_coefficient * (1.0 - fast_fraction) * water
        )
        runoff[index] = max(
            (1.0 - fast_recession) * fast_storage
            + (1.0 - slow_recession) * slow_storage
            + baseflow,
            0.0,
        )
    return runoff


def load_forcing(path: Path, dimension: str, label: str) -> pd.DataFrame:
    with xr.open_dataset(path) as source:
        selected = source.sel({dimension: label}) if dimension in source.coords else source.isel({dimension: 0})
        frame = selected.to_dataframe()[
            [
                "temperature_c",
                "precipitation_mm",
                "snowmelt_mm",
                "evaporation_loss_mm",
            ]
        ].reset_index()
    frame["date"] = pd.to_datetime(frame["time"])
    return frame.drop(columns=[column for column in ["time", dimension] if column in frame])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strict donor-calibrated conceptual runoff model for an ungauged target."
    )
    parser.add_argument("--basin-era5", type=Path, required=True)
    parser.add_argument("--incremental-era5", type=Path, required=True)
    parser.add_argument("--flows", type=Path, default=Path("data/processed/timeseries.csv"))
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--routing-lag-days", type=int, default=3)
    parser.add_argument("--train-end", required=True)
    parser.add_argument("--validation-end", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    upstream_forcing = load_forcing(args.basin_era5, "station", args.upstream)
    incremental_forcing = load_forcing(
        args.incremental_era5, "basin", f"{args.upstream}_to_{args.target}"
    )
    flows = pd.read_csv(args.flows, dtype={"station_id": str})
    flows["station_id"] = flows["station_id"].str.zfill(8)
    flows["date"] = pd.to_datetime(flows["date"])
    upstream_flow = flows.loc[
        flows["station_id"].eq(args.upstream), ["date", "obs_q"]
    ].rename(columns={"obs_q": "upstream_q"})
    target_flow = flows.loc[
        flows["station_id"].eq(args.target), ["date", "obs_q"]
    ].rename(columns={"obs_q": "target_q"})
    upstream = upstream_forcing.merge(upstream_flow, on="date", how="inner")
    train_end = pd.Timestamp(args.train_end)
    validation_end = pd.Timestamp(args.validation_end)
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    upstream_area = float(nodes.loc[args.upstream, "UP_AREA"])
    target_area = float(nodes.loc[args.target, "UP_AREA"])
    incremental_area = target_area - upstream_area
    upstream["observed_runoff_mm"] = upstream["upstream_q"] * 86.4 / upstream_area
    train_mask = upstream["date"] <= train_end

    forcing_columns = [
        "precipitation_mm",
        "temperature_c",
        "snowmelt_mm",
        "evaporation_loss_mm",
    ]
    train = upstream.loc[train_mask].dropna(subset=forcing_columns + ["observed_runoff_mm"])

    candidates = {
        "single_linear_reservoir": {
            "simulate": simulate_runoff_mm,
            "bounds": [(0.0, 2.0), (0.0, 0.995), (0.0, 1.0), (-3.0, 3.0)],
            "parameter_names": [
                "runoff_coefficient",
                "recession",
                "baseflow_mm_day",
                "rain_snow_temperature_threshold_c",
            ],
        },
        "dual_fast_slow_reservoir": {
            "simulate": simulate_dual_runoff_mm,
            "bounds": [
                (0.0, 2.0),
                (0.0, 1.0),
                (0.0, 0.95),
                (0.80, 0.999),
                (0.0, 1.0),
                (-3.0, 3.0),
            ],
            "parameter_names": [
                "runoff_coefficient",
                "fast_fraction",
                "fast_recession",
                "slow_recession",
                "baseflow_mm_day",
                "rain_snow_temperature_threshold_c",
            ],
        },
    }
    calibration = {}
    validation_mask = (upstream["date"] > train_end) & (
        upstream["date"] <= validation_end
    )
    validation_observed = upstream.loc[validation_mask, "upstream_q"].to_numpy(float)
    for name, candidate in candidates.items():
        simulate = candidate["simulate"]

        def objective(parameters: np.ndarray) -> float:
            predicted = simulate(
                train["precipitation_mm"].to_numpy(float),
                train["temperature_c"].to_numpy(float),
                train["snowmelt_mm"].to_numpy(float),
                train["evaporation_loss_mm"].to_numpy(float),
                parameters,
            )
            return float(
                np.sqrt(
                    np.mean(
                        (train["observed_runoff_mm"].to_numpy(float) - predicted)
                        ** 2
                    )
                )
            )

        result = differential_evolution(
            objective,
            bounds=candidate["bounds"],
            seed=42,
            polish=True,
            workers=1,
        )
        full_runoff_mm = simulate(
            upstream["precipitation_mm"].to_numpy(float),
            upstream["temperature_c"].to_numpy(float),
            upstream["snowmelt_mm"].to_numpy(float),
            upstream["evaporation_loss_mm"].to_numpy(float),
            result.x,
        )
        full_q = full_runoff_mm * upstream_area / 86.4
        validation_prediction = full_q[validation_mask.to_numpy()]
        validation_rmse = float(
            np.sqrt(np.mean((validation_observed - validation_prediction) ** 2))
        )
        calibration[name] = {
            "parameters": result.x,
            "full_q": full_q,
            "validation_rmse": validation_rmse,
        }
    best_name = min(calibration, key=lambda name: calibration[name]["validation_rmse"])
    simple_name = "single_linear_reservoir"
    relative_improvement = (
        calibration[simple_name]["validation_rmse"]
        - calibration[best_name]["validation_rmse"]
    ) / calibration[simple_name]["validation_rmse"]
    selected_name = best_name if relative_improvement >= 0.01 else simple_name
    selected = calibration[selected_name]
    parameters = selected["parameters"]
    selected_simulate = candidates[selected_name]["simulate"]
    upstream["donor_model_q"] = selected["full_q"]

    incremental_forcing["local_runoff_mm"] = selected_simulate(
        incremental_forcing["precipitation_mm"].to_numpy(float),
        incremental_forcing["temperature_c"].to_numpy(float),
        incremental_forcing["snowmelt_mm"].to_numpy(float),
        incremental_forcing["evaporation_loss_mm"].to_numpy(float),
        parameters,
    )
    incremental_forcing["local_q"] = (
        incremental_forcing["local_runoff_mm"] * incremental_area / 86.4
    )
    prediction = incremental_forcing.merge(upstream_flow, on="date", how="inner").merge(
        target_flow, on="date", how="inner"
    )
    prediction["routed_upstream_q"] = prediction["upstream_q"].shift(
        args.routing_lag_days
    )
    prediction["donor_physical_q"] = np.maximum(
        prediction["routed_upstream_q"] + prediction["local_q"], 0.0
    )
    prediction = prediction.loc[prediction["date"] > validation_end].dropna(
        subset=["target_q", "donor_physical_q"]
    )
    physical_metrics = regression_metrics(
        prediction["target_q"], prediction["donor_physical_q"]
    )
    validation_upstream = upstream.loc[validation_mask].dropna(
        subset=["upstream_q", "donor_model_q"]
    )
    donor_validation_metrics = regression_metrics(
        validation_upstream["upstream_q"], validation_upstream["donor_model_q"]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction.to_csv(args.output_dir / "test_predictions.csv", index=False)
    summary = {
        "strict_protocol": {
            "target_labels_used_for_calibration": False,
            "calibration_station": args.upstream,
            "target_station": args.target,
            "calibration_end": args.train_end,
            "validation_end": args.validation_end,
        },
        "selected_structure": selected_name,
        "selection_criterion": (
            "lowest upstream-station validation RMSE, but a more complex structure "
            "must improve RMSE by at least 1 percent"
        ),
        "complex_structure_relative_validation_improvement": float(relative_improvement),
        "parameters": {
            parameter_name: float(value)
            for parameter_name, value in zip(
                candidates[selected_name]["parameter_names"], parameters
            )
        }
        | {"routing_lag_days": args.routing_lag_days},
        "candidate_upstream_validation_rmse": {
            name: float(values["validation_rmse"])
            for name, values in calibration.items()
        },
        "areas_km2": {
            "upstream": upstream_area,
            "target": target_area,
            "incremental": incremental_area,
        },
        "upstream_validation_metrics": donor_validation_metrics,
        "target_test_metrics": physical_metrics,
        "water_accounting_note": (
            "Liquid input uses rainfall above the fitted temperature threshold plus ERA5 snowmelt; "
            "snowfall retained in snow storage is not counted as simultaneous liquid input."
        ),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
