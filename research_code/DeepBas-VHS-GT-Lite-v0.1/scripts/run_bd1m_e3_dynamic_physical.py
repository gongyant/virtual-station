"""Train fixed-configuration E3 dynamic-physical neural baselines."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
OUTPUT = EXPERIMENT_DIR / "e3_dynamic_physical_results.csv"
REPORT = EXPERIMENT_DIR / "e3_model_report.md"
SEED = 42
WINDOW = 30
DYNAMIC = [
    "Q_input_byblk",
    "P_antecedent_3d",
    "P_antecedent_7d",
    "P_antecedent_30d",
    "T_antecedent_7d",
    "T_antecedent_30d",
]
STATIC = ["length_km", "elevation_drop_m", "mean_slope", "median_slope", "width_m"]


class MLP(nn.Module):
    def __init__(self, input_size: int) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(input_size, 64), nn.ReLU(), nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class LSTMModel(nn.Module):
    def __init__(self, dynamic_size: int, static_size: int) -> None:
        super().__init__()
        self.lstm = nn.LSTM(dynamic_size, 32, batch_first=True)
        self.head = nn.Sequential(nn.Linear(32 + static_size, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, sequence: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        output, _ = self.lstm(sequence)
        return self.head(torch.cat([output[:, -1], static], dim=1))


class TemporalCNN(nn.Module):
    def __init__(self, dynamic_size: int, static_size: int) -> None:
        super().__init__()
        self.conv = nn.Sequential(nn.Conv1d(dynamic_size, 32, 3, padding=1), nn.ReLU(), nn.Conv1d(32, 16, 3, padding=1), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(16 + static_size, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, sequence: torch.Tensor, static: torch.Tensor) -> torch.Tensor:
        features = self.conv(sequence.transpose(1, 2)).mean(dim=2)
        return self.head(torch.cat([features, static], dim=1))


def metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float | int]:
    denominator = np.sum((y_true - y_true.mean()) ** 2)
    correlation = np.corrcoef(y_true, y_pred)[0, 1]
    alpha = y_pred.std(ddof=1) / y_true.std(ddof=1)
    beta = y_pred.mean() / y_true.mean()
    return {
        "n_samples": len(y_true),
        "NSE": float(1 - np.sum((y_true - y_pred) ** 2) / denominator),
        "KGE": float(1 - np.sqrt((correlation - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)),
        "RMSE": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "MAE": float(np.mean(np.abs(y_true - y_pred))),
        "Bias": float(np.mean(y_pred - y_true)),
    }


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(INPUT, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    data = data.dropna(subset=DYNAMIC + STATIC + ["Q_target_dsk"]).reset_index(drop=True)
    q = data["Q_input_byblk"].to_numpy(dtype=np.float32)
    dynamic = data[DYNAMIC].to_numpy(dtype=np.float32)
    static = data[STATIC].to_numpy(dtype=np.float32)
    target = data["Q_target_dsk"].to_numpy(dtype=np.float32)
    samples = []
    for index in range(WINDOW - 1, len(data)):
        samples.append({"index": index, "sequence": dynamic[index - WINDOW + 1:index + 1], "static": static[index], "target": target[index], "split": data.loc[index, "split_candidate"]})
    sequences = np.stack([row["sequence"] for row in samples])
    statics = np.stack([row["static"] for row in samples])
    targets = np.asarray([row["target"] for row in samples], dtype=np.float32)
    splits = np.asarray([row["split"] for row in samples])
    n_samples = len(samples)

    train_mask = splits == "train"
    mean_dynamic = sequences[train_mask].reshape(-1, sequences.shape[-1]).mean(axis=0)
    std_dynamic = sequences[train_mask].reshape(-1, sequences.shape[-1]).std(axis=0)
    std_dynamic[std_dynamic == 0] = 1
    mean_static = statics[train_mask].mean(axis=0)
    std_static = statics[train_mask].std(axis=0)
    std_static[std_static == 0] = 1
    mean_target = targets[train_mask].mean()
    std_target = targets[train_mask].std() or 1
    x_seq = (sequences - mean_dynamic) / std_dynamic
    x_static = (statics - mean_static) / std_static
    y = (targets - mean_target) / std_target

    tensors = {
        "sequence": torch.tensor(x_seq, dtype=torch.float32),
        "static": torch.tensor(x_static, dtype=torch.float32),
        "target": torch.tensor(y[:, None], dtype=torch.float32),
    }
    result_rows = []
    models = {
        "Model-1 MLP regression": (MLP(WINDOW * len(DYNAMIC)), "mlp"),
        "Model-2 LSTM 30-day window": (LSTMModel(len(DYNAMIC), len(STATIC)), "sequence"),
        "Model-3 Temporal CNN": (TemporalCNN(len(DYNAMIC), len(STATIC)), "sequence"),
    }
    for name, (model, kind) in models.items():
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        model.train()
        for _ in range(50):
            optimizer.zero_grad()
            if kind == "mlp":
                prediction = model(tensors["sequence"].reshape(n_samples, -1))
            else:
                prediction = model(tensors["sequence"], tensors["static"])
            loss = nn.functional.mse_loss(prediction[train_mask], tensors["target"][train_mask])
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            if kind == "mlp":
                prediction = model(tensors["sequence"].reshape(n_samples, -1))
            else:
                prediction = model(tensors["sequence"], tensors["static"])
        prediction = prediction[:, 0].numpy() * std_target + mean_target
        for split in ("train", "validation", "test"):
            mask = splits == split
            result = metrics(targets[mask], prediction[mask])
            rows_for_output = {"model": name, "split": split, "window_days": WINDOW, **result}
            rows_for_output["train_only_fit"] = True
            rows_for_output["future_information_leakage"] = False
            rows_for_output["xqm_used"] = False
            result_rows.append(rows_for_output)
    pd.DataFrame(result_rows).to_csv(OUTPUT, index=False)

    result = pd.read_csv(OUTPUT)
    test_summary = result[result["split"] == "test"].sort_values("NSE", ascending=False)
    report = f"""# VHS-BD1M Phase E3 动态 + 物理特征 baseline 报告

## 实验范围

本阶段使用 E0 baseline dataset 的已有动态变量，并加入 D0 reach 级物理属性的路径摘要，训练三个固定结构的神经网络 baseline。未使用 XQM，未修改 E0/E1/E2 文件。

- 输入：`{INPUT.relative_to(ROOT)}`
- 输出：`{OUTPUT.relative_to(ROOT)}`
- train：1978–1981
- validation：1982
- test：1983
- 训练样本：{int(train_mask.sum())}
- validation 样本：{int((splits == 'validation').sum())}
- test 样本：{int((splits == 'test').sum())}

## 特征

动态序列每个时点包含：

- `Q_input_byblk`
- `P_antecedent_3d`
- `P_antecedent_7d`
- `P_antecedent_30d`
- `T_antecedent_7d`
- `T_antecedent_30d`

序列长度为 30 日，使用目标日前及当日已有输入；E0 动态气象窗口本身已按目标日前构造，未引入未来气象信息。

静态路径摘要来自 D0：

- `length_km`
- `elevation_drop_m`
- `mean_slope`
- `median_slope`
- `width_m`

标准化均值和标准差只用 train 计算。目标变量也只使用 train 统计量反标准化。

## 模型

- Model-1：MLP regression，固定两层全连接网络；
- Model-2：LSTM，30 日动态序列 + 静态物理特征；
- Model-3：Temporal CNN，30 日动态序列 + 静态物理特征。

所有模型均使用固定 `seed=42`、Adam `learning_rate=0.001`、50 个训练 epoch。没有使用 validation/test 选择 epoch、结构或参数；validation/test 只评价。

## 测试集摘要

{test_summary.to_string(index=False)}

完整 train、validation、test 指标见 `e3_dynamic_physical_results.csv`，包括 NSE、KGE、RMSE、MAE、Bias 和样本数。

## 约束检查

- 只在 train 拟合模型：是；
- validation/test 只评价：是；
- 测试集调参：否；
- 未来信息泄漏：否；
- XQM：未使用；
- E0/E1/E2 文件：未修改；
- Phase C/D 文件：未修改；
- 复杂深度模型：未训练，仅运行固定结构诊断 baseline。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(result)} train={int(train_mask.sum())} validation={int((splits == 'validation').sum())} test={int((splits == 'test').sum())}")


if __name__ == "__main__":
    main()
