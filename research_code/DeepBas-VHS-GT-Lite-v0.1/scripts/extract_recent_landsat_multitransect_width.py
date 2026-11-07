from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
from shapely.geometry import Point

from extract_landsat_multitransect_width import (
    ALONG_REACH_OFFSETS_M,
    MAX_WIDTH_IQR_M,
    MIN_VALID_TRANSECTS,
    measure_item,
)
from extract_landsat_river_width import MATCHES, SWORD


STATION_ID = "00705600"
YEARS = [2023, 2024, 2025]
MAX_SCENE_CLOUD = 25.0
MIN_SCENE_GAP_DAYS = 16
OUTPUT = Path("data/processed/natural_width/landsat_recent_byblk_multitransect")


def select_recent_items(items: list) -> list:
    # Reuse the established label-free selector while making the thresholds explicit here.
    selected = []
    for item in sorted(items, key=lambda value: value.datetime):
        cloud = float(item.properties.get("eo:cloud_cover", 100.0))
        if cloud > MAX_SCENE_CLOUD:
            continue
        if not selected:
            selected.append(item)
            continue
        gap = (item.datetime.date() - selected[-1].datetime.date()).days
        if gap >= MIN_SCENE_GAP_DAYS:
            selected.append(item)
        elif cloud < float(selected[-1].properties.get("eo:cloud_cover", 100.0)):
            selected[-1] = item
    return selected


def main() -> None:
    match = pd.read_csv(MATCHES, dtype={"station_id": str})
    match = match.loc[match.station_id.eq(STATION_ID)].iloc[0]
    reach = gpd.read_file(SWORD)
    reach = reach.loc[reach.reach_id.astype("int64").eq(int(match.sword_reach_id))].copy()
    station = Point(float(match.longitude), float(match.latitude))
    bbox = [station.x - 0.025, station.y - 0.025, station.x + 0.025, station.y + 0.025]
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )

    selected = []
    inventory = []
    for year in YEARS:
        found = list(
            catalog.search(
                collections=["landsat-c2-l2"],
                bbox=bbox,
                datetime=f"{year}-01-01/{year}-12-31",
            ).items()
        )
        year_selected = select_recent_items(found)
        selected.extend(year_selected)
        inventory.append(
            {
                "year": year,
                "catalog_items": len(found),
                "selected_items": len(year_selected),
            }
        )

    rows = []
    for number, item in enumerate(selected, start=1):
        try:
            row = measure_item(item, reach, station)
        except Exception as error:
            row = {
                "date": item.datetime.date().isoformat(),
                "item_id": item.id,
                "platform": item.properties.get("platform"),
                "scene_cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
                "measurement_status": f"read_error:{type(error).__name__}",
                "error_message": str(error),
            }
        rows.append(row)
        print(f"[{number}/{len(selected)}] {row['date']} {row['measurement_status']}")

    frame = pd.DataFrame(rows).sort_values("date")
    frame["selection_used_discharge"] = False
    accepted = frame.measurement_status.eq("accepted")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "landsat_recent_multitransect_width_measurements.csv", index=False)
    summary = {
        "status": "completed_recent_landsat_multitransect_extraction",
        "station_id": STATION_ID,
        "sword_reach_id": int(match.sword_reach_id),
        "years": YEARS,
        "maximum_scene_cloud_percent": MAX_SCENE_CLOUD,
        "minimum_scene_gap_days": MIN_SCENE_GAP_DAYS,
        "scene_selection_used_discharge": False,
        "along_reach_offsets_m": ALONG_REACH_OFFSETS_M,
        "minimum_valid_transects": MIN_VALID_TRANSECTS,
        "maximum_width_iqr_m": MAX_WIDTH_IQR_M,
        "catalog_inventory": inventory,
        "selected_scenes": int(len(frame)),
        "accepted_scenes": int(accepted.sum()),
        "accepted_by_year": {
            str(year): int((accepted & pd.to_datetime(frame.date).dt.year.eq(year)).sum())
            for year in YEARS
        },
        "accepted_width_median": (
            float(frame.loc[accepted, "width_m"].median()) if accepted.any() else None
        ),
        "accepted_width_iqr_median": (
            float(frame.loc[accepted, "width_iqr_m"].median()) if accepted.any() else None
        ),
    }
    (OUTPUT / "landsat_recent_width_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
