from __future__ import annotations

import json
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

from extract_landsat_river_width import (
    HALF_TRANSECT_M,
    MATCHES,
    MAX_SCENE_CLOUD,
    MIN_SCENE_GAP_DAYS,
    SAMPLE_SPACING_M,
    STATION_ID,
    SWORD,
    YEARS,
    select_temporally_spaced,
    water_run_near_center,
)


ALONG_REACH_OFFSETS_M = [-300.0, -200.0, -100.0, 0.0, 100.0, 200.0, 300.0]
MIN_VALID_TRANSECTS = 4
MAX_WIDTH_IQR_M = 60.0
OUTPUT = Path("data/processed/natural_width/landsat_byblk_multitransect")


def sample_transect(
    line,
    along: float,
    transform,
    mndwi: np.ndarray,
    clear: np.ndarray,
) -> dict:
    center = line.interpolate(along)
    before = line.interpolate(max(0.0, along - 90.0))
    after = line.interpolate(min(line.length, along + 90.0))
    tangent = np.array([after.x - before.x, after.y - before.y], dtype=float)
    tangent /= np.linalg.norm(tangent)
    perpendicular = np.array([-tangent[1], tangent[0]])
    offsets = np.arange(
        -HALF_TRANSECT_M, HALF_TRANSECT_M + SAMPLE_SPACING_M, SAMPLE_SPACING_M
    )
    xs = center.x + offsets * perpendicular[0]
    ys = center.y + offsets * perpendicular[1]
    cols, rows = (~transform) * (xs, ys)
    coordinates = np.vstack([rows, cols])
    sampled_mndwi = map_coordinates(
        mndwi, coordinates, order=1, mode="constant", cval=np.nan
    )
    sampled_clear = map_coordinates(
        clear.astype(np.uint8), coordinates, order=0, mode="constant", cval=0
    ).astype(bool)
    result = water_run_near_center(
        (sampled_mndwi > 0.0) & sampled_clear, sampled_clear, offsets
    )
    central_clear = float(sampled_clear[np.abs(offsets) <= 300.0].mean())
    if result is None:
        return {"width_m": np.nan, "clear_fraction": central_clear, "accepted": False}
    width_m, center_offset_m, _ = result
    accepted = bool(central_clear >= 0.80 and SAMPLE_SPACING_M <= width_m <= 500.0)
    return {
        "width_m": width_m,
        "center_offset_m": center_offset_m,
        "clear_fraction": central_clear,
        "accepted": accepted,
    }


def measure_item(item, reach: gpd.GeoDataFrame, station: Point) -> dict:
    with rasterio.open(item.assets["green"].href) as source:
        crs = source.crs
        line = reach.to_crs(crs).geometry.iloc[0]
        station_point = gpd.GeoSeries([station], crs="EPSG:4326").to_crs(crs).iloc[0]
        station_along = line.project(station_point)
        along_values = [
            min(max(station_along + offset, 0.0), line.length)
            for offset in ALONG_REACH_OFFSETS_M
        ]
        centers = [line.interpolate(value) for value in along_values]
        margin = HALF_TRANSECT_M + 150.0
        window = from_bounds(
            min(point.x for point in centers) - margin,
            min(point.y for point in centers) - margin,
            max(point.x for point in centers) + margin,
            max(point.y for point in centers) + margin,
            source.transform,
        ).round_offsets().round_lengths()
        green = source.read(1, window=window)
        transform = source.window_transform(window)
    with rasterio.open(item.assets["swir16"].href) as source:
        swir = source.read(1, window=window)
    with rasterio.open(item.assets["qa_pixel"].href) as source:
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
    transects = [
        {
            "along_offset_m": offset,
            **sample_transect(line, along, transform, mndwi, clear),
        }
        for offset, along in zip(ALONG_REACH_OFFSETS_M, along_values)
    ]
    valid = [value for value in transects if value["accepted"]]
    widths = np.array([value["width_m"] for value in valid], dtype=float)
    width_median = float(np.median(widths)) if len(widths) else np.nan
    width_iqr = (
        float(np.percentile(widths, 75) - np.percentile(widths, 25))
        if len(widths)
        else np.nan
    )
    accepted = bool(len(valid) >= MIN_VALID_TRANSECTS and width_iqr <= MAX_WIDTH_IQR_M)
    if len(valid) < MIN_VALID_TRANSECTS:
        status = "rejected_too_few_valid_transects"
    elif width_iqr > MAX_WIDTH_IQR_M:
        status = "rejected_high_cross_section_dispersion"
    else:
        status = "accepted"
    return {
        "date": item.datetime.date().isoformat(),
        "item_id": item.id,
        "platform": item.properties.get("platform"),
        "scene_cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
        "valid_transects": len(valid),
        "total_transects": len(transects),
        "width_m": width_median,
        "width_iqr_m": width_iqr,
        "minimum_width_m": float(widths.min()) if len(widths) else np.nan,
        "maximum_width_m": float(widths.max()) if len(widths) else np.nan,
        "measurement_status": status,
        "transect_details_json": json.dumps(transects, ensure_ascii=False),
    }


def main() -> None:
    match = pd.read_csv(MATCHES, dtype={"station_id": str})
    match = match.loc[match.station_id == STATION_ID].iloc[0]
    reach = gpd.read_file(SWORD)
    reach = reach.loc[reach.reach_id.astype("int64") == int(match.sword_reach_id)].copy()
    station = Point(float(match.longitude), float(match.latitude))
    bbox = [station.x - 0.025, station.y - 0.025, station.x + 0.025, station.y + 0.025]
    catalog = pystac_client.Client.open(
        "https://planetarycomputer.microsoft.com/api/stac/v1",
        modifier=planetary_computer.sign_inplace,
    )
    items = []
    for year in YEARS:
        found = list(
            catalog.search(
                collections=["landsat-c2-l2"],
                bbox=bbox,
                datetime=f"{year}-01-01/{year}-12-31",
            ).items()
        )
        items.extend(select_temporally_spaced(found, MIN_SCENE_GAP_DAYS))

    rows = []
    for number, item in enumerate(items, start=1):
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
        rows.append(row)
        print(f"[{number}/{len(items)}] {row['date']} {row['measurement_status']}")
    frame = pd.DataFrame(rows).sort_values("date")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUTPUT / "landsat_multitransect_width_measurements.csv", index=False)
    accepted = frame.measurement_status.eq("accepted")
    summary = {
        "status": "completed_multitransect_width_supplement",
        "station_id": STATION_ID,
        "sword_reach_id": int(match.sword_reach_id),
        "along_reach_offsets_m": ALONG_REACH_OFFSETS_M,
        "minimum_valid_transects": MIN_VALID_TRANSECTS,
        "maximum_width_iqr_m": MAX_WIDTH_IQR_M,
        "scene_selection_used_discharge": False,
        "selected_scenes": int(len(frame)),
        "accepted_scenes": int(accepted.sum()),
        "accepted_by_year": {
            str(year): int((accepted & pd.to_datetime(frame.date).dt.year.eq(year)).sum())
            for year in YEARS
        },
        "accepted_width_median": float(frame.loc[accepted, "width_m"].median()),
        "accepted_width_iqr_median": float(frame.loc[accepted, "width_iqr_m"].median()),
    }
    (OUTPUT / "multitransect_width_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
