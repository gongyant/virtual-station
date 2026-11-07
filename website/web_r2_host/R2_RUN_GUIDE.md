# 运行候选主站

当前地址：http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1

```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration/start_host.ps1'
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration/tools/acceptance.py'
& 'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration/stop_host.ps1'
```

8792为原v0.6候选副本的端口，不使用生产8775，也不重新制作8791预览。启动脚本只连接127.0.0.1，已运行同目录候选时直接返回；停止脚本核对PID、启动时刻、脚本路径和health主站路径，拒绝误杀其他服务。

依赖为现有Python环境（numpy、pyproj）、已安装Chrome、相邻的冻结WEB-R1代码与数据，以及P4/P5封存模型文件。模型加载验证调用既有 `p5_cli.py verify-release`，不会fit或生成新预测。测试用Chrome临时profile保存在runtime。所有原数据路径只读。

候选默认不加载教师六份CSV。SYRDARYA页说明教师源未挂载；旧适配器、权限和页面文件保留，146项原有合成回归通过。旧LAMAHCE仍展示882站元数据，不接收公开Qsim。

本地候选显示范围来自本轮用户明确指令。它没有生产display许可、签名或verified callback。普通JSON中的GRANTED/verified字段不起作用。未授权执行和Qobs导出仍403。
