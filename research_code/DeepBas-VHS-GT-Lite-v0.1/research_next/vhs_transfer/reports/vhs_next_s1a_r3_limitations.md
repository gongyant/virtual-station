# VHS-NEXT-S1A-R3｜局限与解释边界



RETROSPECTIVE_POST_EXPOSURE_EXPLORATORY_ANALYSIS



本地ERA5生成链未发现目标DSK Q参与P/T构造、筛选或标准化；这仅排除所检查实现的直接目标路径，不证明ERA5供应商同化体系与任何地面水文观测完全独立。流域选择及本轮科学假设受历史Q暴露影响，后验设计身份保留。旧D5选择污染不被继承为训练输入，但不能据此将新设计称为独立。

强迫UTC日界、00UTC累计后移一天、mm/°C转换由项目代码和实际元数据支持；站点Q单位/日界/发布时间未认证，故nominally past-only不等于实时可部署。再分析利用后验资料，不认证operational forecasting。

P7/T7仅固定增量流域七日均值，不是全流域或完整共同气象驱动集。未包括融雪、雪储量、调度和非线性/交互机制。不能以两列气象控制排除所有共同原因。

M2/M3固定Monthly残差OLS、无截距，气象按训练anchor month去季节化并训练std缩放；M1沿用旧三参数，上游新M3系数联合重估而非简单沿用M1系数。系数竞争与相关性影响解释，不能把某系数等同过程效应。

365日主支持、335日swap支持分别比较；每个target的真实P/T、baseline、M3参数和mask在所有donor间相同。month-day映射保留donor真实窗口；不同donor边际分布/湿润状态不相同，五donor非独立随机重复，future donor非因果诊断。

30日正交块为固定误差分解，between不等同基流、within不等同快速输移。真实优于donor与真实优于M2是不同参照，不能混用。状态LOW由训练上游t−1阈值定义，非下游目标低流标签。

三个相邻开发年、重叠训练窗、单上下游案例，均早已暴露。10000次年内配对30/60日circular/noncircular区间只条件于已估计参数和所见年份，不覆盖训练估计、后验方法选择或新站点不确定性；不用原2%阈值作本轮确认性标准，不报告总体p值。

数据/来源/执行/数值PASS不同于科研增量稳定性PASS。哈希仅覆盖定向继承及本轮输入清单，不声称全磁盘审计。角色隔离由独立worker及白名单实现，不是对抗性OS沙箱。所有异常停止，不自动删日/补数据/换变量/搜索。

既有科学结果与论文冻结；没有新盲测、strict zero-shot、河道因果识别、独立气象认证或跨流域泛化。需要新的独立数据而非无限重分析旧年。



`R3_DATA_GATE=PASS`

`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`

`NEW_BLIND_TEST_PERFORMED=false`

`STRICT_ZERO_SHOT_CLAIM=false`

`HISTORICAL_FILES_CHANGED=false`
