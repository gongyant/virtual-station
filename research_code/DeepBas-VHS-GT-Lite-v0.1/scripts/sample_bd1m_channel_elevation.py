"""Sample FABDEM along the frozen HydroRIVERS BYBLK-to-DSK path."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString
from shapely.ops import transform

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
RIVER_SHP = ROOT / "data/raw/hydrorivers/HydroRIVERS_v10_as.shp"
DEM = ROOT / "data/raw/dem/FABDEM_BYBLK_DSK.tif"
OUTPUT = ROOT / "outputs/vhs_bd1m/channel_elevation_profile.csv"
AUDIT = ROOT / "outputs/vhs_bd1m/channel_elevation_sampling_audit.md"
SPACING_M = 100.0


def as_line(geometry: LineString | MultiLineString) -> LineString:
    if isinstance(geometry, LineString):
        return geometry
    parts = list(geometry.geoms)
    coordinates = list(parts[0].coords)
    for part in parts[1:]:
        coordinates.extend(list(part.coords))
    return LineString(coordinates)


def oriented_lines(lines: list[LineString]) -> list[LineString]:
    candidates = [(line, LineString(list(line.coords)[::-1])) for line in lines]
    costs = [{0: 0.0, 1: 0.0}]
    parents: list[dict[int, int]] = [{}]
    for index in range(1, len(lines)):
        current_cost: dict[int, float] = {}
        current_parent: dict[int, int] = {}
        for state, current in enumerate(candidates[index]):
            best_parent, best_cost = min(
                (
                    (
                        previous_state,
                        costs[index - 1][previous_state]
                        + candidates[index - 1][previous_state].boundary.geoms[1].distance(
                            current.boundary.geoms[0]
                        ),
                    )
                    for previous_state in (0, 1)
                ),
                key=lambda item: item[1],
            )
            current_cost[state] = best_cost
            current_parent[state] = best_parent
        costs.append(current_cost)
        parents.append(current_parent)
    state = min(costs[-1], key=costs[-1].get)
    result: list[LineString] = [lines[-1]] * len(lines)
    for index in range(len(lines) - 1, -1, -1):
        result[index] = candidates[index][state]
        if index:
            state = parents[index][state]
    return result


def sample_distances(length_m: float) -> list[float]:
    if length_m <= 0:
        return [0.0]
    distances = list(np.arange(0.0, length_m, SPACING_M))
    if not distances or not math.isclose(distances[-1], length_m, abs_tol=0.01):
        distances.append(length_m)
    return distances


def main() -> None:
    with FREEZE.open("r", encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    if not frozen:
        raise ValueError("Frozen path is empty")

    ids = [row["reach_id"] for row in frozen]
    river = gpd.read_file(RIVER_SHP, engine="pyogrio")
    river["HYRIV_ID_STR"] = river["HYRIV_ID"].astype(str).str.replace(
        r"\.0$", "", regex=True
    )
    selected = river.set_index("HYRIV_ID_STR").loc[ids].reset_index()
    geometries = oriented_lines([as_line(geometry) for geometry in selected.geometry])

    with rasterio.open(DEM) as dem:
        dem_crs = dem.crs
        resolution_m = (abs(dem.res[0]) + abs(dem.res[1])) / 2 * 111320
        sampling_crs = "EPSG:32645"
        to_sampling = Transformer.from_crs(
            "EPSG:4326", sampling_crs, always_xy=True
        ).transform
        from_sampling = Transformer.from_crs(
            sampling_crs, dem_crs, always_xy=True
        ).transform
        to_wgs84 = Transformer.from_crs(
            dem_crs, "EPSG:4326", always_xy=True
        ).transform
        sample_rows: list[dict[str, object]] = []
        missing = 0
        invalid = 0
        cumulative_m = 0.0

        for row, geometry in zip(frozen, geometries):
            projected = transform(to_sampling, geometry)
            distances = sample_distances(projected.length)
            points = [projected.interpolate(distance) for distance in distances]
            dem_points = [transform(from_sampling, point) for point in points]
            coordinates = [(point.x, point.y) for point in dem_points]
            values = list(dem.sample(coordinates, indexes=1, masked=True))
            for local_m, point, value in zip(distances, points, values):
                wgs_point = transform(
                    Transformer.from_crs(
                        sampling_crs, "EPSG:4326", always_xy=True
                    ).transform,
                    point,
                )
                masked = np.ma.is_masked(value) or not np.isfinite(float(value[0]))
                elevation = None if masked else float(value[0])
                if masked:
                    missing += 1
                elif elevation < -500 or elevation > 9000:
                    invalid += 1
                sample_rows.append(
                    {
                        "reach_id": row["reach_id"],
                        "river_id": row["river_id"],
                        "distance_km": f"{cumulative_m / 1000 + local_m / 1000:.6f}",
                        "longitude": f"{wgs_point.x:.8f}",
                        "latitude": f"{wgs_point.y:.8f}",
                        "elevation_m": "" if elevation is None else f"{elevation:.3f}",
                        "dem_source": str(DEM.relative_to(ROOT)),
                        "dem_resolution": f"{resolution_m:.2f} m",
                        "sample_spacing": f"{SPACING_M:.0f} m",
                    }
                )
            cumulative_m += projected.length

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(sample_rows[0]))
        writer.writeheader()
        writer.writerows(sample_rows)

    missing_ratio = missing / len(sample_rows) if sample_rows else 1.0
    report = f"""# BD1M 沿河道高程采样审计

## 结果

- 输入冻结路径：`{FREEZE.relative_to(ROOT)}`
- DEM：`{DEM.relative_to(ROOT)}`
- 路径：BYBLK `40255730` → DSK `40282189`
- reach 数量：{len(frozen)}
- 采样间隔：{SPACING_M:.0f} m
- 采样数量：{len(sample_rows)}
- DEM 分辨率：约 {resolution_m:.2f} m
- 缺失采样点：{missing}
- 缺失比例：{missing_ratio:.6%}
- 异常高程点：{invalid}
- 水库区域异常：未单独判定；当前仅进行了 NoData 与物理范围检查

## 异常定义

异常高程点定义为有效数值不在 `[-500, 9000] m` 范围内；NoData 单独计入缺失点，不写入高程值。

## 约束

本阶段仅沿冻结 HydroRIVERS 中心线进行 DEM 高程采样；未计算坡度、坡降或任何模型结果，未修改冻结路径。
"""
    AUDIT.write_text(report, encoding="utf-8")
    print(
        f"samples={len(sample_rows)} missing={missing} "
        f"missing_ratio={missing_ratio:.6%} invalid={invalid}"
    )


if __name__ == "__main__":
    main()
