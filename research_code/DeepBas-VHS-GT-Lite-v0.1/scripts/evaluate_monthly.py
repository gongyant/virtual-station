from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from vhs.metrics import regression_metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default="outputs/holdout_dsk_strict_v2/test_predictions.csv",
    )
    parser.add_argument(
        "--output",
        default="outputs/holdout_dsk_strict_v2/monthly_predictions.csv",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.8,
    )
    args = parser.parse_args()

    daily = pd.read_csv(
        args.input,
        dtype={"station_id": str},
    )

    daily["date"] = pd.to_datetime(daily["date"])
    daily["month"] = (
        daily["date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    monthly = (
        daily.groupby(["station_id", "month"], as_index=False)
        .agg(
            observed=("observed", "mean"),
            predicted=("predicted", "mean"),
            observed_volume_m3=(
                "observed",
                lambda x: x.sum() * 86400.0,
            ),
            predicted_volume_m3=(
                "predicted",
                lambda x: x.sum() * 86400.0,
            ),
            valid_days=("date", "count"),
        )
    )

    monthly["calendar_days"] = (
        monthly["month"].dt.days_in_month
    )

    monthly["coverage"] = (
        monthly["valid_days"]
        / monthly["calendar_days"]
    )

    # 删除测试期首尾可能存在的不完整月份
    monthly = monthly[
        monthly["coverage"] >= args.min_coverage
    ].copy()

    monthly["observed_volume_1e8m3"] = (
        monthly["observed_volume_m3"] / 1e8
    )
    monthly["predicted_volume_1e8m3"] = (
        monthly["predicted_volume_m3"] / 1e8
    )

    metrics = regression_metrics(
        monthly["observed"].to_numpy(),
        monthly["predicted"].to_numpy(),
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(output, index=False)

    metrics_path = output.with_name(
        "monthly_metrics.json"
    )
    metrics_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(monthly.to_string(index=False))
    print("\nMonthly metrics:")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    print(f"\nsaved: {output}")
    print(f"saved: {metrics_path}")


if __name__ == "__main__":
    main()