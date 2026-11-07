"""Audit E3 static identifiability and build the reach-level graph asset."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
AUDIT_INPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
E3_SCRIPT = ROOT / "scripts/run_bd1m_e3_dynamic_physical.py"
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
PHYSICAL = ROOT / "outputs/vhs_bd1m/bd1m_physical_feature_table.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
IDENTIFIABILITY = EXPERIMENT_DIR / "e35_static_feature_identifiability.csv"
REPORT = EXPERIMENT_DIR / "e35_e3_interpretation_report.md"
NODES = ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv"
EDGES = ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_edges.csv"
STATIC = ["length_km", "elevation_drop_m", "mean_slope", "median_slope", "width_m"]


def main() -> None:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    audit = pd.read_csv(AUDIT_INPUT)
    physical = pd.read_csv(PHYSICAL, dtype={"reach_id": str})
    freeze = pd.read_csv(FREEZE, dtype={"reach_id": str, "upstream_id": str, "downstream_id": str})

    train = audit[audit["split_candidate"] == "train"]
    e3_source = E3_SCRIPT.read_text(encoding="utf-8")
    mlp_uses_static = "MLP(WINDOW * len(DYNAMIC))" not in e3_source
    rows = []
    for feature in STATIC:
        values = audit[feature].dropna().to_numpy(dtype=float)
        train_values = train[feature].dropna().to_numpy(dtype=float)
        standardized = (train_values - train_values.mean()) / (train_values.std() or 1.0)
        rows.append(
            {
                "feature": feature,
                "unique_count": int(pd.Series(values).nunique()),
                "train_variance": 0.0 if np.ptp(train_values) < 1e-10 else float(np.var(train_values, ddof=0)),
                "train_std": 0.0 if np.ptp(train_values) < 1e-10 else float(np.std(train_values, ddof=0)), 
                "standardized_unique_count": int(pd.Series(standardized).nunique()),
                "used_by_mlp": mlp_uses_static,
                "used_by_lstm": True,
                "used_by_tcn": True,
                "identifiable_in_single_path_time_series": False,
                "notes": "路径级摘要在所有日期恒定；单一路径时间序列不能识别其日期变化贡献。",
            }
        )
    pd.DataFrame(rows).to_csv(IDENTIFIABILITY, index=False)

    node_columns = [
        "reach_id", "river_id", "order", "length_km", "elevation_drop_m",
        "mean_slope_m_per_m", "median_slope_m_per_m", "width_m", "sword_reach_id",
        "path_source", "slope_source", "width_source", "width_version",
    ]
    nodes = physical[node_columns].copy()
    nodes = nodes.rename(columns={"order": "reach_order"})
    nodes["spatial_unit"] = "HydroRIVERS reach"
    nodes["physical_feature_source"] = str(PHYSICAL.relative_to(ROOT)).replace("\\", "/")
    nodes.to_csv(NODES, index=False)

    ordered = freeze.sort_values("order").reset_index(drop=True)
    edge_rows = []
    for index in range(len(ordered) - 1):
        upstream = ordered.loc[index]
        downstream = ordered.loc[index + 1]
        edge_rows.append(
            {
                "edge_id": f"{upstream.reach_id}->{downstream.reach_id}",
                "source_reach_id": upstream.reach_id,
                "target_reach_id": downstream.reach_id,
                "source_order": int(upstream["order"]),
                "target_order": int(downstream["order"]),
                "edge_type": "NEXT_DOWN_frozen",
                "edge_source": str(FREEZE.relative_to(ROOT)).replace("\\", "/"),
                "topology_check": "PASS" if upstream.downstream_id == downstream.reach_id else "FAIL",
            }
        )
    edges = pd.DataFrame(edge_rows)
    edges.to_csv(EDGES, index=False)

    node_ids = set(nodes.reach_id)
    edge_ids = set(edges.source_reach_id) | set(edges.target_reach_id)
    order_ok = ordered["order"].tolist() == list(range(1, len(ordered) + 1))
    topology_ok = bool((edges["topology_check"] == "PASS").all())
    graph_ready = len(nodes) == 68 and len(edges) == 67 and node_ids == set(ordered.reach_id) and edge_ids <= node_ids and order_ok and topology_ok
    report = f"""# VHS-BD1M Phase E3.5 物理可识别性与 reach 图资产审计

## 最终状态

- `E3_STATIC_FEATURES_TEMPORALLY_IDENTIFIABLE=false`
- `MLP_ACTUALLY_USED_STATIC_FEATURES={'true' if mlp_uses_static else 'false'}`
- `REACH_GRAPH_ASSET_READY={'true' if graph_ready else 'false'}`
- `READY_FOR_COMPLEX_GNN=false`

## A. E3 静态特征可识别性

输入：`{AUDIT_INPUT.relative_to(ROOT)}`

```text
{IDENTIFIABILITY.relative_to(ROOT)}
```

五个 D0 路径级静态摘要在单一 BYBLK→DSK 案例的时间序列中均为常数：

- 时间维 unique count 为 1；
- train variance 为 0；
- train std 为 0；
- train 标准化后仍只有 1 个 unique 值，标准化值为 0（脚本中对零标准差使用数值保护，不产生变化）。

因此它们不能在当前单一路径时间序列中提供可识别的日期间变化贡献。它们可以作为该路径的元数据或固定边界条件，但不能凭 E3 结果证明 slope、width 或 length 改善了跨日期预测。

### E3 模型实际使用情况

脚本：`{E3_SCRIPT.relative_to(ROOT)}`

- MLP：实际输入是展平后的 30 日动态序列，构造为 `MLP(WINDOW * len(DYNAMIC))`；没有把 static tensor 传入 MLP。因此 `used_by_mlp=false`。
- LSTM：head 接收 LSTM 最后状态与 static tensor 拼接，因此代码层面使用了静态特征；但静态特征在本案例中恒定，时间维上不可识别。
- Temporal CNN：head 接收卷积序列表示与 static tensor 拼接，因此代码层面使用了静态特征；同样不具有当前时间序列中的变化信息。

## B. E3 结果的正确解释

### 1. Dynamic temporal information

`Q_input_byblk`、30 日 BYBLK 历史窗口和目标日前的 ERA5-Land 前期降水/温度窗口随日期变化，E3 主要检验的是这些动态时间信息与 DSK Q 的关系。

### 2. Path-level constant physical descriptors

`length_km`、`elevation_drop_m`、`mean_slope`、`median_slope`、`width_m` 是将 68 个 reach 汇总后的单一路径摘要。在 E3 数据集中，它们对每个日期相同；因此即使 LSTM/T-CNN 的代码接收了它们，也不能从当前案例识别其跨日期贡献。

### 3. Reach-level spatial physical heterogeneity

68 个 reach 的长度、坡度、宽度和高程变化构成空间异质性。该信息没有在 E3 的单行路径级输入中以 68 个 spatial unit 的形式表达；要分析它，需要 reach-level graph 或 sequential routing asset，而不是继续把路径摘要输入同一时间序列模型。

因此，E3 不应被描述为已经证明 slope / width / length 改善 DSK 预测。更准确的表述是：E3 评估了动态输入，并在代码层面对 LSTM/T-CNN 暴露了路径级静态摘要；这些摘要在单一路径时间维上是不可识别常数。

## C. reach-level graph asset

输出：

- 节点：`{NODES.relative_to(ROOT)}`
- 边：`{EDGES.relative_to(ROOT)}`

图结构检查：

- reach 节点数：{len(nodes)}，要求 68；
- 有向边数：{len(edges)}，要求 67；
- 顺序：上游 `order=1` 到下游 `order=68`；
- `NEXT_DOWN` 拓扑检查：`{'PASS' if topology_ok else 'FAIL'}`；
- order 连续性：`{'PASS' if order_ok else 'FAIL'}`；
- 环：无；严格按递增 order 构造，因此为 DAG；
- 断裂：`{'无' if graph_ready else '需复核'}`。

每个 HydroRIVERS reach 是一个 spatial unit。节点至少保留 reach ID、order、length、elevation drop、mean/median slope 和 width，并保留来源字段。

## D. 动态 forcing 的空间边界

当前没有 reach-level ERA5 forcing。本阶段没有把 BYBLK basin-mean P/T 复制到 68 个 reach，也没有声称其为空间气象特征。

- reach physical features：空间变化的静态状态；
- BYBLK Q 与 basin-level antecedent P/T：graph-level / boundary / global forcing；
- 未使用 XQM。

## E. 下一阶段候选方案（不训练）

### 方案 1：Physics-aware routing network

`Q_BYBLK(t) → sequential 68-reach routing → Q_DSK(t)`

每个 reach 的 routing 参数可由 length、slope、width 进行约束或参数化。应优先使用低容量、可解释的逐 reach 传输结构，避免把 68 个 reach 当成可自由拟合的独立深层参数。

### 方案 2：Directed temporal graph network

使用 68-reach 有向图、reach static features、BYBLK boundary flow 和 basin-level meteorological forcing，预测下游 DSK。当前只有一个上下游案例，reach-level latent states 没有直接观测，因此模型容量必须保持低；不建议直接使用 68 节点深 GNN，以免产生不可识别的 latent dynamics。

## 约束

- 未训练新模型；
- 未调参；
- 未修改 E0–E3 已有结果；
- 未修改冻结路径；
- 未复制气象变量到 68 个 reach；
- 未添加 XQM。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"static_features={len(rows)} nodes={len(nodes)} edges={len(edges)} graph_ready={graph_ready}")


if __name__ == "__main__":
    main()
