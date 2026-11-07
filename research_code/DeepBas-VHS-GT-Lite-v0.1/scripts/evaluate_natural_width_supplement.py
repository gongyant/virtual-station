from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics

from evaluate_natural_width_virtual_station import (
    EXTERNAL_Q,
    MULTISITE_Q,
    fit_power_law,
    predict_power_law,
)


SINGLE = Path("data/processed/natural_width/landsat_byblk/landsat_width_measurements.csv")
MULTI = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/natural_width_supplement_round")


def load_discharge() -> pd.DataFrame:
    external = pd.read_csv(EXTERNAL_Q, parse_dates=["date"])[
        ["date", "upstream_q_m3s"]
    ].rename(columns={"upstream_q_m3s": "observed_q_m3s"})
    multisite = pd.read_csv(MULTISITE_Q, parse_dates=["date"])
    multisite = multisite.loc[
        multisite.station_code == "BYBLK", ["date", "observed_q_m3s"]
    ]
    return (
        pd.concat([external, multisite], ignore_index=True)
        .dropna()
        .drop_duplicates("date", keep="first")
    )


def prepare(path: Path, method: str, discharge: pd.DataFrame) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    frame = frame.loc[frame.measurement_status == "accepted"].copy()
    frame = frame.merge(discharge, on="date", how="left", validate="one_to_one")
    frame["method"] = method
    frame["year"] = frame.date.dt.year
    frame["split"] = frame.year.map(
        {2000: "calibration", 2001: "temporal_validation", 2005: "distant_test"}
    )
    train = frame.loc[(frame.split == "calibration") & frame.observed_q_m3s.notna()]
    scale, exponent = fit_power_law(
        train.width_m.to_numpy(float), train.observed_q_m3s.to_numpy(float)
    )
    frame["scale"] = scale
    frame["exponent"] = exponent
    frame["predicted_q_m3s"] = predict_power_law(
        frame.width_m.to_numpy(float), scale, exponent
    )
    frame["calibration_mean_q_m3s"] = float(train.observed_q_m3s.mean())
    return frame


def main() -> None:
    discharge = load_discharge()
    single = prepare(SINGLE, "single_transect", discharge)
    multi = prepare(MULTI, "seven_transect_median", discharge)
    combined = pd.concat([single, multi], ignore_index=True, sort=False)

    metric_rows = []
    for method, method_frame in combined.groupby("method"):
        for split, split_frame in method_frame.groupby("split"):
            paired = split_frame.dropna(subset=["observed_q_m3s"])
            metric_rows.append(
                {
                    "method": method,
                    "split": split,
                    **regression_metrics(
                        paired.observed_q_m3s.to_numpy(float),
                        paired.predicted_q_m3s.to_numpy(float),
                    ),
                }
            )
    validation_baseline = multi.loc[
        (multi.split == "temporal_validation") & multi.observed_q_m3s.notna()
    ]
    metric_rows.append(
        {
            "method": "calibration_mean",
            "split": "temporal_validation",
            **regression_metrics(
                validation_baseline.observed_q_m3s.to_numpy(float),
                validation_baseline.calibration_mean_q_m3s.to_numpy(float),
            ),
        }
    )
    metrics = pd.DataFrame(metric_rows)
    lookup = metrics.set_index(["method", "split"])
    multi_validation = lookup.loc[("seven_transect_median", "temporal_validation")]
    single_validation = lookup.loc[("single_transect", "temporal_validation")]
    mean_validation = lookup.loc[("calibration_mean", "temporal_validation")]

    multi_train = multi.loc[
        (multi.split == "calibration") & multi.observed_q_m3s.notna()
    ]
    loo_exponents = []
    for held_out in multi_train.index:
        subset = multi_train.drop(index=held_out)
        _, exponent = fit_power_law(
            subset.width_m.to_numpy(float), subset.observed_q_m3s.to_numpy(float)
        )
        loo_exponents.append(exponent)

    accepted = bool(
        float(multi.exponent.iloc[0]) > 0
        and multi_validation.nse > 0
        and multi_validation.rmse < single_validation.rmse
        and multi_validation.rmse < mean_validation.rmse
    )
    report = {
        "status": "completed_multitransect_supplement_experiment",
        "protocol": {
            "widths_created_before_discharge_join": True,
            "scene_selection_used_discharge": False,
            "calibration_year": 2000,
            "temporal_validation_year": 2001,
            "post_validation_tuning": False,
            "comparison_uses_identical_scene_dates": True,
        },
        "supplement": {
            "transects_per_scene": 7,
            "along_reach_offsets_m": [-300, -200, -100, 0, 100, 200, 300],
            "minimum_valid_transects": 4,
            "accepted_scenes": int((multi.measurement_status == "accepted").sum()),
            "median_within_scene_width_iqr_m": float(multi.width_iqr_m.median()),
        },
        "rating_curves": {
            method: {
                "scale": float(frame.scale.iloc[0]),
                "exponent": float(frame.exponent.iloc[0]),
            }
            for method, frame in [("single_transect", single), ("seven_transect_median", multi)]
        },
        "metrics": metrics.to_dict("records"),
        "multi_transect_effect": {
            "validation_nse_change": float(multi_validation.nse - single_validation.nse),
            "validation_rmse_reduction_m3s": float(
                single_validation.rmse - multi_validation.rmse
            ),
            "leave_one_out_exponent_min": float(min(loo_exponents)),
            "leave_one_out_exponent_max": float(max(loo_exponents)),
        },
        "candidate_status": "accepted" if accepted else "rejected_for_formal_inversion",
        "decision": (
            "The seven-transect supplement passed the temporal validation gate."
            if accepted
            else "Spatial replication improves width robustness but does not establish a "
            "stable time-transferable width-to-discharge relation. Retain the data and "
            "pipeline, but do not promote this branch to the final virtual station."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT / "single_vs_multitransect_scored.csv", index=False)
    metrics.to_csv(OUTPUT / "single_vs_multitransect_metrics.csv", index=False)
    (OUTPUT / "multitransect_supplement_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11.0, 4.8), dpi=160, sharey=True)
    for axis, (method, frame) in zip(
        axes, [("single transect", single), ("seven-transect median", multi)]
    ):
        for year, color in [(2000, "#1f77b4"), (2001, "#ff7f0e"), (2005, "#2ca02c")]:
            subset = frame.loc[(frame.year == year) & frame.observed_q_m3s.notna()]
            axis.scatter(subset.width_m, subset.observed_q_m3s, s=42, color=color, label=str(year))
        grid = np.linspace(10, 75, 160)
        axis.plot(
            grid,
            predict_power_law(grid, float(frame.scale.iloc[0]), float(frame.exponent.iloc[0])),
            color="#222222",
            linewidth=1.8,
        )
        axis.set_title(method)
        axis.set_xlabel("River width (m)")
        axis.grid(alpha=0.25)
    axes[0].set_ylabel("Observed discharge (m³/s)")
    axes[0].legend(title="Year", frameon=False)
    figure.suptitle("BYBLK supplemental multi-transect width experiment")
    figure.tight_layout()
    figure.savefig(OUTPUT / "single_vs_multitransect_comparison.png", bbox_inches="tight")
    plt.close(figure)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
