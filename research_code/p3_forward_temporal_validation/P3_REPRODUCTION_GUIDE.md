# P3 复现与交付索引
已完成run：PUBLIC_DATA_TEMPORAL_P3-20261026T075026Z-24fc69842c4d
任务：RECONSTRUCTION_WITH_OBSERVED_MET；真实公开Q，非合成，非教师锡尔河。

优先只读核验：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p3_forward_temporal_validation\code\verify_p3.py'
~~~
该命令不重新拟合、不修改run或报告，验证预测/参数/评分、日期、全局预测提交先于测试Q释放和历史哈希。

科学复现入口（仅未来明确要重跑时；不是本轮要求继续执行）：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p3_forward_temporal_validation\code\run_p3.py'
~~~
会创建另一个run并追加attempt；先保留当前完整交付快照。重跑不再是一次全新未见测试，不能把多次复现当独立科学重复。
不要重跑prepare_p3.py覆盖已经冻结的协议和切分；不得修改P2模型文件。
初始边界单元测试可在未封存副本中运行code/test_p3.py；历史P2完整训练未重复。

源数据：公开副本原有日尺度文件，路径/哈希见source/SNAPSHOT.json。source/features.csv无Q；train_labels.csv只含≤2004；test_labels_SCORE_ONLY.csv仅在全局预测包封存后由评分角色读取。
source/weather_monthly.csv及P3_TEMPORAL_SUPPORT_AUDIT.csv记录真实月聚合与前月对齐。缺测不为0。
在预测阶段会读取测试气象，符合月末历史重建；不支持提前流量预报。

run内prediction_bundle含无Qobs预测、参数、内层记录、拟合事件和单独SHA256；外层run再封存评分结果、测试Q释放收据及日志。
根目录SHA256覆盖本次完成交付；RUN_ATTEMPTS是该时间点快照，后续追加会改变交付点哈希，但不得改变原run。
后验汇总代码analyze_p3.py/postmortem_p3.py/diagnose_p3_support.py/report_p3.py只分析封存结果；新CSV以x模式写入，默认拒绝覆盖已有结果。

主报告P3_SCIENTIFIC_REPORT_ZH.md；决定P3_FINAL_MODEL_DECISION.md；失败P3_TEMPORAL_FAILURE_REPORT.md。
P3_COHORT_SUMMARY.csv完整24站为主，全27及部分3站另列。
P3_VS_P2_COMPARISON.csv / P3_VS_P2_SUMMARY.csv是同站不同训练期/测试期的描述比较，不是纯时间效应估计。
环境Python3.14.7、NumPy2.5.3，CPU单线程，无安装/网络下载。
