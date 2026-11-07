from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


DISCHARGE = Path(
    "data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
)
RESERVOIR_GAP = Path(
    "outputs/virtual_station_mainline/formal/monthly_regulation_gap/"
    "monthly_regulation_gap.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/three_regime_round")
REGISTRY = Path("data/processed/virtual_station_regimes.csv")


def safe_metrics(observed: pd.Series, predicted: pd.Series) -> dict[str, float]:
    valid = observed.notna() & predicted.notna()
    return regression_metrics(observed[valid].to_numpy(), predicted[valid].to_numpy())


def best_nonnegative_lag(source: pd.Series, target: pd.Series, max_lag: int = 15) -> dict:
    rows = []
    for lag in range(max_lag + 1):
        aligned = pd.concat([source.shift(lag), target], axis=1).dropna()
        correlation = (
            float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1]))
            if len(aligned) >= 3
            else float("nan")
        )
        rows.append({"lag_days": lag, "correlation": correlation, "n": len(aligned)})
    finite = [row for row in rows if np.isfinite(row["correlation"])]
    return max(finite, key=lambda row: row["correlation"])


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    registry = pd.DataFrame(
        [
            {
                "regime_id": 1,
                "regime": "natural_reach",
                "current_example": "not yet available in the five-station bundle",
                "virtual_target": "river discharge from satellite/observed width",
                "required_observations": (
                    "river width; stage or rating samples; cross-section/bed slope/roughness"
                ),
                "current_status": "blocked_by_missing_width_and_hydraulic_geometry",
            },
            {
                "regime_id": 2,
                "regime": "reservoir_or_hydraulic_structure",
                "current_example": "BYBLK -> DSK",
                "virtual_target": "regulated DSK discharge",
                "required_observations": (
                    "upstream discharge; physical runoff reference; reservoir level/release if available"
                ),
                "current_status": "monthly_physical_baseline_and_unresolved_gap_completed",
            },
            {
                "regime_id": 3,
                "regime": "irrigation_groundwater_return_loop",
                "current_example": "ALAR -> XQM -> AQK",
                "virtual_target": "masked middle-station XQM discharge",
                "required_observations": (
                    "upstream/downstream discharge; reach distance; diversion/return-flow or groundwater proxy"
                ),
                "current_status": "two-endpoint_blind_baseline_and_reach_diagnostics_completed",
            },
        ]
    )
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    registry.to_csv(REGISTRY, index=False, encoding="utf-8-sig")

    discharge = pd.read_csv(DISCHARGE, parse_dates=["date"])
    observed = discharge.pivot_table(
        index="date", columns="station_code", values="observed_q_m3s", aggfunc="mean"
    )
    required = ["ALAR", "XQM", "AQK"]
    missing = [name for name in required if name not in observed]
    if missing:
        raise KeyError(f"Missing Tarim main-stem stations: {missing}")
    reach = observed[required].dropna().copy()

    # Strict blind baselines: XQM is not used to construct any prediction.
    # The equal-distance midpoint is explicitly provisional because the two
    # collapsed reach lengths are absent from the current graph.
    reach["pred_upstream_only"] = reach["ALAR"]
    reach["pred_downstream_only"] = reach["AQK"]
    reach["pred_two_endpoint_midpoint"] = 0.5 * (reach["ALAR"] + reach["AQK"])
    reach["pred_two_endpoint_geometric"] = np.sqrt(
        np.maximum(reach["ALAR"], 0.0) * np.maximum(reach["AQK"], 0.0)
    )
    metric_rows = []
    for column in [
        "pred_upstream_only",
        "pred_downstream_only",
        "pred_two_endpoint_midpoint",
        "pred_two_endpoint_geometric",
    ]:
        metric_rows.append({"method": column, **safe_metrics(reach["XQM"], reach[column])})
    agriculture_metrics = pd.DataFrame(metric_rows).sort_values("nse", ascending=False)

    reach["upper_reach_net_change_q"] = reach["XQM"] - reach["ALAR"]
    reach["lower_reach_net_change_q"] = reach["AQK"] - reach["XQM"]
    reach["total_reach_net_change_q"] = reach["AQK"] - reach["ALAR"]
    reach["upper_reach_net_change_1e6m3_day"] = (
        reach["upper_reach_net_change_q"] * 86400.0 / 1e6
    )
    reach["lower_reach_net_change_1e6m3_day"] = (
        reach["lower_reach_net_change_q"] * 86400.0 / 1e6
    )
    reach["xqm_outside_endpoint_range"] = (reach["XQM"] < reach[["ALAR", "AQK"]].min(axis=1)) | (
        reach["XQM"] > reach[["ALAR", "AQK"]].max(axis=1)
    )
    reach.reset_index().to_csv(
        OUTPUT / "agricultural_reach_daily_diagnostics.csv",
        index=False,
        encoding="utf-8-sig",
    )
    agriculture_metrics.to_csv(
        OUTPUT / "agricultural_virtual_station_metrics.csv", index=False
    )

    monthly_reach = reach.resample("MS").agg(
        ALAR=("ALAR", "mean"),
        XQM=("XQM", "mean"),
        AQK=("AQK", "mean"),
        upper_change=("upper_reach_net_change_q", "mean"),
        lower_change=("lower_reach_net_change_q", "mean"),
        total_change=("total_reach_net_change_q", "mean"),
        xqm_outside_fraction=("xqm_outside_endpoint_range", "mean"),
    )
    monthly_reach.to_csv(
        OUTPUT / "agricultural_reach_monthly_diagnostics.csv",
        encoding="utf-8-sig",
    )

    reservoir = pd.read_csv(RESERVOIR_GAP, parse_dates=["month"])
    reservoir_metrics = safe_metrics(
        reservoir["provided_regulated_q"], reservoir["physical_virtual_q"]
    )
    best_agriculture = agriculture_metrics.iloc[0].to_dict()
    summary = {
        "teacher_regimes": registry.to_dict(orient="records"),
        "regime_1_natural_reach": {
            "experiment_status": "not_run",
            "reason": (
                "No river-width time series or width-discharge calibration samples are "
                "present. Discharge cannot be inverted from width alone without a rating "
                "relation or hydraulic geometry assumptions."
            ),
            "next_valid_experiment": (
                "Collect satellite/field width at gauged natural reaches, fit a rating or "
                "hydraulic-geometry relation on observed stations, then perform leave-one-"
                "station width-to-discharge validation."
            ),
        },
        "regime_2_reservoir": {
            "experiment_status": "completed",
            "months": int(len(reservoir)),
            "physical_virtual_station_vs_teacher_monthly": reservoir_metrics,
            "unresolved_gap_volume_1e8m3": float(
                reservoir["regulation_gap_volume_1e8m3"].sum()
            ),
            "interpretation": (
                "The gap is a combined regulation/withdrawal/return-flow/missing-inflow "
                "diagnostic and is not identified reservoir release."
            ),
        },
        "regime_3_irrigation_return_loop": {
            "experiment_status": "completed_blind_screen",
            "days": int(len(reach)),
            "held_out_station": "XQM",
            "xqm_labels_used_to_construct_predictions": False,
            "best_blind_baseline": best_agriculture,
            "xqm_outside_endpoint_range_fraction": float(
                reach["xqm_outside_endpoint_range"].mean()
            ),
            "mean_upper_reach_net_change_q": float(
                reach["upper_reach_net_change_q"].mean()
            ),
            "mean_lower_reach_net_change_q": float(
                reach["lower_reach_net_change_q"].mean()
            ),
            "best_alar_to_xqm_lag": best_nonnegative_lag(reach["ALAR"], reach["XQM"]),
            "best_xqm_to_aqk_lag": best_nonnegative_lag(reach["XQM"], reach["AQK"]),
            "interpretation": (
                "Persistent reach losses and middle-station values outside the endpoint "
                "range are evidence that topology-only interpolation is insufficient. "
                "They do not by themselves identify irrigation withdrawal, infiltration, "
                "groundwater storage, and return flow separately."
            ),
        },
        "modeling_decision": {
            "shared_backbone": "masked same-time graph reconstruction with physical reference",
            "regime_specific_heads": {
                "natural": "width-to-discharge/rating head",
                "reservoir": "bounded regulation residual head",
                "agriculture": "diversion-storage-return memory head",
            },
            "do_not_do": (
                "Do not mix all three mechanisms into one unlabelled residual or claim "
                "that a topology-only GNN has learned reservoir/irrigation physics."
            ),
        },
    }
    (OUTPUT / "three_regime_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
