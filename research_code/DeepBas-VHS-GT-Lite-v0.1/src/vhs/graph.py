from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from .io import read_station_kmz


def local_utm_epsg(longitude: float, latitude: float) -> int:
    zone = int(math.floor((longitude + 180.0) / 6.0) + 1)
    return (32600 if latitude >= 0 else 32700) + zone


def build_station_graph(
    station_kmz_paths: list[str],
    hydrorivers_path: str,
    hydrobasins_path: str | None,
    bbox: list[float],
    bbox_buffer_degrees: float = 0.2,
    snap_max_km: float = 10.0,
    river_id_column: str = "HYRIV_ID",
    next_down_column: str = "NEXT_DOWN",
    river_length_column: str = "LENGTH_KM",
    reservoir_station_names: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Snap stations to HydroRIVERS and trace the next downstream station.

    Requires geopandas/pyogrio. The river shapefile should already be unpacked.
    """
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise RuntimeError('Install geospatial dependencies with: pip install -e ".[geo]"') from exc

    stations = pd.concat([read_station_kmz(p) for p in station_kmz_paths], ignore_index=True)
    stations = stations.drop_duplicates(subset="station_id", keep="first")
    min_lon, min_lat, max_lon, max_lat = map(float, bbox)
    stations = stations[
        stations.longitude.between(min_lon, max_lon) & stations.latitude.between(min_lat, max_lat)
    ].copy()
    if stations.empty:
        raise ValueError("No stations fall inside study-area bbox")

    buf = float(bbox_buffer_degrees)
    river_bbox = (min_lon - buf, min_lat - buf, max_lon + buf, max_lat + buf)
    rivers = gpd.read_file(hydrorivers_path, bbox=river_bbox)
    required = {river_id_column, next_down_column, river_length_column}
    missing = required - set(rivers.columns)
    if missing:
        raise KeyError(f"HydroRIVERS missing fields: {sorted(missing)}")
    rivers = rivers[list(required) + ["geometry"]].copy()
    rivers[river_id_column] = pd.to_numeric(rivers[river_id_column], errors="coerce").astype("Int64")
    rivers[next_down_column] = pd.to_numeric(rivers[next_down_column], errors="coerce").fillna(0).astype("Int64")
    rivers[river_length_column] = pd.to_numeric(rivers[river_length_column], errors="coerce").fillna(0.0)

    station_gdf = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations.longitude, stations.latitude),
        crs="EPSG:4326",
    )
    epsg = local_utm_epsg(float(stations.longitude.median()), float(stations.latitude.median()))
    station_metric = station_gdf.to_crs(epsg)
    river_metric = rivers.to_crs(epsg)
    matched = gpd.sjoin_nearest(
        station_metric,
        river_metric,
        how="left",
        distance_col="snap_distance_m",
    )
    matched = matched.sort_values("snap_distance_m").drop_duplicates("station_id")
    matched["snap_distance_km"] = matched["snap_distance_m"] / 1000.0
    matched["snap_ok"] = matched["snap_distance_km"] <= float(snap_max_km)
    if matched[river_id_column].isna().any():
        raise ValueError("At least one station could not be snapped to HydroRIVERS")

    nodes = pd.DataFrame(matched.drop(columns=["geometry", "index_right"], errors="ignore"))
    nodes = nodes.rename(columns={river_id_column: "river_id"})
    nodes["river_id"] = nodes["river_id"].astype(int)
    reservoir_names = set(reservoir_station_names or [])
    nodes["reservoir_flag"] = nodes.station_name.isin(reservoir_names).astype(int)

    if hydrobasins_path:
        basins = gpd.read_file(hydrobasins_path, bbox=river_bbox)
        keep = [c for c in ["HYBAS_ID", "SUB_AREA", "UP_AREA", "ENDO", "ORDER", "geometry"] if c in basins]
        joined = gpd.sjoin(station_gdf, basins[keep], how="left", predicate="within")
        basin_cols = [c for c in keep if c != "geometry"]
        basin_frame = pd.DataFrame(joined[["station_id"] + basin_cols]).drop_duplicates("station_id")
        nodes = nodes.merge(basin_frame, on="station_id", how="left")

    river_records = pd.DataFrame(rivers.drop(columns="geometry"))
    by_id = river_records.set_index(river_id_column).to_dict("index")
    stations_by_river: dict[int, list[str]] = {}
    for row in nodes.itertuples(index=False):
        stations_by_river.setdefault(int(row.river_id), []).append(str(row.station_id))

    edges: list[dict[str, object]] = []
    max_steps = len(by_id) + 1
    for station in nodes.itertuples(index=False):
        current = int(station.river_id)
        distance = 0.0
        visited: set[int] = set()
        for _ in range(max_steps):
            if current in visited or current == 0 or current not in by_id:
                break
            visited.add(current)
            rec = by_id[current]
            distance += float(rec.get(river_length_column, 0.0) or 0.0)
            nxt = int(rec.get(next_down_column, 0) or 0)
            downstream_stations = [s for s in stations_by_river.get(nxt, []) if s != str(station.station_id)]
            if downstream_stations:
                for target in downstream_stations:
                    edges.append(
                        {
                            "source": str(station.station_id),
                            "target": str(target),
                            "river_distance_km": distance,
                            "source_river_id": int(station.river_id),
                            "target_river_id": nxt,
                        }
                    )
                break
            current = nxt

    edges_frame = pd.DataFrame(edges).drop_duplicates(subset=["source", "target"])
    if edges_frame.empty:
        raise ValueError(
            "No station-to-station downstream edges were found. Check bbox, station snapping, and whether stations share a river network."
        )
    matches = nodes[["station_id", "station_name", "longitude", "latitude", "river_id", "snap_distance_km", "snap_ok"]].copy()
    return nodes, edges_frame, matches


def edge_arrays(nodes: pd.DataFrame, edges: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    node_to_idx = {str(s): i for i, s in enumerate(nodes.station_id.astype(str))}
    valid = edges.source.astype(str).isin(node_to_idx) & edges.target.astype(str).isin(node_to_idx)
    edges = edges.loc[valid].copy()
    edge_index = np.array(
        [
            [node_to_idx[str(v)] for v in edges.source],
            [node_to_idx[str(v)] for v in edges.target],
        ],
        dtype=np.int64,
    )
    attr_cols = [c for c in ["river_distance_km", "slope", "travel_time_days"] if c in edges]
    if attr_cols:
        edge_attr = edges[attr_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(np.float32)
    else:
        edge_attr = np.ones((len(edges), 1), dtype=np.float32)
    return edge_index, edge_attr

