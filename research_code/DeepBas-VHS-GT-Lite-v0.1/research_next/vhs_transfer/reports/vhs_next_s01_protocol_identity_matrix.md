# VHS-NEXT-S0.1｜协议信息边界与历史模型身份独立对照表


阶段：VHS-NEXT-S0.1 — P0 Resolution and Scientific Experiment Readiness。
日期：2026-10-11，Asia/Singapore。项目根目录：`E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
本轮仅针对S0已定位证据核查、元数据/历史使用可行性和协议设计。未进行真实模型训练、调参、真实预测重跑、GPU任务、S1A实验或E5I1。
`CONFIRMED`仅确认指定事实；来源复制确认不等于物理独立性确认。所有未证实事项保持未证实。

## 已有证据（继承S0，不算本轮发现）

S0已经确认R1/R2/Fourier6使用目标站训练标签、2005目标MQ不独立、E1/E2目标历史输入及D5筛选限制。本轮不重新评价旧性能。

## 本轮新增核查或设计

| 信息/用途 | Protocol A 历史重建 | Protocol B 时间留出重建 | Protocol C strict ungauged/zero-shot |
|---|---|---|---|
| 目标站训练期Q | 允许监督及已声明校准 | 允许，仅早于开发/测试 | 禁止所有时期目标Q参与拟合/归一化/选模 |
| 目标站开发验证Q | 允许评分/开发选择，之后失去最终测试身份 | 允许在最终测试前开发选模 | 禁止目标站Q用于模型选择；仅source站验证 |
| 目标站测试Q | 只在冻结后评分 | 只在模型/代码冻结后一次评分 | 只在全部source训练/选择冻结后评价 |
| 测试期更早日期目标Q回填 | 禁止（不属于本轮缺测重建） | 禁止 | 禁止 |
| 目标站历史参数校准 | 允许但必须标明 | 允许仅训练期，不能用未来dev/test隐式校准 | 禁止目标专用Q校准参数/查表及其派生量 |
| 来源站训练数据 | 允许并记录使用范围 | 允许，按预先规定的时间边界 | 允许，source与target严格隔离 |
| 物理参考流量 | 生成链可核查，若含目标监督须计入A | 不能含测试信息，历史校准限train | 只能独立来源/合法source参数；未知MQ不可接受 |
| 上游观测 | 依声明制度及时间戳可用 | 同上；不能借目标未来修正 | 同上；上游不等于目标标签 |
| 气象信息 | 依时间可用性；后验再分析需标明 | 不含目标未来；forecast与reanalysis分层 | 合法独立气象可用，不能代入含目标Q的派生量 |
| 静态流域属性 | 允许，说明来源和历史代表性 | 同上，禁止用测试Q反推“静态参数” | 允许独立静态属性，禁止目标Q导出的目标专用参数 |
| 统计拟合/标准化范围 | 明确train，不使用最终评分标签 | 每个时间train折，完整feature selection也必须先于test | source训练范围；不能使用target Q统计量 |


| 历史实验 | 实际身份（独立新表，不改旧名称） | 不可作出的主张 |
|---|---|---|
| E4 R1/R2 | A目标监督校准；E4A2只拟合1978–1981 | 不能C；旧tau不能当所有新外层折均未见目标 |
| Fourier6/月残差 | A目标残差监督，1982开发；E4C为冻结方法B式1983评价 | 不能C；不能再把已揭示1983给新方法当盲测 |
| 2005五站snapshot GNN/no-graph | 整站留出C设计意图，当前可见OQ路径遮蔽，但保留目标MQ | C未认证；不能把MQ复制源当独立物理源 |
| 早期1978–1983 base-bundle STGNN | 34站输入、目标遮蔽设计；wg_dis外部率定独立性未核实 | 不能自动认证C，也不能等同68河段图 |
| E1 persistence/E2 DSK_history | 目标观测辅助诊断，测试内过去Q作预测输入 | 不符合此表A/B/C缺测重建；不是无目标观测基线 |
| E1目标监督LR/RF、E2 BYBLK历史、E3 | A，源码按时间分区的历史开发 | 不是C；历史test揭示不能撤销 |
| Stage C P1/D5 M1/M2/M2R/M2C | A目标监督；D5为回顾性LOYO，部分折有未来训练年 | 不是时序B，不是C；M2C全六年筛选不能当独立外层选择 |
| 新S1A-0/1 | A下的按时序折开发，RETROSPECTIVE_DEVELOPMENT_ANALYSIS | MQ-free不是C；不称INDEPENDENT_FINAL_TEST |


A是历史重建的信息约束；B进一步要求严格时序和未揭示最终测试，不是“目标站不能有训练标签”。C是目标站标签/目标Q校准完全隔离，不能通过参数、参考锚点或scaler间接绕过。
现有GNN源码训练target mask证据：[src/vhs/data.py:134](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/data.py:134)；早停用非目标节点：[src/vhs/train.py:94](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/train.py:94)；目标MQ训练约束：[src/vhs/train.py:55](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/train.py:55)。源码路径检查继承S0，不证明历史checkpoint版本绑定或MQ独立。

## 仍未解决

MQ与wg_dis内部校准来源、正式目标站编号和真正新最终测试仍未解决。当前源码的正确遮蔽不能替代对整个信息生成链的证明。

## 对后续实验的影响

S1A不需要先把所有历史分支变成C；应使用清晰A/开发身份执行受限主比较。B最终测试与C认证分别设门槛；不改历史模型名称，不把三个分支强制一起通过。
