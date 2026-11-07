from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]

MONTHLY_XLSX = (
    ROOT
    / "data/raw/runoff/Q-dsk-byblk.xlsx"
)

DAILY_CSV = (
    ROOT
    / "outputs/vhs_bd1m"
    / "bd1m_model_dataset_audit.csv"
)

EXP = (
    ROOT
    / "outputs/vhs_bd1m/experiments"
)

INVENTORY_OUT = (
    EXP
    / "e4d0_monthly_observation_inventory.csv"
)

DAILY_MONTHLY_OUT = (
    EXP
    / "e4d0_daily_derived_monthly_dsk.csv"
)

REPORT_OUT = (
    EXP
    / "e4d0_monthly_observation_audit.md"
)


def main():

    if not MONTHLY_XLSX.exists():
        raise FileNotFoundError(
            MONTHLY_XLSX
        )

    # --------------------------------------------------
    # 1. Workbook inventory
    # --------------------------------------------------

    wb = load_workbook(
        MONTHLY_XLSX,
        read_only=True,
        data_only=True,
    )

    rows = []

    print("WORKBOOK =", MONTHLY_XLSX)

    for ws in wb.worksheets:

        nonempty = 0

        first_values = []

        for i, row in enumerate(
            ws.iter_rows(values_only=True),
            start=1,
        ):

            values = list(row)

            if any(
                value is not None
                for value in values
            ):
                nonempty += 1

            if i <= 15:
                first_values.append(
                    values
                )

        rows.append(
            {
                "sheet": ws.title,
                "max_row": ws.max_row,
                "max_column": ws.max_column,
                "nonempty_rows": nonempty,
            }
        )

        print()
        print("=" * 70)
        print("SHEET:", ws.title)
        print(
            "rows=",
            ws.max_row,
            "cols=",
            ws.max_column,
        )

        for i, values in enumerate(
            first_values,
            start=1,
        ):
            print(i, values)

    wb.close()

    pd.DataFrame(
        rows
    ).to_csv(
        INVENTORY_OUT,
        index=False,
    )

    # --------------------------------------------------
    # 2. Independently derive monthly DSK
    #    from development daily Q
    # --------------------------------------------------

    daily = pd.read_csv(
        DAILY_CSV,
        parse_dates=["date"],
    )

    required = {
        "date",
        "Q_target_dsk",
    }

    if not required.issubset(
        daily.columns
    ):
        raise RuntimeError(
            "Daily dataset missing "
            "date/Q_target_dsk."
        )

    daily = (
        daily[
            [
                "date",
                "Q_target_dsk",
            ]
        ]
        .sort_values("date")
        .copy()
    )

    if len(daily) != 2191:
        raise RuntimeError(
            f"Expected 2191 daily rows, "
            f"got {len(daily)}"
        )

    if daily[
        "Q_target_dsk"
    ].isna().any():
        raise RuntimeError(
            "Daily DSK contains missing Q."
        )

    daily["year"] = (
        daily["date"].dt.year
    )

    daily["month"] = (
        daily["date"].dt.month
    )

    monthly = (
        daily
        .groupby(
            ["year", "month"],
            as_index=False,
        )
        .agg(
            Q_DSK_daily_mean=(
                "Q_target_dsk",
                "mean",
            ),
            days=(
                "Q_target_dsk",
                "size",
            ),
        )
    )

    monthly.to_csv(
        DAILY_MONTHLY_OUT,
        index=False,
    )

    if len(monthly) != 72:
        raise RuntimeError(
            f"Expected 72 months, "
            f"got {len(monthly)}"
        )

    # --------------------------------------------------
    # 3. Stop before claiming admissibility
    # --------------------------------------------------

    report = f"""# VHS-BD1M E4D0 Monthly Observation Audit

## Candidate

- file:
  data/raw/runoff/Q-dsk-byblk.xlsx

- workbook exists:
  true

- sheet count:
  {len(rows)}

## Daily reference

The existing development DSK daily observations are
aggregated independently to monthly mean discharge for
provenance comparison.

- daily period:
  1978-01-01..1983-12-31

- expected months:
  72

- derived months:
  {len(monthly)}

- aggregation:
  arithmetic monthly mean of daily mean discharge

## Important scientific gate

The workbook has NOT yet been declared an independent
official validation source merely because it exists.

Before E4D final scoring, confirm:

1. station identity = DSK / 00705700 / 大山口;
2. temporal coverage;
3. monthly variable definition;
4. units;
5. missing values;
6. original provenance;
7. whether values were derived from the same
   BYBLK-DSK daily dataset.

If workbook monthly values are identical or nearly identical
to monthly means derived from the existing daily DSK series,
the monthly workbook must NOT be described as an independent
validation source.

MONTHLY_WORKBOOK_FOUND=true

MONTHLY_STATION_IDENTITY_CONFIRMED=false

MONTHLY_UNIT_CONFIRMED=false

MONTHLY_PROVENANCE_CONFIRMED=false

MONTHLY_INDEPENDENCE_CONFIRMED=false

READY_FOR_E4D_FINAL_SCORING=false
"""

    REPORT_OUT.write_text(
        report,
        encoding="utf-8",
    )

    print()
    print("E4D0 preliminary audit complete")
    print(
        f"workbook_sheets={len(rows)}"
    )
    print(
        f"daily_derived_months={len(monthly)}"
    )
    print(
        "MONTHLY_WORKBOOK_FOUND=true"
    )
    print(
        "READY_FOR_E4D_FINAL_SCORING=false"
    )


if __name__ == "__main__":
    main()