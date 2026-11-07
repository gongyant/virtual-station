# 运行与复核

使用已有环境，不安装依赖：

```powershell
$py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
$root='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation'
& $py -B "$root\code\verify_delivery.py"
& $py -B "$root\code\analyze_verify.py"
```

analyze_verify.py只加载保存参数复算1152预测、用封存后的观测来源独立核对指标，fit0；会更新本轮的检查/描述性诊断文件，不改不可变runs或历史文件。需要保持整个交付封存字节不变时只运行verify_delivery.py。

已封存run禁止覆盖。run_fixed.py的predict/score入口均带目录存在拒绝；不通过删除run重跑。需要新的数据/期间时建立单独的新run并绑定独立冻结协议。

driver任务复核：code/hourly_legacy_worker.py poll只查询原任务与下载结果，不追加任务；如数据已完成，可执行code/legacy_parity.py复算所取得的重叠日/月。它不是2020评分入口，不能把部分重叠通过当成全60月通过。code/historical_attempts目录保存曾失败的批量下载脚本，仅作历史证据，不应重新运行；CDS要求顺序任务。

没有网站、服务端口、教师数据授权或P4模型改动，因此回滚不涉及原服务：停止使用新目录即可。若需清理新目录应先保留不可变runs与来源哈希，不删除任何历史目录。
