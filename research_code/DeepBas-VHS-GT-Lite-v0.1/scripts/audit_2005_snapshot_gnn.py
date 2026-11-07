from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.metrics import regression_metrics


ROOT = Path("outputs/virtual_station_mainline/multisite_2005")
OUT = Path("outputs/diagnosis_2005_snapshot")
DATA = Path("data/processed/virtual_station_multisite")
SEEDS = [7, 42, 123]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def prediction(path: Path, name: str) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame[["date", "observed", "predicted"]].rename(
        columns={"observed": "observed_q", "predicted": name}
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    graph_metrics = {seed: read_json(ROOT / f"snapshot_gnn_seed{seed}" / "test_metrics.json") for seed in SEEDS}
    no_graph_metrics = {seed: read_json(ROOT / f"snapshot_nograph_seed{seed}" / "test_metrics.json") for seed in SEEDS}
    edge_metrics = {seed: read_json(ROOT / f"snapshot_gnn_seed{seed}" / "edge_ablation.json") for seed in SEEDS}

    discharge = pd.read_csv(DATA / "multisite_discharge_2005.csv", parse_dates=["date"])
    physical = discharge.loc[
        discharge.station_id.astype(str).eq("00705700")
        & discharge.date.between("2005-09-01", "2005-10-31"),
        ["date", "observed_q_m3s", "physical_reference_q_m3s"],
    ].rename(columns={"observed_q_m3s": "observed_q", "physical_reference_q_m3s": "physical_q"})
    physical_metrics = regression_metrics(physical.observed_q, physical.physical_q)

    predictions = physical.copy()
    for seed in SEEDS:
        graph = prediction(ROOT / f"snapshot_gnn_seed{seed}" / "test_predictions.csv", f"directed_gnn_q_seed{seed}")
        no_graph = prediction(ROOT / f"snapshot_nograph_seed{seed}" / "test_predictions.csv", f"no_graph_q_seed{seed}")
        predictions = predictions.merge(graph.drop(columns="observed_q"), on="date", how="inner")
        predictions = predictions.merge(no_graph.drop(columns="observed_q"), on="date", how="inner")
    predictions["directed_gnn_q"] = predictions[[f"directed_gnn_q_seed{s}" for s in SEEDS]].mean(axis=1)
    predictions["no_graph_q"] = predictions[[f"no_graph_q_seed{s}" for s in SEEDS]].mean(axis=1)
    ordered = ["date", "observed_q", "physical_q", "no_graph_q", "directed_gnn_q"]
    ordered += [f"no_graph_q_seed{s}" for s in SEEDS] + [f"directed_gnn_q_seed{s}" for s in SEEDS]
    predictions[ordered].to_csv(OUT / "reproduced_predictions.csv", index=False, date_format="%Y-%m-%d")

    rows = [{"model": "physical_reference", "seed": "fixed", **physical_metrics}]
    for seed in SEEDS:
        rows.append({"model": "directed_snapshot_gnn", "seed": seed, **graph_metrics[seed]})
        rows.append({"model": "independent_no_graph", "seed": seed, **no_graph_metrics[seed]})
    for label, metrics_by_seed in [("directed_snapshot_gnn_seed_metric_mean", graph_metrics), ("independent_no_graph_seed_metric_mean", no_graph_metrics)]:
        row = {"model": label, "seed": "mean"}
        for key in ["n", "rmse", "mae", "pbias", "nse", "kge", "corr"]:
            row[key] = float(np.mean([values[key] for values in metrics_by_seed.values()]))
        rows.append(row)
    rows.append({"model": "directed_snapshot_gnn_daily_ensemble_mean", "seed": "mean_prediction", **regression_metrics(predictions.observed_q, predictions.directed_gnn_q)})
    rows.append({"model": "independent_no_graph_daily_ensemble_mean", "seed": "mean_prediction", **regression_metrics(predictions.observed_q, predictions.no_graph_q)})
    pd.DataFrame(rows).to_csv(OUT / "reproduced_metrics.csv", index=False)

    graph_nse_mean = np.mean([value["nse"] for value in graph_metrics.values()])
    graph_rmse_mean = np.mean([value["rmse"] for value in graph_metrics.values()])
    graph_kge_mean = np.mean([value["kge"] for value in graph_metrics.values()])
    no_graph_nse_mean = np.mean([value["nse"] for value in no_graph_metrics.values()])
    no_graph_rmse_mean = np.mean([value["rmse"] for value in no_graph_metrics.values()])
    no_graph_kge_mean = np.mean([value["kge"] for value in no_graph_metrics.values()])
    edge_mean = np.mean([value["nse_edge_contribution"] for value in edge_metrics.values()])

    report = f"""# 2005年同日快照有向GNN阶段A审计与复现

## 1. 找到的实验文件

- 主运行入口：`src/vhs/train.py`，命令为 `python -m vhs.train --config <配置文件>`。
- 种子42配置：`configs/multisite2005_snapshot_gnn.yaml`、`configs/multisite2005_snapshot_nograph.yaml`。
- 种子7/123配置：`outputs/virtual_station_mainline/multisite_2005/generated_configs/` 下四个对应YAML。
- 原始输入：`data/raw/runoff/Q-新疆.xls`，工作表 `2005-支流` 与 `2005-干流`。
- 数据提取：`scripts/extract_multisite_runoff_2005.py`。
- 张量包构建：`scripts/prepare_multisite_gnn_bundle_2005.py`。
- 张量输入：`data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz`。
- 节点/边：`multisite_stations_2005.csv`、`multisite_edges_2005.csv`。
- 数据集、遮蔽与标准化：`src/vhs/data.py`。
- 图构建：`src/vhs/graph.py`。
- 模型：`src/vhs/model.py` 中 `DirectedSnapshotGNN` 与 `DirectedMessageLayer`。
- 损失、训练、早停和预测：`src/vhs/train.py`。
- 指标：`src/vhs/metrics.py`。
- 汇总：`scripts/summarize_teacher_aligned_snapshot_round.py`。
- 原输出：各 `snapshot_gnn_seed*`、`snapshot_nograph_seed*` 目录中的模型、JSON、CSV与训练历史，以及 `teacher_aligned_snapshot_round` 汇总。

## 2. 任务、节点和有向边

- 目标站：大山口（DSK），站号 `00705700`。
- 全部节点（固定顺序）：巴音布鲁克 `00705600`、大山口 `00705700`、阿拉尔 `TARIM_ALAR`、新其满 `TARIM_XQM`、阿其克 `TARIM_AQK`。
- 有向边：`00705600 -> 00705700`；`TARIM_ALAR -> TARIM_XQM`；`TARIM_XQM -> TARIM_AQK`。
- 后两条属于另一个互不连通的塔里木干流分量；其中 XQM→AQK 是折叠路径，不代表两站直接相邻。
- 边特征：原边表虽有BYBLK→DSK距离212.61 km，但构包时只传入 source/target，三条边均赋单位属性 `[1]`；训练前标准化后全部变成 `[0]`。因此模型没有距离、坡度、传播时间或边类型差异，只学习一个共享的常数门。

## 3. 实际协变量

每个节点的动态字段原始名称只有 `obs_q` 和 `physical_reference_q`。数据集随后为每个字段拼接一个可用性标志，所以网络动态输入实际为4维：标准化观测流量、标准化MQ参考流量、观测流量可用标志、MQ参考可用标志。

静态输入为5维：`node_order_scaled`、`component_kaidu`、`component_tarim`、`log_upstream_area`、`area_available`。只有BYBLK和DSK具有真实汇水面积；三个塔里木节点的面积缺失并填0，同时用 `area_available=0` 标记。

目标变量是各节点同日实测流量 `obs_q`（m³/s）。训练数据损失只使用非目标节点标签；验证早停也只使用非目标节点。DSK标签仅用于最终验证/测试评分。

## 4. physical的准确含义和公式边界

本轮DSK的 `physical_reference_q(t)` 不是本仓库现场计算出的Manning、汇水面积比例或时滞传播结果，而是直接读取 `Q-新疆.xls` 中 `2005-支流` 工作表的 `MQ-DSK-2005-SB` 列。仓库没有提供MQ生成模型或计算公式，因此不能从现有代码继续断言其外部物理机理。

本仓库内可精确写出的预测公式是：

`q_hat_norm_i(t) = q_MQ_norm_i(t) + 0.25 * tanh(decoder(h_i(t)))`

随后以该站 `-y_mean/y_std` 为下限截断，反标准化得到非负流量。训练时还增加：

`loss = MSE(非目标节点预测, 非目标节点观测) + 0.05 * MSE(DSK预测, DSK的MQ参考)`。

本快照配置本身没有使用汇水面积比例，也没有使用传播时滞。面积只以DSK/BYBLK静态节点属性进入编码器；它没有进入MQ计算。模型不使用DSK历史流量或水位，也没有任何水位字段。

## 5. 遮蔽、缺失值和标准化

- DSK的 `obs_q` 在所有输入时刻强制置0，其可用标志也置0；DSK的MQ参考不遮蔽，继续作为输入和输出锚点。
- 训练损失明确排除DSK实测标签。训练与验证还以0.35概率随机遮蔽具有入边的非目标节点，作为节点缺测增强。
- 其他NaN先标准化，再用0替换，同时对应可用性标志为0；没有时间插值或前向填充。
- 动态特征采用“逐站、逐特征、仅训练期”标准化。DSK观测流量在拟合统计量前被设为NaN，最终使用均值0、标准差1占位。
- 目标流量的反标准化均值/标准差不是来自观测Q，而是逐站MQ参考在训练期的均值/标准差。
- 静态特征在五个节点之间按特征全局标准化。

## 6. 时间划分和同日信息

- 张量日期：2005-01-02至2005-10-31，共303天；由于 `history=1`，索引从第二个张量日开始。
- 训练：2005-01-03至2005-06-30。
- 验证：2005-07-01至2005-08-31，共62天。
- 测试：2005-09-01至2005-10-31，共61天。
- 测试只有61天，是因为验证截止日固定为8月31日，而张量在10月31日结束，剩余恰好61个日历日；不是随机抽取61天。
- “同日快照”表示模型完全没有GRU/LSTM和历史窗口，只读取时刻t的五节点状态。
- 图模型确实把BYBLK同日流量作为上游节点状态，经 `BYBLK -> DSK` 边传到DSK；但没有把它写成水量边界公式，也没有传播时滞。即它使用同日上游信息预测同日下游流量，而不是 `Q_up(t-lag)`。

## 7. 有向快照GNN与独立无图模型

有向快照GNN先分别编码同日五个节点，再沿三条有向边进行一层上游→下游消息传递，最后对每个节点解码MQ残差。对DSK而言，唯一图消息来自BYBLK。

独立无图模型保持相同输入、节点编码器、解码器、MQ残差锚点、损失、遮蔽、时间划分和训练参数，但设置 `graph_layers=0`，完全删除消息传递层。各节点仍共享同一个编码器和解码器，所以它不是五个完全独立的模型。

## 8. 原配置复现结果

| 方法 | NSE | RMSE (m³/s) | KGE |
|---|---:|---:|---:|
| MQ physical reference | {physical_metrics['nse']:.6f} | {physical_metrics['rmse']:.4f} | {physical_metrics['kge']:.6f} |
| 有向快照GNN（三种子指标均值） | {graph_nse_mean:.6f} | {graph_rmse_mean:.4f} | {graph_kge_mean:.6f} |
| 独立无图（三种子指标均值） | {no_graph_nse_mean:.6f} | {no_graph_rmse_mean:.4f} | {no_graph_kge_mean:.6f} |
| 同一有向模型删除边的NSE贡献均值 | {edge_mean:.6f} | — | — |

逐种子结果和逐日预测分别见 `reproduced_metrics.csv` 与 `reproduced_predictions.csv`。逐日文件中的 `directed_gnn_q` 和 `no_graph_q` 是三个种子的逐日算术均值，同时保留六个种子级预测列。

## 9. 损失函数与随机种子复现性

数据损失为标准化空间MSE；物理锚定损失权重0.05；AdamW学习率0.001、权重衰减0.0001、梯度范数裁剪1.0，最多100轮，以非目标节点验证MSE早停15轮。

随机种子7、42、123均设置Python、NumPy、PyTorch和CUDA种子。本次在同一CUDA环境重跑后复现了报告数值，仅存在约1e-8量级浮点差异。代码没有显式启用 `torch.use_deterministic_algorithms` 或cuDNN确定性开关，因此可以称为同环境数值可复现，不能保证跨硬件/跨PyTorch版本逐位完全一致。

## 10. 最可能导致边性能下降的三个问题（仅诊断假设，未进入阶段B）

1. **边没有水动力含义且时间对齐错误。** 三条边标准化后属性全为0，没有距离、坡度、旅行时间；BYBLK(t)被直接用于DSK(t)，而212.61 km河段很可能需要非零传播时滞。
2. **图消息层引入额外变换，但DSK已经拥有强MQ锚点。** DSK的MQ参考本身NSE约0.362；消息层通过残差和LayerNorm改变隐藏态，学习到的同日BYBLK消息可能把解码残差推离MQ，且三种子删边实验均改善NSE。
3. **两个不连通流域共用同一消息参数和训练目标。** 早停与数据损失只看非目标节点，且塔里木分量样本期更长、量级和过程不同；共享的唯一消息层可能主要适配ALAR→XQM→AQK，而不是BYBLK→DSK。模型选择并未直接以DSK性能为准。

## 阶段A停止点

本报告只完成定位、原样复现和诊断。未修改核心模型、图结构、数据划分、超参数或随机种子；等待确认后再决定是否进入下一阶段。
"""
    (OUT / "audit_2005_snapshot_gnn.md").write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()

