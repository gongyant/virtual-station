"""Diagnose fixed upstream-to-downstream discharge lags without model training."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
OUT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
RESULTS = OUT_DIR / "byblk_dsk_lag_results.csv"
REPORT = OUT_DIR / "byblk_dsk_lag_report.md"
FIGURE = OUT_DIR / "byblk_dsk_lag_nse_curve.png"
SPLITS = {"train": "train", "validation": "validation", "test": "test"}


def nse(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.sum((observed - np.mean(observed)) ** 2)
    return float(1 - np.sum((observed - predicted) ** 2) / denominator) if denominator else np.nan


def kge(observed: np.ndarray, predicted: np.ndarray) -> float:
    obs_mean = np.mean(observed)
    obs_std = np.std(observed, ddof=1)
    if obs_mean == 0 or obs_std == 0:
        return np.nan
    correlation = np.corrcoef(observed, predicted)[0, 1]
    alpha = np.std(predicted, ddof=1) / obs_std
    beta = np.mean(predicted) / obs_mean
    return float(1 - np.sqrt((correlation - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def calculate(observed: pd.Series, predicted: pd.Series) -> dict[str, float | int]:
    valid = observed.notna() & predicted.notna()
    y_true = observed[valid].to_numpy(dtype=float)
    y_pred = predicted[valid].to_numpy(dtype=float)
    if not len(y_true):
        return {"n_samples": 0, "NSE": np.nan, "KGE": np.nan, "RMSE": np.nan, "MAE": np.nan, "Bias": np.nan}
    residual = y_pred - y_true
    return {
        "n_samples": len(y_true),
        "NSE": nse(y_true, y_pred),
        "KGE": kge(y_true, y_pred),
        "RMSE": float(np.sqrt(np.mean(residual**2))),
        "MAE": float(np.mean(np.abs(residual))),
        "Bias": float(np.mean(residual)),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    data["Q_target_dsk"] = pd.to_numeric(data["Q_target_dsk"], errors="coerce")
    data["Q_input_byblk"] = pd.to_numeric(data["Q_input_byblk"], errors="coerce")
    rows: list[dict[str, object]] = []
    for lag in range(31):
        prediction = data["Q_input_byblk"].shift(lag)
        for split_name, split_value in SPLITS.items():
            subset = data["split_candidate"] == split_value
            result = calculate(data.loc[subset, "Q_target_dsk"], prediction.loc[subset])
            rows.append({"lag_days": lag, "split": split_name, **result})
    results = pd.DataFrame(rows)
    results.to_csv(RESULTS, index=False)

    test = results[results["split"] == "test"].sort_values("lag_days")
    best_test_lag = int(test.loc[test["NSE"].idxmax(), "lag_days"])
    validation = results[results["split"] == "validation"].sort_values("lag_days")
    best_validation_lag = int(validation.loc[validation["NSE"].idxmax(), "lag_days"])
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for split_name in SPLITS:
        subset = results[results["split"] == split_name]
        ax.plot(subset["lag_days"], subset["NSE"], marker="o", markersize=3, label=split_name)
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Upstream discharge lag k (days)")
    ax.set_ylabel("NSE")
    ax.set_title("BYBLK → DSK discharge lag diagnostic")
    ax.set_xticks(range(0, 31, 5))
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.savefig(FIGURE, dpi=180)
    plt.close(fig)

    wide = results.pivot(index="lag_days", columns="split", values="NSE")
    report = f"""# VHS-BD1M Phase E1.5 流量传播滞后诊断

## 实验目的

诊断 BYBLK→DSK 的流量传播滞后，不训练深度模型，不拟合任何复杂模型。对每个 `k=0,1,...,30` 天构造：

`Q_pred_DSK(t; k) = Q_BYBLK(t-k)`

并与当天的 `Q_target_dsk(t)` 比较。

## 数据与划分

- 输入：`{INPUT.relative_to(ROOT)}`
- 输出：`{RESULTS.relative_to(ROOT)}`
- 固定 train：1978–1981
- 固定 validation：1982
- 固定 test：1983
- 输出曲线：`{FIGURE.relative_to(ROOT)}`
- BYBLK 输入：`Q_input_byblk`
- DSK 目标：`Q_target_dsk`

每个 lag 仅在对应日期划分内计算指标；lag 造成的首部无历史流量日期保留为缺失，不跨 split 借用或填补。未修改 E0 数据。

## 指标定义

- NSE：Nash–Sutcliffe Efficiency。
- KGE：Kling–Gupta Efficiency。
- RMSE：均方根误差。
- MAE：平均绝对误差。
- Bias：`mean(Q_pred - Q_observed)`，单位与流量一致；正值表示预测偏高。

## 结果使用规则

本实验是诊断分析。测试集结果只用于最终报告，不能用于选择最佳滞后。若后续需要选择 lag，应预先用 validation 选择，之后一次性报告 test 结果。本报告同时报告 validation 最优 NSE lag（仅诊断信息）和 test 最优 NSE lag（仅描述性，不作为选择依据）。

- validation 最优 NSE lag：`{best_validation_lag}` 天
- test 最大 NSE lag：`{best_test_lag}` 天（描述性，未用于决策）

## NSE 摘要

| lag_days | train NSE | validation NSE | test NSE |
|---:|---:|---:|---:|
""" + "\n".join(
        f"| {lag} | {wide.loc[lag, 'train']:.6f} | {wide.loc[lag, 'validation']:.6f} | {wide.loc[lag, 'test']:.6f} |"
        for lag in wide.index
    ) + f"""

## 约束检查

- 未训练深度模型。
- 未使用测试集选择最佳模型或最佳滞后。
- 未使用未来气象信息。
- 未添加 XQM。
- 未修改 E0 数据。
- 未修改 Phase C/D 数据。
- 未修改冻结路径。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"lags=31 rows={len(results)} validation_best={best_validation_lag} test_descriptive_best={best_test_lag}")


if __name__ == "__main__":
    main()
