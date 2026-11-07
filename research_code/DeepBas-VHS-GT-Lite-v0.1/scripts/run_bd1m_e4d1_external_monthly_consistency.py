from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

WORKBOOK = ROOT / "data/raw/runoff/Q-dsk-byblk.xlsx"

DAILY_PRED = (
    EXP / "e4c_1983_daily_predictions.csv"
)

MONTHLY_OUT = (
    EXP / "e4d1_1983_monthly_comparison.csv"
)

METRICS_OUT = (
    EXP / "e4d1_external_monthly_metrics.csv"
)

REPORT_OUT = (
    EXP / "e4d1_external_monthly_report.md"
)


def nse(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    denominator = np.sum(
        (obs - np.mean(obs)) ** 2
    )

    if denominator == 0:
        return np.nan

    return float(
        1.0
        - np.sum((obs - pred) ** 2)
        / denominator
    )


def kge(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    if len(obs) < 2:
        return np.nan

    obs_std = np.std(obs, ddof=1)
    pred_std = np.std(pred, ddof=1)

    if obs_std == 0 or np.mean(obs) == 0:
        return np.nan

    r = np.corrcoef(obs, pred)[0, 1]

    alpha = pred_std / obs_std
    beta = np.mean(pred) / np.mean(obs)

    return float(
        1.0
        - np.sqrt(
            (r - 1.0) ** 2
            + (alpha - 1.0) ** 2
            + (beta - 1.0) ** 2
        )
    )


def metrics(obs, pred):
    obs = np.asarray(obs, float)
    pred = np.asarray(pred, float)

    mask = (
        np.isfinite(obs)
        & np.isfinite(pred)
    )

    obs = obs[mask]
    pred = pred[mask]

    return {
        "n_months": len(obs),
        "NSE": nse(obs, pred),
        "KGE": kge(obs, pred),
        "RMSE": float(
            np.sqrt(
                np.mean(
                    (obs - pred) ** 2
                )
            )
        ),
        "MAE": float(
            np.mean(
                np.abs(obs - pred)
            )
        ),
        "Bias": float(
            np.mean(pred - obs)
        ),
        "Pearson": float(
            np.corrcoef(obs, pred)[0, 1]
        ),
    }


def read_external_monthly_dsk():
    wb = load_workbook(
        WORKBOOK,
        read_only=True,
        data_only=True,
    )

    ws = wb["DSK"]

    rows = []

    for row_number, row in enumerate(
        ws.iter_rows(values_only=True),
        start=1,
    ):

        date_raw = (
            row[0]
            if len(row) >= 1
            else None
        )

        q_raw = (
            row[1]
            if len(row) >= 2
            else None
        )

        if date_raw is None:
            continue

        date = pd.to_datetime(
            str(date_raw),
            format="%Y-%m",
            errors="coerce",
        )

        q = pd.to_numeric(
            pd.Series([q_raw]),
            errors="coerce",
        ).iloc[0]

        if pd.isna(date) or pd.isna(q):
            continue

        rows.append(
            {
                "source_row": row_number,
                "month": date,
                "Q_external_monthly": float(q),
            }
        )

    wb.close()

    result = pd.DataFrame(rows)

    if result["month"].duplicated().any():
        raise RuntimeError(
            "Duplicate months in DSK monthly workbook."
        )

    return (
        result
        .sort_values("month")
        .reset_index(drop=True)
    )


def main():

    # ==================================================
    # 1. Load frozen E4C daily prediction
    # ==================================================

    daily = pd.read_csv(
        DAILY_PRED,
        parse_dates=["date"],
    )

    required = {
        "date",
        "Q_target_dsk",
        "Q_R1_route",
        "Q_monthly_sensitivity",
        "Q_Fourier6_final",
    }

    missing = required - set(daily.columns)

    if missing:
        raise RuntimeError(
            f"Missing E4C columns: {sorted(missing)}"
        )

    if len(daily) != 365:
        raise RuntimeError(
            f"Expected 365 days in E4C, got {len(daily)}"
        )

    if not (
        daily["date"].dt.year == 1983
    ).all():
        raise RuntimeError(
            "E4C daily file is not exclusively 1983."
        )

    # ==================================================
    # 2. Aggregate to monthly means
    # ==================================================

    daily["month"] = (
        daily["date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    monthly_model = (
        daily
        .groupby(
            "month",
            as_index=False,
        )
        .agg(
            days=("date", "size"),

            Q_daily_label_monthly=(
                "Q_target_dsk",
                "mean",
            ),

            Q_R1_monthly=(
                "Q_R1_route",
                "mean",
            ),

            Q_monthly_baseline=(
                "Q_monthly_sensitivity",
                "mean",
            ),

            Q_Fourier6_monthly=(
                "Q_Fourier6_final",
                "mean",
            ),
        )
    )

    if len(monthly_model) != 12:
        raise RuntimeError(
            f"Expected 12 model months, "
            f"got {len(monthly_model)}"
        )

    # ==================================================
    # 3. Read external monthly workbook
    # ==================================================

    external = read_external_monthly_dsk()

    external_1983 = external[
        external["month"].dt.year == 1983
    ].copy()

    if len(external_1983) != 12:
        raise RuntimeError(
            f"Expected 12 external DSK months "
            f"for 1983, got {len(external_1983)}"
        )

    # ==================================================
    # 4. One-to-one merge
    # ==================================================

    comparison = monthly_model.merge(
        external_1983,
        on="month",
        how="inner",
        validate="one_to_one",
    )

    if len(comparison) != 12:
        raise RuntimeError(
            "1983 monthly merge did not yield 12 months."
        )

    comparison[
        "daily_label_minus_external"
    ] = (
        comparison[
            "Q_daily_label_monthly"
        ]
        - comparison[
            "Q_external_monthly"
        ]
    )

    comparison.to_csv(
        MONTHLY_OUT,
        index=False,
    )

    # ==================================================
    # 5. Score fixed comparison
    # ==================================================

    obs = comparison[
        "Q_external_monthly"
    ].to_numpy(float)

    models = {
        "DAILY_LABEL_MONTHLY_MEAN":
            "Q_daily_label_monthly",

        "R1_ROUTING_ONLY_MONTHLY":
            "Q_R1_monthly",

        "MONTHLY_CLIMATOLOGY_MONTHLY":
            "Q_monthly_baseline",

        "FOURIER6_FINAL_MONTHLY":
            "Q_Fourier6_monthly",
    }

    result_rows = []

    for model_name, column in models.items():

        pred = comparison[
            column
        ].to_numpy(float)

        result_rows.append(
            {
                "model": model_name,
                **metrics(obs, pred),
            }
        )

    result = pd.DataFrame(
        result_rows
    )

    result.to_csv(
        METRICS_OUT,
        index=False,
    )

    # ==================================================
    # 6. Extract rows
    # ==================================================

    result_idx = result.set_index("model")

    daily_label = result_idx.loc[
        "DAILY_LABEL_MONTHLY_MEAN"
    ]

    r1 = result_idx.loc[
        "R1_ROUTING_ONLY_MONTHLY"
    ]

    seasonal = result_idx.loc[
        "MONTHLY_CLIMATOLOGY_MONTHLY"
    ]

    final = result_idx.loc[
        "FOURIER6_FINAL_MONTHLY"
    ]

    # ==================================================
    # 7. Diagnostic improvement
    # ==================================================

    final_gain_vs_r1 = (
        (
            float(r1.RMSE)
            - float(final.RMSE)
        )
        / float(r1.RMSE)
        * 100.0
    )

    # ==================================================
    # 8. Report with strict interpretation boundary
    # ==================================================

    report = f"""# VHS-BD1M E4D1 External Monthly Consistency Evaluation

## Evaluation identity

This phase evaluates the already-frozen E4C daily
predictions after monthly aggregation against the separately
stored DSK monthly series in:

data/raw/runoff/Q-dsk-byblk.xlsx

This workbook is numerically distinct from the 1978-1983
daily DSK observation series.

However, its primary official provenance and explicit unit
metadata remain unresolved.

Therefore this phase MUST NOT be described as
"official independent validation".

Accepted wording:

external monthly-series consistency evaluation

## Fixed protocol

- prediction year = 1983
- months = 12
- no model refit
- no routing refit
- no Fourier refit
- no test-based model selection
- daily predictions are arithmetic-monthly-mean aggregated

## External monthly series

- workbook = Q-dsk-byblk.xlsx
- sheet = DSK
- column A = year-month
- column B = candidate monthly discharge series
- 1983 external months = {len(external_1983)}

Known provenance boundary:

- workbook creator = 刘铁
- workbook internal creation date = 2018-06-09
- workbook SHA256 =
  D3173BF1BBB51F8295F319C42190C208AA395F927DC9A27731FA0F6ED6D6741A
- official provider = unresolved
- explicit unit metadata = unresolved

## Metrics against external monthly series

### Existing daily DSK labels aggregated monthly

- NSE = {float(daily_label.NSE):.6f}
- KGE = {float(daily_label.KGE):.6f}
- RMSE = {float(daily_label.RMSE):.6f}
- MAE = {float(daily_label.MAE):.6f}
- Bias = {float(daily_label.Bias):.6f}
- Pearson = {float(daily_label.Pearson):.6f}

### R1 routing only

- NSE = {float(r1.NSE):.6f}
- KGE = {float(r1.KGE):.6f}
- RMSE = {float(r1.RMSE):.6f}
- MAE = {float(r1.MAE):.6f}
- Bias = {float(r1.Bias):.6f}
- Pearson = {float(r1.Pearson):.6f}

### Monthly-climatology sensitivity baseline

- NSE = {float(seasonal.NSE):.6f}
- KGE = {float(seasonal.KGE):.6f}
- RMSE = {float(seasonal.RMSE):.6f}
- MAE = {float(seasonal.MAE):.6f}
- Bias = {float(seasonal.Bias):.6f}
- Pearson = {float(seasonal.Pearson):.6f}

### Frozen Fourier6 model

- NSE = {float(final.NSE):.6f}
- KGE = {float(final.KGE):.6f}
- RMSE = {float(final.RMSE):.6f}
- MAE = {float(final.MAE):.6f}
- Bias = {float(final.Bias):.6f}
- Pearson = {float(final.Pearson):.6f}

## Fixed comparison

- Fourier6 RMSE improvement vs R1 (%) =
  {final_gain_vs_r1:.6f}

## Interpretation boundary

These scores quantify consistency with an external stored
monthly DSK series whose numerical lineage is distinct from
the current 1978-1983 daily label series.

They do NOT establish official independent validation until
the workbook's primary source, station documentation,
variable definition, and units are independently confirmed.

## Status

E4D1_MONTHLY_AGGREGATION_COMPLETE=true

E4D1_EXTERNAL_MONTHLY_SERIES_EVALUATED=true

E4D1_NUMERICAL_LINEAGE_DISTINCT=true

E4D1_PRIMARY_PROVENANCE_RESOLVED=false

E4D1_OFFICIAL_INDEPENDENT_VALIDATION=false

E4D1_MODEL_CHANGED=false

READY_FOR_E5_WRITEUP=true
"""

    REPORT_OUT.write_text(
        report,
        encoding="utf-8",
    )

    print("E4D1 complete")

    print(
        f"external_1983_months={len(external_1983)}"
    )

    print(
        "external_daily_label_monthly_NSE="
        f"{float(daily_label.NSE):.6f}"
    )

    print(
        "external_daily_label_monthly_RMSE="
        f"{float(daily_label.RMSE):.6f}"
    )

    print(
        "external_R1_NSE="
        f"{float(r1.NSE):.6f}"
    )

    print(
        "external_R1_RMSE="
        f"{float(r1.RMSE):.6f}"
    )

    print(
        "external_Fourier6_NSE="
        f"{float(final.NSE):.6f}"
    )

    print(
        "external_Fourier6_KGE="
        f"{float(final.KGE):.6f}"
    )

    print(
        "external_Fourier6_RMSE="
        f"{float(final.RMSE):.6f}"
    )

    print(
        "external_Fourier6_MAE="
        f"{float(final.MAE):.6f}"
    )

    print(
        "external_Fourier6_Bias="
        f"{float(final.Bias):.6f}"
    )

    print(
        "Fourier6_external_RMSE_gain_vs_R1_pct="
        f"{final_gain_vs_r1:.6f}"
    )

    print(
        "E4D1_OFFICIAL_INDEPENDENT_VALIDATION=false"
    )

    print(
        "READY_FOR_E5_WRITEUP=true"
    )


if __name__ == "__main__":
    main()