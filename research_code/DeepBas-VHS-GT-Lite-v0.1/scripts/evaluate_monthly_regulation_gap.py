from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate a target-label-free monthly virtual-station baseline against "
            "the teacher-provided regulated DSK monthly observations."
        )
    )
    parser.add_argument(
        "--predictions",
        type=Path,
        default=Path(
            "outputs/virtual_station_mainline/formal/mainline_monthly_predictions.csv"
        ),
    )
    parser.add_argument(
        "--monthly-observations",
        type=Path,
        default=Path(
            "outputs/holdout_dsk_strict_v2/monthly_validation/"
            "monthly_observations_clean.csv"
        ),
    )
    parser.add_argument(
        "--mainline-summary",
        type=Path,
        default=Path("outputs/virtual_station_mainline/formal/mainline_summary.json"),
    )
    parser.add_argument("--target-station", default="00705700")
    parser.add_argument("--year", type=int, default=1983)
    parser.add_argument("--physical-column", default="donor_physical_q")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(
            "outputs/virtual_station_mainline/formal/monthly_regulation_gap"
        ),
    )
    return parser.parse_args()


def finite_metrics(observed: pd.Series, predicted: pd.Series) -> dict[str, float]:
    mask = np.isfinite(observed.to_numpy()) & np.isfinite(predicted.to_numpy())
    return regression_metrics(observed.to_numpy()[mask], predicted.to_numpy()[mask])


def main() -> None:
    args = parse_args()
    predictions = pd.read_csv(args.predictions, parse_dates=["date"])
    if args.physical_column not in predictions.columns:
        raise KeyError(
            f"Missing physical reference column {args.physical_column!r} in "
            f"{args.predictions}"
        )

    observations = pd.read_csv(
        args.monthly_observations,
        dtype={"station_id": str},
        parse_dates=["month"],
    )
    observations["station_id"] = observations["station_id"].str.zfill(8)
    target = observations.loc[
        (observations["station_id"] == str(args.target_station).zfill(8))
        & (observations["month"].dt.year == args.year),
        ["month", "monthly_q"],
    ].rename(columns={"monthly_q": "provided_regulated_q"})

    prediction_columns = [
        "date",
        "observed",
        args.physical_column,
        "physics_stgnn",
        "hybrid_75donor_25physics",
    ]
    prediction_columns = [c for c in prediction_columns if c in predictions.columns]
    comparison = predictions[prediction_columns].rename(
        columns={"date": "month", "observed": "daily_aggregated_observed"}
    )
    comparison = comparison.loc[comparison["month"].dt.year == args.year]
    comparison = target.merge(comparison, on="month", how="inner", validate="one_to_one")
    comparison = comparison.sort_values("month").reset_index(drop=True)

    if comparison.empty:
        raise ValueError(
            "No overlapping monthly records between the teacher-provided observations "
            "and the virtual-station predictions."
        )

    comparison["calendar_days"] = comparison["month"].dt.days_in_month
    comparison["seconds_in_month"] = comparison["calendar_days"] * 86400.0
    comparison["physical_virtual_q"] = comparison[args.physical_column]
    comparison["regulation_gap_q"] = (
        comparison["provided_regulated_q"] - comparison["physical_virtual_q"]
    )
    comparison["regulation_gap_volume_1e8m3"] = (
        comparison["regulation_gap_q"] * comparison["seconds_in_month"] / 1e8
    )
    comparison["provided_volume_1e8m3"] = (
        comparison["provided_regulated_q"] * comparison["seconds_in_month"] / 1e8
    )
    comparison["physical_volume_1e8m3"] = (
        comparison["physical_virtual_q"] * comparison["seconds_in_month"] / 1e8
    )
    comparison["gap_fraction_of_observed"] = (
        comparison["regulation_gap_q"] / comparison["provided_regulated_q"]
    )
    comparison["gap_interpretation"] = np.where(
        comparison["regulation_gap_q"] >= 0,
        "regulated flow above physical virtual-station baseline",
        "regulated flow below physical virtual-station baseline",
    )

    mainline_summary = json.loads(args.mainline_summary.read_text(encoding="utf-8"))
    protocol = mainline_summary.get("protocol", {})
    physical_assumptions = mainline_summary.get("physical_assumptions", {})

    candidate_columns = [
        args.physical_column,
        "physics_stgnn",
        "hybrid_75donor_25physics",
    ]
    candidate_columns = [c for c in candidate_columns if c in comparison.columns]
    metrics = {
        name: finite_metrics(comparison["provided_regulated_q"], comparison[name])
        for name in candidate_columns
    }
    daily_monthly_consistency = finite_metrics(
        comparison["provided_regulated_q"],
        comparison["daily_aggregated_observed"],
    )

    total_provided_volume = float(comparison["provided_volume_1e8m3"].sum())
    total_physical_volume = float(comparison["physical_volume_1e8m3"].sum())
    total_gap_volume = float(comparison["regulation_gap_volume_1e8m3"].sum())
    peak_observed_row = comparison.loc[comparison["provided_regulated_q"].idxmax()]
    peak_physical_row = comparison.loc[comparison["physical_virtual_q"].idxmax()]

    checks = {
        "target_flow_excluded_from_inputs": protocol.get("target_flow_in_inputs") is False,
        "target_labels_excluded_from_training": protocol.get("target_labels_in_training")
        is False,
        "target_not_used_for_model_selection": protocol.get("model_selection_uses_target_station")
        is False,
        "all_physical_predictions_nonnegative": bool(
            (comparison["physical_virtual_q"] >= 0).all()
        ),
        "all_months_have_teacher_observations": len(comparison) == 12,
        "predefined_routing_lag_present": bool(
            physical_assumptions.get("predefined_routing_lag_days")
        ),
    }

    summary = {
        "purpose": (
            "Teacher-aligned monthly virtual hydrological station evaluation. The "
            "physical prediction is interpreted as an observable-data baseline, while "
            "the residual is a diagnostic of unresolved regulation, irrigation return "
            "flow, withdrawals, and other missing processes—not a recovered reservoir "
            "operation series."
        ),
        "protocol": {
            "target_station": str(args.target_station).zfill(8),
            "evaluation_year": args.year,
            "physical_reference": args.physical_column,
            "teacher_monthly_observations_used_for_training": False,
            "teacher_monthly_observations_used_for_scoring_only": True,
            "n_months": int(len(comparison)),
        },
        "constraint_checks": checks,
        "all_constraint_checks_passed": all(checks.values()),
        "metrics_vs_teacher_monthly_observations": metrics,
        "daily_observation_aggregation_vs_teacher_monthly_observations": (
            daily_monthly_consistency
        ),
        "annual_volume_diagnostic_1e8m3": {
            "teacher_provided_regulated": total_provided_volume,
            "physical_virtual_station": total_physical_volume,
            "unresolved_gap": total_gap_volume,
            "physical_fraction_of_teacher_observed": (
                total_physical_volume / total_provided_volume
                if total_provided_volume != 0
                else None
            ),
        },
        "peak_timing": {
            "teacher_observed_peak_month": str(peak_observed_row["month"].date()),
            "physical_peak_month": str(peak_physical_row["month"].date()),
            "month_offset": int(
                (peak_physical_row["month"].year - peak_observed_row["month"].year)
                * 12
                + peak_physical_row["month"].month
                - peak_observed_row["month"].month
            ),
        },
        "interpretation_limit": (
            "The regulation gap must not be labelled as reservoir release alone because "
            "reservoir operation, agricultural diversion/return flow, and ungauged "
            "incremental inflow are not separately observed."
        ),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(
        args.output_dir / "monthly_regulation_gap.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        [{"model": name, **values} for name, values in metrics.items()]
    ).sort_values("nse", ascending=False).to_csv(
        args.output_dir / "monthly_model_metrics.csv", index=False
    )
    (args.output_dir / "monthly_regulation_gap_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nSaved outputs to {args.output_dir}")


if __name__ == "__main__":
    main()
