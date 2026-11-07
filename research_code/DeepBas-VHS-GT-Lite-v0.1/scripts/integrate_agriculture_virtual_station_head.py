from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vhs.agriculture import (
    AgricultureHeadPolicy,
    apply_agriculture_head,
    build_agriculture_features,
    split_conformal_radius,
)
from vhs.data import TensorBundle
from vhs.metrics import regression_metrics


INPUT = Path("data/processed/virtual_station_multisite/multisite_discharge_2005.csv")
BASE_BUNDLE = Path(
    "data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz"
)
OUTPUT = Path("outputs/virtual_station_mainline/agriculture_vhs_integration_round")
AUGMENTED_BUNDLE = Path(
    "data/processed/virtual_station_multisite/multisite_agriculture_vhs_bundle_2005.npz"
)
WARMUP_DAYS = 29
SLOW_RHO = 0.99
INTERVAL_COVERAGE = 0.90


def augment_bundle(base: TensorBundle, features: pd.DataFrame) -> TensorBundle:
    station_ids = list(map(str, base.station_ids))
    target_index = station_ids.index("TARIM_XQM")
    dates = pd.DatetimeIndex(base.dates)
    aligned = features.reindex(dates)
    additions = []
    for column in aligned.columns:
        values = np.full((len(dates), len(station_ids)), np.nan, dtype=np.float32)
        values[:, target_index] = aligned[column].to_numpy(dtype=np.float32)
        additions.append(values)
    additions.append(
        np.where(np.isfinite(additions[0]), 0.0, np.nan).astype(np.float32)
    )
    names = list(features.columns) + ["agri_correction_enabled"]
    x = np.concatenate([base.x, np.stack(additions, axis=-1)], axis=-1)
    return TensorBundle(
        dates=base.dates,
        station_ids=base.station_ids,
        feature_names=np.concatenate([base.feature_names.astype(str), np.asarray(names)]),
        x=x,
        y=base.y,
        y_mask=base.y_mask,
        static=base.static,
        edge_index=base.edge_index,
        edge_attr=base.edge_attr,
    )


def main() -> None:
    raw = pd.read_csv(INPUT, parse_dates=["date"])
    reach = raw.pivot_table(
        index="date", columns="station_code", values="observed_q_m3s", aggfunc="mean"
    )[["ALAR", "XQM", "AQK"]].dropna()
    features = build_agriculture_features(
        reach.index,
        reach.ALAR.to_numpy(float),
        reach.AQK.to_numpy(float),
        slow_rho=SLOW_RHO,
    )
    integrated = reach.join(features)
    usable = integrated.iloc[WARMUP_DAYS:].copy()
    n = len(usable)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    validation = usable.iloc[train_end:validation_end]
    test = usable.iloc[validation_end:].copy()

    policy = AgricultureHeadPolicy(
        measured_proxies_available=False,
        seasonal_specificity_supported=False,
        correction_beats_blind_baseline=False,
    )
    candidate_correction = np.zeros(len(integrated), dtype=float)
    integrated["vhs_agriculture_head_q"] = apply_agriculture_head(
        integrated.agri_endpoint_geometric_q.to_numpy(float),
        candidate_correction,
        policy,
    )
    radius = split_conformal_radius(
        np.abs(
            validation.XQM.to_numpy(float)
            - validation.agri_endpoint_geometric_q.to_numpy(float)
        ),
        INTERVAL_COVERAGE,
    )
    integrated["vhs_lower_q"] = np.maximum(
        integrated.vhs_agriculture_head_q - radius, 0.0
    )
    integrated["vhs_upper_q"] = integrated.vhs_agriculture_head_q + radius
    integrated["agri_correction_enabled"] = float(policy.correction_enabled)
    integrated["agri_measured_proxy_available"] = float(
        policy.measured_proxies_available
    )

    test_integrated = integrated.reindex(test.index)
    test_metrics = regression_metrics(
        test_integrated.XQM, test_integrated.vhs_agriculture_head_q
    )
    test_coverage = float(
        (
            (test_integrated.XQM >= test_integrated.vhs_lower_q)
            & (test_integrated.XQM <= test_integrated.vhs_upper_q)
        ).mean()
    )
    interval_radius_to_median_prediction = float(
        radius / max(float(test_integrated.vhs_agriculture_head_q.median()), 1e-6)
    )
    interval_operationally_informative = bool(
        interval_radius_to_median_prediction <= 1.0
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    integrated.reset_index().to_csv(
        OUTPUT / "agriculture_vhs_daily_output.csv", index=False, encoding="utf-8-sig"
    )
    base_bundle = TensorBundle.load(BASE_BUNDLE)
    augmented = augment_bundle(base_bundle, features)
    augmented.save(AUGMENTED_BUNDLE)

    manifest = {
        "status": "integrated_diagnostic_head_point_correction_safely_disabled",
        "virtual_station": {
            "topology": "TARIM_ALAR -> TARIM_XQM -> TARIM_AQK",
            "target": "TARIM_XQM",
            "point_predictor": "geometric mean of upstream/downstream endpoint discharge",
            "target_labels_used_to_construct_point_prediction": False,
        },
        "agriculture_head": {
            "role": "diagnostic features and uncertainty flagging",
            "slow_rho": SLOW_RHO,
            "slow_half_life_days": float(np.log(0.5) / np.log(SLOW_RHO)),
            "measured_proxies_available": policy.measured_proxies_available,
            "seasonal_specificity_supported": policy.seasonal_specificity_supported,
            "correction_beats_blind_baseline": policy.correction_beats_blind_baseline,
            "point_correction_enabled": policy.correction_enabled,
            "promotion_rule": (
                "Enable point correction only when measured diversion/irrigation/groundwater "
                "proxies exist, seasonal specificity passes placebo controls, and a sealed "
                "test beats the blind endpoint baseline."
            ),
        },
        "uncertainty": {
            "method": "validation split-conformal absolute-residual interval",
            "nominal_coverage": INTERVAL_COVERAGE,
            "calibration_period": [
                validation.index.min().date().isoformat(),
                validation.index.max().date().isoformat(),
            ],
            "radius_m3s": radius,
            "previously_opened_test_coverage": test_coverage,
            "radius_to_test_median_prediction_ratio": interval_radius_to_median_prediction,
            "operationally_informative": interval_operationally_informative,
            "operational_rule": (
                "The interval is considered informative only when its half-width does not "
                "exceed the median point prediction."
            ),
        },
        "previously_opened_test": {
            "period": [test.index.min().date().isoformat(), test.index.max().date().isoformat()],
            **test_metrics,
        },
        "gnn_integration": {
            "bundle": str(AUGMENTED_BUNDLE),
            "base_features_preserved": list(map(str, base_bundle.feature_names)),
            "added_target_features": list(features.columns)
            + ["agri_correction_enabled"],
            "features_constructed_from": ["ALAR discharge", "AQK discharge", "calendar"],
            "XQM_observation_used_in_added_features": False,
            "recommended_use": (
                "Use agriculture features as masked diagnostic covariates. Keep "
                "agri_correction_enabled=0 until all promotion gates pass."
            ),
        },
        "completion": {
            "completed_with_current_data": True,
            "causal_agriculture_identification_completed": False,
            "current_data_experiment_layers_completed": 6,
            "current_data_experiment_layers_total": 6,
            "external_blockers": [
                "measured diversion or canal withdrawal",
                "irrigated-area time series",
                "groundwater level or baseflow proxy",
                "a previously unused pre-2011 observation year for independent confirmation",
            ],
        },
    }
    (OUTPUT / "agriculture_vhs_integration_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    completion_matrix = pd.DataFrame(
        [
            ["双端点盲反演与河段诊断", "completed", "当前点预测器"],
            ["滞后与记忆消融", "completed", "仅机制诊断"],
            ["动态储水—回归状态", "completed", "预测器被拒绝"],
            ["季节快慢双通道", "completed", "预测器被拒绝"],
            ["35组季节错位反证", "completed", "季节特异性未通过"],
            ["虚拟水文站/GNN安全融合", "completed", "诊断头已接入，修正关闭"],
            ["实测引水/灌溉/地下水代理", "blocked_external_data", "尚未取得"],
            ["未使用的2011年前年份独立验证", "blocked_external_data", "尚未取得"],
        ],
        columns=["work_item", "status", "decision"],
    )
    completion_matrix.to_csv(
        OUTPUT / "agriculture_completion_matrix.csv",
        index=False,
        encoding="utf-8-sig",
    )

    mainline_summary_path = Path(
        "outputs/virtual_station_mainline/three_regime_round/three_regime_summary.json"
    )
    if mainline_summary_path.exists():
        mainline = json.loads(mainline_summary_path.read_text(encoding="utf-8"))
        agriculture = mainline.setdefault("regime_3_irrigation_return_loop", {})
        agriculture.update(
            {
                "experiment_status": "completed_safe_virtual_station_integration",
                "integrated_point_predictor": "strict blind geometric endpoints",
                "agriculture_head_role": "diagnostic_covariates_only",
                "agriculture_point_correction_enabled": False,
                "integration_manifest": str(
                    OUTPUT / "agriculture_vhs_integration_manifest.json"
                ),
                "integration_bundle": str(AUGMENTED_BUNDLE),
            }
        )
        mainline["modeling_decision"]["regime_specific_heads"]["agriculture"] = (
            "diversion-storage-return diagnostic features behind a three-gate safety switch"
        )
        mainline_summary_path.write_text(
            json.dumps(mainline, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    registry_path = Path("data/processed/virtual_station_regimes.csv")
    if registry_path.exists():
        registry = pd.read_csv(registry_path)
        mask = registry.regime.eq("irrigation_groundwater_return_loop")
        registry.loc[mask, "current_status"] = (
            "safe_vhs_integration_completed_diagnostic_head_correction_disabled"
        )
        registry.to_csv(registry_path, index=False, encoding="utf-8-sig")

    figure, axes = plt.subplots(2, 1, figsize=(11.8, 7.3), constrained_layout=True)
    axes[0].fill_between(
        test_integrated.index,
        test_integrated.vhs_lower_q,
        test_integrated.vhs_upper_q,
        color="#93c5fd",
        alpha=0.35,
        label=f"{int(INTERVAL_COVERAGE * 100)}% validation-calibrated interval",
    )
    axes[0].plot(test_integrated.index, test_integrated.XQM, color="#111827", label="XQM observed")
    axes[0].plot(
        test_integrated.index,
        test_integrated.vhs_agriculture_head_q,
        color="#2563eb",
        label="deployed VHS point estimate",
    )
    axes[0].set(ylabel="Discharge (m³/s)", title="Agriculture-aware virtual station: safe deployment output")
    axes[0].legend(frameon=False, ncol=3)
    axes[0].grid(alpha=0.2)
    axes[1].plot(
        integrated.index,
        integrated.agri_endpoint_imbalance_risk,
        color="#dc2626",
        label="endpoint-imbalance diagnostic risk",
    )
    axes[1].plot(
        integrated.index,
        integrated.agri_smooth_warm_gate,
        color="#16a34a",
        label="calendar warm-season hypothesis",
    )
    axes[1].axvspan(test.index.min(), test.index.max(), color="#f97316", alpha=0.10, label="opened test")
    axes[1].set(
        ylabel="Diagnostic scale",
        title="Agriculture mechanism is retained as a diagnostic, not a causal correction",
    )
    axes[1].legend(frameon=False, ncol=3)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "agriculture_vhs_integration_diagnostics.png", dpi=180)
    plt.close(figure)

    report = f"""# 农业循环支线与虚拟水文站安全融合报告

## 完成结论

现有数据条件下可完成的农业循环实验已经全部完成，并已接入虚拟水文站数据流。正式点预测仍采用不读取XQM标签的上下游流量几何均值；农业循环变量作为诊断特征和不确定性提示输入，不直接修改流量。

按“当前已有数据能够完成的六层实验”计算，完成度为**6/6（100%）**。若把实测农业/地下水代理和全新年份独立验证也列入完整因果证据链，则为**6/8（75%）**；缺少的两项不是程序未完成，而是外部数据尚未取得。

## 为什么没有启用农业修正

农业修正需要同时满足三道门：存在实测农业/地下水代理量、季节时序通过错位安慰剂检验、封闭测试优于盲端点基线。目前三项均未满足，所以`agri_correction_enabled=0`。这是物理安全门，不是遗漏。

## 虚拟水文站结果

- 已打开测试期：{test.index.min().date()}至{test.index.max().date()}；
- 点预测RMSE：{test_metrics['rmse']:.2f} m³/s；
- 点预测NSE：{test_metrics['nse']:.3f}；
- 90%验证期校准区间半径：{radius:.2f} m³/s；
- 测试期经验覆盖率：{test_coverage:.1%}。

该区间半径是测试期中位点预测的{interval_radius_to_median_prediction:.1f}倍，实用性判定为**{'通过' if interval_operationally_informative else '未通过'}**。100%覆盖并不代表区间优秀，而是验证期状态转移造成区间过宽；当前只能作为“风险很高”的警示。

## 接入内容

新增了端点几何流量、端点差、正损失代理、暖季门、门控损失、快回归、慢储存、慢回归、端点失衡风险和农业修正开关等特征。所有新增特征只由ALAR、AQK与日历构造，不读取XQM观测值。

## 尚不能替代的数据

若要把诊断头升级成因果农业修正头，仍须获得实测引水或渠道取水、灌溉面积、地下水位或基流代理，并使用一个此前从未用于建模或查看结果的2011年前年份独立验证；不要求使用近年数据。
"""
    (OUTPUT / "agriculture_vhs_integration_report_zh.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
