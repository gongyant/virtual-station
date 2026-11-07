from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import planetary_computer
import pystac_client
import rasterio
from pyproj import Transformer
from rasterio.transform import rowcol
from rasterio.windows import Window, from_bounds


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/rs_w0"
PREVIEWS = OUT / "previews"
DATA_ROOT = ROOT / "data/remote_sensing/landsat"
MEASUREMENTS = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/discharge_measurements_2011_canonical.csv"
NODES = ROOT / "data/processed/nodes.csv"
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
COLLECTION = "landsat-c2-l2"
AOI_HALF_SIZE_M = 2500.0
LOCAL_QA_RADIUS_M = 120.0
MAX_TIME_DIFFERENCE_DAYS = 8
PRIMARY_SCENE_CLOUD_PERCENT = 20.0
FALLBACK_SCENE_CLOUD_PERCENT = 40.0
STATIONS = {
    "00705600": {"code": "BYBLK", "name": "巴音布鲁克"},
    "00705700": {"code": "DSK", "name": "大山口"},
}
CANONICAL_ASSETS = {
    "blue": "blue",
    "green": "green",
    "red": "red",
    "nir": "nir08",
    "swir1": "swir16",
    "qa_pixel": "qa_pixel",
}
FROZEN_D11_HASHES = {
    "protocol_frozen.json": "a79d51b293718d027caf2b697f3d1f0ddc69b8686196b842c157e02529a8e296",
    "result.json": "563ca32744f4121705bae40c0d53d26a30bad6f8431ab055ba1f1ccb1436e599",
    "outer_month_predictions.csv": "b6f2a0ebc40363f6e9f3eb4a5f995e3fa05dc6d4863fe4bd1ddd6bfa5539a73d",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unsign_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def assert_prior_stages_unchanged() -> None:
    d11 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d11_geometry_cross_validation"
    for name, expected in FROZEN_D11_HASHES.items():
        actual = sha256(d11 / name)
        if actual != expected:
            raise RuntimeError(f"Frozen D11 artifact changed: {name}: {actual}")


def load_canonical_stations() -> pd.DataFrame:
    nodes = pd.read_csv(NODES, dtype={"station_id": str})
    nodes["station_id"] = nodes.station_id.str.zfill(8)
    selected = nodes.loc[nodes.station_id.isin(STATIONS)].copy()
    if set(selected.station_id) != set(STATIONS) or len(selected) != 2:
        raise RuntimeError("Expected exactly one canonical node for BYBLK and DSK")
    if not selected.snap_ok.astype(bool).all():
        raise RuntimeError("Canonical station coordinates did not pass KMZ/river snap review")
    selected["station_code"] = selected.station_id.map(lambda value: STATIONS[value]["code"])
    selected["station_name_canonical"] = selected.station_id.map(lambda value: STATIONS[value]["name"])
    selected["coordinate_status"] = "verified_KMZ_Point_canonical_station_coordinate"
    selected["candidate_section_coordinate_status"] = (
        "station_coordinate_proxy_only_exact_fixed_section_not_georeferenced"
    )
    return selected[
        [
            "station_id",
            "station_code",
            "station_name_canonical",
            "longitude",
            "latitude",
            "source_file",
            "kmz_ID",
            "coordinate_status",
            "candidate_section_coordinate_status",
        ]
    ].sort_values("station_id")


def build_ground_measurements() -> pd.DataFrame:
    data = pd.read_csv(MEASUREMENTS, dtype={"station_id": str})
    data["station_id"] = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.isin(STATIONS)].copy()
    data["station_name"] = data.station_id.map(lambda value: STATIONS[value]["name"])
    data["date"] = pd.to_datetime(data.date).dt.strftime("%Y-%m-%d")
    data["H"] = data.stage_m
    data["Q"] = data.discharge_m3s
    data["A"] = data.area_m2
    data["W"] = data.width_m
    data["D"] = data.mean_depth_m
    data["V"] = data.mean_velocity_ms
    data["source_file"] = data.source_file.astype(str) + "#" + data.source_page.astype(str)
    data["measurement_quality"] = data.confirmation_status
    columns = [
        "measurement_id",
        "station_id",
        "station_name",
        "date",
        "H",
        "Q",
        "A",
        "W",
        "D",
        "V",
        "source_file",
        "measurement_quality",
    ]
    result = data[columns].sort_values(["station_id", "date", "measurement_id"])
    if len(result) != 72 or result.groupby("station_id").size().to_dict() != {
        "00705600": 24,
        "00705700": 48,
    }:
        raise RuntimeError("Expected frozen ground measurement counts of BYBLK=24 and DSK=48")
    return result


def search_items(catalog, longitude: float, latitude: float) -> list:
    degree_margin = 0.04
    items = list(
        catalog.search(
            collections=[COLLECTION],
            bbox=[
                longitude - degree_margin,
                latitude - degree_margin,
                longitude + degree_margin,
                latitude + degree_margin,
            ],
            datetime="2010-12-24/2012-01-08",
        ).items()
    )
    allowed = {"landsat-5", "landsat-7"}
    return sorted(
        [item for item in items if item.properties.get("platform") in allowed],
        key=lambda value: (value.datetime, value.id),
    )


def temporal_bin(days: int) -> str:
    value = abs(int(days))
    if value == 0:
        return "same_day"
    if value <= 1:
        return "within_1day"
    if value <= 3:
        return "within_3days"
    if value <= 5:
        return "within_5days"
    return "within_8days"


def item_rank(item, measurement_date: pd.Timestamp) -> tuple:
    difference = abs((pd.Timestamp(item.datetime.date()) - measurement_date).days)
    cloud = float(item.properties.get("eo:cloud_cover", math.inf))
    cloud_tier = 0 if cloud <= PRIMARY_SCENE_CLOUD_PERCENT else 1 if cloud <= FALLBACK_SCENE_CLOUD_PERCENT else 2
    return difference, cloud_tier, cloud, item.datetime, item.id


def scene_directory(station_code: str, item) -> Path:
    return DATA_ROOT / station_code / item.datetime.date().isoformat() / item.properties.get("platform", "unknown") / item.id


def validate_tiff(path: Path) -> dict:
    if not path.exists() or path.stat().st_size == 0:
        return {"valid": False, "reason": "missing_or_empty"}
    try:
        with rasterio.open(path) as source:
            array = source.read(1)
            valid = source.crs is not None and source.transform is not None and array.size > 0
            return {
                "valid": bool(valid),
                "reason": "ok" if valid else "missing_georeferencing_or_pixels",
                "crs": source.crs.to_string() if source.crs else "",
                "width": source.width,
                "height": source.height,
                "dtype": source.dtypes[0],
                "all_zero": bool(np.all(array == 0)),
            }
    except Exception as error:
        return {"valid": False, "reason": f"read_error:{type(error).__name__}"}


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_aoi_band(asset_url: str, longitude: float, latitude: float) -> tuple[np.ndarray, dict]:
    with rasterio.Env(
        GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
        GDAL_HTTP_CONNECTTIMEOUT="10",
        GDAL_HTTP_TIMEOUT="30",
        GDAL_HTTP_MAX_RETRY="2",
        GDAL_HTTP_RETRY_DELAY="2",
    ):
        with rasterio.open(asset_url) as source:
            transformer = Transformer.from_crs("EPSG:4326", source.crs, always_xy=True)
            center_x, center_y = transformer.transform(longitude, latitude)
            raw_window = from_bounds(
                center_x - AOI_HALF_SIZE_M,
                center_y - AOI_HALF_SIZE_M,
                center_x + AOI_HALF_SIZE_M,
                center_y + AOI_HALF_SIZE_M,
                source.transform,
            ).round_offsets().round_lengths()
            full = Window(0, 0, source.width, source.height)
            window = raw_window.intersection(full)
            array = source.read(1, window=window)
            transform = source.window_transform(window)
            profile = source.profile.copy()
            profile.update(
                driver="GTiff",
                width=array.shape[1],
                height=array.shape[0],
                transform=transform,
                count=1,
                compress="DEFLATE",
                tiled=True,
            )
            metadata = {
                "crs": source.crs.to_string(),
                "transform": list(transform)[:6],
                "pixel_size_x": abs(float(transform.a)),
                "pixel_size_y": abs(float(transform.e)),
                "center_x": center_x,
                "center_y": center_y,
                "window": [float(window.col_off), float(window.row_off), float(window.width), float(window.height)],
                "source_width": source.width,
                "source_height": source.height,
                "profile": profile,
            }
            return array, metadata


def save_band(path: Path, array: np.ndarray, profile: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".partial.tif")
    with rasterio.open(temporary, "w", **profile) as destination:
        destination.write(array, 1)
    temporary.replace(path)


def compute_scene_qa(scene_dir: Path, station: dict, item, resumed: bool) -> dict:
    cropped = scene_dir / "cropped"
    arrays = {}
    metadata = None
    validations = {}
    for canonical_name in CANONICAL_ASSETS:
        path = cropped / f"{canonical_name}.tif"
        validations[canonical_name] = validate_tiff(path)
        if not validations[canonical_name]["valid"]:
            raise RuntimeError(f"Invalid downloaded band {canonical_name}: {validations[canonical_name]['reason']}")
        with rasterio.open(path) as source:
            arrays[canonical_name] = source.read(1)
            if metadata is None:
                transformer = Transformer.from_crs("EPSG:4326", source.crs, always_xy=True)
                center_x, center_y = transformer.transform(station["longitude"], station["latitude"])
                center_row, center_col = rowcol(source.transform, center_x, center_y)
                metadata = {
                    "crs": source.crs.to_string(),
                    "transform": list(source.transform)[:6],
                    "pixel_size_m": abs(float(source.transform.a)),
                    "width": source.width,
                    "height": source.height,
                    "center_row": int(center_row),
                    "center_col": int(center_col),
                }
    shapes = {value.shape for value in arrays.values()}
    if len(shapes) != 1:
        raise RuntimeError(f"Band shape mismatch: {shapes}")
    qa = arrays["qa_pixel"].astype(np.uint16)
    yy, xx = np.indices(qa.shape)
    radius_pixels = max(1.0, LOCAL_QA_RADIUS_M / metadata["pixel_size_m"])
    local = (yy - metadata["center_row"]) ** 2 + (xx - metadata["center_col"]) ** 2 <= radius_pixels**2
    if not local.any():
        raise RuntimeError("Station is not covered by downloaded AOI")
    fill = (qa & (1 << 0)) != 0
    dilated_cloud = (qa & (1 << 1)) != 0
    cloud = (qa & (1 << 3)) != 0
    cloud_shadow = (qa & (1 << 4)) != 0
    snow = (qa & (1 << 5)) != 0
    invalid_qa = fill | dilated_cloud | cloud | cloud_shadow | snow
    spectral_zero = np.zeros(qa.shape, dtype=bool)
    for name in ("blue", "green", "red", "nir", "swir1"):
        spectral_zero |= arrays[name] == 0
    local_cloud = bool(np.any((dilated_cloud | cloud)[local]))
    local_shadow = bool(np.any(cloud_shadow[local]))
    local_snow = bool(np.any(snow[local]))
    local_fill = bool(np.any(fill[local] | spectral_zero[local]))
    local_valid_fraction = float((~(invalid_qa | spectral_zero))[local].mean())
    platform = item.properties.get("platform")
    slc_gap = bool(platform == "landsat-7" and local_fill)
    scene_cloud = float(item.properties.get("eo:cloud_cover", np.nan))
    reasons = []
    if scene_cloud > FALLBACK_SCENE_CLOUD_PERCENT:
        reasons.append("scene_cloud_gt_40pct")
    if local_cloud:
        reasons.append("target_cloud")
    if local_shadow:
        reasons.append("target_cloud_shadow")
    if local_snow:
        reasons.append("target_snow_ice")
    if local_fill:
        reasons.append("target_fill_or_zero")
    if slc_gap:
        reasons.append("landsat7_slc_off_gap_at_target")
    if local_valid_fraction < 0.80:
        reasons.append("target_valid_fraction_lt_0.80")
    usable = not reasons
    return {
        "item_id": item.id,
        "platform": platform,
        "satellite_date": item.datetime.date().isoformat(),
        "scene_cloud_percent": scene_cloud,
        "target_local_cloud_flag": local_cloud,
        "target_cloud_shadow_flag": local_shadow,
        "snow_ice_flag": local_snow,
        "fill_or_zero_flag": local_fill,
        "landsat7_slc_off_target_gap": slc_gap,
        "local_valid_fraction": local_valid_fraction,
        "usable_for_width": usable,
        "rejection_reason": "" if usable else ";".join(reasons),
        "crs": metadata["crs"],
        "transform": metadata["transform"],
        "pixel_size_m": metadata["pixel_size_m"],
        "aoi_width_pixels": metadata["width"],
        "aoi_height_pixels": metadata["height"],
        "aoi_covers_station": 0 <= metadata["center_row"] < metadata["height"] and 0 <= metadata["center_col"] < metadata["width"],
        "resumed_from_complete_scene": resumed,
        "qa_definition": "QA_PIXEL bits 0 fill,1 dilated cloud,3 cloud,4 shadow,5 snow; do not rely on bit6 alone",
    }


def download_and_qa_scene(station: dict, item) -> dict:
    scene_dir = scene_directory(station["station_code"], item)
    raw_dir, cropped_dir, qa_dir = scene_dir / "raw", scene_dir / "cropped", scene_dir / "qa"
    complete = scene_dir / "complete.json"
    expected = [cropped_dir / f"{name}.tif" for name in CANONICAL_ASSETS]
    if complete.exists() and all(validate_tiff(path)["valid"] for path in expected):
        qa_path = qa_dir / "qa_summary.json"
        if qa_path.exists():
            result = json.loads(qa_path.read_text(encoding="utf-8"))
            result["resumed_from_complete_scene"] = True
            return result
    raw_dir.mkdir(parents=True, exist_ok=True)
    cropped_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)
    original_item = item.to_dict()
    for asset in original_item.get("assets", {}).values():
        if "href" in asset:
            asset["href"] = unsign_url(asset["href"])
    write_json_atomic(raw_dir / "stac_item.json", original_item)
    signed = planetary_computer.sign(item)
    source_assets = {}
    pending = []
    for canonical_name, asset_key in CANONICAL_ASSETS.items():
        if asset_key not in signed.assets:
            raise RuntimeError(f"Missing asset {asset_key}")
        source_assets[canonical_name] = {
            "asset_key": asset_key,
            "source_url": unsign_url(signed.assets[asset_key].href),
        }
        destination = cropped_dir / f"{canonical_name}.tif"
        valid = validate_tiff(destination)
        if valid["valid"]:
            continue
        pending.append((canonical_name, signed.assets[asset_key].href, destination))

    def fetch_one(task):
        canonical_name, asset_url, destination = task
        array, metadata = read_aoi_band(
            asset_url,
            station["longitude"],
            station["latitude"],
        )
        save_band(destination, array, metadata.pop("profile"))
        return canonical_name

    if pending:
        with ThreadPoolExecutor(max_workers=min(4, len(pending))) as executor:
            futures = [executor.submit(fetch_one, task) for task in pending]
            for future in as_completed(futures):
                future.result()
    write_json_atomic(raw_dir / "source_assets.json", source_assets)
    qa_result = compute_scene_qa(scene_dir, station, item, resumed=False)
    file_manifest = []
    for path in expected:
        validation = validate_tiff(path)
        file_manifest.append(
            {
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                **validation,
            }
        )
    qa_result["files"] = file_manifest
    qa_result["downloaded_bytes"] = int(sum(row["bytes"] for row in file_manifest))
    qa_result["source_asset_id"] = f"pc://{COLLECTION}/{item.id}"
    qa_result["completed_utc"] = utc_now()
    write_json_atomic(qa_dir / "qa_summary.json", qa_result)
    write_json_atomic(
        complete,
        {
            "status": "complete",
            "item_id": item.id,
            "required_assets": list(CANONICAL_ASSETS),
            "file_sha256": {row["path"]: row["sha256"] for row in file_manifest},
            "completed_utc": utc_now(),
        },
    )
    return qa_result


def reflectance(array: np.ndarray) -> np.ndarray:
    return array.astype(np.float32) * 0.0000275 - 0.2


def robust_rgb(red: np.ndarray, green: np.ndarray, blue: np.ndarray, valid: np.ndarray) -> np.ndarray:
    channels = []
    for array in (red, green, blue):
        values = reflectance(array)
        sample = values[valid & np.isfinite(values)]
        if sample.size:
            low, high = np.nanpercentile(sample, [2, 98])
        else:
            low, high = 0.0, 1.0
        scaled = np.clip((values - low) / max(high - low, 1e-6), 0, 1)
        channels.append(scaled)
    rgb = np.dstack(channels)
    rgb[~valid] = 0.15
    return rgb


def make_preview(station: dict, item, qa_result: dict) -> Path:
    scene_dir = scene_directory(station["station_code"], item)
    arrays = {}
    transform = None
    for name in CANONICAL_ASSETS:
        with rasterio.open(scene_dir / "cropped" / f"{name}.tif") as source:
            arrays[name] = source.read(1)
            transform = source.transform
    qa = arrays["qa_pixel"].astype(np.uint16)
    invalid = np.zeros(qa.shape, dtype=bool)
    for bit in (0, 1, 3, 4, 5):
        invalid |= (qa & (1 << bit)) != 0
    for name in ("blue", "green", "red", "nir", "swir1"):
        invalid |= arrays[name] == 0
    valid = ~invalid
    green = reflectance(arrays["green"])
    nir = reflectance(arrays["nir"])
    swir = reflectance(arrays["swir1"])
    ndwi = np.divide(green - nir, green + nir, out=np.full_like(green, np.nan), where=np.abs(green + nir) > 1e-6)
    mndwi = np.divide(green - swir, green + swir, out=np.full_like(green, np.nan), where=np.abs(green + swir) > 1e-6)
    ndwi[~valid] = np.nan
    mndwi[~valid] = np.nan
    transformer = Transformer.from_crs("EPSG:4326", qa_result["crs"], always_xy=True)
    center_x, center_y = transformer.transform(station["longitude"], station["latitude"])
    center_row, center_col = rowcol(transform, center_x, center_y)
    rgb = robust_rgb(arrays["red"], arrays["green"], arrays["blue"], valid)
    fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), constrained_layout=True)
    panels = [(rgb, "RGB", None), (ndwi, "NDWI", "BrBG"), (mndwi, "MNDWI", "BrBG")]
    for axis, (image, title, cmap) in zip(axes, panels):
        if cmap:
            rendered = axis.imshow(image, cmap=cmap, vmin=-1, vmax=1)
            fig.colorbar(rendered, ax=axis, fraction=0.046, pad=0.04)
        else:
            axis.imshow(image)
        axis.scatter([center_col], [center_row], s=90, facecolors="none", edgecolors="#ffdd00", linewidths=2.2, label="canonical station")
        axis.scatter([center_col], [center_row], s=30, marker="x", color="#ff2d55", linewidths=2, label="section proxy")
        axis.set_title(title)
        axis.set_xticks([])
        axis.set_yticks([])
    axes[0].legend(loc="lower right", fontsize=8)
    fig.suptitle(
        f"{station['station_code']} {item.datetime.date().isoformat()} {item.properties.get('platform')}\n"
        f"{item.id} | Δt matched separately in inventory | section coordinate proxy is unverified",
        fontsize=11,
    )
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    path = PREVIEWS / f"{station['station_code']}_{item.datetime.date().isoformat()}_{item.id}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def inventory_base_row(station: dict, measurement_date: pd.Timestamp, item=None) -> dict:
    satellite_date = pd.Timestamp(item.datetime.date()) if item is not None else pd.NaT
    difference = int((satellite_date - measurement_date).days) if item is not None else np.nan
    properties = item.properties if item is not None else {}
    return {
        "station_id": station["station_id"],
        "station_name": station["station_name"],
        "station_code": station["station_code"],
        "station_longitude": station["longitude"],
        "station_latitude": station["latitude"],
        "measurement_date": measurement_date.strftime("%Y-%m-%d"),
        "satellite_date": satellite_date.strftime("%Y-%m-%d") if item is not None else "",
        "time_difference_days": difference,
        "date_difference_days": difference,
        "absolute_time_difference_days": abs(difference) if item is not None else np.nan,
        "temporal_match_bin": temporal_bin(difference) if item is not None else "no_match_within_8days",
        "platform": properties.get("platform", ""),
        "landsat_product_id": item.id if item is not None else "",
        "collection": COLLECTION,
        "cloud_cover_scene": float(properties.get("eo:cloud_cover", np.nan)),
        "target_local_cloud_flag": np.nan,
        "target_cloud_shadow_flag": np.nan,
        "snow_ice_flag": np.nan,
        "fill_or_zero_flag": np.nan,
        "landsat7_slc_off_target_gap": np.nan,
        "local_valid_fraction": np.nan,
        "usable_for_width": False,
        "selected_for_measurement": False,
        "download_status": "not_evaluated",
        "rejection_reason": "",
        "source_url_or_asset_id": f"pc://{COLLECTION}/{item.id}" if item is not None else STAC_URL,
        "scene_directory": str(scene_directory(station["station_code"], item).relative_to(ROOT)) if item is not None else "",
        "preview_path": "",
        "section_coordinate_status": station["section_status"],
    }


def audit_station(catalog, station: dict, measurement_dates: list[pd.Timestamp], scene_cache: dict) -> list[dict]:
    items = search_items(catalog, station["longitude"], station["latitude"])
    rows = []
    for measurement_date in measurement_dates:
        candidates = [
            item for item in items
            if abs((pd.Timestamp(item.datetime.date()) - measurement_date).days) <= MAX_TIME_DIFFERENCE_DAYS
        ]
        candidates.sort(key=lambda item: item_rank(item, measurement_date))
        if not candidates:
            row = inventory_base_row(station, measurement_date)
            row["download_status"] = "catalog_search_complete"
            row["rejection_reason"] = "no_landsat5_or_7_scene_within_8days"
            rows.append(row)
            continue
        selected_item_id = None
        candidate_results = {}
        for item in candidates:
            cloud = float(item.properties.get("eo:cloud_cover", np.nan))
            if not np.isfinite(cloud) or cloud > FALLBACK_SCENE_CLOUD_PERCENT:
                candidate_results[item.id] = {"download_status": "not_downloaded", "rejection_reason": "missing_cloud_metadata_or_scene_cloud_gt_40pct"}
                continue
            cache_key = (station["station_id"], item.id)
            if cache_key not in scene_cache:
                try:
                    print(
                        f"  [{station['station_code']}] {measurement_date.date()} -> "
                        f"{item.datetime.date()} {item.id} cloud={cloud:.1f}%",
                        flush=True,
                    )
                    scene_cache[cache_key] = download_and_qa_scene(station, item)
                except Exception as error:
                    scene_cache[cache_key] = {
                        "usable_for_width": False,
                        "download_error": f"{type(error).__name__}:{error}",
                        "rejection_reason": f"download_or_read_failed:{type(error).__name__}",
                    }
            result = scene_cache[cache_key]
            candidate_results[item.id] = result
            if result.get("usable_for_width", False):
                selected_item_id = item.id
                if not result.get("preview_path"):
                    preview = make_preview(station, item, result)
                    result["preview_path"] = str(preview.relative_to(ROOT))
                break
        for item in candidates:
            row = inventory_base_row(station, measurement_date, item)
            result = candidate_results.get(item.id)
            if result is None:
                row["download_status"] = "not_downloaded"
                row["rejection_reason"] = "not_selected_after_higher_priority_usable_scene"
            elif "download_error" in result:
                row["download_status"] = "failed"
                row["rejection_reason"] = result["rejection_reason"]
            elif "target_local_cloud_flag" in result:
                for name in (
                    "target_local_cloud_flag", "target_cloud_shadow_flag", "snow_ice_flag",
                    "fill_or_zero_flag", "landsat7_slc_off_target_gap", "local_valid_fraction",
                    "usable_for_width",
                ):
                    row[name] = result.get(name)
                row["download_status"] = "resumed_complete" if result.get("resumed_from_complete_scene") else "downloaded_complete"
                row["rejection_reason"] = result.get("rejection_reason", "")
                row["preview_path"] = result.get("preview_path", "")
            else:
                row["download_status"] = result.get("download_status", "not_downloaded")
                row["rejection_reason"] = result.get("rejection_reason", "")
            if item.id == selected_item_id:
                row["selected_for_measurement"] = True
                row["usable_for_width"] = True
                row["rejection_reason"] = ""
            elif row["usable_for_width"] and selected_item_id is not None:
                row["rejection_reason"] = "usable_but_not_selected_higher_priority_scene_chosen"
            rows.append(row)
    return rows


def build_summary(inventory: pd.DataFrame, ground: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for station_id, info in STATIONS.items():
        station_ground = ground.loc[ground.station_id.eq(station_id)]
        unique_dates = sorted(station_ground.date.unique())
        subset = inventory.loc[inventory.station_id.eq(station_id)]
        selected = subset.loc[subset.selected_for_measurement.eq(True)]
        def dates_within(days: int) -> int:
            matches = subset.loc[subset.absolute_time_difference_days.le(days)]
            return int(matches.measurement_date.nunique())
        rows.append({
            "station_id": station_id,
            "station_name": info["name"],
            "total_ground_measurements": len(station_ground),
            "unique_ground_measurement_dates": len(unique_dates),
            "exact_same_day_images": dates_within(0),
            "within_3day_images": dates_within(3),
            "within_5day_images": dates_within(5),
            "within_8day_images": dates_within(8),
            "usable_clear_images": int(selected.measurement_date.nunique()),
            "selected_landsat5_dates": int(selected.loc[selected.platform.eq("landsat-5"), "measurement_date"].nunique()),
            "selected_landsat7_dates": int(selected.loc[selected.platform.eq("landsat-7"), "measurement_date"].nunique()),
            "evaluated_unique_scenes": int(subset.loc[subset.download_status.isin(["downloaded_complete", "resumed_complete"]), "landsat_product_id"].nunique()),
            "selected_unique_scenes": int(selected.landsat_product_id.nunique()),
            "usable_fraction_of_unique_dates": int(selected.measurement_date.nunique()) / len(unique_dates),
        })
    return pd.DataFrame(rows)


def directory_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file()) if path.exists() else 0


def write_report(summary: pd.DataFrame, inventory: pd.DataFrame, ground: pd.DataFrame, coordinates: pd.DataFrame, bytes_used: int) -> None:
    station_lines = []
    for row in summary.itertuples(index=False):
        station_lines.append(
            f"- {STATIONS[row.station_id]['code']}（{row.station_name}）：地面记录{row.total_ground_measurements}条/"
            f"{row.unique_ground_measurement_dates}个唯一日期；同日{row.exact_same_day_images}，±3天{row.within_3day_images}，"
            f"±5天{row.within_5day_images}，±8天{row.within_8day_images}，最终usable {row.usable_clear_images}个日期；"
            f"Landsat 5/7入选日期分别为{row.selected_landsat5_dates}/{row.selected_landsat7_dates}。"
        )
    evaluated = inventory.loc[inventory.download_status.isin(["downloaded_complete", "resumed_complete"])]
    unique_eval = evaluated.drop_duplicates(["station_id", "landsat_product_id"])
    rejected = unique_eval.loc[~unique_eval.usable_for_width.astype(bool)]
    flag_counts = {
        "target_cloud": int(unique_eval.target_local_cloud_flag.fillna(False).astype(bool).sum()),
        "target_cloud_shadow": int(unique_eval.target_cloud_shadow_flag.fillna(False).astype(bool).sum()),
        "target_snow_ice": int(unique_eval.snow_ice_flag.fillna(False).astype(bool).sum()),
        "target_fill_or_zero": int(unique_eval.fill_or_zero_flag.fillna(False).astype(bool).sum()),
        "landsat7_slc_off_target_gap": int(unique_eval.landsat7_slc_off_target_gap.fillna(False).astype(bool).sum()),
    }
    reasons = Counter()
    for value in rejected.rejection_reason.fillna(""):
        for reason in str(value).split(";"):
            if reason:
                reasons[reason] += 1
    by = summary.set_index("station_id")
    better = "DSK" if by.loc["00705700", "usable_fraction_of_unique_dates"] >= by.loc["00705600", "usable_fraction_of_unique_dates"] else "BYBLK"
    report = f"""# RS-W0：BYBLK–DSK 遥感河宽数据下载与可用性审计

## 阶段结论

RS-W0已执行实际STAC检索、AOI窗口下载、GeoTIFF完整性检查、局部`QA_PIXEL`判读和预览生成。本阶段只审计河宽影像可用性，不拟合Q、不训练模型、不启动RS-W1。

## 1. 地面测流日期

共整理{len(ground)}条地面测流记录、{ground[['station_id','date']].drop_duplicates().shape[0]}个站点—日期组合。H、Q、A、W、D、V只用于形成可追溯的地面日期表；Q没有参与scene排序、局部QA或阈值选择。

{chr(10).join(station_lines)}

## 2. 数据源、坐标与下载方式

- 数据源：Microsoft Planetary Computer STAC `landsat-c2-l2`，仅检索2011年可用的Landsat 5 TM和Landsat 7 ETM+。
- 坐标来自老师KMZ生成的`data/processed/nodes.csv` canonical Point：BYBLK ({coordinates.iloc[0].longitude:.8f}, {coordinates.iloc[0].latitude:.8f})，DSK ({coordinates.iloc[1].longitude:.8f}, {coordinates.iloc[1].latitude:.8f})。
- 每景只通过COG范围读取保存站点中心5 km×5 km窗口；保留Blue、Green、Red、NIR、SWIR1和QA_PIXEL的原始整数像元值，不下载整幅scene。
- `raw/`保存未签名STAC元数据和持久资产URL，`cropped/`保存原始DN/QA的AOI GeoTIFF，`qa/`保存逐景完整性与局部QA。签名token不写入清单。
- 已完成scene以`complete.json`和每波段SHA-256识别；重跑会跳过完整文件。

## 3. 时间匹配结果

`satellite_date`与`measurement_date`始终分列，`time_difference_days`保留正负号。统计中的±3/±5/±8表示存在该窗口内的catalog候选，不把邻日影像写成同日。最终入选以|Δt|优先，场景云量≤20%优先；必要时才放宽至≤40%，并必须通过目标点局部QA。

## 4. 云、雪、阴影、填充值与SLC-off淘汰

共实际评估{len(unique_eval)}个站点—scene，局部QA淘汰{len(rejected)}个。按标志非互斥计数：目标云{flag_counts['target_cloud']}、云影{flag_counts['target_cloud_shadow']}、雪/冰{flag_counts['target_snow_ice']}、fill/全零{flag_counts['target_fill_or_zero']}、Landsat 7目标处SLC-off缺口{flag_counts['landsat7_slc_off_target_gap']}；全部分项拒绝原因计数为`{dict(reasons)}`。Landsat 7在2003年后的SLC-off由目标附近QA fill/光谱零值显式识别；若缺口穿过目标区域即不可用，不做条带插值。

## 5. 最终适合遥感河宽验证的日期

最终usable日期见汇总表和scene inventory的`selected_for_measurement=true`。当前按可用日期比例与典型实测宽度判断，**{better}更适合作为先行人工复核对象**。DSK多数实测宽约66–72m，约2.2–2.4个30m像元；BYBLK多为41–46m，仅约1.4–1.5个像元。两者都处于Landsat河宽定量提取的边缘分辨率，尤其BYBLK不宜把单像元岸线变化直接解释成真实宽度变化。

## 6. 固定断面定位限制

项目中有canonical站点坐标，但未找到两个固定测流断面的地理坐标、方位角或端点。预览中的黄色圆圈是canonical站点，红色叉是“候选断面位置代理”，二者重合且明确标为未验证。正式RS-W1前必须人工确认测流断面位置/方向，否则当前影像只能支持站点附近河道可见性审计。

## 7. 是否需要MODIS补充

不建议用MODIS补充固定断面河宽。MODIS常用250–500m像元远大于约40–72m的实测河宽，即使时间覆盖更密，也不能提供独立可靠的岸线宽度；可用于区域水情背景，但不能替代本阶段30m影像的断面宽度验证。

## 8. 是否值得进入RS-W1

只有在人工确认固定断面坐标/方向，并逐张审核本阶段RGB、NDWI、MNDWI预览后，才值得进行受限的RS-W1试验。优先从DSK的clear scene做小规模交叉验证；BYBLK应把30m分辨率不确定性作为主要误差源。RS-W0没有使用真实测试Q挑scene或水体阈值，也没有启动RS-W1。

## 9. 下载量与可追溯性

`data/remote_sensing/landsat`当前占用{bytes_used / 1024**2:.2f} MiB（{bytes_used} bytes）。所有候选、未下载、失败、局部QA淘汰和最终入选scene均保留`rejection_reason`或状态；原始远程COG未被覆盖。
"""
    (OUT / "stage_rs_w0_download_report_zh.md").write_text(report, encoding="utf-8")


def main() -> None:
    argparse.ArgumentParser(description="Run RS-W0 Landsat download and availability audit").parse_args()
    assert_prior_stages_unchanged()
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    coordinates = load_canonical_stations()
    ground = build_ground_measurements()
    coordinates.to_csv(OUT / "canonical_station_coordinates.csv", index=False, encoding="utf-8-sig")
    ground.to_csv(OUT / "ground_measurement_dates_for_remote_sensing.csv", index=False, encoding="utf-8-sig")
    catalog = pystac_client.Client.open(STAC_URL)
    inventory_rows = []
    scene_cache = {}
    for coordinate in coordinates.itertuples(index=False):
        station = {
            "station_id": coordinate.station_id,
            "station_code": coordinate.station_code,
            "station_name": coordinate.station_name_canonical,
            "longitude": float(coordinate.longitude),
            "latitude": float(coordinate.latitude),
            "section_status": coordinate.candidate_section_coordinate_status,
        }
        dates = sorted(pd.to_datetime(ground.loc[ground.station_id.eq(coordinate.station_id), "date"].unique()))
        print(f"[{station['station_code']}] auditing {len(dates)} unique ground dates", flush=True)
        inventory_rows.extend(audit_station(catalog, station, dates, scene_cache))
    inventory = pd.DataFrame(inventory_rows).sort_values(
        ["station_id", "measurement_date", "absolute_time_difference_days", "cloud_cover_scene", "landsat_product_id"],
        na_position="last",
    )
    inventory.to_csv(OUT / "remote_sensing_scene_inventory.csv", index=False, encoding="utf-8-sig")
    summary = build_summary(inventory, ground)
    summary.to_csv(OUT / "landsat_ground_match_summary.csv", index=False, encoding="utf-8-sig")
    bytes_used = directory_size(DATA_ROOT)
    write_report(summary, inventory, ground, coordinates, bytes_used)
    result = {
        "stage": "RS-W0",
        "status": "completed_download_and_availability_audit",
        "collection": COLLECTION,
        "ground_measurement_rows": len(ground),
        "unique_ground_station_dates": int(ground[["station_id", "date"]].drop_duplicates().shape[0]),
        "downloaded_or_resumed_unique_station_scenes": int(
            inventory.loc[inventory.download_status.isin(["downloaded_complete", "resumed_complete"]), ["station_id", "landsat_product_id"]].drop_duplicates().shape[0]
        ),
        "selected_usable_station_dates": int(inventory.loc[inventory.selected_for_measurement, ["station_id", "measurement_date"]].drop_duplicates().shape[0]),
        "data_bytes": bytes_used,
        "data_mib": bytes_used / 1024**2,
        "scene_selection_used_ground_q": False,
        "width_threshold_fitted": False,
        "discharge_model_fitted": False,
        "sentinel2_used_for_2011": False,
        "modis_downloaded": False,
        "rs_w1_started": False,
        "d9_to_d12_modified": False,
        "created_utc": utc_now(),
    }
    write_json_atomic(OUT / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
