from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from vhs.data import TensorBundle


CLIMATE_VARIABLES = [
    "temperature_c",
    "precipitation_mm",
    "evaporation_loss_mm",
    "swe_mm",
    "soil_water_layer1",
    "snowmelt_mm",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare a strict virtual-station bundle with local/intervening ERA5 forcing."
    )
    parser.add_argument("--base-bundle", type=Path, default=Path("data/processed/real_bundle.npz"))
    parser.add_argument("--basin-era5", type=Path, required=True)
    parser.add_argument("--incremental-era5", type=Path, required=True)
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--routing-lag-days", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    return parser.parse_args()


def align_dataset(dataset: xr.Dataset, dates: np.ndarray) -> xr.Dataset:
    expected = pd.DatetimeIndex(dates.astype("datetime64[D]"))
    actual = pd.DatetimeIndex(dataset.time.values).normalize()
    if not expected.isin(actual).all():
        missing = expected[~expected.isin(actual)]
        raise ValueError(f"ERA5 dataset misses {len(missing)} required dates")
    return dataset.sel(time=expected)


def main() -> None:
    args = parse_args()
    base = TensorBundle.load(args.base_bundle)
    station_ids = list(map(str, base.station_ids))
    upstream_idx = station_ids.index(args.upstream)
    target_idx = station_ids.index(args.target)
    obs_idx = list(map(str, base.feature_names)).index("obs_q")

    with xr.open_dataset(args.basin_era5) as source:
        basin = source.load()
    with xr.open_dataset(args.incremental_era5) as source:
        incremental = source.load()
    start = max(pd.Timestamp(base.dates[0]), pd.Timestamp(basin.time.values[0]), pd.Timestamp(incremental.time.values[0]))
    end = min(pd.Timestamp(base.dates[-1]), pd.Timestamp(basin.time.values[-1]), pd.Timestamp(incremental.time.values[-1]))
    date_mask = (pd.DatetimeIndex(base.dates) >= start) & (pd.DatetimeIndex(base.dates) <= end)
    dates = base.dates[date_mask]
    basin = align_dataset(basin, dates)
    incremental = align_dataset(incremental, dates)
    base_x = base.x[date_mask]

    new_features: list[np.ndarray] = []
    new_names: list[str] = []
    for variable in CLIMATE_VARIABLES:
        values = np.full((len(dates), len(station_ids)), np.nan, dtype=np.float32)
        values[:, upstream_idx] = basin[variable].sel(station=args.upstream).values.astype(np.float32)
        values[:, target_idx] = incremental[variable].isel(basin=0).values.astype(np.float32)
        new_features.append(values)
        new_names.append(f"local_{variable}")

    lag = int(args.routing_lag_days)
    routed = np.full((len(dates), len(station_ids)), np.nan, dtype=np.float32)
    upstream_flow = base_x[:, upstream_idx, obs_idx].astype(np.float32)
    routed[lag:, target_idx] = upstream_flow[:-lag]
    new_features.append(routed)
    new_names.append(f"routed_upstream_q_lag{lag}")

    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    area_ratio = float(nodes.loc[args.target, "UP_AREA"]) / float(
        nodes.loc[args.upstream, "UP_AREA"]
    )
    physical_reference = routed * area_ratio
    new_features.append(physical_reference.astype(np.float32))
    new_names.append(f"physics_area_scaled_q_lag{lag}")

    augmented_x = np.concatenate([base_x, np.stack(new_features, axis=-1)], axis=-1)
    output = TensorBundle(
        dates=dates,
        station_ids=base.station_ids,
        feature_names=np.concatenate([base.feature_names.astype(str), np.asarray(new_names)]),
        x=augmented_x,
        y=base.y[date_mask],
        y_mask=base.y_mask[date_mask],
        static=base.static,
        edge_index=base.edge_index,
        edge_attr=base.edge_attr,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output.save(args.output)
    metadata = {
        "dates": [str(pd.Timestamp(dates[0]).date()), str(pd.Timestamp(dates[-1]).date())],
        "days": len(dates),
        "upstream_station": args.upstream,
        "target_station": args.target,
        "target_observations_used_in_new_features": False,
        "upstream_area_km2": float(nodes.loc[args.upstream, "UP_AREA"]),
        "target_area_km2": float(nodes.loc[args.target, "UP_AREA"]),
        "incremental_area_km2": float(nodes.loc[args.target, "UP_AREA"])
        - float(nodes.loc[args.upstream, "UP_AREA"]),
        "area_ratio": area_ratio,
        "routing_lag_days": lag,
        "new_features": new_names,
        "forcing_assignment": {
            args.upstream: "entire upstream basin",
            args.target: "incremental basin between upstream and target",
        },
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"created {args.output}: dates={len(dates)}, stations={len(station_ids)}, "
        f"features={len(output.feature_names)}"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
