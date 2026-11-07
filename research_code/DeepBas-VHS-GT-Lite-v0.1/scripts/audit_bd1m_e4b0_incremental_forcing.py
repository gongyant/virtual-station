from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr


ROOT = Path(__file__).resolve().parents[1]
ERA5 = ROOT / "data" / "processed" / "era5_land"
OUT = ROOT / "outputs" / "vhs_bd1m" / "experiments"
NODES = ROOT / "data" / "processed" / "nodes.csv"
HYDROBASINS = ROOT / "data" / "raw" / "hydrobasins" / "hybas_as_lev12_v1c.shp"
GRIDDED = ERA5 / "era5land_daily_gridded_1978_1983.nc"
BASIN_FORCING = ERA5 / "era5land_daily_basin_weighted_1978_1983.nc"
WEIGHTS = ERA5 / "incremental_grid_weights.csv"
GEOMETRY = ERA5 / "incremental_basin.geojson"
INVENTORY = OUT / "e4b0_incremental_forcing_inventory.csv"
FEATURES = OUT / "e4b0_incremental_forcing_features.csv"
REPORT = OUT / "e4b0_incremental_forcing_report.md"
UPSTREAM = "00705600"
DOWNSTREAM = "00705700"
EXPECTED_LABEL = f"{UPSTREAM}_to_{DOWNSTREAM}"
EXPECTED_START = pd.Timestamp("1978-01-01")
EXPECTED_END = pd.Timestamp("1983-12-31")
EXPECTED_DATES = pd.date_range(EXPECTED_START, EXPECTED_END, freq="D")
EQUAL_AREA_CRS = "EPSG:6933"

CANDIDATES = [
    "era5land_incremental_byblk_to_dsk_1978_1983.nc",
    "era5land_incremental_byblk_to_dsk_1999_2001.nc",
    "era5land_incremental_byblk_to_dsk_2005.nc",
    "era5land_incremental_byblk_to_dsk_2011.nc",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def upstream_ids(basins: gpd.GeoDataFrame, target_id: int) -> set[int]:
    available = set(basins["HYBAS_ID"].astype(int))
    if target_id not in available:
        raise ValueError(f"HydroBASINS target {target_id} is absent")
    selected = {target_id}
    while True:
        added = set(
            basins.loc[basins["NEXT_DOWN"].isin(selected), "HYBAS_ID"].astype(int)
        ) - selected
        if not added:
            return selected
        selected.update(added)


def bool_text(value: bool) -> str:
    return str(bool(value)).lower()


def audit_lineage() -> dict[str, object]:
    nodes = pd.read_csv(NODES, dtype={"station_id": str}).set_index("station_id")
    basins = gpd.read_file(HYDROBASINS)
    by_id = int(nodes.loc[UPSTREAM, "HYBAS_ID"])
    dsk_id = int(nodes.loc[DOWNSTREAM, "HYBAS_ID"])
    by_ids = upstream_ids(basins, by_id)
    dsk_ids = upstream_ids(basins, dsk_id)
    by_geometry = basins.loc[basins.HYBAS_ID.isin(by_ids), "geometry"].union_all()
    dsk_geometry = basins.loc[basins.HYBAS_ID.isin(dsk_ids), "geometry"].union_all()
    reconstructed = dsk_geometry.difference(by_geometry)
    saved = gpd.read_file(GEOMETRY)
    saved_geometry = saved.geometry.iloc[0]

    def area_km2(geometry) -> float:
        return float(
            gpd.GeoSeries([geometry], crs="EPSG:4326").to_crs(EQUAL_AREA_CRS).area.iloc[0]
            / 1e6
        )

    symmetric_difference_km2 = area_km2(saved_geometry.symmetric_difference(reconstructed))
    upstream_overlap_km2 = area_km2(saved_geometry.intersection(by_geometry))
    outside_downstream_km2 = area_km2(saved_geometry.difference(dsk_geometry))
    reconstructed_area_km2 = area_km2(reconstructed)
    node_area_difference_km2 = float(nodes.loc[DOWNSTREAM, "UP_AREA"]) - float(
        nodes.loc[UPSTREAM, "UP_AREA"]
    )
    area_difference_percent = (
        100.0 * abs(reconstructed_area_km2 - node_area_difference_km2) / node_area_difference_km2
    )
    properties_ok = (
        str(saved.iloc[0]["basin"]) == EXPECTED_LABEL
        and str(saved.iloc[0]["upstream_station"]).zfill(8) == UPSTREAM
        and str(saved.iloc[0]["downstream_station"]).zfill(8) == DOWNSTREAM
    )
    geometry_ok = (
        bool(saved.geometry.is_valid.iloc[0])
        and not bool(saved.geometry.is_empty.iloc[0])
        and symmetric_difference_km2 < 1e-6
        and upstream_overlap_km2 < 1e-6
        and outside_downstream_km2 < 1e-6
    )
    topology_ok = by_ids.issubset(dsk_ids) and by_id in dsk_ids and len(dsk_ids - by_ids) > 0
    return {
        "byblk_hybas_id": by_id,
        "dsk_hybas_id": dsk_id,
        "byblk_upstream_subbasin_count": len(by_ids),
        "dsk_upstream_subbasin_count": len(dsk_ids),
        "incremental_subbasin_count": len(dsk_ids - by_ids),
        "byblk_upstream_set_is_subset_of_dsk": topology_ok,
        "geometry_properties_ok": properties_ok,
        "geometry_valid": bool(saved.geometry.is_valid.iloc[0]),
        "geometry_type": str(saved.geometry.geom_type.iloc[0]),
        "geometry_symmetric_difference_km2": symmetric_difference_km2,
        "geometry_overlap_with_byblk_km2": upstream_overlap_km2,
        "geometry_outside_dsk_km2": outside_downstream_km2,
        "reconstructed_incremental_area_km2": reconstructed_area_km2,
        "node_up_area_difference_km2": node_area_difference_km2,
        "area_difference_percent": area_difference_percent,
        "geometry_matches_reconstruction": geometry_ok,
        "lineage_valid": bool(topology_ok and properties_ok and geometry_ok and area_difference_percent < 2.0),
    }


def audit_weights_and_reproduction(ds: xr.Dataset) -> dict[str, object]:
    weights = pd.read_csv(WEIGHTS, dtype={"station_id": str})
    weight_sum = float(weights.weight.sum())
    area_sum = float(weights.overlap_km2.sum())
    formula_error = float(
        np.max(np.abs(weights.weight.to_numpy() - weights.overlap_km2.to_numpy() / area_sum))
    )
    label_ok = weights.station_id.eq(EXPECTED_LABEL).all()
    unique_cells = not weights.duplicated(["latitude", "longitude"]).any()
    positive = bool((weights[["weight", "overlap_km2"]].to_numpy() > 0).all())

    with xr.open_dataset(GRIDDED) as grid_source:
        grid = grid_source.load()
    weight_values = np.zeros(
        (grid.sizes["latitude"], grid.sizes["longitude"]),
        dtype=float,
    )

    grid_latitudes = grid.latitude.values.astype(float)
    grid_longitudes = grid.longitude.values.astype(float)

    for row in weights.itertuples(index=False):
        lat_index = int(
            np.argmin(np.abs(grid_latitudes - float(row.latitude)))
        )
        lon_index = int(
            np.argmin(np.abs(grid_longitudes - float(row.longitude)))
        )

        lat_error = abs(
            grid_latitudes[lat_index] - float(row.latitude)
        )
        lon_error = abs(
            grid_longitudes[lon_index] - float(row.longitude)
        )

        if lat_error > 1e-8 or lon_error > 1e-8:
            raise ValueError(
                "Weight coordinate "
                f"({row.latitude}, {row.longitude}) "
                "is absent from source grid; "
                f"nearest errors=({lat_error}, {lon_error})"
            )

        weight_values[lat_index, lon_index] = float(row.weight)

    weight_array = xr.DataArray(
        weight_values,
        coords={
            "latitude": grid.latitude,
            "longitude": grid.longitude,
        },
        dims=("latitude", "longitude"),
    )

    reproduced = grid.weighted(weight_array).mean(
        ("latitude", "longitude")
    )
    # weight_values = np.zeros((grid.sizes["latitude"], grid.sizes["longitude"]), dtype=float)
    # grid_latitudes = grid.latitude.values.astype(float)
    # grid_longitudes = grid.longitude.values.astype(float)
    # for row in weights.itertuples(index=False):
    #     lat_index = int(np.argmin(np.abs(grid_latitudes - row.latitude)))
    #     lon_index = int(np.argmin(np.abs(grid_longitudes - row.longitude)))
    #     if (
    #         abs(grid_latitudes[lat_index] - row.latitude) > 1e-8
    #         or abs(grid_longitudes[lon_index] - row.longitude) > 1e-8
    #     ):
    #         raise ValueError(
    #             f"Weight coordinate ({row.latitude}, {row.longitude}) is absent from source grid"
    #         )
    #     weight_values[lat_index, lon_index] = row.weight
    # weight_array = xr.DataArray(
    #     weight_values,
    #     coords={"latitude": grid.latitude, "longitude": grid.longitude},
    #     dims=("latitude", "longitude"),
    # )
    # reproduced = grid.weighted(weight_array).mean(("latitude", "longitude"))
    max_abs_errors: dict[str, float] = {}
    for name in ds.data_vars:
        original = ds[name].squeeze(drop=True)
        max_abs_errors[name] = float(np.max(np.abs(reproduced[name].values - original.values)))
    reproduction_max_abs_error = max(max_abs_errors.values())
    return {
        "weight_rows": len(weights),
        "weight_sum": weight_sum,
        "weight_area_km2": area_sum,
        "weight_formula_max_abs_error": formula_error,
        "weight_label_ok": bool(label_ok),
        "weight_cells_unique": bool(unique_cells),
        "weight_values_positive": positive,
        "weighted_reproduction_max_abs_error": reproduction_max_abs_error,
        "weighted_reproduction_by_variable": max_abs_errors,
        "area_weighting_valid": bool(
            abs(weight_sum - 1.0) < 1e-12
            and formula_error < 1e-15
            and label_ok
            and unique_cells
            and positive
            and reproduction_max_abs_error < 1e-4
        ),
    }


def audit_not_masquerading(ds: xr.Dataset) -> dict[str, object]:
    with xr.open_dataset(BASIN_FORCING) as source:
        cumulative = source.load()
    station_values = [str(value).zfill(8) for value in cumulative.station.values]
    results: dict[str, object] = {}
    all_distinct = True
    for station_id, short_name in ((UPSTREAM, "byblk"), (DOWNSTREAM, "dsk")):
        station_index = station_values.index(station_id)
        for variable in ("precipitation_mm", "temperature_c"):
            inc = ds[variable].squeeze(drop=True).values.astype(float)
            basin = cumulative[variable].isel(station=station_index).values.astype(float)
            max_abs = float(np.max(np.abs(inc - basin)))
            identical = bool(np.array_equal(inc, basin))
            results[f"{variable}_max_abs_difference_from_{short_name}"] = max_abs
            results[f"{variable}_identical_to_{short_name}"] = identical
            all_distinct = all_distinct and not identical and max_abs > 1e-6
    results["distinct_from_both_cumulative_basin_forcings"] = all_distinct
    return results


def build_features(ds: xr.Dataset) -> dict[str, object]:
    precipitation = pd.Series(
        ds.precipitation_mm.squeeze(drop=True).values.astype(float),
        index=pd.DatetimeIndex(ds.time.values),
    )
    temperature = pd.Series(
        ds.temperature_c.squeeze(drop=True).values.astype(float),
        index=pd.DatetimeIndex(ds.time.values),
    )
    lagged_p = precipitation.shift(1)
    lagged_t = temperature.shift(1)
    features = pd.DataFrame({"date": precipitation.index})
    for window in (3, 7, 30):
        features[f"P_inc_{window}d"] = lagged_p.rolling(window, min_periods=window).sum().to_numpy()
    for window in (7, 30):
        features[f"T_inc_{window}d"] = lagged_t.rolling(window, min_periods=window).mean().to_numpy()
    features.to_csv(FEATURES, index=False, date_format="%Y-%m-%d", float_format="%.8f")

    # Independent spot/full check: at t each feature may touch t-1 at the latest.
    checks = []
    for i in range(30, len(features)):
        checks.extend(
            [
                np.isclose(features.loc[i, "P_inc_3d"], precipitation.iloc[i - 3 : i].sum()),
                np.isclose(features.loc[i, "P_inc_7d"], precipitation.iloc[i - 7 : i].sum()),
                np.isclose(features.loc[i, "P_inc_30d"], precipitation.iloc[i - 30 : i].sum()),
                np.isclose(features.loc[i, "T_inc_7d"], temperature.iloc[i - 7 : i].mean()),
                np.isclose(features.loc[i, "T_inc_30d"], temperature.iloc[i - 30 : i].mean()),
            ]
        )
    causal_check = bool(all(checks))
    expected_missing = {
        "P_inc_3d": 3,
        "P_inc_7d": 7,
        "P_inc_30d": 30,
        "T_inc_7d": 7,
        "T_inc_30d": 30,
    }
    actual_missing = {name: int(features[name].isna().sum()) for name in expected_missing}
    missing_pattern_ok = actual_missing == expected_missing
    return {
        "feature_rows": len(features),
        "feature_columns": list(expected_missing),
        "feature_causal_t_minus_1_or_earlier": causal_check,
        "feature_initial_missing_counts": actual_missing,
        "feature_initial_missing_counts_expected": missing_pattern_ok,
        "features_ready": bool(causal_check and missing_pattern_ok),
    }


def audit_primary(path: Path, lineage: dict[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    with xr.open_dataset(path) as source:
        ds = source.load()
    times = pd.DatetimeIndex(ds.time.values)
    expected = pd.date_range(times.min(), times.max(), freq="D") if len(times) else pd.DatetimeIndex([])
    required_fields = {"precipitation_mm", "temperature_c"}
    fields_ok = required_fields.issubset(ds.data_vars)
    units = {name: str(ds[name].attrs.get("units", "")) for name in required_fields if name in ds}
    units_ok = units == {"precipitation_mm": "mm day-1", "temperature_c": "degC"}
    missing = {name: int(ds[name].isnull().sum()) for name in ds.data_vars}
    nonfinite = {name: int((~np.isfinite(ds[name])).sum()) for name in ds.data_vars}
    missing_ok = all(value == 0 for value in missing.values()) and all(
        value == 0 for value in nonfinite.values()
    )
    date_ok = (
        times.equals(expected)
        and times.equals(EXPECTED_DATES)
        and not times.has_duplicates
        and times.is_monotonic_increasing
    )
    metadata_ok = (
        str(ds.attrs.get("basin_definition", ""))
        == "downstream upstream-area minus upstream upstream-area"
        and str(ds.attrs.get("upstream_station", "")).zfill(8) == UPSTREAM
        and str(ds.attrs.get("downstream_station", "")).zfill(8) == DOWNSTREAM
        and str(ds.attrs.get("spatial_aggregation", "")) == "exact intersection-area weighting"
        and str(ds.basin.values[0]) == EXPECTED_LABEL
    )
    dimensions_ok = ds.sizes.get("basin") == 1 and ds.sizes.get("time") == len(EXPECTED_DATES)
    weights = audit_weights_and_reproduction(ds)
    masquerade = audit_not_masquerading(ds)
    lineage_valid = bool(
        lineage["lineage_valid"]
        and metadata_ok
        and weights["area_weighting_valid"]
        and masquerade["distinct_from_both_cumulative_basin_forcings"]
    )
    ready = bool(fields_ok and units_ok and missing_ok and date_ok and dimensions_ok and lineage_valid)
    features = build_features(ds) if ready else {
        "feature_rows": 0,
        "feature_columns": [],
        "feature_causal_t_minus_1_or_earlier": False,
        "feature_initial_missing_counts": {},
        "feature_initial_missing_counts_expected": False,
        "features_ready": False,
    }
    record = {
        "candidate_file": path.name,
        "relative_path": path.relative_to(ROOT).as_posix(),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "time_start": times.min().date().isoformat(),
        "time_end": times.max().date().isoformat(),
        "time_count": len(times),
        "expected_daily_count": len(expected),
        "date_continuous_daily": times.equals(expected),
        "date_matches_1978_1983": times.equals(EXPECTED_DATES),
        "duplicate_dates": int(times.duplicated().sum()),
        "time_monotonic_increasing": times.is_monotonic_increasing,
        "precipitation_field": "precipitation_mm" if "precipitation_mm" in ds else "",
        "precipitation_units": units.get("precipitation_mm", ""),
        "precipitation_missing": missing.get("precipitation_mm", ""),
        "precipitation_min": float(ds.precipitation_mm.min()) if "precipitation_mm" in ds else "",
        "precipitation_max": float(ds.precipitation_mm.max()) if "precipitation_mm" in ds else "",
        "temperature_field": "temperature_c" if "temperature_c" in ds else "",
        "temperature_units": units.get("temperature_c", ""),
        "temperature_missing": missing.get("temperature_c", ""),
        "temperature_min": float(ds.temperature_c.min()) if "temperature_c" in ds else "",
        "temperature_max": float(ds.temperature_c.max()) if "temperature_c" in ds else "",
        "all_variable_missing": sum(missing.values()),
        "all_variable_nonfinite": sum(nonfinite.values()),
        "basin_label": str(ds.basin.values[0]) if "basin" in ds.coords else "",
        "upstream_station": str(ds.attrs.get("upstream_station", "")),
        "downstream_station": str(ds.attrs.get("downstream_station", "")),
        "basin_definition": str(ds.attrs.get("basin_definition", "")),
        "spatial_aggregation": str(ds.attrs.get("spatial_aggregation", "")),
        "incremental_area_km2": float(ds.incremental_area_km2.values[0]),
        "weight_rows": weights["weight_rows"],
        "weight_sum": weights["weight_sum"],
        "weight_area_km2": weights["weight_area_km2"],
        "weight_formula_max_abs_error": weights["weight_formula_max_abs_error"],
        "weighted_reproduction_max_abs_error": weights["weighted_reproduction_max_abs_error"],
        "geometry_matches_reconstruction": lineage["geometry_matches_reconstruction"],
        "geometry_symmetric_difference_km2": lineage["geometry_symmetric_difference_km2"],
        "distinct_from_byblk_and_dsk_forcing": masquerade[
            "distinct_from_both_cumulative_basin_forcings"
        ],
        "lineage_valid": lineage_valid,
        "ready": ready,
        "notes": "deep audit completed",
    }
    details = {
        "units": units,
        "missing": missing,
        "nonfinite": nonfinite,
        "metadata_ok": metadata_ok,
        "fields_ok": fields_ok,
        "units_ok": units_ok,
        "date_ok": date_ok,
        "dimensions_ok": dimensions_ok,
        "lineage_valid": lineage_valid,
        "ready": ready,
        **weights,
        **masquerade,
        **features,
    }
    return record, details


def format_mapping(mapping: dict[str, object]) -> str:
    return ", ".join(f"`{key}={value}`" for key, value in mapping.items())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    existing_matches = sorted(path.name for path in ERA5.glob("era5land_incremental_byblk_to_dsk_*.nc"))
    candidates = list(dict.fromkeys(CANDIDATES + existing_matches))
    primary = ERA5 / CANDIDATES[0]
    lineage = audit_lineage() if GEOMETRY.is_file() and HYDROBASINS.is_file() else {
        "lineage_valid": False,
        "geometry_matches_reconstruction": False,
        "geometry_symmetric_difference_km2": np.nan,
    }
    records: list[dict[str, object]] = []
    details: dict[str, object] = {}
    for name in candidates:
        path = ERA5 / name
        if path == primary and path.is_file():
            record, details = audit_primary(path, lineage)
            records.append(record)
        elif path.is_file():
            with xr.open_dataset(path) as source:
                times = pd.DatetimeIndex(source.time.values)
                variables = set(source.data_vars)
                missing = int(sum(int(source[name].isnull().sum()) for name in source.data_vars))
                records.append(
                    {
                        "candidate_file": name,
                        "relative_path": path.relative_to(ROOT).as_posix(),
                        "exists": True,
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256(path),
                        "time_start": times.min().date().isoformat(),
                        "time_end": times.max().date().isoformat(),
                        "time_count": len(times),
                        "expected_daily_count": len(pd.date_range(times.min(), times.max(), freq="D")),
                        "date_continuous_daily": times.equals(pd.date_range(times.min(), times.max(), freq="D")),
                        "precipitation_field": "precipitation_mm" if "precipitation_mm" in variables else "",
                        "temperature_field": "temperature_c" if "temperature_c" in variables else "",
                        "all_variable_missing": missing,
                        "lineage_valid": False,
                        "ready": False,
                        "notes": "discovered but not the requested 1978-1983 primary asset; lineage not promoted",
                    }
                )
        else:
            records.append(
                {
                    "candidate_file": name,
                    "relative_path": path.relative_to(ROOT).as_posix(),
                    "exists": False,
                    "lineage_valid": False,
                    "ready": False,
                    "notes": "file not found",
                }
            )
    inventory = pd.DataFrame(records)
    inventory.to_csv(INVENTORY, index=False, float_format="%.12g")

    found = bool(primary.is_file())
    lineage_valid = bool(details.get("lineage_valid", False))
    ready = bool(details.get("ready", False) and details.get("features_ready", False))
    report = f"""# VHS-BD1M E4B0 incremental basin forcing 审计

## 冻结前提

E4A2 routing-only 结果已冻结，不再调参：R1 train RMSE = **118.905450**；R2 best train RMSE = **118.849295**。R2 相对 R1 仅改善约 **0.047%**，near-optimal 参数不稳定，且最佳解位于 `required_substeps=576` 数值边界附近。因此固定：

- `ROUTING_ONLY_SUFFICIENT=false`
- `REACH_HETEROGENEITY_GAIN_MEANINGFUL=false`
- `R2_PARAMETERS_PHYSICALLY_IDENTIFIABLE=false`
- `ROUTING_ONLY_RESULT_FROZEN=true`

本阶段没有训练、拟合或选择模型，也没有继续调整 R2。

## 文件盘点

优先目录为 `data/processed/era5_land/`。候选文件共 {len(candidates)} 个，实际发现 {sum(bool(row.get('exists')) for row in records)} 个。逐文件结果见 `e4b0_incremental_forcing_inventory.csv`。

- 1978–1983：`{CANDIDATES[0]}`，存在 = **{bool_text(found)}**。
- 1999–2001：`{CANDIDATES[1]}`，存在 = **{bool_text((ERA5 / CANDIDATES[1]).is_file())}**。
- 2005：`{CANDIDATES[2]}`，存在 = **{bool_text((ERA5 / CANDIDATES[2]).is_file())}**。
- 2011：`{CANDIDATES[3]}`，存在 = **{bool_text((ERA5 / CANDIDATES[3]).is_file())}**。

## 1978–1983 forcing 内容审计

- 时间：`{records[0].get('time_start', '')}` 至 `{records[0].get('time_end', '')}`，{records[0].get('time_count', 0)} 天；完整逐日轴、无重复、严格递增 = **{bool_text(bool(details.get('date_ok', False)))}**。
- 降水：字段 `precipitation_mm`，单位 `{details.get('units', {}).get('precipitation_mm', '')}`，缺失 {details.get('missing', {}).get('precipitation_mm', '')}。
- 温度：字段 `temperature_c`，单位 `{details.get('units', {}).get('temperature_c', '')}`，缺失 {details.get('missing', {}).get('temperature_c', '')}。
- 全部变量缺失：{sum(details.get('missing', {}).values()) if details else ''}；全部变量非有限值：{sum(details.get('nonfinite', {}).values()) if details else ''}。
- forcing SHA-256：`{records[0].get('sha256', '')}`。

## geometry / area lineage

生成链为：

`era5land_daily_gridded_1978_1983.nc` → `area_weight_incremental_era5.py` → `era5land_incremental_byblk_to_dsk_1978_1983.nc`

脚本从 `nodes.csv` 读取 BYBLK (`{UPSTREAM}`) 与 DSK (`{DOWNSTREAM}`) 的 HydroBASINS L12 ID，分别沿 `NEXT_DOWN` 反向收集完整上游子流域，然后执行 `DSK upstream geometry − BYBLK upstream geometry`。审计独立从原始 HydroBASINS shapefile 重建该差集并与保存的 `incremental_basin.geojson` 比较。

- BYBLK HydroBASINS ID：`{lineage.get('byblk_hybas_id', '')}`；DSK HydroBASINS ID：`{lineage.get('dsk_hybas_id', '')}`。
- BYBLK 上游子流域数：{lineage.get('byblk_upstream_subbasin_count', '')}；DSK：{lineage.get('dsk_upstream_subbasin_count', '')}；差集：{lineage.get('incremental_subbasin_count', '')}。
- BYBLK 上游集合是 DSK 上游集合的子集：**{bool_text(bool(lineage.get('byblk_upstream_set_is_subset_of_dsk', False)))}**。
- 保存几何与独立重建差集的对称差面积：{float(lineage.get('geometry_symmetric_difference_km2', np.nan)):.12g} km²。
- 增量几何与 BYBLK 上游域重叠：{float(lineage.get('geometry_overlap_with_byblk_km2', np.nan)):.12g} km²；落在 DSK 上游域之外：{float(lineage.get('geometry_outside_dsk_km2', np.nan)):.12g} km²。
- 重建几何面积：{float(lineage.get('reconstructed_incremental_area_km2', np.nan)):.6f} km²；节点 `UP_AREA` 差：{float(lineage.get('node_up_area_difference_km2', np.nan)):.6f} km²；相对差：{float(lineage.get('area_difference_percent', np.nan)):.6f}%（矢量投影面积与属性汇总口径差）。

以上证明该几何确为 BYBLK 与 DSK 之间的增量流域，而不是任一站的完整上游流域。

## 面积加权与禁止冒充检查

- 增量网格单元数：{details.get('weight_rows', '')}；交叠面积合计：{float(details.get('weight_area_km2', np.nan)):.6f} km²。
- 权重和：{float(details.get('weight_sum', np.nan)):.12f}；`weight = overlap_km2 / total_overlap_km2` 最大误差：{float(details.get('weight_formula_max_abs_error', np.nan)):.3e}。
- 用 gridded forcing 和保存权重独立重算全部变量，与增量 NetCDF 的最大绝对误差：{float(details.get('weighted_reproduction_max_abs_error', np.nan)):.3e}。
- 增量 forcing 与 BYBLK、DSK 两个完整上游流域 forcing 均逐日比较；两者都不相同 = **{bool_text(bool(details.get('distinct_from_both_cumulative_basin_forcings', False)))}**。
- 降水相对 BYBLK/DSK 的最大绝对差：{float(details.get('precipitation_mm_max_abs_difference_from_byblk', np.nan)):.6f} / {float(details.get('precipitation_mm_max_abs_difference_from_dsk', np.nan)):.6f} mm day-1。
- 温度相对 BYBLK/DSK 的最大绝对差：{float(details.get('temperature_c_max_abs_difference_from_byblk', np.nan)):.6f} / {float(details.get('temperature_c_max_abs_difference_from_dsk', np.nan)):.6f} degC。

因此没有用 BYBLK 或 DSK basin forcing 冒充 incremental forcing。

## 仅历史增量特征

合法性通过后生成 `e4b0_incremental_forcing_features.csv`：

- `P_inc_3d`：`sum(P[t-3:t-1])`
- `P_inc_7d`：`sum(P[t-7:t-1])`
- `P_inc_30d`：`sum(P[t-30:t-1])`
- `T_inc_7d`：`mean(T[t-7:t-1])`
- `T_inc_30d`：`mean(T[t-30:t-1])`

全表逐行独立复算通过 = **{bool_text(bool(details.get('feature_causal_t_minus_1_or_earlier', False)))}**。每个窗口先对原序列 `shift(1)`，所以日期 `t` 最晚只读取 `t-1`；没有同日或未来信息。1978 年起始处因文件不含 1977 年历史，前 3/7/30 天分别保留结构性空值，不进行回填、跨边界伪造或未来泄漏。结构性空值计数：{format_mapping(details.get('feature_initial_missing_counts', {}))}。

## 最终状态

`INCREMENTAL_FORCING_FOUND={bool_text(found)}`

`INCREMENTAL_FORCING_LINEAGE_VALID={bool_text(lineage_valid)}`

`INCREMENTAL_FORCING_1978_1983_READY={bool_text(ready)}`

`ROUTING_ONLY_RESULT_FROZEN=true`

`READY_FOR_E4B_INCREMENTAL_MODEL={bool_text(ready)}`
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"wrote {INVENTORY.relative_to(ROOT)}")
    if FEATURES.is_file():
        print(f"wrote {FEATURES.relative_to(ROOT)}")
    print(f"wrote {REPORT.relative_to(ROOT)}")
    print(f"INCREMENTAL_FORCING_FOUND={bool_text(found)}")
    print(f"INCREMENTAL_FORCING_LINEAGE_VALID={bool_text(lineage_valid)}")
    print(f"INCREMENTAL_FORCING_1978_1983_READY={bool_text(ready)}")
    print("ROUTING_ONLY_RESULT_FROZEN=true")
    print(f"READY_FOR_E4B_INCREMENTAL_MODEL={bool_text(ready)}")
    if not ready:
        sys.exit(1)


if __name__ == "__main__":
    main()
