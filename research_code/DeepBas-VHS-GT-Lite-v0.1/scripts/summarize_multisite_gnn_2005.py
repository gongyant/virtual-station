from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


ROOT = Path("outputs/virtual_station_mainline/multisite_2005")
RUNS = {
    "residual_gnn": ROOT / "residual_gnn",
    "residual_nograph": ROOT / "residual_nograph",
    "direct_gnn": ROOT / "direct_gnn",
    "direct_nograph": ROOT / "direct_nograph",
}


def main() -> None:
    rows = []
    predictions = {}
    for name, directory in RUNS.items():
        metrics = json.loads((directory / "test_metrics.json").read_text(encoding="utf-8"))
        rows.append({"model": name, "role": "trained_model", **metrics})
        frame = pd.read_csv(directory / "test_predictions.csv", parse_dates=["date"])
        predictions[name] = frame

    discharge = pd.read_csv(
        "data/processed/virtual_station_multisite/multisite_discharge_2005.csv",
        parse_dates=["date"],
        dtype={"station_id": str},
    )
    target = discharge.loc[
        (discharge.station_id == "00705700")
        & (discharge.date >= predictions["residual_gnn"].date.min())
        & (discharge.date <= predictions["residual_gnn"].date.max())
    ]
    physical = regression_metrics(
        target.observed_q_m3s.to_numpy(float),
        target.physical_reference_q_m3s.to_numpy(float),
    )
    rows.append({"model": "physical_reference_mq", "role": "frozen_baseline", **physical})
    summary = pd.DataFrame(rows).sort_values("nse", ascending=False)

    residual_pair = predictions["residual_gnn"].merge(
        predictions["residual_nograph"], on=["date", "station_id"], suffixes=("_graph", "_nograph")
    )
    graph_effect = residual_pair.predicted_graph - residual_pair.predicted_nograph
    conclusions = {
        "status": "completed_screening",
        "protocol": {
            "held_out_station": "00705700",
            "held_out_station_name": "大山口",
            "target_observations_used_in_training": False,
            "training_supervision_stations": 4,
            "test_dates": [
                str(target.date.min().date()),
                str(target.date.max().date()),
            ],
            "test_days": int(len(target)),
        },
        "ranking": summary.astype(object).where(pd.notna(summary), None).to_dict("records"),
        "residual_graph_effect": {
            "mean_absolute_prediction_difference_m3s": float(np.mean(np.abs(graph_effect))),
            "max_absolute_prediction_difference_m3s": float(np.max(np.abs(graph_effect))),
            "nse_difference_graph_minus_nograph": float(
                summary.set_index("model").loc["residual_gnn", "nse"]
                - summary.set_index("model").loc["residual_nograph", "nse"]
            ),
        },
        "decision": (
            "Keep the physical-reference residual architecture as the current 2005 benchmark. "
            "Do not claim a graph gain: graph and no-graph residual results are effectively tied. "
            "The next GNN change should normalize discharge by station or predict a dimensionless "
            "correction before further topology tuning."
        ),
    }
    out_dir = ROOT / "summary"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out_dir / "multisite_2005_model_comparison.csv", index=False)
    (out_dir / "multisite_2005_summary.json").write_text(
        json.dumps(conclusions, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(summary.to_string(index=False))
    print(json.dumps(conclusions["residual_graph_effect"], indent=2))


if __name__ == "__main__":
    main()
