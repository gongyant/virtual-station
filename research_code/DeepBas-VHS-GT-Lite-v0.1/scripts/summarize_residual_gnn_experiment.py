from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.config import load_config
from vhs.data import TensorBundle
from vhs.metrics import regression_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize strict residual GNN ablations.")
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--configs", type=Path, nargs="+", required=True)
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--test-year", type=int, default=1983)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = TensorBundle.load(args.bundle)
    target_idx = list(map(str, bundle.station_ids)).index(args.target)
    reference_idx = list(map(str, bundle.feature_names)).index("residual_reference_q")
    dates = pd.DatetimeIndex(bundle.dates)
    test_mask = dates.year == args.test_year
    observed = bundle.y[test_mask, target_idx]
    reference = bundle.x[test_mask, target_idx, reference_idx]
    valid = np.isfinite(observed) & np.isfinite(reference)
    reference_metrics = regression_metrics(observed[valid], reference[valid])

    rows = [
        {
            "model": "frozen_physical_reference",
            "graph_layers": 0,
            "residual_scale": 0.0,
            "physics_anchor_weight": None,
            "best_donor_validation_nse": None,
            "correction_mean_m3s": 0.0,
            "correction_std_m3s": 0.0,
            "correction_max_abs_m3s": 0.0,
            **reference_metrics,
        }
    ]
    for config_path in args.configs:
        config = load_config(config_path)
        output_dir = Path(config["output_dir"])
        metrics = json.loads((output_dir / "test_metrics.json").read_text(encoding="utf-8"))
        predictions = pd.read_csv(output_dir / "test_predictions.csv")
        reference_values = np.asarray(
            [bundle.x[int(index), target_idx, reference_idx] for index in predictions["time_index"]],
            dtype=float,
        )
        correction = predictions["predicted"].to_numpy(float) - reference_values
        history = pd.read_csv(output_dir / "training_history.csv")
        rows.append(
            {
                "model": output_dir.name,
                "config": str(config_path),
                "graph_layers": int(config["model"].get("graph_layers", 0)),
                "residual_scale": float(config["model"].get("residual_scale", 0.0)),
                "physics_anchor_weight": float(
                    config["training"].get("physics_loss_weight", 0.0)
                ),
                "best_donor_validation_nse": float(history["val_nse"].max()),
                "correction_mean_m3s": float(correction.mean()),
                "correction_std_m3s": float(correction.std()),
                "correction_max_abs_m3s": float(np.max(np.abs(correction))),
                **metrics,
            }
        )
    results = pd.DataFrame(rows).sort_values("nse", ascending=False).reset_index(drop=True)
    best = results.iloc[0]
    graph_rows = results[results["graph_layers"].eq(1)]
    best_graph = graph_rows.sort_values("nse", ascending=False).iloc[0]
    baseline_nse = float(reference_metrics["nse"])
    summary = {
        "protocol": {
            "target_station": args.target,
            "target_labels_used_for_training": False,
            "target_labels_used_for_model_selection": False,
            "model_selection_station": "00705600",
            "test_year": args.test_year,
            "test_reuse_warning": (
                "1983 was previously inspected; these results are development diagnostics, "
                "not a new untouched external test."
            ),
        },
        "best_overall": best.to_dict(),
        "best_graph_model": best_graph.to_dict(),
        "reference_nse": baseline_nse,
        "best_graph_nse_gain_over_reference": float(best_graph["nse"] - baseline_nse),
        "graph_conclusion": (
            "No positive graph contribution under the current single-donor supervision"
            if float(best_graph["nse"]) <= float(
                results.loc[results["model"].eq("no_graph_scale025"), "nse"].iloc[0]
            )
            else "Graph contribution is positive"
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output_dir / "residual_gnn_ablation_metrics.csv", index=False)
    (args.output_dir / "residual_gnn_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(results.to_string(index=False))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
