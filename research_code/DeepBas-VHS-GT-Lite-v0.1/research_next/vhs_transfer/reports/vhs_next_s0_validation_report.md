# VHS-NEXT-S0｜中文最终验证报告


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


## 1. 审计文件及证据

机器读取/索引866项资产，重点深读三个runoff工作簿与导入/张量化代码、E0数据集、五站图和68河段图、E4A–E4D协议与脚本、E5A登记、E5I0状态、D5 round2/3/4代码及来源/选模审计。机器清单不等同全部逐篇精读。
`data_audit/source_manifest.json`记录绝对路径/哈希/大小，`code_evidence.txt`记录路径和行号，`live_audit_facts.json`包含原始值到衍生字段的实际检查。专题报告保存可点击核心代码证据。没有仅凭旧PASS或脚本名宣布通过。

## 2. 数据来源风险

日流量4382站日加工一致，无项目层目标插补/平滑；供数者、打印单位、日界仍需补证。MQ原工作簿→CSV→tensor链已确认，生成链**PROVENANCE_UNVERIFIED**。外部月序列与日序列独立性/单位/官方来源未知。WaterGAP目标校准独立性未知；ERA5-Land本地时间和单位链可检查，未重跑大规模原始网格流程。

## 3. 已确认及潜在泄漏

已确认：E1 persistence/E2 DSK_history在无目标测试Q的重建边界下读取过去测试目标；D5 M2C的候选天气特征在全六年目标残差上筛选，外层不是独立特征选择评估。这些历史记录已注明诊断/开发身份，不被本轮改写。
未确认但潜在：目标MQ可能来自目标监督校准；外部参考可能共享未知目标来源。当前GNN源码对目标obs/availability/scaler直接路径的遮蔽通过合成扰动，但保留MQ，不能认证C。
R1/R2/Fourier6、目标监督基线、Stage C P1和D5同站跨年拟合均不能叫strict zero-shot。E4C冻结预测未见测试目标回填/状态重置；结论只限已检查源码/注册文件。

## 4. 可复用基线

same-day、lag、归一化核、单储量、68串联R1/R2和残差修正均已有。直接复用冻结方法与参考，禁止重复拟合R1/R2/Fourier6以及D5已拒绝模型搜索。Muskingum没有找到现成本地实现，已交付规范和后续测试计划，本轮未实现。

## 5. CPU合成测试结果

标签：**SYNTHETIC_UNIT_TEST_ONLY**。7/7物理测试通过，0失败；另global/station_reference两种输入边界扰动检查通过。没有真实流量模型训练或真实预测重跑；CPU PyTorch版本为2.14.0+cpu，未启动GPU任务。
- 恒定入流：稳态输出最大差0，空初态长期收敛差0。
- 单脉冲：t=4入流，终端峰在t=11；累计输入10 Q·day、输出10、尾部残余0；这只是人为tau条件，不是真实传播时间。
- 守恒：最大单日闭合误差4.04121e-14 Q·day，累计7.10543e-15 Q·day；若Q=m³/s，累计约6.14e−10m³。
- 已知延迟3day：终端峰精确后移3day；改变未来forcing不改变预测前缀。
- 日内dt=0.05/0.025/0.0125/0.00625day均稳定、非负、守恒，相邻分辨率L1差1.306263→0.528118→0.247337。公共外步仍1day，不声称已测试可变日步接口。
- 10种非法Q/tau/shape/state/substep/参数情形全部清晰ValueError拒绝。
- 分段状态连续传递与整段输出/末态逐值一致。
这些测试仅验证当前纯Python代码的所测性质；不验证现实侧向过程、参数物理真实性、真实预测能力或历史JIT产物。
代码/日志：`tests/run_synthetic_tests.py`、`synthetic_results.json/.log`、`check_synthetic_input_boundary.py`、`synthetic_input_boundary.json`。适配器按原文件AST精确加载，避免Numba在历史目录写cache。

## 6. 不可直接比较

2005五节点snapshot图、早期34节点STGNN和1978–1983的68河段物理链是不同设置。信息源、训练监督、年份、标签、容量和有效日均不同；不能据此声称图结构造成普遍负迁移。R2训练0.047227%改善不等于图结构因果效应。D5回顾性LOYO不是E4固定时序测试，外部月不能替代日尺度独立检验。

## 7. 下一阶段推荐三项

先过数据/协议门槛，再按research_protocol设计执行：季节条件化的上游增量信息检验；同输入同容量的方向×时滞消融；冻结R1+小残差在新未揭示年份的外推失效检验。当前不重做历史lag/R1/R2/Fourier/LOYO/M2C，跨站与跨流域需真实数据。

## 8. P0/P1/P2

P0：MQ血缘、日Q单位/日界/供数说明、月数据源与单位、新封存测试区间、C独立参数来源、历史全期筛选的评价身份。具体阻断分支见研究协议；MQ不明不禁止MQ-free带警告探索，但禁止C/独立验证主张。
P1：侧向来水/取水/闸控/断面和reach标签缺失、参数可识别性、现代几何代表性、日尺度传播分辨率、容量预算和共同日期、初始化、辅助接口合法性及历史执行绑定证据。
P2：大合成网、多站GNN、Caravan/CAMELS、遥感、神经算子与扩散；全部延期且不虚构输入。

## 9. 历史冻结文件完整性

本轮前后SHA-256核对 **2398文件、约4.43GB**：修改0、删除0、历史范围新增0。范围scripts/src/configs/tests/reports/outputs/data/processed/data/raw及根项目文件；包含E4、E5A、E5B图件、全部已有论文和审计。排除.git/.venv/node_modules/cache及data/remote_sensing；本轮未向这些目录写入。E5A登记源文件 **17/17哈希和大小匹配**，是与既存冻结记录的独立比较；前后快照则只证明本轮没有改变。
Git状态命令实际失败：fatal: not a git repository。无法判断本轮开始前是否存在未提交修改，记UNVERIFIED，未修复/重建Git、未reset/clean/checkout。完整差异见data_audit/integrity_result.json。

## 10. 准入与停止

S0来源清单、来源/泄漏/拓扑/物理基线审计、研究协议和最小合成测试已完成；来源/独立性仍存在P0，**READY_FOR_VHS_NEXT_S1=false**。审计完成不表示来源PASS。本轮真实模型训练=false、冻结结果修改=false、已有论文修改=false。已停止，等待用户对P0补证和具体S1分支的批准；不执行E5I1或任何Future任务。
