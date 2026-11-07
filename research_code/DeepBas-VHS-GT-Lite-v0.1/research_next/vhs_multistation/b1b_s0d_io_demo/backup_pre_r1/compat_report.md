# VHS-NEXT-B1B-S0D｜与 B1B-S0 契约的兼容性报告

日期：2026-10-17（UTC+8）。标注：VERIFIED（本轮实测/实读）、INFERRED（推断）、PROPOSED（提议，待确认）、UNKNOWN。

## 1. 已核对的旧资产（只读，VERIFIED）

位置：`research_next\vhs_multistation\b1b_s0_deepbas_mvp\`，共 12 个文件，与 08 报告列出的名称与数量一致：01–04 md、05_api_contract_example.json（4 个示例：A/B/C/D）、06、07、08 md、vhs_contract.py（12,847 B，SHA-256 `38009ed2…e163595b`）、vhs_response.schema.json（8,666 B，`4e21e4d1…90fa1158`）、tests\test_vhs_contract.py、tests\test_run_output_windows.txt（22 项，OK，exit=0，运行于 2026-10-17 11:01:56 +08:00，`.venv\Scripts\python.exe` 3.14.7）。完整哈希见 `integrity_report.md` §3。

vhs_contract.py 中已有：`API_VERSION="vhs-contract-0.1.0-draft"`、`STATUS_VALUES`、`SCIENCE_STAGES`、`DATA_ROLES`、`SYNTHETIC_PREFIX`、`ERROR_CODES`（VHS-E001…**E012**）、`KNOWN_CRS`（4326/3035/2056）、`FORBIDDEN_Q_KEY_PATTERNS`、`FORBIDDEN_METRIC_KEY_PATTERNS`、`FORBIDDEN_LOG_TEXT`、`ContractError`、`scan_forbidden_fields`、`assert_log_safe`、`validate_crs`、`REQUIRED_TOP`、`validate_response(resp, policy="S0")`、`make_error`、`STATION_ID_RE`、`lookup_virtual_station`。

## 2. 复用方式（VERIFIED）

- `demo_core.py` 通过 `sys.path` 指向旧目录、`sys.dont_write_bytecode=True` 后 `import vhs_contract`；**未拷贝、未修改**旧文件；运行时记录旧模块 SHA-256 于每个响应的 `contract_ref.sha256`，测试断言其等于 `38009ed2…e163595b`。
- 复用：`API_VERSION`、`ERROR_CODES`、`STATION_ID_RE`、`make_error`、`validate_response`（所有对外响应的出口闸门）、`scan_forbidden_fields`（回显字段名过滤、测试）、`assert_log_safe` + `ContractError`（日志过滤）。
- 成功响应全部采用旧 `status_response` 信封（REQUIRED_TOP 17 个字段齐全），错误响应采用旧 `make_error` 结构。
- 测试 14：本轮测试中产生的全部响应（>150 个，含 HTTP 响应）对旧 `validate_response` 返回 `[]`；并用标准库实现的 JSON Schema 子集校验器（`tests/mini_schema.py`）对旧 `vhs_response.schema.json` 校验，0 错误。该 schema 实际使用的关键字（`oneOf`、`$ref`、`type`、`enum`、`const`、`required`、`properties`、`items`、`minLength`、`minItems`、`maxItems`）均被该子集支持；`$schema`/`$id`/`title`/`description`/`x-forbidden-key-policy` 为注释性关键字，未参与校验。**旧 schema 与旧校验器均未改动。**

## 3. 向后兼容的扩展（PROPOSED）

只新增字段，不改动旧字段语义（旧 schema 未设 `additionalProperties:false`，旧校验器忽略额外键）：

| 位置 | 新增字段 | 含义 |
|---|---|---|
| 顶层（所有响应） | `protocol_status`=`PROPOSED_NOT_DEEPBAS_OFFICIAL`、`protocol_note`、`data_class`=`SYNTHETIC_DEMO_ONLY`、`stage`、`function`、`contract_ref`、`s0d_status` | 原型标识与本次功能的总体状态 |
| 顶层（成功） | `s0d.station` / `s0d.network` / `s0d.audit` / `s0d.demo` / `s0d.predict` | 各功能明细 |
| 顶层（demo） | `synthetic_display_data` | 合成序列（`data_class`、`banner`、`unit`=SYN_UNIT、`is_prediction`=false、`generator`…） |
| 顶层（成功） | `target_station_name`、`river_network_ref`、`control_status`、`admission_status` | 沿用旧示例 05 中出现、但旧 schema 未定义的字段 |
| `error` | `alias`、`reason_code` | 新别名与细分原因 |
| 预测类错误响应 | `prediction_authorized`={status: NOT_AUTHORIZED} | 让"所有预测请求均返回 NOT_AUTHORIZED"在错误路径上也成立 |
| `upstream_donors[]`/`nonconnected_controls[]` | `synthetic`=true；对照另有 `match_basis`=[]、`dependency_group`=合成弱连通分量 ID | |

## 4. 错误码映射（新别名 → 旧码）

| 新别名（S0D） | reason_code 示例 | 旧码 | 旧名称 | HTTP |
|---|---|---|---|---|
| INVALID_REQUEST | STATION_ID_MISSING | VHS-E001 | STATION_ID_MISSING | 400 |
| INVALID_REQUEST | STATION_ID_INVALID_FORMAT | VHS-E003 | STATION_ID_INVALID_FORMAT | 400 |
| INVALID_REQUEST | UNKNOWN_PARAMETER、TIME_RANGE_MISSING、TIME_FORMAT_INVALID、TIME_RANGE_START_AFTER_END、TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW、TIME_RANGE_TOO_LONG、QUERY_INVALID、JSON_PARSE_ERROR、BODY_NOT_OBJECT、CONTENT_LENGTH_INVALID、CHUNKED_NOT_SUPPORTED、URL_TOO_LONG、STATION_ID_DUPLICATED | VHS-E011 | SCHEMA_VIOLATION | 400/411/414 |
| UNKNOWN_STATION | UNKNOWN_STATION | VHS-E002 | STATION_NOT_FOUND | 404 |
| UNKNOWN_DATASET | DATASET_OR_VERSION_UNKNOWN | VHS-E004 | DATASET_OR_VERSION_MISMATCH | 404 |
| ROUTE_NOT_FOUND | ROUTE_NOT_FOUND、STATIC_FILE_MISSING | VHS-E011 | SCHEMA_VIOLATION | 404 |
| METHOD_NOT_ALLOWED | USE_POST、METHOD_NOT_ALLOWED、POST_NOT_ALLOWED | VHS-E011 | SCHEMA_VIOLATION | 405 |
| REQUEST_TOO_LARGE | BODY_TOO_LARGE | VHS-E011 | SCHEMA_VIOLATION | 413 |
| INTERNAL_CONTRACT_VIOLATION | 首个违规旧码 | VHS-E011 | SCHEMA_VIOLATION | 500（测试中未出现） |
| （非错误）NOT_AUTHORIZED | — | 无（旧 04 §5：未授权是正常状态，不是错误） | — | 403 |

旧码 E005–E010、E012 在本原型中由出口闸门间接使用（若响应出现 CRS 问题、Q/指标字段或非空 prediction 即被拦截），正常运行与测试中均未触发。

## 5. 差异与待确认项（PROPOSED，需平台组/项目持有人确认）

1. **错误码数量与任务书不一致（VERIFIED）**：任务书写"E001–E010"，旧 `vhs_contract.py` 与 04 文档实际定义 **E001–E012**（另有 E011 SCHEMA_VIOLATION、E012 UNSUPPORTED_API_VERSION）。08 报告 §4 只说测试覆盖 E001–E010 的场景，并非只定义 10 个。
2. 旧码没有请求层面的时间范围、未知参数、路由不存在、方法不允许、请求体过大等错误；本原型全部映射到 E011（原义偏"响应结构违规"）。是否新增专用码（例如 E013 INVALID_TIME_RANGE、E014 ROUTE_NOT_FOUND）待确认。
3. 旧示例 D 与旧校验器允许"`prediction_authorized=PASS` + `data_class=SYNTHETIC_DEMO_ONLY`"时 `prediction` 非空，且单位写为 `m3 s-1`。本轮任务要求更严：**prediction 恒为 null**，合成序列放 `synthetic_display_data`，单位为 SYN_UNIT。本原型采用更严规则（出口闸门额外拒绝任何非空 prediction）；旧示例 D 的写法是否废弃待确认。
4. 旧 schema `relation.relation` 只有 CONNECTED_UPSTREAM / NONCONNECTED_CONTROL，没有"下游""同水系非上游"类别；本原型只在 `s0d.network.downstream_nodes` / `same_system_not_upstream` 中给出，未放入旧数组。
5. `evidence_level` 枚举没有 SYNTHETIC；本原型对合成关系一律用 PROPOSED。
6. 旧 schema 未定义 `admission_status`、`control_status`、`river_network_ref`、`target_station_name`（旧示例中有）；本原型沿用示例写法。
7. `science_stage` 用法：station/network/predict 用 METADATA_ONLY，audit 用 ADMISSION_REVIEW，demo 用 SYNTHETIC_DEMO_ONLY——语义是否符合平台预期待确认。
8. 接口路径：旧 04 草案为 `GET /vhs/v0/station-status?...`；本轮按任务书使用 `/api/vhs/stations/{id}` 等。两者都只是 PROPOSED。
9. 站点 ID：本轮按任务书使用 `DEMO_*`，未用旧示例的 `SYNTHETIC_EXAMPLE_STN_*` 前缀；dataset_id 保留旧前缀（`SYNTHETIC_EXAMPLE_S0D_DEMO`），符合旧 `SYNTHETIC_PREFIX`。
10. 预测请求无效时（站点不存在、JSON 错误等）返回旧 `error` 结构 + 额外 `prediction_authorized`，HTTP 状态为 400/404 而非 403；是否应统一为 403 待确认。
11. CRS 只使用 EPSG:4326；未演示 3035/2056 合成站点（旧测试已覆盖其校验）。
