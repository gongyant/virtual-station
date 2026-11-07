
## R1 章节：待确认项 → 决策映射（VHS-NEXT-B1B-S0D-R1 追加；以上原文未删改）

> 任务书称"八项接口问题"，原 §5 实际列出 **11** 项；R1 按主题归并到 D1–D8（详见 `interface_decisions.md`）。状态均为 PROPOSED，非 DeepBas 官方协议，未完成正式集成。

| §5 原项 | 主题 | R1 决策 | 处理结果 |
|---|---|---|---|
| 1 | 错误码实为 E001–E012 | D5 | 保留 E001–E012 原样；任务书"E001–E010"的差异继续记录 |
| 2 | 请求层错误无专用码，均映射 E011 | D5、D6 | 运行时仍用旧码；新码 V2-E… 只写入 `schema_draft\error_codes_v0.2.draft.json`；HTTP 状态与别名一一对应 |
| 3 | 旧示例 D 允许 prediction 非空 | D2 | prediction 一律 null；旧示例 D 写法标为 deprecated draft |
| 4 | 旧 relation 枚举无下游/同水系非上游 | D1 | 旧数组不变；v0.2 草案扩展数组 `network_relations`（CONNECTED_DOWNSTREAM、SAME_SYSTEM_NOT_UPSTREAM、IN_CYCLE_TOPOLOGY_INVALID） |
| 5 | evidence_level 无 SYNTHETIC | D3、D4 | 不加 SYNTHETIC；用 `data_mode=SYNTHETIC` 表达数据性质，`certification_status=NOT_CERTIFIED` 表达未认证 |
| 6 | 旧 schema 未定义 admission_status 等字段 | D1、D3 | 写入 v0.2 草案 required；admission_status 改为对象（status + rule_basis） |
| 7 | science_stage 一字段多义 | D3 | 四字段分离；science_stage 恒 METADATA_ONLY；s0d_status 为废弃别名 |
| 8 | 接口路径与旧 04 草案不同 | D8 | 继续 PROPOSED，`interface_status=PROPOSED`，路径取舍待平台确认 |
| 9 | 站点 ID 前缀 | D1 | 不变（DEMO_*；dataset 保留旧 SYNTHETIC_EXAMPLE 前缀） |
| 10 | 无效预测请求带 prediction_authorized | D6 | 400/404 不再带；仅合法且存在的站点返回 403 NOT_AUTHORIZED |
| 11 | 只用 EPSG:4326 | D7 | 明示 `axis_order=lat,lon`，前端映射抽成纯函数并做 node/Python 一致性测试；3035/4326 混用拒绝测试保持 |

R1 新增发现：`..` 等全点号 ID 符合旧 `STATION_ID_RE`，原型不改旧正则（D1），只作字典查找返回 404；dataset 参数类型错误由 404 改为 400 `DATASET_PARAM_INVALID`（草案 V2-E107）。
