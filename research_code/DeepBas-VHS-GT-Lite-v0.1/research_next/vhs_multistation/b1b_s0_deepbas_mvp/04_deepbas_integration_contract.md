# VHS-NEXT-B1B-S0｜04 DeepBas 集成契约草案

日期：2026-10-17（Asia/Singapore）。状态：**PROPOSED 候选草案，等待 DeepBas 平台组确认**。本轮没有访问、修改或部署 DeepBas 平台源码、环境或数据库；**不声称已完成平台集成**。机器可读部分见 `vhs_response.schema.json`、`05_api_contract_example.json`、`vhs_contract.py`。

## 1. 五类功能划分（核心）

| 类别 | 内容 | 证据等级 |
|---|---|---|
| **A. 现有平台已确认功能** | 本轮**没有任何一项能被独立确认**。用户陈述 DeepBas 界面已有 GIS 地图、水文站、河网、ERA5-Land 气象查询、HBV/SWAT 等功能（截图可见）。截图可见不等于有标准 API。 | 用户陈述；API 为 UNKNOWN |
| **B. 需平台组协议才能确认的接口** | ①站点图层查询（ID↔要素映射、CRS）；②河网图层与河段 ID 体系；③ERA5-Land 查询接口（变量、时区、聚合方式）；④外部服务注册/插件或 HTTP 调用方式；⑤用户身份与角色/权限传递；⑥审计日志落点与保留策略；⑦地图图层注入与图表组件；⑧合成演示横幅的强制显示 | PROPOSED，全部待确认 |
| **C. 用户可独立完成的 Python 科研模块** | 契约校验器与防泄漏守卫（本轮已写，`vhs_contract.py`）；官方元数据→拓扑/准入登记表生成器；依赖组与对照候选计算；数据角色与许可登记；合成数据测试 | 校验器 VERIFIED（本轮实测）；其余 PROPOSED |
| **D. 当前可展示的元数据** | 站点 ID/名称/坐标（附 CRS 与数据集署名）、流域边界、上游关系与证据等级、依赖组、准入状态与阻断原因、证据引用、许可状态。LamaH-CE 许可冲突未解决前，仅限内部科研展示，不做公开再分发（CONDITIONAL） | PROPOSED；许可状态 VERIFIED 为 CONDITIONAL |
| **E. 未来才允许展示的真实流量估计** | 任何真实站点的预测序列、不确定性区间、C0/C1/C2 比较结果、技能指标 | NOT_AUTHORIZED |

## 2. 分工（PROPOSED）

- **DeepBas 平台**：地图与站点选择 UI、图层渲染、用户认证、调用 VHS 服务、按状态渲染（徽章、横幅、阻断面板）、平台侧日志。不计算准入、不接触封存数据。
- **VHS Python 服务**：F1–F3 元数据计算与响应组装；契约校验；防泄漏守卫；准入登记表版本管理；未来（独立授权后）F4 调用封装。不修改平台数据库。
- **科研流程（离线）**：生成并冻结准入登记表与拓扑证据；产出 evidence_refs；任何真实预测/评分须独立授权。

## 3. 接口草案（PROPOSED；传输方式待平台组确认，HTTP 只是示例）

- `GET /vhs/v0/station-status?dataset_id=…&dataset_version=…&target_station_id=…` → 状态响应或错误响应；
- `POST /vhs/v0/locate`（body：坐标对象＋CRS＋region_scope）→ 候选断面列表（snap 状态），需用户确认后再查 station-status；
- `GET /vhs/v0/prediction`：**S0 不开放**；未来返回同一响应结构中的 `prediction` 字段；未授权时只返回 `prediction_authorized.status=NOT_AUTHORIZED` 与 `prediction=null`。
- 不预先规定响应时间指标（项目组没有依据）。

## 4. 字段（与 Schema 对应）

| 字段 | 类型 | 说明 |
|---|---|---|
| api_version | string | 当前 `vhs-contract-0.1.0-draft` |
| dataset_id / dataset_version | string | 例：真实使用时为 `LamaH-CE` / `1.0`（Zenodo 5153305）；示例中一律 `SYNTHETIC_EXAMPLE_*` |
| target_station_id | string | 数据集官方 ID；LamaH 需同时保留 ID 与 country/govnr（B1A 规则） |
| region_scope | string | `EUROPE`、`CENTRAL_ASIA` 等，用于 CRS 适用区检查 |
| coordinate_reference_system | object | `epsg`、`units`、`epsg_authority_axis_order`、`coordinate_axis_order_in_payload`、`coordinates`；缺失→E005 |
| catchment_area_km2 | object | `{value|null, status, source}`；不可信时 value=null |
| topology_status / data_readiness / license_status | object | `{status, reasons[]}`，status ∈ PASS/CONDITIONAL/BLOCKED/UNKNOWN/NOT_AUTHORIZED |
| upstream_donors / nonconnected_controls | array | 见 03 §4；距离/面积比仅在拓扑 PASS 时非空 |
| science_stage | enum | METADATA_ONLY / ADMISSION_REVIEW / PREDICTION_PROTOCOL_FROZEN / INDEPENDENTLY_VALIDATED / SYNTHETIC_DEMO_ONLY |
| prediction_authorized | object | `{status, authorization_ref, reason}`；非 PASS 时 prediction 必须 null 且 status 必须 NOT_AUTHORIZED |
| prediction | object/null | S0 政策：仅 `SYNTHETIC_DEMO_ONLY` 可非空 |
| evidence_refs / warnings | array | 证据引用与告警 |

坐标系说明（VERIFIED＋INFERRED）：LamaH-CE 站点 CSV 中名为 `lon/lat` 的列是 EPSG:3035 米制 easting/northing（B1A VERIFIED）；EPSG:3035 权威轴序为 northing, easting（INFERRED）。DeepBas 的新疆/前苏联区域不在 EPSG:3035 适用区内，应使用 EPSG:4326（声明轴序）或平台组指定的投影（UNKNOWN，需平台组给出）。契约用 `region_scope` 与 CRS 登记表检查这一点（E007）。

## 5. 错误码（PROPOSED）

| 代码 | 名称 | 场景 |
|---|---|---|
| VHS-E001 | STATION_ID_MISSING | 未提供或为空 |
| VHS-E002 | STATION_NOT_FOUND | 数据集版本中不存在 |
| VHS-E003 | STATION_ID_INVALID_FORMAT | 非法字符/过长 |
| VHS-E004 | DATASET_OR_VERSION_MISMATCH | 数据集或版本未登记 |
| VHS-E005 | CRS_MISSING | 坐标系缺失/空 |
| VHS-E006 | CRS_INVALID | EPSG 未登记、单位/轴序不一致、度数越界 |
| VHS-E007 | CRS_AREA_OF_USE_MISMATCH | 如 EPSG:3035 用于中亚 |
| VHS-E008 | SEALED_TARGET_Q_LEAK_BLOCKED | 响应或日志出现观测 Q/封存 Q/Q 派生统计键或赋值 |
| VHS-E009 | FORBIDDEN_SKILL_METRIC_FIELD | NSE/KGE/RMSE 等技能指标字段 |
| VHS-E010 | PREDICTION_NOT_AUTHORIZED_BUT_PRESENT | 未授权却带 prediction；或 S0 下非合成预测 |
| VHS-E011 | SCHEMA_VIOLATION | 缺字段、状态枚举错误等 |
| VHS-E012 | UNSUPPORTED_API_VERSION | 版本不符 |

注意：“未授权预测”本身不是错误，而是正常状态 `NOT_AUTHORIZED`；E010 只用于“未授权却出现预测值”的违规响应。

## 6. 数据访问矩阵（PROPOSED）

| 数据角色 \ 主体 | DeepBas 前端用户 | DeepBas 平台后端 | VHS 服务（S0） | 科研流程（S0） | 未来独立评分器 |
|---|---|---|---|---|---|
| OPEN_METADATA | 查看（附署名，许可 CONDITIONAL 时限内部） | 透传 | 读 | 读 | 读 |
| OPEN_FORCING | 仅看覆盖状态 | 现有 ERA5-Land 功能（用户陈述） | 读元数据 | 读表头/元数据 | 读 |
| SEALED_TARGET_Q | 禁止 | 禁止 | **禁止** | **禁止** | 仅在独立授权下、隔离环境中读 |
| AUTHORIZED_DONOR_Q_FUTURE | 禁止 | 禁止 | 仅状态 | 禁止（未授权） | 授权后读 |
| QUARANTINE | 禁止 | 禁止 | 禁止 | 禁止 | 禁止（除非另行审查） |
| UNKNOWN | 禁止 | 禁止 | 默认拒绝 | 默认拒绝 | 默认拒绝 |

隔离说明：B1A 的封存是同一 Windows 账户内的目录＋程序策略（VERIFIED），**不是 OS 级/加密/air-gapped 隔离**。真正的角色分离需要未来部署层面的权限控制，由平台组/项目持有人决定（UNKNOWN）。

## 7. 地图与站点 ID 可追踪映射（PROPOSED）

每个地图要素必须带 `(dataset_id, dataset_version, target_station_id)` 三元组与 CRS；VHS 响应原样回传三元组；平台日志按三元组＋request_id 记录。依赖组 ID 使用独立命名空间（如 `DEPGRP-…`），不得复用河流根 ID（B1A 中 `20323928` 同时代表 Rhine 根与合并组，易混淆，VERIFIED）。

## 8. 平台组需要书面回答的问题（PROPOSED）

1. 站点与河网图层是否有可编程接口？ID 体系与 CRS 是什么？
2. 外部 Python 服务以何种方式接入（HTTP、插件、批处理文件）？
3. 用户角色与权限能否传给 VHS？日志写在哪里、谁能看？
4. 地图能否渲染线型/图例区分与强制横幅？
5. ERA5-Land 查询的变量、时区、聚合与发布时刻定义？
6. 平台是否涉及商业用途（决定 LamaH-Ice 流量 CC BY-NC 等许可能否使用）？
