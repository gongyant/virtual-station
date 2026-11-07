from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
import xlrd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract BYBLK inputs and sealed DSK labels for an external virtual-station test."
        )
    )
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--sheet", default="2000-支流")
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    args = parse_args()
    book = xlrd.open_workbook(args.workbook)
    sheet = book.sheet_by_name(args.sheet)
    header = [str(sheet.cell_value(0, column)).strip() for column in range(sheet.ncols)]
    required = {
        "date": "Discharge",
        "target_q": "OQ-DSK-2000",
        "upstream_q": "OQ-BYBLK-2000",
    }
    column_index = {}
    for field, label in required.items():
        if label not in header:
            raise ValueError(f"Required column {label!r} was not found in {args.sheet!r}")
        column_index[field] = header.index(label)

    rows = []
    for row_index in range(1, sheet.nrows):
        date_value = sheet.cell_value(row_index, column_index["date"])
        if not isinstance(date_value, (int, float)):
            continue
        date = xlrd.xldate.xldate_as_datetime(date_value, book.datemode).date()
        upstream_q = sheet.cell_value(row_index, column_index["upstream_q"])
        target_q = sheet.cell_value(row_index, column_index["target_q"])
        if not isinstance(upstream_q, (int, float)) or not isinstance(
            target_q, (int, float)
        ):
            raise ValueError(f"Non-numeric discharge at source row {row_index + 1}")
        rows.append(
            {
                "date": pd.Timestamp(date),
                "upstream_q_m3s": float(upstream_q),
                "target_q_m3s": float(target_q),
                "source_row": row_index + 1,
            }
        )
    combined = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if combined.empty:
        raise ValueError("No daily discharge rows were extracted")
    if combined["date"].duplicated().any():
        raise ValueError("Duplicate dates were found")
    expected = pd.date_range(combined["date"].min(), combined["date"].max(), freq="D")
    missing_dates = expected.difference(pd.DatetimeIndex(combined["date"]))
    if len(missing_dates):
        raise ValueError(f"Missing {len(missing_dates)} dates in the extracted series")
    if (combined[["upstream_q_m3s", "target_q_m3s"]] < 0).any().any():
        raise ValueError("Negative discharge values were found")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    input_frame = combined[["date", "upstream_q_m3s", "source_row"]].copy()
    input_frame.insert(1, "station_id", args.upstream)
    input_frame["role"] = "model_input"
    label_frame = combined[["date", "target_q_m3s", "source_row"]].copy()
    label_frame.insert(1, "station_id", args.target)
    label_frame["role"] = "sealed_external_label"
    input_path = args.output_dir / "external_input_byblk_2000_2001.csv"
    label_path = args.output_dir / "external_label_dsk_2000_2001.csv"
    audit_path = args.output_dir / "external_runoff_audit_combined.csv"
    input_frame.to_csv(input_path, index=False, date_format="%Y-%m-%d")
    label_frame.to_csv(label_path, index=False, date_format="%Y-%m-%d")
    combined.to_csv(audit_path, index=False, date_format="%Y-%m-%d")

    metadata = {
        "status": "passed",
        "purpose": "independent_external_virtual_station_evaluation",
        "source": {
            "workbook": str(args.workbook),
            "sha256": sha256(args.workbook),
            "sheet": args.sheet,
            "column_mapping": required,
        },
        "protocol": {
            "upstream_station": args.upstream,
            "target_station": args.target,
            "upstream_file_role": "model_input",
            "target_file_role": "sealed_external_label",
            "target_labels_must_not_be_loaded_during_training_or_model_selection": True,
        },
        "quality_control": {
            "start": combined["date"].min().date().isoformat(),
            "end": combined["date"].max().date().isoformat(),
            "days": int(len(combined)),
            "unique_dates": int(combined["date"].nunique()),
            "missing_dates": int(len(missing_dates)),
            "upstream_missing": int(combined["upstream_q_m3s"].isna().sum()),
            "target_missing": int(combined["target_q_m3s"].isna().sum()),
            "upstream_min": float(combined["upstream_q_m3s"].min()),
            "upstream_max": float(combined["upstream_q_m3s"].max()),
            "target_min": float(combined["target_q_m3s"].min()),
            "target_max": float(combined["target_q_m3s"].max()),
        },
        "outputs": {
            "model_input": str(input_path),
            "sealed_target_label": str(label_path),
            "audit_combined": str(audit_path),
        },
    }
    metadata_path = args.output_dir / "external_runoff_metadata.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
