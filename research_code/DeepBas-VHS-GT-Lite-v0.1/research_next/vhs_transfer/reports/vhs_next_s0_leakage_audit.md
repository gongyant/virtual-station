# VHS-NEXT-S0｜目标站信息泄漏与协议分类


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


## 协议定义

**A Historical reconstruction**：目标站训练期Q可用于监督/校准；预测构造不能读取测试期目标标签，包括测试期更早日期的实测Q回填。
**B Temporally held-out reconstruction**：A的时间严格化；训练、开发验证、最终测试按时序，所有选择先于最终测试。历史已揭示测试不能再作为新方法盲测。
**C Strict ungauged / zero-shot**：该目标站任何时期Q都不能进入监督、校准、目标专用参数、选模或预测回填。只屏蔽x中的obs_q不足以证明C。
若研究明确允许上一日目标观测，那是观测辅助的一步预测，必须另立协议，不能混进A/B/C的缺测重建比较。

## 逐实验族判定

1. **E1 Model-0 Persistence**：[scripts/run_bd1m_baselines.py:64](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_bd1m_baselines.py:64) (`data["persistence_prediction"] = data["Q_target_dsk"].shift(1)`)
   **CONFIRMED_LEAKAGE（相对本轮A/B/C重建边界）**：全序列shift后按split评分，1983-01-02起使用1983测试期DSK Q(t−1)。这是已明示的持久性诊断，不是发现隐瞒；没有未来t+1泄漏，但不能作为无目标观测预测。首个测试日可以使用测试前历史值，不改变其后364日的结论。
2. **E2 DSK_history**：[scripts/run_bd1m_e2_temporal_memory.py:65](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_bd1m_e2_temporal_memory.py:65) (`dsk_features = build_windows(data, "Q_target_dsk")`); [scripts/run_bd1m_e2_temporal_memory.py:56](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_bd1m_e2_temporal_memory.py:56) (`data[name] = data[column].shift(lag)`)
   **CONFIRMED_LEAKAGE（同一重建边界）**：测试窗口包含测试期内t−1..t−30目标观测；仅适用于有观测的记忆诊断，不能称C或无标签A/B。
3. **E1 upstream transfer、LR/RF；E2 BYBLK_history；E3 MLP/GRU/TCN**：A、按源码固定时间切分的B式历史开发。LR/RF/神经模型使用DSK训练Q，不能C。E1训练中位数填特征；E3 scaler仅train。**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**：未发现测试目标作为这些模型输入或标准化来源。历史测试已多次揭示，不能保证后续人工决策从未使用测试；整体独立性UNVERIFIED。same-day上游Q是日末历史重建可用信息，不是日初预报信息。
4. **E1.5滞后扫描与E2分区相关**：0..30天仅为诊断；各split都报告不能用于选择新方法lag。统计相关及最大NSE不是实测传播时间。把1983最优lag拿来选模将构成泄漏，当前未找到已经这样选择的直接证据，记**POTENTIAL_LEAKAGE**。两个滞后诊断脚本都输出同名结果，不能由文件名证明唯一生成命令；源码全序列shift允许合法跨split历史，而旧某报告“不同split不借用”文字过强，应在新记录中澄清，不修改历史。
5. **E4A2 R1/R2**：A、B的训练校准步骤；[scripts/bd1m_e4a2_optimizer.py:29](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/bd1m_e4a2_optimizer.py:29) (`TRAIN_OBJECTIVE = "train RMSE only, 1978-01-01..1981-12-31"`)。训练DSK进入RMSE目标，不能C。检查train-only输入映射1461日、无1982/1983参与fit；**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**，限可见源码/注册文件。
6. **E4B1/B2A/B2B/B2C、Fourier6**：A及B式开发，目标是train的DSK减routing残差，1982用于开发选模，LOYO在开发范围内。[scripts/run_bd1m_e4b1_incremental_residual.py:306](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_bd1m_e4b1_incremental_residual.py:306) (`model.fit(`); `e4b3_method_freeze.json`。不能C。t−1增量气象5字段已独立重算；未见测试标签进入这些特征。不能把修正项解释为观测证实的侧向流量。
7. **E4C**：冻结方法下B式固定1983评价。读取冻结tau及Fourier系数，1978一次初始化、连续推进，不使用DSK测试流量重置。[scripts/run_bd1m_e4c_fixed_1983_holdout.py:643](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_bd1m_e4c_fixed_1983_holdout.py:643) (`initialize_steady_state(`); [outputs/vhs_bd1m/experiments/e4c_1983_holdout_report.md](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/vhs_bd1m/experiments/e4c_1983_holdout_report.md)。**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**；没有重算此实验。本轮不能证明历史执行文件与当前源码逐字相同；E5A登记结果源17/17哈希匹配。E1–E3已报告1983，因此E4的“固定方法”身份应与全球从未查看过的盲测严格区分。
8. **E4D**：冻结预测的外部月一致性评分，承接A/B训练的模型；未知单位及来源，独立性**UNVERIFIED / POTENTIAL_LEAKAGE**，不属于C或官方独立验证。
9. **2005五站snapshot GNN/no-graph**：设计为整站留出，DSK OQ从训练标签及全窗口x排除，早停evaluate(target_only=False)只用非目标站；scaler只用训练前缀。[src/vhs/train.py:94](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/train.py:94) (`# target_only=False：只评价非目标站，用于模型选择和早停`); [src/vhs/data.py:134](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/data.py:134) (`train_x[:, target_mask, flow_idx] = np.nan`); [src/vhs/data.py:254](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/data.py:254) (`availability[:, self.target_node_mask, self.flow_idx] = 0.0`)
   当前源码直接标签路径为**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**；合成扰动验证global/station_reference两模式目标obs及非训练数据改变不影响scaler，目标obs/availability确实遮蔽。但是目标MQ保持为输入、归一化参考、残差锚点和训练physics loss，MQ生成链未知，故**POTENTIAL_LEAKAGE**，不能认证C。历史checkpoint是否正由当前代码构造**UNVERIFIED**；未训练或载入checkpoint推理。
10. **早期1978–1983 holdout_dsk/mainline STGNN**：与五站2005不是同一图。基础NPZ含34站，许多站无Q；遮蔽机制见当前data.py，wg_dis外部校准独立性未知。属于C设计意图但严格C**UNVERIFIED**，不凭配置命名批准。
11. **calibrated_residual、Stage C P1**：使用DSK训练期Q拟合线性/残差校正，A，不能C；2005既有test被标作legacy diagnostic而非盲测。Stage C的P2分支即使不监督目标也仍受MQ来源限制；见 `scripts/run_stage_c_boundary_lag_residual.py` 与 `evaluate_calibrated_residual.py`。
12. **D5 round2 M1/M2与round4 M2R/M2C**：A的回顾性嵌套LOYO，不是B，因为留出较早年份时会训练于其后的年份；同一DSK其他年份Q参与拟合，不能C。未见目标Q作预测时状态重置；状态用上游Q预热。round3用全部六年残差筛选weather，包含各外层测试年DSK信息，round4继承此选择。**CONFIRMED_LEAKAGE（特征选择对外层独立评估的污染）**，历史报告已明确承认，故其开发性结果本身可保留；禁止包装成完全独立nested test。[outputs/diagnosis_2005_snapshot/stage_d5_round4/candidate_selection_report_zh.md:18](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5_round4/candidate_selection_report_zh.md:18) (`候选产生和筛选明确属于`development_diagnostic_only`。同一批1978—1983数据同时参与了候选诊断，存在多重筛选与赢家偏差；第四轮外层年份不具备完全独立的特征选择身份，结果不得称为无偏外部评价。`)

## 检查项总答

- 原始Q本地加工无插补；供数前处理UNVERIFIED。模型缺特征用train中位数或NaN+availability，不等于目标Q未来插补。
- 已查train/global/station_reference、E3 scaler、D5 weather fold scaler，未见全时期目标scaler；全部历史脚本所有路径未穷举，不能宣布全项目零泄漏。
- 未查到E4测试目标状态重置；上游实测日平均输入可合法用于日末重建，跨split合法历史不是目标标签泄漏。
- 图消息输入目标obs被当前代码屏蔽；隐藏共享MQ来源及WaterGAP率定不能由屏蔽证明无泄漏。
- 历史“future_information_leakage=False”在E0生成器为常量赋值，旧单测只断言此标志，证据不足。本轮增加真实赋值链核查与合成扰动，仍保持范围限定。

完整分类机读版见 `evaluation/protocol_classification.json`。确认事项均注明违规所相对的协议，不把允许的训练监督误称泄漏，不把未知来源断言为已确认泄漏。
