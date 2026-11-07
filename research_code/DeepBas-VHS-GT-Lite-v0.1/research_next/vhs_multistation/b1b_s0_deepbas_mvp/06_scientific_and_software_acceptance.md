# VHS-NEXT-B1B-S0｜06 科研验收与软件验收（分开判定）

日期：2026-10-17（Asia/Singapore）。本轮只做检查，**不使用 NSE、KGE 或任何模型预测结果**。

## A. 科研验收（当前仅检查）

| 检查项 | 结果 | 依据 |
|---|---|---|
| 数据来源可追踪 | PASS（LamaH-CE 日包） | VERIFIED：`provenance.json` 记录 Zenodo 5153305 v1.0、字节数、MD5、SHA-256（B1A 自报，本轮未重算哈希） |
| 站点身份与拓扑可信 | CONDITIONAL | VERIFIED：808 RiverATLAS PASS，但 snap 未独立核验、43 站 >500 m、42 站缺映射；全部组认证 CONDITIONAL_OPERATIONS_INCOMPLETE |
| 独立依赖组是否充分 | **BLOCKED** | VERIFIED：暂定目标所在依赖组 1，认证独立目标组 0 |
| C2 共同支持可行性 | **BLOCKED** | VERIFIED：仅 2 个 unique 对照（同属 Elbe），0 目标达 3 对照 |
| 目标 Q 保持在授权边界内 | PASS（本轮范围） | VERIFIED：本轮未进入 sealed_runoff/quarantine，未读 Q；B1A 的边界为程序策略级（非 OS 级） |
| 未知与失败状态如实保留 | PASS | VERIFIED：01 §6 列出全部 CONDITIONAL/BLOCKED/UNKNOWN/NOT_TESTABLE |
| 新增独立系统 | NO-GO（当前） | VERIFIED：02 中没有任何候选被证明八项满足；多个候选为 UNKNOWN，待核验 |

科研总判定：**NO_GO_CURRENT_MULTISYSTEM_BENCHMARK 维持**；新增系统可行性 = 需下一轮元数据核验（INFERRED）。

## B. 软件验收（当前检查，基于合成数据）

| 检查项 | 结果 | 依据 |
|---|---|---|
| 输入输出定义完整 | PASS（草案级） | 03、04、`vhs_response.schema.json` |
| 缺失/无效站点返回明确错误 | PASS | 合成测试 E001/E002/E003/E004（见 08 运行记录） |
| API 能报告阻断与不确定性 | PASS（字段级） | `admission_status.reasons`、`topology_status.reasons`、`prediction.uncertainty.status` |
| 地图与站点 ID 可追踪映射 | CONDITIONAL | 契约要求三元组回传；平台侧是否支持 UNKNOWN |
| 合成数据单元测试 | PASS | `tests/test_vhs_contract.py`，结果见 08 |
| 防止封存目标 Q 出现在响应与日志 | PASS（键名/赋值样式级） | 合成测试覆盖 qobs、target_q、q_mean、runoff_ratio、fdc、日志赋值样式；局限：基于键名/文本模式，不能识别改名或编码后的数值，平台层仍需权限隔离（INFERRED） |
| 未批准预测时显示 NOT_AUTHORIZED | PASS | 合成测试（含“登记表夹带预测”被强制清空） |
| 平台集成 | NOT STARTED / UNKNOWN | 无平台协议；未访问 DeepBas |
| 响应时间指标 | 不设定 | 无项目组依据 |

软件总判定：**契约草案与合成测试 PASS；平台集成未开始**。
