from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from rasterio.windows import from_bounds
from shapely.geometry import Point

from extract_landsat_multitransect_width import (
    ALONG_REACH_OFFSETS_M,
    MAX_WIDTH_IQR_M,
    MIN_VALID_TRANSECTS,
    sample_transect,
)
from extract_landsat_river_width import MATCHES, STATION_ID, SWORD


YEARS = [2023, 2024, 2025]
MAX_CLOUD = 20.0
MIN_GAP_DAYS = 20
OUTPUT = Path("data/processed/natural_width/sentinel2_byblk_multitransect")
LANDSAT_MULTI = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)


def select_scenes(items: list) -> list:
    selected = []
    for item in sorted(items, key=lambda value: value.datetime):
        cloud = float(item.properties.get("eo:cloud_cover", 100.0))
        if cloud > MAX_CLOUD:
            continue
        if not selected or (item.datetime.date() - selected[-1].datetime.date()).days >= MIN_GAP_DAYS:
            selected.append(item)
        elif cloud < float(selected[-1].properties.get("eo:cloud_cover", 100.0)):
            selected[-1] = item
    return selected


def measure(item, reach: gpd.GeoDataFrame, station: Point) -> dict:
    with rasterio.open(item.assets["B03"].href) as source:
        crs = source.crs
        line = reach.to_crs(crs).geometry.iloc[0]
        station_point = gpd.GeoSeries([station], crs="EPSG:4326").to_crs(crs).iloc[0]
        station_along = line.project(station_point)
        along_values = [
            min(max(station_along + offset, 0.0), line.length)
            for offset in ALONG_REACH_OFFSETS_M
        ]
        centers = [line.interpolate(value) for value in along_values]
        margin = 750.0
        window = from_bounds(
            min(point.x for point in centers) - margin,
            min(point.y for point in centers) - margin,
            max(point.x for point in centers) + margin,
            max(point.y for point in centers) + margin,
            source.transform,
        ).round_offsets().round_lengths()
        green = source.read(1, window=window)
        transform = source.window_transform(window)
        shape = green.shape
    with rasterio.open(item.assets["B08"].href) as source:
        nir = source.read(1, window=window)
    scl = np.zeros(shape, dtype=np.uint8)
    with rasterio.open(item.assets["SCL"].href) as source:
        reproject(
            source=rasterio.band(source, 1),
            destination=scl,
            src_transform=source.transform,
            src_crs=source.crs,
            dst_transform=transform,
            dst_crs=crs,
            resampling=Resampling.nearest,
        )
    denominator = green.astype(float) + nir.astype(float)
    ndwi = np.divide(
        green.astype(float) - nir.astype(float),
        denominator,
        out=np.full(shape, np.nan, dtype=float),
        where=denominator > 0,
    )
    rejected_classes = np.isin(scl, [0, 1, 3, 8, 9, 10, 11])
    clear = (~rejected_classes) & (green > 0) & (nir > 0)
    transects = [
        {
            "along_offset_m": offset,
            **sample_transect(line, along, transform, ndwi, clear),
        }
        for offset, along in zip(ALONG_REACH_OFFSETS_M, along_values)
    ]
    valid = [value for value in transects if value["accepted"]]
    widths = np.asarray([value["width_m"] for value in valid], dtype=float)
    median = float(np.median(widths)) if len(widths) else np.nan
    iqr = (
        float(np.percentile(widths, 75) - np.percentile(widths, 25))
        if len(widths)
        else np.nan
    )
    if len(valid) < MIN_VALID_TRANSECTS:
        status = "rejected_too_few_valid_transects"
    elif iqr > MAX_WIDTH_IQR_M:
        status = "rejected_high_cross_section_dispersion"
    else:
        status = "accepted"
    return {
        "date": item.datetime.date().isoformat(),
        "item_id": item.id,
        "platform": item.properties.get("platform"),
        "scene_cloud_percent": float(item.properties.get("eo:cloud_cover", np.nan)),
        "valid_transects": len(valid),
        "width_m": median,
        "width_iqr_m": iqr,
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
                collections=["sentinel-2-l2a"],
                bbox=bbox,
                datetime=f"{year}-04-01/{year}-10-31",
                query={"eo:cloud_cover": {"lt": MAX_CLOUD}},
            ).items()
        )
        items.extend(select_scenes(found))
    rows = []
    for number, item in enumerate(items, start=1):
        try:
            row = measure(item, reach, station)
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
    frame.to_csv(OUTPUT / "sentinel2_multitransect_width_measurements.csv", index=False)
    accepted = frame.loc[frame.measurement_status == "accepted"]
    landsat = pd.read_csv(LANDSAT_MULTI)
    landsat = landsat.loc[landsat.measurement_status == "accepted"]
    summary = {
        "status": "completed_sentinel2_resolution_supplement",
        "station_id": STATION_ID,
        "years": YEARS,
        "selected_scenes": int(len(frame)),
        "accepted_scenes": int(len(accepted)),
        "scene_selection_used_discharge": False,
        "flow_validation_allowed": False,
        "reason_no_flow_validation": "No contemporaneous observed BYBLK discharge is available.",
        "method": {
            "green_band": "B03 10 m",
            "nir_band": "B08 10 m",
            "water_index": "NDWI=(green-NIR)/(green+NIR), threshold 0",
            "quality_mask": "Sentinel-2 SCL cloud, cloud-shadow, cirrus, snow and defective classes",
            "transects": 7,
        },
        "width_comparison": {
            "sentinel2_median_m": float(accepted.width_m.median()) if len(accepted) else None,
            "sentinel2_within_scene_iqr_median": float(accepted.width_iqr_m.median()) if len(accepted) else None,
            "historical_landsat_median_m": float(landsat.width_m.median()),
            "static_sword_reach_mean_m": float(match.width_m),
        },
        "interpretation": (
            "Sentinel-2 supplies a finer-resolution morphology check only. Without same-date "
            "discharge it must not be reported as a width-to-flow validation."
        ),
    }
    (OUTPUT / "sentinel2_width_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
