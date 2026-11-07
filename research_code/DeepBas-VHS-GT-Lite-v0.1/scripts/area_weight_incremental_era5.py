from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr

from area_weight_era5_land import basin_weights, make_grid, upstream_ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Area-weight ERA5-Land over the basin between an upstream and downstream station."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--hydrobasins",
        type=Path,
        default=Path("data/raw/hydrobasins/hybas_as_lev12_v1c.shp"),
    )
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--downstream", default="00705700")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--weights-output", type=Path, required=True)
    parser.add_argument("--basin-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    basins = gpd.read_file(args.hydrobasins)
    upstream_id = int(nodes.loc[args.upstream, "HYBAS_ID"])
    downstream_id = int(nodes.loc[args.downstream, "HYBAS_ID"])
    upstream = basins[basins["HYBAS_ID"].isin(upstream_ids(basins, upstream_id))]
    downstream = basins[
        basins["HYBAS_ID"].isin(upstream_ids(basins, downstream_id))
    ]
    upstream_geometry = upstream.geometry.union_all()
    downstream_geometry = downstream.geometry.union_all()
    incremental_geometry = downstream_geometry.difference(upstream_geometry)
    if incremental_geometry.is_empty:
        raise ValueError("Incremental basin is empty; verify station topology")

    with xr.open_dataset(args.input) as source:
        dataset = source.load()
    grid = make_grid(dataset.latitude.values, dataset.longitude.values)
    label = f"{args.upstream}_to_{args.downstream}"
    weights = basin_weights(grid, incremental_geometry, label)
    weight_array = xr.DataArray(
        np.zeros((dataset.sizes["latitude"], dataset.sizes["longitude"])),
        coords={"latitude": dataset.latitude, "longitude": dataset.longitude},
        dims=("latitude", "longitude"),
    )
    for row in weights.itertuples(index=False):
        weight_array.loc[
            {"latitude": row.latitude, "longitude": row.longitude}
        ] = row.weight
    result = dataset.weighted(weight_array).mean(("latitude", "longitude"))
    result = result.expand_dims(basin=[label])
    result = result.assign_coords(
        upstream_station=("basin", [args.upstream]),
        downstream_station=("basin", [args.downstream]),
        incremental_area_km2=("basin", [float(weights["overlap_km2"].sum())]),
    )
    result.attrs.update(dataset.attrs)
    result.attrs.update(
        {
            "spatial_aggregation": "exact intersection-area weighting",
            "basin_definition": "downstream upstream-area minus upstream upstream-area",
            "upstream_station": args.upstream,
            "downstream_station": args.downstream,
        }
    )
    for name in result.data_vars:
        if int(result[name].isnull().sum()) != 0:
            raise ValueError(f"Incremental variable {name} contains missing values")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    encoding = {
        name: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for name in result.data_vars
    }
    result.to_netcdf(temporary, engine="netcdf4", encoding=encoding)
    temporary.replace(args.output)
    weights.to_csv(args.weights_output, index=False)
    gpd.GeoDataFrame(
        [
            {
                "basin": label,
                "upstream_station": args.upstream,
                "downstream_station": args.downstream,
                "area_km2": float(weights["overlap_km2"].sum()),
                "geometry": incremental_geometry,
            }
        ],
        crs="EPSG:4326",
    ).to_file(args.basin_output, driver="GeoJSON")
    expected_area = float(nodes.loc[args.downstream, "UP_AREA"]) - float(
        nodes.loc[args.upstream, "UP_AREA"]
    )
    print(
        f"created {args.output}: days={result.sizes['time']}, cells={len(weights)}, "
        f"intersection_area_km2={weights['overlap_km2'].sum():.1f}, "
        f"hydrobasins_area_difference_km2={expected_area:.1f}, "
        f"weight_sum={weights['weight'].sum():.12f}"
    )


if __name__ == "__main__":
    main()
