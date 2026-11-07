from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.quality import (
    QUALITY_POLICY_VERSION,
    evaluate_physical_reference,
    evaluate_specialist_output,
)
from vhs.router import SafetyEvidence, route_virtual_station_output


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "virtual_station_mainline"
NATURAL = ROOT / "data" / "processed" / "natural_width" / "gnn_inputs" / "byblk_natural_reach_daily_features.csv"
RESERVOIR = BASE / "reservoir_regulation_head_round" / "reservoir_regulation_daily_predictions.csv"
AGRICULTURE = BASE / "agriculture_vhs_integration_round" / "agriculture_vhs_daily_output.csv"
V1 = BASE / "unified_virtual_station_delivery" / "unified_virtual_station_output.csv"
OUTPUT = BASE / "unified_virtual_station_delivery_v2"
RATIO_BOUNDS = (0.3803267861502814, 4.10469250180117)


V2_COLUMNS = [
    "date",
    "virtual_station_id",
    "station_name",
    "regime",
    "point_q_m3s",
    "lower_q_m3s",
    "upper_q_m3s",
    "baseline_q_m3s",
    "specialist_q_m3s",
    "method",
    "output_status",
    "correction_applied",
    "quality_rejected",
    "quality_rejection_reason",
    "fallback_reason",
    "withhold_reason",
    "quality_policy_version",
    "uncertainty_status",
    "claim_scope",
    "source_period_status",
    "quality_flag",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def frozen_policy() -> dict:
    reservoir = pd.read_csv(RESERVOIR)
    agriculture = pd.read_csv(AGRICULTURE)
    return {
        "version": QUALITY_POLICY_VERSION,
        "envelope_multiplier": 1.01,
        "reservoir_physical_upper_m3s": float(reservoir.physical_q_m3s.max() * 1.01),
        "reservoir_specialist_upper_m3s": float(reservoir.bounded_regulation_q_m3s.max() * 1.01),
        "agriculture_baseline_upper_m3s": float(agriculture.agri_endpoint_geometric_q.max() * 1.01),
        "reservoir_specialist_to_reference_ratio_bounds": list(RATIO_BOUNDS),
        "negative_values_rejected": True,
        "nonfinite_values_rejected": True,
        "policy_scope": "accepted historical envelope; must be re-frozen under a declared new calibration package",
    }


def natural_rows() -> pd.DataFrame:
    frame = pd.read_csv(NATURAL, parse_dates=["date"])
    frame = frame.loc[frame.any_satellite_observation_mask.eq(1)].copy()
    rows = []
    evidence = SafetyEvidence(
        required_inputs_available=False,
        physical_reference_available=False,
        specialist_validated=False,
        specialist_authorized=False,
        scope="satellite_geometry_only_no_discharge_claim",
    )
    for item in frame.itertuples(index=False):
        routed = route_virtual_station_output(None, None, evidence, "no_rating_baseline", "natural_width_head")
        sensors = []
        if item.landsat_observation_mask:
            sensors.append("landsat")
        if item.sentinel_observation_mask:
            sensors.append("sentinel2")
        if item.swot_observation_mask:
            sensors.append("swot")
        rows.append(
            {
                "date": item.date,
                "virtual_station_id": "00705600",
                "station_name": "BYBLK",
                "regime": "natural_reach",
                "point_q_m3s": routed.point_q_m3s,
                "lower_q_m3s": np.nan,
                "upper_q_m3s": np.nan,
                "baseline_q_m3s": np.nan,
                "specialist_q_m3s": np.nan,
                "method": routed.method,
                "output_status": routed.output_status,
                "correction_applied": routed.correction_applied,
                "quality_rejected": False,
                "quality_rejection_reason": "not_evaluated_no_discharge_model",
                "fallback_reason": "not_applicable",
                "withhold_reason": "missing_contemporaneous_discharge_stage_supervision",
                "quality_policy_version": QUALITY_POLICY_VERSION,
                "uncertainty_status": "withheld_no_discharge_model",
                "claim_scope": routed.claim_scope,
                "source_period_status": "recent_geometry_observation",
                "quality_flag": "geometry_available_" + "+".join(sensors),
            }
        )
    return pd.DataFrame(rows, columns=V2_COLUMNS)


def reservoir_rows(policy: dict) -> pd.DataFrame:
    frame = pd.read_csv(RESERVOIR, parse_dates=["date"])
    rows = []
    for item in frame.itertuples(index=False):
        baseline_quality = evaluate_physical_reference(
            item.physical_q_m3s,
            upper_envelope_m3s=policy["reservoir_physical_upper_m3s"],
        )
        specialist_quality = evaluate_specialist_output(
            item.bounded_regulation_q_m3s,
            item.physical_q_m3s if baseline_quality.accepted else None,
            specialist_upper_envelope_m3s=policy["reservoir_specialist_upper_m3s"],
            ratio_lower=RATIO_BOUNDS[0],
            ratio_upper=RATIO_BOUNDS[1],
        )
        evidence = SafetyEvidence(
            required_inputs_available=baseline_quality.accepted,
            physical_reference_available=baseline_quality.accepted,
            specialist_validated=specialist_quality.accepted,
            specialist_authorized=specialist_quality.accepted,
            scope="historically_gauged_gap_reconstruction_not_ungauged_release_recovery",
        )
        routed = route_virtual_station_output(
            item.physical_q_m3s if baseline_quality.accepted else None,
            item.bounded_regulation_q_m3s if specialist_quality.accepted else None,
            evidence,
            "physical_area_routed_reference",
            "bounded_reservoir_regulation_head",
        )
        if not baseline_quality.accepted:
            withhold_reason = baseline_quality.reason
            fallback_reason = "not_applicable"
        elif not specialist_quality.accepted:
            withhold_reason = "not_withheld"
            fallback_reason = specialist_quality.reason
        else:
            withhold_reason = "not_withheld"
            fallback_reason = "not_applicable"
        quality_rejected = baseline_quality.rejected or specialist_quality.rejected
        rejection_reason = ";".join(
            decision.reason
            for decision in (baseline_quality, specialist_quality)
            if decision.rejected
        ) or "none"
        rows.append(
            {
                "date": item.date,
                "virtual_station_id": "00705700",
                "station_name": "DSK",
                "regime": "reservoir_or_hydraulic_structure",
                "point_q_m3s": routed.point_q_m3s,
                "lower_q_m3s": np.nan,
                "upper_q_m3s": np.nan,
                "baseline_q_m3s": item.physical_q_m3s,
                "specialist_q_m3s": item.bounded_regulation_q_m3s,
                "method": routed.method,
                "output_status": routed.output_status,
                "correction_applied": routed.correction_applied,
                "quality_rejected": quality_rejected,
                "quality_rejection_reason": rejection_reason,
                "fallback_reason": fallback_reason,
                "withhold_reason": withhold_reason,
                "quality_policy_version": QUALITY_POLICY_VERSION,
                "uncertainty_status": "not_calibrated",
                "claim_scope": routed.claim_scope,
                "source_period_status": str(item.split),
                "quality_flag": "historically_gauged_model_output",
            }
        )
    return pd.DataFrame(rows, columns=V2_COLUMNS)


def agriculture_rows(policy: dict) -> pd.DataFrame:
    frame = pd.read_csv(AGRICULTURE, parse_dates=["date"])
    rows = []
    for item in frame.itertuples(index=False):
        baseline_quality = evaluate_physical_reference(
            item.agri_endpoint_geometric_q,
            upper_envelope_m3s=policy["agriculture_baseline_upper_m3s"],
        )
        evidence = SafetyEvidence(
            required_inputs_available=baseline_quality.accepted,
            physical_reference_available=baseline_quality.accepted,
            specialist_validated=False,
            specialist_authorized=False,
            scope="strict_endpoint_virtual_station_with_agriculture_diagnostics",
        )
        routed = route_virtual_station_output(
            item.agri_endpoint_geometric_q if baseline_quality.accepted else None,
            item.vhs_agriculture_head_q,
            evidence,
            "strict_geometric_endpoint_baseline",
            "agriculture_storage_return_head",
        )
        rows.append(
            {
                "date": item.date,
                "virtual_station_id": "TARIM_XQM",
                "station_name": "XQM",
                "regime": "irrigation_groundwater_return_loop",
                "point_q_m3s": routed.point_q_m3s,
                "lower_q_m3s": np.nan,
                "upper_q_m3s": np.nan,
                "baseline_q_m3s": item.agri_endpoint_geometric_q,
                "specialist_q_m3s": item.vhs_agriculture_head_q,
                "method": routed.method,
                "output_status": routed.output_status,
                "correction_applied": routed.correction_applied,
                "quality_rejected": baseline_quality.rejected,
                "quality_rejection_reason": baseline_quality.reason if baseline_quality.rejected else "none",
                "fallback_reason": (
                    "agriculture_specialist_not_validated_or_authorized"
                    if baseline_quality.accepted
                    else "not_applicable"
                ),
                "withhold_reason": baseline_quality.reason if baseline_quality.rejected else "not_withheld",
                "quality_policy_version": QUALITY_POLICY_VERSION,
                "uncertainty_status": "withheld_interval_too_wide",
                "claim_scope": routed.claim_scope,
                "source_period_status": "historical_2005_development",
                "quality_flag": (
                    "high_endpoint_imbalance"
                    if item.agri_endpoint_imbalance_risk >= 0.75
                    else "endpoint_baseline_available"
                ),
            }
        )
    return pd.DataFrame(rows, columns=V2_COLUMNS)


def write_report(manifest: dict, status: pd.DataFrame) -> None:
    lines = [
        "# 统一虚拟水文站 V2 中文交付说明",
        "",
        f"- 质量策略：`{manifest['quality_policy']['version']}`",
        f"- 记录数：{manifest['rows']}；站点数：{manifest['stations']}",
        f"- 有效流量：{manifest['nonmissing_discharge_rows']}；负流量：{manifest['negative_discharge_rows']}",
        f"- 质量拒绝：{manifest['quality_rejected_rows']}；回退：{manifest['fallback_rows']}；暂缓：{manifest['withheld_rows']}",
        f"- 与 V1 点流量最大绝对差：{manifest['v1_comparison']['max_absolute_point_q_difference_m3s']}",
        "",
        "## 新增字段",
        "",
        "- `quality_rejected`：物理参考或专家值是否被质量门拒绝。",
        "- `quality_rejection_reason`：具体拒绝原因；正常为 `none`。",
        "- `fallback_reason`：为何回退物理基线。",
        "- `withhold_reason`：为何暂缓流量。",
        "- `quality_policy_version`：冻结阈值对应的策略版本。",
        "",
        "## 三站状态",
        "",
        "|虚拟站|情景|记录|流量输出|质量拒绝|回退|暂缓|主要状态|",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in status.itertuples(index=False):
        lines.append(
            f"|{row.station_name}|{row.regime}|{row.rows}|{row.discharge_output_rows}|{row.quality_rejected_rows}|{row.fallback_rows}|{row.withheld_rows}|{row.primary_status}|"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "V2 不改变现有干净数据上的点流量结果；它增加的是可解释质量门和故障状态。历史包络阈值已经冻结，新数据不得自动扩展阈值。若需更新，必须建立新的校准包、版本号和独立验收记录。",
        ]
    )
    (OUTPUT / "unified_virtual_station_v2_report_zh.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    policy = frozen_policy()
    frames = [natural_rows(), reservoir_rows(policy), agriculture_rows(policy)]
    unified = pd.concat(frames, ignore_index=True).sort_values(["virtual_station_id", "date"]).reset_index(drop=True)
    if unified.duplicated(["virtual_station_id", "date"]).any():
        raise ValueError("V2 output contains duplicate station-date rows")
    if unified.point_q_m3s.dropna().lt(0).any():
        raise ValueError("V2 output contains negative discharge")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / "unified_virtual_station_output_v2.csv"
    unified.to_csv(output_path, index=False, encoding="utf-8-sig")
    status = (
        unified.groupby(["virtual_station_id", "station_name", "regime"], dropna=False)
        .agg(
            first_date=("date", "min"),
            last_date=("date", "max"),
            rows=("date", "size"),
            discharge_output_rows=("point_q_m3s", "count"),
            quality_rejected_rows=("quality_rejected", "sum"),
            fallback_rows=("output_status", lambda values: int(values.eq("physical_baseline_fallback").sum())),
            withheld_rows=("output_status", lambda values: int(values.str.startswith("withheld").sum())),
            primary_method=("method", lambda values: values.mode().iloc[0]),
            primary_status=("output_status", lambda values: values.mode().iloc[0]),
            claim_scope=("claim_scope", "first"),
        )
        .reset_index()
    )
    status_path = OUTPUT / "unified_virtual_station_status_v2.csv"
    status.to_csv(status_path, index=False, encoding="utf-8-sig")

    v1 = pd.read_csv(V1, parse_dates=["date"])
    compared = v1[["date", "virtual_station_id", "point_q_m3s"]].merge(
        unified[["date", "virtual_station_id", "point_q_m3s"]],
        on=["date", "virtual_station_id"],
        how="outer",
        suffixes=("_v1", "_v2"),
        indicator=True,
    )
    paired = compared.point_q_m3s_v1.notna() & compared.point_q_m3s_v2.notna()
    max_difference = float(
        np.max(np.abs(compared.loc[paired, "point_q_m3s_v1"] - compared.loc[paired, "point_q_m3s_v2"]))
    )
    manifest = {
        "status": "final_unified_virtual_station_output_v2_generated",
        "rows": int(len(unified)),
        "stations": int(unified.virtual_station_id.nunique()),
        "nonmissing_discharge_rows": int(unified.point_q_m3s.notna().sum()),
        "negative_discharge_rows": int(unified.point_q_m3s.dropna().lt(0).sum()),
        "duplicate_station_date_rows": int(unified.duplicated(["virtual_station_id", "date"]).sum()),
        "quality_rejected_rows": int(unified.quality_rejected.sum()),
        "fallback_rows": int(unified.output_status.eq("physical_baseline_fallback").sum()),
        "withheld_rows": int(unified.output_status.str.startswith("withheld").sum()),
        "quality_policy": policy,
        "v1_comparison": {
            "merge_left_only": int(compared._merge.eq("left_only").sum()),
            "merge_right_only": int(compared._merge.eq("right_only").sum()),
            "paired_nonmissing_rows": int(paired.sum()),
            "max_absolute_point_q_difference_m3s": max_difference,
            "comparison_tolerance_m3s": 1e-12,
            "point_outputs_identical_on_clean_delivery": bool(max_difference <= 1e-12),
        },
        "output_sha256": sha256(output_path),
        "output_files": {
            "daily": str(output_path.relative_to(ROOT)),
            "status": str(status_path.relative_to(ROOT)),
            "report": str((OUTPUT / "unified_virtual_station_v2_report_zh.md").relative_to(ROOT)),
        },
    }
    if not manifest["v1_comparison"]["point_outputs_identical_on_clean_delivery"]:
        raise AssertionError("V2 unexpectedly changed clean V1 point outputs")
    manifest_path = OUTPUT / "final_delivery_manifest_v2.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(manifest, status)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
