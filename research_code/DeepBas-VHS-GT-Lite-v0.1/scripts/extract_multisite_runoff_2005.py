from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xlrd


STATIONS = [
    {
        "station_code": "BYBLK",
        "station_id": "00705600",
        "station_name": "巴音布鲁克",
        "component": "kaidu_headwater",
        "node_order": 0,
        "source_sheet_index": 9,
        "date_column": 0,
        "physical_reference_column": 3,
        "observed_column": 4,
        "source_header": "OQ-BYBLK-2005",
    },
    {
        "station_code": "DSK",
        "station_id": "00705700",
        "station_name": "大山口",
        "component": "kaidu_headwater",
        "node_order": 1,
        "source_sheet_index": 9,
        "date_column": 0,
        "physical_reference_column": 1,
        "observed_column": 2,
        "source_header": "OQ-DSK-2005",
    },
    {
        "station_code": "ALAR",
        "station_id": "TARIM_ALAR",
        "station_name": "阿拉尔",
        "component": "tarim_mainstem",
        "node_order": 0,
        "source_sheet_index": 11,
        "date_column": 0,
        "physical_reference_column": 1,
        "observed_column": 4,
        "source_header": "OQ-Alar-2005",
    },
    {
        "station_code": "XQM",
        "station_id": "TARIM_XQM",
        "station_name": "新其满",
        "component": "tarim_mainstem",
        "node_order": 1,
        "source_sheet_index": 11,
        "date_column": 0,
        "physical_reference_column": 2,
        "observed_column": 5,
        "source_header": "OQ-XQM-2005",
    },
    {
        "station_code": "AQK",
        "station_id": "TARIM_AQK",
        "station_name": "阿其克",
        "component": "tarim_mainstem",
        "node_order": 2,
        "source_sheet_index": 11,
        "date_column": 0,
        "physical_reference_column": 3,
        "observed_column": 6,
        "source_header": "OQ-AQK-2005",
    },
]


EDGES = [
    {
        "source": "00705600",
        "target": "00705700",
        "component": "kaidu_headwater",
        "river_distance_km": 212.61,
        "topology_status": "verified_project_river_network",
        "basis": "data/processed/edges.csv",
    },
    {
        "source": "TARIM_ALAR",
        "target": "TARIM_XQM",
        "component": "tarim_mainstem",
        "river_distance_km": np.nan,
        "topology_status": "verified_literature",
        "basis": "Alar-Xinqiman is the first main-stem reach",
    },
    {
        "source": "TARIM_XQM",
        "target": "TARIM_AQK",
        "component": "tarim_mainstem",
        "river_distance_km": np.nan,
        "topology_status": "collapsed_verified_order",
        "basis": "Collapsed Xinqiman-Yingbaza-Usman-Aqike path; intermediate stations absent",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the 2005 five-station discharge data for leave-one-station GNN work."
    )
    parser.add_argument("--workbook", type=Path, default=Path("data/raw/runoff/Q-新疆.xls"))
    parser.add_argument(
        "--nodes", type=Path, default=Path("data/processed/nodes.csv")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed/virtual_station_multisite"),
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def excel_date(value: float, datemode: int) -> pd.Timestamp:
    return pd.Timestamp(*xlrd.xldate_as_tuple(value, datemode)[:6]).normalize()


def metric_summary(observed: np.ndarray, reference: np.ndarray) -> dict[str, float]:
    valid = np.isfinite(observed) & np.isfinite(reference)
    obs = observed[valid]
    ref = reference[valid]
    if len(obs) < 2:
        return {"reference_rmse": np.nan, "reference_nse": np.nan, "reference_r": np.nan}
    rmse = float(np.sqrt(np.mean((ref - obs) ** 2)))
    denom = float(np.sum((obs - np.mean(obs)) ** 2))
    nse = float(1.0 - np.sum((ref - obs) ** 2) / denom) if denom > 0 else np.nan
    corr = float(np.corrcoef(obs, ref)[0, 1]) if np.std(obs) > 0 and np.std(ref) > 0 else np.nan
    return {"reference_rmse": rmse, "reference_nse": nse, "reference_r": corr}


def main() -> None:
    args = parse_args()
    workbook_path = args.workbook.resolve()
    book = xlrd.open_workbook(str(workbook_path), formatting_info=False)
    records: list[dict[str, object]] = []
    source_ranges: dict[str, str] = {}

    for station in STATIONS:
        sheet = book.sheet_by_index(int(station["source_sheet_index"]))
        source_ranges[sheet.name] = f"A1:{xlrd.formula.colname(sheet.ncols - 1)}{sheet.nrows}"
        for row_idx in range(1, sheet.nrows):
            raw_date = sheet.cell_value(row_idx, int(station["date_column"]))
            raw_obs = sheet.cell_value(row_idx, int(station["observed_column"]))
            raw_reference = sheet.cell_value(
                row_idx, int(station["physical_reference_column"])
            )
            if not isinstance(raw_date, (float, int)):
                continue
            date = excel_date(float(raw_date), book.datemode)
            obs = float(raw_obs) if isinstance(raw_obs, (float, int)) and raw_obs != "" else np.nan
            reference = (
                float(raw_reference)
                if isinstance(raw_reference, (float, int)) and raw_reference != ""
                else np.nan
            )
            records.append(
                {
                    "date": date,
                    "station_id": station["station_id"],
                    "station_code": station["station_code"],
                    "station_name": station["station_name"],
                    "component": station["component"],
                    "node_order": station["node_order"],
                    "observed_q_m3s": obs,
                    "physical_reference_q_m3s": reference,
                    "source_sheet": sheet.name,
                    "source_row": row_idx + 1,
                    "source_header": station["source_header"],
                    "target_holdout": station["station_code"] == "DSK",
                }
            )

    discharge = pd.DataFrame(records).sort_values(["date", "component", "node_order"])
    if discharge.duplicated(["date", "station_id"]).any():
        raise ValueError("Duplicate date/station records found")
    if (discharge["observed_q_m3s"].dropna() < 0).any():
        raise ValueError("Negative observed discharge found")

    project_nodes = pd.read_csv(args.nodes, dtype={"station_id": str})
    node_lookup = project_nodes.set_index("station_id")
    station_rows = []
    coverage_rows = []
    for station in STATIONS:
        station_id = str(station["station_id"])
        frame = discharge.loc[discharge.station_id == station_id].copy()
        first = frame.date.min()
        last = frame.date.max()
        expected = int((last - first).days + 1)
        observed_count = int(frame.observed_q_m3s.notna().sum())
        reference_count = int(frame.physical_reference_q_m3s.notna().sum())
        row = {
            "station_id": station_id,
            "station_code": station["station_code"],
            "station_name": station["station_name"],
            "component": station["component"],
            "node_order": station["node_order"],
            "target_holdout": station["station_code"] == "DSK",
            "longitude": np.nan,
            "latitude": np.nan,
            "upstream_area_km2": np.nan,
            "static_metadata_status": "not_in_project_nodes",
        }
        if station_id in node_lookup.index:
            source = node_lookup.loc[station_id]
            row.update(
                {
                    "longitude": float(source.longitude),
                    "latitude": float(source.latitude),
                    "upstream_area_km2": float(source.UP_AREA),
                    "static_metadata_status": "matched_project_nodes",
                }
            )
        station_rows.append(row)
        summary = {
            "station_id": station_id,
            "station_code": station["station_code"],
            "component": station["component"],
            "first_date": first,
            "last_date": last,
            "calendar_days": expected,
            "rows": int(len(frame)),
            "observed_days": observed_count,
            "observed_missing_days": int(expected - observed_count),
            "reference_days": reference_count,
            "observed_coverage_fraction": observed_count / expected,
            "observed_min_m3s": float(frame.observed_q_m3s.min()),
            "observed_mean_m3s": float(frame.observed_q_m3s.mean()),
            "observed_max_m3s": float(frame.observed_q_m3s.max()),
        }
        summary.update(
            metric_summary(
                frame.observed_q_m3s.to_numpy(float),
                frame.physical_reference_q_m3s.to_numpy(float),
            )
        )
        coverage_rows.append(summary)

    stations = pd.DataFrame(station_rows)
    coverage = pd.DataFrame(coverage_rows)
    edges = pd.DataFrame(EDGES)

    observed = discharge.pivot(index="date", columns="station_code", values="observed_q_m3s")
    overlap = pd.DataFrame(index=observed.columns, columns=observed.columns, dtype=int)
    for left in observed.columns:
        for right in observed.columns:
            overlap.loc[left, right] = int((observed[left].notna() & observed[right].notna()).sum())
    overlap.index.name = "station_code"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    discharge_path = args.output_dir / "multisite_discharge_2005.csv"
    stations_path = args.output_dir / "multisite_stations_2005.csv"
    edges_path = args.output_dir / "multisite_edges_2005.csv"
    coverage_path = args.output_dir / "multisite_coverage_2005.csv"
    overlap_path = args.output_dir / "multisite_overlap_days_2005.csv"
    discharge.to_csv(discharge_path, index=False, date_format="%Y-%m-%d")
    stations.to_csv(stations_path, index=False)
    edges.to_csv(edges_path, index=False)
    coverage.to_csv(coverage_path, index=False, date_format="%Y-%m-%d")
    overlap.to_csv(overlap_path)

    metadata = {
        "status": "created",
        "protocol": "five-station 2005 leave-one-station data audit",
        "held_out_target": {"station_code": "DSK", "station_id": "00705700"},
        "source": {
            "path": str(workbook_path),
            "sha256": sha256(workbook_path),
            "ranges": source_ranges,
            "observed_prefix": "OQ",
            "physical_reference_prefix": "MQ",
        },
        "topology_sources": [
            "data/processed/edges.csv",
            "https://www.mdpi.com/2073-4441/7/6/2821",
            "https://www.mdpi.com/2071-1050/17/4/1526",
        ],
        "topology_note": (
            "The Tarim XQM-to-AQK edge is a collapsed path because Yingbaza and Usman "
            "observations are absent from the workbook. It is not a claim of direct adjacency."
        ),
        "records": int(len(discharge)),
        "stations": int(len(stations)),
        "components": int(stations.component.nunique()),
        "all_station_overlap_days": int(observed.notna().all(axis=1).sum()),
        "target_observations_reserved_for_scoring": True,
        "target_observations_allowed_in_training": False,
        "outputs": [
            str(discharge_path),
            str(stations_path),
            str(edges_path),
            str(coverage_path),
            str(overlap_path),
        ],
    }
    metadata_path = args.output_dir / "multisite_metadata_2005.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print(coverage.to_string(index=False))


if __name__ == "__main__":
    main()
