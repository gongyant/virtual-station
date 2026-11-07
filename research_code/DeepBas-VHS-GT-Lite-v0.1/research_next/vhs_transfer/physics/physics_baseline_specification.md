# VHS-NEXT-S0 物理基线技术规范

状态：SPECIFICATION_ONLY；现有router的单元核验另记SYNTHETIC_UNIT_TEST_ONLY。任何新参数拟合均须下一阶段授权。本规范时间t以day表示，Q以项目约定m³/s表示（原始打印单位仍待核实），物理V为m³，内部S为(m³/s)·day，V=86400S。

## 1. 水量守恒

dV/dt_seconds = Q_in + Q_lateral − Q_out − Q_withdrawal。
若以day和S写：dS/dt_day = Q_in + Q_lateral − Q_out − Q_withdrawal。
所有流量及物理V非负，取水不得使储量负值；空间单元所有流入流出要用同一日界。初始V≥0由目标测试前上游forcing和预先规定状态给出，不得用测试目标反求。累计体积闭合为V_end−V_start=86400Σ(Q_in+Q_lat−Q_out−Q_withdraw)Δt_day，有限窗必须包含末端残余储量。
现有E4只有边界输入和终端输出，默认Q_lat=Q_withdraw=0；闭合只验证该简化系统的数值守恒，不证明真实河道没有其他水量项。仅首末Q不能独立识别侧向流入、取水及蓄水变化。

## 2. 固定时滞与仿射转移

Q_down(t)=a Q_up(t−tau)+b，tau≥0 day、a≥0无量纲、b为m³/s。整数日lag仅用当前/过去可用上游Q；分数时滞需预注册只使用已知样本的插值，禁止跨越预测起点读取未来Q。same-day tau=0用于日末历史重建；若日初预报则不能使用当日完整平均Q。
初期缺窗用合法上游warm-up或保留缺失，禁止目标Q填补。纯无源延迟要求a=1,b=0；a≠1或b≠0是经验水量增益/损失，不是已观测侧向补给。统计滞后受共同季节性、日界和库容影响，不独立识别波速。已有E1.5和Stage C，不重跑。

## 3. 分布式响应核

Q_route(t)=Σ_{k=0..K} alpha_k Q_up(t−k)，alpha_k≥0、Σalpha=1，权重无量纲、lag单位day。仅固定非负索引；若预测信息截至t−1则alpha_0禁用。固定核对完整时间积分守恒；有限窗的未释放尾部和初始历史贡献需计入，不能丢掉尾巴宣称缺水。
归一化核只能重新分配输入时间，不能创造未知侧向流量、取水或固定增益。若再乘g或加b，必须另列经验修正项与水量预算。已有D5 M1 normalized核外另有a,b；平滑核可防任意尖峰但不能独自解决信息不足。核宽度、形状和增益可能高度共线，必须用开发折、参数稳定性和物理资料评估，禁止按测试选择。

## 4. 线性水库与68河段串联

Q_out_i=S_i/tau_i，dS_i/dt_day=Q_in_i−Q_out_i；tau_i>0 day，Q_in_{i+1}=Q_out_i。
原Euler更新：先算旧S对应outflow，再 S_i←S_i+(Q_in_i−Q_out_i)dt；下游用该substep上游旧状态outflow。不能把最后河段刚更新后的S/tau误当同substep排出量。
public route_daily固定Δt_outer=1day，m个substeps，dt=1/m day；原规则dt/tau_i≤0.5，m=max(1,ceil(1/(0.5min tau)))。这是保守非负/稳定规则：标量Euler衰减稳定需dt/tau≤2，非负单调需≤1，本项目采用更严格0.5；通过稳定不等于步长误差足够小，需要收敛对照。
初始S_i=tau_i Q_BYBLK(first_train_day)，仅一次；train/validation/test连续传状态，禁用DSK状态重置。输出为一天积分的终端排出量除以1day，数值与Q·day在固定一天步长下相同；更改外步必须显式除Δt。
R1：68个tau均0.7071228027343739day，m=3；全链一阶平均时间尺度Σtau约48.08435day，不是观测传播时滞。
R2：tau_i=tau0(L_i/median L)^a(Slope_i/median Slope)^b(W_i/median W)^c。
L为km、W为m，Slope=max(abs(median_slope_m_per_m)×1000,0.01)m/km；比值无量纲。tau0>0，原优化上界30day；a∈[0,2]、b,c∈[−2,2]，原数值门槛substeps≤576。指数仅拟合参数，不是真实水力指数。截断/abs坡度不能证明正确回水机制。单上下游Q不能唯一识别68状态或四指数；保留现有不可辨识证据。
对应：scripts/bd1m_physics_routing_model.py、bd1m_e4a2_optimizer.py、E4A协议。S0适配器执行精确原函数AST，避免导入Numba写旧cache；未修改历史源码。

## 5. Muskingum（仅规范，无实现）

S=K[X I+(1−X)O]，K>0 day，0≤X≤0.5；S为Q·day，I/O为m³/s。连续守恒dS/dt=I−O。
梯形积分：O_{n+1}=C0 I_{n+1}+C1 I_n+C2 O_n；
D=2K(1−X)+dt，C0=(dt−2KX)/D，C1=(dt+2KX)/D，C2=(2K(1−X)−dt)/D，ΣC=1。
所有系数非负的充分范围为2KX≤dt≤2K(1−X)。这比仅检查有限输出更明确；不满足时拒绝/按预注册规则改离散或子河段，不能裁剪负流量来掩盖问题。减小dt不一定更好（X>0时也有下限），K/X/分段方案需一起检查。
初值O0≥0、S0=K[X I0+(1−X)O0]，不得用未来目标校准；稳态O0=I0可由合法上游指定。I_{n+1}在后验区间末重建中可已知，但在区间起点预报中未知，必须明确时间语义。原式以时点流量及梯形积分定义；不能无说明直接把日均Q当瞬时端点。侧向/取水若存在要扩展守恒方程。
K/X从可审查河道/波速先验或训练站校准获得；若目标站专属Q校准则不能C。仅L/S/W不够保证Muskingum或Muskingum-Cunge水力参数可识别；两者不能混称。本轮未实现、不生成真数据拟合。
后续测试计划：恒流稳态；脉冲非负及响应；梯形守恒+初末S；系数和1；合法/不合法dt与边界X；分段时间收敛；连续初值；目标未来扰动不改前缀。先明确日均/端点约定再写代码。

## 6. 路由+预测残差

Q_pred(t)=Q_route(t)+DeltaQ_model(t)，修正项单位m³/s，可正可负；最终若clip到0，必须独立记录裁剪引入的体积变化。修正的fit用训练残差Q_obs−Q_route；正负号不得与D5使用prediction−observation的诊断残差混用。
模型输入只能使用协议规定的上游Q、静态资料、合法过去气象/日历，不得用目标测试Q或带未知目标来源的参考量。模型初态仅训练/上游预热。残差可能包含侧向来水、取水、库容模型错误、观测误差和日界差异，不能直接解释为真实观测侧向流量。
DeltaQ使总输出不再自动满足route-only闭合；必须同时报告route数值质量误差与最终预测对观测的体积偏差，并承认未观测侧向项的不可识别性。已有Fourier6、月残差、气象OLS、Stage C/D5修正；全部冻结不重拟合。

## 一手技术来源（2026-10-11在线核对）

- [USACE HEC Muskingum routing](https://www.hec.usace.army.mil/confluence/cwmsdocs/rsum/muskingum-routing-58631546.html)：K、X及分段含义；本规范系数与非负区间由守恒/梯形代数展开给出。
- [ECMWF ERA5-Land data documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=501029136)：00UTC累计对应前一天，支持本地日处理时间约定；不证明本项目流量水文日界。
原始文件与代码哈希见data_audit/source_manifest.json与historical_before.json。
