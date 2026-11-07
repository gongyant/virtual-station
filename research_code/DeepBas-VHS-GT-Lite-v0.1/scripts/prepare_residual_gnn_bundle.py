from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from evaluate_donor_rolling_validation import simulate_degree_day_snow_runoff_mm
from vhs.data import TensorBundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add a leakage-free self-supervised reference for residual GNN training."
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--incremental-era5", type=Path, required=True)
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--parameter-summaries", type=Path, nargs="+", required=True)
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--routing-lag-days", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = TensorBundle.load(args.bundle)
    station_ids = list(map(str, bundle.station_ids))
    upstream_idx = station_ids.index(args.upstream)
    target_idx = station_ids.index(args.target)
    feature_names = list(map(str, bundle.feature_names))
    obs_idx = feature_names.index("obs_q")
    routed_idx = feature_names.index(f"routed_upstream_q_lag{args.routing_lag_days}")

    with xr.open_dataset(args.incremental_era5) as source:
        incremental = source.load().isel(basin=0)
    forcing_dates = pd.DatetimeIndex(incremental.time.values).normalize()
    bundle_dates = pd.DatetimeIndex(bundle.dates)
    if not bundle_dates.isin(forcing_dates).all():
        raise ValueError("Incremental ERA5 forcing does not cover the bundle dates")
    incremental = incremental.sel(time=bundle_dates)

    parameter_sets = []
    parameter_sources = []
    for summary_path in args.parameter_summaries:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["selection"]["selected_structure"] != "degree_day_snow_reservoir":
            raise ValueError(f"Unexpected selected structure in {summary_path}")
        values = summary["final_parameters"]
        parameter_sets.append(
            np.asarray(
                [
                    values["runoff_coefficient"],
                    values["recession"],
                    values["baseflow_mm_day"],
                    values["snowfall_temperature_threshold_c"],
                    values["melt_temperature_threshold_c"],
                    values["degree_day_factor_mm_c_day"],
                ],
                dtype=float,
            )
        )
        parameter_sources.append(str(summary_path))

    local_members = []
    for parameters in parameter_sets:
        local_members.append(
            simulate_degree_day_snow_runoff_mm(
                incremental["precipitation_mm"].values.astype(float),
                incremental["temperature_c"].values.astype(float),
                incremental["snowmelt_mm"].values.astype(float),
                incremental["evaporation_loss_mm"].values.astype(float),
                parameters,
            )
        )
    local_runoff_mm = np.mean(np.stack(local_members), axis=0)
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    incremental_area = float(nodes.loc[args.target, "UP_AREA"]) - float(
        nodes.loc[args.upstream, "UP_AREA"]
    )
    local_q = local_runoff_mm * incremental_area / 86.4

    reference = np.full((len(bundle.dates), len(station_ids)), np.nan, dtype=np.float32)
    upstream_flow = bundle.x[:, upstream_idx, obs_idx].astype(np.float32)
    reference[1:, upstream_idx] = upstream_flow[:-1]
    routed_upstream = bundle.x[:, target_idx, routed_idx].astype(np.float32)
    reference[:, target_idx] = routed_upstream + local_q.astype(np.float32)
    reference_name = "residual_reference_q"
    if reference_name in feature_names:
        raise ValueError(f"Bundle already contains {reference_name}")
    augmented = TensorBundle(
        dates=bundle.dates,
        station_ids=bundle.station_ids,
        feature_names=np.concatenate([bundle.feature_names, np.asarray([reference_name])]),
        x=np.concatenate([bundle.x, reference[:, :, None]], axis=-1),
        y=bundle.y,
        y_mask=bundle.y_mask,
        static=bundle.static,
        edge_index=bundle.edge_index,
        edge_attr=bundle.edge_attr,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    augmented.save(args.output)
    metadata = {
        "status": "created",
        "reference_feature": reference_name,
        "protocol": {
            "target_station": args.target,
            "target_observations_used": False,
            "upstream_reference": "previous-day observed upstream discharge",
            "target_reference": (
                "lagged observed upstream discharge plus donor-calibrated incremental-basin "
                "degree-day runoff ensemble"
            ),
            "parameter_sources": parameter_sources,
        },
        "coverage": {
            "dates": [str(bundle_dates[0].date()), str(bundle_dates[-1].date())],
            "upstream_reference_days": int(np.isfinite(reference[:, upstream_idx]).sum()),
            "target_reference_days": int(np.isfinite(reference[:, target_idx]).sum()),
        },
        "incremental_area_km2": incremental_area,
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
