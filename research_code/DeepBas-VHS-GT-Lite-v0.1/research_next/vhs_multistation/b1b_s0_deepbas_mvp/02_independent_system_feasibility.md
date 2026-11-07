# VHS-NEXT-B1B-S0｜02 新增独立水文系统可行性（仅元数据级桌面调查）

日期：2026-10-17（Asia/Singapore）。所有网页均为本日只读访问（WebSearch/WebFetch/curl 读取公开页面或数据仓库元数据 API），**未下载任何数据集归档**。唯一取回的文件是 CAMELS-FR 仓库内 `README.md`（9,839 bytes）和 `NEWS.md`（1,236 bytes）两个说明文本，取回到助手自己的 box 用于读许可与文件清单，未写入用户电脑。

证据等级：**OFFICIAL_EVIDENCE**＝数据集官方仓库/官方论文/官方机构页面原文；**SECONDARY_EVIDENCE**＝搜索摘要、第三方页面或间接表述；**UNVERIFIED**＝未找到官方证据。另用 VERIFIED/INFERRED/PROPOSED/UNKNOWN 标陈述本身。

## 0. 判定口径（PROPOSED，沿用 B1A 规则，不放宽）

- **图连通分量**：站点图里互相连通的一组站，可能因为中间缺测站而把同一条河拆成多个分量；不能直接当独立水系。
- **自然河流系统**：最终流入同一海洋出口或终端湖的完整河网（如 RiverATLAS MAIN_RIV）。
- **人工依赖组**：自然系统再按已知跨流域输水、运河、调水合并后的组。
- **独立评价单元**：在依赖组之上，再要求组内有合格的连通目标对、组间无共享干流/重叠集水区/已知输水，并在静态/气象条件上与其他单元有共同支持。只有这一层能用于统计外推。
- 行政区、不同数据文件、不同 region、不同数据集**都不能**直接当独立水系；同一条河（如 Rhône）出现在两个数据集中也只算一个系统。

## 1. 候选逐项评估

八项标准：①多个可识别独立河流系统；②上下游嵌套站点；③真实站点身份与有向关系；④可核验集水面积/边界；⑤足够长且重叠的日尺度观测；⑥合法使用与科研比较条件；⑦可按静态/气象条件匹配的不连通负对照；⑧与 DeepBas 科研接口兼容的元数据结构。

### 1.1 CAMELS-FR（法国）

- 版本/来源（OFFICIAL_EVIDENCE，VERIFIED）：Recherche Data Gouv，doi:10.57745/WH7FJR，元数据 API 显示最新版本 3.2（发布时间 2025-08-12T07:12:18Z，即新加坡时间 2025-08-12 15:12）；文件 7 个，含 `CAMELS_FR_attributes.zip` 9,882,622 bytes、`CAMELS_FR_geography.zip` 1,447,477 bytes、`CAMELS_FR_time_series.zip` 361,390,042 bytes。URL：https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/?persistentId=doi:10.57745/WH7FJR （访问 2026-10-17）。
- 论文（OFFICIAL_EVIDENCE）：Delaigue et al., ESSD 17, 1461–2025，https://essd.copernicus.org/articles/17/1461/2025/ （访问 2026-10-17）。654 个流域，从 4667 个候选经四项标准筛出；日流量至少 30 年（1970–2021 期间）；流域与站点由 DTM 推导，文中明确提供“station nestedness（是否嵌套、下游站数等）”信息。
- ① INFERRED/OFFICIAL：论文指出法国本土以 Loire、Seine、Garonne、Rhône 四大河为主（覆盖 >60% 本土面积），另有大量独立入海河流；但**654 站中有多少独立系统含合格嵌套对：UNKNOWN**。
- ② OFFICIAL_EVIDENCE：README 文件清单包含 `CAMELS_FR_catchment_nestedness_information.csv`（VERIFIED，见 README 第 150 行）。字段含义与是否给出直接上下游 ID：UNVERIFIED。
- ③ 站点身份：README 提到 Banque Hydro/Hydroportail 站码（VERIFIED）；有向关系是否以官方河网（CARTHAGE）为依据：SECONDARY_EVIDENCE（搜索摘要），需下一轮核验。
- ④ OFFICIAL_EVIDENCE：论文第 4 节有“集水面积一致性”筛选；提供 DTM 推导面积。
- ⑤ OFFICIAL_EVIDENCE：≥30 年日流量；站间重叠年数 UNKNOWN。
- ⑥ **许可冲突**：README 与仓库 terms 写 CC BY 4.0（OFFICIAL_EVIDENCE，VERIFIED）；但维护者在 2025-09-19 的 GitLab issue 中写“CAMELS-FR dataset is now distributed under CC BY-SA 4.0”（SECONDARY_EVIDENCE，https://gitlab.irstea.fr/HYCAR-Hydro/airgrgalaxy/airgrdatasets/-/issues/17 ，访问 2026-10-17）。各原始变量另有 Etalab 2.0、CC BY 3.0/4.0 等许可（OFFICIAL，README）。状态 CONDITIONAL。
- ⑦ INFERRED：法国气候梯度大，有可能在不同独立系统之间按静态/气象条件匹配对照；UNKNOWN，需拓扑数据确认。
- ⑧ INFERRED：CSV＋shapefile/geopackage 结构，可映射到 VHS 契约；坐标参考系 UNVERIFIED。
- 关键风险（OFFICIAL_EVIDENCE）：论文明确写道，**取水和跨流域调水信息“could not be accessed and processed easily”，未作为筛选条件**；选择标准偏向“有限人类影响”，可能剔除了大量干流下游站，导致嵌套对偏少（INFERRED）。Rhône 与 CAMELS-CH 的 Rhône 是同一系统，不能重复计。
- 综合：拓扑证据等级 **OFFICIAL_EVIDENCE（有嵌套信息文件）／计数 UNVERIFIED**。值得下一轮核验：**是（第 1 优先）**，因为元数据文件小（attributes＋geography 共约 11.3 MB），可以只读核验拓扑而不碰流量。

### 1.2 LamaH-Ice（冰岛）

- 版本/来源（OFFICIAL_EVIDENCE）：HydroShare v1.5（2025 年 2 月更新），https://www.hydroshare.org/resource/705d69c0f77c48538d83cf383f8c63d6/ ；原始资源 https://www.hydroshare.org/resource/86117a5f36cc4b7c90a5d54e18161c91/ ；论文 Helgason & Nijssen, ESSD 16, 2741–2771, 2024，https://essd.copernicus.org/articles/16/2741/2024/ （均访问 2026-10-17）。
- ① INFERRED：冰岛为岛国，多数河流独立入海；107 个流域覆盖约 46,000 km²（OFFICIAL）。**独立系统数与含嵌套对的系统数：UNKNOWN**。
- ② OFFICIAL_EVIDENCE：论文写明 A 划分中 51 个流域位于其他流域内；B/C 划分提供 HIERARCHY、NEXTUPID、NEXTDOWNID（与 LamaH-CE 同结构）。
- ③ OFFICIAL_EVIDENCE：站点坐标来自冰岛气象局（IMO）与 Landsvirkjun；流域用 Pysheds 推导。
- ④ OFFICIAL：提供流域划分；面积核验方法 UNVERIFIED。
- ⑤ OFFICIAL：v1.5 运行站流量延伸至 2023-09-30 或 2024-09-30；起始年与站间重叠 UNKNOWN。
- ⑥ OFFICIAL_EVIDENCE：**流量数据 CC BY-NC 4.0（禁止商用），其余数据 CC BY 4.0**；HydroShare 另有数据免责声明（流量站多数归 IMO/Landsvirkjun 所有）。离线科研可用（INFERRED）；若 DeepBas 存在商业用途则 BLOCKED（INFERRED）。
- ⑦ UNKNOWN：107 站规模小，冰川/泉水/直接径流三类河流差异大，共同支持可能很窄（INFERRED）。
- ⑧ OFFICIAL/INFERRED：与 LamaH-CE 同结构，B1A 已有的拓扑审计代码思路可直接复用（INFERRED）；ERA5-Land 气象与 DeepBas 现有 ERA5-Land 功能一致（用户陈述）。
- 关键风险：论文写明测站在“major hydropower facilities”所在的西南与东部高地更密（OFFICIAL）→ 水电调水/调节可能形成人工依赖（INFERRED）；67/107 站无影响（OFFICIAL），即约 37% 有影响；样本小。
- 综合：拓扑 **OFFICIAL_EVIDENCE（字段存在）／计数 UNVERIFIED**。值得下一轮核验：**是（第 2 优先）**。

### 1.3 CAMELS-CH（瑞士水文区）

- 版本/来源（OFFICIAL_EVIDENCE）：Zenodo https://zenodo.org/records/10354485 （CC BY 4.0）；论文 Höge et al., ESSD 15, 5755–5784, 2023，https://essd.copernicus.org/articles/15/5755/2023/ （访问 2026-10-17）。331 个流域（298 河流＋33 湖泊），1981-01-01 至 2020-12-31 日尺度。
- ① OFFICIAL：覆盖 Rhine、Rhône、Po（Ticino）、Danube（Inn）源区。**其中 Rhine 与 Inn(Danube) 和 LamaH-CE 属同一自然系统／依赖组（VERIFIED：B1A 的 Danube+Rhine 合并组），论文还写明 15 个奥地利流域与 LamaH-CE 重合**（OFFICIAL）。只有 Rhône 与 Ticino/Po 可能构成相对 LamaH-CE 的新独立系统（INFERRED）。
- ② OFFICIAL：明确提供嵌套层级属性 h1/h2（hierarchy_lower/upper）以及 sub_gauge_id/sub_area。
- ③ OFFICIAL：瑞士境内用 FOEN 流域划分，论文提醒出口位置可能与测站位置不完全一致；境外用 EU-Hydro。
- ④ OFFICIAL：坐标系 LV95（INFERRED：即 EPSG:2056）。
- ⑤ OFFICIAL：40 年共同期。
- ⑥ OFFICIAL：CC BY 4.0（Zenodo 页面）。
- ⑦ UNKNOWN：Rhône/Ticino 中合格目标与对照数量未知。
- ⑧ INFERRED：结构可映射，但嵌套用区间编码表示，需转换成有向边。
- 关键风险（INFERRED）：阿尔卑斯水电调节与跨流域引水普遍；Rhône 下游与 CAMELS-FR 重叠需去重。
- 综合：拓扑 **OFFICIAL_EVIDENCE**；可用于新增独立系统的部分仅 Rhône 与 Ticino。值得下一轮核验：**是（第 3 优先，限 Rhône/Ticino）**。

### 1.4 CAMELS-GB v2（英国）

- 来源（OFFICIAL_EVIDENCE）：NERC EDS EIDC，doi:10.5285/9a46d428-958f-4ac1-86eb-94eee70c0955，页面 https://catalogue.ceh.ac.uk/documents/9a46d428-958f-4ac1-86eb-94eee70c0955 （访问 2026-10-17）。671 个流域；日数据 1970-10-01 至 2022-09-30；空间参考 OSGB 1936 / British National Grid；**Open Government Licence**；数据集 2026-05-06 有更新（页面原文）。v1 论文（ESSD 12, 2459, 2020）写明 671 个流域“includes nested catchments”（OFFICIAL）。
- ① INFERRED：大不列颠有大量独立入海河流；数量 UNKNOWN。
- ② OFFICIAL：存在嵌套流域；**是否提供显式上下游 ID 字段：UNVERIFIED**。
- ③④ OFFICIAL：提供流域边界与 hydrometry 属性；有向关系需另行核验（UNVERIFIED）。
- ⑤ OFFICIAL：约 52 年日数据。
- ⑥ OFFICIAL：OGL（较宽松）。
- ⑦ UNKNOWN。⑧ INFERRED：可映射。
- 关键风险（INFERRED）：英国取水、地下水影响与跨流域调水较多；拓扑需从边界多边形推导，属于派生证据。
- 综合：拓扑 **UNVERIFIED（嵌套存在为 OFFICIAL，显式关系 UNVERIFIED）**。值得下一轮核验：可以（第 4 优先）。

### 1.5 EStreams（欧洲目录型数据集）

- 来源（OFFICIAL_EVIDENCE）：do Nascimento et al., Scientific Data 2024，https://doi.org/10.1038/s41597-024-03706-1 ；字段表 https://www.nature.com/articles/s41597-024-03706-1/tables/10 （访问 2026-10-17）。17,130 个流域、41 国、1900–2022；测站层含 `gauges_upstream`、`nested_catchments`、`watershed_group` 字段（OFFICIAL）。
- 定位：它是**目录与属性集**；摘要写明通过目录指向各国数据源以绕开再分发限制（OFFICIAL）→ 流量本身多数需从原始供数方获取，许可逐国不同（INFERRED）。EStreams 自身许可：UNVERIFIED。
- 用途（PROPOSED）：可用作跨数据集“系统归属/嵌套”索引，帮助判断 CAMELS-FR/CH/GB/DE 与 LamaH-CE 之间是否同属一个自然系统；不宜直接作 benchmark 数据源。
- 综合：拓扑 **OFFICIAL_EVIDENCE（嵌套字段）**，流量合法性 UNVERIFIED。值得下一轮核验：可以（第 5 优先，仅作索引）。

### 1.6 其他已查但不推荐进入下一轮的来源

- **CAMELS-DE v1.1.0**（OFFICIAL：Zenodo https://zenodo.org/records/16755906 ，CC BY 4.0，1582 站，1951–2020；论文 https://essd.copernicus.org/articles/16/5625/2024/ ）。论文写明只收**完全位于德国境内**、面积 5–15,000 km² 的流域，边界由 MERIT Hydro 推导；论文中**未找到显式上下游层级字段**（UNVERIFIED）。德国 Rhine/Danube/Elbe 支流与 LamaH-CE 属同一自然系统（INFERRED），Weser/Ems 等虽是另外的自然系统，但德国运河网（如 Mittellandkanal、Main-Donau-Kanal）可能形成人工依赖（INFERRED，未核验）。数据包内含 LSTM/HBV 模拟流量（OFFICIAL），属目标 Q 衍生物，必须列入黑名单。暂不推荐。
- **Caravan**（OFFICIAL：Zenodo https://zenodo.org/records/10968468 ，v1.4，CC BY 4.0，各子集另有许可文件）：是多个数据集的汇编，**LamaH-CE 本身已被并入**（更新日志：把 LamaH ID 改为 govnr），与原始来源重复；未见拓扑字段（UNVERIFIED）。不应作为独立系统来源，只能回溯到原始数据集。
- **GRDC**（OFFICIAL：https://grdc.bafg.de/about/data_policy/ ）：数据免费、需实名、**禁止商用、禁止用户再分发、禁止分发整库或大部分**。流域边界 GeoJSON 覆盖约 99% 站点（SECONDARY_EVIDENCE，搜索摘要）。没有官方有向站点图（UNVERIFIED）。对 DeepBas 的中亚/新疆区域有潜在价值（INFERRED），但“禁止再分发”与平台展示天然冲突，平台展示状态为 BLOCKED（INFERRED）。不推荐作为下一轮 benchmark 来源。
- CAMELS-US / BR / CL / AUS 等：**本轮未调查，全部 UNVERIFIED**，不作结论。

## 2. 汇总矩阵

| 候选 | ①多系统 | ②嵌套 | ③身份/有向 | ④面积/边界 | ⑤日序列 | ⑥许可 | ⑦负对照 | ⑧接口 | 拓扑证据 |
|---|---|---|---|---|---|---|---|---|---|
| CAMELS-FR | INFERRED | OFFICIAL（文件） | CONDITIONAL | OFFICIAL | OFFICIAL ≥30 年 | CONDITIONAL（BY vs BY-SA） | UNKNOWN | INFERRED | OFFICIAL_EVIDENCE |
| LamaH-Ice | INFERRED | OFFICIAL（51 嵌套） | OFFICIAL 字段 | OFFICIAL | OFFICIAL | CONDITIONAL（流量 NC） | UNKNOWN | INFERRED 高 | OFFICIAL_EVIDENCE |
| CAMELS-CH | 仅 Rhône/Ticino 新增 | OFFICIAL（h1/h2） | OFFICIAL | OFFICIAL | OFFICIAL 40 年 | OFFICIAL CC BY | UNKNOWN | INFERRED | OFFICIAL_EVIDENCE |
| CAMELS-GB v2 | INFERRED | OFFICIAL（存在） | UNVERIFIED | OFFICIAL | OFFICIAL | OFFICIAL OGL | UNKNOWN | INFERRED | UNVERIFIED |
| EStreams | 索引 | OFFICIAL 字段 | OFFICIAL 字段 | OFFICIAL | 依供数方 | UNVERIFIED | UNKNOWN | INFERRED | OFFICIAL_EVIDENCE |
| CAMELS-DE | 与 LamaH 重叠 | UNVERIFIED | UNVERIFIED | OFFICIAL | OFFICIAL | OFFICIAL CC BY | UNKNOWN | INFERRED | UNVERIFIED |
| Caravan | 汇编重复 | UNVERIFIED | UNVERIFIED | OFFICIAL | OFFICIAL | 分子集 | — | — | UNVERIFIED |
| GRDC | INFERRED | UNVERIFIED | UNVERIFIED | SECONDARY | OFFICIAL | 禁止再分发 | — | 展示 BLOCKED | UNVERIFIED |

**没有任何候选在本轮被证明八项全部满足**（VERIFIED，以上逐项）。

## 3. 本轮结论

- 科研问题 (1) 的回答：**当前 NO-GO 宣称“已构建更多合格跨水系样本”**。公开文献与仓库元数据显示存在若干**值得核验**的候选（CAMELS-FR、LamaH-Ice、CAMELS-CH 的 Rhône/Ticino 部分），但独立系统数、嵌套对数、负对照共同支持全部是 UNKNOWN，必须读取各自的拓扑元数据文件后才能判断。
- 未为凑规模放宽任何条件；不同数据集、region、国家没有被当作独立系统。

## 4. 下一轮最多五个值得核查的来源（PROPOSED，均需用户另行批准）

| 排序 | 来源 | 优势 | 关键风险 | 是否申请下一轮授权 |
|---|---|---|---|---|
| 1 | CAMELS-FR v3.2 | 官方嵌套信息文件；654 站；多独立入海系统；元数据包小（约 11.3 MB） | 许可 BY/BY-SA 冲突；调水未作筛选；属性包内含 Q 派生签名，需只读白名单文件 | **是（建议作为唯一一项最小任务，见 07）** |
| 2 | LamaH-Ice v1.5 | 与 LamaH-CE 同结构，拓扑字段齐全；ERA5-Land | 流量 CC BY-NC；水电调节；样本小；单文件能否单独下载未知 | 是，排在 CAMELS-FR 之后 |
| 3 | CAMELS-CH（仅 Rhône/Ticino） | 官方 h1/h2 层级；40 年共同期；CC BY | Rhine/Inn 与 LamaH-CE 同组；水电；与 CAMELS-FR Rhône 去重 | 视 1 的结果再定 |
| 4 | CAMELS-GB v2 | OGL；52 年；多独立入海河流 | 显式拓扑字段未证实；人类影响 | 暂不申请 |
| 5 | EStreams | 跨国嵌套与 watershed_group 字段，可做系统去重索引 | 流量需回原供数方，许可逐国不同 | 暂不申请，仅作索引备选 |
