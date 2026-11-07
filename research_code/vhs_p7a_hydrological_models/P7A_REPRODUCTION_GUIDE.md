# P7A复现与只读核验
本次目录已封存，禁止覆盖。首先运行只读验证（无fit、无新评分）：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\code\verify_delivery.py'
```

若需完整复现实验，复制code至新的独立输出目录，设置VHS_P7A_OUTPUT及VHS_WEB_S1_OUTPUT为尚无协议/清单的新目录。不能指向任何P0–P7旧目录。运行该副本的prepare.py → engine.py → final_train.py → historical_predict.py → score_verify_report.py → verify_extra.py。prepare先封存协议；engine训练期评分后才可晋升；final_train仅使用<=2017Q；historical_predict不导入fit，不读同期Q；独立score最后才关联P6D已暴露标签。所有过程沿用原公开资料，无需下载或安装。

本次实际首次engine运行数值训练已完成但自输出哈希读取被拒，使用 --resume-summary-only 恢复汇总，未重训。final_train首个ID2 C0+PT已完成，恢复复用了保存参数及内层选择，16次拟合的原耗时不可恢复，未伪造。见evidence/RECOVERY_AND_ATTEMPTS.json和RUN_ATTEMPTS.jsonl。

已保存模型推理入口（weather-csv必须仅含date,P,T，且有真实前月/记忆初始化历史，不接受Q）：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\code\predict_saved.py' --model 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\models\ID_2\P7-MEM\model.json' --weather-csv '<经过准入的date_P_T文件.csv>' --dates 'YYYY-MM' --output '<新的输出路径.json>'
```

此模板不代表已获得未来Q或完成新独立评分；MEM目前仅研究候选。执行命令记录见evidence/ACTUAL_EXECUTION_COMMANDS.json。全部样本/折/模型参数、内层损失、最终alpha/rho、支持限制均可回溯。训练cache只含2017及以前Q。训练读取审计、原P4标签哈希、模型/预测封存分别保存；不通过synthetic布尔值变更来源。
