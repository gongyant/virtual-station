from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "diagnosis_2005_snapshot"
OUT = BASE / "stage_d6"
PLOTS = OUT / "plots" / "model_evidence_overview"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def audit_manifest(path: Path, expected_count: int | None = None) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    checks = []
    for item in manifest["files"]:
        item_path = item.get("file_path", item.get("path"))
        expected_size = item.get("file_size", item.get("bytes"))
        p = ROOT / item_path
        actual_hash = sha256(p) if p.exists() else None
        actual_size = p.stat().st_size if p.exists() else None
        checks.append(
            {
                "file_path": item_path,
                "expected_sha256": item["sha256"],
                "actual_sha256": actual_hash,
                "expected_size": expected_size,
                "actual_size": actual_size,
                "hash_match": actual_hash == item["sha256"],
                "size_match": expected_size in (None, actual_size),
            }
        )
    declared = int(manifest["file_count"])
    return {
        "manifest_path": rel(path),
        "manifest_sha256": sha256(path),
        "declared_file_count": declared,
        "listed_file_count": len(manifest["files"]),
        "required_file_count": expected_count,
        "count_match": declared == len(manifest["files"])
        and (expected_count is None or declared == expected_count),
        "all_hashes_match": all(x["hash_match"] for x in checks),
        "all_sizes_match": all(x["size_match"] for x in checks),
        "checks": checks,
    }


def fnum(value: str | float | None) -> float | str:
    if value in (None, ""):
        return ""
    return float(value)


def exp_row(**kwargs) -> dict:
    fields = [
        "stage", "experiment_id", "task_protocol", "model", "input_variables",
        "target_station", "training_period", "validation_period", "test_period",
        "NSE", "RMSE", "KGE", "PBIAS", "status", "legal_interpretation",
        "rejection_reason", "data_leakage_status", "artifact_path",
    ]
    return {f: kwargs.get(f, "") for f in fields}


def build_registry() -> list[dict]:
    rows: list[dict] = []
    repro_path = BASE / "reproduced_metrics.csv"
    repro = read_csv(repro_path)
    selected = {
        "physical_reference": ("A_PHY", "MQ_reference", "DSK MQ reference", "q_dsk_mq"),
        "directed_snapshot_gnn_seed_metric_mean": ("A_GNN", "directed_snapshot_gnn", "rejected", "all node features + true directed edges"),
        "independent_no_graph_seed_metric_mean": ("A_NG", "independent_no_graph", "retained comparator", "same node features; no message passing"),
    }
    for r in repro:
        if r["model"] not in selected:
            continue
        eid, model, status, inputs = selected[r["model"]]
        rows.append(exp_row(
            stage="A", experiment_id=eid, task_protocol="2005 fixed 61-day internal test",
            model=model, input_variables=inputs, target_station="大山口 00705700",
            training_period="2005-01-03..2005-06-30", validation_period="2005-07-01..2005-08-31",
            test_period="2005-09-01..2005-10-31", NSE=fnum(r["nse"]), RMSE=fnum(r["rmse"]),
            KGE=fnum(r["kge"]), PBIAS=fnum(r["pbias"]), status=status,
            legal_interpretation="内部历史诊断；不是跨年份外部验证",
            rejection_reason="" if eid == "A_PHY" else ("真实边、反向边和随机边表现接近且均弱于自环/无图，普通消息聚合无稳定增益" if eid == "A_GNN" else "仅作结构对照，不是已晋升正式模型"),
            data_leakage_status="test labels not used for training or early stopping",
            artifact_path=rel(repro_path),
        ))

    graph_path = BASE / "graph_edge_ablation.csv"
    for r in read_csv(graph_path):
        rows.append(exp_row(
            stage="B1", experiment_id=f"B1_{r['structure']}", task_protocol="same features/epochs/seeds 7|42|123",
            model=r["structure"], input_variables="same node features; edge structure varied only",
            target_station="大山口 00705700", training_period="2005-01-03..2005-06-30",
            validation_period="2005-07-01..2005-08-31", test_period="2005-09-01..2005-10-31",
            NSE=fnum(r["nse_mean"]), RMSE=fnum(r["rmse_mean"]), KGE=fnum(r["kge_mean"]),
            PBIAS=fnum(r["pbias_mean"]), status="diagnostic_ablation",
            legal_interpretation="结构因果对照；不用于模型晋升",
            rejection_reason="真实边未优于无图/自环；方向改变没有恢复性能" if r["structure"] != "G1_self_loops" else "自环较好但不构成河网信息贡献",
            data_leakage_status="fixed test; no hyperparameter selection on test",
            artifact_path=rel(graph_path),
        ))

    lag_path = BASE / "lag_diagnosis.csv"
    lag_rows = [r for r in read_csv(lag_path) if r["split"] == "development" and r["flow_regime"] == "all"]
    for r in lag_rows:
        k = int(r["lag_days"])
        rows.append(exp_row(
            stage="B2", experiment_id=f"B2_L{k:02d}", task_protocol="development-period lag ablation",
            model=f"raw_upstream_lag_{k}", input_variables=f"Q_BYBLK(t-{k})",
            target_station="大山口 00705700", training_period="none; direct boundary diagnostic",
            validation_period="2005-05-01..2005-08-31", test_period="not evaluated",
            NSE=fnum(r["raw_upstream_nse"]), RMSE=fnum(r["raw_upstream_rmse"]), KGE="", PBIAS="",
            status="diagnostic_only", legal_interpretation="时滞相关/直接边界基线；不能与61天测试模型作同协议排名",
            rejection_reason="单一未标定上游流量不能直接代表闸下流量",
            data_leakage_status="development labels only; no 61-day test labels used for lag curve",
            artifact_path=rel(lag_path),
        ))

    legacy_path = BASE / "stage_c" / "legacy_diagnostic_comparison.csv"
    for r in read_csv(legacy_path):
        if r["model"] not in {"distributed", "kernel"}:
            continue
        is_k10 = r["model"] == "distributed"
        rows.append(exp_row(
            stage="C", experiment_id="C_K10_LEGACY" if is_k10 else "C_KERNEL_LEGACY",
            task_protocol="P1 once-only revealed 2005 legacy diagnostic",
            model=r["selected_model"], input_variables="Q_BYBLK lag0..10" if is_k10 else "Q_BYBLK lag0..10 with fixed low-dimensional kernel",
            target_station="大山口 00705700", training_period="2005-05-01..2005-08-31",
            validation_period="five expanding-window folds within 2005-05..08", test_period="2005-09-01..2005-10-31",
            NSE=fnum(r["nse"]), RMSE=fnum(r["rmse"]), KGE=fnum(r["kge"]), PBIAS=fnum(r["pbias"]),
            status="candidate_then_cross_year_not_supported" if is_k10 else "diagnostic_high_score_not_promoted",
            legal_interpretation="已揭示历史期诊断，不是外部盲测",
            rejection_reason="2011冻结跨年主窗口仅NSE=0.138" if is_k10 else "滚动验证平均NSE为负且未完成同身份冻结跨年晋升",
            data_leakage_status="legacy labels not used for selection, but period is now revealed",
            artifact_path=rel(legacy_path),
        ))

    rolling_path = BASE / "stage_c" / "rolling_validation_summary.csv"
    for r in read_csv(rolling_path):
        if r["model"] not in {"C3_distributed_nnls_K10", "C3_kernel_c0_w1"}:
            continue
        rows.append(exp_row(
            stage="C", experiment_id=f"C_ROLL_{r['model']}", task_protocol="P1 five expanding-window validation folds",
            model=r["model"], input_variables="Q_BYBLK lag0..10",
            target_station="大山口 00705700", training_period="expanding subsets of 2005-05..07",
            validation_period="five folds through 2005-08-31", test_period="not used in these summary metrics",
            NSE=fnum(r["nse_mean"]), RMSE=fnum(r["rmse_mean"]), KGE=fnum(r["kge_mean"]), PBIAS=fnum(r["pbias_mean"]),
            status="development_candidate", legal_interpretation="短fold开发稳定性证据；不能与整年LOYO直接比较",
            rejection_reason="fold NSE总体为负；仅以RMSE多数性支持候选，不足以证明迁移",
            data_leakage_status="validation-only model development; 2005 legacy test not used",
            artifact_path=rel(rolling_path),
        ))

    d4b_path = BASE / "stage_d4b" / "boundary_only_2011_external_metrics.csv"
    for r in read_csv(d4b_path):
        rows.append(exp_row(
            stage="D4B", experiment_id=f"D4B_{r['window_id']}", task_protocol="preregistered cross-year evaluation",
            model=r["model_name"], input_variables="2011 BYBLK Q lag0..10 + frozen 2005 coefficients",
            target_station="大山口 00705700", training_period="2005-05-11..2005-08-31 (113 valid rows)",
            validation_period="frozen before 2011 scoring", test_period=f"{r['start_date']}..{r['end_date']}",
            NSE=fnum(r["NSE"]), RMSE=fnum(r["RMSE"]), KGE=fnum(r["KGE"]), PBIAS=fnum(r["PBIAS"]),
            status="failed_primary_cross_year" if r["window_id"] == "primary" else "secondary_extrapolation_diagnostic",
            legal_interpretation="P1预注册跨年份评价；不是阶段C主模型外部验证，也不是完全盲测",
            rejection_reason="主窗口NSE仅0.138，冻结K10不能稳定迁移" if r["window_id"] == "primary" else "全年仅为预先冻结的次要外推诊断",
            data_leakage_status="prediction frozen and hashed before DSK label scoring",
            artifact_path=rel(d4b_path),
        ))

    d5r2_path = BASE / "stage_d5_round2" / "outer_year_metrics.csv"
    for r in read_csv(d5r2_path):
        if r["row_type"] != "macro_mean" or r["model"] not in {"M0", "M1", "M2"}:
            continue
        reasons = {
            "M0": "冻结尖峰基线跨年稳定性差",
            "M1": "1979变差、核宽持续触及15天上界且绝对PBIAS门槛失败",
            "M2": "虽6/6年RMSE优于M0，但平均绝对PBIAS恶化且储量尺度参数频繁触边",
        }
        rows.append(exp_row(
            stage="D5R2", experiment_id=f"D5R2_{r['model']}", task_protocol="1978-1983 nested leave-one-year-out",
            model=r["model"], input_variables="BYBLK Q history only",
            target_station="大山口 00705700", training_period="five outer-training years per fold",
            validation_period="inner leave-one-year-out within outer training years", test_period="one held-out year; common scoring support",
            NSE=fnum(r["nse"]), RMSE=fnum(r["rmse"]), KGE=fnum(r["kge"]), PBIAS=fnum(r["pbias"]),
            status="frozen_baseline" if r["model"] == "M0" else "rejected_not_promoted",
            legal_interpretation="多年份回顾性嵌套留一年稳健性评价；不含2011选模",
            rejection_reason=reasons[r["model"]], data_leakage_status="outer test year excluded from fit; M1 selection nested",
            artifact_path=rel(d5r2_path),
        ))

    for model, path in [
        ("M2R", BASE / "stage_d5_round4" / "m2r_nested_loyo_results.csv"),
        ("M2C", BASE / "stage_d5_round4" / "m2c_nested_loyo_results.csv"),
    ]:
        r = next(x for x in read_csv(path) if x["row_type"] == "macro_mean")
        rows.append(exp_row(
            stage="D5R4", experiment_id=f"D5R4_{model}", task_protocol="developmental nested leave-one-year-out robustness evaluation",
            model=model, input_variables="BYBLK Q storage state" if model == "M2R" else "BYBLK Q storage state + prior-14-day interval snowmelt",
            target_station="大山口 00705700", training_period="five outer-training years per fold",
            validation_period="nested development inside outer training years", test_period="one held-out year; 1978-1983",
            NSE=fnum(r["nse"]), RMSE=fnum(r["rmse"]), KGE=fnum(r["kge"]), PBIAS=fnum(r["pbias"]),
            status="reference_reparameterization" if model == "M2R" else "reject_M2C_interval_snowmelt",
            legal_interpretation="开发性稳健性评价；M2C特征曾用六年残差探索筛选，不能称独立外部验证",
            rejection_reason="与M2数值等价；未改变拒绝决定" if model == "M2R" else "1979低估未缓解且最长连续负误差由115增至156天；仅11/12门槛通过",
            data_leakage_status="no 2011 selection; M2C outer years not feature-selection blind",
            artifact_path=rel(path),
        ))
    return rows


def build_lineage() -> list[dict]:
    doc = "data/teacher_raw/Doc1.docx"
    return [
        {
            "station_id": "00705600", "station_name": "巴音布鲁克", "variable": "daily_discharge_2011",
            "source_page": "embedded_image_order_049", "table_title": "巴音布鲁克站逐日平均流量表",
            "daily_direct_measurement_status": "no",
            "generation_evidence": "4月11日至12月4日采用单一曲线法推求；其余时间采用连实测流量过程线法推求",
            "rating_curve_phase_status": "partially_confirmed_single_curve_for_stated_period",
            "temporary_curve_status": "not_stated_for_BYBLK", "special_correction_status": "unknown_requires_teacher_confirmation",
            "measurement_independence_status": "unknown_requires_teacher_confirmation",
            "circularity_risk_for_H_to_daily_Q": "high_for_curve-derived_period",
            "overall_status": "generation_method_partially_confirmed", "source_file": doc,
        },
        {
            "station_id": "00705700", "station_name": "大山口", "variable": "daily_stage_2011",
            "source_page": "embedded_image_order_010", "table_title": "大山口站逐日平均水位表",
            "daily_direct_measurement_status": "no_continuous_recorder_compilation",
            "generation_evidence": "表内水位采用自记资料整编；水位经常受闸门启闭影响而产生突变",
            "rating_curve_phase_status": "not_applicable", "temporary_curve_status": "not_applicable",
            "special_correction_status": "gate_effect_on_stage_confirmed; correction_method_not_stated",
            "measurement_independence_status": "not_applicable",
            "circularity_risk_for_H_to_daily_Q": "source-side evidence for high risk",
            "overall_status": "source_note_confirmed", "source_file": doc,
        },
        {
            "station_id": "00705700", "station_name": "大山口", "variable": "daily_discharge_2011",
            "source_page": "embedded_image_order_050", "table_title": "大山口站逐日平均流量表",
            "daily_direct_measurement_status": "no",
            "generation_evidence": "表内流量采用临时曲线法推求；主要曲线标准差为2.7%",
            "rating_curve_phase_status": "unknown_requires_teacher_confirmation",
            "temporary_curve_status": "confirmed", "special_correction_status": "unknown_requires_teacher_confirmation",
            "measurement_independence_status": "unknown_requires_teacher_confirmation",
            "circularity_risk_for_H_to_daily_Q": "high_unresolved; curve predictor not explicitly named on page",
            "overall_status": "derived_Q_confirmed_but_curve_lineage_incomplete", "source_file": doc,
        },
        {
            "station_id": "00705700", "station_name": "大山口", "variable": "discharge_measurements_2011",
            "source_page": "embedded_image_order_023_to_024", "table_title": "大山口站流量测验成果表",
            "daily_direct_measurement_status": "48_discrete_gaugings_not_daily",
            "generation_evidence": "独立表列出测次、时间、H、Q、A、V、W等；Q≈A×V通过既有复核",
            "rating_curve_phase_status": "not_stated", "temporary_curve_status": "not_stated",
            "special_correction_status": "no_gate_operation_series_in_measurement_notes",
            "measurement_independence_status": "separate_observation_table_but_use_in_daily_Q_curve_unknown",
            "circularity_risk_for_H_to_daily_Q": "can_be_independent_only_if withheld from curve construction or used as direct Q target",
            "overall_status": "separate_measurements_confirmed_statistical_independence_unknown", "source_file": doc,
        },
        {
            "station_id": "00705850", "station_name": "焉耆", "variable": "daily_discharge_2011",
            "source_page": "embedded_image_order_051", "table_title": "焉耆站逐日平均流量表",
            "daily_direct_measurement_status": "no",
            "generation_evidence": "3月25日11:30至12月16日采用临时曲线法推求；其余时间采用连实测流量过程线法推求",
            "rating_curve_phase_status": "temporary_curve_period_confirmed; detailed segmentation unknown",
            "temporary_curve_status": "confirmed", "special_correction_status": "unknown_requires_teacher_confirmation",
            "measurement_independence_status": "unknown_requires_teacher_confirmation",
            "circularity_risk_for_H_to_daily_Q": "high_for_curve-derived_period",
            "overall_status": "generation_method_partially_confirmed", "source_file": doc,
        },
    ]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    PLOTS.mkdir(parents=True, exist_ok=True)

    audits = [
        audit_manifest(BASE / "stage_d5_round4" / "stage_d5_round4_manifest.json", 29),
        audit_manifest(BASE / "stage_d5_round3" / "stage_d5_round3_manifest.json", 28),
        audit_manifest(BASE / "stage_d5_round2" / "stage_d5_round2_manifest.json", None),
    ]
    all_ok = all(a["count_match"] and a["all_hashes_match"] and a["all_sizes_match"] for a in audits)
    audit_out = {
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "stage_d5_round4_decision_expected": "reject_M2C_interval_snowmelt",
        "stage_d5_round4_decision_verified": json.loads((BASE / "stage_d5_round4" / "stage_d5_round4_manifest.json").read_text(encoding="utf-8"))["decision"],
        "write_policy": "stage_d5_round2_round3_round4_read_only",
        "all_integrity_checks_passed": all_ok,
        "audited_manifests": audits,
    }
    (OUT / "d5_round4_immutability_audit.json").write_text(json.dumps(audit_out, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all_ok:
        raise RuntimeError("D5 frozen artifact integrity check failed; Stage D6 stopped.")

    registry = build_registry()
    registry_fields = [
        "stage", "experiment_id", "task_protocol", "model", "input_variables",
        "target_station", "training_period", "validation_period", "test_period",
        "NSE", "RMSE", "KGE", "PBIAS", "status", "legal_interpretation",
        "rejection_reason", "data_leakage_status", "artifact_path",
    ]
    write_csv(OUT / "experiment_registry_A_to_D5.csv", registry, registry_fields)
    lineage = build_lineage()
    lineage_fields = list(lineage[0].keys())
    write_csv(OUT / "daily_discharge_generation_lineage_2011.csv", lineage, lineage_fields)

    gaps = [
        ("DSK闸前水位", "1978-1983及至少两个非2011年份", "daily/subdaily", "水库/水电站运行档案或水文年鉴", "control-aware P1B", "not_found", "P0", "无合法替代；日历或自动聚类不能冒充开度", "无法区分回水与闸门控制分支"),
        ("DSK闸后水位", "1978-1983及至少两个非2011年份", "daily/subdaily", "水文站自记水位整编", "stage-assisted P1B", "2011_only", "P0", "保持停止扩模", "跨年H-Q关系不可审计"),
        ("库水位", "1978-1983及验证年", "daily", "水库管理部门", "storage/control-aware model", "not_found", "P0", "无", "储量状态只能是潜变量，不能解释为真实库容"),
        ("闸门开度", "1978-1983及验证年", "event/subdaily", "水电站调度日志", "control-aware model", "not_found", "P0", "闸前后水位可作次优代理", "同水位多Q分支不可识别"),
        ("发电流量", "1978-1983及验证年", "hourly/daily", "电站运行报表", "controlled release reconstruction", "not_found", "P0", "总出库流量/机组出力曲线", "闸下Q的主要控制量缺失"),
        ("调度日志", "1978-1983及验证年", "event", "水库/电站档案", "control regime labels", "not_found", "P0", "不得用无监督聚类命名真实状态", "控制状态无法监督"),
        ("中间支流Q", "1978-1983及验证年", "daily", "开都河区间水文站/年鉴", "interval inflow model", "not_found", "P0", "仅可保留未识别残差", "年度增益与区间来水混淆"),
        ("区间水文站Q", "1978-1983及验证年", "daily", "流域管理机构", "interval inflow model", "not_found", "P0", "焉耆仅适合明确的历史事后重建", "单一上游边界欠定"),
        ("引水/退水", "1978-1983及验证年", "daily/旬/monthly", "灌区与水资源公报", "water-balance correction", "not_found", "P1", "月尺度用水量仅作不确定性范围", "水量偏差可能被误归因于气象"),
        ("地下水补给代理", "1978-1983及验证年", "daily/monthly", "地下水位或基流分割资料", "interval storage interpretation", "not_found", "P1", "不把潜在储量命名为地下水", "储量参数缺少物理对应"),
        ("非2011 DSK日水位", "至少两个完整非2011年份", "daily", "水文年鉴/原始自记整编", "stage-assisted P1B", "not_found", "P0", "保持2011为已揭示诊断年", "无法跨年验证水位辅助"),
        ("非2011 BYBLK日水位", "与DSK同期至少两个年份", "daily", "水文年鉴", "upstream stage boundary", "not_found", "P1", "仅用Q边界", "洪水传播状态信息缺失"),
        ("对应测流记录", "与多年份水位同期", "event", "流量测验成果表", "rating-curve lineage/independent Q validation", "2011_only", "P0", "需老师确认其是否参与日Q曲线", "H-Q标签循环不可排除"),
        ("未参与任何开发的新完整年份", "一完整水文年", "daily", "水文年鉴或管理部门", "final external validation", "not_found", "P0", "若无则只写回顾性研究，不宣称外部泛化", "无法提供真正未揭示验证"),
    ]
    gap_fields = ["data_name", "required_years", "required_frequency", "preferred_source", "task_enabled", "current_status", "priority", "fallback", "risk_if_missing"]
    write_csv(OUT / "critical_data_gap_registry.csv", [dict(zip(gap_fields, x)) for x in gaps], gap_fields)

    integrated = """# 阶段A—D5综合证据报告

## 结论先行

现有证据不支持继续扩展单一上游流量模型。普通有向GNN在同一61天内部期的NSE为0.311，低于无图0.367和自环0.396；K10在2005已揭示历史期达到0.853，却在预注册2011主窗口降至0.138；多年份留一年中，单储量M2把宏平均NSE从M0的0.099提高到0.388，但未通过绝对PBIAS与参数触边门槛；M2C提高到0.439，仍因1979持续低估恶化被拒绝。

核心科研结论是：**单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。**

## 证据链

1. 阶段A/B隔离了图结构影响。真实边、反向边和随机边都接近0.31 NSE，而自环与无图更高，说明负贡献来自邻居消息混合，而不是河网方向提供了可迁移信息。
2. 阶段C证明2005内部期可被边界时滞模型很好拟合，但五个短滚动fold的平均NSE仍为负。高内部成绩不能替代跨年验证。
3. D4B严格先冻结参数与预测哈希、后解封2011 DSK标签。主窗口结果显著回落，揭示自由K10的年份迁移失败。
4. D5发现K10实际只在lag0和lag5保留权重；条件数73.98、最大VIF 231.04、有效秩2.36/11，尖峰位置不稳定。
5. M2用单一储量状态表示数周记忆，6/6留出年RMSE优于M0；但年度水量偏差方向相反，说明固定增益仍不能识别区间来水与控制状态。
6. M2C只加入过去14日区间融雪。宏平均改善不等于稳健晋升：1979 PBIAS由-30.43%变为-31.35%，连续负误差由115天增至156天，因此按预注册门槛拒绝。

## 指标口径警告

登记表保留所有关键失败和对照。2005内部61天、2011预注册跨年窗口、1978—1983嵌套留一年不是同一协议，图中的条形只用于展示证据演变，不能当作单一排行榜。M2C的融雪变量经过六年残差探索筛选，其外层年份不是特征选择意义上的完全独立检验。
"""
    write_text(OUT / "integrated_evidence_report_zh.md", integrated)

    conclusions = """# 科研结论冻结稿

冻结决定：`reject_M2C_interval_snowmelt`。以下结论在获得新信息前不再通过调参改写。

1. **普通GNN为何失败。** 当前边没有距离、坡度、传播时间或控制状态；三条边的单位属性标准化后均为0。同日邻居信息被共享消息层混入目标表示，真实边NSE 0.311，反向边0.306、随机边0.309，而无图0.367、自环0.396。图的存在带来混合，真实方向没有带来可识别的水文传播。
2. **自由K10为何退化为尖峰。** 11个相邻日上游流量高度共线，冻结解只有lag0与lag5非零。条件数73.98、最大VIF 231.04、有效秩仅2.36/11；许多尖峰组合可表达相近的平滑过程，所以尖峰位置不能解释为稳定传播时间。
3. **单储量为何优于尖峰lag。** M2用一个递推状态积累上游来水，rho约0.968—0.976，对应数周记忆；它降低自由度并强制连续记忆，因此6/6留出年RMSE均优于M0，宏平均NSE由0.099升至0.388。
4. **M2为何仍未晋升。** 宏平均绝对PBIAS为13.19%，比M0的9.49%更差并越过预注册容差；储量尺度参数在5/6 fold触边。它改善过程形状，却没有稳定识别跨年水量增益。
5. **M2C为何平均改善仍被拒绝。** 它将宏平均NSE提高到0.439、RMSE降至55.15 m³/s，但只在4/6年降低RMSE、3/6年降低绝对PBIAS。1979低估加深且最长连续负误差由115天增至156天，12项门槛只通过11项。
6. **1979与1982说明什么。** 1979是跨月持续缺水量并伴随洪峰贡献，不是删除一个洪峰即可解决；1982则是若干月份和低流量基线抬高。两年偏差方向相反，暴露固定年度增益无法同时代表区间来水与闸门控制。
7. **为何不能再试另外7个气象变量。** 融雪变量已通过全六年残差探索筛选；失败后继续逐个试变量会把留出年份反馈进特征选择，形成多重尝试和事后择优，违反冻结门槛。
8. **瓶颈为何是信息缺失。** 上游Q无法区分沿程支流、引退水、地下水补给与闸门/水库状态。增加网络容量只能更灵活地拟合这些混合残差，不能让缺失的控制量变得可识别。

**核心结论：单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。**
"""
    write_text(OUT / "scientific_conclusions_frozen_zh.md", conclusions)

    circularity = """# 2011水位—流量标签循环审计

## 审计结论

大山口2011逐日Q并非每天直接测量。原表附注明确写明“表内流量采用临时曲线法推求，主要曲线标准差为2.7%”。大山口逐日H则由自记资料整编，且原表明确说明水位经常受闸门启闭影响产生突变。由此可确认逐日Q是曲线推求量，但现有页没有明确写出临时曲线的自变量、分期边界、曲线版本和特殊修正规则。因此“主要由H通过评级曲线生成”只能标记为`unknown_requires_teacher_confirmation`，不能仅凭常规水文做法直接认定。

## 九个问题的正式回答

1. **逐日Q是否每天直接测量？** 否。原表称其由临时曲线法推求；48条测流是离散测次，不是365天每日测流。
2. **是否主要由逐日H通过评级曲线推算？** `unknown_requires_teacher_confirmation`。临时曲线推求已确认，但原附注未把曲线明确写成H-Q曲线。
3. **是否使用分期评级曲线？** `unknown_requires_teacher_confirmation`。大山口页未给分期日期或曲线编号。
4. **是否有临时曲线？** 是，原表直接确认；主要曲线标准差记为2.7%。
5. **是否有冰期、回水或闸门修正？** `unknown_requires_teacher_confirmation`。只确认H受闸门启闭影响；未找到Q的冰期、回水或闸门修正说明。
6. **48条DSK测流是否独立于逐日Q？** 文件层面是独立的测流成果表；统计意义上的独立性未知，因为没有说明这些测次是否用于建立/校核临时曲线。
7. **日流量与测流Q是什么关系？** 测流Q来自离散测次并有A、V等要素，Q≈A×V已通过复核；日Q来自临时曲线推求。测流Q是否作为曲线控制点仍待确认。
8. **用H预测逐日Q是否有标签构造循环？** 有高风险且当前不能排除。若日Q本来由H-Q临时曲线推得，再用同一H拟合日Q，主要是在复现整编曲线而不是独立预测真实流量。
9. **何种H-Q任务仍合法？** 可以做历史整编关系复现、质量控制、在曲线版本已知条件下补表；也可把独立留出的直接测流Q作为目标评价H-Q关系。未经来源审计，不得把“用H重建曲线推求日Q”包装成独立虚拟站验证。

## 旁证

巴音布鲁克表明确给出4月11日至12月4日采用单一曲线法，其余时间采用连实测流量过程线法；焉耆表明确给出3月25日11:30至12月16日采用临时曲线法，其余时间采用连实测流量过程线法。这说明Doc1会在附注中记录生成方法，也进一步支持向老师索取大山口临时曲线分期和整编说明。
"""
    write_text(OUT / "stage_discharge_circularity_audit_zh.md", circularity)

    questions = """# 请老师确认：2011大山口逐日流量的生成来源

1. “临时曲线法推求”具体是否指水位—流量（H-Q）曲线？曲线自变量、公式和编号是什么？
2. 2011年用了几条临时曲线，各自适用的起止日期是什么？是否存在转折、临时换线或分期评级？
3. 48次流量测验是否用于建立或校核这些临时曲线？若是，请提供测次与曲线的对应关系。
4. 冰期、回水、冲淤或闸门启闭期间，逐日Q是否另行修正？修正方法与日期能否提供？
5. 大山口水位是闸前还是闸后水位？测流断面与闸门的相对位置是什么？
6. “主要曲线标准差2.7%”对应哪条曲线、哪些日期和多少个测次？
7. 逐日流量的日界和平均口径是什么：00—24时、08—次日08时，还是自记过程积分？
8. 能否提供2011整编说明、评级曲线表/图及临时曲线变更记录？
9. 是否有至少两个非2011年份的DSK逐日水位及同期测流成果，可用于避免只在2011上验证？
"""
    write_text(OUT / "questions_for_teacher_stage_discharge_zh.md", questions)

    decision = {
        "decision": "stop_model_expansion_and_write",
        "decision_code": "E",
        "decision_time_utc": datetime.now(timezone.utc).isoformat(),
        "authorized_new_model_training": False,
        "evidence": {
            "reliable_DSK_daily_stage_for_at_least_two_non_2011_years": False,
            "daily_Q_H_generation_relation_fully_audited": False,
            "acceptable_stage_label_circularity": False,
            "reservoir_forebay_tailwater_or_gate_state_available": False,
            "reliable_intermediate_station_or_tributary_Q_available": False,
            "multiyear_Yanqi_or_other_downstream_Q_available_for_historical_reconstruction": False,
            "new_complete_untouched_validation_year_available": False,
        },
        "why_A_to_D_not_selected": {
            "A_proceed_P1B_stage_assisted": "only 2011 DSK daily stage is available; Q-H lineage remains incomplete",
            "B_proceed_control_aware_model": "no reservoir level, forebay/tailwater level series, gate opening, generation flow, or dispatch log found",
            "C_proceed_interval_inflow_model": "no reliable intermediate station or tributary Q series found",
            "D_proceed_bidirectional_historical_reconstruction": "no multiyear Yanqi/downstream Q aligned with 1978-1983 development years found",
        },
        "frozen_scientific_statement": "单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。",
        "next_action": "write research results and request the listed new data; reopen modeling only when a preregistered information gate is met",
    }
    (OUT / "research_go_no_go_decision.json").write_text(json.dumps(decision, ensure_ascii=False, indent=2), encoding="utf-8")

    teacher = """# 给老师的一页决策简报

## 已经做了什么

我们先复现了原2005年61天结果，再用无图、自环、真边、反向边和随机边定位GNN负贡献；随后建立显式上游边界与时滞模型，并把冻结系数一次性用于2011跨年评价；最后用1978—1983六个年份做嵌套留一年检验，比较尖峰时滞、平滑核、单储量和单一融雪修正。

## 最可靠的结果

最可靠的不是某个最高NSE，而是三条一致证据：普通GNN真边不如无图/自环；2005内部很高的K10在2011主窗口降到NSE 0.138；单储量模型在六个留出年都降低RMSE，但仍无法稳定控制年度水量偏差。融雪修正平均变好，却使1979长期低估更严重，因此按预先规则拒绝。

## 为什么NSE没有继续提高

大山口是受闸门影响的控制站。仅靠上游巴音布鲁克流量，模型看不到沿程支流、引退水、地下水补给、库水位、闸前后水位和闸门状态。同一上游来水在不同年份可以对应不同下泄过程，模型因此缺少决定目标流量的关键信息。

## 为什么继续调模型解决不了

更复杂的网络只能更灵活地记住已见年份，不能从不存在的输入中恢复闸门状态或区间来水。继续试更多气象变量还会造成事后择优，使跨年检验失去独立性。

## 现在最需要的资料

优先级最高的是：非2011年份的大山口逐日水位及同期测流；闸前/闸后水位、库水位、闸门开度、发电流量或调度日志；巴音布鲁克—大山口之间支流站、引水和退水资料；以及一个从未参与开发的新完整年份。同时请确认2011逐日Q的临时曲线、分期和修正规则。

## 有资料后分别能做什么

有多年份可靠水位且排除标签循环，可做P1B水位辅助；有闸门/库水位，可做控制状态模型；有区间支流Q，可做区间来水模型；有多年份焉耆Q，只能在任务明确为历史事后重建时做双边界；有新完整年份，才能做真正独立的最终验证。

## 如果没有更多资料

停止扩模并完成论文：报告GNN失败、时滞共线性、储量模型的有限改善和信息缺失瓶颈，不把被拒绝模型包装成成功模型。当前冻结结论是：单一上游流量不足以跨年份稳定重建闸下日流量。
"""
    write_text(OUT / "teacher_decision_brief_zh.md", teacher)

    results_outline = """# 论文结果部分提纲

1. **数据、任务与协议分层**：定义P1（有上游Q）、P1B（有目标站本地状态但无目标Q）、P2（目标站无本地观测）；分开2005内部诊断、2011预注册跨年评价和1978—1983嵌套留一年。
2. **普通图消息传递失败**：报告无图、自环、真边、反向边、随机边；说明边特征缺少距离、坡度、时滞与控制状态。
3. **时滞相关与自由K10尖峰退化**：展示lag相关、条件数/VIF/有效秩、lag0+lag5冻结权重和重采样不稳定性。
4. **2011冻结迁移揭示**：先预测哈希后评分；报告主窗口NSE 0.138和全年诊断0.455，强调协议身份。
5. **平滑核与单储量跨年比较**：M1宏NSE 0.249，M2 0.388；M2在6/6年降低RMSE，但偏差门槛失败。
6. **年度水量偏差不可识别**：1979持续低估、1982低流量/月份高估，说明固定增益跨年失配。
7. **单一融雪变量的有限改善与拒绝**：M2C宏NSE 0.439、RMSE 55.15；报告4/6 RMSE改善、1979恶化和11/12门槛。
8. **信息门槛与研究收束**：控制状态、区间来水、多年份水位和全新验证年均缺失，选择stop_model_expansion_and_write。
"""
    discussion_outline = """# 论文讨论部分提纲

1. 河网拓扑不等于可用水文因果：同日共享消息在受控河段可能只是特征污染。
2. 高自相关会让自由时滞权重看似可解释，实际存在严重共线性与非唯一性。
3. 单储量状态的价值在于低维连续记忆，而不是证明真实水库储量已被识别。
4. 1979与1982的相反偏差说明，区间来水和控制状态不能由单一固定增益替代。
5. 融雪变量的负系数只代表开发期条件关联，不能解释为已确认物理因果。
6. P1、P1B与P2必须分开：加入目标站H会改变任务身份，若Q由H曲线生成还可能产生标签循环。
7. 评价设计的启示：短期高NSE、一次性跨年和嵌套多年份稳健性回答不同问题，不能混作排行榜。
8. 实务意义：下一单位成本最高收益来自控制/区间观测，而非扩大模型容量。
"""
    limitations = """# 论文局限性

- 2005原内部测试仅61天，洪峰数量和季节覆盖有限；其结果只用于诊断。
- 2011虽按冻结协议一次评分，但资料已经人工转录，且不是完全盲测。
- 2011逐日Q明确由临时曲线推求，但临时曲线自变量、分期、测流控制点和特殊修正规则尚未完全审计。
- 1978—1983原表未打印单位、质量标志和水文日口径；来源一致性已核对，但元数据仍不完整。
- M2C融雪变量经六年残差探索筛选，外层年份不是特征选择意义上的完全独立验证。
- 没有非2011多年份DSK日水位、闸门/库水位、区间支流Q及引退水资料。
- M2潜在储量不能命名为真实库容、地下水或闸门状态；负融雪系数也不能作因果解释。
- 尚无一个从未参与任何开发或查看结果的新完整年份，因此不能声称最终外部泛化能力。
- 本研究结论适用于当前BYBLK—DSK闸下控制任务，不应直接推广到自然河道或其他流域。
"""
    write_text(OUT / "paper_results_outline_zh.md", results_outline)
    write_text(OUT / "paper_discussion_outline_zh.md", discussion_outline)
    write_text(OUT / "paper_limitations_zh.md", limitations)

    generated = [p for p in OUT.rglob("*") if p.is_file() and p.name != "stage_d6_manifest.json"]
    manifest = {
        "stage": "D6",
        "decision": "stop_model_expansion_and_write",
        "new_model_trained": False,
        "new_NSE_generated": False,
        "migration_predictions_generated": False,
        "M2C_retrained": False,
        "other_weather_variables_tested": False,
        "file_count": len(generated),
        "files": [{"file_path": rel(p), "file_size": p.stat().st_size, "sha256": sha256(p)} for p in sorted(generated)],
    }
    (OUT / "stage_d6_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
