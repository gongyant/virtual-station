# PUBLIC_DATA_EXPLORATORY_P1
实际完成四模型真实结构消融，已封存run：
PUBLIC_DATA_EXPLORATORY_P1-20261026T015059Z-7f0aabd5cf43

先读 P1_SCIENTIFIC_REPORT_ZH.md。原三站与新增六站结果分别在reports两个子目录。
本轮7200条新真实OOF，另引用旧1440条；600新外层拟合、13500内层拟合。
不访问教师Q；无锡尔河真实结果；没有实施P2。

只读核验（不重新拟合、不改已有run）：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p1_seasonal_meteorology_ablation\code\verify_p1.py'
~~~
如用户以后明确要求重新复现，以下命令会创建另一个run，绝不覆盖原run：
~~~powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\p1_seasonal_meteorology_ablation\code\run_p1.py'
~~~
不要重新执行prepare_p1.py、select_candidates.py或freeze_data.py来改变已冻结方案。
SHA256SUMS.txt覆盖P1交付，真实run另有独立SHA256SUMS。RUN_ATTEMPTS保留最初零拟合调度失败。
