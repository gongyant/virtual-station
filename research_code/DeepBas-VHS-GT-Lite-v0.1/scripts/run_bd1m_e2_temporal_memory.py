"""Run E2 temporal-memory and cross-correlation diagnostics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
HISTORY_OUTPUT = EXPERIMENT_DIR / "history_window_results.csv"
CORR_OUTPUT = EXPERIMENT_DIR / "cross_correlation_results.csv"
REPORT = EXPERIMENT_DIR / "e2_temporal_memory_report.md"

SPLITS = {"train": "train", "validation": "validation", "test": "test"}


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


def metrics(observed: pd.Series, predicted: np.ndarray) -> dict[str, float | int]:
    valid = observed.notna() & np.isfinite(predicted)
    y_true = observed[valid].to_numpy(dtype=float)
    y_pred = predicted[valid]
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


def build_windows(data: pd.DataFrame, column: str) -> list[str]:
    names = []
    for lag in range(1, 31):
        name = f"{column}_lag_{lag}d"
        data[name] = data[column].shift(lag)
        names.append(name)
    return names


def main() -> None:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    byblk_features = build_windows(data, "Q_input_byblk")
    dsk_features = build_windows(data, "Q_target_dsk")
    data["Q_DSK_target"] = data["Q_target_dsk"]

    result_rows: list[dict[str, object]] = []
    for family, features in (("BYBLK_history", byblk_features), ("DSK_history", dsk_features)):
        train_mask = (data["split_candidate"] == SPLITS["train"]) & data[features + ["Q_DSK_target"]].notna().all(axis=1)
        train = data.loc[train_mask]
        for model_name, model in (
            ("Linear Regression", LinearRegression()),
            ("Random Forest", RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)),
        ):
            model.fit(train[features], train["Q_DSK_target"])
            for split_name, split_value in SPLITS.items():
                mask = (data["split_candidate"] == split_value) & data[features + ["Q_DSK_target"]].notna().all(axis=1)
                subset = data.loc[mask]
                prediction = model.predict(subset[features]) if len(subset) else np.array([])
                result_rows.append({
                    "feature_family": family,
                    "model": model_name,
                    "split": split_name,
                    **metrics(subset["Q_DSK_target"], prediction),
                })

    pd.DataFrame(result_rows).to_csv(HISTORY_OUTPUT, index=False)

    correlation_rows: list[dict[str, object]] = []
    for lag in range(31):
        shifted = data["Q_input_byblk"].shift(lag)
        for split_name, split_value in SPLITS.items():
            mask = (data["split_candidate"] == split_value) & shifted.notna() & data["Q_target_dsk"].notna()
            if mask.sum() >= 2:
                pearson = float(shifted[mask].corr(data.loc[mask, "Q_target_dsk"]))
            else:
                pearson = float("nan")
            correlation_rows.append({
                "lag_days": lag,
                "split": split_name,
                "n_samples": int(mask.sum()),
                "pearson_correlation": pearson,
            })
    pd.DataFrame(correlation_rows).to_csv(CORR_OUTPUT, index=False)

    history = pd.DataFrame(result_rows)
    corr = pd.DataFrame(correlation_rows)
    report_lines = []
    for family in ("BYBLK_history", "DSK_history"):
        subset = history[(history.feature_family == family) & (history.split == "test")]
        best = subset.sort_values("NSE", ascending=False).iloc[0]
        report_lines.append(
            f"- {family} 测试集最高 NSE 仅作描述性摘要：{best.model}，NSE=`{best.NSE:.6f}`；未据此调参。"
        )
    corr_test = corr[corr.split == "test"].sort_values("pearson_correlation", ascending=False).iloc[0]
    report = f"""# VHS-BD1M Phase E2 时间记忆与上游输入贡献报告

## 实验目的

本阶段诊断 DSK 流量中的时间记忆与 BYBLK 上游输入贡献，不训练复杂深度模型，不进行测试集调参，不修改 E0/E1 文件。

输出：

- 历史窗口结果：`{HISTORY_OUTPUT.relative_to(ROOT)}`
- BYBLK–DSK 交叉相关：`{CORR_OUTPUT.relative_to(ROOT)}`

## 固定时间划分

- train：1978–1981；
- validation：1982；
- test：1983。

模型只在 train 子集拟合；validation 和 test 只用于分区诊断。

## 实验 1：BYBLK 历史窗口

构造 `Q_BYBLK(t-1)` 至 `Q_BYBLK(t-30)`，训练：

- Linear Regression；
- Random Forest，固定 `n_estimators=300`、`random_state=42`，无参数搜索。

## 实验 2：DSK 自身历史窗口

构造 `Q_DSK(t-1)` 至 `Q_DSK(t-30)`，训练：

- Linear Regression；
- Random Forest，固定 `n_estimators=300`、`random_state=42`，无参数搜索。

DSK 历史窗口仅作为时间记忆诊断输入，未与 XQM 或其他站点数据混合。

## 实验 3：BYBLK–DSK cross correlation

对 `lag=0...30` 计算：

`Pearson(Q_BYBLK(t-lag), Q_DSK(t))`

分别在 train、validation、test 内计算，并记录有效样本数。没有根据 test 相关系数选择 lag。

测试集最高 Pearson 仅作描述性摘要：lag=`{int(corr_test.lag_days)} days`，r=`{corr_test.pearson_correlation:.6f}`；不作为模型选择。

## 结果摘要

{chr(10).join(report_lines)}

完整 NSE、KGE、RMSE、MAE、Bias 和样本数见 `history_window_results.csv`；完整 0–30 日 Pearson 结果见 `cross_correlation_results.csv`。

## 指标

- NSE：Nash–Sutcliffe Efficiency；
- KGE：Kling–Gupta Efficiency；
- RMSE：均方根误差；
- MAE：平均绝对误差；
- Bias：`mean(Q_pred - Q_DSK)`；
- Pearson correlation：BYBLK 滞后流量与 DSK 当日流量的线性相关系数。

## 缺失与泄漏处理

每个历史窗口要求完整的 30 日历史；窗口起始处不足 30 天的记录不参与对应模型训练或评估，不进行插值、填补或复制。窗口只使用目标日前的 Q 值，没有使用未来气象信息。

## 约束确认

- 未修改 `bd1m_model_dataset_audit.csv`；
- 未修改 E1 lag 诊断文件；
- 未修改 Phase C/D 资产；
- 未使用 XQM；
- 未使用测试集调参；
- 未训练复杂深度模型；
- 未选择或部署最佳模型。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"history_rows={len(result_rows)} correlation_rows={len(correlation_rows)}")


if __name__ == "__main__":
    main()
