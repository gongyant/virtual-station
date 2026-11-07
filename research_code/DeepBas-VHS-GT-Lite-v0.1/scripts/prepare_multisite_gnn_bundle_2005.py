from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.data import build_bundle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the five-station 2005 residual-GNN tensor bundle."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/processed/virtual_station_multisite"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz"
        ),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path(
            "data/processed/virtual_station_multisite/multisite_bundle_metadata_2005.json"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    discharge = pd.read_csv(
        args.input_dir / "multisite_discharge_2005.csv", parse_dates=["date"]
    )
    nodes = pd.read_csv(
        args.input_dir / "multisite_stations_2005.csv", dtype={"station_id": str}
    )
    edges = pd.read_csv(
        args.input_dir / "multisite_edges_2005.csv",
        dtype={"source": str, "target": str},
    )

    discharge = discharge.rename(
        columns={
            "observed_q_m3s": "obs_q",
            "physical_reference_q_m3s": "physical_reference_q",
        }
    )
    component_max = nodes.groupby("component")["node_order"].transform("max").replace(0, 1)
    nodes["node_order_scaled"] = nodes["node_order"] / component_max
    nodes["component_kaidu"] = (nodes.component == "kaidu_headwater").astype(float)
    nodes["component_tarim"] = (nodes.component == "tarim_mainstem").astype(float)
    area = pd.to_numeric(nodes.upstream_area_km2, errors="coerce")
    nodes["log_upstream_area"] = np.log1p(area).fillna(0.0)
    nodes["area_available"] = area.notna().astype(float)

    # Distances for two Tarim collapsed edges are unknown. A topology-only graph
    # is safer than inserting fabricated distances, so edge_arrays receives no
    # distance column and assigns a neutral unit edge attribute.
    topology_edges = edges[["source", "target"]].copy()
    bundle = build_bundle(
        nodes=nodes,
        edges=topology_edges,
        timeseries=discharge,
        dynamic_features=["obs_q", "physical_reference_q"],
        static_features=[
            "node_order_scaled",
            "component_kaidu",
            "component_tarim",
            "log_upstream_area",
            "area_available",
        ],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    bundle.save(args.output)

    dates = pd.DatetimeIndex(bundle.dates)
    station_ids = list(map(str, bundle.station_ids))
    target_idx = station_ids.index("00705700")
    metadata = {
        "status": "created",
        "bundle": str(args.output),
        "dates": [str(dates[0].date()), str(dates[-1].date())],
        "days": int(len(dates)),
        "stations": station_ids,
        "features": list(map(str, bundle.feature_names)),
        "static_features": [
            "node_order_scaled",
            "component_kaidu",
            "component_tarim",
            "log_upstream_area",
            "area_available",
        ],
        "edges": edges[["source", "target", "topology_status"]].to_dict("records"),
        "edge_attribute_policy": "unit topology-only edge attribute",
        "held_out_target": "00705700",
        "held_out_target_observation_days": int(bundle.y_mask[:, target_idx].sum()),
        "held_out_target_flow_is_masked_by_window_dataset": True,
        "held_out_target_labels_are_excluded_from_training": True,
        "physical_reference": (
            "MQ columns from the source workbook; permitted as a non-observational residual anchor"
        ),
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
