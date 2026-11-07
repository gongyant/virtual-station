# VHS-NEXT-S1A-R2｜交付验证

身份：POST_HOC_EXPLORATORY_DIAGNOSTIC。数值/执行完整性 PASS 不代表科研主假设通过。

226个继承定向保护文件开始/结束SHA256一致。已封存预测、48套参数及训练月份均值、标准差、beta字节未变；E4/E5/论文/S0/S0.1/R0/R1清单内文件未变。没有重新进行大规模历史扫描。

48组R1指标独立按已评分日视图复核；历史bootstrap256行只读，不重抽样。六组365日原真实预测在生成任何swap之前由冻结参数重建，并满足rtol=1e−12、atol=1e−12；最大误差见pre_swap_validation.json。36组×335日共12060行交换预测再由独立逐日标量实现复核。每个目标年两种基线都保留1978–1983六条参照（五donor+self），同日期同目标基线同冻结beta/scaler同真实分组，无择优删除。

训练DSK Q20/Q90与上游t−1 Q20/Q90分别定义两套互斥完整分层。独立复核主365日每个日期标签与36组swap固定mask；各层SSE与年度加总、偏差平方+ddof=0误差方差恒等式通过。原39组placebo支持始终275日Jan1–Oct2，完整13个k，无跨支持排名。year-swap Jan31–Dec31固定335日；1978历史最早Jan1；1980按month-day映射，Mar1为实际Mar1，窗口自然含Feb29。

非重叠30日块从Jan1开始，年末5日独立块。335/275日对原日历块取交集并记录n。900行块分解SSE守恒且cross-term满足1e−10+1e−12*SSE，最大abs(cross)/max(SSE,1)=7.28e-16。最初固定绝对1e−10的零检验在一条placebo块遇到−1.1213e−10浮点舍入，已明确改用SSE尺度容差；未改变分解、日期或模型。

5项CPU合成测试通过：偏差方差恒等式、阈值边界覆盖、跨块正交、闰年month-day/真实窗口、335日计数。全部R2 Python源AST未出现模型fit/OLS/pinv/lstsq/优化调用；没有导入历史拟合执行器。阈值为允许的训练分位数诊断统计，不更新模型scaler。写入仅R2及三个R2报告和status，无原始数据目录写入代码路径；该证明基于代码与限定哈希，不是对抗性OS沙箱。

五张图各有PDF/SVG/600dpi PNG，标注Retrospective post-hoc diagnostic.，同类面板共享y轴范围。渲染轴对齐、源码、5pt下限、最终PDF碰撞全部通过；逐年面板与整图人工检查见visual_qa.json。PDF库只读复用R1隔离目录，使用Python -B，没有安装依赖或修改历史缓存。

空单元n=0保留NA，n<10标小样本；不以空格为零误差。年度占比守卫、绝对贡献、固定top5/10/20、全部块删除及所有donor结果均保留。没有p值、独立确认、物理机制或lag识别升级。

复现顺序（当前封存目录不覆盖重跑）：在新的授权输出目录使用相同源码和冻结输入，analyze.py → build_reports.py → plot_results.py → figure_qa.py → validate_delivery.py。analyze.py已完成保护会拒绝自动重跑；后处理不修改历史或模型。代码/输入哈希、原始中间CSV及delivery_manifest.json均可追溯。

R1主失败结论不变。本轮没有新lag/OLS/ridge/Fourier/GNN/Muskingum/气象训练/GPU/S1B/S1C/E5I1。完成R2后停止等待批准。
