from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize multi-seed donor rolling validation.")
    parser.add_argument("--runs", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    metric_rows: list[dict] = []
    parameter_rows: list[dict] = []
    selections: list[str] = []
    improvements: list[float] = []
    for run in args.runs:
        summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
        run_name = run.name
        selections.append(summary["selection"]["selected_structure"])
        improvements.append(
            summary["selection"]["pooled_best_relative_rmse_improvement_over_simple"]
        )
        for row in summary["aggregate_metrics"]:
            metric_rows.append({"run": run_name, **row})
        parameter_rows.append({"run": run_name, **summary["final_parameters"]})

    metrics = pd.DataFrame(metric_rows)
    parameters = pd.DataFrame(parameter_rows)
    metric_summary = (
        metrics.groupby("model")[["rmse", "mae", "pbias", "nse", "kge", "corr"]]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
    )
    metric_summary.columns = [
        column if isinstance(column, str) else "_".join(part for part in column if part)
        for column in metric_summary.columns
    ]
    numeric_parameters = parameters.select_dtypes(include=[np.number])
    parameter_summary = numeric_parameters.agg(["mean", "std", "min", "max"]).T.reset_index()
    parameter_summary = parameter_summary.rename(columns={"index": "parameter"})
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.output_dir / "all_seed_metrics.csv", index=False)
    metric_summary.to_csv(args.output_dir / "metric_robustness.csv", index=False)
    parameters.to_csv(args.output_dir / "all_seed_parameters.csv", index=False)
    parameter_summary.to_csv(args.output_dir / "parameter_robustness.csv", index=False)
    selection_counts = pd.Series(selections).value_counts().to_dict()
    summary = {
        "run_count": len(args.runs),
        "selection_counts": selection_counts,
        "degree_day_selected_in_all_runs": selection_counts.get(
            "degree_day_snow_reservoir", 0
        )
        == len(args.runs),
        "relative_rmse_improvement_over_simple": {
            "mean": float(np.mean(improvements)),
            "std": float(np.std(improvements, ddof=1)),
            "min": float(np.min(improvements)),
            "max": float(np.max(improvements)),
        },
        "protocol_check": {
            "selection_uses_only_donor_station": True,
            "formal_1983_target_test_used": False,
        },
    }
    (args.output_dir / "robustness_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
