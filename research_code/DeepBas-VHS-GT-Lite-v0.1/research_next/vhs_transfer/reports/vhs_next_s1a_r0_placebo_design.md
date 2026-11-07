阶段：VHS-NEXT-S1A-R0，2026-10-11。所有新内容为独立v2；原S0/S0.1、E4/E5与论文冻结。本轮只执行CPU人工合成信号测试，未读取真实开发目标值用于拟合、预测或评分。

关联：[原S0.1协议](./vhs_next_s01_mq_free_s1a_protocol.md)、[原设计契约](./vhs_next_s01_s1a_design_contract.json)、[v2配置](../experiments/s1a/protocol_v2.json)、[合成测试](../experiments/s1a/synthetic_test_results.json)。

# Displaced-Upstream Placebo预定设计

问题：If upstream discharge contains day-level predictive information, how sensitive is the observed skill to disruption of its temporal alignment with downstream discharge?

## 符号和变换顺序

固定k=±3、±7、±14、±30、±60、±90及真实对齐k=0。U_k(t)=U(t-k)，因此正k取更早上游、负k取未来上游。对原past-only窗口移位：W1,k(t)=U(t-k-1)，W7,k(t)=mean U(t-k-7..t-k-1)，W30,k(t)=mean U(t-k-30..t-k-1)。负k的W30可能混合过去与未来，整个模型仍统一标NONCAUSAL_FUTURE_UPSTREAM_PLACEBO，绝不参与合法预测主排名。

先在每折原完整合法train锚点s上构造未移位W_j(s)，拟合12个源月均C_Wj(m)与去月均后std s_j(ddof=0)。源窗口可以读取train开始前的合法上游预热，但不得用train结束后的上游估计统计量。定义Z_j(s)=[W_j(s)-C_Wj(month(s))]/s_j，最后以s=t-k取Z_j(t-k)。使用窗口锚点源月份month(t-k)，不能用目标月份month(t)，也不逐原始日先去季节后再平均；这保留原S0.1“窗口后去月均”定义。所有k共享同一个原train源统计估计器。

目标气候态仍是原完整train DSK月均C_y(month(t))，同一折所有k包括0完全相同；目标月份不会随上游位移。三系数OLS只在共同训练目标日期拟合Q_DSK(t)-C_y(month(t))，每个k重新拟合自身beta但不调参。训练负k虽相对训练目标t使用未来上游，也只允许用该折train截止日前源日期，不能偷用开发上游来拟合诊断系数。气候态/源尺度用完整合法train是预定共享nuisance fit，不是开发信息。

## 共同支持、边界与k=0

共同训练T*=交集{t在原train，所有k的s=t-k都在原train锚点范围，且窗口原始源日合法}。已知完整日历下等价原train[90:-90]：起日1978-05-01，各折尾日1980/1981/1982-10-02，计划n=886/1251/1616。删除来自固定±90边界约束，不来自目标值、缺测或性能。所有k的源参数仍按原完整合法train拟合，beta按相同T*拟合。

共同开发D*=原开发日交集{所有k的源锚点≤该开发年Dec31且窗口源日合法}。不借下一年上游，也不虚构1984数据；完整日历下为Jan1..Oct2，每年275日。早期开发日的正位移可用合法上一年上游历史。采用保守锚点截止，即便某窗口原始源日可再多一天也不另扩支持。

必须保存原主完整train/365日开发结果；安慰剂k=0另在T*重新fit并在D*评分，其余k同T*/D*。完整主模型亦可额外在D*计算一个明确标注的support-only诊断，但不能用它代替共同T*的安慰剂k=0，或把不同训练/开发支持混排。所有k的缺值/异常导致整个预定比较停止，不按k各自dropna或按目标流量筛mask。无np.roll、周期重复、年末拼接或边界填充。

275日评分不能代表完整年季节覆盖，特别不覆盖Oct3..Dec31。所有计数由日历计算，并非真实Q完整性检查；真实运行尚未获准。共同训练削减也改变拟合精度，所有k统一受此约束，不能把变化解释成位移的纯物理效应。

## 预定输出与解释规则

每年报告13个k的固定指标、g_y(k)=(RMSE0-RMSE_k)/RMSE0；RMSE0来自同一共享季节基线及D*。另报三年等权宏平均gain-versus-displacement曲线，不按不同n加权、不选择best k。

逐绝对位移a报告g(+a)-g(-a)，正负差仅描述较早/未来信息的不对称。near组固定{-7,-3,0,3,7}，far组固定{-90,-60,60,90}；报告near均值−far均值、g(0)−各far gain、far绝对增益及far均值/g(0)。g(0)≤0时保留绝对值与差值，ratio标NA；远位移gain为负不截成0。三年全部并列，峰形只在此固定网格分辨率上描述，±14/±30也完整展示。

没有新增用于追溯修改2%主规则的安慰剂显著性阈值；不把12个k当随机样本做p值，不用最大峰选择新lag。若主比较成立只先支持L1；若真实对齐/近零相对固定far呈稳定优势，可讨论描述性L2，但须报告各年方向、全部曲线及掩码条件。若placebo-compatible、远错位仍相似或不同年份模式不一致，L2证据不足，可能仅保留实际支持的L1。反向未来优势、平坦曲线、残留季节与自相关均必须披露，不反调窗口。

即便出现尖锐近零峰也不能排除共同天气事件或证明河道传播；没有实测日界与独立强迫控制，不能给出L3/L4、亚日时滞、传播速度或因果贡献。新增检验决定解释边界，不替代主实验判定。
