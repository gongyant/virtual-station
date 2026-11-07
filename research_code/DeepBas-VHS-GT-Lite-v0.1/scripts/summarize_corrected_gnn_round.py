from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path("outputs/virtual_station_mainline/multisite_2005")
SEEDS = [7, 42, 123]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    rows = []
    for seed in SEEDS:
        graph_dir = ROOT / f"corrected_residual_gnn_seed{seed}"
        no_graph_dir = ROOT / f"corrected_residual_nograph_seed{seed}"
        graph = load_json(graph_dir / "test_metrics.json")
        edge = load_json(graph_dir / "edge_ablation.json")
        no_graph = load_json(no_graph_dir / "test_metrics.json")
        rows.append(
            {
                "seed": seed,
                "graph_nse": graph["nse"],
                "graph_rmse": graph["rmse"],
                "same_model_no_edges_nse": edge["same_model_no_edges"]["nse"],
                "causal_edge_nse_contribution": edge["nse_edge_contribution"],
                "independent_nograph_nse": no_graph["nse"],
                "paired_graph_minus_nograph_nse": graph["nse"] - no_graph["nse"],
            }
        )
    frame = pd.DataFrame(rows)
    baseline = pd.read_csv(ROOT / "summary/multisite_2005_model_comparison.csv")
    physical_nse = float(
        baseline.loc[baseline.model == "physical_reference_mq", "nse"].iloc[0]
    )
    scale010 = {
        "graph": load_json(ROOT / "corrected_scale010_gnn_seed42/test_metrics.json"),
        "edge_ablation": load_json(ROOT / "corrected_scale010_gnn_seed42/edge_ablation.json"),
        "nograph": load_json(ROOT / "corrected_scale010_nograph_seed42/test_metrics.json"),
    }
    aggregate = {
        "graph_nse_mean": float(frame.graph_nse.mean()),
        "graph_nse_std": float(frame.graph_nse.std(ddof=1)),
        "independent_nograph_nse_mean": float(frame.independent_nograph_nse.mean()),
        "independent_nograph_nse_std": float(frame.independent_nograph_nse.std(ddof=1)),
        "paired_graph_gain_mean": float(frame.paired_graph_minus_nograph_nse.mean()),
        "paired_graph_gain_std": float(frame.paired_graph_minus_nograph_nse.std(ddof=1)),
        "causal_edge_contribution_mean": float(frame.causal_edge_nse_contribution.mean()),
        "causal_edge_contribution_std": float(frame.causal_edge_nse_contribution.std(ddof=1)),
        "positive_causal_edge_seeds": int((frame.causal_edge_nse_contribution > 0).sum()),
    }
    report = {
        "status": "completed",
        "protocol": {
            "target": "DSK / 00705700",
            "target_observations_used_in_training": False,
            "test_days": 61,
            "seeds": SEEDS,
            "corrected_nonnegative_rule": (
                "Residual outputs are clipped only below the physical zero floor; "
                "positive references are no longer shifted by Softplus."
            ),
        },
        "physical_reference_nse": physical_nse,
        "seed_results": frame.to_dict("records"),
        "aggregate": aggregate,
        "scale010_screen": scale010,
        "invalidated_legacy_result": {
            "nse": 0.72288,
            "reason": "Softplus after residual addition introduced a systematic positive offset",
        },
        "decision": (
            "The corrected model provides causal evidence that directed edges can affect DSK "
            "predictions: removing edges reduced NSE for all three scale-0.25 seeds. However, "
            "the effect is highly seed-sensitive and the mean full-graph NSE remains below the "
            "frozen physical reference. Keep the graph as an experimental correction branch, "
            "not as the current operational winner. Next prioritize conservative gating or an "
            "ensemble that cannot degrade the physical reference when graph confidence is low."
        ),
    }
    out = ROOT / "corrected_gnn_round"
    out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out / "corrected_gnn_multiseed_metrics.csv", index=False)
    (out / "corrected_gnn_round_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(frame.to_string(index=False))
    print(json.dumps(aggregate, indent=2))
    print(report["decision"])


if __name__ == "__main__":
    main()
