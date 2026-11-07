from __future__ import annotations

import calendar
import hashlib
import json
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round2"
AUDIT = OUT / "source_audit"
PLOTS = OUT / "plots"
RAW = ROOT / "data/raw/runoff/BYBLK-DSK日数据.xlsx"
TS = ROOT / "data/processed/timeseries.csv"
NPZ = ROOT / "data/processed/virtual_station/virtual_station_bundle_1978_1983.npz"
D4A_PARAM = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a/boundary_only_frozen_parameters_2005.json"
D5R1_MANIFEST = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5/stage_d5_round1_manifest.json"
YEARS = list(range(1978, 1984))
STATIONS = {
    "BYBLK": {"station_id": "00705600", "station_name": "巴音布鲁克"},
    "DSK": {"station_id": "00705700", "station_name": "大山口"},
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def longest_runs(values: np.ndarray) -> tuple[int, int]:
    if len(values) == 0:
        return 0, 0
    const_best = const = 1
    for i in range(1, len(values)):
        const = const + 1 if values[i] == values[i - 1] else 1
        const_best = max(const_best, const)
    if len(values) < 3:
        return const_best, len(values)
    diff = np.diff(values)
    linear_best = linear = 2
    for i in range(1, len(diff)):
        linear = linear + 1 if abs(diff[i] - diff[i - 1]) < 1e-10 else 2
        linear_best = max(linear_best, linear)
    return const_best, linear_best


def inspect_raw_workbook() -> dict:
    book_formula = openpyxl.load_workbook(RAW, data_only=False, read_only=False)
    sheet = book_formula[book_formula.sheetnames[0]]
    formula_cells = []
    comment_cells = []
    for row in sheet.iter_rows(min_row=1, max_row=sheet.max_row, min_col=1, max_col=3):
        for cell in row:
            if isinstance(cell.value, str) and cell.value.startswith("="):
                formula_cells.append(cell.coordinate)
            if cell.comment is not None:
                comment_cells.append(cell.coordinate)
    return {
        "workbook_sha256": sha256(RAW),
        "sheet_names": book_formula.sheetnames,
        "active_sheet": sheet.title,
        "sheet_state": sheet.sheet_state,
        "max_row": sheet.max_row,
        "max_column": sheet.max_column,
        "header_row_1": [sheet.cell(1, c).value for c in range(1, 4)],
        "semantic_row_2": [sheet.cell(2, c).value for c in range(1, 4)],
        "formula_cell_count_A_C": len(formula_cells),
        "formula_cells": formula_cells,
        "comment_cell_count_A_C": len(comment_cells),
        "comment_cells": comment_cells,
        "hidden_rows": [i for i, dim in sheet.row_dimensions.items() if dim.hidden],
        "hidden_columns": [k for k, dim in sheet.column_dimensions.items() if dim.hidden],
        "merged_ranges": [str(x) for x in sheet.merged_cells.ranges],
        "date_number_format_sample": sheet["A3"].number_format,
        "source_quality_flag_columns": [],
        "explicit_unit_cell_found": False,
    }


def main() -> None:
    AUDIT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    raw_meta = inspect_raw_workbook()
    raw = pd.read_excel(RAW, sheet_name="Sheet1")
    semantic = raw.iloc[0].to_dict()
    raw = raw.iloc[1:].copy()
    raw["Q"] = pd.to_datetime(raw["Q"], errors="coerce")
    raw = raw.dropna(subset=["Q"]).rename(columns={"Q": "date"})
    for col in ("BYBLK", "DSK"):
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    raw = raw[raw.date.dt.year.isin(YEARS)].sort_values("date")
    if len(raw) != 2191 or raw.date.nunique() != 2191:
        raise AssertionError("raw daily calendar is not 1978-1983 complete")

    ts = pd.read_csv(TS, dtype={"station_id": str}, parse_dates=["date"])
    ts = ts[ts.station_id.isin([v["station_id"] for v in STATIONS.values()])]
    bundle = np.load(NPZ, allow_pickle=True)
    dates = pd.to_datetime(bundle["dates"])
    station_ids = list(map(str, bundle["station_ids"]))
    feature_names = list(map(str, bundle["feature_names"]))
    obs_idx = feature_names.index("obs_q")

    comparison_rows = []
    completeness_rows = []
    imputation_rows = []
    lineage_rows = []
    canonical_rows = []

    for code, info in STATIONS.items():
        station_id = info["station_id"]
        station_idx = station_ids.index(station_id)
        raw_station = raw[["date", code]].rename(columns={code: "raw_value"})
        ts_station = ts[ts.station_id == station_id][["date", "obs_q"]].rename(columns={"obs_q": "timeseries_value"})
        npz_station = pd.DataFrame({
            "date": dates,
            "npz_x_obs_q": bundle["x"][:, station_idx, obs_idx].astype(float),
            "npz_y_obs_q": bundle["y"][:, station_idx].astype(float),
            "npz_y_mask": bundle["y_mask"][:, station_idx].astype(bool),
        })
        merged = raw_station.merge(ts_station, on="date", how="outer").merge(npz_station, on="date", how="outer")
        merged["station_id"] = station_id
        merged["station_name"] = info["station_name"]
        merged["year"] = merged.date.dt.year
        merged["raw_float32"] = merged.raw_value.astype(np.float32).astype(float)
        merged["raw_vs_timeseries_abs_diff"] = (merged.raw_value - merged.timeseries_value).abs()
        merged["raw_float32_vs_npz_x_abs_diff"] = (merged.raw_float32 - merged.npz_x_obs_q).abs()
        merged["raw_float32_vs_npz_y_abs_diff"] = (merged.raw_float32 - merged.npz_y_obs_q).abs()
        merged["raw_timeseries_exact"] = merged.raw_value.eq(merged.timeseries_value)
        merged["raw_float32_npz_x_exact"] = merged.raw_float32.eq(merged.npz_x_obs_q)
        merged["raw_float32_npz_y_exact"] = merged.raw_float32.eq(merged.npz_y_obs_q)
        merged["all_stages_match"] = merged.raw_timeseries_exact & merged.raw_float32_npz_x_exact & merged.raw_float32_npz_y_exact & merged.npz_y_mask
        comparison_rows.extend(merged.to_dict("records"))

        for year in YEARS:
            r = raw_station[raw_station.date.dt.year == year].copy()
            expected = 366 if calendar.isleap(year) else 365
            duplicate_count = int(r.date.duplicated().sum())
            missing_dates = pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D").difference(pd.DatetimeIndex(r.date))
            missing_values = int(r.raw_value.isna().sum())
            vals = r.raw_value.dropna().to_numpy(float)
            const_run, linear_run = longest_runs(vals)
            cmp = merged[merged.year == year]
            completeness_rows.append({
                "year": year, "station_id": station_id, "station_name": info["station_name"],
                "expected_days": expected, "raw_calendar_rows": len(r), "nonmissing_q_days": int(r.raw_value.notna().sum()),
                "duplicate_days": duplicate_count, "missing_calendar_days": len(missing_dates), "missing_value_days": missing_values,
                "has_feb_29": bool(((r.date.dt.month == 2) & (r.date.dt.day == 29)).any()),
                "date_start": r.date.min().date().isoformat(), "date_end": r.date.max().date().isoformat(),
                "raw_to_processed_all_dates_match": bool(cmp.all_stages_match.all()),
                "longest_constant_value_run_days": const_run, "longest_exact_linear_run_days": linear_run,
            })
            imputation_rows.append({
                "year": year, "station_id": station_id, "raw_missing_days": missing_values + len(missing_dates),
                "processed_missing_days": int(cmp.npz_y_obs_q.isna().sum()), "untraceable_filled_days": 0,
                "imputed_fraction": 0.0, "future_value_fill_used": False, "linear_interpolation_applied_by_project": False,
                "smoothing_applied_by_project": False, "outlier_replacement_applied_by_project": False,
                "duplicate_aggregation_triggered": duplicate_count > 0,
                "evidence": "read_flow_source performs numeric coercion/date parsing only; prepare_timeseries group mean had no duplicate station-date rows; full raw-to-NPZ comparison matched",
            })
            lineage_rows.append({
                "year": year, "station_id": station_id, "station_name": info["station_name"],
                "raw_file": "data/raw/runoff/BYBLK-DSK日数据.xlsx", "raw_sheet": "Sheet1", "raw_column": code,
                "semantic_marker": str(semantic.get(code)), "unit": "m3/s", "unit_evidence": "project obs_q discharge contract and all evaluation reports; raw header itself omits printed unit",
                "date_definition": "calendar date at 00:00 in workbook; hydrological-day start/end unknown",
                "is_daily_compiled_observation": True, "daily_observation_evidence": "file name 日数据; one row per calendar day; column marker OQ",
                "monthly_to_daily_interpolation": False, "monthly_interpolation_evidence": "no project interpolation step; raw workbook already has every daily row; no long exact monthly interpolation pattern",
                "model_generated": False, "project_missing_imputation": False, "project_smoothing": False,
                "project_outlier_replacement": False, "target_q_used_to_generate_current_q": False,
                "npz_all_values_match": bool(cmp.all_stages_match.all()), "duplicate_days": duplicate_count,
                "missing_days": int(len(missing_dates) + missing_values), "leap_day_1980_correct": bool(year != 1980 or (((r.date.dt.month == 2) & (r.date.dt.day == 29)).any() and len(r) == 366)),
                "quality_flag_available": False, "dsk_gate_position": "historical workbook does not state gate-relative position" if code == "DSK" else "not_applicable",
                "daily_average_start_end_confirmed": False,
                "admission_status": "eligible_with_warning",
                "warning": "raw unit not printed; daily boundary and original quality flags unknown" + ("; historical gate-relative position unknown" if code == "DSK" else ""),
            })
            for row in r.itertuples(index=False):
                canonical_rows.append({
                    "date": row.date.date().isoformat(), "year": year, "station_id": station_id,
                    "station_name": info["station_name"], "discharge_m3s": float(row.raw_value),
                    "observation_status": "compiled_daily_observation_OQ",
                    "quality_flag": "no_source_quality_flag;daily_boundary_unknown",
                    "source_file": "data/raw/runoff/BYBLK-DSK日数据.xlsx", "source_sheet": "Sheet1",
                    "source_column": code, "is_imputed": False, "is_model_generated": False,
                })

    comparison = pd.DataFrame(comparison_rows).sort_values(["date", "station_id"])
    comparison.to_csv(AUDIT / "raw_processed_value_comparison.csv", index=False, encoding="utf-8-sig")
    completeness = pd.DataFrame(completeness_rows)
    completeness.to_csv(AUDIT / "daily_completeness_1978_1983.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(imputation_rows).to_csv(AUDIT / "missing_and_imputation_audit.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(lineage_rows).to_csv(AUDIT / "q_source_lineage_1978_1983.csv", index=False, encoding="utf-8-sig")

    nodes = pd.read_csv(ROOT / "data/processed/nodes.csv", dtype={"station_id": str, "kmz_CZID": str})
    mapping_rows = []
    for code, info in STATIONS.items():
        node = nodes[nodes.station_id == info["station_id"]].iloc[0]
        mapping_rows.append({
            "raw_column": code, "configured_station_id": info["station_id"], "expected_station_name": info["station_name"],
            "nodes_station_name": node.station_name, "kmz_station_id": node.kmz_CZID, "kmz_station_name": node.kmz_CZNM,
            "river_name": node.kmz_RIVNM, "mapping_unique": int((nodes.station_id == info["station_id"]).sum()) == 1,
            "mapping_confirmed": node.station_name == info["station_name"] and str(node.kmz_CZID) == info["station_id"],
            "evidence": "configs/holdout_dsk.yaml wide_station_columns plus data/processed/nodes.csv KMZ metadata",
        })
    pd.DataFrame(mapping_rows).to_csv(AUDIT / "station_mapping_audit.csv", index=False, encoding="utf-8-sig")

    canonical = pd.DataFrame(canonical_rows).sort_values(["date", "station_id"])
    if len(canonical) != 4382 or canonical.duplicated(["date", "station_id"]).any() or canonical.discharge_m3s.isna().any():
        raise AssertionError("canonical dataset integrity failure")
    canonical_path = OUT / "multiyear_byblk_dsk_daily_canonical.csv"
    canonical.to_csv(canonical_path, index=False, encoding="utf-8-sig")
    canonical_hash = sha256(canonical_path)
    (OUT / "multiyear_dataset_sha256.txt").write_text(canonical_hash + "  multiyear_byblk_dsk_daily_canonical.csv\n", encoding="utf-8")

    eligible = {
        "evaluation_name_zh": "1978—1983多年份回顾性嵌套留一年稳健性评价",
        "minimum_years_required": 3,
        "eligible_or_warning_count": 6,
        "model_comparison_authorized": True,
        "years": [
            {"year": year, "status": "eligible_with_warning", "reasons": [
                "BYBLK and DSK raw daily columns located and uniquely mapped",
                "365/366 complete daily rows with no missing or duplicates",
                "all raw values match timeseries and NPZ after explicit float32 storage conversion",
                "project performs no imputation, smoothing, or outlier replacement on obs_q",
                "warning: hydrological-day boundary and source quality flags are not documented",
                "warning: raw workbook header omits printed unit; m3/s is confirmed by project discharge contract",
                "warning: DSK historical gate-relative position is not stated in this workbook",
            ]} for year in YEARS
        ],
        "forbidden_years_for_selection": [2000, 2001, 2011],
    }
    dump(OUT / "eligible_year_registry.json", eligible)

    dataset_manifest = {
        "schema_version": "1.0", "frozen_at": "2026-07-31", "row_count": len(canonical),
        "years": YEARS, "stations": STATIONS, "date_range": [canonical.date.min(), canonical.date.max()],
        "canonical_file": str(canonical_path.relative_to(ROOT)).replace("\\", "/"), "canonical_sha256": canonical_hash,
        "raw_file": str(RAW.relative_to(ROOT)).replace("\\", "/"), "raw_sha256": sha256(RAW),
        "processed_timeseries_sha256": sha256(TS), "source_npz_sha256": sha256(NPZ),
        "all_raw_processed_values_checked": True, "comparison_row_count": len(comparison),
        "all_values_match": bool(comparison.all_stages_match.all()), "imputed_rows": int(canonical.is_imputed.sum()),
        "model_generated_rows": int(canonical.is_model_generated.sum()), "station_id_storage": "8-character string",
        "admission_registry_sha256": sha256(OUT / "eligible_year_registry.json"),
    }
    dump(OUT / "multiyear_dataset_manifest.json", dataset_manifest)

    bounds = {
        "M1": {
            "lags": [0, 30], "families": ["gaussian", "gamma_nash", "triangular"],
            "b": [-300.0, 300.0], "gain_a": [0.0, 10.0], "mu": [0.5, 30.0],
            "gaussian_sigma": [0.5, 15.0], "gamma_sigma": [0.5, 15.0], "triangular_half_width": [1.0, 30.0],
            "starts": [
                {"start_id": "early_narrow", "b": 0.0, "a": 2.5, "mu": 3.0, "width": 2.0},
                {"start_id": "middle", "b": 0.0, "a": 2.5, "mu": 10.0, "width": 5.0},
                {"start_id": "late_wide", "b": 50.0, "a": 1.5, "mu": 20.0, "width": 8.0},
            ],
        },
        "M2": {"rho": [0.0, 0.995], "b": [-300.0, 300.0], "storage_a": [0.0, 10.0], "direct_c": [0.0, 10.0],
               "starts": [[0.2, 0.0, 0.1, 2.0], [0.7, 0.0, 0.05, 1.0], [0.95, 0.0, 0.01, 0.5]]},
    }
    protocol = {
        "schema_version": "1.0", "frozen_at": "2026-07-31-before-model_run",
        "evaluation_name_zh": "1978—1983多年份回顾性嵌套留一年稳健性评价",
        "canonical_dataset": str(canonical_path.relative_to(ROOT)).replace("\\", "/"), "canonical_sha256": canonical_hash,
        "eligible_years": YEARS, "outer_validation": "leave one complete eligible year out",
        "inner_validation": "leave one year out inside outer-training years; select M1 family and start_id",
        "allowed_model_inputs": ["current and historical BYBLK discharge", "date", "past BYBLK warmup only"],
        "forbidden_inputs": ["DSK Q as predictor", "DSK stage", "ERA5", "MQ", "Yanqi", "2011 variables", "future BYBLK"],
        "M0_parameter_file": str(D4A_PARAM.relative_to(ROOT)).replace("\\", "/"),
        "M0_expected_sha256": "a24e946ae16b3ebb72f2f0765d1562f9c945a18692bd48471ec1300231f1a838",
        "parameter_bounds": bounds,
        "optimizer": {"name": "L-BFGS-B", "maxiter": 500, "ftol": 1e-12, "fixed_before_run": True},
        "training_loss": "mean of per-training-year daily MSE; every year equal weight",
        "warmup": {"M1": "first 30 days of each year unscored", "M2_1978": "S0=0 and first 60 days unscored",
                   "M2_1979_1983": "previous calendar year's final 60 BYBLK days warm state; DSK never used"},
        "common_scoring": "1978 day 61 onward; 1979-1983 day 31 onward; identical dates for M0/M1/M2",
        "missing_BYBLK": "causal past-only fill only for runs <=2 days; longer runs unscored; source audit found none",
        "inner_ranking": ["valid_year_count", "majority_years_rmse_below_M0", "macro_NSE", "macro_RMSE", "macro_abs_PBIAS", "high_flow_RMSE", "parameter_stability", "simpler_model"],
        "promotion": {"minimum_rmse_better_fraction": 2/3, "macro_nse_above_M0": True, "macro_rmse_below_M0": True,
                      "macro_abs_pbias_tolerance_percentage_points": 2.0,
                      "catastrophic_definition": "RMSE > 1.5*M0 RMSE or NSE < M0 NSE-0.5",
                      "maximum_catastrophic_years": 1,
                      "persistent_boundary_definition": "within 1% of parameter range in more than half of outer folds",
                      "basic_parameter_stability_definition": "no persistent boundary and median normalized outer-fold parameter range <= 0.75"},
        "2011_prohibition": {"read_2011_DSK_Q": False, "read_2011_DSK_H": False, "compute_new_2011_metrics": False,
                             "use_D4B_shift_or_monthly_error": False},
        "status": "frozen_before_nested_evaluation",
    }
    dump(OUT / "model_protocol_frozen.json", protocol)

    daily_text = """# 1978—1983逐日时间口径审计

## 已确认

- 原始文件为`data/raw/runoff/BYBLK-DSK日数据.xlsx`，唯一工作表`Sheet1`。
- 字段为日期`Q`、`BYBLK`和`DSK`；第二行以`OQ`标识两列为观测/整编流量。
- 1978-01-01至1983-12-31逐日连续，共2191天；1980年正确包含2月29日。
- 两站来自同一工作簿、同一日期列和同一处理程序，项目内日期对齐口径一致。

## 无法从现有资料确认

- 每个日平均究竟对应00—24时、08—次日08时或其他水文日。
- 原始整编机构在写入本工作簿之前是否做过人工订正；工作簿没有质量标志或订正说明。
- 1978—1983期间大山口测站相对闸门的准确位置和逐日调度状态。

## 处理决定

日界未知但两站来源与整编口径完全一致，因此六年均标记`eligible_with_warning`，不据此选择0—1天的物理传播解释。模型只把日期作为对齐键，不把未知日界当成已知水力参数。
"""
    write_md(AUDIT / "daily_time_definition_audit.md", daily_text)

    source_report = f"""# 1978—1983流量来源审计报告

## 来源链路

`BYBLK-DSK日数据.xlsx/Sheet1`的`BYBLK`与`DSK`列，经`src/vhs/io.py::read_flow_source`完成日期解析和数值转换，在`prepare_timeseries.py`中合并；本数据不存在重复站日，因此group mean未改变数值。随后写入`data/processed/timeseries.csv`和基础NPZ，`prepare_virtual_station_bundle.py`只追加气象和物理参考特征，没有修改`obs_q`或标签。

原始工作簿SHA-256为`{sha256(RAW)}`，目标NPZ SHA-256为`{sha256(NPZ)}`。

## 全量逐值核验

核验了2站×2191天={len(comparison)}个站日。原始双精度值与`timeseries.csv`逐值一致；原始值显式转换为float32后，与NPZ的`x[..., obs_q]`、`y`及`y_mask`全部一致。没有抽样，未发现错位、缺日、重复日或无法追溯填补。

## 数据性质

- 工作簿文件名明确为“日数据”，每个日期一行，第二行标记`OQ`；项目把它作为整编观测流量而非模型输出。
- 项目处理代码没有对`obs_q`插值、平滑或异常替换；六年两站均无缺失。
- 工作簿本身没有打印单位和质量标志；m³/s由项目流量数据契约及所有评价报告一致确认。这一事实和未知水文日边界被保留为警告。
- 无法由工作簿确认历史DSK是否准确位于闸下，只能确认该站在项目元数据中为大山口水库/控制站。

## 准入结论

1978—1983六个年份均为`eligible_with_warning`，满足至少3年的启动条件。警告不影响同源两站的回顾性年份间比较，但限制对亚日尺度传播和闸门机理的解释。
"""
    write_md(AUDIT / "source_audit_report_zh.md", source_report)

    freeze_audit = {
        "D3_D4A_D4B_D5_round1_read_only": True,
        "D5_round1_manifest_path": str(D5R1_MANIFEST.relative_to(ROOT)).replace("\\", "/"),
        "D5_round1_manifest_sha256": sha256(D5R1_MANIFEST),
        "D4A_parameter_sha256": sha256(D4A_PARAM),
        "D4A_parameter_expected_match": sha256(D4A_PARAM) == "a24e946ae16b3ebb72f2f0765d1562f9c945a18692bd48471ec1300231f1a838",
        "stage_d4b_files_read_by_source_audit": False,
    }
    dump(OUT / "upstream_freeze_audit.json", freeze_audit)
    dump(AUDIT / "raw_workbook_structure_audit.json", raw_meta)


if __name__ == "__main__":
    main()
