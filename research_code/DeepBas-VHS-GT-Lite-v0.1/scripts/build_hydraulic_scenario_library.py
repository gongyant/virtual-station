from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.hydraulics import ReachHydraulics, build_hydraulic_scenario_library


DEFAULT_MEASUREMENTS = Path(
    "outputs/diagnosis_2005_snapshot/stage_d4b/"
    "discharge_measurements_2011_canonical.csv"
)
DEFAULT_META = Path("outputs/diagnosis_2005_snapshot/stage_d/station_meta.csv")
DEFAULT_EDGES = Path("data/processed/virtual_station_multisite/multisite_edges_2005.csv")
DEFAULT_DEM = Path(
    "outputs/diagnosis_2005_snapshot/stage_d3/dem_reach_slopes_2011.csv"
)
DEFAULT_OUTPUT = Path("outputs/hydraulic_scenario_library/byblk_to_dsk_2011")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _find_edge_length_m(edges: pd.DataFrame, source: str, target: str) -> float:
    source_col = "source" if "source" in edges else "source_station_id"
    target_col = "target" if "target" in edges else "target_station_id"
    rows = edges.loc[
        edges[source_col].astype(str).eq(source)
        & edges[target_col].astype(str).eq(target)
    ]
    if len(rows) != 1:
        raise ValueError(f"expected one {source}->{target} edge, found {len(rows)}")
    for column, factor in (("river_distance_km", 1000.0), ("distance_km", 1000.0), ("length_m", 1.0)):
        if column in rows:
            value = float(pd.to_numeric(rows.iloc[0][column], errors="coerce")) * factor
            if np.isfinite(value) and value > 0:
                return value
    raise ValueError("edge table does not contain a positive reach length")


def _station_datum(meta: pd.DataFrame, station_id: str) -> float:
    rows = meta.loc[meta.station_id.astype(str).eq(station_id)]
    if len(rows) != 1:
        raise ValueError(f"expected one metadata row for station {station_id}")
    column = "stage_datum_offset_m" if "stage_datum_offset_m" in rows else "stage_datum_m"
    value = float(pd.to_numeric(rows.iloc[0][column], errors="coerce"))
    if not np.isfinite(value):
        raise ValueError(f"station {station_id} lacks a confirmed vertical datum")
    return value


def _dem_slope(path: Path, source: str, target: str) -> tuple[float | None, dict[str, object]]:
    if not path.exists():
        return None, {"status": "missing_dem_slope_file", "path": str(path)}
    frame = pd.read_csv(path, dtype={"station_id": str})
    column = "dem_derived_slope_proxy"
    if column not in frame:
        return None, {"status": "missing_dem_slope_column", "path": str(path)}
    selected = frame.loc[frame.station_id.astype(str).isin([source, target])].copy()
    values = pd.to_numeric(selected[column], errors="coerce")
    finite = values[np.isfinite(values) & values.gt(0)]
    if finite.empty:
        statuses = sorted(selected.get("status", pd.Series(dtype=str)).dropna().astype(str).unique())
        return None, {
            "status": "dem_raster_not_materialized",
            "path": str(path),
            "reported_statuses": statuses,
        }
    return float(finite.median()), {
        "status": "available",
        "path": str(path),
        "aggregation": "median_positive_station_slope",
        "n": int(len(finite)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Enumerate a mass/energy-constrained upstream-downstream hydraulic lookup table."
    )
    parser.add_argument("--measurements", type=Path, default=DEFAULT_MEASUREMENTS)
    parser.add_argument("--station-meta", type=Path, default=DEFAULT_META)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--dem-slopes", type=Path, default=DEFAULT_DEM)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--upstream-station-id", default="00705600")
    parser.add_argument("--downstream-station-id", default="00705700")
    parser.add_argument("--manning-n-upstream", type=float, default=0.04)
    parser.add_argument("--manning-n-downstream", type=float, default=0.04)
    parser.add_argument("--side-slope-h-to-v", type=float, default=2.0)
    parser.add_argument(
        "--allow-missing-dem",
        action="store_true",
        help="Build a diagnostic-only table from common-datum water levels when the DEM raster is absent.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    measurements = pd.read_csv(args.measurements, dtype={"station_id": str})
    meta = pd.read_csv(args.station_meta, dtype={"station_id": str})
    edges = pd.read_csv(args.edges, dtype=str)
    source = str(args.upstream_station_id)
    target = str(args.downstream_station_id)
    upstream = measurements.loc[measurements.station_id.astype(str).eq(source)].copy()
    downstream = measurements.loc[measurements.station_id.astype(str).eq(target)].copy()
    if upstream.empty or downstream.empty:
        raise ValueError("both stations require discharge-measurement section states")

    length_m = _find_edge_length_m(edges, source, target)
    upstream_datum = _station_datum(meta, source)
    downstream_datum = _station_datum(meta, target)
    dem_slope, dem_evidence = _dem_slope(args.dem_slopes, source, target)
    if dem_slope is None and not args.allow_missing_dem:
        raise RuntimeError(
            "DEM slope evidence is unavailable. Supply the raster-derived slope table or "
            "rerun with --allow-missing-dem for a diagnostic-only datum fallback."
        )

    reach = ReachHydraulics(
        length_m=length_m,
        manning_n_upstream=args.manning_n_upstream,
        manning_n_downstream=args.manning_n_downstream,
        dem_bed_slope_m_per_m=dem_slope,
    )
    scenarios = build_hydraulic_scenario_library(
        upstream,
        downstream,
        reach,
        upstream_stage_datum_m=upstream_datum,
        downstream_stage_datum_m=downstream_datum,
        side_slope_h_to_v=args.side_slope_h_to_v,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = args.output_dir / "hydraulic_scenarios.csv"
    scenarios.to_csv(scenario_path, index=False)

    valid = scenarios.loc[scenarios.physics_valid.astype(bool)]
    status = "physics_ready" if dem_slope is not None else "diagnostic_only_missing_dem_raster"
    manifest = {
        "status": status,
        "claim_scope": (
            "physical_reference_candidate"
            if dem_slope is not None
            else "diagnostic_scenario_envelope_not_authorized_as_discharge_label"
        ),
        "upstream_station_id": source,
        "downstream_station_id": target,
        "scenario_count": int(len(scenarios)),
        "valid_scenario_count": int(len(valid)),
        "source_state_counts": {"upstream": int(len(upstream)), "downstream": int(len(downstream))},
        "reach": {
            "length_m": length_m,
            "upstream_stage_datum_m": upstream_datum,
            "downstream_stage_datum_m": downstream_datum,
            "manning_n_upstream": args.manning_n_upstream,
            "manning_n_downstream": args.manning_n_downstream,
            "side_slope_h_to_v": args.side_slope_h_to_v,
        },
        "dem_evidence": dem_evidence,
        "physics": {
            "mass_balance": "steady Q_up = Q_down; lateral inflow and storage change fixed to zero",
            "energy_balance": "common-datum water-surface head drop = Manning friction + velocity-head change",
            "interpolation_policy": "inside enumerated feature bounds only; no extrapolation",
        },
        "limitations": [
            "Manning roughness and side slope are assumptions until independently calibrated.",
            "The 2011 daily discharge series may be rating-curve-derived and is not used to solve scenarios.",
            "A reservoir/control reach needs gate, storage, or release state before formal authorization.",
        ],
        "inputs": {
            str(path): _sha256(path)
            for path in (args.measurements, args.station_meta, args.edges, args.dem_slopes)
            if path.exists()
        },
        "output": str(scenario_path),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
