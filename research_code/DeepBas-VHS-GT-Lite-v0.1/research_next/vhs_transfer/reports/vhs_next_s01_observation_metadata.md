# VHS-NEXT-S0.1｜观测单位、日界与站点证据等级


阶段：VHS-NEXT-S0.1 — P0 Resolution and Scientific Experiment Readiness。
日期：2026-10-11，Asia/Singapore。项目根目录：`E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
本轮仅针对S0已定位证据核查、元数据/历史使用可行性和协议设计。未进行真实模型训练、调参、真实预测重跑、GPU任务、S1A实验或E5I1。
`CONFIRMED`仅确认指定事实；来源复制确认不等于物理独立性确认。所有未证实事项保持未证实。

## 已有证据（继承S0，不算本轮发现）

4382站日加工一致、无项目层目标插补是S0既有结论。本轮仅读取原始表的前两行文字与docProps，不再次统计Q。历史单位与时间口径记录：[outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/daily_time_definition_audit.md](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/daily_time_definition_audit.md)、[outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/raw_workbook_structure_audit.json](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/raw_workbook_structure_audit.json)。

## 本轮新增核查或设计

| 项目 | 原始证据级别 | 项目支持级别 | 代码级别 |
|---|---|---|---|
| Q单位m³/s | UNVERIFIED | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |
| 日平均还是某时刻瞬时值 | UNVERIFIED | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |
| 水文日界/时区/时间戳意义 | UNVERIFIED | UNVERIFIED | ASSUMED_BY_EXISTING_CODE |
| 两站共享同一日期键 | VERIFIED_FROM_PRIMARY_SOURCE | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |
| 两站真实日统计窗口相同 | UNVERIFIED | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |
| 站名/站号项目内映射 | UNVERIFIED | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |
| 物理模型单位与原Q真实单位一致 | UNVERIFIED | SUPPORTED_BY_PROJECT_METADATA | ASSUMED_BY_EXISTING_CODE |

逐项解释：
- **Q单位m³/s**：原始头为Q/BYBLK/DSK、OQ；原单位检查无打印单位。m³/s来自项目契约/评价及导入列名，不是原始计量证明。

- **日平均还是某时刻瞬时值**：日数据文件名和逐日索引支持daily cadence；daily mean流量是现有routing解释，不等于已证实daily mean。

- **水文日界/时区/时间戳意义**：read_flow_source只pd.to_datetime；build_bundle normalize到日期，无水文日/时区换算。

- **两站共享同一日期键**：原工作簿同一Q日期列、BYBLK/DSK两列；此项只确认文件布局。

- **两站真实日统计窗口相同**：同表对齐不能证明原始汇编前两站用了相同起止时刻。

- **站名/站号项目内映射**：配置/KMZ衍生映射：00705600巴音布鲁克，00705700大山口；未见正式编号名录/站址沿革认证。

- **物理模型单位与原Q真实单位一致**：现有代码按Q=m³/s、tau=day、S=Q·day计算，代码内部量纲可一致，但原Q单位/日均身份未证实。

本轮直接核得原日工作簿 `creator=MECHREVO`、`lastModifiedBy=Tie`、创建 `2026-07-20T06:45:48Z`、修改 `2026-07-20T06:46:45Z`。这些是文件属性；不能当官方供数者、1978–1983采集时间或科学真实性证明，也不能因新文件日期推断数据伪造。
原两行：A1=Q、B1=BYBLK、C1=DSK；B2/C2=OQ，无单位/日界文字。已知旧结构审计没有单位单元格，本轮没有全面重新扫描工作表。
导入证据：[src/vhs/io.py:104](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/src/vhs/io.py:104); 项目映射：[outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/station_mapping_audit.csv](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/station_mapping_audit.csv)。
关键区分：历史报告“同来源/同整编口径”可支持项目对齐，不能升级为两站真实水文日界相同的原始证明；不修改其历史文字。

## 仍未解决

最少索取四类资料：①带机构/提供者身份的原始数据说明与版本；②Q单位、是否日平均/瞬时、统计方法及缺测/质控/人工订正说明；③两站各自日统计起止时刻、时区、时间戳标记起日/止日和历年变更；④正式站号—站名—站址沿革/测站位置对应。可为一份覆盖以上字段的正式说明，不要求虚构多个文件。MQ和外部月序列另需各自生成/来源说明。

## 对后续实验的影响

`DAILY_Q_METADATA_VERIFIED=false`。S1A可按已有日期键与数值Q约定做受限开发，RMSE/MAE/Bias标“项目Q数值单位，m³/s尚未由原始来源证实”；NSE/相对RMSE/PBIAS仍只解释为同源数值比较，不能认证物理量纲。日水量只报告数值日和/相对偏差，不转m³；峰时只解释为日期索引误差。不能声称实时可用、亚日物理时滞或真实水量闭合。
