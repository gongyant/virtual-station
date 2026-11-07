from __future__ import annotations

import calendar
import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/teacher_raw/Doc1.docx"
SOURCE_IMAGE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d/_doc1_media/009.png"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10_byblk_stage"


# Manual visual transcription from embedded_image_order_009. The table prints a
# full value when the carried integer changes, then suppresses the integer and
# decimal point in following cells. Tokens are retained verbatim for audit.
TOKENS = {
    1: "4.30 27 26 26 24 24 24 23 23 24 24 23 23 22 22 21 21 20 19 18 17 16 15 15 13 13 14 15 15 16 18".split(),
    2: "4.19 19 19 21 21 23 21 18 18 18 15 13 13 13 09 08 06 06 04 04 07 08 08 08 08 08 11 13".split(),
    3: "4.13 11 11 11 11 09 10 08 07 10 10 10 09 09 09 09 08 08 08 08 02 05 07 07 08 08 18 17 17 17 18".split(),
    4: "4.13 05 3.86 63 59 55 55 54 53 54 55 59 61 65 72 90 4.00 21 56 99 5.14 08 01 4.88 80 72 61 58 49 49".split(),
    5: "4.42 36 20 05 3.96 94 98 99 96 90 85 83 83 84 85 84 85 89 91 92 89 88 89 89 87 86 85 84 85 84 85".split(),
    6: "3.86 88 91 93 91 92 93 96 97 96 96 96 99 4.05 12 15 18 19 22 22 23 25 21 13 06 00 3.99 98 99 99".split(),
    7: "3.96 99 4.04 07 09 10 08 09 07 3.98 92 90 90 89 91 96 4.00 03 05 05 03 02 01 00 3.99 98 99 4.00 3.99 96 96".split(),
    8: "4.01 08 07 06 05 03 02 01 03 03 05 08 08 09 11 10 08 04 00 3.98 95 93 92 92 91 90 97 4.01 02 06 10".split(),
    9: "4.12 11 10 09 07 04 01 3.97 94 92 91 90 90 88 88 87 86 87 87 86 87 86 86 86 85 85 84 84 83 83".split(),
    10: "3.83 84 83 83 83 83 83 83 83 83 80 82 85 87 85 84 84 84 83 84 84 85 85 84 84 84 83 82 81 79 76".split(),
    11: "3.74 75 75 75 75 75 75 73 71 71 72 71 71 71 71 69 71 66 67 69 68 70 70 67 68 70 69 69 69 69".split(),
    12: "3.68 65 67 63 66 66 68 68 69 59 70 70 72 73 73 73 73 72 73 4.45 58 57 57 50 47 44 44 41 41 41 42".split(),
}

PRINTED_MONTHLY_MEAN = {
    1: 4.20,
    2: 4.13,
    3: 4.10,
    4: 4.15,
    5: 3.93,
    6: 4.04,
    7: 4.00,
    8: 4.02,
    9: 3.92,
    10: 3.83,
    11: 3.71,
    12: 4.00,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expand_month(tokens: list[str]) -> list[float]:
    integer: int | None = None
    values = []
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
    rows = []
    reconciliation = []
    for month in range(1, 13):
        expected = calendar.monthrange(2011, month)[1]
        if len(TOKENS[month]) != expected:
            raise AssertionError(
                f"month {month}: {len(TOKENS[month])} tokens, expected {expected}"
            )
        values = expand_month(TOKENS[month])
        calculated = sum(values) / len(values)
        printed = PRINTED_MONTHLY_MEAN[month]
        rounded_match = round(calculated + 1e-12, 2) == printed
        reconciliation.append(
            {
                "month": month,
                "day_count": len(values),
                "calculated_mean_stage_m": calculated,
                "printed_monthly_mean_stage_m": printed,
                "absolute_difference_m": abs(calculated - printed),
                "rounded_to_0_01_matches": rounded_match,
            }
        )
        for day, (token, value) in enumerate(zip(TOKENS[month], values), 1):
            rows.append(
                {
                    "station_id": "00705600",
                    "station_name": "巴音布鲁克",
                    "date": f"2011-{month:02d}-{day:02d}",
                    "stage_m": value,
                    "stage_absolute_elevation_m": value + 2435.565,
                    "source_page": "embedded_image_order_009",
                    "source_cell": f"month_{month:02d}_day_{day:02d}_cell",
                    "source_token": token,
                    "confirmation_status": "manual_visual_confirmed_first_pass",
                    "reviewer": "Codex逐格视觉复核（待第二位人工抽查）",
                    "review_date": "2026-08-28",
                    "confidence": "high" if "." in token else "medium",
                    "needs_second_reviewer": True,
                }
            )
    daily = pd.DataFrame(rows)
    monthly = pd.DataFrame(reconciliation)
    if len(daily) != 365 or daily.date.nunique() != 365 or daily.stage_m.isna().any():
        raise AssertionError("daily stage completeness check failed")
    failed = monthly.loc[~monthly.rounded_to_0_01_matches, "month"].tolist()

    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "daily_stage_byblk_2011_reviewed.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(
        OUT / "byblk_daily_stage_monthly_reconciliation_2011.csv",
        index=False,
        encoding="utf-8-sig",
    )
    manifest = {
        "status": (
            "first_pass_complete_pending_second_reviewer"
            if not failed
            else "first_pass_complete_with_monthly_summary_discrepancy"
        ),
        "station_id": "00705600",
        "rows": len(daily),
        "date_range": [daily.date.min(), daily.date.max()],
        "monthly_mean_rounding_matches": int(monthly.rounded_to_0_01_matches.sum()),
        "monthly_summary_discrepancy_months": failed,
        "vertical_datum": "table stage + 2435.565 m = Yellow Sea datum elevation",
        "source_docx_sha256": sha256(SOURCE),
        "source_image_sha256": sha256(SOURCE_IMAGE),
        "use_policy": "diagnostic modeling only; formal promotion requires independent second review and resolution of every monthly summary discrepancy",
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(monthly.to_string(index=False))


if __name__ == "__main__":
    main()
