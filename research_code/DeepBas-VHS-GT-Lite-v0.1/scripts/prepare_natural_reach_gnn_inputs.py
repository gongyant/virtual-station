from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


SENTINEL_PATH = Path(
    "data/processed/natural_width/sentinel2_byblk_multitransect/"
    "sentinel2_multitransect_width_measurements.csv"
)
RECENT_LANDSAT_PATH = Path(
    "data/processed/natural_width/landsat_recent_byblk_multitransect/"
    "landsat_recent_multitransect_width_measurements.csv"
)
SWOT_PATH = Path(
    "outputs/virtual_station_mainline/natural_width_swot_round/"
    "swot_geometry_with_track_groups.csv"
)
SWORD_PATH = Path("data/processed/natural_width/station_sword_width_matches.csv")
GROUND_PATH = Path("data/raw/natural_width/byblk_ground_observations.csv")
TEMPLATE_PATH = Path("data/templates/byblk_ground_observations_template.csv")
OUTPUT = Path("data/processed/natural_width/gnn_inputs")
REPORT_OUTPUT = Path("outputs/virtual_station_mainline/natural_reach_gnn_input_round")
STATION_ID = "00705600"
REACH_ID = "48220900311"


def load_ground_observations(path: Path) -> pd.DataFrame:
    required = [
        "date",
        "discharge_m3s",
        "stage_m",
        "rating_curve_version",
        "quality_code",
        "change_note",
    ]
    if not path.exists():
        return pd.DataFrame(columns=required)
    frame = pd.read_csv(path)
    missing = [column for column in required if column not in frame]
    if missing:
        raise ValueError("Ground observation file is missing columns: " + ", ".join(missing))
    frame = frame[required].copy()
    frame["date"] = pd.to_datetime(frame.date, errors="coerce").dt.normalize()
    if frame.date.isna().any():
        raise ValueError("Ground observation file contains invalid dates")
    if frame.date.duplicated().any():
        raise ValueError("Ground observation file contains duplicate dates")
    for column in ["discharge_m3s", "stage_m"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame.discharge_m3s.dropna().lt(0).any():
        raise ValueError("Discharge must be non-negative")
    return frame


def same_day_pair_count(daily: pd.DataFrame, satellite_mask: str, ground_column: str) -> int:
    return int((daily[satellite_mask].eq(1) & daily[ground_column].notna()).sum())


def main() -> None:
    landsat = pd.read_csv(RECENT_LANDSAT_PATH)
    landsat = landsat.loc[landsat.measurement_status.eq("accepted")].copy()
    landsat["date"] = pd.to_datetime(landsat.date).dt.normalize()
    landsat = landsat[
        ["date", "width_m", "width_iqr_m", "valid_transects", "scene_cloud_percent"]
    ].rename(
        columns={
            "width_m": "landsat_width_m",
            "width_iqr_m": "landsat_width_iqr_m",
            "valid_transects": "landsat_valid_transects",
            "scene_cloud_percent": "landsat_scene_cloud_percent",
        }
    )
    landsat["landsat_observation_mask"] = 1

    sentinel = pd.read_csv(SENTINEL_PATH)
    sentinel = sentinel.loc[sentinel.measurement_status.eq("accepted")].copy()
    sentinel["date"] = pd.to_datetime(sentinel.date).dt.normalize()
    sentinel = sentinel[
        ["date", "width_m", "width_iqr_m", "valid_transects", "scene_cloud_percent"]
    ].rename(
        columns={
            "width_m": "sentinel_width_m",
            "width_iqr_m": "sentinel_width_iqr_m",
            "valid_transects": "sentinel_valid_transects",
            "scene_cloud_percent": "sentinel_scene_cloud_percent",
        }
    )
    sentinel["sentinel_observation_mask"] = 1

    swot = pd.read_csv(SWOT_PATH)
    swot["date"] = pd.to_datetime(swot.datetime).dt.normalize()
    swot = swot[
        [
            "date",
            "wse",
            "wse_u",
            "wse_anomaly_m",
            "width",
            "width_u",
            "width_anomaly_m",
            "slope",
            "slope_u",
            "xtrk_dist",
            "track_group",
            "obs_frac_n",
            "n_good_nod",
        ]
    ].rename(
        columns={
            "wse": "swot_wse_m",
            "wse_u": "swot_wse_uncertainty_m",
            "wse_anomaly_m": "swot_track_demeaned_wse_m",
            "width": "swot_reach_width_m",
            "width_u": "swot_width_uncertainty_m",
            "width_anomaly_m": "swot_track_demeaned_width_m",
            "slope": "swot_slope_m_per_m",
            "slope_u": "swot_slope_uncertainty_m_per_m",
            "xtrk_dist": "swot_cross_track_distance_m",
            "track_group": "swot_track_group",
            "obs_frac_n": "swot_observed_node_fraction",
            "n_good_nod": "swot_good_nodes",
        }
    )
    swot["swot_observation_mask"] = 1
    for group in ["west_far", "near", "east_far"]:
        swot[f"swot_track_{group}"] = swot.swot_track_group.eq(group).astype(int)

    ground = load_ground_observations(GROUND_PATH)

    start = min(landsat.date.min(), sentinel.date.min(), swot.date.min())
    end = max(landsat.date.max(), sentinel.date.max(), swot.date.max())
    daily = pd.DataFrame({"date": pd.date_range(start, end, freq="D")})
    daily = daily.merge(landsat, on="date", how="left", validate="one_to_one")
    daily = daily.merge(sentinel, on="date", how="left", validate="one_to_one")
    daily = daily.merge(swot, on="date", how="left", validate="one_to_one")
    if len(ground):
        daily = daily.merge(ground, on="date", how="left", validate="one_to_one")
    else:
        for column in [
            "discharge_m3s",
            "stage_m",
            "rating_curve_version",
            "quality_code",
            "change_note",
        ]:
            daily[column] = np.nan
    daily["station_id"] = STATION_ID
    daily["reach_id"] = REACH_ID
    daily["landsat_observation_mask"] = daily.landsat_observation_mask.fillna(0).astype(int)
    daily["sentinel_observation_mask"] = daily.sentinel_observation_mask.fillna(0).astype(int)
    daily["swot_observation_mask"] = daily.swot_observation_mask.fillna(0).astype(int)
    for group in ["west_far", "near", "east_far"]:
        column = f"swot_track_{group}"
        daily[column] = daily[column].fillna(0).astype(int)
    daily["discharge_label_mask"] = daily.discharge_m3s.notna().astype(int)
    daily["stage_label_mask"] = daily.stage_m.notna().astype(int)
    daily["any_satellite_observation_mask"] = (
        daily.landsat_observation_mask.eq(1)
        | daily.sentinel_observation_mask.eq(1)
        | daily.swot_observation_mask.eq(1)
    ).astype(int)

    sword = pd.read_csv(SWORD_PATH)
    match = sword.loc[
        sword.station_id.astype(str).str.zfill(8).eq(STATION_ID)
        & sword.sword_reach_id.astype(str).eq(REACH_ID)
    ]
    if len(match) != 1:
        raise ValueError(f"Expected one SWORD match for {STATION_ID}/{REACH_ID}, found {len(match)}")
    match = match.iloc[0]
    static = pd.DataFrame(
        [
            {
                "station_id": STATION_ID,
                "reach_id": REACH_ID,
                "station_longitude": float(match.longitude),
                "station_latitude": float(match.latitude),
                "station_upstream_area_km2": float(match.station_upstream_area_km2),
                "sword_upstream_area_km2": float(match.sword_facc_km2),
                "sword_to_station_area_ratio": float(match.area_ratio_sword_to_station),
                "sword_prior_width_m": float(match.width_m),
                "sword_prior_width_std_m": float(match.width_std_m),
                "sword_slope_m_per_km": float(match.slope_m_per_km),
                "natural_reach_flag": int(bool(match.natural_reach_candidate)),
                "reservoir_flag": int(match.reservoir_flag),
            }
        ]
    )

    landsat_q_pairs = same_day_pair_count(
        daily, "landsat_observation_mask", "discharge_m3s"
    )
    sentinel_q_pairs = same_day_pair_count(
        daily, "sentinel_observation_mask", "discharge_m3s"
    )
    swot_q_pairs = same_day_pair_count(daily, "swot_observation_mask", "discharge_m3s")
    swot_stage_pairs = same_day_pair_count(daily, "swot_observation_mask", "stage_m")
    discharge_years = int(daily.loc[daily.discharge_m3s.notna(), "date"].dt.year.nunique())
    # Predeclared minimums prevent starting a high-capacity GNN on a handful of labels.
    supervised_ready = bool(
        (landsat_q_pairs + sentinel_q_pairs + swot_q_pairs) >= 30
        and swot_stage_pairs >= 10
        and discharge_years >= 2
    )

    dynamic_feature_columns = [
        "landsat_width_m",
        "landsat_width_iqr_m",
        "landsat_valid_transects",
        "landsat_scene_cloud_percent",
        "sentinel_width_m",
        "sentinel_width_iqr_m",
        "sentinel_valid_transects",
        "sentinel_scene_cloud_percent",
        "swot_wse_m",
        "swot_wse_uncertainty_m",
        "swot_track_demeaned_wse_m",
        "swot_reach_width_m",
        "swot_width_uncertainty_m",
        "swot_track_demeaned_width_m",
        "swot_slope_m_per_m",
        "swot_slope_uncertainty_m_per_m",
        "swot_cross_track_distance_m",
        "swot_observed_node_fraction",
        "swot_good_nodes",
        "swot_track_west_far",
        "swot_track_near",
        "swot_track_east_far",
        "landsat_observation_mask",
        "sentinel_observation_mask",
        "swot_observation_mask",
    ]
    summary = {
        "status": "model_inputs_prepared_supervised_training_blocked"
        if not supervised_ready
        else "model_inputs_prepared_supervised_training_ready",
        "station_id": STATION_ID,
        "sword_reach_id": REACH_ID,
        "daily_rows": int(len(daily)),
        "date_range": [daily.date.min().date().isoformat(), daily.date.max().date().isoformat()],
        "recent_landsat_observation_days": int(daily.landsat_observation_mask.sum()),
        "sentinel_observation_days": int(daily.sentinel_observation_mask.sum()),
        "swot_observation_days": int(daily.swot_observation_mask.sum()),
        "ground_discharge_days": int(daily.discharge_label_mask.sum()),
        "ground_stage_days": int(daily.stage_label_mask.sum()),
        "same_day_pairs": {
            "landsat_discharge": landsat_q_pairs,
            "sentinel_discharge": sentinel_q_pairs,
            "swot_discharge": swot_q_pairs,
            "swot_stage": swot_stage_pairs,
        },
        "minimum_supervised_gate": {
            "total_satellite_discharge_pairs": 30,
            "swot_stage_pairs": 10,
            "discharge_years": 2,
        },
        "supervised_training_ready": supervised_ready,
        "dynamic_feature_columns": dynamic_feature_columns,
        "missing_value_policy": (
            "No temporal interpolation of satellite geometry. NaN values remain missing and "
            "observation masks are explicit."
        ),
        "physics_policy": (
            "Geometry variables are auxiliary inputs, not discharge references. Discharge loss "
            "and discharge physics anchoring remain disabled until ground labels are available."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    REPORT_OUTPUT.mkdir(parents=True, exist_ok=True)
    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_PATH.exists():
        pd.DataFrame(
            columns=[
                "date",
                "discharge_m3s",
                "stage_m",
                "rating_curve_version",
                "quality_code",
                "change_note",
            ]
        ).to_csv(TEMPLATE_PATH, index=False)
    daily.to_csv(OUTPUT / "byblk_natural_reach_daily_features.csv", index=False)
    static.to_csv(OUTPUT / "byblk_natural_reach_static_features.csv", index=False)
    (OUTPUT / "byblk_natural_reach_gnn_readiness.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (REPORT_OUTPUT / "natural_reach_gnn_input_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
