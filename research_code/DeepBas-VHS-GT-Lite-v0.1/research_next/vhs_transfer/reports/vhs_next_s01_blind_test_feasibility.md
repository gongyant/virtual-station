# VHS-NEXT-S0.1｜新盲测可行性与封存方案


阶段：VHS-NEXT-S0.1 — P0 Resolution and Scientific Experiment Readiness。
日期：2026-10-11，Asia/Singapore。项目根目录：`E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
本轮仅针对S0已定位证据核查、元数据/历史使用可行性和协议设计。未进行真实模型训练、调参、真实预测重跑、GPU任务、S1A实验或E5I1。
`CONFIRMED`仅确认指定事实；来源复制确认不等于物理独立性确认。所有未证实事项保持未证实。

## 已有证据（继承S0，不算本轮发现）

S0已指出1978–1983/2005及2000、2001、2011都存在揭示历史，新最终测试尚缺。此结论不因目录名sealed/blind或曾经predictions_frozen而改变。

## 本轮新增核查或设计

本轮只列举 `data/raw/runoff/` 三个工作簿、`data/teacher_raw/Doc1.docx`，读取工作簿sheet名/docProps、既有source metadata、D5可用性注册及历史评分产物存在性。没有打开候选label CSV或新的目标数值，没有计算目标统计量或绘图；哈希是文件字节摘要，不是解析标签。

- **1978–1983 BYBLK/DSK日数据**：`CONTRADICTED_AS_NEW_BLIND`；来源 `data/raw/runoff/BYBLK-DSK日数据.xlsx`；时间元数据：1978-01-01..1983-12-31 inherited S0。历史使用：E1–E4及D5全六年开发/评价。

- **2000–2001支流OQ**：`CONTRADICTED_AS_NEW_BLIND`；来源 `data/raw/runoff/Q-新疆.xls / 2000-支流`；时间元数据：2000-01-01..2001-12-01 per existing frozen metadata, not full two calendar years。历史使用：existing blind_scoring artifact present; S0 already records revealed。

- **2005五站OQ/MQ**：`CONTRADICTED_AS_NEW_BLIND`；来源 `data/raw/runoff/Q-新疆.xls / 2005-支流,2005-干流`；时间元数据：merged 2005-01-02..10-31 per existing metadata; per-station ranges inherited S0。历史使用：GNN train/dev/evaluation and Stage B/C diagnostics。

- **2011 Doc1/水位测流资料**：`CONTRADICTED_AS_NEW_BLIND`；来源 `data/teacher_raw/Doc1.docx`；时间元数据：2011 identity inherited historical D5/S0; no document table parsed this phase。历史使用：historical Stage D–D12 and D5 documented revealed material。

- **外部月序列其余区间**：`UNVERIFIED_NOT_CERTIFIED`；来源 `data/raw/runoff/Q-dsk-byblk.xlsx`；时间元数据：1983 evaluation already revealed; other ranges not certified by this bounded check。历史使用：E4D source audit/overlap; provenance/units and access history incomplete。

- **Q-新疆其他sheet别名/副本**：`UNVERIFIED_NOT_CERTIFIED`；来源 `data/raw/runoff/Q-新疆.xls`；时间元数据：sheet names only DSK2000/BYBLK2000 and 2005 SB/RS variants; no new named year identified。历史使用：alias or unseen range cannot be inferred without access history; no cell values opened。

- **新增站/流域观测**：`NOT_FOUND_WITHIN_CHECKED_SCOPE`；来源 `bounded local runoff/teacher source inventory + prior additional-station registry`；时间元数据：no certified unused range identified。历史使用：2005 ALAR/XQM/AQK already used, cannot relabel them unseen。

本轮新增的直接元数据证据：Q-新疆12个sheet名称仅出现2000/2005及其SB/RS副本名；不能用副本后缀断言新观测或独立性。旧2000–2001冻结记录仍写target_labels_loaded=false，但它只描述当时生成预测的步骤；`outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/blind_scoring/external_validation_summary.json`已经存在。本轮只检查其存在与哈希，未读取指标。这不是当前“仍封存”的证明。该区间元数据截至2001-12-01，不能按文件名误写完整2000–2001年。

## 后续真正新测试的封存协议（未执行）

1. 数据保管者给候选target站/流域、日期范围、单位、日界、来源记录和文件哈希；候选若与历史文件同值副本则不能算新。agent仅看元数据，目标文件存于模型进程不可访问的独立权限边界。
2. 保管者核对既有脚本、访问/解封记录、成果、模型选择历史，签注“未进入任何开发”；只有文件mtime新、未命名test或代码声明sealed均不够。缺记录则UNVERIFIED。
3. 预注册A/B/C身份、训练/开发数据、两输入制度、所有特征与超参、主要比较/指标、缺测/日期support、失败和停止规则。现有候选label不能参与选择。
4. 冻结最终模型权重、代码、配置、环境/输入白名单及哈希，由保管者独立保留；先用合法上游/静态输入生成并哈希预测，模型进程无target labels可读路径。
5. 一次性解封，由评价器与预测按date join评分，不把标签提供给训练/预测程序。保留访问日志、输出哈希与全部预注册指标，失败也报告。
6. 若解封后修改特征/参数或重算选择，该测试立即成为开发资料，最终独立主张需要另一批未揭示数据；不得“重新封存”恢复盲测身份。

## 仍未解决

本地未找到能够认证的新且未揭示最终测试。检查范围是S0指向的流量来源和元数据，不是全盘所有可能资源的穷举；不证明世界上不存在新数据。其他月范围/别名sheet无访问历史、单位或独立性证明，保持未认证，不打开数值去挑性能好的年份。

## 对后续实验的影响

`NEW_BLIND_TEST_AVAILABLE=false`、`S1B_FINAL_HOLDOUT_READINESS=BLOCKED`。继续MQ-free历史开发设计，不因最终测试缺失终止准备。需要未来新供数及访问历史证明；本轮未下载、移动、复制封存标签或申请外部发送。
