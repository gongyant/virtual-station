from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import lsq_linear

from vhs.metrics import regression_metrics


INPUT = Path("data/processed/virtual_station_multisite/multisite_discharge_2005.csv")
OUTPUT = Path(
    "outputs/virtual_station_mainline/irrigation_seasonal_dual_path_round"
)
WARMUP_DAYS = 29
FAST_RHOS = [0.0, 0.5, 0.8, 0.9]
SLOW_RHOS = [0.95, 0.97, 0.99]
SINGLE_RHOS = [0.0, 0.5, 0.8, 0.9, 0.95, 0.97, 0.99]
FAMILIES = [
    "single_all_year",
    "single_fixed_may_sep",
    "dual_all_year",
    "dual_fixed_may_sep",
    "dual_smooth_warm",
]


def seasonal_gate(index: pd.DatetimeIndex, kind: str) -> np.ndarray:
    if kind == "all_year":
        return np.ones(len(index), dtype=float)
    if kind == "fixed_may_sep":
        return np.asarray(index.month.isin([5, 6, 7, 8, 9]), dtype=float)
    if kind == "smooth_warm":
        # Calendar-only half-wave: positive from roughly April through September.
        phase = 2.0 * np.pi * (index.dayofyear.to_numpy(float) - 91.0) / 365.25
        return np.maximum(np.sin(phase), 0.0)
    raise ValueError(f"Unknown gate kind: {kind}")


def gated_storage(
    loss_proxy: np.ndarray, gate: np.ndarray, rho: float
) -> tuple[np.ndarray, np.ndarray]:
    if not 0.0 <= rho < 1.0:
        raise ValueError("rho must be in [0, 1)")
    loss = np.maximum(np.asarray(loss_proxy, dtype=float), 0.0)
    gate = np.clip(np.asarray(gate, dtype=float), 0.0, 1.0)
    if len(loss) != len(gate):
        raise ValueError("loss_proxy and gate must have equal length")
    storage = np.zeros(len(loss), dtype=float)
    release = np.zeros(len(loss), dtype=float)
    state = 0.0
    for index, value in enumerate(loss * gate):
        state = rho * state + value
        storage[index] = state
        release[index] = (1.0 - rho) * state if rho > 0 else value
    return storage, release


def prepare_reach() -> pd.DataFrame:
    raw = pd.read_csv(INPUT, parse_dates=["date"])
    reach = raw.pivot_table(
        index="date", columns="station_code", values="observed_q_m3s", aggfunc="mean"
    )[["ALAR", "XQM", "AQK"]].dropna()
    reach = reach.iloc[WARMUP_DAYS:].copy()
    reach["geometric_endpoint_q"] = np.sqrt(
        np.maximum(reach.ALAR, 0.0) * np.maximum(reach.AQK, 0.0)
    )
    reach["endpoint_gap_q"] = reach.ALAR - reach.AQK
    reach["positive_loss_proxy_q"] = np.maximum(reach.endpoint_gap_q, 0.0)
    return reach


def family_configuration(family: str) -> tuple[str, bool]:
    if family == "single_all_year":
        return "all_year", False
    if family == "single_fixed_may_sep":
        return "fixed_may_sep", False
    if family == "dual_all_year":
        return "all_year", True
    if family == "dual_fixed_may_sep":
        return "fixed_may_sep", True
    if family == "dual_smooth_warm":
        return "smooth_warm", True
    raise ValueError(f"Unknown family: {family}")


def build_candidate(
    reach: pd.DataFrame, gate_kind: str, fast_rho: float, slow_rho: float | None
) -> tuple[pd.DataFrame, list[str], np.ndarray, np.ndarray]:
    candidate = reach.copy()
    gate = seasonal_gate(candidate.index, gate_kind)
    candidate["seasonal_gate"] = gate
    candidate["gated_loss_proxy_q"] = candidate.positive_loss_proxy_q * gate
    fast_storage, fast_release = gated_storage(
        candidate.positive_loss_proxy_q.to_numpy(float), gate, fast_rho
    )
    candidate["fast_storage_proxy_q_days"] = fast_storage
    candidate["fast_return_proxy_q"] = fast_release
    features = ["geometric_endpoint_q", "endpoint_gap_q"]
    lower = [0.0, -2.0]
    upper = [3.0, 2.0]
    if gate_kind != "all_year":
        features.append("gated_loss_proxy_q")
        lower.append(-2.0)
        upper.append(0.0)
    features.append("fast_return_proxy_q")
    lower.append(0.0)
    upper.append(2.0)
    if slow_rho is not None:
        slow_storage, slow_release = gated_storage(
            candidate.positive_loss_proxy_q.to_numpy(float), gate, slow_rho
        )
        candidate["slow_storage_proxy_q_days"] = slow_storage
        candidate["slow_return_proxy_q"] = slow_release
        features.append("slow_return_proxy_q")
        lower.append(0.0)
        upper.append(2.0)
    features.append("intercept")
    candidate["intercept"] = 1.0
    lower.append(-200.0)
    upper.append(200.0)
    return candidate, features, np.asarray(lower), np.asarray(upper)


def fit_candidate(
    frame: pd.DataFrame, features: list[str], lower: np.ndarray, upper: np.ndarray
) -> np.ndarray:
    result = lsq_linear(
        frame[features].to_numpy(float),
        frame.XQM.to_numpy(float),
        bounds=(lower, upper),
    )
    return result.x


def predict_candidate(
    frame: pd.DataFrame, features: list[str], coefficients: np.ndarray
) -> np.ndarray:
    return np.maximum(frame[features].to_numpy(float) @ coefficients, 0.0)


def regime_metrics(observed: np.ndarray, predicted: np.ndarray) -> dict:
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    threshold_low = float(np.quantile(observed, 0.25))
    threshold_high = float(np.quantile(observed, 0.75))
    low = observed <= threshold_low
    high = observed >= threshold_high
    return {
        "low_flow_rmse_m3s": float(np.sqrt(np.mean((predicted[low] - observed[low]) ** 2))),
        "high_flow_rmse_m3s": float(np.sqrt(np.mean((predicted[high] - observed[high]) ** 2))),
        "peak_bias_percent": float(
            100.0 * (predicted.max() - observed.max()) / observed.max()
        ),
    }


def main() -> None:
    reach = prepare_reach()
    n = len(reach)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    train = reach.iloc[:train_end]
    validation = reach.iloc[train_end:validation_end]
    test = reach.iloc[validation_end:].copy()

    validation_rows = []
    family_winners = {}
    for family in FAMILIES:
        gate_kind, dual = family_configuration(family)
        configurations = (
            [(fast, slow) for fast in FAST_RHOS for slow in SLOW_RHOS if fast < slow]
            if dual
            else [(rho, None) for rho in SINGLE_RHOS]
        )
        best = None
        for fast_rho, slow_rho in configurations:
            candidate, features, lower, upper = build_candidate(
                reach, gate_kind, fast_rho, slow_rho
            )
            coefficients = fit_candidate(
                candidate.iloc[:train_end], features, lower, upper
            )
            prediction = predict_candidate(
                candidate.iloc[train_end:validation_end], features, coefficients
            )
            score = regression_metrics(validation.XQM, prediction)
            row = {
                "family": family,
                "gate_kind": gate_kind,
                "fast_rho": fast_rho,
                "slow_rho": slow_rho,
                **score,
            }
            validation_rows.append(row)
            if best is None or (score["rmse"], fast_rho, slow_rho or -1) < (
                best["validation_rmse"],
                best["fast_rho"],
                best["slow_rho"] or -1,
            ):
                best = {
                    "family": family,
                    "gate_kind": gate_kind,
                    "fast_rho": fast_rho,
                    "slow_rho": slow_rho,
                    "validation_rmse": score["rmse"],
                    "validation_nse": score["nse"],
                    "features": features,
                    "coefficients": coefficients,
                    "candidate": candidate,
                }
        family_winners[family] = best

    selected = min(
        family_winners.values(), key=lambda value: (value["validation_rmse"], value["family"])
    )
    test_predictions = test[["ALAR", "XQM", "AQK", "geometric_endpoint_q", "endpoint_gap_q"]].copy()
    metric_rows = []
    coefficient_rows = []
    for family, winner in family_winners.items():
        candidate = winner["candidate"]
        prediction = predict_candidate(
            candidate.iloc[validation_end:], winner["features"], winner["coefficients"]
        )
        test_predictions[family] = prediction
        score = regression_metrics(test.XQM, prediction)
        metric_rows.append(
            {
                "method": family,
                "selected_by_validation": family == selected["family"],
                "validation_rmse": winner["validation_rmse"],
                "validation_nse": winner["validation_nse"],
                **score,
                **regime_metrics(test.XQM.to_numpy(float), prediction),
            }
        )
        coefficient_rows.extend(
            {
                "family": family,
                "feature": feature,
                "coefficient": float(coefficient),
                "fast_rho": winner["fast_rho"],
                "slow_rho": winner["slow_rho"],
                "gate_kind": winner["gate_kind"],
            }
            for feature, coefficient in zip(winner["features"], winner["coefficients"])
        )

    blind = test.geometric_endpoint_q.to_numpy(float)
    test_predictions["strict_blind_geometric_endpoints"] = blind
    blind_score = regression_metrics(test.XQM, blind)
    metric_rows.append(
        {
            "method": "strict_blind_geometric_endpoints",
            "selected_by_validation": False,
            "validation_rmse": np.nan,
            "validation_nse": np.nan,
            **blind_score,
            **regime_metrics(test.XQM.to_numpy(float), blind),
        }
    )
    metrics = pd.DataFrame(metric_rows).sort_values("nse", ascending=False)
    selected_score = metrics.loc[metrics.method.eq(selected["family"])].iloc[0]
    blind_row = metrics.loc[
        metrics.method.eq("strict_blind_geometric_endpoints")
    ].iloc[0]
    accepted = bool(
        selected_score.nse > 0
        and selected_score.nse > blind_row.nse
        and selected_score.rmse < blind_row.rmse
    )

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(validation_rows).to_csv(
        OUTPUT / "seasonal_dual_path_validation_candidates.csv", index=False
    )
    metrics.to_csv(OUTPUT / "seasonal_dual_path_test_metrics.csv", index=False)
    pd.DataFrame(coefficient_rows).to_csv(
        OUTPUT / "seasonal_dual_path_coefficients.csv", index=False
    )
    test_predictions.reset_index().to_csv(
        OUTPUT / "seasonal_dual_path_test_predictions.csv", index=False
    )

    selected_candidate = selected["candidate"]
    figure, axes = plt.subplots(2, 1, figsize=(12.0, 7.4), constrained_layout=True)
    axes[0].plot(test.index, test.XQM, color="#111827", lw=1.8, label="XQM observed")
    axes[0].plot(test.index, blind, color="#2563eb", lw=1.4, label="blind endpoints")
    axes[0].plot(
        test.index,
        test_predictions[selected["family"]],
        color="#ea580c",
        lw=1.5,
        label=f"selected: {selected['family']}",
    )
    axes[0].set(ylabel="Discharge (m³/s)", title="Sealed chronological test")
    axes[0].legend(frameon=False, ncol=3)
    axes[0].grid(alpha=0.2)
    axes[1].plot(
        selected_candidate.index,
        selected_candidate.positive_loss_proxy_q,
        color="#64748b",
        alpha=0.55,
        label="positive endpoint-loss proxy",
    )
    axes[1].plot(
        selected_candidate.index,
        selected_candidate.seasonal_gate * selected_candidate.positive_loss_proxy_q,
        color="#16a34a",
        label="seasonally gated input",
    )
    if "slow_return_proxy_q" in selected_candidate:
        axes[1].plot(
            selected_candidate.index,
            selected_candidate.slow_return_proxy_q,
            color="#7c3aed",
            label="slow return proxy",
        )
    axes[1].axvspan(validation.index.min(), validation.index.max(), color="#facc15", alpha=0.12)
    axes[1].axvspan(test.index.min(), test.index.max(), color="#f97316", alpha=0.10)
    axes[1].set(ylabel="Proxy flow scale (m³/s)", title="Selected latent seasonal-loop state")
    axes[1].legend(frameon=False, ncol=3)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "seasonal_dual_path_diagnostics.png", dpi=180)
    plt.close(figure)

    summary = {
        "status": (
            "accepted_for_historically_gauged_gap_reconstruction"
            if accepted
            else "completed_seasonal_loop_diagnostic_predictor_rejected"
        ),
        "scope": (
            "Chronological mechanism diagnostic for historically observed XQM. Seasonal gates "
            "are calendar hypotheses, not measured irrigation schedules; latent storages are "
            "not groundwater observations."
        ),
        "protocol": {
            "train": [train.index.min().date().isoformat(), train.index.max().date().isoformat()],
            "validation": [validation.index.min().date().isoformat(), validation.index.max().date().isoformat()],
            "sealed_test": [test.index.min().date().isoformat(), test.index.max().date().isoformat()],
            "test_labels_used_for_fitting_or_selection": False,
            "families": FAMILIES,
            "selected_by": "lowest validation RMSE across predeclared families and memory grid",
        },
        "selected_candidate": {
            "family": selected["family"],
            "gate_kind": selected["gate_kind"],
            "fast_rho": selected["fast_rho"],
            "slow_rho": selected["slow_rho"],
            "fast_half_life_days": (
                float(np.log(0.5) / np.log(selected["fast_rho"]))
                if selected["fast_rho"] > 0
                else 0.0
            ),
            "slow_half_life_days": (
                float(np.log(0.5) / np.log(selected["slow_rho"]))
                if selected["slow_rho"] is not None and selected["slow_rho"] > 0
                else None
            ),
            "features": selected["features"],
            "coefficients": [float(value) for value in selected["coefficients"]],
        },
        "test_metrics": metrics.to_dict(orient="records"),
        "accepted_as_predictor": accepted,
        "decision": (
            "The validation-selected seasonal/dual-path candidate passed the sealed test and "
            "beat the label-free endpoint baseline."
            if accepted
            else "The seasonal/dual-path mechanism was evaluated under a sealed chronology but "
            "did not beat the label-free endpoint baseline. Retain only as latent mechanism "
            "diagnosis; measured diversion, irrigated-area, groundwater or baseflow proxies are "
            "still required before a causal irrigation-return claim."
        ),
    }
    (OUTPUT / "seasonal_dual_path_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_rows = metrics[
        ["method", "nse", "rmse", "pbias", "kge", "low_flow_rmse_m3s", "high_flow_rmse_m3s"]
    ].copy()
    report_table = "\n".join(
        "| {method} | {nse:.3f} | {rmse:.2f} | {pbias:+.2f}% | {kge:.3f} | {low:.2f} | {high:.2f} |".format(
            method=row.method,
            nse=row.nse,
            rmse=row.rmse,
            pbias=row.pbias,
            kge=row.kge,
            low=row.low_flow_rmse_m3s,
            high=row.high_flow_rmse_m3s,
        )
        for row in report_rows.itertuples(index=False)
    )
    report = f"""# 农业循环季节门控双通道实验

## 实验目的

在不使用实测引水量、灌溉面积或地下水位的情况下，把老师提出的“取水—下渗—储存—延迟回补”拆成快速与慢速两条潜在通道，并检验固定暖季门控能否改善XQM封闭重建。所有季节门控均由日历预先给定，不使用测试期XQM标签。

## 固定时间协议

- 率定：{train.index.min().date().isoformat()} 至 {train.index.max().date().isoformat()}；
- 验证：{validation.index.min().date().isoformat()} 至 {validation.index.max().date().isoformat()}；
- 封闭测试：{test.index.min().date().isoformat()} 至 {test.index.max().date().isoformat()}；
- 测试期标签未参与参数率定、记忆系数选择或模型家族选择。

验证期选中的候选为 `{selected['family']}`，快速记忆系数 {selected['fast_rho']}，慢速记忆系数 {selected['slow_rho']}，慢通道半衰期约 {summary['selected_candidate']['slow_half_life_days']:.1f} 天。

## 封闭测试结果

| 方法 | NSE | RMSE (m³/s) | PBIAS | KGE | 低流RMSE | 高流RMSE |
|---|---:|---:|---:|---:|---:|---:|
{report_table}

## 结论

验证期选中的季节双通道模型在测试期NSE为 {selected_score.nse:.3f}、RMSE为 {selected_score.rmse:.2f} m³/s、PBIAS为 {selected_score.pbias:+.2f}%，没有超过严格端点基线的NSE={blind_row.nse:.3f}、RMSE={blind_row.rmse:.2f} m³/s。慢状态在端点差快速下降后仍持续释放，造成测试期系统性高估。

因此，本轮保留“存在快慢记忆的潜在机制”作为诊断假设，但拒绝把它升级为正式虚拟站预测器。日历暖季不能代替真实引水计划；潜在储存也不能命名为真实地下水储量。下一步至少需要引水量、灌溉面积/作物需水、地下水位或基流分割中的一种独立代理。
"""
    (OUTPUT / "seasonal_dual_path_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
