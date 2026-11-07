from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

from evaluate_donor_physical_model import (
    load_forcing,
    simulate_dual_runoff_mm,
    simulate_runoff_mm,
)
from vhs.metrics import regression_metrics


def simulate_seasonal_runoff_mm(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    snowmelt: np.ndarray,
    evaporation: np.ndarray,
    parameters: np.ndarray,
    months: np.ndarray,
) -> np.ndarray:
    """One continuous store with different cold- and warm-season recession."""
    (
        runoff_coefficient,
        cold_recession,
        warm_recession,
        baseflow,
        temperature_threshold,
    ) = parameters
    liquid_precipitation = precipitation * (temperature > temperature_threshold)
    effective_water = np.maximum(liquid_precipitation + snowmelt - evaporation, 0.0)
    storage = 0.0
    runoff = np.zeros_like(effective_water, dtype=float)
    warm = np.isin(months, np.arange(4, 11))
    for index, water in enumerate(effective_water):
        recession = warm_recession if warm[index] else cold_recession
        storage = recession * storage + runoff_coefficient * water
        runoff[index] = max((1.0 - recession) * storage + baseflow, 0.0)
    return runoff


def simulate_degree_day_snow_runoff_mm(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    snowmelt: np.ndarray,
    evaporation: np.ndarray,
    parameters: np.ndarray,
) -> np.ndarray:
    """Explicit snow storage and degree-day melt; ERA5 snowmelt is intentionally ablated."""
    (
        runoff_coefficient,
        recession,
        baseflow,
        snowfall_temperature_threshold,
        melt_temperature_threshold,
        degree_day_factor,
    ) = parameters
    storage = 0.0
    snow_storage = 0.0
    runoff = np.zeros_like(precipitation, dtype=float)
    for index, water in enumerate(precipitation):
        if temperature[index] <= snowfall_temperature_threshold:
            snow_storage += max(water, 0.0)
            rainfall = 0.0
        else:
            rainfall = max(water, 0.0)
        potential_melt = degree_day_factor * max(
            temperature[index] - melt_temperature_threshold, 0.0
        )
        actual_melt = min(snow_storage, potential_melt)
        snow_storage -= actual_melt
        effective_water = max(rainfall + actual_melt - evaporation[index], 0.0)
        storage = recession * storage + runoff_coefficient * effective_water
        runoff[index] = max((1.0 - recession) * storage + baseflow, 0.0)
    return runoff


def simulate_degree_day_fastflow_runoff_mm(
    precipitation: np.ndarray,
    temperature: np.ndarray,
    snowmelt: np.ndarray,
    evaporation: np.ndarray,
    parameters: np.ndarray,
) -> np.ndarray:
    """Degree-day snow store plus a mass-conserving threshold-excess fast pathway."""
    (
        runoff_coefficient,
        recession,
        baseflow,
        snowfall_temperature_threshold,
        melt_temperature_threshold,
        degree_day_factor,
        fastflow_threshold_mm_day,
        fastflow_fraction,
    ) = parameters
    storage = 0.0
    snow_storage = 0.0
    runoff = np.zeros_like(precipitation, dtype=float)
    for index, water in enumerate(precipitation):
        if temperature[index] <= snowfall_temperature_threshold:
            snow_storage += max(water, 0.0)
            rainfall = 0.0
        else:
            rainfall = max(water, 0.0)
        potential_melt = degree_day_factor * max(
            temperature[index] - melt_temperature_threshold, 0.0
        )
        actual_melt = min(snow_storage, potential_melt)
        snow_storage -= actual_melt
        effective_water = max(rainfall + actual_melt - evaporation[index], 0.0)
        threshold_excess = max(effective_water - fastflow_threshold_mm_day, 0.0)
        fast_input = fastflow_fraction * threshold_excess
        slow_input = effective_water - fast_input
        storage = recession * storage + runoff_coefficient * slow_input
        slow_release = (1.0 - recession) * storage
        fast_release = runoff_coefficient * fast_input
        runoff[index] = max(slow_release + fast_release + baseflow, 0.0)
    return runoff


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rolling-origin donor-only validation for conceptual runoff structures. "
            "The target-station flow series is never loaded."
        )
    )
    parser.add_argument("--basin-era5", type=Path, required=True)
    parser.add_argument("--flows", type=Path, default=Path("data/processed/timeseries.csv"))
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--first-validation-year", type=int, default=1980)
    parser.add_argument("--last-validation-year", type=int, default=1982)
    parser.add_argument("--complexity-threshold", type=float, default=0.01)
    parser.add_argument(
        "--candidates",
        nargs="+",
        help="Optional subset of conceptual structures to evaluate.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--maxiter", type=int, default=120)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    forcing = load_forcing(args.basin_era5, "station", args.upstream)
    flows = pd.read_csv(args.flows, dtype={"station_id": str})
    flows["station_id"] = flows["station_id"].str.zfill(8)
    flows["date"] = pd.to_datetime(flows["date"])
    donor_flow = flows.loc[
        flows["station_id"].eq(args.upstream), ["date", "obs_q"]
    ].rename(columns={"obs_q": "donor_q"})
    data = forcing.merge(donor_flow, on="date", how="inner").sort_values("date")
    area = float(
        pd.read_csv(args.nodes, dtype={"station_id": str})
        .assign(station_id=lambda frame: frame["station_id"].str.zfill(8))
        .set_index("station_id")
        .loc[args.upstream, "UP_AREA"]
    )
    data["observed_runoff_mm"] = data["donor_q"] * 86.4 / area
    data["month"] = data["date"].dt.month
    required = [
        "precipitation_mm",
        "temperature_c",
        "snowmelt_mm",
        "evaporation_loss_mm",
        "observed_runoff_mm",
    ]
    data = data.dropna(subset=required).reset_index(drop=True)

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
            "complexity": 4,
        },
        "seasonal_single_reservoir": {
            "simulate": simulate_seasonal_runoff_mm,
            "bounds": [
                (0.0, 2.0),
                (0.0, 0.995),
                (0.0, 0.995),
                (0.0, 1.0),
                (-3.0, 3.0),
            ],
            "parameter_names": [
                "runoff_coefficient",
                "cold_season_recession",
                "warm_season_recession",
                "baseflow_mm_day",
                "rain_snow_temperature_threshold_c",
            ],
            "complexity": 5,
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
            "complexity": 6,
        },
        "degree_day_snow_reservoir": {
            "simulate": simulate_degree_day_snow_runoff_mm,
            "bounds": [
                (0.0, 2.0),
                (0.0, 0.995),
                (0.0, 1.0),
                (-3.0, 3.0),
                (-3.0, 5.0),
                (0.0, 10.0),
            ],
            "parameter_names": [
                "runoff_coefficient",
                "recession",
                "baseflow_mm_day",
                "snowfall_temperature_threshold_c",
                "melt_temperature_threshold_c",
                "degree_day_factor_mm_c_day",
            ],
            "complexity": 6,
        },
        "degree_day_threshold_fastflow": {
            "simulate": simulate_degree_day_fastflow_runoff_mm,
            "bounds": [
                (0.0, 2.0),
                (0.0, 0.995),
                (0.0, 1.0),
                (-3.0, 3.0),
                (-3.0, 5.0),
                (0.0, 10.0),
                (0.0, 20.0),
                (0.0, 1.0),
            ],
            "parameter_names": [
                "runoff_coefficient",
                "recession",
                "baseflow_mm_day",
                "snowfall_temperature_threshold_c",
                "melt_temperature_threshold_c",
                "degree_day_factor_mm_c_day",
                "fastflow_threshold_mm_day",
                "fastflow_fraction",
            ],
            "complexity": 8,
        },
    }
    if args.candidates:
        unknown = sorted(set(args.candidates) - set(candidates))
        if unknown:
            raise ValueError(f"Unknown candidates: {unknown}")
        candidates = {name: candidates[name] for name in args.candidates}
    if "single_linear_reservoir" not in candidates:
        # The degree-day reservoir is the preregistered simple reference in focused runs.
        reference_name = "degree_day_snow_reservoir"
    else:
        reference_name = "single_linear_reservoir"

    def simulate(candidate: dict, frame: pd.DataFrame, parameters: np.ndarray) -> np.ndarray:
        arguments = [
            frame["precipitation_mm"].to_numpy(float),
            frame["temperature_c"].to_numpy(float),
            frame["snowmelt_mm"].to_numpy(float),
            frame["evaporation_loss_mm"].to_numpy(float),
            parameters,
        ]
        if candidate["simulate"] is simulate_seasonal_runoff_mm:
            arguments.append(frame["month"].to_numpy(int))
        return candidate["simulate"](*arguments)

    rows: list[dict] = []
    predictions: list[pd.DataFrame] = []
    fold_parameter_rows: list[dict] = []
    for validation_year in range(args.first_validation_year, args.last_validation_year + 1):
        calibration = data[data["date"].dt.year < validation_year].copy()
        validation = data[data["date"].dt.year == validation_year].copy()
        through_validation = data[data["date"].dt.year <= validation_year].copy()
        if calibration.empty or validation.empty:
            raise ValueError(f"Missing donor data for rolling fold {validation_year}")
        for offset, (name, candidate) in enumerate(candidates.items()):
            observed = calibration["observed_runoff_mm"].to_numpy(float)

            def objective(parameters: np.ndarray) -> float:
                predicted = simulate(candidate, calibration, parameters)
                return float(np.sqrt(np.mean((observed - predicted) ** 2)))

            result = differential_evolution(
                objective,
                bounds=candidate["bounds"],
                seed=args.seed + validation_year + offset,
                maxiter=args.maxiter,
                popsize=10,
                polish=True,
                workers=1,
            )
            fold_parameter_rows.append(
                {
                    "validation_year": validation_year,
                    "model": name,
                    **{
                        parameter_name: float(value)
                        for parameter_name, value in zip(
                            candidate["parameter_names"], result.x
                        )
                    },
                }
            )
            continuous_prediction_mm = simulate(candidate, through_validation, result.x)
            validation_positions = through_validation["date"].dt.year.eq(validation_year)
            predicted_q = continuous_prediction_mm[validation_positions.to_numpy()] * area / 86.4
            metrics = regression_metrics(validation["donor_q"], predicted_q)
            rows.append(
                {
                    "validation_year": validation_year,
                    "model": name,
                    "calibration_start": calibration["date"].min().date().isoformat(),
                    "calibration_end": calibration["date"].max().date().isoformat(),
                    **metrics,
                }
            )
            fold_prediction = validation[["date", "donor_q"]].copy()
            fold_prediction["prediction"] = predicted_q
            fold_prediction["model"] = name
            fold_prediction["validation_year"] = validation_year
            predictions.append(fold_prediction)

    metrics_frame = pd.DataFrame(rows)
    predictions_frame = pd.concat(predictions, ignore_index=True)
    aggregate_rows = []
    for name in candidates:
        selected = predictions_frame[predictions_frame["model"].eq(name)]
        aggregate_rows.append(
            {
                "model": name,
                "complexity": candidates[name]["complexity"],
                "folds": selected["validation_year"].nunique(),
                **regression_metrics(selected["donor_q"], selected["prediction"]),
            }
        )
    aggregate = pd.DataFrame(aggregate_rows).sort_values("rmse").reset_index(drop=True)
    regime_rows: list[dict] = []
    peak_rows: list[dict] = []
    for (validation_year, name), group in predictions_frame.groupby(
        ["validation_year", "model"], sort=True
    ):
        low_threshold = float(group["donor_q"].quantile(0.10))
        high_threshold = float(group["donor_q"].quantile(0.90))
        regimes = {
            "all_days": np.ones(len(group), dtype=bool),
            "high_flow_top10pct": group["donor_q"].ge(high_threshold).to_numpy(),
            "low_flow_bottom10pct": group["donor_q"].le(low_threshold).to_numpy(),
            "warm_apr_oct": group["date"].dt.month.between(4, 10).to_numpy(),
        }
        for regime, mask in regimes.items():
            selected_group = group.loc[mask]
            regime_rows.append(
                {
                    "validation_year": validation_year,
                    "model": name,
                    "regime": regime,
                    "observed_threshold_low": low_threshold,
                    "observed_threshold_high": high_threshold,
                    **regression_metrics(
                        selected_group["donor_q"], selected_group["prediction"]
                    ),
                }
            )
        observed_peak_row = group.loc[group["donor_q"].idxmax()]
        predicted_peak_row = group.loc[group["prediction"].idxmax()]
        peak_rows.append(
            {
                "validation_year": validation_year,
                "model": name,
                "observed_peak_date": observed_peak_row["date"].date().isoformat(),
                "predicted_peak_date": predicted_peak_row["date"].date().isoformat(),
                "peak_timing_error_days": int(
                    (predicted_peak_row["date"] - observed_peak_row["date"]).days
                ),
                "observed_peak_q": float(observed_peak_row["donor_q"]),
                "predicted_peak_q": float(predicted_peak_row["prediction"]),
                "peak_magnitude_bias_percent": float(
                    100.0
                    * (predicted_peak_row["prediction"] - observed_peak_row["donor_q"])
                    / observed_peak_row["donor_q"]
                ),
            }
        )
    regime_metrics = pd.DataFrame(regime_rows)
    peak_diagnostics = pd.DataFrame(peak_rows)
    simple_rmse = float(
        aggregate.loc[aggregate["model"].eq(reference_name), "rmse"].iloc[0]
    )
    best = aggregate.iloc[0]
    relative_improvement = (simple_rmse - float(best["rmse"])) / simple_rmse
    selected_name = (
        str(best["model"])
        if best["model"] == reference_name
        or relative_improvement >= args.complexity_threshold
        else reference_name
    )

    final_candidate = candidates[selected_name]
    final_data = data[data["date"].dt.year <= args.last_validation_year].copy()
    final_observed = final_data["observed_runoff_mm"].to_numpy(float)

    def final_objective(parameters: np.ndarray) -> float:
        predicted = simulate(final_candidate, final_data, parameters)
        return float(np.sqrt(np.mean((final_observed - predicted) ** 2)))

    final_result = differential_evolution(
        final_objective,
        bounds=final_candidate["bounds"],
        seed=args.seed,
        maxiter=args.maxiter,
        popsize=10,
        polish=True,
        workers=1,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics_frame.to_csv(args.output_dir / "fold_metrics.csv", index=False)
    aggregate.to_csv(args.output_dir / "aggregate_metrics.csv", index=False)
    predictions_frame.to_csv(args.output_dir / "rolling_predictions.csv", index=False)
    pd.DataFrame(fold_parameter_rows).to_csv(
        args.output_dir / "fold_parameters.csv", index=False
    )
    regime_metrics.to_csv(args.output_dir / "regime_metrics.csv", index=False)
    peak_diagnostics.to_csv(args.output_dir / "peak_diagnostics.csv", index=False)
    summary = {
        "protocol": {
            "donor_station": args.upstream,
            "target_station_flow_loaded": False,
            "validation_years": list(
                range(args.first_validation_year, args.last_validation_year + 1)
            ),
            "selection_uses_only_donor_station": True,
            "formal_1983_target_test_used": False,
        },
        "selection": {
            "selected_structure": selected_name,
            "pooled_best_structure": str(best["model"]),
            "pooled_best_relative_rmse_improvement_over_simple": float(
                relative_improvement
            ),
            "minimum_complexity_improvement": args.complexity_threshold,
            "reference_structure": reference_name,
        },
        "final_refit_period": [
            final_data["date"].min().date().isoformat(),
            final_data["date"].max().date().isoformat(),
        ],
        "final_parameters": {
            name: float(value)
            for name, value in zip(
                final_candidate["parameter_names"], final_result.x
            )
        },
        "aggregate_metrics": aggregate.to_dict(orient="records"),
        "selected_structure_peak_diagnostics": peak_diagnostics.loc[
            peak_diagnostics["model"].eq(selected_name)
        ].to_dict(orient="records"),
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
