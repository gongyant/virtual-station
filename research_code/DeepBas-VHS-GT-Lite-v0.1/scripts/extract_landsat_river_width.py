from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from rasterio.windows import from_bounds
from scipy.ndimage import map_coordinates
from shapely.geometry import Point


STATION_ID = "00705600"
YEARS = [2000, 2001, 2005]
MAX_SCENE_CLOUD = 25.0
MIN_SCENE_GAP_DAYS = 0
HALF_TRANSECT_M = 600.0
SAMPLE_SPACING_M = 5.0
OUTPUT = Path("data/processed/natural_width/landsat_byblk")
MATCHES = Path("data/processed/natural_width/station_sword_width_matches.csv")
SWORD = Path("data/raw/sword_v2/hb48/as_sword_reaches_hb48_v2.shp")


def select_temporally_spaced(items: list, gap_days: int) -> list:
    selected = []
    for item in sorted(items, key=lambda value: value.datetime):
        cloud = float(item.properties.get("eo:cloud_cover", 100.0))
        if cloud > MAX_SCENE_CLOUD:
            continue
        if not selected:
            selected.append(item)
            continue
        gap = (item.datetime.date() - selected[-1].datetime.date()).days
        if gap >= gap_days:
            selected.append(item)
        elif cloud < float(selected[-1].properties.get("eo:cloud_cover", 100.0)):
            selected[-1] = item
    return selected


def water_run_near_center(
    water: np.ndarray, valid: np.ndarray, offsets_m: np.ndarray
) -> tuple[float, float, int] | None:
    runs = []
    start = None
    for index, value in enumerate(water):
        if value and start is None:
            start = index
        if start is not None and (not value or index == len(water) - 1):
            end = index if value and index == len(water) - 1 else index - 1
            midpoint = 0.5 * (offsets_m[start] + offsets_m[end])
            width = offsets_m[end] - offsets_m[start] + SAMPLE_SPACING_M
            runs.append((abs(midpoint), width, midpoint, start, end))
            start = None
    nearby = [run for run in runs if run[0] <= 180.0]
    if not nearby:
        return None
    _, width, midpoint, start, end = min(nearby, key=lambda run: (run[0], -run[1]))
    valid_fraction = float(valid[start : end + 1].mean())
    return float(width), float(midpoint), int(end - start + 1) if valid_fraction > 0 else None


def measure_item(item, reach: gpd.GeoDataFrame, station: Point) -> dict:
    green_url = item.assets["green"].href
    swir_url = item.assets["swir16"].href
    qa_url = item.assets["qa_pixel"].href
    with rasterio.open(green_url) as green_source:
        crs = green_source.crs
        reach_projected = reach.to_crs(crs).geometry.iloc[0]
        station_projected = gpd.GeoSeries([station], crs="EPSG:4326").to_crs(crs).iloc[0]
        along = reach_projected.project(station_projected)
        center = reach_projected.interpolate(along)
        before = reach_projected.interpolate(max(0.0, along - 90.0))
        after = reach_projected.interpolate(min(reach_projected.length, along + 90.0))
        tangent = np.array([after.x - before.x, after.y - before.y], dtype=float)
        tangent /= np.linalg.norm(tangent)
        perpendicular = np.array([-tangent[1], tangent[0]])

        margin = HALF_TRANSECT_M + 120.0
        window = from_bounds(
            center.x - margin,
            center.y - margin,
            center.x + margin,
            center.y + margin,
            green_source.transform,
        ).round_offsets().round_lengths()
        green = green_source.read(1, window=window)
        transform = green_source.window_transform(window)
        pixel_size_m = float(abs(green_source.transform.a))
    with rasterio.open(swir_url) as source:
        swir = source.read(1, window=window)
    with rasterio.open(qa_url) as source:
        qa = source.read(1, window=window)

    green_reflectance = green.astype(float) * 0.0000275 - 0.2
    swir_reflectance = swir.astype(float) * 0.0000275 - 0.2
    denominator = green_reflectance + swir_reflectance
    mndwi = np.divide(
        green_reflectance - swir_reflectance,
        denominator,
        out=np.full_like(denominator, np.nan),
        where=np.abs(denominator) > 1e-8,
    )
    invalid_bits = sum(1 << bit for bit in [0, 1, 2, 3, 4, 5])
    clear = ((qa & invalid_bits) == 0) & (green > 0) & (swir > 0)

    offsets = np.arange(
        -HALF_TRANSECT_M, HALF_TRANSECT_M + SAMPLE_SPACING_M, SAMPLE_SPACING_M
    )
    xs = center.x + offsets * perpendicular[0]
    ys = center.y + offsets * perpendicular[1]
    cols, rows = (~transform) * (xs, ys)
    coordinates = np.vstack([rows, cols])
    # Bilinear sampling gives a sub-pixel shoreline crossing estimate while the
    # QA mask remains nearest-neighbour categorical data.
    sampled_mndwi = map_coordinates(mndwi, coordinates, order=1, mode="constant", cval=np.nan)
    sampled_clear = map_coordinates(
        clear.astype(np.uint8), coordinates, order=0, mode="constant", cval=0
    ).astype(bool)
    sampled_water = (sampled_mndwi > 0.0) & sampled_clear
    result = water_run_near_center(sampled_water, sampled_clear, offsets)
    central = np.abs(offsets) <= 300.0
    central_clear_fraction = float(sampled_clear[central].mean())
    if result is None:
        width_m = center_offset_m = np.nan
        water_samples = 0
        status = "no_water_run_near_center"
    else:
        width_m, center_offset_m, water_samples = result
        status = "accepted" if central_clear_fraction >= 0.80 else "rejected_low_clear_fraction"
        if width_m < SAMPLE_SPACING_M or width_m > 500.0:
            status = "rejected_implausible_width"

    return {
        "date": item.datetime.date().isoformat(),
        "item_id": item.id,
        "platform": item.properties.get("platform"),
        "scene_cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
        "wrs_path": item.properties.get("landsat:wrs_path"),
        "wrs_row": item.properties.get("landsat:wrs_row"),
        "pixel_size_m": pixel_size_m,
        "mndwi_threshold": 0.0,
        "central_clear_fraction": central_clear_fraction,
        "width_m": width_m,
        "width_center_offset_m": center_offset_m,
        "water_samples": water_samples,
        "measurement_status": status,
    }


def main() -> None:
    match = pd.read_csv(MATCHES, dtype={"station_id": str})
    match = match.loc[match.station_id == STATION_ID].iloc[0]
    if not bool(match.match_accepted) or not bool(match.natural_reach_candidate):
        raise ValueError("BYBLK did not pass the static natural-reach match gate")
    reach = gpd.read_file(SWORD)
    reach = reach.loc[reach.reach_id.astype("int64") == int(match.sword_reach_id)].copy()
    if len(reach) != 1:
        raise ValueError("Matched SWORD reach is not unique")
    station = Point(float(match.longitude), float(match.latitude))
    bbox = [station.x - 0.025, station.y - 0.025, station.x + 0.025, station.y + 0.025]

    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    selected_items = []
    inventory_rows = []
    for year in YEARS:
        items = list(
            catalog.search(
                collections=["landsat-c2-l2"],
                bbox=bbox,
                datetime=f"{year}-01-01/{year}-12-31",
            ).items()
        )
        selected = select_temporally_spaced(items, MIN_SCENE_GAP_DAYS)
        selected_items.extend(selected)
        inventory_rows.extend(
            {
                "year": year,
                "item_id": item.id,
                "date": item.datetime.date().isoformat(),
                "cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
                "selected_without_discharge": item in selected,
            }
            for item in items
        )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(inventory_rows).sort_values(["date", "cloud_percent"]).to_csv(
        OUTPUT / "landsat_scene_inventory.csv", index=False
    )
    measurements = []
    for number, item in enumerate(selected_items, start=1):
        try:
            row = measure_item(item, reach, station)
        except Exception as error:
            row = {
                "date": item.datetime.date().isoformat(),
                "item_id": item.id,
                "platform": item.properties.get("platform"),
                "scene_cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
                "measurement_status": f"read_error:{type(error).__name__}",
            }
        measurements.append(row)
        print(f"[{number}/{len(selected_items)}] {row['date']} {row['measurement_status']}")
    measurement_frame = pd.DataFrame(measurements).sort_values("date")
    measurement_frame.to_csv(OUTPUT / "landsat_width_measurements.csv", index=False)

    accepted = measurement_frame.measurement_status.eq("accepted")
    summary = {
        "status": "completed_landsat_width_extraction",
        "station_id": STATION_ID,
        "sword_reach_id": int(match.sword_reach_id),
        "static_sword_width_m": float(match.width_m),
        "years": YEARS,
        "scene_selection_used_discharge": False,
        "selected_scenes": int(len(measurement_frame)),
        "accepted_widths": int(accepted.sum()),
        "accepted_by_year": {
            str(year): int(
                (accepted & pd.to_datetime(measurement_frame.date).dt.year.eq(year)).sum()
            )
            for year in YEARS
        },
        "method": {
            "sensor_product": "Landsat Collection 2 Level-2 surface reflectance",
            "water_index": "MNDWI=(green-SWIR1)/(green+SWIR1)",
            "threshold": 0.0,
            "cloud_mask": "QA_PIXEL bits 0-5 removed",
            "transect": "perpendicular to matched SWORD centerline",
            "sample_spacing_m": SAMPLE_SPACING_M,
            "native_pixel_m": 30,
            "reflectance_sampling": "bilinear_subpixel_transect",
        },
        "limitations": (
            "A nominal 67 m channel is only about two Landsat pixels wide. Widths are a "
            "screening product and require visual/cross-section validation before a formal "
            "hydraulic inversion claim."
        ),
        "created_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    (OUTPUT / "landsat_width_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
