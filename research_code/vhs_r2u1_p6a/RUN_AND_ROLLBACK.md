# 运行、复核与回滚

候选主站：http://127.0.0.1:8793/#/overview?dataset=LAMAH_CE_PUBLIC_V1

```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a/start_host.ps1'
& 'E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/.venv/Scripts/python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a/code/verify_u1.py'
& 'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a/stop_host.ps1'
```

只停止8793的已记录实际服务PID并检查UTC启动时刻和health身份；R2的8792、R1的8791与原8775不由本轮脚本管理。回滚只需停止8793，未替换R2文件。生产display仍NOT_GRANTED，正式接口、动态执行与Qobs导出保留403，教师Q未挂载。

P6复核可只读执行code/verify_u1.py；不要再次运行已经完成的admit/predict/score来覆盖原run，代码会拒绝覆盖。要做独立复现，先选新的独立输出目录并保持本轮协议、源文件和模型哈希一致。新拟合和调参不属于本轮。

本轮新增代码在code/，候选代码在host/；R2U1_CODE_DIFF.patch给出精确差异。运行日志、Chrome profile、PID记录位于runtime和host/logs/tmp/var，为可变运行区，关键验收已复制到evidence。根SHA256SUMS封存其余交付文件；独立P6预测与评分各自另有manifest。
