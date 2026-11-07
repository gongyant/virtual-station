# VHS-NEXT-S1A-R3｜验证报告

身份：RETROSPECTIVE_POST_EXPOSURE_EXPLORATORY_ANALYSIS。执行/来源/数值验证PASS不同于稳定科学增量得到确认。

数据门槛PASS：实际NetCDF2191日、P/T变量定义、单位、UTC边界、增量流域、175项面积权重、保存日网格P/T加权重现、S0来源SHA均核对；无目标Q进入所检查强迫生成链。没有重跑原始下载或大规模历史审计。P7固定7日平均与旧P_inc_7d总和差异在fit前明确报告，未更换窗口。

全部319个定向历史/来源保护文件执行前后SHA一致。S0/S0.1/R0/R1/R2、E4/E5及论文清单内冻结项未改；M0/M1逐日期复用原预测，未重新拟合。R3公式/输入/日期/环境及全部脚本哈希在fit前冻结。

4项CPU人工合成检查通过。每折M2/M3共同train=1066/1431/1796日、dev365日，训练月均/尺度、满秩2/5及最晚t−1检查通过。气象均值/尺度仅训练，Q尺度及目标月均原样复用R1。无截距、ridge、窗口、lag、谐波搜索。6次真实OLS事件先于全局预测封存，封存先于独立评分器打开标签；评分后0次fit。4380行主预测和6030行swap预测参数/预测SHA保持不变。

独立复核12组RMSE/MAE/NSE/PBIAS/年数值和误差、12个配对DeltaSSE与状态分层加总、块SSE守恒。主预测冻结参数重建最大绝对差0；18组335日swap全部重建，目标P7/T7和M2参照不变、真实mask不变、month-day正确、各donor同参同日。未遗漏1981/1982不利结果或1980donor，未跨365/335日排名。

30日块Jan1锚定、年末5日，cross-term容差1e−10+1e−12*SSE；between+within严格加总。全部四对照的10000次30/60日circular/noncircular条件bootstrap共64行，固定seed；无p值、无2%确认性标准。估计条件数/SVD/VIF/beta全部报告，无因诊断值修改模型。

评分/报告/验证源码AST无fit/pinv/OLS调用，模型worker不导入评分器、不读取开发目标视图。角色边界为可检查的进程/代码隔离，不是对抗性OS沙箱；历史标签先前已暴露的事实保留。新增写入仅R3及命名R3报告，未写原始数据目录、未运行旧finalizer/模型/GPU任务。

未生成图件不影响要求的CSV/报告交付；所有指定文件均实际生成，没有空文件冒充成功。全部可复现中间参数、台账、事件、源码、配置、环境及SHA在R3目录。最终顺序preflight→fit_predict→score_results_v2（保留原中断记录）→build_reports→validate_delivery_v2→finalize_delivery；预检查/拟合/评分都有一次执行保护，禁止在封存目录自动覆盖重跑，独立复现需新目录和后续授权。

R3结束即停止，不开展GNN/Muskingum/lag搜索/S1B/S1C/GPU/E5I1。

`R3_DATA_GATE=PASS`

`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`

`NEW_BLIND_TEST_PERFORMED=false`

`STRICT_ZERO_SHOT_CLAIM=false`

`HISTORICAL_FILES_CHANGED=false`


## 执行问题与透明修正记录

首次评分在year-swap的1月单日单元（Jan31）遇到NSE未定义，原评分器对None作减法而停止；没有输出完整评分、没有改动或重新拟合模型。保留原冻结score_results.py及原scoring_started标记，另存score_results_v2.py，仅将未定义DeltaNSE设NA，并使用独立一次恢复标记。修正版SHA在执行前记录于scoring_repair_manifest.json；全部预测与原执行代码SHA仍保持不变。该单日单元其他误差指标可定义，日期没有删除。

首次交付校验误沿用R1的256行bootstrap期待值，R3实际只有4对照×4种block/circular模式×4个年度/宏平均scope=64行。数据输出正确，不重采样。保留原冻结validate_delivery.py，修正版validate_delivery_v2.py把断言、报告和机读计数统一为实际64行，独立哈希见validation_repair_manifest.json。两处均为评分/交付边界实现错误，不是数据缺失、泄漏、秩或模型准入异常；修正后没有继续拟合（新增fit=0），不改变模型、窗口、参数、日期或评价定义。

最终额外检查：逐项代码差异限定NA处理/恢复标记；18条Jan31交换单元n=1、DeltaNSE=NA保留；6套参数训练正态方程残差与训练气象中心/尺度复核；18组swap的RMSE/DeltaSSE/状态加总独立复核。复现应使用冻结原执行器加两份明确版本的评分/验证修正，不覆盖原冻结源码。

`R3_DATA_GATE=PASS`

`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`

`NEW_BLIND_TEST_PERFORMED=false`

`STRICT_ZERO_SHOT_CLAIM=false`

`HISTORICAL_FILES_CHANGED=false`

完成并停止，等待下一次批准。
