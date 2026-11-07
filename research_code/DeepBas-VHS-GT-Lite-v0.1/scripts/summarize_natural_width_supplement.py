from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


LANDSAT = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)
SENTINEL = Path(
    "data/processed/natural_width/sentinel2_byblk_multitransect/"
    "sentinel2_multitransect_width_measurements.csv"
)
EVALUATION = Path(
    "outputs/virtual_station_mainline/natural_width_supplement_round/"
    "multitransect_supplement_summary.json"
)
OUTPUT = Path("outputs/virtual_station_mainline/natural_width_supplement_round")


def main() -> None:
    landsat = pd.read_csv(LANDSAT, parse_dates=["date"])
    sentinel = pd.read_csv(SENTINEL, parse_dates=["date"])
    landsat = landsat.loc[landsat.measurement_status == "accepted"].copy()
    sentinel = sentinel.loc[sentinel.measurement_status == "accepted"].copy()
    evaluation = json.loads(EVALUATION.read_text(encoding="utf-8"))

    figure, axes = plt.subplots(2, 1, figsize=(10.5, 7.2), dpi=160)
    axes[0].scatter(landsat.date, landsat.width_m, color="#1f77b4", label="Landsat 30 m")
    axes[0].scatter(sentinel.date, sentinel.width_m, color="#2ca02c", label="Sentinel-2 10 m")
    axes[0].axhline(67.0, color="#333333", linestyle="--", label="SWORD reach mean 67 m")
    axes[0].set_ylabel("Seven-transect median width (m)")
    axes[0].set_title("BYBLK river-width supplements (non-contemporaneous sensors)")
    axes[0].legend(frameon=False)
    axes[0].grid(alpha=0.25)

    boxes = [landsat.width_iqr_m.dropna(), sentinel.width_iqr_m.dropna()]
    axes[1].boxplot(boxes, tick_labels=["Landsat 30 m", "Sentinel-2 10 m"])
    axes[1].set_ylabel("Within-scene width IQR across 7 transects (m)")
    axes[1].set_title("Spatial width consistency improves at 10 m resolution")
    axes[1].grid(axis="y", alpha=0.25)
    figure.tight_layout()
    figure.savefig(OUTPUT / "landsat_sentinel_width_supplement.png", bbox_inches="tight")
    plt.close(figure)

    summary = {
        "status": "completed_natural_width_data_supplement_round",
        "landsat_historical": {
            "accepted_scenes": int(len(landsat)),
            "median_width_m": float(landsat.width_m.median()),
            "median_within_scene_iqr_m": float(landsat.width_iqr_m.median()),
            "flow_validation_available": True,
        },
        "sentinel2_recent": {
            "accepted_scenes": int(len(sentinel)),
            "median_width_m": float(sentinel.width_m.median()),
            "median_within_scene_iqr_m": float(sentinel.width_iqr_m.median()),
            "flow_validation_available": False,
        },
        "historical_flow_result": {
            "single_validation_nse": next(
                row["nse"]
                for row in evaluation["metrics"]
                if row["method"] == "single_transect"
                and row["split"] == "temporal_validation"
            ),
            "multitransect_validation_nse": next(
                row["nse"]
                for row in evaluation["metrics"]
                if row["method"] == "seven_transect_median"
                and row["split"] == "temporal_validation"
            ),
            "multitransect_candidate_status": evaluation["candidate_status"],
        },
        "decision": (
            "The added spatial transects and 10 m imagery improve width measurement quality, "
            "but a formal virtual-station upgrade remains blocked by the negative 2001 NSE "
            "and the absence of discharge contemporaneous with Sentinel-2."
        ),
        "next_required_data": [
            "BYBLK observed discharge or stage for selected 2023-2025 Sentinel-2 dates",
            "surveyed cross-section or field/very-high-resolution width samples",
            "multiple nearby transects retained as an uncertainty ensemble",
        ],
    }
    (OUTPUT / "natural_width_data_supplement_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
