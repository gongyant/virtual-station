from __future__ import annotations

import argparse
from functools import reduce
from pathlib import Path

import pandas as pd

from vhs.config import load_config
from vhs.data import build_bundle
from vhs.io import extract_netcdf_nearest, read_flow_source


def outer_merge(frames: list[pd.DataFrame]) -> pd.DataFrame:
    return reduce(lambda a, b: a.merge(b, on=["date", "station_id"], how="outer"), frames)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    paths = cfg["paths"]
    nodes = pd.read_csv(paths["nodes"], dtype={"station_id": str})
    edges = pd.read_csv(paths["edges"], dtype={"source": str, "target": str})

    flow_frames = [read_flow_source(spec) for spec in cfg.get("flow_sources", [])]
    if not flow_frames:
        raise ValueError("At least one flow_sources entry is required")
    flows = pd.concat(flow_frames, ignore_index=True).groupby(["date", "station_id"], as_index=False).obs_q.mean()
    frames = [flows]
    netcdf_specs = cfg.get("netcdf_sources", [])
    for spec in netcdf_specs:
        if spec.get("method", "nearest_station") != "nearest_station":
            raise NotImplementedError("Lite version currently supports nearest_station NetCDF extraction")
        frames.append(
            extract_netcdf_nearest(
                file_pattern=spec["files"],
                variable=spec["variable"],
                stations=nodes,
                feature_name=spec["name"],
            )
        )
    timeseries = outer_merge(frames).sort_values(["station_id", "date"])
    # 仅保留具有实测径流的研究时段
    observed = flows.dropna(subset=["obs_q"])
    obs_start = observed["date"].min()
    obs_end = observed["date"].max()

    timeseries = timeseries[
        (timeseries["date"] >= obs_start)
        & (timeseries["date"] <= obs_end)
    ].copy()

    print(
        f"restricted to observation period: "
        f"{obs_start.date()} -> {obs_end.date()}"
    )
    for spec in netcdf_specs:
        if spec.get("fill_method") == "forward":
            name = spec["name"]
            limit = int(spec.get("fill_limit_days", 35))
            timeseries[name] = timeseries.groupby("station_id", sort=False)[name].ffill(limit=limit)
    timeseries = timeseries.sort_values(["date", "station_id"])
    output = Path(paths["timeseries"])
    output.parent.mkdir(parents=True, exist_ok=True)
    timeseries.to_csv(output, index=False)

    data_cfg = cfg["data"]
    bundle = build_bundle(nodes, edges, timeseries, dynamic_features=list(data_cfg["dynamic_features"]))
    bundle.save(data_cfg["bundle_path"])
    print(f"rows={len(timeseries)} dates={timeseries.date.nunique()} stations={timeseries.station_id.nunique()}")
    print(f"saved: {output}, {data_cfg['bundle_path']}")


if __name__ == "__main__":
    main()
