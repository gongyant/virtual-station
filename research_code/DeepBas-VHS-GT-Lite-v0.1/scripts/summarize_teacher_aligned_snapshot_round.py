from __future__ import annotations

import json
from pathlib import Path

import numpy as np


ROOT = Path("outputs/virtual_station_mainline/multisite_2005")
OUTPUT = ROOT / "teacher_aligned_snapshot_round"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    seeds = [7, 42, 123]
    graph_by_seed = {
        seed: read_json(ROOT / f"snapshot_gnn_seed{seed}" / "test_metrics.json")
        for seed in seeds
    }
    graph_ablation_by_seed = {
        seed: read_json(ROOT / f"snapshot_gnn_seed{seed}" / "edge_ablation.json")
        for seed in seeds
    }
    no_graph_by_seed = {
        seed: read_json(ROOT / f"snapshot_nograph_seed{seed}" / "test_metrics.json")
        for seed in seeds
    }
    graph = graph_by_seed[42]
    graph_ablation = graph_ablation_by_seed[42]
    no_graph = no_graph_by_seed[42]
    safety_gate = read_json(ROOT / "physics_safety_gate" / "safety_gate_summary.json")
    physical = next(
        row for row in safety_gate["metrics"] if row["method"] == "physical_reference"
    )

    summary = {
        "status": "completed_multiseed_screen",
        "teacher_alignment": {
            "task": "same-time masked-node virtual hydrological station reconstruction",
            "uses_recurrent_encoder": False,
            "uses_same_time_graph_snapshot": True,
            "target_station": "DSK / 00705700",
            "target_observations_used_in_training": False,
            "physical_reference_used_as_residual_anchor": True,
            "nonnegative_discharge_constraint": True,
        },
        "test_protocol": {
            "year": 2005,
            "test_days": int(graph["n"]),
            "seeds": seeds,
            "warning": "short 61-day test period; external-period confirmation is required",
        },
        "metrics": {
            "physical_reference": physical,
            "snapshot_directed_graph": graph,
            "same_graph_model_with_edges_removed": graph_ablation["same_model_no_edges"],
            "independently_trained_snapshot_no_graph": no_graph,
        },
        "multiseed": {
            "graph": {
                "by_seed": graph_by_seed,
                "nse_mean": float(np.mean([v["nse"] for v in graph_by_seed.values()])),
                "nse_std": float(np.std([v["nse"] for v in graph_by_seed.values()])),
            },
            "no_graph": {
                "by_seed": no_graph_by_seed,
                "nse_mean": float(np.mean([v["nse"] for v in no_graph_by_seed.values()])),
                "nse_std": float(np.std([v["nse"] for v in no_graph_by_seed.values()])),
            },
            "causal_edge_nse_contribution": {
                "by_seed": {
                    str(seed): values["nse_edge_contribution"]
                    for seed, values in graph_ablation_by_seed.items()
                },
                "mean": float(
                    np.mean(
                        [
                            values["nse_edge_contribution"]
                            for values in graph_ablation_by_seed.values()
                        ]
                    )
                ),
                "positive_seed_count": int(
                    sum(
                        values["nse_edge_contribution"] > 0
                        for values in graph_ablation_by_seed.values()
                    )
                ),
            },
        },
        "comparisons": {
            "snapshot_graph_minus_previous_corrected_gnn_nse": (
                graph["nse"] - 0.2917866857705429
            ),
            "snapshot_graph_minus_physical_reference_nse": (
                graph["nse"] - physical["nse"]
            ),
            "causal_edge_nse_contribution": graph_ablation[
                "nse_edge_contribution"
            ],
            "snapshot_nograph_minus_physical_reference_nse": (
                no_graph["nse"] - physical["nse"]
            ),
        },
        "physical_data_readiness": {
            "available_now": [
                "directed station topology",
                "physical discharge reference",
                "observed discharge and observation mask",
                "upstream area for part of the network",
                "DSK reservoir flag in the formal graph",
            ],
            "missing_for_full_saint_venant": [
                "water-level time series",
                "river cross-section geometry",
                "bed elevation",
                "bed slope on the five-station 2005 graph",
                "Manning roughness",
                "lateral inflow or withdrawal observations",
            ],
            "full_saint_venant_loss_currently_valid": False,
            "reason": (
                "A Saint-Venant residual cannot be evaluated without stage, cross-section, "
                "bed geometry, and roughness. Fabricating these inputs would make the "
                "physics constraint scientifically invalid."
            ),
        },
        "decision": (
            "The no-recurrence snapshot formulation is retained because it matches the "
            "virtual-station task and slightly improves over the previous recurrent GNN. "
            "However, the current topology-only directed edge is not consistently useful, "
            "so this graph candidate is not promoted. The independently trained no-graph "
            "snapshot screen is competitive but remains provisional until external-period "
            "validation. Full Saint-Venant constraints are deferred until "
            "the required hydraulic observations are available."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "teacher_aligned_snapshot_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# Teacher-aligned virtual-station snapshot round

## Outcome

- The new model reconstructs DSK from a **same-time river-network snapshot** and contains no GRU/LSTM.
- DSK observations remain excluded from training; the physical discharge reference is the residual anchor.
- Snapshot directed graph, three-seed mean NSE {np.mean([v['nse'] for v in graph_by_seed.values()]):.3f} (std {np.std([v['nse'] for v in graph_by_seed.values()]):.3f}).
- Physical reference: NSE {physical['nse']:.3f}, RMSE {physical['rmse']:.2f} m3/s.
- Independently trained snapshot no-graph control, three-seed mean NSE {np.mean([v['nse'] for v in no_graph_by_seed.values()]):.3f} (std {np.std([v['nse'] for v in no_graph_by_seed.values()]):.3f}).
- Removing edges from each trained graph model gives a mean causal edge contribution of {np.mean([v['nse_edge_contribution'] for v in graph_ablation_by_seed.values()]):.3f}; positive in {sum(v['nse_edge_contribution'] > 0 for v in graph_ablation_by_seed.values())}/3 seeds. The current topology-only edge is therefore not accepted as beneficial.

## Physics gate

The present data support directed topology, non-negative discharge, a physical reference, and masked-node reconstruction. They do not contain water level, cross-sections, bed elevation/slope, Manning roughness, or measured lateral inflow. A full Saint-Venant continuity/momentum loss would therefore be unidentifiable and is not activated.

## Decision

Keep the snapshot task formulation, reject promotion of the current graph edge branch, and treat the no-graph improvement as provisional. The next confirmatory work is multi-seed snapshot screening plus the already-running frozen 2000-2001 external validation. Hydraulic constraints can be added only after the missing hydraulic fields are obtained.
"""
    (OUTPUT / "teacher_aligned_snapshot_report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
