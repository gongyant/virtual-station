from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from vhs.metrics import regression_metrics


WIDTH = Path("data/processed/natural_width/landsat_byblk/landsat_width_measurements.csv")
EXTERNAL_Q = Path(
    "data/processed/virtual_station_external/external_input_byblk_2000_2001.csv"
)
MULTISITE_Q = Path(
    "data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
)
STATIC_MATCH = Path("data/processed/natural_width/station_sword_width_matches.csv")
OUTPUT = Path("outputs/virtual_station_mainline/natural_width_round")
PIXEL_HALF_WIDTH_M = 15.0


def fit_power_law(width: np.ndarray, discharge: np.ndarray) -> tuple[float, float]:
    design = np.column_stack([np.ones(len(width)), np.log(width)])
    intercept, exponent = np.linalg.lstsq(design, np.log(discharge), rcond=None)[0]
    return float(np.exp(intercept)), float(exponent)


def predict_power_law(width: np.ndarray, scale: float, exponent: float) -> np.ndarray:
    return scale * np.maximum(width, 1.0) ** exponent


def main() -> None:
    width = pd.read_csv(WIDTH, parse_dates=["date"])
    width = width.loc[width.measurement_status == "accepted"].copy()
    external = pd.read_csv(EXTERNAL_Q, parse_dates=["date"])[
        ["date", "upstream_q_m3s"]
    ].rename(columns={"upstream_q_m3s": "observed_q_m3s"})
    multisite = pd.read_csv(MULTISITE_Q, parse_dates=["date"])
    multisite = multisite.loc[
        multisite.station_code == "BYBLK", ["date", "observed_q_m3s"]
    ]
    discharge = (
        pd.concat([external, multisite], ignore_index=True)
        .dropna()
        .drop_duplicates("date", keep="first")
    )
    data = width.merge(discharge, on="date", how="left", validate="one_to_one")
    data["year"] = data.date.dt.year
    data["split"] = data.year.map(
        {2000: "calibration", 2001: "temporal_validation", 2005: "distant_test"}
    )

    train = data.loc[(data.split == "calibration") & data.observed_q_m3s.notna()]
    if len(train) < 6:
        raise ValueError("At least six accepted calibration width-flow pairs are required")
    scale, exponent = fit_power_law(
        train.width_m.to_numpy(float), train.observed_q_m3s.to_numpy(float)
    )
    data["predicted_q_width_powerlaw"] = predict_power_law(
        data.width_m.to_numpy(float), scale, exponent
    )
    data["predicted_q_train_mean"] = float(train.observed_q_m3s.mean())
    data["predicted_q_width_minus_15m"] = predict_power_law(
        np.maximum(data.width_m.to_numpy(float) - PIXEL_HALF_WIDTH_M, 1.0),
        scale,
        exponent,
    )
    data["predicted_q_width_plus_15m"] = predict_power_law(
        data.width_m.to_numpy(float) + PIXEL_HALF_WIDTH_M, scale, exponent
    )

    metric_rows = []
    for split in ["calibration", "temporal_validation", "distant_test"]:
        subset = data.loc[(data.split == split) & data.observed_q_m3s.notna()]
        for method, column in {
            "width_powerlaw": "predicted_q_width_powerlaw",
            "calibration_mean": "predicted_q_train_mean",
        }.items():
            metric_rows.append(
                {
                    "split": split,
                    "method": method,
                    **regression_metrics(
                        subset.observed_q_m3s.to_numpy(float),
                        subset[column].to_numpy(float),
                    ),
                }
            )
    metrics = pd.DataFrame(metric_rows)
    validation = metrics.loc[
        (metrics.split == "temporal_validation") & (metrics.method == "width_powerlaw")
    ].iloc[0]
    validation_baseline = metrics.loc[
        (metrics.split == "temporal_validation")
        & (metrics.method == "calibration_mean")
    ].iloc[0]
    accepted = bool(
        exponent > 0
        and validation["n"] >= 5
        and validation["nse"] > 0
        and validation["rmse"] < validation_baseline["rmse"]
    )

    static = pd.read_csv(STATIC_MATCH, dtype={"station_id": str})
    static = static.loc[static.station_id == "00705600"].iloc[0]
    paired = data.loc[data.observed_q_m3s.notna()].copy()
    report = {
        "status": "completed_natural_width_feasibility_experiment",
        "station": {
            "station_id": "00705600",
            "name": "BYBLK (Bayinbuluke)",
            "natural_reach_gate_passed": bool(static.natural_reach_candidate),
            "sword_reach_id": int(static.sword_reach_id),
            "station_to_reach_distance_m": float(static.distance_km) * 1000.0,
            "station_area_km2": float(static.station_upstream_area_km2),
            "sword_area_km2": float(static.sword_facc_km2),
            "static_sword_width_m": float(static.width_m),
            "landsat_accepted_width_median": float(width.width_m.median()),
        },
        "protocol": {
            "scene_selection_used_discharge": False,
            "calibration_year": 2000,
            "temporal_validation_year": 2001,
            "distant_test_year": 2005,
            "post_validation_tuning": False,
            "daily_flow_is_only_joined_after_width_quality_control": True,
        },
        "rating_curve": {
            "equation": "Q = scale * width^exponent",
            "scale": scale,
            "exponent": exponent,
            "expected_physical_sign": "exponent > 0",
        },
        "sample_counts": {
            "accepted_widths": int(len(width)),
            "paired_width_flow": int(len(paired)),
            "calibration": int((paired.split == "calibration").sum()),
            "temporal_validation": int((paired.split == "temporal_validation").sum()),
            "distant_test": int((paired.split == "distant_test").sum()),
        },
        "metrics": metrics.to_dict("records"),
        "pixel_scale_sensitivity": {
            "assumed_width_error_m": PIXEL_HALF_WIDTH_M,
            "median_prediction_span_m3s": float(
                (
                    paired.predicted_q_width_plus_15m
                    - paired.predicted_q_width_minus_15m
                ).median()
            ),
        },
        "candidate_status": "accepted" if accepted else "rejected_for_formal_inversion",
        "decision": (
            "The width-only rating curve passed the temporal validation gate."
            if accepted
            else "The available Landsat width series is useful as a real-data feasibility "
            "screen, but it does not pass the formal width-to-discharge inversion gate. "
            "Do not feed these widths into the final virtual station until finer imagery "
            "and stage/cross-section samples are added."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    data.to_csv(OUTPUT / "natural_width_scored_observations.csv", index=False)
    metrics.to_csv(OUTPUT / "natural_width_metrics.csv", index=False)
    figure, axis = plt.subplots(figsize=(8.0, 5.2), dpi=160)
    colors = {
        "calibration": "#1f77b4",
        "temporal_validation": "#ff7f0e",
        "distant_test": "#2ca02c",
    }
    labels = {
        "calibration": "2000 calibration",
        "temporal_validation": "2001 temporal validation",
        "distant_test": "2005 distant test",
    }
    for split in colors:
        subset = paired.loc[paired.split == split]
        axis.scatter(
            subset.width_m,
            subset.observed_q_m3s,
            s=48,
            color=colors[split],
            label=f"{labels[split]} (n={len(subset)})",
            zorder=3,
        )
    width_grid = np.linspace(max(10.0, width.width_m.min() - 5.0), width.width_m.max() + 5.0, 200)
    axis.plot(
        width_grid,
        predict_power_law(width_grid, scale, exponent),
        color="#222222",
        linewidth=2.0,
        label=f"Q={scale:.3f} W^{exponent:.3f}",
    )
    axis.set_xlabel("Landsat-derived river width (m)")
    axis.set_ylabel("Observed discharge (m³/s)")
    axis.set_title("BYBLK natural-reach width–discharge feasibility")
    axis.grid(alpha=0.25)
    axis.legend(frameon=False)
    figure.tight_layout()
    figure.savefig(OUTPUT / "natural_width_rating_curve.png", bbox_inches="tight")
    plt.close(figure)
    (OUTPUT / "natural_width_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
