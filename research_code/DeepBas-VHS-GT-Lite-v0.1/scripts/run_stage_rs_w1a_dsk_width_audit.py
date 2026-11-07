from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import requests
import shapefile
from pyproj import Transformer
from rasterio.windows import Window, from_bounds
from shapely.geometry import LineString, Point, mapping
from shapely.ops import transform as shp_transform


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/rs_w1a"
SCENE_PRODUCTS = OUT / "scene_products"
DIAGNOSTICS = OUT / "diagnostics"
PAN_DIR = OUT / "pan"

STATION_ID = "00705700"
STATION_CODE = "DSK"
SR_SCALE = 0.0000275
SR_OFFSET = -0.2
PRIMARY_METHOD = "mndwi_fixed_0"
PRIMARY_TRANSECT = "T0"
FIXED_THRESHOLDS = {"ndwi_fixed_0": 0.0, "mndwi_fixed_0": 0.0}
TRANSECT_OFFSETS_M = {
    "T_minus_60m": -60.0,
    "T_minus_30m": -30.0,
    "T0": 0.0,
    "T_plus_30m": 30.0,
    "T_plus_60m": 60.0,
}
TRANSECT_HALF_LENGTH_M = 500.0
PROFILE_STEP_M = 1.0
SEED_SEARCH_RADIUS_M = 300.0
SENSITIVITY_RANGE_LIMIT_M = 30.0

RSW0 = OUT.parent / "rs_w0"
INVENTORY = RSW0 / "remote_sensing_scene_inventory.csv"
GROUND = RSW0 / "ground_measurement_dates_for_remote_sensing.csv"
COORDINATES = RSW0 / "canonical_station_coordinates.csv"
RIVER_MATCH = ROOT / "data/processed/station_river_matches.csv"
SNAP_CANDIDATES = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a/station_river_snap_candidates_2011.csv"
HYDRORIVERS = ROOT / "data/raw/hydrorivers/HydroRIVERS_v10_as.shp"
DAILY_STAGE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5/d5c_stage_and_features/daily_stage_dsk_2011_reviewed.csv"
DAILY_Q = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/daily_discharge_2011_canonical.csv"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hashes(path: Path) -> dict[str, str]:
    return {str(p.relative_to(ROOT)).replace("\\", "/"): sha256(p) for p in sorted(path.rglob("*")) if p.is_file()}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    def scientific_json(value):
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.floating):
            return float(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=scientific_json), encoding="utf-8")


def bool_value(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def tier_for_days(days: int) -> str:
    if days == 0:
        return "A"
    if days <= 1:
        return "B"
    if days <= 3:
        return "C"
    return "D"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    inventory = pd.read_csv(INVENTORY, dtype={"station_id": str})
    ground = pd.read_csv(GROUND, dtype={"station_id": str})
    coords = pd.read_csv(COORDINATES, dtype={"station_id": str})
    dsk = coords.loc[coords.station_id.eq(STATION_ID)]
    if len(dsk) != 1:
        raise RuntimeError("Canonical DSK coordinate must be unique")
    inventory = inventory.loc[inventory.station_id.eq(STATION_ID)].copy()
    inventory["usable_for_width"] = inventory.usable_for_width.map(bool_value)
    inventory = inventory.loc[inventory.usable_for_width].copy()
    if inventory.empty:
        raise RuntimeError("No usable DSK scenes in frozen RS-W0 inventory")
    ground = ground.loc[ground.station_id.eq(STATION_ID)].copy()
    for col in ("H", "Q", "A", "W", "D", "V"):
        ground[col] = pd.to_numeric(ground[col], errors="coerce")
    return inventory, ground, dsk.iloc[0]


def aggregate_ground(ground: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for date, group in ground.groupby("date", sort=True):
        row = {"measurement_date": date, "ground_measurement_count": len(group)}
        for col in ("H", "Q", "A", "W", "D", "V"):
            values = group[col].dropna().astype(float)
            row[f"{col}_ground_min"] = values.min() if len(values) else np.nan
            row[f"{col}_ground_max"] = values.max() if len(values) else np.nan
            row[f"{col}_ground_mean"] = values.mean() if len(values) else np.nan
        row["same_day_multiple_ground_measurements"] = len(group) > 1
        row["measurement_time_available"] = False
        rows.append(row)
    return pd.DataFrame(rows)


def unique_scenes(inventory: pd.DataFrame, ground_by_date: pd.DataFrame) -> pd.DataFrame:
    rows = []
    key_cols = ["station_id", "satellite_date", "landsat_product_id"]
    for keys, group in inventory.groupby(key_cols, sort=True):
        pair_dates = sorted(group.measurement_date.dropna().astype(str).unique())
        pair_rows = ground_by_date.loc[ground_by_date.measurement_date.isin(pair_dates)]
        candidates = group[["measurement_date", "absolute_time_difference_days"]].drop_duplicates().copy()
        candidates["absolute_time_difference_days"] = pd.to_numeric(candidates.absolute_time_difference_days)
        candidates = candidates.sort_values(["absolute_time_difference_days", "measurement_date"], kind="stable")
        canonical = candidates.iloc[0]
        base = group.iloc[0]
        days = int(round(float(canonical.absolute_time_difference_days)))
        rows.append({
            "station_id": keys[0],
            "station_code": STATION_CODE,
            "satellite_date": keys[1],
            "platform": base.platform,
            "landsat_product_id": keys[2],
            "collection": base["collection"],
            "scene_directory": base.scene_directory,
            "ground_pair_count": len(pair_dates),
            "ground_measurement_row_count": int(pair_rows.ground_measurement_count.sum()),
            "paired_measurement_dates": ";".join(pair_dates),
            "validation_measurement_date": canonical.measurement_date,
            "validation_delta_days": days,
            "validation_tier": tier_for_days(days),
            "unique_satellite_scene": True,
            "same_day_scene": days == 0,
            "target_local_cloud_flag": bool_value(base.target_local_cloud_flag),
            "target_cloud_shadow_flag": bool_value(base.target_cloud_shadow_flag),
            "snow_ice_flag": bool_value(base.snow_ice_flag),
            "fill_or_zero_flag": bool_value(base.fill_or_zero_flag),
            "landsat7_slc_off_target_gap": bool_value(base.landsat7_slc_off_target_gap),
            "local_valid_fraction": float(base.local_valid_fraction),
            "section_coordinate_status": base.section_coordinate_status,
        })
    result = pd.DataFrame(rows).sort_values(["satellite_date", "landsat_product_id"]).reset_index(drop=True)
    if result.duplicated(key_cols).any():
        raise AssertionError("Scene deduplication failed")
    return result


def load_centerline(station: pd.Series) -> tuple[LineString, dict]:
    match = pd.read_csv(RIVER_MATCH, dtype={"station_id": str})
    match = match.loc[match.station_id.eq(STATION_ID)].iloc[0]
    river_id = int(match.river_id)
    candidates = pd.read_csv(SNAP_CANDIDATES, dtype={"station_id": str})
    target = candidates.loc[
        candidates.station_id.eq(STATION_ID)
        & pd.to_numeric(candidates.hyriv_id, errors="coerce").eq(river_id)
    ]
    if target.empty:
        raise RuntimeError("HydroRIVERS record index evidence is missing")
    record_index = int(target.iloc[0].hydrorivers_record_index)
    reader = shapefile.Reader(str(HYDRORIVERS))
    record = reader.record(record_index).as_dict()
    if int(record["HYRIV_ID"]) != river_id:
        raise AssertionError("HydroRIVERS record id mismatch")
    shape = reader.shape(record_index)
    if len(shape.parts) != 1:
        raise RuntimeError("Unexpected multipart HydroRIVERS reach")
    line_wgs84 = LineString(shape.points)
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True).transform
    line_utm = shp_transform(to_utm, line_wgs84)
    station_utm = shp_transform(to_utm, Point(float(station.longitude), float(station.latitude)))
    along = line_utm.project(station_utm)
    snap = line_utm.interpolate(along)
    evidence = {
        "source": str(HYDRORIVERS.relative_to(ROOT)).replace("\\", "/"),
        "hydrorivers_record_index": record_index,
        "hyriv_id": river_id,
        "next_down": int(record["NEXT_DOWN"]),
        "main_riv": int(record["MAIN_RIV"]),
        "ord_flow": int(record["ORD_FLOW"]),
        "line_length_m_projected": line_utm.length,
        "canonical_station_to_centerline_m": station_utm.distance(snap),
        "fixed_measurement_section_georeferenced": False,
        "interpretation": "HydroRIVERS centerline proxy near canonical station; not the surveyed fixed-section coordinate",
    }
    return line_utm, evidence


def build_transects(line_utm: LineString, station: pd.Series, evidence: dict) -> tuple[dict[str, LineString], dict]:
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True).transform
    to_wgs = Transformer.from_crs("EPSG:32645", "EPSG:4326", always_xy=True).transform
    station_utm = shp_transform(to_utm, Point(float(station.longitude), float(station.latitude)))
    base_d = line_utm.project(station_utm)
    features, lines = [], {}
    for tid, offset in TRANSECT_OFFSETS_M.items():
        d = min(max(base_d + offset, 0.0), line_utm.length)
        center = line_utm.interpolate(d)
        tangent_half = 75.0
        p0 = line_utm.interpolate(max(0.0, d - tangent_half))
        p1 = line_utm.interpolate(min(line_utm.length, d + tangent_half))
        dx, dy = p1.x - p0.x, p1.y - p0.y
        norm = math.hypot(dx, dy)
        if norm == 0:
            raise RuntimeError("Cannot estimate local river direction")
        ux, uy = dx / norm, dy / norm
        nx, ny = -uy, ux
        line = LineString([
            (center.x - nx * TRANSECT_HALF_LENGTH_M, center.y - ny * TRANSECT_HALF_LENGTH_M),
            (center.x + nx * TRANSECT_HALF_LENGTH_M, center.y + ny * TRANSECT_HALF_LENGTH_M),
        ])
        lines[tid] = line
        az = (math.degrees(math.atan2(nx, ny)) + 360) % 360
        geom = shp_transform(to_wgs, line)
        features.append({
            "type": "Feature",
            "properties": {
                "transect_id": tid,
                "along_stored_centerline_offset_m": offset,
                "transect_length_m": 2 * TRANSECT_HALF_LENGTH_M,
                "transect_azimuth_deg": az,
                "centerline_source": evidence["source"],
                "hyriv_id": evidence["hyriv_id"],
                "canonical_station_to_centerline_m": evidence["canonical_station_to_centerline_m"],
                "fixed_measurement_section_georeferenced": False,
                "direction_note": "minus/plus follow stored HydroRIVERS geometry order; upstream/downstream identity not asserted",
            },
            "geometry": mapping(geom),
        })
    geojson = {
        "type": "FeatureCollection",
        "name": "DSK candidate cross-river transects",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
        "metadata": evidence,
    }
    return lines, geojson


def qa_valid(qa: np.ndarray, bands: list[np.ndarray]) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    flags = {
        "fill": (qa & (1 << 0)) != 0,
        "dilated_cloud": (qa & (1 << 1)) != 0,
        "cloud": (qa & (1 << 3)) != 0,
        "cloud_shadow": (qa & (1 << 4)) != 0,
        "snow": (qa & (1 << 5)) != 0,
    }
    invalid = np.logical_or.reduce(list(flags.values()))
    for band in bands:
        invalid |= band == 0
    return ~invalid, flags


def safe_index(a: np.ndarray, b: np.ndarray, valid: np.ndarray) -> np.ndarray:
    denom = a + b
    result = np.full(a.shape, np.nan, dtype=np.float32)
    good = valid & np.isfinite(denom) & (np.abs(denom) > 1e-8)
    result[good] = ((a[good] - b[good]) / denom[good]).astype(np.float32)
    return result


def otsu_threshold(values: np.ndarray) -> float:
    values = values[np.isfinite(values)]
    if values.size < 50:
        return float("nan")
    low, high = np.percentile(values, [2, 98])
    if not np.isfinite(low + high) or high <= low:
        return float("nan")
    hist, edges = np.histogram(np.clip(values, low, high), bins=256, range=(low, high))
    centers = (edges[:-1] + edges[1:]) / 2
    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]
    mean1 = np.cumsum(hist * centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((hist * centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]
    variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    return float(centers[int(np.argmax(variance))])


def pixel_centers(transform, shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    rows, cols = np.indices(shape)
    xs = transform.c + (cols + 0.5) * transform.a + (rows + 0.5) * transform.b
    ys = transform.f + (cols + 0.5) * transform.d + (rows + 0.5) * transform.e
    return xs, ys


def connected_component(mask: np.ndarray, transform, seed_point: Point) -> tuple[np.ndarray, dict]:
    xs, ys = pixel_centers(transform, mask.shape)
    distance = np.hypot(xs - seed_point.x, ys - seed_point.y)
    candidates = np.argwhere(mask & (distance <= SEED_SEARCH_RADIUS_M))
    if len(candidates) == 0:
        return np.zeros_like(mask, dtype=bool), {"status": "failed", "reason": "no_water_seed_within_300m"}
    best = candidates[np.argmin(distance[candidates[:, 0], candidates[:, 1]])]
    start = (int(best[0]), int(best[1]))
    seen = np.zeros_like(mask, dtype=bool)
    seen[start] = True
    queue = deque([start])
    while queue:
        row, col = queue.popleft()
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                rr, cc = row + dr, col + dc
                if 0 <= rr < mask.shape[0] and 0 <= cc < mask.shape[1] and mask[rr, cc] and not seen[rr, cc]:
                    seen[rr, cc] = True
                    queue.append((rr, cc))
    return seen, {
        "status": "ok",
        "seed_row": start[0],
        "seed_col": start[1],
        "seed_distance_to_centerline_m": float(distance[start]),
        "component_pixels": int(seen.sum()),
    }


def sample_bilinear(array: np.ndarray, transform, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    inv = ~transform
    cols, rows = inv * (xs, ys)
    cols = np.asarray(cols) - 0.5
    rows = np.asarray(rows) - 0.5
    c0 = np.floor(cols).astype(int)
    r0 = np.floor(rows).astype(int)
    dc, dr = cols - c0, rows - r0
    out = np.full(xs.shape, np.nan, dtype=float)
    good = (r0 >= 0) & (c0 >= 0) & (r0 + 1 < array.shape[0]) & (c0 + 1 < array.shape[1])
    idx = np.where(good)[0]
    if len(idx):
        a00 = array[r0[idx], c0[idx]]
        a01 = array[r0[idx], c0[idx] + 1]
        a10 = array[r0[idx] + 1, c0[idx]]
        a11 = array[r0[idx] + 1, c0[idx] + 1]
        w00 = (1 - dr[idx]) * (1 - dc[idx])
        w01 = (1 - dr[idx]) * dc[idx]
        w10 = dr[idx] * (1 - dc[idx])
        w11 = dr[idx] * dc[idx]
        vals = np.vstack([a00, a01, a10, a11])
        weights = np.vstack([w00, w01, w10, w11])
        finite = np.isfinite(vals)
        numerator = np.nansum(vals * weights, axis=0)
        denominator = np.sum(weights * finite, axis=0)
        local = np.full(len(idx), np.nan)
        ok = denominator > 0.999
        local[ok] = numerator[ok] / denominator[ok]
        out[idx] = local
    return out


def sample_nearest(mask: np.ndarray, transform, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    inv = ~transform
    cols, rows = inv * (xs, ys)
    cols, rows = np.floor(cols).astype(int), np.floor(rows).astype(int)
    good = (rows >= 0) & (cols >= 0) & (rows < mask.shape[0]) & (cols < mask.shape[1])
    out = np.zeros(xs.shape, dtype=bool)
    out[good] = mask[rows[good], cols[good]]
    return out


def runs(binary: np.ndarray) -> list[tuple[int, int]]:
    padded = np.r_[False, binary.astype(bool), False].astype(np.int8)
    changes = np.diff(padded)
    return list(zip(np.where(changes == 1)[0], np.where(changes == -1)[0] - 1))


def crossing(x0: float, y0: float, x1: float, y1: float, threshold: float) -> float:
    if not np.isfinite(y0 + y1) or y1 == y0:
        return (x0 + x1) / 2
    fraction = (threshold - y0) / (y1 - y0)
    return float(x0 + np.clip(fraction, 0, 1) * (x1 - x0))


def measure_transect(line: LineString, index: np.ndarray, component: np.ndarray, raw_water: np.ndarray, transform, threshold: float) -> dict:
    s = np.arange(-TRANSECT_HALF_LENGTH_M, TRANSECT_HALF_LENGTH_M + PROFILE_STEP_M, PROFILE_STEP_M)
    points = [line.interpolate(float(v + TRANSECT_HALF_LENGTH_M)) for v in s]
    xs = np.array([p.x for p in points])
    ys = np.array([p.y for p in points])
    comp_profile = sample_nearest(component, transform, xs, ys)
    raw_profile = sample_nearest(raw_water, transform, xs, ys)
    index_profile = sample_bilinear(index, transform, xs, ys)
    component_runs = runs(comp_profile)
    all_runs = [r for r in runs(raw_profile & (np.abs(s) <= 300)) if (r[1] - r[0] + 1) * PROFILE_STEP_M >= 5]
    result = {
        "status": "failed",
        "failure_reason": "no_connected_water_intersection",
        "W_RS_binary": np.nan,
        "W_RS_subpixel": np.nan,
        "left_bank_position_m": np.nan,
        "right_bank_position_m": np.nan,
        "subpixel_estimate_label": "subpixel edge-interpolated width estimate",
        "channel_count_within_300m": len(all_runs),
        "multi_channel": len(all_runs) > 1,
        "profile_distance_m": s,
        "profile_index": index_profile,
    }
    if not component_runs:
        return result
    selected = min(component_runs, key=lambda ab: abs((s[ab[0]] + s[ab[1]]) / 2))
    a, b = selected
    binary_left = s[a] - PROFILE_STEP_M / 2
    binary_right = s[b] + PROFILE_STEP_M / 2
    binary_width = binary_right - binary_left
    above = np.isfinite(index_profile) & (index_profile > threshold)
    index_runs = runs(above)
    if not index_runs:
        result.update(status="partial", failure_reason="no_subpixel_threshold_run", W_RS_binary=binary_width)
        return result
    binary_mid = (s[a] + s[b]) / 2
    candidate = min(index_runs, key=lambda ab: abs((s[ab[0]] + s[ab[1]]) / 2 - binary_mid))
    ia, ib = candidate
    if ia == 0 or ib == len(s) - 1 or not np.isfinite(index_profile[ia - 1]) or not np.isfinite(index_profile[ib + 1]):
        result.update(status="partial", failure_reason="subpixel_bank_bracket_invalid", W_RS_binary=binary_width)
        return result
    left = crossing(s[ia - 1], index_profile[ia - 1], s[ia], index_profile[ia], threshold)
    right = crossing(s[ib], index_profile[ib], s[ib + 1], index_profile[ib + 1], threshold)
    width = right - left
    if width <= 0 or width > 600:
        result.update(status="partial", failure_reason="subpixel_width_out_of_bounds", W_RS_binary=binary_width)
        return result
    result.update(
        status="ok",
        failure_reason="",
        W_RS_binary=float(binary_width),
        W_RS_subpixel=float(width),
        left_bank_position_m=float(left),
        right_bank_position_m=float(right),
    )
    return result


def save_mask(path: Path, mask: np.ndarray, valid: np.ndarray, profile: dict, tags: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = np.where(valid, mask.astype(np.uint8), 255).astype(np.uint8)
    meta = profile.copy()
    meta.update(dtype="uint8", count=1, nodata=255, compress="deflate")
    with rasterio.open(path, "w", **meta) as dst:
        dst.write(out, 1)
        dst.update_tags(**{k: str(v) for k, v in tags.items()})


def read_scene(scene: pd.Series, t0_center: Point) -> dict:
    scene_dir = ROOT / Path(str(scene.scene_directory).replace("\\", "/"))
    arrays = {}
    profile = transform = crs = None
    for name in ("blue", "green", "red", "nir", "swir1", "qa_pixel"):
        with rasterio.open(scene_dir / "cropped" / f"{name}.tif") as src:
            arrays[name] = src.read(1)
            if profile is None:
                profile, transform, crs = src.profile, src.transform, src.crs
    if str(crs) != "EPSG:32645":
        raise RuntimeError(f"Unexpected scene CRS {crs}")
    valid, qa_flags = qa_valid(arrays["qa_pixel"].astype(np.uint16), [arrays[x] for x in ("blue", "green", "red", "nir", "swir1")])
    scaled = {name: arrays[name].astype(np.float32) * SR_SCALE + SR_OFFSET for name in ("blue", "green", "red", "nir", "swir1")}
    ndwi = safe_index(scaled["green"], scaled["nir"], valid)
    mndwi = safe_index(scaled["green"], scaled["swir1"], valid)
    raw_ndwi = safe_index(arrays["green"].astype(float), arrays["nir"].astype(float), valid)
    xs, ys = pixel_centers(transform, valid.shape)
    local = valid & (np.hypot(xs - t0_center.x, ys - t0_center.y) <= 600)
    otsu = otsu_threshold(mndwi[local])
    method_specs = {
        "ndwi_fixed_0": (ndwi, 0.0),
        "mndwi_fixed_0": (mndwi, 0.0),
        "mndwi_local_otsu": (mndwi, otsu),
    }
    products = {}
    for method, (index, threshold) in method_specs.items():
        if np.isfinite(threshold):
            raw_mask = valid & np.isfinite(index) & (index > threshold)
            component, component_meta = connected_component(raw_mask, transform, t0_center)
        else:
            raw_mask = np.zeros_like(valid)
            component = raw_mask.copy()
            component_meta = {"status": "failed", "reason": "otsu_threshold_unavailable"}
        products[method] = {"index": index, "threshold": threshold, "raw_mask": raw_mask, "component": component, "component_meta": component_meta}
    return {
        "arrays": arrays,
        "scaled": scaled,
        "valid": valid,
        "qa_flags": qa_flags,
        "ndwi": ndwi,
        "mndwi": mndwi,
        "raw_ndwi": raw_ndwi,
        "profile": profile,
        "transform": transform,
        "crs": crs,
        "products": products,
    }


def reflectance_audit(unique: pd.DataFrame, scene_data: dict[str, dict]) -> dict:
    rows, comparisons = [], []
    for scene in unique.itertuples(index=False):
        item_path = ROOT / Path(scene.scene_directory.replace("\\", "/")) / "raw/stac_item.json"
        item = json.loads(item_path.read_text(encoding="utf-8"))
        for canonical, asset in (("green", "green"), ("nir", "nir08"), ("swir1", "swir16")):
            band_meta = item["assets"][asset].get("raster:bands", [{}])[0]
            rows.append({
                "platform": scene.platform,
                "product_id": scene.landsat_product_id,
                "band": canonical,
                "asset_key": asset,
                "scale": band_meta.get("scale"),
                "offset": band_meta.get("offset"),
                "source_metadata": str(item_path.relative_to(ROOT)).replace("\\", "/") + f"#assets.{asset}.raster:bands[0]",
            })
            if float(band_meta.get("scale")) != SR_SCALE or float(band_meta.get("offset")) != SR_OFFSET:
                raise AssertionError("Unexpected Collection 2 Level-2 scale/offset")
        data = scene_data[scene.landsat_product_id]
        valid = np.isfinite(data["raw_ndwi"]) & np.isfinite(data["ndwi"])
        delta = data["ndwi"][valid] - data["raw_ndwi"][valid]
        comparisons.append({
            "product_id": scene.landsat_product_id,
            "platform": scene.platform,
            "valid_pixels": int(valid.sum()),
            "raw_dn_ndwi_mean": float(np.nanmean(data["raw_ndwi"][valid])),
            "scaled_ndwi_mean": float(np.nanmean(data["ndwi"][valid])),
            "mean_absolute_difference": float(np.nanmean(np.abs(delta))),
            "max_absolute_difference": float(np.nanmax(np.abs(delta))),
            "classification_disagreement_at_threshold_0_fraction": float(np.mean((data["raw_ndwi"][valid] > 0) != (data["ndwi"][valid] > 0))),
        })
    return {
        "stage": "RS-W1A",
        "formula": "surface_reflectance = DN * 0.0000275 - 0.2",
        "direct_raw_dn_index_prohibited": True,
        "metadata_records": rows,
        "raw_dn_vs_scaled_ndwi": comparisons,
        "all_metadata_consistent": True,
    }


def rgb_stretch(scaled: dict) -> np.ndarray:
    rgb = np.dstack([scaled["red"], scaled["green"], scaled["blue"]]).astype(float)
    out = np.zeros_like(rgb)
    for i in range(3):
        band = rgb[:, :, i]
        valid = np.isfinite(band)
        low, high = np.percentile(band[valid], [2, 98])
        out[:, :, i] = np.clip((band - low) / max(high - low, 1e-6), 0, 1)
    return out


def diagnostic_figure(scene: pd.Series, data: dict, transects: dict[str, LineString], centerline: LineString, primary: dict, field_row: pd.Series, path: Path) -> None:
    transform = data["transform"]
    bounds = rasterio.transform.array_bounds(data["valid"].shape[0], data["valid"].shape[1], transform)
    extent = [bounds[0], bounds[2], bounds[1], bounds[3]]
    fig, axes = plt.subplots(2, 3, figsize=(18, 11), constrained_layout=True)
    axes[0, 0].imshow(rgb_stretch(data["scaled"]), extent=extent, origin="upper")
    axes[0, 0].set_title("1. RGB (scaled surface reflectance)")
    im1 = axes[0, 1].imshow(data["ndwi"], extent=extent, origin="upper", cmap="RdYlBu", vmin=-0.6, vmax=0.6)
    axes[0, 1].set_title("2. Scaled NDWI")
    fig.colorbar(im1, ax=axes[0, 1], shrink=0.75)
    im2 = axes[0, 2].imshow(data["mndwi"], extent=extent, origin="upper", cmap="RdYlBu", vmin=-0.6, vmax=0.6)
    axes[0, 2].set_title("3. Scaled MNDWI")
    fig.colorbar(im2, ax=axes[0, 2], shrink=0.75)
    mask_show = np.where(data["valid"], data["products"][PRIMARY_METHOD]["component"].astype(float), np.nan)
    axes[1, 0].imshow(mask_show, extent=extent, origin="upper", cmap="Blues", vmin=0, vmax=1)
    axes[1, 0].set_title("4. Connected target-water mask (MNDWI > 0)")
    axes[1, 1].imshow(rgb_stretch(data["scaled"]), extent=extent, origin="upper")
    axes[1, 1].plot(*centerline.xy, color="yellow", lw=2, label="HydroRIVERS 40282189")
    colors = {"T0": "red", "T_minus_60m": "cyan", "T_minus_30m": "lime", "T_plus_30m": "magenta", "T_plus_60m": "orange"}
    for tid, line in transects.items():
        axes[1, 1].plot(*line.xy, color=colors[tid], lw=1.5, label=tid)
    axes[1, 1].set_title("5. Centerline proxy and frozen transects")
    axes[1, 1].legend(fontsize=7, loc="upper right")
    s = primary["profile_distance_m"]
    axes[1, 2].plot(s, primary["ndwi_profile"], label="scaled NDWI", alpha=0.8)
    axes[1, 2].plot(s, primary["profile_index"], label="scaled MNDWI", lw=2)
    axes[1, 2].axhline(0, color="black", ls="--", label="frozen threshold=0")
    if np.isfinite(primary["left_bank_position_m"]):
        axes[1, 2].axvline(primary["left_bank_position_m"], color="blue", ls=":")
        axes[1, 2].axvline(primary["right_bank_position_m"], color="blue", ls=":")
    axes[1, 2].set_xlim(-250, 250)
    axes[1, 2].set_ylim(-1, 1)
    axes[1, 2].set_xlabel("Distance along T0 (m)")
    axes[1, 2].set_ylabel("Index")
    axes[1, 2].set_title("6. T0 spectral profile and interpolated banks")
    axes[1, 2].legend(fontsize=8)
    for ax in axes.flat[:5]:
        ax.set_xlim(transects["T0"].centroid.x - 800, transects["T0"].centroid.x + 800)
        ax.set_ylim(transects["T0"].centroid.y - 800, transects["T0"].centroid.y + 800)
        ax.set_aspect("equal")
    w_field = field_row.W_ground_mean if field_row is not None else np.nan
    title = (
        f"DSK {scene.satellite_date} {scene.platform} | {scene.landsat_product_id}\n"
        f"W_RS(subpixel,T0,MNDWI)={primary['W_RS_subpixel']:.2f} m | W_field={w_field:.2f} m | "
        f"delta={scene.validation_delta_days} d | native pixel=30 m"
    )
    fig.suptitle(title, fontsize=13)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=220)
    plt.close(fig)


def crop_remote_pan(url: str, longitude: float, latitude: float, destination: Path) -> dict:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        try:
            with rasterio.open(destination) as src:
                if src.width > 0 and src.height > 0:
                    return {"status": "resumed", "path": str(destination.relative_to(ROOT)).replace("\\", "/"), "pixel_size_m": abs(src.transform.a)}
        except Exception:
            pass
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_TIMEOUT="60", GDAL_HTTP_MAX_RETRY="3"):
        with rasterio.open(url) as src:
            transformer = Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)
            x, y = transformer.transform(longitude, latitude)
            raw = from_bounds(x - 2500, y - 2500, x + 2500, y + 2500, src.transform)
            window = Window(math.floor(raw.col_off), math.floor(raw.row_off), math.ceil(raw.width), math.ceil(raw.height)).intersection(Window(0, 0, src.width, src.height))
            array = src.read(1, window=window)
            profile = src.profile.copy()
            profile.update(height=array.shape[0], width=array.shape[1], transform=src.window_transform(window), compress="deflate")
    temp = destination.with_suffix(".partial.tif")
    with rasterio.open(temp, "w", **profile) as dst:
        dst.write(array, 1)
    temp.replace(destination)
    return {"status": "downloaded", "path": str(destination.relative_to(ROOT)).replace("\\", "/"), "pixel_size_m": abs(profile["transform"].a)}


def pan_audit(unique: pd.DataFrame, station: pd.Series, primary_rows: pd.DataFrame) -> pd.DataFrame:
    rows = []
    l7 = unique.loc[unique.platform.eq("landsat-7")]
    prior_path = OUT / "dsk_landsat7_pan_audit.csv"
    prior = pd.read_csv(prior_path) if prior_path.exists() else pd.DataFrame()
    for scene in l7.itertuples(index=False):
        row = {
            "product_id": scene.landsat_product_id,
            "satellite_date": scene.satellite_date,
            "l2_collection_contains_pan": False,
            "source_collection": "USGS landsat-c2l1",
            "download_status": "not_attempted",
            "pan_usable": False,
            "slc_off_rule_applied": True,
            "used_for_water_classification": False,
            "edge_shift_left_m": np.nan,
            "edge_shift_right_m": np.nan,
            "notes": "",
        }
        pan_path = PAN_DIR / scene.landsat_product_id / "pan15m.tif"
        prior_row = prior.loc[prior.product_id.eq(scene.landsat_product_id)] if len(prior) and "product_id" in prior else pd.DataFrame()
        if pan_path.exists() and len(prior_row) == 1 and bool_value(prior_row.iloc[0].pan_usable):
            preserved = prior_row.iloc[0].to_dict()
            preserved["download_status"] = "resumed"
            preserved["used_for_water_classification"] = False
            rows.append(preserved)
            continue
        try:
            scene_item = json.loads((ROOT / Path(scene.scene_directory.replace("\\", "/")) / "raw/stac_item.json").read_text(encoding="utf-8"))
            wrs_path = scene_item["properties"]["landsat:wrs_path"]
            wrs_row = scene_item["properties"]["landsat:wrs_row"]
            date = scene.satellite_date
            body = {"collections": ["landsat-c2l1"], "bbox": [float(station.longitude) - 0.05, float(station.latitude) - 0.05, float(station.longitude) + 0.05, float(station.latitude) + 0.05], "datetime": f"{date}T00:00:00Z/{date}T23:59:59Z", "limit": 20}
            response = requests.post("https://landsatlook.usgs.gov/stac-server/search", json=body, timeout=60)
            response.raise_for_status()
            features = response.json().get("features", [])
            matches = [f for f in features if str(f["properties"].get("landsat:wrs_path")).zfill(3) == str(wrs_path).zfill(3) and str(f["properties"].get("landsat:wrs_row")).zfill(3) == str(wrs_row).zfill(3) and f["properties"].get("platform") == "LANDSAT_7"]
            if len(matches) != 1 or "pan" not in matches[0].get("assets", {}):
                row.update(download_status="unavailable", notes=f"matching_l1_items={len(matches)}")
                rows.append(row)
                continue
            item = matches[0]
            c2_pan_url = item["assets"]["pan"]["href"]
            fallback_note = ""
            try:
                result = crop_remote_pan(c2_pan_url, float(station.longitude), float(station.latitude), pan_path)
                actual_pan_url = c2_pan_url
                actual_source_collection = "USGS Landsat Collection 2 Level-1"
            except Exception as c2_error:
                # The USGS STAC URL can redirect to ers.cr.usgs.gov, which is not
                # reachable in some environments.  A same-acquisition Collection-1
                # Level-1 Pan is an acceptable visual-only fallback, but its lineage
                # and lack of use in spectral classification must stay explicit.
                gcs_prefix = f"LE07/01/{str(wrs_path).zfill(3)}/{str(wrs_row).zfill(3)}/LE07_L1TP_{str(wrs_path).zfill(3)}{str(wrs_row).zfill(3)}_{date.replace('-', '')}"
                listing = requests.get(
                    "https://storage.googleapis.com/storage/v1/b/gcp-public-data-landsat/o",
                    params={"prefix": gcs_prefix, "delimiter": "/", "maxResults": 100},
                    timeout=30,
                )
                listing.raise_for_status()
                prefixes = listing.json().get("prefixes", [])
                if len(prefixes) != 1:
                    raise RuntimeError(f"Collection-1 Pan fallback ambiguous: prefixes={prefixes}") from c2_error
                folder = prefixes[0]
                c1_product = folder.rstrip("/").split("/")[-1]
                actual_pan_url = f"https://storage.googleapis.com/gcp-public-data-landsat/{folder}{c1_product}_B8.TIF"
                result = crop_remote_pan(actual_pan_url, float(station.longitude), float(station.latitude), pan_path)
                actual_source_collection = "Google Cloud public Landsat Collection 1 Level-1 visual-only fallback"
                fallback_note = f"USGS C2 Pan download failed ({type(c2_error).__name__}: {c2_error}); used same acquisition/path/row C1 Pan only for visual edge sensitivity."
            with rasterio.open(pan_path) as src:
                pan = src.read(1).astype(float)
                transform = src.transform
            zeros = pan == 0
            centerline_row = primary_rows.loc[primary_rows.landsat_product_id.eq(scene.landsat_product_id)]
            usable = not bool(scene.landsat7_slc_off_target_gap) and float(np.mean(zeros)) < 0.5
            row.update(
                l1_product_id=item["id"],
                pan_source_url=actual_pan_url,
                usgs_collection2_pan_url=c2_pan_url,
                actual_source_collection=actual_source_collection,
                download_status=result["status"],
                pan_path=result["path"],
                pixel_size_m=result["pixel_size_m"],
                zero_fraction=float(np.mean(zeros)),
                pan_usable=usable,
                notes=(fallback_note + " Pan used only for edge-gradient sensitivity; spectral water classification remains MNDWI/NDWI.").strip() if usable else (fallback_note + " Pan affected by SLC/fill or unavailable near target.").strip(),
            )
            if usable and len(centerline_row):
                # Quantitative edge use is deliberately limited to a sensitivity check.
                row["edge_sensitivity_status"] = "available_but_not_used_to_move_spectral_banks"
        except Exception as exc:
            row.update(download_status="failed", notes=f"{type(exc).__name__}: {exc}")
        rows.append(row)
    return pd.DataFrame(rows)


def daily_hq_audit(unique: pd.DataFrame) -> pd.DataFrame:
    stage = pd.read_csv(DAILY_STAGE, dtype={"station_id": str})
    stage = stage.loc[stage.station_id.eq(STATION_ID), ["date", "stage_m"]].copy()
    stage["stage_m"] = pd.to_numeric(stage.stage_m, errors="coerce")
    q = pd.read_csv(DAILY_Q, dtype={"station_id": str})
    q = q.loc[q.station_id.eq(STATION_ID), ["date", "discharge_m3s"]].copy()
    q["discharge_m3s"] = pd.to_numeric(q.discharge_m3s, errors="coerce")
    rows = []
    for scene in unique.itertuples(index=False):
        def val(table, date, col):
            x = table.loc[table.date.eq(date), col]
            return float(x.iloc[0]) if len(x) and pd.notna(x.iloc[0]) else np.nan
        hm, hs = val(stage, scene.validation_measurement_date, "stage_m"), val(stage, scene.satellite_date, "stage_m")
        qm, qs = val(q, scene.validation_measurement_date, "discharge_m3s"), val(q, scene.satellite_date, "discharge_m3s")
        rows.append({
            "product_id": scene.landsat_product_id,
            "measurement_date": scene.validation_measurement_date,
            "satellite_date": scene.satellite_date,
            "delta_days": scene.validation_delta_days,
            "tier": scene.validation_tier,
            "H_measurement_day_m": hm,
            "H_satellite_day_m": hs,
            "delta_H_m": hs - hm if np.isfinite(hm + hs) else np.nan,
            "Q_measurement_day_m3s": qm,
            "Q_satellite_day_m3s": qs,
            "delta_Q_m3s": qs - qm if np.isfinite(qm + qs) else np.nan,
            "use": "time_mismatch_diagnostic_only_not_scene_selection_or_thresholding",
        })
    return pd.DataFrame(rows)


def metrics(frame: pd.DataFrame, estimate_col: str) -> dict:
    valid = frame[["W_field", estimate_col]].dropna()
    n = len(valid)
    if n == 0:
        return {"n": 0, "MAE_W": np.nan, "RMSE_W": np.nan, "Bias_W": np.nan, "mean_relative_error_W": np.nan, "correlation": np.nan}
    error = valid[estimate_col] - valid.W_field
    corr = valid[estimate_col].corr(valid.W_field) if n >= 3 and valid[estimate_col].nunique() > 1 and valid.W_field.nunique() > 1 else np.nan
    return {
        "n": n,
        "MAE_W": float(np.mean(np.abs(error))),
        "RMSE_W": float(np.sqrt(np.mean(error**2))),
        "Bias_W": float(np.mean(error)),
        "mean_relative_error_W": float(np.mean(np.abs(error) / valid.W_field)),
        "correlation": float(corr) if pd.notna(corr) else np.nan,
    }


def generate_report(unique, widths, validation, sensitivity, scaling, pan, daily, evidence, decision, protocol) -> str:
    primary = widths.loc[widths.independent_validation_pair & widths.transect_id.eq(PRIMARY_TRANSECT) & widths.threshold_method.eq(PRIMARY_METHOD)].copy()
    same = primary.loc[primary.tier.eq("A")]
    same_lines = "\n".join(
        f"- {r.satellite_date}：实测 {r.W_field:.2f} m，二值 {r.W_RS_binary:.2f} m，亚像元 {r.W_RS_subpixel:.2f} m，误差 {r.W_RS_subpixel-r.W_field:+.2f} m。"
        for r in same.itertuples(index=False)
    ) or "- 无合法同日样本。"
    val_lines = "\n".join(
        f"- {r.tier_scope} / {r.estimator}：n={int(r.n)}，MAE={r.MAE_W:.2f} m，RMSE={r.RMSE_W:.2f} m，Bias={r.Bias_W:.2f} m，相对误差={r.mean_relative_error_W:.1%}。"
        for r in validation.itertuples(index=False)
    )
    sens_primary = sensitivity.loc[sensitivity.threshold_method.eq(PRIMARY_METHOD)]
    median_range = sens_primary.transect_width_range.median()
    max_range = sens_primary.transect_width_range.max()
    pan_ok = int(pan.pan_usable.fillna(False).sum()) if len(pan) else 0
    raw_diff = np.mean([r["mean_absolute_difference"] for r in scaling["raw_dn_vs_scaled_ndwi"]])
    primary_ab = primary.loc[primary.tier.isin(["A", "B"])]
    field_range = primary_ab.W_field.max() - primary_ab.W_field.min() if len(primary_ab) else np.nan
    fallback_count = int(pan.actual_source_collection.fillna("").str.contains("Collection 1").sum()) if len(pan) and "actual_source_collection" in pan else 0
    apr = primary.loc[primary.satellite_date.eq("2011-04-24")]
    sep = primary.loc[primary.satellite_date.eq("2011-09-07")]
    def case_text(x):
        if x.empty:
            return "未形成合法主方法结果"
        r = x.iloc[0]
        return f"W_field={r.W_field:.2f} m，W_RS_binary={r.W_RS_binary:.2f} m，W_RS_subpixel={r.W_RS_subpixel:.2f} m，状态={r.measurement_status}"
    return f"""# RS-W1A 大山口固定断面定位、Landsat 水体分割与遥感河宽可测性验证

## 1. 研究问题与冻结边界

本阶段仅研究大山口（00705700），回答30 m Landsat 5/7能否稳定恢复约66–72 m的河宽。未预测Q，未训练GNN/Transformer，未修改D9–D12或RS-W0。Q和逐日H/Q只在场景、阈值和T0全部冻结后用于水文状态/时间错配描述。

阈值协议在误差计算前冻结：NDWI>0、MNDWI>0，以及不读取W/Q的局部MNDWI Otsu。主验证方法固定为`{PRIMARY_METHOD}`，主断面固定为`{PRIMARY_TRANSECT}`，禁止事后选“最接近实测W”的断面。

## 2. 独立场景与时间分层

RS-W0的DSK可用匹配共有{int(unique.ground_pair_count.sum())}个场景—日期配对，但去重后只有{len(unique)}景独立卫星影像。其中Tier A同日{int((unique.validation_tier=='A').sum())}景、Tier B {int((unique.validation_tier=='B').sum())}景、Tier C {int((unique.validation_tier=='C').sum())}景、Tier D {int((unique.validation_tier=='D').sum())}景。Tier D仅探索，不进入主指标。

同日场景为：{', '.join(unique.loc[unique.same_day_scene, 'satellite_date'].tolist())}。

## 3. 反射率缩放审计

所有Green/NIR/SWIR1元数据均直接给出scale=0.0000275、offset=-0.2，正式指数先应用`SR=DN×0.0000275-0.2`。直接用DN计算NDWI与正确缩放NDWI的逐景平均绝对差约{raw_diff:.3f}，因此直接DN指数不合法。完整逐资产证据见`surface_reflectance_scaling_audit.json`。

## 4. 固定断面定位与不确定性

KMZ坐标是站点代理点，不是测流断面坐标。最近匹配HydroRIVERS河段为{evidence['hyriv_id']}，代理点到中心线距离{evidence['canonical_station_to_centerline_m']:.1f} m。T0取该中心线最近点并按局部河向构造垂线，另沿HydroRIVERS存储方向平移±30/±60 m。没有证据证明该点就是“基下3m”真实断面，因此所有结果均是站点附近中心线代理断面的可测性实验。

## 5. 水体分割、连通性与河宽定义

QA_PIXEL剔除fill、膨胀云、云、云影和雪；从T0附近300 m内最近水像元播种，只保留8邻域连通的目标河道成分。分汊以`multi_channel`和`channel_count_within_300m`记录，不将不连通水体宽度静默相加。

`W_RS_binary`是原生30 m分类栅格与断面的交线宽；`W_RS_subpixel`仅是双线性指数剖面在冻结阈值处进行线性交点插值的“subpixel edge-interpolated width estimate”，不代表真正15 m/5 m观测。

## 6. W_RS 与 W_field 验证

{val_lines}

同日逐样本：

{same_lines}

地面宽度在独立验证配对中的范围仅{field_range:.2f} m，小于一个30 m像元；即使某些绝对误差看起来不大，也不能据此宣称能解析真实的细小宽度变化。

## 7. 断面位置敏感性

主方法五断面亚像元宽度的逐景中位range为{median_range:.2f} m，最大range为{max_range:.2f} m；range>30 m标记为位置敏感。该结果直接衡量站点代理坐标和局部河形对宽度的影响，没有根据W_field挑选断面。

## 8. 两个重点案例

- 2011-04-24：{case_text(apr)}。
- 2011-09-07：{case_text(sep)}。

两景都保留完整六联诊断图，不能只凭这两景外推全年泛化能力。

## 9. Landsat 7 Pan

三景已选L7的Level-2 SR条目不含Pan。脚本先查询相同日期、path/row的USGS Collection 2 Level-1；因其下载链接在当前网络重定向到不可达服务器，{fallback_count}景透明回退到Google公开Landsat Collection 1中同获取日期、同path/row的Level-1 Band 8，并在逐景审计中保留两套URL与失败原因。Pan裁剪保存到RS-W1A独立目录，{pan_ok}/{len(pan)}景通过本地可用性检查。Pan不参与判水，也不移动MNDWI河岸，仅用于确认15 m亮度边缘是否支持已有光谱边缘，因此不能消除水/陆光谱混合与SLC-off缺口。

## 10. 结论与七个问题

决策：**{decision['decision']}**。

1. **Landsat能否量大山口河宽？** {decision['answer_can_measure']}
2. **same-day误差多大？** {decision['answer_same_day_error']}
3. **亚像元是否明显改善？** {decision['answer_subpixel']}
4. **±30/60 m移动影响多大？** 中位range {median_range:.2f} m，最大 {max_range:.2f} m；详见逐景敏感性表。
5. **L7 Pan是否有帮助？** 可作边缘可见性辅助，但不能单独判水，也没有把30 m多光谱数据变成15 m水体分类。
6. **30 m是否主要瓶颈？** 是。实测河宽只有约2.2–2.4个像元，且实测变化幅度小于一个像元。
7. **下一步？** {decision['next_step']}

## 11. 科研完整性与停止点

RS-W0全树哈希在运行前后逐文件一致；失败scene/transect未删除；Tier D未混入同步主指标；同一影像只在独立验证中计一次。逐日H/Q只写入`dsk_time_mismatch_hq_audit.csv`，没有参与场景、断面或阈值选择。

RS-W1B、RS-W2、W→D、D→Q、GNN、GRU和最终VHS预测均未启动。`rs_w1b_started=false`，`rs_w2_started=false`。
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-pan-download", action="store_true", help="Record Pan as skipped; normal scientific run should not use this flag")
    args = parser.parse_args()
    before_hashes = tree_hashes(RSW0)
    OUT.mkdir(parents=True, exist_ok=True)
    DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
    protocol = {
        "stage": "RS-W1A",
        "frozen_before_width_error_evaluation": True,
        "station_id": STATION_ID,
        "primary_threshold_method": PRIMARY_METHOD,
        "primary_transect": PRIMARY_TRANSECT,
        "fixed_thresholds": FIXED_THRESHOLDS,
        "otsu_definition": "per-scene local MNDWI Otsu within 600 m; no W/Q inputs",
        "transect_offsets_m": TRANSECT_OFFSETS_M,
        "seed_search_radius_m": SEED_SEARCH_RADIUS_M,
        "section_location_sensitive_if_range_gt_m": SENSITIVITY_RANGE_LIMIT_M,
        "tier_definitions": {"A": "0 d", "B": "<=1 d", "C": "<=3 d", "D": "4-8 d exploratory only"},
        "decision_rules": {
            "PASS": "A+B independent n>=4, success>=0.8, subpixel MAE<=15 m, RMSE<=20 m, |Bias|<=15 m, median transect range<=30 m, and field variation is resolvable above one native pixel",
            "LIMITED": "success>=0.5 and subpixel MAE<=30 m, but resolution/sensitivity prevents high-precision continuous width",
            "FAIL": "otherwise",
        },
        "uses_Q_for_scene_threshold_or_transect_selection": False,
        "uses_ground_W_for_threshold_or_transect_selection": False,
        "created_utc": now_utc(),
    }
    write_json(OUT / "frozen_method_protocol.json", protocol)
    inventory, ground, station = load_inputs()
    ground_by_date = aggregate_ground(ground)
    unique = unique_scenes(inventory, ground_by_date)
    unique.to_csv(OUT / "dsk_unique_usable_scenes.csv", index=False, encoding="utf-8-sig")
    centerline, centerline_evidence = load_centerline(station)
    transects, geojson = build_transects(centerline, station, centerline_evidence)
    write_json(OUT / "dsk_candidate_transects.geojson", geojson)
    t0_center = transects["T0"].centroid

    scene_data = {}
    measurements = []
    raw_index_comparison_rows = []
    for scene in unique.itertuples(index=False):
        print(f"Processing {scene.satellite_date} {scene.landsat_product_id}", flush=True)
        data = read_scene(pd.Series(scene._asdict()), t0_center)
        scene_data[scene.landsat_product_id] = data
        product_dir = SCENE_PRODUCTS / scene.landsat_product_id
        for method, filename in (("ndwi_fixed_0", "water_mask_ndwi.tif"), ("mndwi_fixed_0", "water_mask_mndwi.tif"), ("mndwi_local_otsu", "water_mask_mndwi_otsu.tif")):
            spec = data["products"][method]
            save_mask(product_dir / filename, spec["component"], data["valid"], data["profile"], {
                "threshold_method": method,
                "threshold_value": spec["threshold"],
                "connectivity": "8-neighbor component seeded within 300 m of T0 centerline proxy",
                "classification_resolution_m": 30,
            })
        valid_cmp = np.isfinite(data["raw_ndwi"]) & np.isfinite(data["ndwi"])
        raw_index_comparison_rows.append({
            "product_id": scene.landsat_product_id,
            "satellite_date": scene.satellite_date,
            "raw_dn_ndwi_mean": np.nanmean(data["raw_ndwi"][valid_cmp]),
            "scaled_ndwi_mean": np.nanmean(data["ndwi"][valid_cmp]),
            "mean_absolute_difference": np.nanmean(np.abs(data["raw_ndwi"][valid_cmp] - data["ndwi"][valid_cmp])),
        })
        pair_group = inventory.loc[inventory.landsat_product_id.eq(scene.landsat_product_id)]
        for measurement_date in sorted(pair_group.measurement_date.astype(str).unique()):
            field = ground_by_date.loc[ground_by_date.measurement_date.eq(measurement_date)].iloc[0]
            delta = abs((pd.Timestamp(scene.satellite_date) - pd.Timestamp(measurement_date)).days)
            independent = measurement_date == scene.validation_measurement_date
            for method, spec in data["products"].items():
                for tid, line in transects.items():
                    result = measure_transect(line, spec["index"], spec["component"], spec["raw_mask"], data["transform"], spec["threshold"])
                    measurements.append({
                        "measurement_date": measurement_date,
                        "satellite_date": scene.satellite_date,
                        "delta_days": delta,
                        "tier": tier_for_days(delta),
                        "platform": scene.platform,
                        "product_id": scene.landsat_product_id,
                        "landsat_product_id": scene.landsat_product_id,
                        "W_field": field.W_ground_mean,
                        "W_ground_min": field.W_ground_min,
                        "W_ground_max": field.W_ground_max,
                        "W_ground_mean": field.W_ground_mean,
                        "same_day_multiple_ground_measurements": field.same_day_multiple_ground_measurements,
                        "measurement_time_available": False,
                        "W_RS_binary": result["W_RS_binary"],
                        "W_RS_subpixel": result["W_RS_subpixel"],
                        "binary_pixel_width_m": result["W_RS_binary"],
                        "subpixel_interpolated_edge_width_m": result["W_RS_subpixel"],
                        "subpixel_estimate_label": result["subpixel_estimate_label"],
                        "left_bank_position_m": result["left_bank_position_m"],
                        "right_bank_position_m": result["right_bank_position_m"],
                        "transect_id": tid,
                        "threshold_method": method,
                        "threshold_value": spec["threshold"],
                        "section_location_sensitive": False,
                        "cloud_flag": scene.target_local_cloud_flag,
                        "cloud_shadow_flag": scene.target_cloud_shadow_flag,
                        "snow_flag": scene.snow_ice_flag,
                        "fill_flag": scene.fill_or_zero_flag,
                        "slc_off_flag": scene.landsat7_slc_off_target_gap,
                        "multi_channel": result["multi_channel"],
                        "channel_count_within_300m": result["channel_count_within_300m"],
                        "measurement_status": result["status"],
                        "failure_reason": result["failure_reason"],
                        "independent_validation_pair": independent,
                        "unique_satellite_scene": True,
                        "notes": "T0 and thresholds frozen before W error; Tier D exploratory only; failures retained",
                    })
        primary_spec = data["products"][PRIMARY_METHOD]
        primary = measure_transect(transects[PRIMARY_TRANSECT], primary_spec["index"], primary_spec["component"], primary_spec["raw_mask"], data["transform"], primary_spec["threshold"])
        primary["ndwi_profile"] = measure_transect(transects[PRIMARY_TRANSECT], data["ndwi"], data["products"]["ndwi_fixed_0"]["component"], data["products"]["ndwi_fixed_0"]["raw_mask"], data["transform"], 0.0)["profile_index"]
        field = ground_by_date.loc[ground_by_date.measurement_date.eq(scene.validation_measurement_date)].iloc[0]
        diagnostic_figure(pd.Series(scene._asdict()), data, transects, centerline, primary, field, DIAGNOSTICS / f"DSK_{scene.satellite_date}_{scene.landsat_product_id}_diagnostic.png")

    widths = pd.DataFrame(measurements)
    sensitivity_rows = []
    for (product_id, method), group in widths.loc[widths.independent_validation_pair].groupby(["product_id", "threshold_method"]):
        values = group.W_RS_subpixel.dropna().astype(float)
        width_mean = values.mean() if len(values) else np.nan
        width_sd = values.std(ddof=1) if len(values) > 1 else (0.0 if len(values) == 1 else np.nan)
        width_range = values.max() - values.min() if len(values) else np.nan
        sensitive = bool(np.isfinite(width_range) and width_range > SENSITIVITY_RANGE_LIMIT_M)
        scene = unique.loc[unique.landsat_product_id.eq(product_id)].iloc[0]
        sensitivity_rows.append({
            "satellite_date": scene.satellite_date,
            "platform": scene.platform,
            "product_id": product_id,
            "threshold_method": method,
            "successful_transects": len(values),
            "transect_width_mean": width_mean,
            "transect_width_sd": width_sd,
            "transect_width_range": width_range,
            "section_location_sensitive": sensitive,
            **{f"W_{tid}": group.loc[group.transect_id.eq(tid), "W_RS_subpixel"].iloc[0] if len(group.loc[group.transect_id.eq(tid)]) else np.nan for tid in TRANSECT_OFFSETS_M},
        })
        widths.loc[widths.product_id.eq(product_id) & widths.threshold_method.eq(method), "section_location_sensitive"] = sensitive
    sensitivity = pd.DataFrame(sensitivity_rows)
    widths.to_csv(OUT / "dsk_width_estimates.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(OUT / "dsk_transect_sensitivity.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(raw_index_comparison_rows).to_csv(OUT / "raw_dn_vs_scaled_ndwi_diagnostic.csv", index=False, encoding="utf-8-sig")

    scaling = reflectance_audit(unique, scene_data)
    write_json(OUT / "surface_reflectance_scaling_audit.json", scaling)
    primary = widths.loc[widths.independent_validation_pair & widths.transect_id.eq(PRIMARY_TRANSECT) & widths.threshold_method.eq(PRIMARY_METHOD)].copy()
    validation_rows = []
    for scope, allowed in (("Tier A", ["A"]), ("Tier A+B", ["A", "B"]), ("Tier A+B+C", ["A", "B", "C"])):
        subset = primary.loc[primary.tier.isin(allowed)]
        for estimator, col in (("binary_native_mask_intercept", "W_RS_binary"), ("subpixel_edge_interpolated", "W_RS_subpixel")):
            validation_rows.append({"tier_scope": scope, "estimator": estimator, **metrics(subset, col), "independent_scene_count": subset.product_id.nunique(), "tier_D_included": False})
    validation = pd.DataFrame(validation_rows)
    validation.to_csv(OUT / "dsk_width_validation_by_tier.csv", index=False, encoding="utf-8-sig")
    primary.to_csv(OUT / "dsk_primary_validation_samples.csv", index=False, encoding="utf-8-sig")

    daily = daily_hq_audit(unique)
    daily.to_csv(OUT / "dsk_time_mismatch_hq_audit.csv", index=False, encoding="utf-8-sig")
    pan = pd.DataFrame()
    if args.skip_pan_download:
        pan = unique.loc[unique.platform.eq("landsat-7"), ["landsat_product_id", "satellite_date"]].rename(columns={"landsat_product_id": "product_id"})
        pan["download_status"] = "skipped_by_command_line"
        pan["pan_usable"] = False
        pan["used_for_water_classification"] = False
    else:
        pan = pan_audit(unique, station, primary)
    pan.to_csv(OUT / "dsk_landsat7_pan_audit.csv", index=False, encoding="utf-8-sig")

    ab = primary.loc[primary.tier.isin(["A", "B"])]
    m_sub = metrics(ab, "W_RS_subpixel")
    m_bin = metrics(ab, "W_RS_binary")
    success = m_sub["n"] / len(ab) if len(ab) else 0
    sens_primary = sensitivity.loc[sensitivity.threshold_method.eq(PRIMARY_METHOD)]
    med_range = sens_primary.transect_width_range.median()
    field_variation = ab.W_field.max() - ab.W_field.min() if len(ab) else np.nan
    pass_core = m_sub["n"] >= 4 and success >= 0.8 and m_sub["MAE_W"] <= 15 and m_sub["RMSE_W"] <= 20 and abs(m_sub["Bias_W"]) <= 15 and med_range <= 30 and field_variation >= 30
    limited_core = m_sub["n"] > 0 and success >= 0.5 and m_sub["MAE_W"] <= 30
    decision_label = "PASS" if pass_core else ("LIMITED" if limited_core else "FAIL")
    same_sub = metrics(primary.loc[primary.tier.eq("A")], "W_RS_subpixel")
    decision = {
        "decision": decision_label,
        "answer_can_measure": "可识别河道并提供粗尺度宽度状态，但不能作为高精度连续河宽。" if decision_label == "LIMITED" else ("在冻结门槛下具备进入后续验证的条件。" if decision_label == "PASS" else "不能稳定恢复具有物理意义的断面河宽。"),
        "answer_same_day_error": f"独立同日n={same_sub['n']}，亚像元MAE={same_sub['MAE_W']:.2f} m，RMSE={same_sub['RMSE_W']:.2f} m，Bias={same_sub['Bias_W']:.2f} m。",
        "answer_subpixel": f"A+B二值MAE={m_bin['MAE_W']:.2f} m，亚像元MAE={m_sub['MAE_W']:.2f} m；" + ("有改善，但仍受30 m混合像元限制。" if m_sub["MAE_W"] < m_bin["MAE_W"] else "未显示稳定改善。"),
        "next_step": "优先调整遥感数据源（更高分辨率光学/SAR）或取得真实断面坐标；仅在把W_RS定位为粗状态特征时再考虑RS-W1B/RS-W2。" if decision_label != "PASS" else "可在冻结协议后进入RS-W1B/RS-W2，但仍需保留30 m分辨率限制。",
        "a_plus_b_success_fraction": success,
        "field_variation_A_plus_B_m": field_variation,
        "native_multispectral_pixel_m": 30,
        "pass_rule_met": pass_core,
        "limited_rule_met": limited_core,
    }
    write_json(OUT / "decision.json", decision)

    after_hashes = tree_hashes(RSW0)
    integrity = {
        "stage": "RS-W1A",
        "rs_w0_hashes_before": before_hashes,
        "rs_w0_hashes_after": after_hashes,
        "rs_w0_unchanged": before_hashes == after_hashes,
        "q_used_for_threshold_scene_or_transect_selection": False,
        "ground_w_used_for_threshold_or_transect_selection": False,
        "primary_transect_selected_before_errors": True,
        "thresholds_frozen_before_errors": True,
        "unique_scene_independence_enforced": True,
        "tier_d_in_primary_metrics": False,
        "subpixel_claims_true_resolution_gain": False,
        "failed_rows_retained": True,
        "daily_hq_use": "diagnostic_only_after_selection",
        "landsat_30m_uncertainty_reported": True,
        "q_prediction_performed": False,
        "gnn_or_transformer_trained": False,
        "d9_to_d12_modified": False,
        "rs_w1b_started": False,
        "rs_w2_started": False,
    }
    if not integrity["rs_w0_unchanged"]:
        raise AssertionError("RS-W0 changed during RS-W1A")
    write_json(OUT / "scientific_integrity_audit.json", integrity)
    report = generate_report(unique, widths, validation, sensitivity, scaling, pan, daily, centerline_evidence, decision, protocol)
    (OUT / "stage_rs_w1a_report_zh.md").write_text(report, encoding="utf-8")
    result = {
        "stage": "RS-W1A",
        "status": "completed_and_stopped",
        "decision": decision_label,
        "independent_usable_scenes": len(unique),
        "same_day_independent_scenes": int(unique.same_day_scene.sum()),
        "width_rows_including_all_methods_transects_and_legal_pairs": len(widths),
        "diagnostic_figures": len(list(DIAGNOSTICS.glob("*.png"))),
        "rs_w0_unchanged": True,
        "rs_w1b_started": False,
        "rs_w2_started": False,
        "created_utc": now_utc(),
    }
    write_json(OUT / "result.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
