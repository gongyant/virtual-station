# VHS-NEXT-S0.1｜MQ来源逐问题决策


阶段：VHS-NEXT-S0.1 — P0 Resolution and Scientific Experiment Readiness。
日期：2026-10-11，Asia/Singapore。项目根目录：`E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
本轮仅针对S0已定位证据核查、元数据/历史使用可行性和协议设计。未进行真实模型训练、调参、真实预测重跑、GPU任务、S1A实验或E5I1。
`CONFIRMED`仅确认指定事实；来源复制确认不等于物理独立性确认。所有未证实事项保持未证实。

## 已有证据（继承S0，不算本轮发现）

S0确认工作簿→CSV→NPZ的复制链一致，原始生成/校准链未确认。既有D5血缘记录同样阻断：[outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md)。本轮不重做逐值比对。

## 本轮新增核查或设计

**MQ1 physical_reference_q原始工作簿来源：`CONFIRMED`。** 本地Q-新疆.xls/2005-支流/MQ-DSK-2005-SB，DSK B列；此为导入源，非最初生成来源。

**MQ2 MQ是否按工作簿值直接复制导入：`CONFIRMED`。** extract_multisite_runoff_2005读取reference后赋给physical_reference_q_m3s，再改名为tensor physical_reference_q；没有在此计算物理MQ。

**MQ3 原始MQ生成脚本是否找到：`UNVERIFIED`。** 在S0指向的导入/血缘/使用链中未找到；不把局部未发现扩张成全盘不存在证明。

**MQ4 能否证明MQ未用目标站Q校准：`UNVERIFIED`。** 缺生成输入、校准站/年/参数记录；既不能证明独立，也不能断言确有目标校准。

**MQ5 MQ是否含目标站历史插补、平滑或模拟结果：`UNVERIFIED`。** 复制链不修改值；工作簿之前的处理及MQ含义无证据，SB/RS字样不能替代模型说明。

**MQ6 是否有可验证供数者、观测时期与单位说明：`UNVERIFIED`。** 已知2005表头及文件user_name=MECHREVO只能证文件内标记，不能认证提供者/水文日/单位；未见正式供数说明。

**MQ7 把本仓库导入器称为MQ独立物理生成模型：`CONTRADICTED`。** 源码在该位置直接复制现成列；这只否定导入器现场生成MQ，不否定未知外部存在物理模型。

**MQ8 S1A主输入是否需要MQ：`NOT_APPLICABLE`。** 新主比较排除MQ及其派生量，生成链不是S1A主比较的数值输入依赖。

本轮只核对已知2005支流/干流表头和导入赋值，不读取其他sheet的目标流量。源码证据：[scripts/extract_multisite_runoff_2005.py:159](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/extract_multisite_runoff_2005.py:159); [scripts/extract_multisite_runoff_2005.py:180](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/extract_multisite_runoff_2005.py:180); [scripts/prepare_multisite_gnn_bundle_2005.py:55](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/prepare_multisite_gnn_bundle_2005.py:55)。
文件SHA-256：`9bd677ae904e3520fd89f759589ec3194fbaff8f10b6f9ccca5a63f8c78efe46`，与S0/既有元数据一致。worksheet表头的2005是本地时期标记，不是正式数据采集证明。

## 仍未解决

没有MQ公式/可执行生成脚本、原始输入清单、校准站点及年份、目标标签是否参与的记录、参数/版本、提供者和原始变量单位。需要原提供者提供这些最小记录；不得通过Q相关性或数值范围反推。

## 对后续实验的影响

`MQ_PROVENANCE_VERIFIED=false`；`MQ_FREE_PRIMARY_PROTOCOL=true`。MQ及MQ派生残差锚点、physics loss、station_reference归一化全部排除出S1A主比较。不能把“MQ-free”改称strict zero-shot，因为S1A仍使用DSK训练标签。MQ分支及S1C继续阻断。
