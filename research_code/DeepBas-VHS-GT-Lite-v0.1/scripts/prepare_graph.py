from __future__ import annotations

import argparse
from pathlib import Path

from vhs.config import load_config
from vhs.graph import build_station_graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    cfg = load_config(args.config)
    p, area, graph = cfg["paths"], cfg["study_area"], cfg["graph"]
    nodes, edges, matches = build_station_graph(
        station_kmz_paths=p["station_kmz"],
        hydrorivers_path=p["hydrorivers"],
        hydrobasins_path=p.get("hydrobasins_l12"),
        bbox=area["bbox"],
        bbox_buffer_degrees=area.get("bbox_buffer_degrees", 0.2),
        snap_max_km=area.get("snap_max_km", 10.0),
        river_id_column=graph.get("river_id_column", "HYRIV_ID"),
        next_down_column=graph.get("next_down_column", "NEXT_DOWN"),
        river_length_column=graph.get("river_length_column", "LENGTH_KM"),
        reservoir_station_names=graph.get("reservoir_station_names", []),
    )
    node_path, edge_path = Path(p["nodes"]), Path(p["edges"])
    node_path.parent.mkdir(parents=True, exist_ok=True)
    nodes.to_csv(node_path, index=False)
    edges.to_csv(edge_path, index=False)
    matches.to_csv(node_path.parent / "station_river_matches.csv", index=False)
    print(f"nodes={len(nodes)} edges={len(edges)}")
    print(f"saved: {node_path}, {edge_path}")


if __name__ == "__main__":
    main()

