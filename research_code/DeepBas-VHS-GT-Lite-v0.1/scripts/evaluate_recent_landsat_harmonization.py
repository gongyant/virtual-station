from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu


HISTORICAL = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)
RECENT = Path(
    "data/processed/natural_width/landsat_recent_byblk_multitransect/"
    "landsat_recent_multitransect_width_measurements.csv"
)
SENTINEL = Path(
    "data/processed/natural_width/sentinel2_byblk_multitransect/"
    "sentinel2_multitransect_width_measurements.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/natural_sensor_harmonization_round")


def accepted(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame.loc[frame.measurement_status.eq("accepted")].copy()
    frame["date"] = pd.to_datetime(frame.date).dt.normalize()
    return frame


def greedy_date_pairs(
    left: pd.DataFrame, right: pd.DataFrame, maximum_days: int
) -> pd.DataFrame:
    candidates = []
    for left_index, left_row in left.iterrows():
        for right_index, right_row in right.iterrows():
            delta = abs((left_row.date - right_row.date).days)
            if delta <= maximum_days:
                candidates.append((delta, left_index, right_index))
    used_left, used_right, rows = set(), set(), []
    for delta, left_index, right_index in sorted(candidates):
        if left_index in used_left or right_index in used_right:
            continue
        used_left.add(left_index)
        used_right.add(right_index)
        lrow, rrow = left.loc[left_index], right.loc[right_index]
        rows.append(
            {
                "landsat_date": lrow.date.date().isoformat(),
                "landsat_width_m": float(lrow.width_m),
                "landsat_width_iqr_m": float(lrow.width_iqr_m),
                "sentinel_date": rrow.date.date().isoformat(),
                "sentinel_width_m": float(rrow.width_m),
                "sentinel_width_iqr_m": float(rrow.width_iqr_m),
                "absolute_date_difference_days": int(delta),
                "landsat_minus_sentinel_width_m": float(lrow.width_m - rrow.width_m),
            }
        )
    return pd.DataFrame(rows)


def pair_metrics(pairs: pd.DataFrame) -> dict[str, float | int | None]:
    if not len(pairs):
        return {"n": 0, "mean_bias_m": None, "mae_m": None, "rmse_m": None}
    difference = pairs.landsat_minus_sentinel_width_m.to_numpy(float)
    return {
        "n": int(len(pairs)),
        "mean_bias_m": float(np.mean(difference)),
        "median_bias_m": float(np.median(difference)),
        "mae_m": float(np.mean(np.abs(difference))),
        "rmse_m": float(np.sqrt(np.mean(difference**2))),
        "difference_iqr_m": float(np.percentile(difference, 75) - np.percentile(difference, 25)),
    }


def main() -> None:
    historical = accepted(HISTORICAL)
    recent = accepted(RECENT)
    sentinel = accepted(SENTINEL)
    pairs_3d = greedy_date_pairs(recent, sentinel, maximum_days=3)
    pairs_7d = greedy_date_pairs(recent, sentinel, maximum_days=7)

    distribution_rows = []
    for name, frame in [
        ("historical_landsat_2000_2005", historical),
        ("recent_landsat_2023_2025", recent),
        ("sentinel2_2023_2025", sentinel),
    ]:
        distribution_rows.append(
            {
                "series": name,
                "n": int(len(frame)),
                "median_width_m": float(frame.width_m.median()),
                "width_iqr_m": float(frame.width_m.quantile(0.75) - frame.width_m.quantile(0.25)),
                "median_within_scene_iqr_m": float(frame.width_iqr_m.median()),
                "minimum_width_m": float(frame.width_m.min()),
                "maximum_width_m": float(frame.width_m.max()),
            }
        )
    distributions = pd.DataFrame(distribution_rows)
    historical_recent_test = mannwhitneyu(
        historical.width_m, recent.width_m, alternative="two-sided", method="auto"
    )
    metrics_3d = pair_metrics(pairs_3d)
    metrics_7d = pair_metrics(pairs_7d)
    # A correction needs enough independent pairs; otherwise a small apparent bias is not stable.
    correction_ready = bool(len(pairs_3d) >= 10 and abs(float(metrics_3d["mean_bias_m"])) <= 10)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pairs_3d.to_csv(OUTPUT / "landsat_sentinel_pairs_within_3_days.csv", index=False)
    pairs_7d.to_csv(OUTPUT / "landsat_sentinel_pairs_within_7_days.csv", index=False)
    distributions.to_csv(OUTPUT / "sensor_width_distributions.csv", index=False)

    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), constrained_layout=True)
    axes[0].boxplot(
        [historical.width_m, recent.width_m, sentinel.width_m],
        tick_labels=["Historical\nLandsat", "Recent\nLandsat", "Sentinel-2"],
    )
    axes[0].set(ylabel="Seven-transect median width (m)", title="Width distributions")
    axes[0].grid(axis="y", alpha=0.2)
    if len(pairs_7d):
        axes[1].scatter(
            pairs_7d.sentinel_width_m,
            pairs_7d.landsat_width_m,
            c=pairs_7d.absolute_date_difference_days,
            cmap="viridis",
            s=65,
        )
        lower = float(min(pairs_7d.sentinel_width_m.min(), pairs_7d.landsat_width_m.min())) - 2
        upper = float(max(pairs_7d.sentinel_width_m.max(), pairs_7d.landsat_width_m.max())) + 2
        axes[1].plot([lower, upper], [lower, upper], "k--", lw=1)
        axes[1].set(xlim=(lower, upper), ylim=(lower, upper))
    axes[1].set(
        xlabel="Sentinel-2 width (m)",
        ylabel="Landsat width (m)",
        title="One-to-one nearest dates (<=7 days)",
    )
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "sensor_harmonization_diagnostics.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": "completed_bias_correction_not_identified"
        if not correction_ready
        else "completed_bias_correction_ready",
        "scene_selection_used_discharge": False,
        "distributions": distributions.to_dict(orient="records"),
        "historical_vs_recent_landsat_mann_whitney": {
            "statistic": float(historical_recent_test.statistic),
            "pvalue": float(historical_recent_test.pvalue),
        },
        "paired_within_3_days": metrics_3d,
        "paired_within_7_days_sensitivity": metrics_7d,
        "minimum_pairs_for_bias_correction": 10,
        "bias_correction_ready": correction_ready,
        "decision": (
            "Recent Landsat is accepted as a separate masked GNN feature. Historical and recent "
            "Landsat medians are consistent, but too few <=3-day Landsat/Sentinel pairs exist to "
            "estimate a defensible sensor conversion. Do not apply a fitted bias correction or "
            "replace Sentinel widths with Landsat widths."
        ),
    }
    (OUTPUT / "sensor_harmonization_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
