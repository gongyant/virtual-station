# VHS-NEXT-S0｜已有物理基线与复用边界


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


1. **same-day transfer：已实现并有历史输出**。`run_bd1m_baselines.py` Model1和E4 R0；直接Q_BYBLK(t)，不重复运行。
2. **fixed lag：已实现并做0..30日历史诊断**。两个lag脚本共享结果文件；`prepare_virtual_station_bundle.py`还生成lag3面积比参考。固定lag存在不意味着统计最优lag是真实传播时长。
3. **分布式非负归一化响应核：已实现**。D5 round2的kernel_weights与M1 family支持Gaussian/Gamma-Nash，归一化核外另拟合增益a与截距b；Stage C还含自由分布式和低维核。不能把这些既有模型伪装成本轮新方法。[scripts/run_stage_d5_round2_nested_loyo.py:64](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/run_stage_d5_round2_nested_loyo.py:64) (`def kernel_weights(family, mu, width):`)
4. **线性水库：已实现并验证**。E4 route_daily的68串联R1及纯Python测试；另有D5 `s=rho*s+Q_up` 单记忆状态M2、归一化M2R。D5统计状态加gain/direct/intercept并不自动具有物理m³库容或严格质量闭合。
5. **异质串联水库R2：已实现并完成train多起点**。tau0,a,b,c经L/S/W生成，训练RMSE R1=118.905450，R2=118.849295，改善0.047227%，这是E5A登记数值。参数不可辨识与触边仅限该数据/参数化。原结果、参数和方法冻结，禁止本轮重拟合。
6. **Muskingum：当前scripts/src/tests未发现可调用实现或其单测**。文献矩阵出现术语不算实现。本轮只给规范与测试计划，不临时实现。
7. **残差修正：已存在**。E4B OLS气象修正、月气候态、Fourier6及温度/季节对照；Stage C线性与非线性残差；D5 M2C区间融雪扩展。Fourier6为冻结最终方法；D5 M2C保持reject_M2C_interval_snowmelt，不能为了新阶段重新开放其余候选。

## 可复用与无需重复

直接复用算法：纯Python route_daily（适配器提取原函数AST，方程未重写）；流量原始导入、t−1特征定义、静态L/S/W来源规则、现有评价指标实现可作审阅参考。
直接复用冻结参考：R1 tau=0.7071228027343739 day/河段、substeps3、初始化和已保存预测；Fourier6原系数和1983结果只作已完成历史证据。**不重新计算真实数据预测**。
无需重复：E4 R1/R2拟合、E1滞后扫描、Fourier/温度季节区分、E4B稳定性、1983固定方法评价、外部月一致性、D5 M1/M2嵌套LOYO、M2C单融雪变量搜索。
后续若采用历史R1作跨年外层折基线，必须标出其已经见过1978–1981 DSK标签；它在那些年份不能称outer-fold独立训练。不得偷偷为每个折重拟合历史R1以“解决”此问题。

## 实现限制与缺资料

- 参数tau是等效响应参数，非独立实测传播速度；宽度/坡度不提供完整断面、水深、糙率、闸控、侧向径流与取水。
- R2负坡度取abs并设0.01m/km下限，数学合法不保证水力方向或回水过程得到物理解读。
- 原route_daily输出日平均Q，内部S为Q·day；docstring“discharge per day”应按原方程理解为Q，不是m³/s/day。以Q=m³/s时物理库容V=86400S m³；本轮仅在新规范澄清。
- 公共router会校验非负有限Q、正tau、68节点、非负状态和dt/tau≤0.5。initialize_steady_state独立调用未完整验证tau，substeps整数类型未显式检查；后续新接口需统一契约。本轮测试通过不表示所有辅助函数非法输入均已穷举。
- 本轮只测纯Python route_daily，没有启动Numba编译/复测JIT性能，也没有验证真实水文机理有效性。

详细数学规范见 [research_next/vhs_transfer/physics/physics_baseline_specification.md](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/research_next/vhs_transfer/physics/physics_baseline_specification.md)。
