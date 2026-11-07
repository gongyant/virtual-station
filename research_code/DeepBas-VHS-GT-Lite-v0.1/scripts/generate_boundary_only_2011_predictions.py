from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(r"E:\CodexProject\DeepBas-VHS-GT-Lite-v0.1")
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b"
PARAMETER_FILE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a/boundary_only_frozen_parameters_2005.json"
INPUT_FILE = OUT / "boundary_only_2011_byblk_input_frozen.csv"
PREDICTION_FILE = OUT / "boundary_only_2011_predictions_frozen.csv"
MANIFEST_FILE = OUT / "boundary_only_2011_prediction_manifest.json"
EXPECTED_PARAMETER_SHA256 = "a24e946ae16b3ebb72f2f0765d1562f9c945a18692bd48471ec1300231f1a838"
PRIMARY_START, PRIMARY_END = date(2011, 5, 11), date(2011, 8, 31)
FULL_START, FULL_END = date(2011, 1, 11), date(2011, 12, 31)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if PREDICTION_FILE.exists() or MANIFEST_FILE.exists():
        raise SystemExit("frozen prediction artifacts already exist; regeneration is forbidden")
    parameter_sha = sha256(PARAMETER_FILE)
    if parameter_sha != EXPECTED_PARAMETER_SHA256:
        raise SystemExit("parameter SHA-256 mismatch; prediction forbidden")
    p = json.loads(PARAMETER_FILE.read_text(encoding="utf-8"))
    if p.get("model_name") != "C_EXT_boundary_only_K10" or p.get("K") != 10:
        raise SystemExit("unexpected frozen model identity")
    weights = {int(x["lag_day"]): float(x["weight"]) for x in p["weights"]}
    if sorted(weights) != list(range(11)) or any(v < 0 for v in weights.values()):
        raise SystemExit("invalid lag weights")
    intercept = float(p["intercept_b"])

    input_sha = sha256(INPUT_FILE)
    values = {}
    with INPUT_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["station_id", "date", "discharge_m3s"]:
            raise SystemExit("unexpected predictor input schema")
        for r in reader:
            if r["station_id"] != "00705600":
                raise SystemExit("predictor input contains a non-BYBLK station")
            dt = date.fromisoformat(r["date"])
            if dt in values:
                raise SystemExit(f"duplicate predictor date: {dt}")
            values[dt] = float(r["discharge_m3s"])
    if len(values) != 365 or min(values) != date(2011, 1, 1) or max(values) != date(2011, 12, 31):
        raise SystemExit("predictor input is not a complete 2011 daily series")

    rows = []
    dt = FULL_START
    while dt <= FULL_END:
        required = [dt - timedelta(days=k) for k in range(11)]
        if any(d not in values for d in required):
            raise SystemExit(f"missing required lag at {dt}")
        raw = intercept + sum(weights[k] * values[dt - timedelta(days=k)] for k in range(11))
        q_pred = max(0.0, raw)
        rows.append({
            "date": dt.isoformat(),
            "q_pred": f"{q_pred:.10f}",
            "window_primary": "true" if PRIMARY_START <= dt <= PRIMARY_END else "false",
            "window_full_year_diagnostic": "true",
            "parameter_sha256": parameter_sha,
            "input_sha256": input_sha,
        })
        dt += timedelta(days=1)
    if len(rows) != 355 or sum(r["window_primary"] == "true" for r in rows) != 113:
        raise SystemExit("frozen window row counts are inconsistent")

    with PREDICTION_FILE.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    prediction_sha = sha256(PREDICTION_FILE)
    program_sha = sha256(Path(__file__))
    manifest = {
        "schema_version": "1.0",
        "model_name": "C_EXT_boundary_only_K10",
        "evaluation_name_zh": "预注册跨年份评估",
        "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "prediction_file": str(PREDICTION_FILE.relative_to(ROOT)).replace("\\", "/"),
        "prediction_sha256": prediction_sha,
        "parameter_file": str(PARAMETER_FILE.relative_to(ROOT)).replace("\\", "/"),
        "parameter_sha256": parameter_sha,
        "predictor_input_file": str(INPUT_FILE.relative_to(ROOT)).replace("\\", "/"),
        "input_sha256": input_sha,
        "generator_program": str(Path(__file__).relative_to(ROOT)).replace("\\", "/"),
        "generator_program_sha256": program_sha,
        "prediction_row_count": len(rows),
        "prediction_date_range": {"start": rows[0]["date"], "end": rows[-1]["date"]},
        "primary_window_row_count": 113,
        "prediction_inputs_used": ["frozen 2005 parameter JSON", "2011 BYBLK date and discharge_m3s"],
        "used_2011_target_discharge": False,
        "used_2011_target_stage": False,
        "used_2011_target_measurements": False,
        "prediction_frozen_before_scoring": True,
    }
    MANIFEST_FILE.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "prediction_frozen", "rows": len(rows), "prediction_sha256": prediction_sha}, ensure_ascii=False))


if __name__ == "__main__":
    main()
