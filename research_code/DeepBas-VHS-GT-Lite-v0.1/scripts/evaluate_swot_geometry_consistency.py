from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr


SWOT_PATH = Path(
    "data/processed/natural_width/swot_byblk_reach/swot_reach_observations_accepted.csv"
)
SENTINEL_PATH = Path(
    "data/processed/natural_width/sentinel2_byblk_multitransect/"
    "sentinel2_multitransect_width_measurements.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/natural_width_swot_round")


def finite_correlation(x: pd.Series, y: pd.Series, method: str) -> tuple[float, float]:
    keep = np.isfinite(x) & np.isfinite(y)
    if int(keep.sum()) < 3 or x.loc[keep].nunique() < 2 or y.loc[keep].nunique() < 2:
        return np.nan, np.nan
    result = pearsonr(x.loc[keep], y.loc[keep]) if method == "pearson" else spearmanr(
        x.loc[keep], y.loc[keep]
    )
    return float(result.statistic), float(result.pvalue)


def nse(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = float(np.sum((observed - np.mean(observed)) ** 2))
    if denominator <= 0:
        return np.nan
    return float(1 - np.sum((observed - predicted) ** 2) / denominator)


def assign_track_group(xtrk_dist: pd.Series) -> pd.Series:
    # Three stable cross-track clusters are visible in this reach. Keeping them separate
    # prevents spatial sampling offsets from being misread as temporal river response.
    return pd.Series(
        np.select(
            [xtrk_dist < -30000, xtrk_dist.between(0, 27000), xtrk_dist >= 27000],
            ["west_far", "near", "east_far"],
            default="other",
        ),
        index=xtrk_dist.index,
    )


def main() -> None:
    swot = pd.read_csv(SWOT_PATH)
    swot["datetime"] = pd.to_datetime(swot["date_time"], unit="ms", errors="coerce")
    swot["date"] = swot.datetime.dt.normalize()
    swot["year"] = swot.datetime.dt.year
    swot["track_group"] = assign_track_group(swot.xtrk_dist)
    swot["width_anomaly_m"] = swot.width - swot.groupby("track_group").width.transform(
        "median"
    )
    swot["wse_anomaly_m"] = swot.wse - swot.groupby("track_group").wse.transform(
        "median"
    )

    group_rows: list[dict[str, float | int | str]] = []
    validation_rows: list[dict[str, float | int | str]] = []
    for group, frame in swot.groupby("track_group"):
        pearson_r, pearson_p = finite_correlation(frame.wse, frame.width, "pearson")
        spearman_r, spearman_p = finite_correlation(frame.wse, frame.width, "spearman")
        group_rows.append(
            {
                "track_group": group,
                "records": int(len(frame)),
                "median_xtrk_distance_m": float(frame.xtrk_dist.median()),
                "median_width_m": float(frame.width.median()),
                "median_wse_m": float(frame.wse.median()),
                "pearson_wse_width_r": pearson_r,
                "pearson_p": pearson_p,
                "spearman_wse_width_rho": spearman_r,
                "spearman_p": spearman_p,
            }
        )

        train = frame.loc[frame.year == 2025]
        test = frame.loc[frame.year == 2026]
        if len(train) >= 3 and len(test) >= 2 and train.wse.nunique() >= 2:
            slope, intercept = np.polyfit(train.wse, train.width, 1)
            prediction = intercept + slope * test.wse.to_numpy()
            validation_rows.append(
                {
                    "track_group": group,
                    "train_year": 2025,
                    "test_year": 2026,
                    "train_records": int(len(train)),
                    "test_records": int(len(test)),
                    "width_change_per_wse_m": float(slope),
                    "test_nse": nse(test.width.to_numpy(), prediction),
                    "test_mae_m": float(np.mean(np.abs(test.width.to_numpy() - prediction))),
                    "test_rmse_m": float(
                        np.sqrt(np.mean((test.width.to_numpy() - prediction) ** 2))
                    ),
                }
            )

    groups = pd.DataFrame(group_rows).sort_values("track_group")
    validation = pd.DataFrame(validation_rows).sort_values("track_group")
    anomaly_pearson_r, anomaly_pearson_p = finite_correlation(
        swot.wse_anomaly_m, swot.width_anomaly_m, "pearson"
    )
    anomaly_spearman_r, anomaly_spearman_p = finite_correlation(
        swot.wse_anomaly_m, swot.width_anomaly_m, "spearman"
    )

    sentinel = pd.read_csv(SENTINEL_PATH)
    sentinel = sentinel.loc[sentinel.measurement_status.eq("accepted")].copy()
    sentinel["sentinel_date"] = pd.to_datetime(sentinel.date).dt.normalize()
    pair_rows: list[dict[str, object]] = []
    for _, scene in sentinel.iterrows():
        days = (swot.date - scene.sentinel_date).abs() / pd.Timedelta(days=1)
        nearest_index = days.idxmin()
        nearest = swot.loc[nearest_index]
        delta_days = float(days.loc[nearest_index])
        if delta_days <= 7:
            pair_rows.append(
                {
                    "sentinel_date": scene.sentinel_date.date().isoformat(),
                    "sentinel_width_m": float(scene.width_m),
                    "sentinel_width_iqr_m": float(scene.width_iqr_m),
                    "swot_date": nearest.date.date().isoformat(),
                    "swot_width_m": float(nearest.width),
                    "swot_wse_m": float(nearest.wse),
                    "swot_track_group": nearest.track_group,
                    "absolute_date_difference_days": delta_days,
                    "primary_pair_within_3_days": bool(delta_days <= 3),
                    "swot_minus_sentinel_width_m": float(nearest.width - scene.width_m),
                    "spatial_support_warning": (
                        "SWOT reach average and Sentinel local seven-transect median are not interchangeable"
                    ),
                }
            )
    pairs = pd.DataFrame(pair_rows)
    primary_pairs = pairs.loc[pairs.primary_pair_within_3_days].copy()

    # These dates are the smallest, highest-priority ground-observation package needed
    # to decide whether the satellite geometry can be calibrated to discharge.
    request_rows: list[dict[str, object]] = []
    for _, pair in primary_pairs.iterrows():
        for source, date_column in [("Sentinel-2", "sentinel_date"), ("SWOT", "swot_date")]:
            request_rows.append(
                {
                    "priority": "P1",
                    "date": pair[date_column],
                    "satellite_source": source,
                    "requested_ground_fields": (
                        "BYBLK daily mean discharge; daily mean stage; rating-curve version; "
                        "measurement/change note"
                    ),
                    "acceptable_time_window": "same day preferred; +/-1 day with hourly values",
                }
            )
    for _, row in sentinel.iterrows():
        request_rows.append(
            {
                "priority": "P2",
                "date": row.sentinel_date.date().isoformat(),
                "satellite_source": "Sentinel-2",
                "requested_ground_fields": "BYBLK daily mean discharge and stage",
                "acceptable_time_window": "same day preferred",
            }
        )
    for _, row in swot.iterrows():
        request_rows.append(
            {
                "priority": "P2",
                "date": row.date.date().isoformat(),
                "satellite_source": "SWOT",
                "requested_ground_fields": "BYBLK daily mean discharge and stage",
                "acceptable_time_window": "same day preferred",
            }
        )
    request_manifest = (
        pd.DataFrame(request_rows)
        .drop_duplicates(subset=["priority", "date", "satellite_source"])
        .sort_values(["priority", "date", "satellite_source"])
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    swot.to_csv(OUTPUT / "swot_geometry_with_track_groups.csv", index=False)
    groups.to_csv(OUTPUT / "swot_track_group_diagnostics.csv", index=False)
    validation.to_csv(OUTPUT / "swot_2025_to_2026_width_validation.csv", index=False)
    pairs.to_csv(OUTPUT / "sentinel_swot_nearest_date_pairs.csv", index=False)
    request_manifest.to_csv(OUTPUT / "byblk_ground_observation_request_manifest.csv", index=False)

    colors = {"west_far": "#3b82f6", "near": "#f97316", "east_far": "#16a34a"}
    figure, axes = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    for group, frame in swot.groupby("track_group"):
        axes[0].scatter(frame.wse, frame.width, label=group, color=colors.get(group), s=38)
        axes[1].plot(frame.datetime, frame.width, "o-", label=group, color=colors.get(group), ms=4)
    axes[0].set(xlabel="SWOT WSE (m)", ylabel="SWOT reach width (m)", title="WSE-width by overpass group")
    axes[0].legend(frameon=False)
    axes[1].set(xlabel="Date", ylabel="SWOT reach width (m)", title="Systematic overpass-group offsets")
    axes[1].tick_params(axis="x", rotation=35)
    if len(pairs):
        axes[2].scatter(pairs.sentinel_width_m, pairs.swot_width_m, c=pairs.absolute_date_difference_days, cmap="viridis", s=60)
        lower = float(min(pairs.sentinel_width_m.min(), pairs.swot_width_m.min()))
        upper = float(max(pairs.sentinel_width_m.max(), pairs.swot_width_m.max()))
        axes[2].plot([lower, upper], [lower, upper], "k--", lw=1)
    axes[2].set(
        xlabel="Sentinel local 7-transect width (m)",
        ylabel="SWOT reach-average width (m)",
        title="Nearest observations (<=7 days)",
    )
    figure.savefig(OUTPUT / "swot_geometry_consistency.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": "completed_but_not_accepted_for_discharge_inversion",
        "swot_geometry_records": int(len(swot)),
        "swot_discharge_records": 0,
        "track_groups": int(swot.track_group.nunique()),
        "track_group_median_width_range_m": [
            float(groups.median_width_m.min()),
            float(groups.median_width_m.max()),
        ],
        "track_demeaned_wse_width": {
            "pearson_r": anomaly_pearson_r,
            "pearson_p": anomaly_pearson_p,
            "spearman_rho": anomaly_spearman_r,
            "spearman_p": anomaly_spearman_p,
        },
        "chronological_2026_validation": validation.to_dict(orient="records"),
        "sentinel_swot_pairs_within_3_days": int(len(primary_pairs)),
        "sentinel_swot_pairs_within_7_days": int(len(pairs)),
        "decision": (
            "SWOT WSE, slope and width are retained as auxiliary geometry/physics features only. "
            "Width has strong overpass-group spatial offsets, track-demeaned WSE-width coupling "
            "is not supported, and no usable SWOT discharge field exists. Do not train or validate "
            "a discharge inversion until contemporaneous BYBLK stage/discharge is obtained."
        ),
    }
    (OUTPUT / "swot_geometry_consistency_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
