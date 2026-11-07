# VHS-NEXT-S0｜来源真实性与 physical_reference_q 血缘审计


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


## MQ的实际链路

`Q-新疆.xls` → `2005-支流/MQ-DSK-2005-SB`（B列、零基1） → `extract_multisite_runoff_2005.py`直接读取 → `physical_reference_q_m3s` → `multisite_discharge_2005.csv` → `prepare_multisite_gnn_bundle_2005.py`改名 → NPZ `x[..., physical_reference_q]` → `WindowDataset`输入、output_reference和physics_reference → 模型残差锚点/物理损失 → 与独立存放于y的DSK OQ评分。

BYBLK MQ是同sheet D列（零基3），OQ分别DSK C列、BYBLK E列；干流MQ为index11的B/C/D列，OQ为E/F/G列。干流首行表头并不明确MQ物理模型名称，不能借支流表头补造其生成机制。

证据：[scripts/extract_multisite_runoff_2005.py:159](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/extract_multisite_runoff_2005.py:159) (`raw_reference = sheet.cell_value(`); [scripts/prepare_multisite_gnn_bundle_2005.py:55](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/prepare_multisite_gnn_bundle_2005.py:55) (`"physical_reference_q_m3s": "physical_reference_q",`); [configs/multisite2005_snapshot_gnn.yaml:12](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/configs/multisite2005_snapshot_gnn.yaml:12) (`output_reference_feature: physical_reference_q`); [src/vhs/train.py:55](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/train.py:55) (`physics_mask = batch["physics_reference_mask"].bool() & target_nodes`); [src/vhs/data.py:309](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/data.py:309) (`output_reference = self.bundle.x[`)。

本轮逐单元格核对工作簿→CSV，逐float32核对CSV→NPZ，均一致。但在工作簿值**之前**，没有发现可核查生成脚本、公式、输入清单、校准年份、站点标签使用记录或参数文件。最终生成链状态：**PROVENANCE_UNVERIFIED**。不能认定为独立物理模型，也不能反向断定确有目标标签泄漏。模型可能复制MQ中的目标信息是POTENTIAL_LEAKAGE。

历史D5已明确相同阻断：[outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md)。本轮不重建MQ、不补造2011 MQ。

## obs_q与不同参考量的关系

- obs_q来自日工作簿或2005 OQ列，是监督/评分标签，同时在上游节点可作为合法输入。名称“obs”或OQ不证明它未经过供数者外部整编。
- `physical_reference_q`是2005 MQ列复制，两者不同列、不同数值并不意味着统计独立或无共同率定来源。
- `physics_area_scaled_q_lag3`由上游Q(t−3)×UP_AREA比率算得，仓库生成链可追；它不是MQ。[scripts/prepare_virtual_station_bundle.py:89](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/prepare_virtual_station_bundle.py:89) (`physical_reference = routed * area_ratio`)
- `residual_reference_q`还可由lag3上游Q加本地降水产流代理构成，不能与68河段routing或MQ合并解释。见 `scripts/prepare_residual_gnn_bundle.py`。
- E4 R1的route_daily在本地有完整计算公式与初始状态规定，但tau通过DSK训练期Q校准，因此不是strict zero-shot参考；68个相同tau构成串联水库，0.7071228027 day是**单河段**tau，非整个212.61km的实测传播时长。其总一阶平均驻留尺度约48.08435 day，不可等同洪峰延迟。
- WaterGAP的wg_dis是另一个外部模型字段，其内部目标站率定独立性UNVERIFIED。

## 数据可信度分层及缺证请求

本地复制与数值一致性已核实：1978–1983两站日流量、2005 OQ/MQ导入、E0列映射、E4B0严格滞后特征、E5A17源文件哈希。
元数据/独立性未核实：日流量官方供数者、打印单位和日界；MQ原始模型/校准及目标信息；外部月序列单位/提供者/原始变量；WaterGAP目标站校准；现代几何与历史时期对应。
向原提供者索取：原始供数说明、站号/站址沿革、单位、日统计窗口、质控及插补记录；MQ公式/脚本/参数/输入与校准清单；月序列原始供数机构、变量和单位、与日序列的关系。获取前不得将任一未知填为PASS。

最严格来源门槛尚未满足；MQ与外部月序列不得进入独立验证或Protocol C主张。可用同源日Q做带警告的回顾性开发，但本阶段并未获准执行。
