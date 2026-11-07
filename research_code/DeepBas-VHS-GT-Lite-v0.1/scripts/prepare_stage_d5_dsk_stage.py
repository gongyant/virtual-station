from __future__ import annotations

import calendar
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5/d5c_stage_and_features"


# Manual visual transcription from Doc1 embedded_image_order_010.  The source table
# suppresses the integer part after a full value; a new full token resets the carried
# integer.  Tokens are preserved here so the reconstruction remains auditable.
TOKENS = {
    1: "5.36 63 73 65 63 63 6.15 5.74 28 32 58 46 32 70 64 71 81 6.00 5.82 82 74 73 80 87 80 79 79 87 81 6.04 5.83".split(),
    2: "5.84 56 94 97 77 90 92 79 67 70 61 82 70 75 74 89 75 76 88 89 81 76 81 77 74 79 93 6.02".split(),
    3: "5.96 86 87 83 97 90 91 82 79 87 92 79 77 83 94 98 86 79 85 77 65 85 59 95 31 94 49 87 65 54 95".split(),
    4: "5.89 68 66 62 47 84 6.00 5.89 92 55 80 68 86 93 6.01 10 12 11 12 19 23 47 7.00 47 40 34 22 14 06 6.93".split(),
    5: "6.91 90 74 83 99 7.15 6.91 72 70 59 43 22 33 34 18 30 34 13 14 07 5.96 6.03 12 08 5.98 6.18 03 11 06 10 07".split(),
    6: "6.06 01 27 28 52 44 53 68 67 57 44 36 49 32 47 51 51 45 37 41 48 54 66 75 76 78 74 78 80 88".split(),
    7: "6.88 71 70 70 86 87 73 70 71 82 60 52 51 54 59 47 36 51 52 58 54 58 39 41 54 54 41 51 42 53 53".split(),
    8: "6.42 52 54 63 64 65 84 78 62 53 49 47 61 58 63 63 62 63 66 67 75 73 55 85 74 69 63 33 38 35 14".split(),
    9: "6.19 46 44 73 81 75 75 71 50 57 35 23 22 43 39 47 46 20 35 30 49 39 42 49 41 5.98 6.30 41 53 26".split(),
    10: "6.16 19 26 18 26 04 12 38 33 5.93 99 91 6.07 5.95 6.24 16 15 5.82 6.25 5.86 6.09 12 24 5.97 6.30 37 11 25 26 01 01".split(),
    11: "6.00 5.82 5.87 89 81 81 88 87 85 83 93 6.11 5.85 81 55 92 70 96 97 6.06 5.95 79 98 84 6.02 5.63 99 6.08 5.62 6.07".split(),
    12: "6.06 5.99 6.01 10 5.85 68 91 71 89 85 82 96 90 89 93 76 78 82 77 74 78 74 75 76 78 79 81 73 73 71 79".split(),
}

PRINTED_MONTHLY_MEAN = {1: 5.71, 2: 5.80, 3: 5.81, 4: 6.26, 5: 6.38, 6: 6.52,
                        7: 6.59, 8: 6.59, 9: 6.43, 10: 6.13, 11: 5.88, 12: 5.83}


def expand_month(tokens: list[str]) -> list[float]:
    integer = None
    values: list[float] = []
    for token in tokens:
        if "." in token:
            value = float(token)
            integer = int(value)
        else:
            if integer is None:
                raise ValueError("suppressed token appears before a full token")
            value = integer + int(token) / 100.0
        values.append(value)
    return values


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    reconciliation = []
    for month in range(1, 13):
        expected = calendar.monthrange(2011, month)[1]
        if len(TOKENS[month]) != expected:
            raise AssertionError((month, len(TOKENS[month]), expected))
        values = expand_month(TOKENS[month])
        for day, (token, value) in enumerate(zip(TOKENS[month], values), 1):
            rows.append({
                "station_id": "00705700",
                "date": f"2011-{month:02d}-{day:02d}",
                "stage_m": value,
                "source_page": "embedded_image_order_010",
                "source_cell": f"month_{month:02d}_day_{day:02d}_cell",
                "original_ocr": token,
                "confirmed_value": value,
                "reviewer": "Codex逐格视觉复核（待第二位人工抽查）",
                "review_date": "2026-07-31",
                "confidence": "high" if "." in token else "medium",
                "quality_symbol": "",
                "needs_manual_check": False,
            })
        calc = sum(values) / len(values)
        printed = PRINTED_MONTHLY_MEAN[month]
        reconciliation.append({
            "month": month,
            "day_count": len(values),
            "calculated_mean_stage_m": calc,
            "printed_monthly_mean_stage_m": printed,
            "absolute_difference_m": abs(calc - printed),
            "rounded_to_0_01_matches": round(calc, 2) == printed,
        })
    out = pd.DataFrame(rows)
    assert len(out) == 365 and out.date.nunique() == 365 and out.stage_m.notna().all()
    out.to_csv(OUT / "daily_stage_dsk_2011_reviewed.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(reconciliation).to_csv(
        OUT / "dsk_daily_stage_monthly_reconciliation_2011.csv", index=False, encoding="utf-8-sig"
    )


if __name__ == "__main__":
    main()
