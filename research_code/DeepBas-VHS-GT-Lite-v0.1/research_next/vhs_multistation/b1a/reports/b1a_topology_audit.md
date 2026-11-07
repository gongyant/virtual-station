# VHS-NEXT-B1A｜真实拓扑审查

日期：2026-10-16（Asia/Singapore）。本阶段仅官方数据清点、元数据/拓扑和受限日期-QC扫描；没有真实训练、性能评分或GPU任务。


882测站中859有A/B划分，形成834条直接有向站间边；DAG无环、ID唯一、NEXTUPID/NEXTDOWNID互相一致，没有未解析外部站号。所有834边的area_calc及area_gov均下游大于上游。A目标面积=自身B增量面积+各直接上游A面积的检查859/859在1%容差内通过。另23站无明确集水区，不加入图以凑数。

全部祖先→后代组合共7701，仅为图的传递闭包，不是7701独立样本；主候选CSV保留834个直接对，hops=1，确保多支流每一上游都正确标记为连通。

RiverATLAS独立命名空间HYRIV_ID→NEXT_DOWN：808路径PASS，23 NOT_TESTABLE（ID缺失）、3 NOT_TESTABLE_BOUNDARY；未把不可测计PASS。808对也通过≥98% donor A多边形位于target A的嵌套几何检查。这是官方资料间的可复核结构证据，仍不等于独立现场测站认证。

EU-Hydro OBJECT_ID→NEXTDOWNID单独核查：832 PASS、2同一河段NOT_TESTABLE，未将RL/CL字符串与HydroRIVERS数字混用。核查路径未见STRAHLER=-1的人工河段，但缺失人工渠系不能因此判无调水。详细路径结果见eu_hydro_path_checks.csv。

站点与指定RiverATLAS线的距离840站可测：约0.14–5172.36m，43站>500m；其余42站缺映射，其中19在A/B图内、23不在A/B。808对中726对两端≤500m。500m只用于暂缓大偏差候选，剩余仍未核对竞争河段、迁站与日界时效，不能叫可靠snapping全面PASS。

本地原HydroRIVERS为亚洲图层，对欧洲对照为NOT_TESTABLE_WRONG_GEOGRAPHIC_COVERAGE；不额外下载欧洲图层。使用的是此次官方包自带RiverATLAS，不能冒称已用本地亚洲文件交叉验证。

降级/未核实对全部保留在connected_candidates.csv，并明确fully_admitted=false。沿程坝库、灌渠、回流、支流观测站及物理行程仍需复核。真实结构候选808，完整准入0；两者不得混报。
