from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.prepare_natural_reach_gnn_inputs import load_ground_observations


DAILY_PATH = Path(
    "data/processed/natural_width/gnn_inputs/byblk_natural_reach_daily_features.csv"
)
GROUND_PATH = Path("data/raw/natural_width/byblk_ground_observations.csv")
REQUEST_PATH = Path(
    "outputs/virtual_station_mainline/natural_width_resolution_uncertainty_round/"
    "byblk_exact_ground_data_request_manifest.csv"
)
OUTPUT = Path(
    "outputs/virtual_station_mainline/natural_hydraulic_supervision_protocol_round"
)

EXISTING_GATE = {
    "unique_satellite_discharge_dates": 30,
    "swot_stage_dates": 10,
    "discharge_years": 2,
}
HYDRAULIC_GATE = {
    "joint_stage_discharge_dates": 20,
    "rating_curve_version_completeness": 0.80,
    "quality_code_completeness": 0.80,
}


def completeness(series: pd.Series) -> float:
    if len(series) == 0:
        return 0.0
    cleaned = series.astype("string").str.strip().replace("", pd.NA)
    return float(cleaned.notna().mean())


def chronological_split(dates: pd.Series) -> pd.DataFrame:
    unique = pd.Series(pd.to_datetime(dates).dropna().unique()).sort_values().reset_index(drop=True)
    if len(unique) == 0:
        return pd.DataFrame(columns=["date", "split", "sealed_label"])
    train_end = max(1, int(np.floor(len(unique) * 0.60)))
    validation_end = max(train_end + 1, int(np.floor(len(unique) * 0.80)))
    validation_end = min(validation_end, len(unique))
    rows = []
    for index, date in enumerate(unique):
        if index < train_end:
            split = "calibration"
        elif index < validation_end:
            split = "validation"
        else:
            split = "sealed_test"
        rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "split": split,
                "sealed_label": split == "sealed_test",
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    daily = pd.read_csv(DAILY_PATH, parse_dates=["date"])
    ground = load_ground_observations(GROUND_PATH)
    ground_columns = [
        "discharge_m3s",
        "stage_m",
        "rating_curve_version",
        "quality_code",
        "change_note",
    ]
    daily = daily.drop(columns=[column for column in ground_columns if column in daily])
    daily = daily.merge(ground, on="date", how="left", validate="one_to_one")

    any_satellite = daily[
        ["landsat_observation_mask", "sentinel_observation_mask", "swot_observation_mask"]
    ].eq(1).any(axis=1)
    q_available = daily.discharge_m3s.notna()
    h_available = daily.stage_m.notna()
    counts = {
        "ground_discharge_dates": int(q_available.sum()),
        "ground_stage_dates": int(h_available.sum()),
        "joint_stage_discharge_dates": int((q_available & h_available).sum()),
        "unique_satellite_discharge_dates": int((any_satellite & q_available).sum()),
        "landsat_discharge_dates": int(
            (daily.landsat_observation_mask.eq(1) & q_available).sum()
        ),
        "sentinel_discharge_dates": int(
            (daily.sentinel_observation_mask.eq(1) & q_available).sum()
        ),
        "swot_discharge_dates": int(
            (daily.swot_observation_mask.eq(1) & q_available).sum()
        ),
        "swot_stage_dates": int((daily.swot_observation_mask.eq(1) & h_available).sum()),
        "discharge_years": int(daily.loc[q_available, "date"].dt.year.nunique()),
    }
    labelled = daily.loc[q_available | h_available]
    coverage = {
        "rating_curve_version_completeness": completeness(
            labelled.rating_curve_version
        ),
        "quality_code_completeness": completeness(labelled.quality_code),
    }
    existing_checks = {
        key: counts[key] >= threshold for key, threshold in EXISTING_GATE.items()
    }
    hydraulic_checks = {
        "joint_stage_discharge_dates": counts["joint_stage_discharge_dates"]
        >= HYDRAULIC_GATE["joint_stage_discharge_dates"],
        "rating_curve_version_completeness": coverage[
            "rating_curve_version_completeness"
        ]
        >= HYDRAULIC_GATE["rating_curve_version_completeness"],
        "quality_code_completeness": coverage["quality_code_completeness"]
        >= HYDRAULIC_GATE["quality_code_completeness"],
    }
    supervised_ready = all(existing_checks.values())
    physics_ready = supervised_ready and all(hydraulic_checks.values())

    missing = {
        "additional_unique_satellite_discharge_dates": max(
            0,
            EXISTING_GATE["unique_satellite_discharge_dates"]
            - counts["unique_satellite_discharge_dates"],
        ),
        "additional_swot_stage_dates": max(
            0, EXISTING_GATE["swot_stage_dates"] - counts["swot_stage_dates"]
        ),
        "additional_discharge_years": max(
            0, EXISTING_GATE["discharge_years"] - counts["discharge_years"]
        ),
        "additional_joint_stage_discharge_dates": max(
            0,
            HYDRAULIC_GATE["joint_stage_discharge_dates"]
            - counts["joint_stage_discharge_dates"],
        ),
    }

    pair_dates = daily.loc[any_satellite & q_available, "date"]
    split = chronological_split(pair_dates)
    request = pd.read_csv(REQUEST_PATH, dtype={"date": str})
    ground_for_join = ground.copy()
    ground_for_join["date"] = ground_for_join.date.dt.date.astype(str)
    audit = request.merge(ground_for_join, on="date", how="left", validate="one_to_one")
    audit["discharge_received"] = audit.discharge_m3s.notna()
    audit["stage_received"] = audit.stage_m.notna()
    audit["rating_curve_version_received"] = (
        audit.rating_curve_version.astype("string").str.strip().replace("", pd.NA).notna()
    )
    audit["ready_for_width_q"] = audit.discharge_received
    audit["ready_for_swot_h"] = audit.satellite_sources.str.contains("SWOT") & audit.stage_received

    protocol = {
        "status": (
            "physics_constrained_training_ready"
            if physics_ready
            else "supervised_training_ready_hydraulic_metadata_incomplete"
            if supervised_ready
            else "blocked_waiting_for_ground_hydraulic_observations"
        ),
        "station_id": "00705600",
        "reach_id": "48220900311",
        "counts": counts,
        "metadata_completeness": coverage,
        "existing_supervised_gate": {
            "thresholds": EXISTING_GATE,
            "checks": existing_checks,
            "passed": supervised_ready,
        },
        "hydraulic_interpretation_gate": {
            "thresholds": HYDRAULIC_GATE,
            "checks": hydraulic_checks,
            "passed": physics_ready,
        },
        "remaining_minimum": missing,
        "predeclared_model_order": [
            "segmented ground rating curve H->Q by rating_curve_version",
            "satellite width/WSE->ground H monotonic baseline",
            "chained satellite geometry->H->Q baseline",
            "direct monotonic satellite geometry->Q baseline",
            "physics-safe residual GNN only after all earlier gates",
        ],
        "predeclared_split": {
            "method": "chronological 60/20/20 on unique labelled satellite dates",
            "calibration_fraction": 0.60,
            "validation_fraction": 0.20,
            "sealed_test_fraction": 0.20,
            "sealed_test_labels_must_not_enter_feature_or_model_selection": True,
        },
        "promotion_rule": (
            "A complex model must improve sealed-test NSE and RMSE over the simplest "
            "eligible baseline, preserve non-negative discharge, and avoid material PBIAS."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUTPUT / "ground_data_arrival_audit.csv", index=False)
    split.to_csv(OUTPUT / "predeclared_chronological_split.csv", index=False)
    (OUTPUT / "natural_hydraulic_supervision_protocol.json").write_text(
        json.dumps(protocol, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = f"""# 自然河道Q/H—评级曲线监督实验启动协议

## 当前正式状态

`{protocol['status']}`

当前地面Q日期 {counts['ground_discharge_dates']} 天、H日期 {counts['ground_stage_dates']} 天；卫星同日Q配对 {counts['unique_satellite_discharge_dates']} 天，SWOT同日H配对 {counts['swot_stage_dates']} 天，Q覆盖 {counts['discharge_years']} 个年份。

## 距离既定监督门槛还缺

- 卫星—Q唯一日期：还缺 {missing['additional_unique_satellite_discharge_dates']} 天；
- SWOT—H日期：还缺 {missing['additional_swot_stage_dates']} 天；
- Q覆盖年份：还缺 {missing['additional_discharge_years']} 个；
- Q/H联合日期：为解释评级曲线还缺 {missing['additional_joint_stage_discharge_dates']} 天。

## 固定实验顺序

1. 按评级曲线版本建立地面H→Q基线；
2. 建立河宽/SWOT WSE→地面H的单调基线；
3. 组合为卫星几何→H→Q链式基线；
4. 与直接几何→Q模型比较；
5. 只有通过封闭测试后，才允许训练物理安全残差GNN。

当前阻断是正确的科学门控，不会用ERA5、SWORD静态河宽、SWOT河宽或曼宁假设生成伪Q标签。
"""
    (OUTPUT / "natural_hydraulic_supervision_protocol_report_zh.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(protocol, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
