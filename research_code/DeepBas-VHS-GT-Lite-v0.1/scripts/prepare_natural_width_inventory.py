from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point


NODES = Path("data/processed/nodes.csv")
SWORD_ROOT = Path("data/raw/sword_v2")
OUTPUT = Path("data/processed/natural_width")
MAX_DISTANCE_KM = 10.0
MIN_AREA_RATIO = 0.2
MAX_AREA_RATIO = 5.0


def load_sword() -> gpd.GeoDataFrame:
    paths = sorted(SWORD_ROOT.glob("hb4[678]/*reaches*.shp"))
    if not paths:
        raise FileNotFoundError("SWORD hb46/hb47/hb48 shapefiles are missing")
    frames = []
    for path in paths:
        frame = gpd.read_file(path)
        frame["sword_partition"] = path.parent.name
        frames.append(frame)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs="EPSG:4326")


def local_utm_epsg(longitude: float, latitude: float) -> int:
    zone = int((longitude + 180.0) // 6.0) + 1
    return (32600 if latitude >= 0 else 32700) + zone


def main() -> None:
    nodes = pd.read_csv(NODES, dtype={"station_id": str})
    nodes = nodes.dropna(subset=["longitude", "latitude", "UP_AREA"]).copy()
    sword = load_sword()
    candidate_rows: list[dict] = []
    selected_rows: list[dict] = []

    for _, station in nodes.iterrows():
        epsg = local_utm_epsg(float(station.longitude), float(station.latitude))
        projected = sword.to_crs(epsg=epsg)
        point = gpd.GeoSeries(
            [Point(float(station.longitude), float(station.latitude))], crs="EPSG:4326"
        ).to_crs(epsg=epsg).iloc[0]
        distance_km = projected.geometry.distance(point) / 1000.0
        nearest_indices = distance_km.nsmallest(10).index
        station_candidates = []
        for rank, index in enumerate(nearest_indices, start=1):
            reach = sword.loc[index]
            area_ratio = float(reach.facc) / float(station.UP_AREA)
            area_log_error = abs(float(np.log(max(area_ratio, 1e-12))))
            row = {
                "station_id": station.station_id,
                "station_name": station.station_name,
                "longitude": float(station.longitude),
                "latitude": float(station.latitude),
                "reservoir_flag": int(station.reservoir_flag),
                "station_upstream_area_km2": float(station.UP_AREA),
                "distance_rank": rank,
                "sword_partition": reach.sword_partition,
                "sword_reach_id": int(reach.reach_id),
                "distance_km": float(distance_km.loc[index]),
                "sword_facc_km2": float(reach.facc),
                "area_ratio_sword_to_station": area_ratio,
                "area_log_error": area_log_error,
                "selection_score": float(distance_km.loc[index]) + 2.0 * area_log_error,
                "width_m": float(reach.width),
                "width_std_m": float(np.sqrt(max(float(reach.width_var), 0.0))),
                "max_width_m": float(reach.max_width),
                "slope_m_per_km": float(reach.slope),
                "obstruction_type": int(reach.obstr_type),
                "lake_flag": int(reach.lakeflag),
                "sword_type": int(reach.type),
            }
            candidate_rows.append(row)
            station_candidates.append(row)

        eligible = [
            row
            for row in station_candidates
            if row["distance_km"] <= MAX_DISTANCE_KM
            and MIN_AREA_RATIO <= row["area_ratio_sword_to_station"] <= MAX_AREA_RATIO
        ]
        selected = min(
            eligible or station_candidates, key=lambda row: row["selection_score"]
        ).copy()
        selected["match_accepted"] = bool(eligible)
        selected["quality_reason"] = (
            "distance_and_area_pass"
            if eligible
            else "provisional_only_no_candidate_passes_distance_and_area"
        )
        selected["natural_reach_candidate"] = bool(
            selected["match_accepted"]
            and selected["reservoir_flag"] == 0
            and selected["obstruction_type"] == 0
            and selected["lake_flag"] == 0
        )
        selected_rows.append(selected)

    candidates = pd.DataFrame(candidate_rows)
    selected = pd.DataFrame(selected_rows).sort_values(
        ["natural_reach_candidate", "distance_km"], ascending=[False, True]
    )
    byblk = selected.loc[selected.station_id == "00705600"]
    summary = {
        "status": "completed_static_sword_width_inventory",
        "source": {
            "dataset": "SWOT River Database (SWORD) v2",
            "doi": "10.5281/zenodo.5643392",
            "partitions": sorted(sword.sword_partition.unique().tolist()),
            "static_width_is_not_a_width_time_series": True,
        },
        "selection_without_discharge_labels": True,
        "quality_thresholds": {
            "maximum_distance_km": MAX_DISTANCE_KM,
            "accepted_area_ratio": [MIN_AREA_RATIO, MAX_AREA_RATIO],
            "natural_requires_no_obstruction_and_no_lake_flag": True,
        },
        "stations_checked": int(len(selected)),
        "accepted_matches": int(selected.match_accepted.sum()),
        "natural_reach_candidates": int(selected.natural_reach_candidate.sum()),
        "byblk_match": byblk.iloc[0].to_dict() if len(byblk) else None,
        "experiment_readiness": {
            "static_hydraulic_geometry": "ready_for_feasibility_diagnostic",
            "dynamic_width_to_discharge_calibration": "blocked_by_missing_width_time_series",
            "required_next_input": (
                "Landsat-derived width observations contemporaneous with BYBLK daily flow, "
                "plus cross-section or stage samples for hydraulic interpretation."
            ),
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(OUTPUT / "station_sword_width_candidates.csv", index=False)
    selected.to_csv(OUTPUT / "station_sword_width_matches.csv", index=False)
    (OUTPUT / "natural_width_inventory_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
