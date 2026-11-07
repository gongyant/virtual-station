from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from vhs.metrics import regression_metrics


PREDICTION = Path(
    "outputs/virtual_station_mainline/external_2000_2001/"
    "frozen_predictions/frozen_external_predictions.csv"
)
METADATA = PREDICTION.with_name("frozen_prediction_metadata.json")
LABEL = Path(
    "data/processed/virtual_station_external/external_label_dsk_2000_2001.csv"
)
OUTPUT = PREDICTION.parent / "blind_scoring"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def score(frame: pd.DataFrame, methods: dict[str, str], scale: str) -> pd.DataFrame:
    rows = []
    for method, column in methods.items():
        values = frame[["target_q_m3s", column]].dropna()
        rows.append(
            {
                "scale": scale,
                "method": method,
                **regression_metrics(
                    values["target_q_m3s"].to_numpy(float),
                    values[column].to_numpy(float),
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(["scale", "nse"], ascending=[True, False])


def main() -> None:
    protocol = json.loads(METADATA.read_text(encoding="utf-8"))
    if protocol.get("status") != "predictions_frozen":
        raise ValueError("Prediction metadata is not marked as frozen")
    blind_fields = protocol.get("protocol", {})
    if any(
        blind_fields.get(field, True)
        for field in [
            "target_labels_loaded",
            "target_labels_used_for_training",
            "target_labels_used_for_model_selection",
        ]
    ):
        raise ValueError("Blind protocol failed: target labels entered prediction generation")

    prediction = pd.read_csv(PREDICTION, parse_dates=["date"])
    label = pd.read_csv(LABEL, parse_dates=["date"], dtype={"station_id": str})
    if set(label["role"].dropna().unique()) != {"sealed_external_label"}:
        raise ValueError("Target file is not the sealed external label file")
    scored = prediction.merge(
        label[["date", "target_q_m3s"]], on="date", how="inner", validate="one_to_one"
    )
    scored = scored.loc[scored["prediction_available"].astype(bool)].copy()

    methods = {
        "virtual_station_ensemble": "virtual_station_ensemble",
        "virtual_station_member_1": "virtual_station_member_1",
        "virtual_station_member_2": "virtual_station_member_2",
        "virtual_station_member_3": "virtual_station_member_3",
        "area_scaled_lag1": "baseline_area_scaled_lag1",
        "area_scaled_lag3": "baseline_area_scaled_lag3",
        "routed_upstream_lag3": "routed_upstream_q_lag3",
    }
    daily_metrics = score(scored, methods, "daily")

    monthly_columns = ["target_q_m3s", *methods.values()]
    indexed = scored.set_index("date")[monthly_columns]
    monthly = indexed.resample("MS").mean().reset_index()
    monthly["paired_days"] = indexed["target_q_m3s"].resample("MS").count().to_numpy()
    monthly["days_in_month"] = monthly["date"].dt.days_in_month
    monthly["coverage_fraction"] = monthly["paired_days"] / monthly["days_in_month"]
    # Do not let the final one-day fragment (2001-12-01) act as a monthly result.
    # January 2000 remains valid after the predeclared three-day routing warm-up.
    monthly = monthly.loc[monthly["coverage_fraction"] >= 0.80].copy()
    monthly_metrics = score(monthly, methods, "monthly_mean")
    metrics = pd.concat([daily_metrics, monthly_metrics], ignore_index=True)

    daily = daily_metrics.set_index("method")
    ensemble = daily.loc["virtual_station_ensemble"]
    baseline_names = ["area_scaled_lag1", "area_scaled_lag3"]
    beats_each_nse = all(ensemble["nse"] > daily.loc[name, "nse"] for name in baseline_names)
    beats_each_rmse = all(
        ensemble["rmse"] < daily.loc[name, "rmse"] for name in baseline_names
    )
    accepted = bool(beats_each_nse and beats_each_rmse)

    report = {
        "status": "completed_blind_external_scoring",
        "protocol": {
            **blind_fields,
            "prediction_sha256_at_label_open": sha256(PREDICTION),
            "sealed_label_sha256": sha256(LABEL),
            "paired_daily_rows": int(len(scored)),
            "paired_months": int(len(monthly)),
            "monthly_minimum_daily_coverage": 0.80,
            "label_opened_only_after_predictions_frozen": True,
            "post_label_parameter_tuning": False,
        },
        "daily_metrics": daily_metrics.to_dict("records"),
        "monthly_metrics": monthly_metrics.to_dict("records"),
        "acceptance_rule": (
            "The frozen ensemble must have higher daily NSE and lower daily RMSE "
            "than both predeclared area-scaled lag baselines."
        ),
        "candidate_status": "accepted" if accepted else "rejected",
        "operational_selection": (
            "virtual_station_ensemble" if accepted else "best_predeclared_baseline"
        ),
        "decision": (
            "The frozen ensemble passed the one-time external gate."
            if accepted
            else "The frozen ensemble failed the one-time external gate; retain the best "
            "predeclared baseline and do not tune on the external period."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    scored.to_csv(OUTPUT / "external_scored_daily_predictions.csv", index=False)
    monthly.to_csv(OUTPUT / "external_scored_monthly_predictions.csv", index=False)
    metrics.to_csv(OUTPUT / "external_validation_metrics.csv", index=False)
    (OUTPUT / "external_validation_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
