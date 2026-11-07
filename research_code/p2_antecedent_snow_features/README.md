# PUBLIC_DATA_EXPLORATORY_P2
已完成真实公开观测训练；未更改P1/私有VHS；无P3训练。
先读 P2_SCIENTIFIC_REPORT_ZH.md 和 P2_EXTERNAL_VALIDATION_REPORT.md。

不可变run：runs/PUBLIC_DATA_EXPLORATORY_P2-20261026T054233Z-36d2a5289632
540外层折、1620外层参数拟合、72900内层拟合、19440条OOF。
原九站与新增18站分组CSV位于reports两个子目录。

只读复核（不重新拟合，不写已有run）：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p2_antecedent_snow_features\P2_MODEL_CODE\verify_p2.py'
~~~

将来显式复现会生成新run并追加attempt；当前交付封存是此时间点快照，先保留完整交付副本再重跑：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p2_antecedent_snow_features\P2_MODEL_CODE\run_p2.py'
~~~

P2_FEATURE_SUPPORT.csv是原始年月及前期日期支持；P2_FOLD_FEATURE_SUPPORT.csv是训练折常数/弱支持。
P2_PROXY_EXTRAPOLATION.csv保留每个雪代理测试异常与同月训练范围，未作剔除。
P2_FLOW_DIAGNOSTICS.csv/P2_DIAGNOSTIC_COMPARISONS.csv保留高低流量与季节公平比较。
原始预测主分析；非负预测为预定次分析。没有按测试分数改变模型、阈值、网格或流域。
