"""Run fixed-split BD1M baseline experiments without test-set tuning."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
RESULTS = EXPERIMENT_DIR / "baseline_results.csv"
REPORT = EXPERIMENT_DIR / "baseline_report.md"

SPLITS = {"train": "train", "validation": "validation", "test": "test"}
DYNAMIC_FEATURES = [
    "P_antecedent_3d",
    "P_antecedent_7d",
    "P_antecedent_30d",
    "T_antecedent_7d",
    "T_antecedent_30d",
]
MODEL_FEATURES = ["Q_input_byblk", *DYNAMIC_FEATURES]


def nse(observed: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.sum((observed - np.mean(observed)) ** 2)
    return float(1 - np.sum((observed - predicted) ** 2) / denominator) if denominator else float("nan")


def kge(observed: np.ndarray, predicted: np.ndarray) -> float:
    obs_std = np.std(observed, ddof=1)
    pred_std = np.std(predicted, ddof=1)
    if obs_std == 0 or np.mean(observed) == 0:
        return float("nan")
    correlation = np.corrcoef(observed, predicted)[0, 1]
    alpha = pred_std / obs_std
    beta = np.mean(predicted) / np.mean(observed)
    return float(1 - np.sqrt((correlation - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def metrics(observed: pd.Series, predicted: pd.Series) -> dict[str, float | int]:
    valid = observed.notna() & predicted.notna()
    y_true = observed[valid].to_numpy(dtype=float)
    y_pred = predicted[valid].to_numpy(dtype=float)
    if not len(y_true):
        return {"n_samples": 0, "NSE": np.nan, "KGE": np.nan, "RMSE": np.nan, "MAE": np.nan}
    return {
        "n_samples": len(y_true),
        "NSE": nse(y_true, y_pred),
        "KGE": kge(y_true, y_pred),
        "RMSE": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "MAE": float(np.mean(np.abs(y_true - y_pred))),
    }


def main() -> None:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT, parse_dates=["date"])
    data = data.sort_values("date").reset_index(drop=True)
    data["persistence_prediction"] = data["Q_target_dsk"].shift(1)
    data["transfer_prediction"] = data["Q_input_byblk"]
    complete = data[MODEL_FEATURES + ["Q_target_dsk", "split_candidate"]].notna().all(axis=1)
    train = data[(data["split_candidate"] == SPLITS["train"]) & complete]
    validation = data[data["split_candidate"] == SPLITS["validation"]]
    test = data[data["split_candidate"] == SPLITS["test"]]

    predictions: dict[str, pd.Series] = {
        "Model-0 Persistence": data["persistence_prediction"],
        "Model-1 Upstream discharge transfer": data["transfer_prediction"],
    }
    linear = LinearRegression()
    linear.fit(train[MODEL_FEATURES], train["Q_target_dsk"])
    rf = RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)
    rf.fit(train[MODEL_FEATURES], train["Q_target_dsk"])
    predictions["Model-2 Linear Regression"] = pd.Series(
        linear.predict(data[MODEL_FEATURES].fillna(train[MODEL_FEATURES].median())), index=data.index
    )
    predictions["Model-3 Random Forest"] = pd.Series(
        rf.predict(data[MODEL_FEATURES].fillna(train[MODEL_FEATURES].median())), index=data.index
    )

    rows: list[dict[str, object]] = []
    for model_name, prediction in predictions.items():
        for split_name, split_value in SPLITS.items():
            subset = data["split_candidate"] == split_value
            result = metrics(data.loc[subset, "Q_target_dsk"], prediction.loc[subset])
            rows.append({"model": model_name, "split": split_name, **result})
    pd.DataFrame(rows).to_csv(RESULTS, index=False)

    report = f"""# VHS-BD1M Phase E1 Baseline 实验报告

## 实验范围

本阶段只运行四个 baseline，不训练复杂模型、不进行参数搜索、不使用 XQM，也不修改 Phase C/D 资产。

- 输入：`{INPUT.relative_to(ROOT)}`
- 目标：`Q_target_dsk`
- 输入流量：`Q_input_byblk`
- 动态气象：仅使用 E0 中已构建且来自目标日前的前期变量
- 实验结果：`{RESULTS.relative_to(ROOT)}`

## 固定时间划分

- train：1978–1981，`split_candidate=train`
- validation：1982，`split_candidate=validation`
- test：1983，`split_candidate=test`

测试集只用于最终报告指标；没有用测试集调参。验证集也没有用于调参，因为本阶段没有调参步骤。

## 模型定义

- **Model-0 Persistence**：`Q_DSK(t) = Q_DSK(t-1)`；仅作为时间持久性参考，不使用未来值。
- **Model-1 Upstream discharge transfer**：`Q_DSK(t) = Q_BYBLK(t)`。
- **Model-2 Linear Regression**：使用 `Q_input_byblk`、5 个 E0 动态气象变量拟合普通最小二乘线性回归；仅在 train 拟合。
- **Model-3 Random Forest**：使用相同输入变量，固定 `n_estimators=300`、`random_state=42`、`n_jobs=-1`；仅在 train 拟合，无参数搜索。

E0 中窗口不足的记录不参与回归模型训练；原始输入文件不被修改。为生成全日期预测，回归模型对缺失特征使用 train 中位数进行内部预测占位，但这些占位预测不会改变输入 CSV，也不作为完整样本指标的替代；指标按各模型实际有效预测样本计算。

## 指标

- NSE：Nash–Sutcliffe Efficiency，越高越好。
- KGE：Kling–Gupta Efficiency，越高越好。
- RMSE：均方根误差，单位与 Q 相同。
- MAE：平均绝对误差，单位与 Q 相同。

`baseline_results.csv` 按模型和 split 记录 `n_samples`、NSE、KGE、RMSE、MAE。

## 样本审计

- train 完整回归样本：{len(train)}
- validation 日期记录：{len(validation)}
- test 日期记录：{len(test)}
- Model-0 首日无前一日目标值，因此首日不计入有效预测样本。
- 未填补数据文件中的缺失值。

## 约束检查

- 测试集调参：否
- 未来气象信息：否；沿用 E0 的目标日前窗口字段
- XQM：未使用
- Phase C/D 文件：未修改
- 复杂模型训练：未执行
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"train={len(train)} validation={len(validation)} test={len(test)} results={RESULTS}")


if __name__ == "__main__":
    main()
