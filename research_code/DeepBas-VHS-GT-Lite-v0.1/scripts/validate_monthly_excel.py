from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from vhs.metrics import regression_metrics


EXCEL_PATH = Path("data/raw/runoff/Q-dsk-byblk.xlsx")
PREDICTION_PATH = Path(
    "outputs/holdout_dsk_strict_v2/monthly_predictions.csv"
)
OUTPUT_DIR = Path(
    "outputs/holdout_dsk_strict_v2/monthly_validation"
)


def read_monthly_sheet(
    path: Path,
    sheet_name: str,
    station_id: str,
    station_name: str,
) -> pd.DataFrame:
    # header=None很重要，防止第一条数据被当成表头
    raw = pd.read_excel(
        path,
        sheet_name=sheet_name,
        header=None,
        usecols=[0, 1],
    )

    raw.columns = ["month", "monthly_q"]

    raw["month"] = (
        raw["month"]
        .astype(str)
        .str.strip()
        .str.replace("年", "-", regex=False)
        .str.replace("月", "", regex=False)
        .str.replace("/", "-", regex=False)
    )

    raw["month"] = pd.to_datetime(
        raw["month"],
        format="%Y-%m",
        errors="coerce",
    )

    raw["monthly_q"] = pd.to_numeric(
        raw["monthly_q"],
        errors="coerce",
    )

    raw = raw.dropna(
        subset=["month", "monthly_q"]
    ).copy()

    raw["month"] = (
        raw["month"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    raw["station_id"] = station_id
    raw["station_name"] = station_name

    raw = raw.drop_duplicates(
        subset=["month", "station_id"],
        keep="first",
    )

    return raw[
        [
            "month",
            "station_id",
            "station_name",
            "monthly_q",
        ]
    ].sort_values("month")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    byblk = read_monthly_sheet(
        EXCEL_PATH,
        sheet_name="BYBLK",
        station_id="00705600",
        station_name="巴音布鲁克",
    )

    dsk = read_monthly_sheet(
        EXCEL_PATH,
        sheet_name="DSK",
        station_id="00705700",
        station_name="大山口",
    )

    clean = pd.concat(
        [byblk, dsk],
        ignore_index=True,
    )

    clean.to_csv(
        OUTPUT_DIR / "monthly_observations_clean.csv",
        index=False,
        encoding="utf-8-sig",
    )

    predictions = pd.read_csv(
        PREDICTION_PATH,
        dtype={"station_id": str},
    )

    predictions["month"] = pd.to_datetime(
        predictions["month"]
    )

    # 正式比较只保留完整月份
    predictions = predictions[
        predictions["coverage"] >= 0.95
    ].copy()

    dsk_validation = dsk.rename(
        columns={
            "monthly_q": "provided_monthly_observed"
        }
    )

    comparison = predictions.merge(
        dsk_validation[
            [
                "month",
                "provided_monthly_observed",
            ]
        ],
        on="month",
        how="inner",
    )

    comparison = comparison.rename(
        columns={
            "observed":
                "daily_aggregated_observed",
            "predicted":
                "model_monthly_predicted",
        }
    )

    comparison["model_error"] = (
        comparison["model_monthly_predicted"]
        - comparison["provided_monthly_observed"]
    )

    comparison["model_relative_error_pct"] = (
        100.0
        * comparison["model_error"]
        / comparison["provided_monthly_observed"]
    )

    comparison["daily_monthly_difference"] = (
        comparison["daily_aggregated_observed"]
        - comparison["provided_monthly_observed"]
    )

    comparison.to_csv(
        OUTPUT_DIR
        / "dsk_monthly_validation_comparison.csv",
        index=False,
        encoding="utf-8-sig",
    )

    model_metrics = regression_metrics(
        comparison[
            "provided_monthly_observed"
        ].to_numpy(),
        comparison[
            "model_monthly_predicted"
        ].to_numpy(),
    )

    consistency_metrics = regression_metrics(
        comparison[
            "provided_monthly_observed"
        ].to_numpy(),
        comparison[
            "daily_aggregated_observed"
        ].to_numpy(),
    )

    results = {
        "model_vs_provided_monthly": model_metrics,
        "daily_aggregation_vs_provided_monthly":
            consistency_metrics,
    }

    metrics_path = (
        OUTPUT_DIR
        / "dsk_monthly_validation_metrics.json"
    )

    metrics_path.write_text(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("BYBLK months:", len(byblk))
    print("DSK months:", len(dsk))
    print("Overlapping complete test months:",
          len(comparison))

    print("\nComparison:")
    print(
        comparison[
            [
                "month",
                "provided_monthly_observed",
                "daily_aggregated_observed",
                "model_monthly_predicted",
                "model_error",
                "model_relative_error_pct",
            ]
        ].to_string(index=False)
    )

    print("\nMetrics:")
    print(
        json.dumps(
            results,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()