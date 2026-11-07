# 运行、接口与回滚
在PowerShell执行：
```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_web_s1_research_integration\start_host.ps1'
```
只启动127.0.0.1:8794，检查现有进程身份，不替换其他占用者。明确未挂载教师源，不占用8775/8791/8792/8793。原主站API与导航保留，新增GET /api/v6/candidate-public/research/catalog|station|report|p7。station请求必须携带dataset、精确period/snapshot、命名空间station和合法model。source contract精确关联P6源与P4-V2模型，默认无Qobs。

```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_web_s1_research_integration\stop_host.ps1'
```
停止脚本核对自己的PID、启动时间及host_root，只停止本候选。回滚无需恢复旧文件：旧R2/R2U1/v0.6和端口未修改。停止8794后返回原版本URL/原启动器，不能删除旧结果或修改权限。

只读核验两套交付：运行P7A/code/verify_delivery.py。SHA排除runtime、host/logs、host/tmp、host/var及__pycache__这类可变操作目录；其余已封存文件应保持哈希一致。运行服务只读科研源，不重新训练或评分。source hash不一致时拒绝，不自动回退到锡尔河或旧metadata snapshot。

正式生产接入仍需原平台有权负责人批准精确结果展示范围及原可信display callback；本轮未授予生产、在线执行或教师数据权限。P6新Q接口复用同一source/run/station/model/period外键，先独立封存科学结果，再增加新的证据snapshot，不能回写旧成绩。
