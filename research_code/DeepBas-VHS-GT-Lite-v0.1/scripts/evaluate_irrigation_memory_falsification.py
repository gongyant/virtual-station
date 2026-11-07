from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics

from scripts.evaluate_irrigation_seasonal_dual_path import (
    fit_candidate,
    gated_storage,
    predict_candidate,
    prepare_reach,
)


OUTPUT = Path(
    "outputs/virtual_station_mainline/irrigation_memory_falsification_round"
)
PHASE_SHIFTS_DAYS = list(range(0, 360, 10))
FAST_RHO = 0.0
SLOW_RHO = 0.99


def smooth_warm_gate_with_phase(
    index: pd.DatetimeIndex, phase_shift_days: float
) -> np.ndarray:
    phase = (
        2.0
        * np.pi
        * (index.dayofyear.to_numpy(float) - 91.0 - phase_shift_days)
        / 365.25
    )
    return np.maximum(np.sin(phase), 0.0)


def build_phase_candidate(
    reach: pd.DataFrame, phase_shift_days: float
) -> tuple[pd.DataFrame, list[str], np.ndarray, np.ndarray]:
    candidate = reach.copy()
    gate = smooth_warm_gate_with_phase(candidate.index, phase_shift_days)
    candidate["seasonal_gate"] = gate
    candidate["gated_loss_proxy_q"] = candidate.positive_loss_proxy_q * gate
    fast_storage, fast_release = gated_storage(
        candidate.positive_loss_proxy_q.to_numpy(float), gate, FAST_RHO
    )
    slow_storage, slow_release = gated_storage(
        candidate.positive_loss_proxy_q.to_numpy(float), gate, SLOW_RHO
    )
    candidate["fast_storage_proxy_q_days"] = fast_storage
    candidate["fast_return_proxy_q"] = fast_release
    candidate["slow_storage_proxy_q_days"] = slow_storage
    candidate["slow_return_proxy_q"] = slow_release
    candidate["intercept"] = 1.0
    features = [
        "geometric_endpoint_q",
        "endpoint_gap_q",
        "gated_loss_proxy_q",
        "fast_return_proxy_q",
        "slow_return_proxy_q",
        "intercept",
    ]
    lower = np.array([0.0, -2.0, -2.0, 0.0, 0.0, -200.0])
    upper = np.array([3.0, 2.0, 0.0, 2.0, 2.0, 200.0])
    return candidate, features, lower, upper


def percentile_lower_is_better(value: float, controls: pd.Series) -> float:
    controls = pd.Series(controls).dropna()
    if len(controls) == 0:
        return np.nan
    return float(controls.ge(value).mean())


def native_dict(series: pd.Series) -> dict:
    """Convert pandas/numpy scalars to JSON-safe native Python values."""
    return {
        key: value.item() if isinstance(value, np.generic) else value
        for key, value in series.to_dict().items()
    }


def main() -> None:
    reach = prepare_reach()
    n = len(reach)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    train = reach.iloc[:train_end]
    validation = reach.iloc[train_end:validation_end]
    test = reach.iloc[validation_end:]

    rows = []
    predictions = pd.DataFrame(index=test.index)
    predictions["XQM_observed"] = test.XQM
    predictions["strict_blind_geometric_endpoints"] = test.geometric_endpoint_q
    for shift in PHASE_SHIFTS_DAYS:
        candidate, features, lower, upper = build_phase_candidate(reach, shift)
        coefficients = fit_candidate(
            candidate.iloc[:train_end], features, lower, upper
        )
        validation_prediction = predict_candidate(
            candidate.iloc[train_end:validation_end], features, coefficients
        )
        test_prediction = predict_candidate(
            candidate.iloc[validation_end:], features, coefficients
        )
        validation_score = regression_metrics(validation.XQM, validation_prediction)
        test_score = regression_metrics(test.XQM, test_prediction)
        rows.append(
            {
                "phase_shift_days": shift,
                "control_type": "teacher_aligned_warm_gate" if shift == 0 else "season_phase_placebo",
                "validation_nse": validation_score["nse"],
                "validation_rmse_m3s": validation_score["rmse"],
                "validation_pbias_percent": validation_score["pbias"],
                "test_nse": test_score["nse"],
                "test_rmse_m3s": test_score["rmse"],
                "test_pbias_percent": test_score["pbias"],
                "geometric_coefficient": float(coefficients[0]),
                "endpoint_gap_coefficient": float(coefficients[1]),
                "gated_loss_coefficient": float(coefficients[2]),
                "fast_return_coefficient": float(coefficients[3]),
                "slow_return_coefficient": float(coefficients[4]),
                "intercept": float(coefficients[5]),
            }
        )
        predictions[f"phase_shift_{shift:03d}_q"] = test_prediction

    scores = pd.DataFrame(rows).sort_values("phase_shift_days")
    physical = scores.loc[scores.phase_shift_days.eq(0)].iloc[0]
    controls = scores.loc[scores.phase_shift_days.ne(0)]
    selected_placebo = controls.sort_values(
        ["validation_rmse_m3s", "phase_shift_days"]
    ).iloc[0]
    blind_score = regression_metrics(test.XQM, test.geometric_endpoint_q)

    validation_percentile = percentile_lower_is_better(
        physical.validation_rmse_m3s, controls.validation_rmse_m3s
    )
    test_percentile = percentile_lower_is_better(
        physical.test_rmse_m3s, controls.test_rmse_m3s
    )
    control_validation_outperform = int(
        controls.validation_rmse_m3s.le(physical.validation_rmse_m3s).sum()
    )
    control_test_outperform = int(
        controls.test_rmse_m3s.le(physical.test_rmse_m3s).sum()
    )
    season_specific = bool(
        validation_percentile >= 0.90
        and test_percentile >= 0.90
        and physical.test_rmse_m3s < blind_score["rmse"]
        and physical.test_nse > blind_score["nse"]
    )

    summary = {
        "status": "completed_post_sealed_memory_falsification_audit",
        "scope": (
            "Post-sealed falsification audit. The test block was opened in the previous round; "
            "these results can reject specificity but cannot create a new blind acceptance claim."
        ),
        "protocol": {
            "train": [train.index.min().date().isoformat(), train.index.max().date().isoformat()],
            "validation": [validation.index.min().date().isoformat(), validation.index.max().date().isoformat()],
            "previously_opened_test": [test.index.min().date().isoformat(), test.index.max().date().isoformat()],
            "phase_shifts_days": PHASE_SHIFTS_DAYS,
            "placebo_controls": len(controls),
            "fixed_fast_rho": FAST_RHO,
            "fixed_slow_rho": SLOW_RHO,
            "coefficients_refit_on_training_only_for_each_phase": True,
            "placebo_selected_by_validation_only": True,
        },
        "teacher_aligned_gate": native_dict(physical),
        "validation_selected_placebo": native_dict(selected_placebo),
        "strict_blind_endpoint_baseline": blind_score,
        "specificity": {
            "teacher_gate_validation_percentile_lower_rmse_is_better": validation_percentile,
            "teacher_gate_test_percentile_lower_rmse_is_better": test_percentile,
            "placebos_outperform_teacher_gate_on_validation": control_validation_outperform,
            "placebos_outperform_teacher_gate_on_test": control_test_outperform,
            "season_timing_specificity_supported": season_specific,
        },
        "decision": (
            "Teacher-aligned seasonal timing survived the placebo audit, but because this is a "
            "post-sealed analysis it still requires a new year for confirmation."
            if season_specific
            else "The 69-day seasonal-memory interpretation is not specific enough: phase-shifted "
            "calendar controls perform as well as or better, or the model still fails to beat the "
            "label-free endpoint baseline. Retain the latent state only as a non-causal diagnostic."
        ),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    scores.to_csv(OUTPUT / "memory_phase_placebo_metrics.csv", index=False)
    predictions.reset_index().to_csv(
        OUTPUT / "memory_phase_placebo_test_predictions.csv", index=False
    )
    (OUTPUT / "memory_falsification_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(2, 1, figsize=(11.5, 7.3), constrained_layout=True)
    axes[0].plot(
        scores.phase_shift_days,
        scores.validation_rmse_m3s,
        marker="o",
        ms=3.5,
        color="#2563eb",
        label="validation RMSE",
    )
    axes[0].plot(
        scores.phase_shift_days,
        scores.test_rmse_m3s,
        marker="o",
        ms=3.5,
        color="#ea580c",
        label="previously opened test RMSE",
    )
    axes[0].axvline(0, color="#111827", linestyle="--", label="teacher-aligned gate")
    axes[0].axhline(blind_score["rmse"], color="#64748b", linestyle=":", label="endpoint baseline")
    axes[0].set(
        xlabel="Seasonal gate phase shift (days)",
        ylabel="RMSE (m³/s)",
        title="Calendar-phase placebo audit",
    )
    axes[0].legend(frameon=False, ncol=2)
    axes[0].grid(alpha=0.2)

    axes[1].plot(test.index, test.XQM, color="#111827", lw=1.8, label="XQM observed")
    axes[1].plot(
        test.index,
        test.geometric_endpoint_q,
        color="#2563eb",
        label="blind endpoints",
    )
    axes[1].plot(
        test.index,
        predictions["phase_shift_000_q"],
        color="#ea580c",
        label="teacher-aligned warm gate",
    )
    axes[1].plot(
        test.index,
        predictions[f"phase_shift_{int(selected_placebo.phase_shift_days):03d}_q"],
        color="#7c3aed",
        linestyle="--",
        label=f"validation-selected placebo ({int(selected_placebo.phase_shift_days)} d)",
    )
    axes[1].set(
        ylabel="Discharge (m³/s)",
        title="Previously opened test: physical gate versus placebo",
    )
    axes[1].legend(frameon=False, ncol=2)
    axes[1].grid(alpha=0.2)
    figure.savefig(OUTPUT / "memory_falsification_diagnostics.png", dpi=180)
    plt.close(figure)

    report = f"""# 农业循环69天记忆机制反证实验

## 说明

本轮是事后反证审计，不是新的盲测。上一轮已经打开2005-09-04至2005-10-28的测试标签，因此本轮结果只能削弱或保留机制假设，不能重新宣布模型通过。

固定快通道ρ={FAST_RHO}、慢通道ρ={SLOW_RHO}，将暖季门控每10天平移一次，共比较1个教师机制对齐门和{len(controls)}个季节相位安慰剂。每个相位的系数只使用率定期XQM拟合；最佳安慰剂只按验证期选择。

## 结果

- 教师对齐门：验证RMSE={physical.validation_rmse_m3s:.2f} m³/s，事后测试RMSE={physical.test_rmse_m3s:.2f} m³/s，NSE={physical.test_nse:.3f}；
- 验证期选择的安慰剂相位：平移{int(selected_placebo.phase_shift_days)}天，验证RMSE={selected_placebo.validation_rmse_m3s:.2f} m³/s，事后测试RMSE={selected_placebo.test_rmse_m3s:.2f} m³/s；
- {control_validation_outperform}/{len(controls)}个安慰剂在验证期RMSE不高于教师对齐门；
- {control_test_outperform}/{len(controls)}个安慰剂在事后测试RMSE不高于教师对齐门；
- 严格端点基线事后测试RMSE={blind_score['rmse']:.2f} m³/s、NSE={blind_score['nse']:.3f}。

## 结论

季节时序特异性是否得到支持：**{'是' if season_specific else '否'}**。

{'教师对齐的季节门通过了相位安慰剂审计，但由于测试标签已经打开，仍需用新年份独立确认。' if season_specific else '69天季节记忆的解释不具备足够特异性：错位日历对照能够达到或超过它，且该模型未超过无标签端点基线。因此只能把这一潜在状态保留为非因果诊断量。'}

因此，69天慢记忆不能命名为真实地下水回补时间。下一步若没有独立引水、灌溉面积、地下水位或基流代理，应停止继续增加储水状态复杂度；可保留端点基线作为当前正式预测器。
"""
    (OUTPUT / "memory_falsification_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
