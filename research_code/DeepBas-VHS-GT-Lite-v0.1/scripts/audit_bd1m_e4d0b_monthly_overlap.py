from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "outputs/vhs_bd1m/experiments"

WORKBOOK = ROOT / "data/raw/runoff/Q-dsk-byblk.xlsx"
DAILY_DERIVED = EXP / "e4d0_daily_derived_monthly_dsk.csv"

COMPARE_OUT = EXP / "e4d0b_monthly_overlap_comparison.csv"
REPORT_OUT = EXP / "e4d0b_monthly_overlap_report.md"


def parse_month(value):
    if value is None:
        return pd.NaT

    text = str(value).strip()

    try:
        return pd.to_datetime(
            text,
            format="%Y-%m"
        )
    except ValueError:
        return pd.to_datetime(
            text,
            errors="coerce"
        )


def main():

    # ==================================================
    # 1. Read DSK raw monthly series
    # ==================================================

    wb_values = load_workbook(
        WORKBOOK,
        read_only=True,
        data_only=True
    )

    if "DSK" not in wb_values.sheetnames:
        raise RuntimeError("DSK sheet not found.")

    ws = wb_values["DSK"]

    rows = []

    for row_idx, row in enumerate(
        ws.iter_rows(values_only=True),
        start=1
    ):

        date_raw = row[0] if len(row) >= 1 else None
        q_raw = row[1] if len(row) >= 2 else None

        date = parse_month(date_raw)
        q = pd.to_numeric(
            pd.Series([q_raw]),
            errors="coerce"
        ).iloc[0]

        if pd.isna(date) and pd.isna(q):
            continue

        rows.append(
            {
                "source_row": row_idx,
                "date_raw": date_raw,
                "month": date,
                "Q_workbook": q,
            }
        )

    wb_values.close()

    monthly_book = pd.DataFrame(rows)

    monthly_book = monthly_book[
        monthly_book["month"].notna()
        & monthly_book["Q_workbook"].notna()
    ].copy()

    monthly_book["year"] = (
        monthly_book["month"].dt.year
    )

    monthly_book["month_number"] = (
        monthly_book["month"].dt.month
    )

    monthly_book = (
        monthly_book
        .sort_values("month")
        .reset_index(drop=True)
    )

    if monthly_book["month"].duplicated().any():
        dup = monthly_book[
            monthly_book["month"].duplicated(
                keep=False
            )
        ]
        raise RuntimeError(
            f"Duplicate DSK months found:\n{dup}"
        )

    # ==================================================
    # 2. Check whether column B itself contains formulas
    # ==================================================

    wb_formula = load_workbook(
        WORKBOOK,
        read_only=False,
        data_only=False
    )

    ws_formula = wb_formula["DSK"]

    column_b_formula_count = 0
    column_g_formula_count = 0
    column_h_formula_count = 0

    for r in range(
        1,
        ws_formula.max_row + 1
    ):

        for column, label in [
            ("B", "B"),
            ("G", "G"),
            ("H", "H"),
        ]:

            value = ws_formula[f"{column}{r}"].value

            is_formula = (
                isinstance(value, str)
                and value.startswith("=")
            )

            if not is_formula:
                continue

            if label == "B":
                column_b_formula_count += 1
            elif label == "G":
                column_g_formula_count += 1
            elif label == "H":
                column_h_formula_count += 1

    wb_formula.close()

    # ==================================================
    # 3. Load monthly means independently derived
    #    from daily DSK series
    # ==================================================

    daily_month = pd.read_csv(
        DAILY_DERIVED
    )

    required = {
        "year",
        "month",
        "Q_DSK_daily_mean",
        "days",
    }

    missing = required - set(daily_month.columns)

    if missing:
        raise RuntimeError(
            f"Missing daily-derived columns: {missing}"
        )

    daily_month = daily_month.rename(
        columns={
            "month": "month_number"
        }
    )

    daily_month["month"] = pd.to_datetime(
        dict(
            year=daily_month["year"],
            month=daily_month["month_number"],
            day=1,
        )
    )

    # ==================================================
    # 4. Compare overlap
    # ==================================================

    overlap = monthly_book.merge(
        daily_month[
            [
                "year",
                "month_number",
                "month",
                "Q_DSK_daily_mean",
                "days",
            ]
        ],
        on=[
            "year",
            "month_number",
            "month",
        ],
        how="inner",
        validate="one_to_one",
    )

    if overlap.empty:
        raise RuntimeError(
            "No overlapping months."
        )

    overlap["difference"] = (
        overlap["Q_workbook"]
        - overlap["Q_DSK_daily_mean"]
    )

    overlap["abs_difference"] = (
        overlap["difference"].abs()
    )

    overlap["workbook_equals_daily_2dp"] = (
        np.round(
            overlap["Q_workbook"], 2
        )
        ==
        np.round(
            overlap["Q_DSK_daily_mean"], 2
        )
    )

    overlap["within_0_01"] = (
        overlap["abs_difference"]
        <= 0.01
    )

    overlap["within_0_05"] = (
        overlap["abs_difference"]
        <= 0.05
    )

    overlap.to_csv(
        COMPARE_OUT,
        index=False
    )

    # ==================================================
    # 5. Summary
    # ==================================================

    n = len(overlap)

    rmse = float(
        np.sqrt(
            np.mean(
                overlap["difference"] ** 2
            )
        )
    )

    mae = float(
        overlap["abs_difference"].mean()
    )

    max_abs = float(
        overlap["abs_difference"].max()
    )

    correlation = float(
        overlap[
            [
                "Q_workbook",
                "Q_DSK_daily_mean",
            ]
        ].corr().iloc[0, 1]
    )

    match_2dp = int(
        overlap[
            "workbook_equals_daily_2dp"
        ].sum()
    )

    within_001 = int(
        overlap["within_0_01"].sum()
    )

    within_005 = int(
        overlap["within_0_05"].sum()
    )

    # Numerical lineage diagnostic only.
    #
    # This does NOT prove provenance.
    nearly_same = bool(
        within_005 / n >= 0.95
    )

    if nearly_same:
        numerical_interpretation = (
            "Workbook monthly Q is numerically "
            "almost identical to monthly means derived "
            "from the existing daily DSK observations. "
            "It must not be treated as independent "
            "validation unless separate official provenance "
            "is documented."
        )
    else:
        numerical_interpretation = (
            "Workbook monthly Q is not simply reproduced "
            "by arithmetic monthly means of the existing "
            "daily DSK observations. This supports distinct "
            "numerical lineage, but independent official "
            "provenance still requires documentary evidence."
        )

    report = f"""# VHS-BD1M E4D0B Monthly Overlap Audit

## Workbook DSK series

- parsed rows = {len(monthly_book)}
- start = {monthly_book["month"].min().date()}
- end = {monthly_book["month"].max().date()}
- column-B formula count = {column_b_formula_count}
- column-G formula count = {column_g_formula_count}
- column-H formula count = {column_h_formula_count}

Column B is treated as the candidate raw monthly DSK
discharge series.

Columns G/H are not used for validation.

## Daily/monthly overlap

- overlap months = {n}
- overlap start = {overlap["month"].min().date()}
- overlap end = {overlap["month"].max().date()}

Comparison:

- correlation = {correlation:.10f}
- RMSE difference = {rmse:.10f}
- MAE difference = {mae:.10f}
- maximum absolute difference = {max_abs:.10f}
- exact after rounding to 2 decimals = {match_2dp}/{n}
- abs difference <= 0.01 = {within_001}/{n}
- abs difference <= 0.05 = {within_005}/{n}

## Numerical lineage interpretation

{numerical_interpretation}

## Important limitation

Numerical disagreement alone does NOT prove that this
workbook is an independent official observation source.

The following still require documentary/provenance
confirmation:

- DSK identity = 大山口 / 00705700
- variable definition = monthly mean discharge
- unit = m3/s
- original provider/source
- whether workbook values came from an official hydrological
  yearbook or another independent record

## Status

MONTHLY_DSK_SERIES_PARSED=true

MONTHLY_COLUMN_B_IS_FORMULA={str(column_b_formula_count > 0).lower()}

MONTHLY_NUMERICALLY_NEAR_DAILY_AGGREGATE={str(nearly_same).lower()}

MONTHLY_PROVENANCE_CONFIRMED=false

MONTHLY_INDEPENDENCE_CONFIRMED=false

READY_FOR_E4D_FINAL_SCORING=false
"""

    REPORT_OUT.write_text(
        report,
        encoding="utf-8"
    )

    print("E4D0B complete")
    print(
        "workbook_DSK_start="
        f"{monthly_book['month'].min().date()}"
    )
    print(
        "workbook_DSK_end="
        f"{monthly_book['month'].max().date()}"
    )
    print(
        f"workbook_DSK_rows={len(monthly_book)}"
    )
    print(
        f"column_B_formula_count="
        f"{column_b_formula_count}"
    )
    print(
        f"overlap_months={n}"
    )
    print(
        f"correlation={correlation:.10f}"
    )
    print(
        f"overlap_RMSE_difference={rmse:.10f}"
    )
    print(
        f"overlap_MAE_difference={mae:.10f}"
    )
    print(
        f"max_abs_difference={max_abs:.10f}"
    )
    print(
        f"exact_2dp={match_2dp}/{n}"
    )
    print(
        f"within_0_01={within_001}/{n}"
    )
    print(
        f"within_0_05={within_005}/{n}"
    )
    print(
        "MONTHLY_NUMERICALLY_NEAR_DAILY_AGGREGATE="
        f"{str(nearly_same).lower()}"
    )


if __name__ == "__main__":
    main()