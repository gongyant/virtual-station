"""Diagnose BYBLK-to-DSK discharge propagation lags without model selection."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
OUTPUT = EXPERIMENT_DIR / "byblk_dsk_lag_results.csv"
REPORT = EXPERIMENT_DIR / "byblk_dsk_lag_report.md"
PLOT = EXPERIMENT_DIR / "byblk_dsk_lag_nse.png"


def nse(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.sum((observed - np.mean(observed)) ** 2)
    return float(1 - np.sum((observed - predicted) ** 2) / denominator) if denominator else float("nan")


def kge(observed: np.ndarray, predicted: np.ndarray) -> float:
    if len(observed) < 2 or np.mean(observed) == 0 or np.std(observed, ddof=1) == 0:
        return float("nan")
    correlation = np.corrcoef(observed, predicted)[0, 1]
    alpha = np.std(predicted, ddof=1) / np.std(observed, ddof=1)
    beta = np.mean(predicted) / np.mean(observed)
    return float(1 - np.sqrt((correlation - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def score(observed: pd.Series, predicted: pd.Series) -> dict[str, float | int]:
    valid = observed.notna() & predicted.notna()
    y_true = observed[valid].to_numpy(dtype=float)
    y_pred = predicted[valid].to_numpy(dtype=float)
    if not len(y_true):
        return {"n_samples": 0, "NSE": np.nan, "KGE": np.nan, "RMSE": np.nan, "MAE": np.nan, "Bias": np.nan}
    return {
        "n_samples": len(y_true),
        "NSE": nse(y_true, y_pred),
        "KGE": kge(y_true, y_pred),
        "RMSE": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "MAE": float(np.mean(np.abs(y_true - y_pred))),
        "Bias": float(np.mean(y_pred - y_true)),
    }


def main() -> None:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    data["Q_BYBLK"] = data["Q_input_byblk"]
    rows: list[dict[str, object]] = []
    for lag in range(31):
        prediction = data["Q_BYBLK"].shift(lag)
        for split in ("train", "validation", "test"):
            mask = data["split_candidate"] == split
            values = score(data.loc[mask, "Q_target_dsk"], prediction.loc[mask])
            rows.append({"lag_days": lag, "split": split, **values})
    results = pd.DataFrame(rows)
    results.to_csv(OUTPUT, index=False)

    plot_data = results.pivot(index="lag_days", columns="split", values="NSE")
    plt.figure(figsize=(8, 5))
    for split, color in (("train", "#2563eb"), ("validation", "#d97706"), ("test", "#dc2626")):
        plt.plot(plot_data.index, plot_data[split], marker="o", linewidth=1.8, label=split, color=color)
    plt.axhline(0, color="#6b7280", linewidth=0.8)
    plt.xlabel("BYBLK lag k (days)")
    plt.ylabel("NSE")
    plt.title("BYBLK → DSK lag diagnostic")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(PLOT, dpi=180)
    plt.close()

    valid = results[results["n_samples"] > 0]
    summary_lines = []
    for split in ("train", "validation", "test"):
        subset = valid[valid["split"] == split].sort_values("NSE", ascending=False).iloc[0]
        summary_lines.append(f"- {split} 最高 NSE 的 lag 仅作为诊断摘要：`{int(subset.lag_days)} days`，NSE=`{subset.NSE:.6f}`。")
    report = f"""# VHS-BD1M Phase E1.5 流量传播滞后诊断

## 目的

诊断 BYBLK 到 DSK 的候选流量传播滞后，不训练深度模型，不建立待部署模型，也不使用测试集选择最佳 lag。

## 方法

对每个 `k = 0, 1, ..., 30` days，构造：

`Q_pred_DSK(t; k) = Q_BYBLK(t-k)`

其中 `k=0` 表示同日转移，`k>0` 表示使用目标日前的 BYBLK 流量。每个 lag 在固定时间分区内单独计算指标：

- train：1978–1981；
- validation：1982；
- test：1983。

输出：`{OUTPUT.relative_to(ROOT)}`

## 指标

- NSE：Nash–Sutcliffe Efficiency；
- KGE：Kling–Gupta Efficiency；
- RMSE：均方根误差，单位与 Q 相同；
- MAE：平均绝对误差，单位与 Q 相同；
- Bias：`mean(Q_pred - Q_DSK)`，单位与 Q 相同。

每个 lag 的有效样本数 `n_samples` 单独记录；由于移位会在序列起始处产生缺失，不进行填补。

## 图形

lag-NSE 曲线：`{PLOT.relative_to(ROOT)}`

![lag-NSE curve](byblk_dsk_lag_nse.png)

## 诊断摘要

{chr(10).join(summary_lines)}

上述最高 NSE 仅为分区内描述性统计，不作为模型选择依据；本阶段没有根据 validation 或 test 结果选择最终 lag。

## 数据与约束

- 输入：`{INPUT.relative_to(ROOT)}`；E0 数据只读，未修改；
- BYBLK 输入：`Q_input_byblk`；
- DSK 目标：`Q_target_dsk`；
- 未使用 XQM；
- 未使用未来气象信息；
- 未修改 Phase C/D 资产；
- 未训练深度模型；
- 未进行测试集选择、调参或模型部署。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"lags=31 rows={len(results)} plot={PLOT}")


if __name__ == "__main__":
    main()
