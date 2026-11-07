# 原主站候选运行及回滚

入口：http://127.0.0.1:8795/#/overview?dataset=KAZAKHSTAN_PUBLIC_NETWORK

```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_kaz_n1_national_virtual_stations\web_candidate\start_host.ps1'
& 'E:\VHS_Public_Baseline_Lab\vhs_kaz_n1_national_virtual_stations\web_candidate\stop_host.ps1'
```

当前8795已实际运行并经HTTP和浏览器检查。启动器仅接受8795空闲或该候选健康身份；停止器核对该候选PID和启动时间。不要直接kill任意端口进程。原8775/8791/8792/8793/8794不占用、不停止。

新增在原WEB-S1复制版的四层导航与共享选择状态中：官方四问、真实部分河网及1230初筛点、3个状态独立图层、8大流域名称及几何缺口、实际密度、欧洲PUB完整负结果。真实物理站当前坐标0、可预测虚拟站0，地图为空图层有明确原因。欧洲指标以外国数据集命名，不写入KAZ/SYRDARYA成绩。

候选新增`host/kaz_national.py`、`static/view_kaz_national.js`；原复制版`r2_public.py`/`server.py`/`index.html`接入只读路由、数据集页签。`WEB_KAZ_SOURCE_PINS.json`严格绑定来源；请求跨快照拒绝，训练/推理/导出Qobs及正式生产公开端点403。新页签选中状态也同步ARIA。旧默认P2-L1及54个公开模型身份保持；旧教师源未挂载。

本次仅本地候选，生产发布仍NOT_GRANTED，没有伪造审批或改原服务。回滚只停止本候选并使用原历史主站入口；没有覆盖旧目录，无需恢复旧文件。不需要删科研产物。若未来发布，应由有权负责人按旧可信展示许可机制批准新数据集/快照/来源范围；展示许可不能替代执行许可。
