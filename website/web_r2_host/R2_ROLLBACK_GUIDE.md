# 恢复与回滚

本轮没有替换原发布目录，没有修改8775监听服务、R1的8791进程或P0–P5。候选运行于 `E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration/host`，因此当前回滚只需执行独立的 `stop_host.ps1`；原工程无需恢复文件。

停止脚本仅处理runtime/host_identity.json指定且启动时刻、端口和health路径均匹配的R2进程。身份不匹配会拒绝；不要使用全局按Python进程名结束命令。

未来如获准正式发布，先保存实际生产目录、启动命令、文件哈希、可信display审批记录和上一版发布指针。以独立版本切换部署，失败时切回旧指针与原启动命令。当前未确认8775活跃发布目录，因此不得把候选路径推定成生产目录，也不得直接覆盖候选原v0.6。

`evidence/HISTORY_BEFORE.json` 与 `HISTORY_AFTER.json` 记录历史封存文件哈希；`R2_DEPLOYMENT_DIFF.md` 与 `evidence/HOST_SOURCE_DIFF.patch` 是最小改动清单。候选内旧SHA256SUMS_v0.6.txt仅作原版参考，候选自身以根目录SHA256SUMS.txt为准。
