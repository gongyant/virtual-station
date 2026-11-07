from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze a physics-gated GNN ensemble before opening DSK labels."
    )
    parser.add_argument(
        "--gate-input",
        type=Path,
        default=Path(
            "data/processed/virtual_station_multisite/safety_gate_2005/"
            "gate_inputs_without_dsk_labels.csv"
        ),
    )
    parser.add_argument(
        "--label",
        type=Path,
        default=Path(
            "data/processed/virtual_station_multisite/safety_gate_2005/sealed_dsk_labels.csv"
        ),
    )
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("outputs/virtual_station_mainline/multisite_2005"),
    )
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 42, 123])
    parser.add_argument("--routing-lag-days", type=int, default=3)
    parser.add_argument("--max-reference-fraction", type=float, default=0.25)
    parser.add_argument("--max-gate-weight", type=float, default=0.5)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "outputs/virtual_station_mainline/multisite_2005/physics_safety_gate"
        ),
    )
    return parser.parse_args()


def build_frozen_predictions(args: argparse.Namespace) -> tuple[pd.DataFrame, dict]:
    gate_input = pd.read_csv(args.gate_input, parse_dates=["date"], dtype={"station_id": str})
    target_input = gate_input.loc[
        gate_input.station_id == "00705700", ["date", "observed_q_m3s", "physical_reference_q_m3s"]
    ].copy()
    if target_input.observed_q_m3s.notna().any():
        raise ValueError("Gate input contains unsealed DSK observations")
    target_input = target_input.rename(columns={"physical_reference_q_m3s": "physical_reference"})
    donor = gate_input.loc[
        gate_input.station_id == "00705600", ["date", "observed_q_m3s", "physical_reference_q_m3s"]
    ].copy()
    donor["donor_anomaly"] = donor.observed_q_m3s - donor.physical_reference_q_m3s
    donor = donor.sort_values("date")
    donor["donor_anomaly_lagged"] = donor.donor_anomaly.shift(args.routing_lag_days)

    prediction = target_input[["date", "physical_reference"]]
    seed_columns = []
    for seed in args.seeds:
        path = args.run_root / f"corrected_residual_gnn_seed{seed}" / "test_predictions.csv"
        member = pd.read_csv(path, parse_dates=["date"])[["date", "predicted"]]
        name = f"gnn_seed{seed}"
        member = member.rename(columns={"predicted": name})
        prediction = prediction.merge(member, on="date", how="inner")
        seed_columns.append(name)
    prediction = prediction.merge(
        donor[["date", "donor_anomaly_lagged"]], on="date", how="left"
    )
    corrections = prediction[seed_columns].sub(prediction.physical_reference, axis=0)
    prediction["ensemble_median_correction"] = corrections.median(axis=1)
    prediction["ensemble_correction_std"] = corrections.std(axis=1, ddof=1)
    positive = (corrections > 0).all(axis=1)
    negative = (corrections < 0).all(axis=1)
    prediction["all_members_same_sign"] = positive | negative
    prediction["sign_matches_donor"] = (
        prediction.ensemble_median_correction * prediction.donor_anomaly_lagged > 0
    )
    prediction["ensemble_confident"] = prediction.ensemble_correction_std <= (
        prediction.ensemble_median_correction.abs() + 1.0
    )
    prediction["gate_open"] = (
        prediction.all_members_same_sign
        & prediction.sign_matches_donor
        & prediction.ensemble_confident
        & prediction.donor_anomaly_lagged.notna()
    )

    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    area_ratio = float(nodes.loc["00705700", "UP_AREA"]) / float(
        nodes.loc["00705600", "UP_AREA"]
    )
    physical_cap = np.minimum(
        args.max_reference_fraction * prediction.physical_reference.abs(),
        area_ratio * prediction.donor_anomaly_lagged.abs(),
    ).fillna(0.0)
    accepted = np.sign(prediction.ensemble_median_correction) * np.minimum(
        prediction.ensemble_median_correction.abs(), physical_cap
    )
    accepted = accepted * float(args.max_gate_weight)
    prediction["accepted_correction"] = np.where(prediction.gate_open, accepted, 0.0)
    prediction["safety_gate_prediction"] = np.maximum(
        0.0, prediction.physical_reference + prediction.accepted_correction
    )
    prediction["ensemble_median_prediction"] = prediction[seed_columns].median(axis=1)

    protocol = {
        "status": "predictions_frozen_before_label_access",
        "target": "00705700",
        "target_observations_used": False,
        "seeds": args.seeds,
        "routing_lag_days": args.routing_lag_days,
        "area_ratio": area_ratio,
        "gate_rules": {
            "all_members_same_sign": True,
            "sign_must_match_lagged_upstream_anomaly": True,
            "ensemble_std_max": "abs(median correction) + 1 m3/s",
            "absolute_cap": "min(25% of target reference, area_ratio * upstream anomaly)",
            "maximum_gate_weight": args.max_gate_weight,
        },
        "gate_open_days": int(prediction.gate_open.sum()),
        "total_days": int(len(prediction)),
    }
    return prediction, protocol


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    prediction, protocol = build_frozen_predictions(args)
    prediction_path = args.output_dir / "frozen_safety_gate_predictions.csv"
    prediction.to_csv(prediction_path, index=False, date_format="%Y-%m-%d")
    (args.output_dir / "safety_gate_protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Labels are opened only after the rule and prediction file are frozen above.
    label = pd.read_csv(args.label, parse_dates=["date"], dtype={"station_id": str})
    scored = prediction.merge(label[["date", "sealed_observed_q_m3s"]], on="date", how="inner")
    methods = {
        "physics_safety_gate": "safety_gate_prediction",
        "physical_reference": "physical_reference",
        "ensemble_median": "ensemble_median_prediction",
        **{f"gnn_seed{seed}": f"gnn_seed{seed}" for seed in args.seeds},
    }
    metrics = []
    for method, column in methods.items():
        metrics.append(
            {
                "method": method,
                **regression_metrics(
                    scored.sealed_observed_q_m3s.to_numpy(float),
                    scored[column].to_numpy(float),
                ),
            }
        )
    metrics_frame = pd.DataFrame(metrics).sort_values("nse", ascending=False)
    metrics_frame.to_csv(args.output_dir / "safety_gate_metrics.csv", index=False)
    by_method = metrics_frame.set_index("method")
    accepted = bool(
        by_method.loc["physics_safety_gate", "nse"]
        >= by_method.loc["physical_reference", "nse"]
    )
    report = {
        "protocol": protocol,
        "metrics": metrics_frame.to_dict("records"),
        "candidate_status": "accepted" if accepted else "rejected",
        "operational_selection": (
            "physics_safety_gate" if accepted else "physical_reference"
        ),
        "decision": (
            "Accept the gate only if it improves or preserves the frozen physical reference. "
            + (
                "The condition passed."
                if accepted
                else "The condition failed after blind scoring, so predictions fall back to the physical reference."
            )
        ),
    }
    (args.output_dir / "safety_gate_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(protocol, ensure_ascii=False, indent=2))
    print(metrics_frame.to_string(index=False))


if __name__ == "__main__":
    main()
