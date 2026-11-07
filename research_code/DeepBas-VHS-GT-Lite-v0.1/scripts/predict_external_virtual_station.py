from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate_donor_physical_model import load_forcing
from evaluate_donor_rolling_validation import simulate_degree_day_snow_runoff_mm


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create frozen BYBLK-to-DSK external virtual-station predictions without "
            "loading target labels."
        )
    )
    parser.add_argument("--upstream-input", type=Path, required=True)
    parser.add_argument("--incremental-era5", type=Path, required=True)
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--parameter-summaries", type=Path, nargs="+", required=True)
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--routing-lag-days", type=int, default=3)
    parser.add_argument("--evaluation-start", required=True)
    parser.add_argument("--evaluation-end", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    upstream = pd.read_csv(args.upstream_input, dtype={"station_id": str})
    upstream["station_id"] = upstream["station_id"].str.zfill(8)
    if set(upstream["station_id"].unique()) != {args.upstream}:
        raise ValueError("The external input file must contain only the upstream station")
    upstream["date"] = pd.to_datetime(upstream["date"])
    upstream = upstream[["date", "upstream_q_m3s"]].sort_values("date")

    incremental = load_forcing(
        args.incremental_era5, "basin", f"{args.upstream}_to_{args.target}"
    ).sort_values("date")
    nodes = (
        pd.read_csv(args.nodes, dtype={"station_id": str})
        .assign(station_id=lambda frame: frame["station_id"].str.zfill(8))
        .set_index("station_id")
    )
    upstream_area = float(nodes.loc[args.upstream, "UP_AREA"])
    target_area = float(nodes.loc[args.target, "UP_AREA"])
    incremental_area = target_area - upstream_area
    evaluation_start = pd.Timestamp(args.evaluation_start)
    evaluation_end = pd.Timestamp(args.evaluation_end)

    parameter_sets = []
    for summary_path in args.parameter_summaries:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["selection"]["selected_structure"] != "degree_day_snow_reservoir":
            raise ValueError(f"Unexpected selected structure in {summary_path}")
        parameters = summary["final_parameters"]
        ordered = np.array(
            [
                parameters["runoff_coefficient"],
                parameters["recession"],
                parameters["baseflow_mm_day"],
                parameters["snowfall_temperature_threshold_c"],
                parameters["melt_temperature_threshold_c"],
                parameters["degree_day_factor_mm_c_day"],
            ],
            dtype=float,
        )
        parameter_sets.append((summary_path.stem + "_" + summary_path.parent.name, ordered))

    predictions = incremental[["date"]].copy()
    member_columns = []
    for member_index, (member_name, parameters) in enumerate(parameter_sets, start=1):
        local_runoff_mm = simulate_degree_day_snow_runoff_mm(
            incremental["precipitation_mm"].to_numpy(float),
            incremental["temperature_c"].to_numpy(float),
            incremental["snowmelt_mm"].to_numpy(float),
            incremental["evaporation_loss_mm"].to_numpy(float),
            parameters,
        )
        column = f"incremental_local_q_member_{member_index}"
        predictions[column] = local_runoff_mm * incremental_area / 86.4
        member_columns.append(column)

    predictions["incremental_local_q_ensemble"] = predictions[member_columns].mean(axis=1)
    predictions = predictions.merge(upstream, on="date", how="left")
    predictions["routed_upstream_q_lag3"] = predictions["upstream_q_m3s"].shift(
        args.routing_lag_days
    )
    ratio = target_area / upstream_area
    predictions["baseline_area_scaled_lag1"] = (
        predictions["upstream_q_m3s"].shift(1) * ratio
    )
    predictions["baseline_area_scaled_lag3"] = (
        predictions["routed_upstream_q_lag3"] * ratio
    )
    for member_index, column in enumerate(member_columns, start=1):
        predictions[f"virtual_station_member_{member_index}"] = np.maximum(
            predictions["routed_upstream_q_lag3"] + predictions[column], 0.0
        )
    virtual_member_columns = [
        f"virtual_station_member_{index}"
        for index in range(1, len(member_columns) + 1)
    ]
    predictions["virtual_station_ensemble"] = predictions[
        virtual_member_columns
    ].mean(axis=1)
    predictions = predictions.loc[
        predictions["date"].between(evaluation_start, evaluation_end)
    ].copy()
    predictions["prediction_available"] = predictions[
        "virtual_station_ensemble"
    ].notna()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction_path = args.output_dir / "frozen_external_predictions.csv"
    predictions.to_csv(prediction_path, index=False, date_format="%Y-%m-%d")
    metadata = {
        "status": "predictions_frozen",
        "protocol": {
            "target_station": args.target,
            "target_labels_loaded": False,
            "target_labels_used_for_training": False,
            "target_labels_used_for_model_selection": False,
            "evaluation_window": [args.evaluation_start, args.evaluation_end],
            "routing_lag_days": args.routing_lag_days,
            "prediction_rows": int(len(predictions)),
            "available_prediction_rows": int(predictions["prediction_available"].sum()),
        },
        "areas_km2": {
            "upstream": upstream_area,
            "target": target_area,
            "incremental": incremental_area,
        },
        "ensemble": {
            "members": len(parameter_sets),
            "parameter_sources": [str(path) for path in args.parameter_summaries],
            "member_names": [name for name, _ in parameter_sets],
        },
        "input_hashes": {
            "upstream_input_sha256": file_sha256(args.upstream_input),
            "incremental_era5_sha256": file_sha256(args.incremental_era5),
            "parameter_summary_sha256": {
                str(path): file_sha256(path) for path in args.parameter_summaries
            },
        },
        "output": str(prediction_path),
    }
    (args.output_dir / "frozen_prediction_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
