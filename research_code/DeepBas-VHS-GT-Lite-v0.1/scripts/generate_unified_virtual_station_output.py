from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vhs.router import SafetyEvidence, route_virtual_station_output


NATURAL = Path(
    "data/processed/natural_width/gnn_inputs/byblk_natural_reach_daily_features.csv"
)
RESERVOIR = Path(
    "outputs/virtual_station_mainline/reservoir_regulation_head_round/"
    "reservoir_regulation_daily_predictions.csv"
)
AGRICULTURE = Path(
    "outputs/virtual_station_mainline/agriculture_vhs_integration_round/"
    "agriculture_vhs_daily_output.csv"
)
OUTPUT = Path("outputs/virtual_station_mainline/unified_virtual_station_delivery")


UNIFIED_COLUMNS = [
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
    "uncertainty_status",
    "claim_scope",
    "source_period_status",
    "quality_flag",
]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def natural_rows() -> pd.DataFrame:
    frame = pd.read_csv(NATURAL, parse_dates=["date"])
    frame = frame.loc[frame.any_satellite_observation_mask.eq(1)].copy()
    evidence = SafetyEvidence(
        required_inputs_available=False,
        physical_reference_available=False,
        specialist_validated=False,
        specialist_authorized=False,
        scope="satellite_geometry_only_no_discharge_claim",
    )
    rows = []
    for item in frame.itertuples(index=False):
        routed = route_virtual_station_output(
            None, None, evidence, "no_rating_baseline", "natural_width_head"
        )
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
                "uncertainty_status": "withheld_no_discharge_model",
                "claim_scope": routed.claim_scope,
                "source_period_status": "recent_geometry_observation",
                "quality_flag": "geometry_available_" + "+".join(sensors),
            }
        )
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def reservoir_rows() -> pd.DataFrame:
    frame = pd.read_csv(RESERVOIR, parse_dates=["date"])
    evidence = SafetyEvidence(
        required_inputs_available=True,
        physical_reference_available=True,
        specialist_validated=True,
        specialist_authorized=True,
        scope="historically_gauged_gap_reconstruction_not_ungauged_release_recovery",
    )
    rows = []
    for item in frame.itertuples(index=False):
        routed = route_virtual_station_output(
            item.physical_q_m3s,
            item.bounded_regulation_q_m3s,
            evidence,
            "physical_area_routed_reference",
            "bounded_reservoir_regulation_head",
        )
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
                "uncertainty_status": "not_calibrated",
                "claim_scope": routed.claim_scope,
                "source_period_status": str(item.split),
                "quality_flag": "historically_gauged_model_output",
            }
        )
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def agriculture_rows() -> pd.DataFrame:
    frame = pd.read_csv(AGRICULTURE, parse_dates=["date"])
    evidence = SafetyEvidence(
        required_inputs_available=True,
        physical_reference_available=True,
        specialist_validated=False,
        specialist_authorized=False,
        scope="strict_endpoint_virtual_station_with_agriculture_diagnostics",
    )
    rows = []
    for item in frame.itertuples(index=False):
        routed = route_virtual_station_output(
            item.agri_endpoint_geometric_q,
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
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def main() -> None:
    frames = [natural_rows(), reservoir_rows(), agriculture_rows()]
    unified = pd.concat(frames, ignore_index=True)
    unified = unified.sort_values(["virtual_station_id", "date"]).reset_index(drop=True)
    if (unified.point_q_m3s.dropna() < 0).any():
        raise ValueError("unified output contains negative discharge")
    duplicated = unified.duplicated(["virtual_station_id", "date"])
    if duplicated.any():
        raise ValueError("unified output contains duplicate station-date rows")

    OUTPUT.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT / "unified_virtual_station_output.csv"
    unified.to_csv(output_path, index=False, encoding="utf-8-sig")
    status = (
        unified.groupby(
            ["virtual_station_id", "station_name", "regime"], dropna=False
        )
        .agg(
            first_date=("date", "min"),
            last_date=("date", "max"),
            rows=("date", "size"),
            discharge_output_rows=("point_q_m3s", "count"),
            correction_rows=("correction_applied", "sum"),
            primary_method=("method", lambda values: values.mode().iloc[0]),
            primary_status=("output_status", lambda values: values.mode().iloc[0]),
            claim_scope=("claim_scope", "first"),
        )
        .reset_index()
    )
    status.to_csv(
        OUTPUT / "unified_virtual_station_status.csv", index=False, encoding="utf-8-sig"
    )

    manifest = {
        "status": "final_unified_virtual_station_output_generated",
        "rows": int(len(unified)),
        "stations": int(unified.virtual_station_id.nunique()),
        "nonmissing_discharge_rows": int(unified.point_q_m3s.notna().sum()),
        "negative_discharge_rows": int(unified.point_q_m3s.dropna().lt(0).sum()),
        "duplicate_station_date_rows": int(duplicated.sum()),
        "output_sha256": file_sha256(output_path),
        "routing": {
            "natural": "withhold discharge; retain satellite geometry status until ground supervision exists",
            "reservoir": "authorized bounded head for historically gauged gap reconstruction only",
            "agriculture": "strict endpoint baseline; rejected agriculture correction and interval withheld",
        },
        "shared_weight_decision": (
            "No trainable weights are shared across regimes. The unified layer shares schema, "
            "evidence gates, nonnegative constraints, provenance, and output formatting only."
        ),
        "source_files": {
            "natural": str(NATURAL),
            "reservoir": str(RESERVOIR),
            "agriculture": str(AGRICULTURE),
        },
        "output_files": {
            "daily": str(output_path),
            "status": str(OUTPUT / "unified_virtual_station_status.csv"),
        },
    }
    (OUTPUT / "final_delivery_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    reservoir = unified.loc[
        unified.virtual_station_id.eq("00705700")
        & unified.source_period_status.eq("test")
    ]
    agriculture = unified.loc[unified.virtual_station_id.eq("TARIM_XQM")]
    natural = unified.loc[unified.virtual_station_id.eq("00705600")]
    figure, axes = plt.subplots(3, 1, figsize=(12, 9), constrained_layout=True)
    axes[0].scatter(
        natural.date,
        np.ones(len(natural)),
        s=12,
        color="#16a34a",
        label="satellite geometry available; Q withheld",
    )
    axes[0].set(yticks=[], title="Natural reach BYBLK: evidence-aware refusal")
    axes[0].legend(frameon=False)
    axes[0].grid(axis="x", alpha=0.2)
    axes[1].plot(reservoir.date, reservoir.baseline_q_m3s, color="#64748b", label="physical reference")
    axes[1].plot(reservoir.date, reservoir.point_q_m3s, color="#2563eb", label="authorized bounded head")
    axes[1].set(ylabel="Q (m³/s)", title="Reservoir DSK: 1983 sealed historical reconstruction")
    axes[1].legend(frameon=False)
    axes[1].grid(alpha=0.2)
    axes[2].plot(agriculture.date, agriculture.point_q_m3s, color="#ea580c", label="strict endpoint baseline")
    risk = agriculture.quality_flag.eq("high_endpoint_imbalance")
    axes[2].scatter(agriculture.loc[risk, "date"], agriculture.loc[risk, "point_q_m3s"], s=10, color="#dc2626", label="high imbalance diagnostic")
    axes[2].set(ylabel="Q (m³/s)", title="Agriculture XQM: baseline output with diagnostic flags")
    axes[2].legend(frameon=False)
    axes[2].grid(alpha=0.2)
    figure.savefig(OUTPUT / "unified_virtual_station_overview.png", dpi=180)
    plt.close(figure)

    natural_count = int(status.loc[status.virtual_station_id.eq("00705600"), "rows"].iloc[0])
    reservoir_count = int(status.loc[status.virtual_station_id.eq("00705700"), "discharge_output_rows"].iloc[0])
    agriculture_count = int(status.loc[status.virtual_station_id.eq("TARIM_XQM"), "discharge_output_rows"].iloc[0])
    report = f"""# 统一虚拟水文站最终输出报告

## 最终交付

已将自然河道、水库建筑物和农业循环三种情景接入同一个安全路由与输出规范，共生成{len(unified)}条站点—日期记录，其中{unified.point_q_m3s.notna().sum()}条具有流量输出。所有非空流量均非负，无重复站点—日期记录。

## 三情景输出

- 自然河道BYBLK：{natural_count}个卫星几何观测日进入统一表，但由于没有同期地面流量/水位和有效率定关系，流量被安全拒绝，不以卫星宽度直接编造Q。
- 水库DSK：{reservoir_count}条历史重建流量，采用已通过的有界调节头；适用范围仅为历史有站资料缺口重建，不解释成真实水库下泄过程。
- 农业XQM：{agriculture_count}条虚拟流量，采用不读取XQM标签的上下游端点几何基线；农业储水修正关闭，过宽的不确定性区间不输出。

## 统一但不强行共享

三种机制共享字段、目标遮蔽规范、证据安全门、非负约束、来源记录和输出格式，不共享已经被负迁移实验否定的可训练参数。证据不足时系统回退物理基线；连物理基线也不成立时，明确拒绝给出流量。

## 文件校验

统一逐日输出SHA-256：`{manifest['output_sha256']}`。
"""
    (OUTPUT / "unified_virtual_station_final_report_zh.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
