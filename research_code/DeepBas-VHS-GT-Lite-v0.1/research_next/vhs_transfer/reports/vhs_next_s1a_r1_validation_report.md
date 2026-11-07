# VHS-NEXT-S1A-R1｜执行与交付验证

身份：PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS。全部年份曾被历史研究接触；STRICT_ZERO_SHOT=false，INDEPENDENT_FINAL_TEST=false，CAUSAL_TRANSPORT_IDENTIFIED=false。单位仅为项目Q数值单位；日均/原始单位/水文日界/发布时刻/供数方未证实，不换算物理m³。

执行/数值/完整性验证PASS；科研主实践规则未通过，二者严格分开。新增4项CPU合成检查通过，沿用哈希未变的R0数值模块及22项原测试证据，没有改写R0测试结果。

输入SHA匹配；2191个连续源日、每折train=1066/1431/1796、完整开发365日、placebo275日，模型均无缺值/秩/尺度异常。新视图仅白名单，模型worker不读取evaluation视图。独立评分器无fit调用，全部48次fit先于预测全局封存，封存先于评价标签打开，评分后预测/参数/config仍字节一致。

48组输出指标用已评分日视图独立核对RMSE/MAE/PBIAS/相对增益，误差0；没有再次真实拟合、重新bootstrap或加入新模型。所有16个预定对照×circular/noncircular×30/60日×逐年/宏平均共有256行CI记录，固定seed/10000次。

150个定向历史保护文件未变；复用S0/S0.1/R0记录，没有全面重扫2398个历史文件或大型模型/图。输入仅已授权日数据CSV，旧R1参考预测未作为新数值输入；Own-Past未执行。

三张图PDF/SVG/600dpi PNG完成，源代码、渲染轴对齐、5pt字形下限和最终PDF碰撞均通过。逐面板与整图人工检查：placebo三年共用纵轴并保留全部13点；gain图分隔Past-only/Same-day/F2并使用同一条件CI定义；残差图完整展示三个年份365日，包含不利洪峰，无删点、平滑或择优绘制。

PDF碰撞工具原环境缺PyMuPDF，已仅在新R1目录隔离安装PyMuPDF 1.28.2用于QA；未修改数值.venv或历史依赖。Python绘图后处理代码独立登记哈希，未变更预拟合冻结的执行器。API/过程隔离不是对抗性OS沙箱，可信CSV拆分层能接触原始行字符串；旧年份暴露和人为绕过风险不被升级为零泄漏证明。

可复现顺序：项目.venv Python -B依次执行test_executor.py、preflight.py、fit_predict.py、score_results.py；绘图与报告随后执行。preflight/fit/score有已运行保护，在当前交付目录不允许自动覆盖重跑；将来若需复现须另行批准并使用新输出目录及同一冻结代码/config/环境，不覆盖本轮。

[机读验证](../experiments/s1a_r1/delivery_validation.json)、[完整数据角色台账](../experiments/s1a_r1/data_role_ledger.json)、[图形QA](../experiments/s1a_r1/figure_qa_summary.json)、[完整性](../experiments/s1a_r1/s1a_r1_integrity_report.json)。

本阶段已停止，未开启下一轮研究。
