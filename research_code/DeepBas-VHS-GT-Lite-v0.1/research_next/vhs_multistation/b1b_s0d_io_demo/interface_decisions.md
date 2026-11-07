# VHS-NEXT-B1B-S0D-R1 接口决策记录（D1–D8）

> 状态：**PROPOSED**。非 DeepBas 官方协议，未完成正式集成。全部数据为 SYNTHETIC（合成），不含任何真实观测/流量数值。
> 本文件只在 `b1b_s0d_io_demo\`（下称 D）内新增；B1B-S0（`b1b_s0_deepbas_mvp\`）、B1A 与全部历史科研文件只读，未修改。
> 测试编号对应 `tests\test_r1.py` 中的测试方法（如 `R1-D1-01` = `R1_D1_SchemaCompat.test_D1_01_*`）；旧 42 项编号见 `tests\test_demo.py`（T01…T17、THTTP）。

## 1. 决策总表

| 号 | 问题 | 决策 | 实现位置 | 测试编号 |
|---|---|---|---|---|
| D1 | 原型字段/关系类别超出旧 schema（下游、同水系非上游、data_mode 等），是否改旧契约 | **不改**旧 `vhs_response.schema.json` 与 `vhs_contract.py`（SHA-256 固定检测）；所有扩展写入 v0.2 草案 `schema_draft\vhs_response_v0.2.draft.schema.json`（`x-status=DRAFT_PROPOSED_NOT_ACTIVE`）；旧数组 `upstream_donors/nonconnected_controls` 仍只用旧枚举，新类别只出现在扩展数组 `network_relations` | `schema_draft\*`、`demo_core.py`（`network_relations_v02`、`common_meta.contract_ref.draft_next`） | R1-D1-01…04、R1-ZZ-01、R1-OLD-01、T17 |
| D2 | 旧示例 D 允许 `prediction` 非空（合成序列 + PASS） | 正式字段 `prediction` **一律 null**；合成序列只在 `synthetic_display_data`（`is_prediction=false`，仅 SYNTHETIC_DEMO 操作出现）；旧示例 D 写法标为 **deprecated draft**（草案 `x-deprecated`，原型出口闸门 `finalize` 拒绝） | `demo_core.py`（`finalize`、`handle_demo`、`handle_predict`）、草案 `prediction: {type: null}` | R1-D2-01…03、R1-D1-04、R1-ZZ-01、T11、T13 |
| D3 | `science_stage`/`s0d_status` 一字段多义（阶段、数据性质、准入结论、操作类型混用） | 拆为四字段：`science_stage`（科学阶段，本原型恒 `METADATA_ONLY`）/ `data_mode`（`SYNTHETIC`）/ `admission_status`（准入结论 + `rule_basis`）/ `operation`（STATION_LOOKUP、NETWORK_QUERY、ADMISSION_AUDIT、SYNTHETIC_DEMO、PREDICT_REQUEST、UNRESOLVED）；`s0d_status` 保留为兼容别名，`deprecations[]` 写明废弃计划（v0.2 正式化时移除） | `demo_core.py`（`OPERATIONS`、`common_meta`、`build_envelope`、`DEPRECATIONS`） | R1-D3-01…03、T13（M2） |
| D4 | `evidence_level=PROPOSED` 易被误读为"已认证" | 新增 `certification_status=NOT_CERTIFIED`（顶层与每条关系）+ `certification_note`；warnings、README、网页 `#certExplain` 均写明：**PROPOSED 只表示"提议中的关系/接口"，不等于数据已获科学认证** | `demo_core.py`（`CERTIFICATION_*`、`R1_WARNINGS`）、`index.html`、`app.js`（`#fieldLine`） | R1-D4-01、R1-D4-02 |
| D5 | 请求层错误没有专用旧码 | **保留 E001–E012 原样**（运行时只输出旧码）；新错误码 `V2-E1xx…E5xx` 只写在 `schema_draft\error_codes_v0.2.draft.json`，每条带 `legacy_code` 与 `http_status` 对照；运行代码中不出现 `V2-E` | `schema_draft\error_codes_v0.2.draft.json`、`demo_core.ERROR_ALIAS_MAP/ALIAS_HTTP` | R1-D5-01、R1-D5-02、R1-ZZ-02 |
| D6 | HTTP 状态与语义：无效预测请求曾返回 400/404 同时带 `prediction_authorized=NOT_AUTHORIZED` | 状态与别名一一对应：400 INVALID_REQUEST / 404 UNKNOWN_STATION·UNKNOWN_DATASET·ROUTE_NOT_FOUND / **403 NOT_AUTHORIZED（仅对合法且存在的站点）** / 405 METHOD_NOT_ALLOWED / 413 REQUEST_TOO_LARGE（另保留 411、414、500）；**4xx（非 403）响应不带 `prediction_authorized`**，改为 `prediction_authorization_evaluated=false` + 说明"不表示存在任何授权"；`error.http_status` 与实际状态一致 | `demo_core.py`（`ALIAS_HTTP`、`RequestError`、`error_response`、`handle_predict`）、`demo_server.py` | R1-D6-01…03、R1-IN-01…06、R1-PR-01…03、T11（M1）、THTTP（M3） |
| D7 | EPSG:4326 轴序（lat, lon）与前端 SVG（x, y）容易颠倒 | 载荷 `coordinates=[lat, lon]`，`axis_order="lat,lon"`，另给只读辅助 `lon_lat`；前端映射抽成纯函数 `geo_map.js`（`VHSGeo.makeProjector`）：**x ← 经度（向东增大），y ← 纬度翻转（向北减小）**；Python 参考实现 `tests\axis_ref.py` 与 node 用同一夹具 `tests\fixtures\axis_cases.json` 对比；EPSG:3035/4326 混用、轴名不符、越界、缺轴序一律拒绝 | `geo_map.js`、`app.js`（`drawNetwork`、`#coordLine`）、`demo_core.lat_lon_from_crs`、`build_envelope.crs` | R1-D7-01…06、`tests\js\test_geo_map.js`（node）、T05/T06（旧 CRS 拒绝测试保持） |
| D8 | 原型可能被误认为 DeepBas 正式接口 | 所有响应 `interface_status=PROPOSED` + `interface_notice`；响应头 `X-VHS-Interface-Status: PROPOSED`；README/网页横幅 `#proposedBanner` 写明"**非 DeepBas 官方协议，未完成正式集成**"；静态扫描禁止任何声称已完成对接的措辞（测试 R1-D8-02 列出禁用词） | `demo_core.INTERFACE_*`、`demo_server.py`、`index.html`、`README.md` | R1-D8-01、R1-D8-02 |

## 2. 关键细节

### D2 / D6 预测请求的判定顺序（`POST /api/vhs/predict`）
1. 请求体超限 → 413；chunked → 411；Content-Type 非 `application/json` → 400 `CONTENT_TYPE_UNSUPPORTED`（v0.2 正式化时可考虑 415，草案已注明）。
2. JSON 解析失败 / 重复键 / 嵌套过深 → 400；请求体非对象 → 400 `BODY_NOT_OBJECT`；URL 带查询串 → 400 `UNKNOWN_PARAMETER`。
3. `target_station_id` 与 `station_id` 冲突 → 400 `STATION_ID_CONFLICT`；缺失 → 400 E001；格式非法 → 400 E003。
4. 若提供 `start/end`：格式/先后不合法 → 400（不检查合成演示窗口，预测本身不会执行）。
5. `dataset_id/dataset_version` 类型非法 → 400 `DATASET_PARAM_INVALID`；不匹配 → 404 UNKNOWN_DATASET（E004）。
6. 站点不存在 → 404 UNKNOWN_STATION（E002）。
7. 其余一律 **403 NOT_AUTHORIZED**，`prediction=null`；`mode/model/authorized/force/token…` 等任何附加字段（大小写、空白、连字符变体、嵌套）都不会改变结果，只在 `s0d.predict.override_attempts_ignored` 中回显键路径（含受限词的路径只计数 `override_attempts_hidden_count`，不回显）。

### D3 字段取值（本原型）
| 字段 | 取值 | 含义 |
|---|---|---|
| science_stage | METADATA_ONLY（恒定） | 科学阶段：只有元数据，没有任何经过验证的科学产出 |
| data_mode | SYNTHETIC | 数据性质：全部为合成 |
| admission_status | PASS/WARN/FAIL/… + rule_basis=SYNTHETIC_RULES… | 合成规则下的准入审查结论，不是科学认证 |
| operation | STATION_LOOKUP / NETWORK_QUERY / ADMISSION_AUDIT / SYNTHETIC_DEMO / PREDICT_REQUEST / UNRESOLVED | 本次调用做了什么 |
| s0d_status | 旧值 | **DEPRECATED_ALIAS**，计划在 v0.2 正式化时移除 |

### D7 映射公式（`geo_map.js` 与 `tests\axis_ref.py` 完全一致）
`x = left + (lon − minLon)/(maxLon − minLon) × width`（经度跨度为 0 时取 `left + width/2`）；
`y = top + (maxLat − lat)/(maxLat − minLat) × height`（纬度跨度为 0 时取 `top + height/2`）；默认画框 `{left:50, top:40, width:660, height:300}`。
夹具"东/北"用例：O(40,80)→(50,340)，E(40,81)→(710,340)，N(41,80)→(50,40)，NE→(710,40)。

## 3. 与 compat_report.md §5 的对应
compat_report §5 原有 **11** 个待确认项（任务书称"八项接口问题"，按主题归并为 D1–D8，映射见 compat_report.md「R1 章节」）。

## 4. 被修改的旧测试（`tests\test_demo.py`，逐条说明；未放松任何安全断言）

| 编号 | 位置 | 修改 | 原因 | 安全断言是否放松 |
|---|---|---|---|---|
| M1 | `T11.test_rejected_even_when_invalid` | 原期望"无效预测请求 = 400/404 且带 `prediction_authorized=NOT_AUTHORIZED`"→ 改为期望 404 UNKNOWN_STATION / 400 INVALID_REQUEST、**不带** `prediction_authorized`、`prediction_authorization_evaluated=false`、`prediction is None` | D6：非 403 的错误响应不得声称已做授权判定 | 否：`prediction is None` 保留，并新增"不得出现授权字段"断言（更严） |
| M2 | `T13.test_demo_markers` | 原断言 `science_stage=SYNTHETIC_DEMO_ONLY` → 改为 `science_stage=METADATA_ONLY`、`operation=SYNTHETIC_DEMO`、`data_mode=SYNTHETIC` | D3：四字段分离 | 否：合成标注、`is_prediction=false`、prediction null 断言均保留 |
| M3 | `THTTP.test_predict_http`（`{not json` 用例） | 增加断言 400 且不带 `prediction_authorized` | D6 | 否（新增断言） |
| M4 | `T16_StaticScan.PRODUCT` | 加入 `geo_map.js`、`tools\gen_io_examples_r1.py`；两个 io 示例生成工具只允许指向 127.0.0.1 | 新增产品文件也要接受"无外部 URL / 无 sealed / 无 0.0.0.0"静态扫描 | 否（扫描范围扩大） |

`tests\mini_schema.py` 扩展了布尔 schema、allOf/anyOf/not、maxLength、pattern、minimum/maximum、additionalProperties（旧 schema 不使用这些关键字，对旧校验结果无影响）。

## 5. 未决 / 需平台确认（PROPOSED）
- 是否把 Content-Type 错误从 400 改为 415；
- `..`、`.` 等全点号 ID 符合旧 `STATION_ID_RE`（允许 "."），原型未收紧（D1 不改旧正则），只作字典键查找 → 404，不触碰文件系统；v0.2 是否禁止待定；
- 接口路径 `/api/vhs/...` 与旧 04 草案 `/vhs/v0/station-status` 的取舍；
- `s0d_status` 别名的移除时间点。
