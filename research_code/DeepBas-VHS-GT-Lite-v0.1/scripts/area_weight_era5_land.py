from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import box


DEFAULT_STATIONS = ["00705600", "00705700"]
EQUAL_AREA_CRS = "EPSG:6933"


def coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2:
        raise ValueError("Grid coordinates must be one-dimensional with at least two values")
    if not np.all(np.diff(values) > 0):
        raise ValueError("coordinate_edges expects strictly increasing coordinates")
    middle = (values[:-1] + values[1:]) / 2.0
    return np.concatenate(
        ([values[0] - (middle[0] - values[0])], middle, [values[-1] + (values[-1] - middle[-1])])
    )


def upstream_ids(basins: gpd.GeoDataFrame, target_id: int) -> set[int]:
    available = set(basins["HYBAS_ID"].astype(int))
    if target_id not in available:
        raise ValueError(f"Target HydroBASINS ID {target_id} is absent")
    selected = {target_id}
    while True:
        added = set(
            basins.loc[basins["NEXT_DOWN"].isin(selected), "HYBAS_ID"].astype(int)
        ) - selected
        if not added:
            return selected
        selected.update(added)


def make_grid(latitude: np.ndarray, longitude: np.ndarray) -> gpd.GeoDataFrame:
    lat_sorted = np.sort(np.asarray(latitude, dtype=float))
    lon_sorted = np.sort(np.asarray(longitude, dtype=float))
    lat_edges = coordinate_edges(lat_sorted)
    lon_edges = coordinate_edges(lon_sorted)
    records = []
    for lat_index, lat in enumerate(lat_sorted):
        for lon_index, lon in enumerate(lon_sorted):
            records.append(
                {
                    "latitude": lat,
                    "longitude": lon,
                    "geometry": box(
                        lon_edges[lon_index],
                        lat_edges[lat_index],
                        lon_edges[lon_index + 1],
                        lat_edges[lat_index + 1],
                    ),
                }
            )
    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def basin_weights(
    grid: gpd.GeoDataFrame, basin_geometry, station_id: str
) -> pd.DataFrame:
    basin_equal_area = gpd.GeoSeries([basin_geometry], crs="EPSG:4326").to_crs(
        EQUAL_AREA_CRS
    ).iloc[0]
    candidate = grid[grid.intersects(basin_geometry)].to_crs(EQUAL_AREA_CRS).copy()
    candidate["overlap_km2"] = candidate.geometry.intersection(basin_equal_area).area / 1e6
    candidate = candidate[candidate["overlap_km2"] > 0].copy()
    total = float(candidate["overlap_km2"].sum())
    if total <= 0:
        raise ValueError(f"No ERA5-Land cells overlap station {station_id} basin")
    candidate["weight"] = candidate["overlap_km2"] / total
    candidate["station_id"] = station_id
    return candidate[["station_id", "latitude", "longitude", "overlap_km2", "weight"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create exact-area-weighted ERA5-Land daily basin series."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/processed/era5_land/era5land_daily_gridded_1978_1983.nc"),
    )
    parser.add_argument(
        "--hydrobasins",
        type=Path,
        default=Path("data/raw/hydrobasins/hybas_as_lev12_v1c.shp"),
    )
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--station-ids", nargs="+", default=DEFAULT_STATIONS)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc"
        ),
    )
    parser.add_argument(
        "--weights-output",
        type=Path,
        default=Path("data/processed/era5_land/basin_grid_weights.csv"),
    )
    parser.add_argument(
        "--basins-output",
        type=Path,
        default=Path("data/processed/era5_land/target_upstream_basins.geojson"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str})
    basins = gpd.read_file(args.hydrobasins)
    required_columns = {"HYBAS_ID", "NEXT_DOWN", "SUB_AREA", "UP_AREA", "geometry"}
    missing_columns = required_columns - set(basins.columns)
    if missing_columns:
        raise ValueError(f"HydroBASINS fields missing: {sorted(missing_columns)}")

    with xr.open_dataset(args.input) as source:
        dataset = source.load()
    if not {"time", "latitude", "longitude"}.issubset(dataset.dims):
        raise ValueError("Input must contain time, latitude, and longitude dimensions")
    grid = make_grid(dataset.latitude.values, dataset.longitude.values)

    weighted_datasets = []
    all_weights = []
    basin_records = []
    for station_id in args.station_ids:
        station = nodes.loc[nodes["station_id"].eq(station_id)]
        if len(station) != 1:
            raise ValueError(f"Expected exactly one nodes.csv row for station {station_id}")
        station = station.iloc[0]
        target_id = int(station["HYBAS_ID"])
        selected_ids = upstream_ids(basins, target_id)
        selected = basins[basins["HYBAS_ID"].isin(selected_ids)]
        basin_geometry = selected.geometry.union_all()
        weights = basin_weights(grid, basin_geometry, station_id)
        all_weights.append(weights)

        weight_array = xr.DataArray(
            np.zeros((dataset.sizes["latitude"], dataset.sizes["longitude"])),
            coords={"latitude": dataset.latitude, "longitude": dataset.longitude},
            dims=("latitude", "longitude"),
        )
        for row in weights.itertuples(index=False):
            weight_array.loc[
                {"latitude": row.latitude, "longitude": row.longitude}
            ] = row.weight
        station_daily = dataset.weighted(weight_array).mean(("latitude", "longitude"))
        station_daily = station_daily.expand_dims(station=[station_id])
        station_daily = station_daily.assign_coords(
            station_name=("station", [str(station["station_name"])]),
            station_longitude=("station", [float(station["longitude"])]),
            station_latitude=("station", [float(station["latitude"])]),
            hydrobasins_id=("station", [target_id]),
            hydrobasins_up_area_km2=("station", [float(station["UP_AREA"])]),
            weighted_polygon_area_km2=("station", [float(weights["overlap_km2"].sum())]),
        )
        weighted_datasets.append(station_daily)
        basin_records.append(
            {
                "station_id": station_id,
                "station_name": str(station["station_name"]),
                "hydrobasins_id": target_id,
                "subbasin_count": len(selected_ids),
                "hydrobasins_up_area_km2": float(station["UP_AREA"]),
                "geometry": basin_geometry,
            }
        )

    result = xr.concat(weighted_datasets, dim="station")
    result.attrs.update(dataset.attrs)
    result.attrs.update(
        {
            "spatial_aggregation": "exact grid-cell intersection area weighting",
            "basin_source": "HydroBASINS level 12",
            "area_crs": EQUAL_AREA_CRS,
        }
    )
    for name in result.data_vars:
        if int(result[name].isnull().sum()) != 0:
            raise ValueError(f"Area-weighted variable {name} contains missing values")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    encoding = {
        name: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for name in result.data_vars
    }
    result.to_netcdf(temporary, engine="netcdf4", encoding=encoding)
    temporary.replace(args.output)
    pd.concat(all_weights, ignore_index=True).to_csv(args.weights_output, index=False)
    gpd.GeoDataFrame(basin_records, crs="EPSG:4326").to_file(
        args.basins_output, driver="GeoJSON"
    )
    print(
        f"created {args.output}: days={result.sizes['time']}, "
        f"stations={result.sizes['station']}, variables={len(result.data_vars)}"
    )
    for record, weights in zip(basin_records, all_weights):
        print(
            f"{record['station_id']}: subbasins={record['subbasin_count']}, "
            f"cells={len(weights)}, area_km2={weights['overlap_km2'].sum():.1f}, "
            f"weight_sum={weights['weight'].sum():.12f}"
        )


if __name__ == "__main__":
    main()
