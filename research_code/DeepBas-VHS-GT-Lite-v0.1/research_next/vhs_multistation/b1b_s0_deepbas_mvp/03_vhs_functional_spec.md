# VHS-NEXT-B1B-S0｜03 DeepBas 虚拟水文站（DeepBas-VHS）功能规格

日期：2026-10-17（Asia/Singapore）。整份文档状态：**PROPOSED（候选设计）**，没有实现到 DeepBas 平台，也没有执行任何流量估计。凡涉及 DeepBas 现有功能的描述均为**用户陈述**（截图可见功能），本轮未访问 DeepBas，无法确认有没有标准 API（UNKNOWN）。

## 0. 一句话定义（给普通软件开发者）

DeepBas-VHS 是一个“**虚拟测站准入与（未来）流量估计服务**”：用户在地图上点一个没有流量观测的河流断面或选一个目标站，服务回答五件事：
1. 这个点在官方数据里**是谁**（站点身份、坐标系、所在流域与河段）；
2. 它的**真实上游有哪些站**，有向路径证据有多强；**不连通但条件相似的对照站**有哪些；
3. 可用的输入数据（气象、静态属性、未来授权的供数站流量）**是否齐全、是否合法**；
4. 当前**科研准入状态**（PASS / CONDITIONAL / BLOCKED / UNKNOWN / NOT_AUTHORIZED）及每条阻断原因；
5. 只有在独立授权与独立验证之后，才返回**流量估计序列与不确定性**；在此之前 `prediction` 恒为 `null`，状态为 `NOT_AUTHORIZED`。

## 1. 端到端流程（PROPOSED）

```
用户选目标断面 → F1 站点身份与坐标系核验 → F2 河网拓扑与供数站/对照识别
→ F3 数据角色、质量、许可、血缘核验 → 生成科研准入状态
→ [未来，需独立授权] F4 流量估计（C0/C1/C2）→ 返回时间序列与经验证的不确定性
→ F5 DeepBas 地图与图表展示 + 审计日志
```

## 2. 数据角色（F3 的核心，PROPOSED）

| 角色 | 含义 | 当前（S0）是否可读 | 能否出现在响应中 |
|---|---|---|---|
| OPEN_METADATA | 站点 ID、名称、坐标、流域边界、层级、静态属性（已审定白名单） | 可读 | 可以（附许可署名） |
| OPEN_FORCING | ERA5-Land 等气象强迫 | 可读文件头/元数据；数值仅在未来授权任务中 | 只返回覆盖/质量状态，不返回数值 |
| SEALED_TARGET_Q | 目标站观测流量及一切由其衍生的统计、签名、模型输出 | **禁止** | **永远禁止**（键名级拦截，见 04/05） |
| AUTHORIZED_DONOR_Q_FUTURE | 经未来协议授权的供数站流量 | 禁止（未授权） | 当前只返回可用性状态 |
| QUARANTINE | 已隔离、未分类或黑名单资产（如 LamaH A5/A10/F_hydrol_model） | 禁止 | 只能返回“存在隔离资产”的计数类元数据 |
| UNKNOWN | 未经字段审查的数据 | 默认拒绝 | 不返回 |

依据：B1A 字段白/黑名单与隔离分类（VERIFIED，`b1a_field_dictionary.md`、`b1a_archive_manifest.md`）。

## 3. F1 虚拟水文站选点

- 输入：`target_station_id`（优先）或“经用户确认的目标断面位置”（必须附 CRS）；`dataset_id`、`dataset_version`；`region_scope`（研究区域标识，如 `EUROPE`、`CENTRAL_ASIA`）。
- 处理：
  1. 校验 ID 格式与存在性（不存在→`VHS-E002`；缺失→`VHS-E001`；格式非法→`VHS-E003`；数据集/版本不符→`VHS-E004`）；
  2. 校验坐标参考系：必须给出 EPSG 码、单位、权威轴序、载荷轴序；**禁止根据字段名 lon/lat 推断单位**（B1A 曾因此出错，VERIFIED `correction_log.json`）；检查 CRS 适用区与 `region_scope` 是否一致（EPSG:3035 只适用于欧洲，不适用于新疆/中亚 → `VHS-E007`）；
  3. 若为点选位置：snap 到官方河网，记录 snap 距离与候选竞争河段；超过阈值（阈值需按数据集冻结，B1A 用 500 m 作暂缓阈值）则状态 CONDITIONAL；
  4. 查询科研准入登记表（由 Python 科研模块产出、版本化）。
- 输出：站点元数据（ID、名称、数据集版本、CRS 对象）、流域与河网标识（network_id、reach_id、snap 状态）、`admission_status` 及阻断原因列表。

## 4. F2 上下游河网与供数站识别

- 输入：目标站 ID；已认证的河网拓扑（官方站点层级＋独立河网产品，如 LamaH 的 Gauge_hierarchy 与 RiverATLAS/EU-Hydro）；静态流域属性白名单。
- 处理：
  1. 在官方站点层级中找直接上游与全部祖先（区分直接边与传递闭包，B1A 中 834 直接边 vs 7701 祖先对，VERIFIED）；
  2. 用独立河网命名空间复核有向路径（B1A：RiverATLAS 808 PASS / 26 不可测，VERIFIED）；
  3. **仅当拓扑为 PASS 且来源可追溯时**才计算河段距离与集水面积比；否则字段为 `null` 并给出原因；
  4. 识别潜在不连通对照：双向无路径、不同依赖组、流域多边形无重叠、静态/气象描述符卡尺内；**不得使用目标 Q 衍生的水文签名参与匹配**；
  5. 记录人工输水/调度/snapping/边界不确定性，按依赖组（而非图分量或行政区）分组。
- 输出：`upstream_donors[]`（每项含 station_id、relation、relation_status、evidence_level、path_ref、可空的距离/面积比、data_role、access_status）；`nonconnected_controls[]`（同上，另含 dependency_group、match_basis）；`control_status`。

## 5. F3 水文数据输入与质量控制

- 允许的未来输入：ERA5-Land 等气象；地形/土壤/土地利用静态属性；合法供数站流量序列（AUTHORIZED_DONOR_Q_FUTURE）；时间索引（含时区、日界）；可用性与质量标识。
- 当前不得读取真实目标 Q（SEALED_TARGET_Q）。
- 处理：按第 2 节角色分类；核验覆盖期与重叠期（只用日期/缺测/QC 掩码，沿用 B1A 受限扫描思想）；核验许可与再分发限制；记录数据血缘（数据集 DOI、版本、文件哈希、处理脚本版本）。
- 输出：`data_readiness`（status、各角色覆盖与质量状态、lineage_refs）、`license_status`、输入是否合法。

## 6. F4 虚拟流量估计（仅设计，不执行）

- 科研问题（PROPOSED）：目标站**零历史流量校准**条件下估计其流量，并检验上游供数站是否带来**增量预测价值**。
- 比较臂：C0 不用任何供数站 Q 的共同基线；C1 真实连通上游供数站 Q；C2 公平匹配的不连通供数站 Q。三臂使用同一时间掩码、同一气象输入、同一评价分母；具体模型和统计在未来独立授权的协议中冻结（沿用 B1A 的 LEVEL_A/B/C 区分：LEVEL_C 物理路由因果不作主张）。
- 未来输出字段：预测序列（time_index, values）、时间分辨率与单位、预测模式（`REALTIME_FORECAST` 或 `RETROSPECTIVE_RECONSTRUCTION`，两者必须分轨，归档 UTC 日期不等于发布时刻）、模型 ID 与协议版本、比较臂、数据可用性说明、**经独立验证**的不确定性（若无则 status=UNKNOWN，不给区间）。
- 硬约束：未经独立验证的模型数值不得作为真实产品结果；S0 阶段仅允许 `SYNTHETIC_DEMO_ONLY` 合成演示值。

## 7. F5 DeepBas 可视化与审计（PROPOSED，需平台组确认渲染能力）

- 地图选目标站（或点选断面后确认 snap 结果）；
- 高亮真实上游河网路径（证据等级用线型区分：PASS 实线、CONDITIONAL 虚线、UNKNOWN 灰色）；
- 连通供数站与不连通对照用不同图例（如实心三角/空心圆），并显示依赖组；
- 准入状态徽章（5 种状态固定颜色＋文字，不能只靠颜色）；
- 阻断原因与数据来源面板（evidence_refs 可点击到报告/DOI）；
- 未来：只显示经验证的预测曲线；
- 合成演示：曲线与面板必须带固定横幅 `SYNTHETIC_DEMO_ONLY — 非真实流量`；
- **当前不允许绘制任何真实目标站的新预测曲线**，也不显示真实目标 Q。
- 审计：每次查询记录 request_id、站点 ID、数据集版本、返回状态、契约版本；日志经过防泄漏检查（`assert_log_safe`），不得写入 Q 值或技能指标。

## 8. 完成条件（Definition of Done，分阶段）

| 阶段 | 完成条件 | 当前状态 |
|---|---|---|
| S0（本轮） | 规格、契约草案、合成测试、证据审查齐备 | 见 06/08 |
| 元数据服务 MVP | Python 模块能对指定数据集版本返回 F1–F3 完整响应；全部站点 prediction=null；契约测试全过；地图 ID 映射可追踪 | 未开始（需平台协议） |
| 平台集成 | 平台组书面确认接口、权限、日志、图层渲染；联调用合成数据通过 | UNKNOWN / 未开始 |
| 预测能力 | 独立授权＋协议冻结＋独立评分器验证后才允许 prediction 非空 | NOT_AUTHORIZED |
