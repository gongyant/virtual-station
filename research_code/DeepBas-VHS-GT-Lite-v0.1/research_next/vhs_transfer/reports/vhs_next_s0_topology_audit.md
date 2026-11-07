# VHS-NEXT-S0｜拓扑、传播与不可比设置


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


## 设置1：2005五站有向图

- 5个站点节点：BYBLK/00705600、DSK/00705700、ALAR/TARIM_ALAR、XQM/TARIM_XQM、AQK/TARIM_AQK；3条有向边，2个弱连通分量（2站开都河、3站塔里木）。实际NPZ边0→1、2→3、3→4，无环；不是跨流域连边。
- BYBLK→DSK 212.61 km；另外两条塌缩边的距离缺证。`prepare_multisite_gnn_bundle_2005.py`主动丢弃距离，实际edge_attr全部1，仅拓扑；不能当作米或公里。
- BYBLK/DSK为2005-05-01至10-31各184日；其他三站01-02至10-28各300日；合并303日，不同站有缺窗。
- snapshot history1用当日非目标站OQ与所有节点MQ，history current_snapshot=True；2005-06-30 train截止、08-31 validation截止，之后test。损失用非目标站，MQ在目标仍保留。没有显式物理库容递推或测定时滞；C设计未经MQ血缘认证。
- 方向来自项目边及文献顺序声明；本轮复核本地边/张量一致，未重新进行塔里木野外站址或文献验证，collapsed边并非三个连续实体河段。

证据：[data/processed/virtual_station_multisite/multisite_edges_2005.csv](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/data/processed/virtual_station_multisite/multisite_edges_2005.csv)；[scripts/prepare_multisite_gnn_bundle_2005.py:69](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/prepare_multisite_gnn_bundle_2005.py:69) (`topology_edges = edges[["source", "target"]].copy()`); [configs/multisite2005_snapshot_gnn.yaml](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/configs/multisite2005_snapshot_gnn.yaml)。

## 设置2：BYBLK→DSK 68河段

- 两个有观测Q的站点，68个HydroRIVERS河段空间单元，67条链内边，1个弱连通分量；顺序1..68全部对应上游→下游。
- 本轮直接重读原始DBF：匹配68/68，链内67条NEXT_DOWN无矛盾；总LENGTH_KM=212.61。最后包含河段40282031→DSK匹配河段40282189；后者是终点边界，不是第69个被路由库容。没有靠历史PASS标志代替核查。
- 日Q 1978–1983；首端当日Q作为边界，终端DSK作train校准/评价。68河段无逐河段Q标签；气象仅流域或增量流域，不是68份独立观测。
- R1为68个相同tau串联，R2为68个由L/S/W共享四参数生成的tau。初始S_i=tau_i×首日上游Q；日内Euler，原生接口外步固定1day；无侧向、取水、显式闸门或回水方程。
- 1978–1981 train、1982开发、1983原冻结方法评价；R1/R2使用DSK训练期标签，A/B而非C。

## 另一套早期图

`real_bundle.npz`实际含34个站节点，动态wg_dis/obs_q，仅BYBLK/DSK有1978–1983观测，许多其他节点只有外部模型流量。`holdout_dsk_graph1`/`mainline_formal_graph`不能自动归入2005五站设置，更不能等同68河段库容图。实际station_ids/edge_index见live_audit_facts.json。

## 不能直接比较的结果

2005 snapshot GNN vs 1978–1983 R1/R2：年份、站点/空间单元、输入MQ、标签监督与容量均不同。五站图局部性能降低不能证明68河段图负迁移，更不能证明GNN普遍失败。
R2约0.047227%改善是训练目标在该参数化的微小差异，不是独立测试图贡献，也不证明河道异质性没有物理作用。
D5 M1/M2为单路径统计传递与宏平均嵌套LOYO；E4为固定时序与68库容；参数、预热、有效日和监督范围不同，不能直接比较NSE认定某结构优越。
E1 persistence/E2目标历史窗使用额外目标观测，不能与无目标Q模型作同信息比较。外部月结果也不能与逐日结果直接排序。
