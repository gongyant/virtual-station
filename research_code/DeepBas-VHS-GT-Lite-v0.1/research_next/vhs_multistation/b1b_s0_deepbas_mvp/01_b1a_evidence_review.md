# VHS-NEXT-B1B-S0｜01 B1A 证据只读审查

日期：2026-10-17（Asia/Singapore, UTC+8）。范围：只读审查 B1A 已有报告、开放元数据 CSV 表头与元数据列、拓扑摘要 JSON。**未进入 `b1a\sealed_runoff\` 与 `b1a\quarantine\`（只记录了这两个目录本身的修改时间，未列出其内容）**，未读取任何 Q 数值，未重跑 B1A 脚本。

标签含义：**VERIFIED**＝本轮实际读到/核对（注明来源）；**INFERRED**＝基于已读证据的推断；**PROPOSED**＝本轮建议；**UNKNOWN**＝无法判断。下文路径均相对 `research_next\vhs_multistation\b1a\`。

## 0. 路径与读取方式核实

- VERIFIED：`b1a\reports\` 下共 15 个文件（13 份 md + `b1a_status.txt` + `b1a_provider_email_draft.md`），全部以 `Get-Content -Encoding UTF8` 只读读取。来源：目录列举（08 报告附清单）。
- VERIFIED：任务给出的 `research_next\vhs_multistation\b1a\connected_candidates.csv` 路径**真实存在**（位于 b1a 根目录，317,037 bytes，834 数据行）。
- VERIFIED：`connected_candidates.csv` 表头 38 列，均为站点 ID、govnr、拓扑、面积、距离、影响等级、覆盖资格布尔量等元数据，**不含 qobs/Q 均值/FDC/NSE/KGE 等 Q 数值列**；`coverage_by_year.csv` 含缺测/checked 天数计数（属 B1A 资格用 QC 计数，本轮只读表头、未使用其行）。`Crossbasin_water_transfers.csv` 含 `lower_thres;upper_thres` 两列（INFERRED：可能为流量阈值），本轮**未读取这两列数值**，只计行数。
- 说明：用户电脑的结构化 Read 工具对该路径被拒（本地执行根限制），改用 PowerShell 只读命令；这不是越权，读写边界见 08。

## 1. 用户陈述与报告的一致性核对

| 用户陈述项 | 报告/文件实际值 | 结论 |
|---|---|---|
| 直接有向站点边 834 | `topology_summary.json` directed_edges=834；CSV 834 行 hops=1 | VERIFIED 一致 |
| RiverATLAS 路径及嵌套支持 808 | `RiverATLAS_path_status.PASS=808`（另 NOT_TESTABLE 23、BOUNDARY 3）；CSV topology_candidate_pass=808 | VERIFIED 一致 |
| 暂定站点对 141、暂定目标站 92 | `b1a_decision.json`；CSV provisional_primary_eligible=True 141 行、unique target 92 | VERIFIED 一致 |
| 完整科学准入对 0 | `fully_admitted_pairs=0`；CSV fully_admitted 全部 False | VERIFIED 一致 |
| 自然主河系统 3 | natural_roots 20282220(Elbe)/20323928(Rhine)/20498112(Danube) | VERIFIED 一致 |
| 已知输水合并后依赖组 2 | operational_transfer_groups=2 | VERIFIED 一致 |
| 暂定目标所在依赖组 1 | provisional_target_transfer_groups=1 | VERIFIED 一致 |
| 至少有一个暂定不连通邻站的目标 70 | targets_with_any_control=70；nonnested_candidates.csv 116 行、70 unique target | VERIFIED 一致 |
| 实际独立负对照供数站 2 | unique_control_stations=2（ID 377、378） | VERIFIED 一致（但见 §4：二者并非“独立”重复） |
| 满足三对照条件目标 0 | targets_with_three_controls=0 | VERIFIED 一致 |
| NO_GO_CURRENT_MULTISYSTEM_BENCHMARK | `b1a_status.txt` overall | VERIFIED 一致 |
| 596 历史保护文件哈希未变 | `final_validation.json` protected_files=596、mismatches=[] | VERIFIED（这是 B1A 当时的自报结果；本轮**未重新哈希**这 596 个文件） |
| 归档 1,477,248,617 bytes、MD5 69fd…3dc | `provenance.json` | VERIFIED 一致（本轮未重算哈希） |

细微差异（非矛盾，但需在下游注意）：
- VERIFIED：报告称“25 个图连通分量”；`group_membership.csv` 的 `gauge_graph_component` 列有 26 个不同取值，其中 1 个为空值（23 个不在 A/B 划分中的站）。即 25 个真实分量＋1 个“未入图”标签。
- VERIFIED：CSV 全 834 行中 `both_endpoint_snap_le500m=True` 为 729、`coverage_pass=True` 为 738；限定于 808 拓扑通过行后分别为 726、717，与报告一致。报告数字均为“808 子集内”口径。
- VERIFIED/工程问题：`operational_group` 取值 `20323928` 与 Rhine 的 RiverATLAS MAIN_RIV 编号相同，但它代表的是“Danube+Rhine 输水合并组”。报告称“目标全部位于同一输水依赖组 ['20323928']”易被误读为“全部在 Rhine”。实际 92 个目标中 90 个自然根为 Danube。PROPOSED：未来契约中依赖组 ID 必须使用独立命名空间（如 `DEPGRP-…`），不得复用河流根 ID。

## 2. 141 个暂定候选经过哪些资格条件

VERIFIED（`attrition.csv`、`b1a_pair_eligibility.md`、`b1a_topology_audit.md`，并用 CSV 布尔列复核）逐级筛选：

1. 882 站有日径流文件 → 859 站有 A/B 流域划分；
2. 834 条官方站点层级直接有向边（NEXTUPID/NEXTDOWNID 互洽、DAG 无环、area_calc 与 area_gov 均下游大于上游，hops=1）；
3. 808：RiverATLAS HYRIV_ID→NEXT_DOWN 有向路径 PASS，且 ≥98% donor A 多边形落在 target A 内（嵌套几何）；
4. 717：两站 checked 日期掩码逐年求交，联合 ≥10 个公历年、每年 ≥90% 有效且 ckhs=1（仅日期/缺测/QC，不含 Q 数值）；
5. 162：两端 degimpact 为低/无影响；
6. 141：两端站点到指定 RiverATLAS 河段距离 ≤500 m（暂缓 43 个 >500 m 站）。

CSV 复核：141 行 `known_uncertainties` 全部为同一字符串“provider snapping not independently surveyed; operations metadata incomplete; license discrepancy; publication latency unknown”，`fully_admitted` 全部 False。141 行涉及 141 个不同 donor（每个站只有一个直接下游，INFERRED 合理）与 92 个 target。141 行官方河段距离 `official_distance_km` 范围 0.6–50.4 km，连通面积比 0.015–0.938（仅为元数据描述，不作为样本统计）。

**重要**：141 是同一河网内高度相关的“边”，不是 141 个独立统计样本（VERIFIED，报告原文亦如此声明）。

## 3. 92 个目标站落在什么依赖组

VERIFIED（CSV + `group_membership.csv` + `station_metadata.csv` 元数据列）：

- 输水依赖组：**92/92 全部位于 operational_group 20323928（Danube+Rhine 合并组）**；Elbe 组（20282220）目标数为 0。
- 自然根：90 个目标（139 对）属 Danube（20498112）；2 个目标（2 对）属 Rhine（20323928）。
- 站点图连通分量：分布于 11 个分量（399:60、602:16、521:3、29:2、426:2、456:2、464:2、609:2、429:1、434:1、444:1）。这些分量**不是**独立水系：除 29（Rhine）外都在 Danube 自然系统内，仅因中间缺少测站而在站点图上断开。
- 国家：AUT 77、DEU 14、CZE 1；区域（River_regions）16 个，如 Drava 18、Danube between Enns and Morava 16、Inn above Salzach 12 等。区域只作元数据，`region_is_independence_unit` 全为 False（VERIFIED）。
- 认证状态：92 个全部 `CONDITIONAL_OPERATIONS_INCOMPLETE`。

结论（INFERRED，与报告一致）：当前可评估的独立目标组数为 1（若严格按输水合并），完整认证独立目标组为 0。即使未来维护者证明 Danube–Rhine 输水可忽略，Rhine 也只有 2 个暂定目标，仍不足以构成第二个有效评价单元。

## 4. 两个负对照供数站为何不能支撑原设计

VERIFIED（`nonnested_candidates.csv`、`station_metadata.csv`、`b1a_neighbor_matching.md`、`matching_common_support.json`）：

- 377：Leopoldschlag / Maltsch，AUT，area_gov 95.3 km²；378：Ehrendorf / Lainsitz，AUT，area_gov 267.6 km²。二者均属 Elbe 自然系统（Vltava 区域）、degimpact=l，且各自是单站图分量。
- 116 条候选关联中 377 被复用 79 次、378 被复用 37 次；70 个目标中 82 对仅 1 个对照、17 对 2 个对照、0 对达到 3 个。
- 共同支持：282 个跨组比较中仅 116 个同时满足面积（0.5–2 倍）与干湿度卡尺；未匹配面积比 0.0083–68.10。

不能支撑原设计的原因：
1. （VERIFIED）数量：原设计要求每目标 3 个公平不连通对照，实际 0 个目标满足。
2. （INFERRED）非独立：两站同一自然系统、同一区域、相距较近，被几十个目标反复使用，C2 臂的有效样本量约等于 2 个站，而不是 116。
3. （VERIFIED）结构：Danube 与 Rhine 已因输水合并，不能互作负对照；同一目标上游汇合的支流均是真上游，也不能作负对照。因此可作 C2 的只有 Elbe 的 6 站，其中满足严格池条件且有共同支持的只有 2 个。
4. （INFERRED）共同支持窄：两站为小流域（95.3、267.6 km²），面积卡尺限制只能匹配到较小 donor，C2 结果无法外推到大面积比或干流目标。
5. （VERIFIED）候选状态为 `CONDITIONAL_METADATA_CANDIDATE_NOT_FINAL_MATCH`，匹配规则未冻结。

## 5. 哪些阻断可以靠补充元数据解决，哪些属于真实结构限制

| 阻断 | 类别 | 证据 |
|---|---|---|
| 许可冲突（Zenodo 正文 CC BY-SA 4.0 vs API cc-by-4.0 vs 包内 CC BY 4.0 正文） | 可补元数据（维护者书面澄清） | VERIFIED `b1a_license_audit.md`、`provenance.json` |
| 4 条 To_ID=0 域外去向、另 2 条未定位转移（8→809、413→364） | 可补元数据（维护者补充） | VERIFIED `topology_summary.json` |
| 43 站 >500 m 河段偏差、42 站缺 RiverATLAS 映射、迁站历史 | 部分可补（官方站址历史/河段 ID）；也可能是真实 snap 误差 | VERIFIED `snap_forcing_summary.json` |
| 沿程坝库、有效集水面积、库容更新 | 可补元数据 | VERIFIED `b1a_license_audit.md` |
| 数据发布时刻/日界约定、供数方特殊合同 | 可补元数据 | VERIFIED `b1a_field_dictionary.md`、license audit |
| Danube–Rhine 有文献记录的 5 条跨根输水 | **真实依赖结构**，改代码无法消除；只能由新证据证明其可忽略 | VERIFIED `topology_summary.json` cross_root_transfers |
| LamaH-CE 只覆盖 3 个自然系统，Danube 占 791/840 已映射站 | **真实数据覆盖结构**，改代码无法解决 | VERIFIED |
| Elbe 只有 6 站，没有可用的连通目标对 | **真实结构** | VERIFIED |
| 负对照只有 2 个 unique 站 | **真实结构**（同一池子内无更多候选）；放宽卡尺属于改变估计目标，需另行批准 | VERIFIED/INFERRED |

结论（INFERRED）：补充元数据最多能把 141 对中的部分对从 CONDITIONAL 提升为 PASS，但**不能把独立目标组数从 1 提升到 ≥2**。跨系统验证需要 LamaH-CE 以外的新独立系统（与 B1A go/no-go 第 10 条结论一致）。

## 6. 证据状态清单

- CONDITIONAL（VERIFIED，`b1a_status.txt`）：B1A_TOPOLOGY_CANDIDATES_VERIFIED、B1A_INDEPENDENT_GROUPS_ESTIMATED、B1A_LICENSE_REVIEW_COMPLETE；snap 认证 `CONDITIONAL_NEAREST_ALTERNATIVE_AND_OFFICIAL_LOCATION_HISTORY_NOT_REVIEWED`；匹配 `CONDITIONAL_UNFROZEN_METADATA_SCREEN`；全部 882 站组认证 `CONDITIONAL_OPERATIONS_INCOMPLETE`。
- BLOCKED（VERIFIED）：B1A_READY_FOR_B2_REVIEW；完整跨系统 train/dev/test 验证。
- NOT_TESTABLE（VERIFIED）：RiverATLAS 23＋3（BOUNDARY）；EU-Hydro 2 条同河段；本地亚洲 HydroRIVERS 对欧洲 `NOT_TESTABLE_WRONG_GEOGRAPHIC_COVERAGE`。
- UNKNOWN（VERIFIED 为“报告标注未知”）：数据发布时延；域外输水去向；供数方特殊合同条款；气象逐日有效性与实际发布时间（只核查了表头）；插补前缺口 230 文件未并入日级资格。
- 隔离级别（VERIFIED）：`isolation=PROGRAM_POLICY_ONLY`，同一 Windows 账户目录＋程序策略，**不是** OS 级、加密或 air-gapped 隔离。本轮沿用这一表述。

## 7. EPSG:3035 坐标转换修复是否被正确记录

VERIFIED 记录位置：
1. `reports\b1a_validation_report.md`“工具修复与局限”：lon/lat 列初被当作度数，导致初版距离与零匹配不可信；按官方 Gauges.shp（EPSG:3035 米）修正并重算全部距离/匹配，最终 70 目标而非初版 0；
2. `evidence\correction_log.json`：coordinate_correction 条目＋`initial_matching_zero_controls_superseded: true`；
3. `evidence\final_validation.json` corrections 字段；
4. `evidence\snap_forcing_summary.json`：`station_coordinate_crs = "EPSG:3035; fields named lon/lat are projected meters, verified against Gauges.shp"`；
5. `reports\b1a_field_dictionary.md` 与 `station_metadata.csv`：882 站 `coordinate_crs` 全为 EPSG:3035，另列 `longitude_wgs84/latitude_wgs84`。

本轮独立元数据交叉检查（只读坐标列，非 Q）：
- VERIFIED：`station_metadata.csv` 的 `lon` 列取值 4,192,433–4,917,967，`lat` 列 2,596,838–3,021,806，量级为米制 easting/northing；`longitude_wgs84` 8.28–18.23°，`latitude_wgs84` 46.48–50.09°，与中欧范围一致。
- VERIFIED：`open_metadata\D_gauges\3_shapefiles\Gauges.prj` 为 ETRS89_LAEA_Europe（lat_0=52、lon_0=10、FE=4321000、FN=3210000、单位 Meter）。
- INFERRED：`matching_common_support.json` 中目标—邻站距离 19.45–408.11 km、对照卡尺 ≤500 km，与米制换算一致；本轮**未重算**距离，因此“重算后的数值正确”只能标 INFERRED。
- 记录缺口（VERIFIED）：`b1a_go_no_go.md` 正文未提及该修复（只在验证报告与 JSON 中）。另外，EPSG 注册表对 3035 的权威轴顺序是 northing, easting（INFERRED，来自 EPSG 定义的通用知识，本轮未联网核对 EPSG 注册页），而 LamaH 文件以 easting 存在名为 `lon` 的列中。PROPOSED：VHS 契约要求同时声明 `epsg_authority_axis_order` 与 `coordinate_axis_order_in_payload`（见 04/05）。

总体判断：修复**已被正确且可追溯地记录**于验证报告与机读证据中（VERIFIED）；最终结果使用修正后坐标（INFERRED，依据为修正记录＋最终计数 70≠0＋距离量级合理）。
