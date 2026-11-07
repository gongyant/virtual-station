# P6B复核与复现

现有环境（不安装依赖）：

```powershell
$py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
$root='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation'
& $py -B "$root\code\verify_delivery.py"
```

该入口完全只读，不联网、不fit、不预测、不评分，验证整个交付SHA。

完整算法复核代码：analyze_verify.py独立重算24站1152预测及指标；verify_2020.py重算818站24预测、366日观测指标和区间；arco_legacy_parity.py按原官方代码核对1415小时与60个月。它们fit0，但会写验证/诊断文件。若要求交付目录字节保持不变，应复制到独立复核目录并仅在副本调整R输出路径后运行；历史L/P4输入只读。

run_fixed.py predict/score和run_818_2020.py freeze2020/predict2020/score2020是已经实际调用的执行入口；现有不可变run存在时拒绝覆盖。不得删除run强行重跑。新资料必须新run、新冻结输入与独立来源绑定。

四格点CDS任务已完成，无待轮询或隐含下载进程。code中的早期批量请求脚本只作失败历史证据，不应重跑；CDS要求顺序提交等待完成。本轮官方NetCDF容器和原R处理代码都已随来源证据保存，通常无需再次下载。

没有修改网站或端口、P4模型、教师授权。回滚无需改原服务；停止使用新目录即可。不要删除历史科研文件。
