from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

from vhs.metrics import regression_metrics


WIDTH_PATH = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)
FLOW_PATH = Path("data/processed/virtual_station_external/external_input_byblk_2000_2001.csv")
STATIC_PATH = Path("data/processed/natural_width/station_sword_width_matches.csv")
OUTPUT = Path("outputs/virtual_station_mainline/natural_manning_constraint_round")
STATION_ID = "00705600"
BOUNDS = {"bottom_width_m": (0.0, 16.0), "side_slope_h_to_v": (0.5, 10.0), "manning_n": (0.02, 0.08)}


def trapezoidal_manning_discharge(
    top_width_m: np.ndarray,
    bottom_width_m: float,
    side_slope_h_to_v: float,
    manning_n: float,
    channel_slope_m_per_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    width = np.asarray(top_width_m, dtype=float)
    if (
        bottom_width_m < 0
        or side_slope_h_to_v <= 0
        or manning_n <= 0
        or channel_slope_m_per_m <= 0
    ):
        raise ValueError("Hydraulic parameters and slope must be physically positive")
    depth = (width - bottom_width_m) / (2.0 * side_slope_h_to_v)
    valid = depth > 0
    area = depth * (bottom_width_m + width) / 2.0
    wetted_perimeter = bottom_width_m + 2.0 * depth * np.sqrt(
        1.0 + side_slope_h_to_v**2
    )
    hydraulic_radius = np.divide(
        area,
        wetted_perimeter,
        out=np.full_like(area, np.nan),
        where=wetted_perimeter > 0,
    )
    discharge = (
        area
        * np.power(hydraulic_radius, 2.0 / 3.0)
        * np.sqrt(channel_slope_m_per_m)
        / manning_n
    )
    discharge[~valid] = np.nan
    return discharge, depth


def fit_manning(frame: pd.DataFrame, slope: float, seed: int = 42) -> dict[str, float]:
    width = frame.width_m.to_numpy(float)
    observed = frame.observed_q_m3s.to_numpy(float)

    def objective(parameters: np.ndarray) -> float:
        predicted, _ = trapezoidal_manning_discharge(width, *parameters, slope)
        if not np.isfinite(predicted).all() or np.any(predicted <= 0):
            return 1e9
        # Log error balances low- and high-flow observations and is declared before validation.
        return float(np.mean((np.log(predicted) - np.log(observed)) ** 2))

    result = differential_evolution(
        objective,
        list(BOUNDS.values()),
        seed=seed,
        tol=1e-9,
        polish=True,
        workers=1,
    )
    return {
        "bottom_width_m": float(result.x[0]),
        "side_slope_h_to_v": float(result.x[1]),
        "manning_n": float(result.x[2]),
        "log_mse": float(result.fun),
    }


def fit_power_law(frame: pd.DataFrame) -> tuple[float, float]:
    design = np.column_stack([np.ones(len(frame)), np.log(frame.width_m.to_numpy(float))])
    intercept, exponent = np.linalg.lstsq(
        design, np.log(frame.observed_q_m3s.to_numpy(float)), rcond=None
    )[0]
    return float(np.exp(intercept)), float(exponent)


def main() -> None:
    width = pd.read_csv(WIDTH_PATH, parse_dates=["date"])
    width = width.loc[width.measurement_status.eq("accepted")].copy()
    flow = pd.read_csv(FLOW_PATH, parse_dates=["date"])[["date", "upstream_q_m3s"]].rename(
        columns={"upstream_q_m3s": "observed_q_m3s"}
    )
    data = width.merge(flow, on="date", how="inner", validate="one_to_one").dropna(
        subset=["width_m", "observed_q_m3s"]
    )
    data["year"] = data.date.dt.year
    train = data.loc[data.year.eq(2000)].copy()
    validation = data.loc[data.year.eq(2001)].copy()
    if len(train) < 6 or len(validation) < 5:
        raise ValueError("The predeclared 2000/2001 split lacks enough paired observations")

    static = pd.read_csv(STATIC_PATH, dtype={"station_id": str})
    row = static.loc[static.station_id.eq(STATION_ID)].iloc[0]
    slope = float(row.slope_m_per_km) / 1000.0
    parameters = fit_manning(train, slope)
    parameter_values = [
        parameters["bottom_width_m"],
        parameters["side_slope_h_to_v"],
        parameters["manning_n"],
    ]
    data["manning_predicted_q_m3s"], data["implied_depth_m"] = trapezoidal_manning_discharge(
        data.width_m.to_numpy(float), *parameter_values, slope
    )
    scale, exponent = fit_power_law(train)
    data["powerlaw_predicted_q_m3s"] = scale * np.power(data.width_m, exponent)
    data["calibration_mean_q_m3s"] = float(train.observed_q_m3s.mean())
    data["split"] = np.where(data.year.eq(2000), "calibration", "temporal_validation")

    metric_rows = []
    for split, frame in data.groupby("split"):
        for method, column in {
            "trapezoidal_manning": "manning_predicted_q_m3s",
            "empirical_powerlaw": "powerlaw_predicted_q_m3s",
            "calibration_mean": "calibration_mean_q_m3s",
        }.items():
            metric_rows.append(
                {
                    "split": split,
                    "method": method,
                    **regression_metrics(frame.observed_q_m3s, frame[column]),
                }
            )
    metrics = pd.DataFrame(metric_rows)

    leave_one_out = []
    for omitted_index in train.index:
        subset = train.drop(index=omitted_index)
        fitted = fit_manning(subset, slope, seed=42 + int(omitted_index))
        leave_one_out.append(
            {
                "omitted_date": train.loc[omitted_index, "date"].date().isoformat(),
                **fitted,
            }
        )
    leave_one_out = pd.DataFrame(leave_one_out)

    bounds_hit = {
        name: bool(
            (value - lower) <= 0.01 * (upper - lower)
            or (upper - value) <= 0.01 * (upper - lower)
        )
        for (name, (lower, upper)), value in zip(BOUNDS.items(), parameter_values)
    }
    val_manning = metrics.loc[
        metrics.split.eq("temporal_validation")
        & metrics.method.eq("trapezoidal_manning")
    ].iloc[0]
    val_powerlaw = metrics.loc[
        metrics.split.eq("temporal_validation") & metrics.method.eq("empirical_powerlaw")
    ].iloc[0]
    accepted = bool(
        not any(bounds_hit.values())
        and val_manning.nse > 0
        and val_manning.rmse < val_powerlaw.rmse
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT / "manning_scored_observations.csv", index=False)
    metrics.to_csv(OUTPUT / "manning_model_metrics.csv", index=False)
    leave_one_out.to_csv(OUTPUT / "manning_leave_one_out_parameters.csv", index=False)

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for split, color in [("calibration", "#2563eb"), ("temporal_validation", "#ea580c")]:
        frame = data.loc[data.split.eq(split)]
        axes[0].scatter(frame.width_m, frame.observed_q_m3s, color=color, s=52, label=split)
    grid = np.linspace(data.width_m.min(), data.width_m.max(), 200)
    manning_grid, _ = trapezoidal_manning_discharge(grid, *parameter_values, slope)
    axes[0].plot(grid, manning_grid, color="#111827", label="trapezoidal Manning")
    axes[0].plot(grid, scale * grid**exponent, "--", color="#16a34a", label="power law")
    axes[0].set(xlabel="Landsat 7-transect width (m)", ylabel="Discharge (m3/s)", title="2000 calibration and 2001 validation")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.2)
    axes[1].plot(data.date, data.observed_q_m3s, "o-", label="observed", color="#111827")
    axes[1].plot(data.date, data.manning_predicted_q_m3s, "o--", label="Manning", color="#7c3aed")
    axes[1].axvline(pd.Timestamp("2001-01-01"), color="#9ca3af", linestyle=":")
    axes[1].set(xlabel="Date", ylabel="Discharge (m3/s)", title="Strict temporal transfer")
    axes[1].tick_params(axis="x", rotation=35)
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "manning_constraint_diagnostics.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": "completed_rejected_for_formal_inversion" if not accepted else "accepted",
        "protocol": {
            "calibration_year": 2000,
            "temporal_validation_year": 2001,
            "validation_used_for_parameter_fitting": False,
            "channel_slope_source": "SWORD matched reach static slope",
            "channel_slope_m_per_m": slope,
            "objective": "mean squared log discharge error",
        },
        "model": "trapezoidal cross-section plus Manning equation",
        "parameter_bounds": BOUNDS,
        "fitted_parameters": parameters,
        "parameter_near_bound": bounds_hit,
        "implied_depth_range_m": [
            float(data.implied_depth_m.min()),
            float(data.implied_depth_m.max()),
        ],
        "sample_counts": {"calibration": int(len(train)), "temporal_validation": int(len(validation))},
        "metrics": metrics.to_dict(orient="records"),
        "leave_one_out_parameter_ranges": {
            column: [float(leave_one_out[column].min()), float(leave_one_out[column].max())]
            for column in ["bottom_width_m", "side_slope_h_to_v", "manning_n"]
        },
        "accepted": accepted,
        "decision": (
            "The hydraulic constraint is rejected. Width and static slope alone do not identify "
            "depth, cross-section shape, and roughness; a fitted parameter reaches its allowed "
            "boundary and the 2001 temporal validation does not beat the empirical width model. "
            "Keep Manning as a diagnostic envelope only, not a discharge label or GNN anchor."
            if not accepted
            else "The hydraulic constraint passed all predeclared gates."
        ),
    }
    (OUTPUT / "manning_constraint_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
