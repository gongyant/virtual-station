# S0D-R1 输入输出示例摘要（SYNTHETIC_DEMO_ONLY；interface_status=PROPOSED）

> 非 DeepBas 官方协议，未完成正式集成。旧版示例 `io_examples.json/.md` 保留不动（其中 4xx 预测错误仍带 NOT_AUTHORIZED，是 R1 前的写法，见 interface_decisions.md D6）。

由 `tools/gen_io_examples_r1.py` 于 2026-10-17T17:27:58+0800 在 PC-20260821NZLG（Python 3.14.7）实际运行生成；完整响应见 `io_examples_r1.json`。

| 场景 | 请求 | HTTP | operation | s0d_status（废弃别名） | error.alias / code / reason | prediction_authorized | prediction |
|---|---|---|---|---|---|---|---|
| F1 合法合成站点 -> 200 | `GET /api/vhs/stations/DEMO_TARGET_A` | 200 | STATION_LOOKUP | BLOCKED | - | NOT_AUTHORIZED | null |
| F1 不存在站点 -> 404 UNKNOWN_STATION | `GET /api/vhs/stations/DEMO_NOT_EXIST` | 404 | STATION_LOOKUP | UNKNOWN_STATION | UNKNOWN_STATION / VHS-E002 / UNKNOWN_STATION | （未声明） | null |
| F1 非法站点 ID -> 400 | `GET /api/vhs/stations/bad%20id%3B` | 400 | STATION_LOOKUP | INVALID_REQUEST | INVALID_REQUEST / VHS-E003 / STATION_ID_INVALID_FORMAT | （未声明） | null |
| F1 控制字符 -> 400 | `GET /api/vhs/stations/DEMO%00X` | 400 | STATION_LOOKUP | INVALID_REQUEST | INVALID_REQUEST / VHS-E003 / STATION_ID_INVALID_FORMAT | （未声明） | null |
| F1 未知参数 -> 400 | `GET /api/vhs/stations/DEMO_TARGET_A?foo=1` | 400 | STATION_LOOKUP | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / UNKNOWN_PARAMETER | （未声明） | null |
| F1 重复参数 -> 400 | `GET /api/vhs/stations/DEMO_TARGET_A?dataset_id=a&dataset_id=b` | 400 | UNRESOLVED | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / QUERY_INVALID | （未声明） | null |
| F1 未登记数据集版本 -> 404 UNKNOWN_DATASET | `GET /api/vhs/stations/DEMO_TARGET_A?dataset_version=9.9` | 404 | STATION_LOOKUP | UNKNOWN_DATASET | UNKNOWN_DATASET / VHS-E004 / DATASET_OR_VERSION_UNKNOWN | （未声明） | null |
| F2 上游河网 | `GET /api/vhs/stations/DEMO_TARGET_A/network` | 200 | NETWORK_QUERY | CONDITIONAL | - | NOT_AUTHORIZED | null |
| F2 环路测试图 -> CYCLE_DETECTED | `GET /api/vhs/stations/DEMO_CYCLE_X/network` | 200 | NETWORK_QUERY | BLOCKED | - | NOT_AUTHORIZED | null |
| F3 准入：目标 Q 封存 + 许可未知 + snap 未认证 | `GET /api/vhs/stations/DEMO_TARGET_A/audit` | 200 | ADMISSION_AUDIT | BLOCKED | - | NOT_AUTHORIZED | null |
| F3 准入：QC 缺失 | `GET /api/vhs/stations/DEMO_QC_MISSING/audit` | 200 | ADMISSION_AUDIT | UNKNOWN | - | NOT_AUTHORIZED | null |
| 合成演示序列 -> 200 | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-14` | 200 | SYNTHETIC_DEMO | SYNTHETIC_DEMO_ONLY | - | NOT_AUTHORIZED | null |
| 合成演示：start>end -> 400 | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-14&end=2020-01-01` | 400 | SYNTHETIC_DEMO | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / TIME_RANGE_START_AFTER_END | （未声明） | null |
| 合成演示：非法日期 -> 400 | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-02-30&end=2020-03-01` | 400 | SYNTHETIC_DEMO | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / TIME_FORMAT_INVALID | （未声明） | null |
| 合成演示：超出窗口 -> 400 | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2019-12-31&end=2020-01-02` | 400 | SYNTHETIC_DEMO | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW | （未声明） | null |
| F4 预测（站点存在）-> 403 NOT_AUTHORIZED | `POST /api/vhs/predict` | 403 | PREDICT_REQUEST | NOT_AUTHORIZED | - | NOT_AUTHORIZED | null |
| F4 预测（越权字段、大小写变体、嵌套）-> 403 | `POST /api/vhs/predict` | 403 | PREDICT_REQUEST | NOT_AUTHORIZED | - | NOT_AUTHORIZED | null |
| F4 预测（准入 PASS 的合成站）-> 403 | `POST /api/vhs/predict` | 403 | PREDICT_REQUEST | NOT_AUTHORIZED | - | NOT_AUTHORIZED | null |
| F4 预测（不存在站点）-> 404 UNKNOWN_STATION | `POST /api/vhs/predict` | 404 | PREDICT_REQUEST | UNKNOWN_STATION | UNKNOWN_STATION / VHS-E002 / UNKNOWN_STATION | （未声明） | null |
| F4 预测（站点 ID 非法）-> 400 | `POST /api/vhs/predict` | 400 | PREDICT_REQUEST | INVALID_REQUEST | INVALID_REQUEST / VHS-E003 / STATION_ID_INVALID_FORMAT | （未声明） | null |
| F4 预测（日期非法）-> 400 | `POST /api/vhs/predict` | 400 | PREDICT_REQUEST | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / TIME_FORMAT_INVALID | （未声明） | null |
| F4 预测（JSON 解析错误）-> 400 | `POST /api/vhs/predict` | 400 | PREDICT_REQUEST | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / JSON_PARSE_ERROR | （未声明） | null |
| F4 预测（JSON 重复键）-> 400 | `POST /api/vhs/predict` | 400 | PREDICT_REQUEST | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / JSON_DUPLICATE_KEY | （未声明） | null |
| F4 预测（Content-Type 错误）-> 400 | `POST /api/vhs/predict` | 400 | PREDICT_REQUEST | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 / CONTENT_TYPE_UNSUPPORTED | （未声明） | null |
| F4 预测（请求体过大）-> 413 | `POST /api/vhs/predict` | 413 | PREDICT_REQUEST | REQUEST_TOO_LARGE | REQUEST_TOO_LARGE / VHS-E011 / BODY_TOO_LARGE | （未声明） | null |
| F4 GET 预测接口 -> 405 | `GET /api/vhs/predict` | 405 | PREDICT_REQUEST | METHOD_NOT_ALLOWED | METHOD_NOT_ALLOWED / VHS-E011 / USE_POST | （未声明） | null |
| PUT 站点接口 -> 405 | `PUT /api/vhs/stations/DEMO_TARGET_A` | 405 | UNRESOLVED | METHOD_NOT_ALLOWED | METHOD_NOT_ALLOWED / VHS-E011 / METHOD_NOT_ALLOWED | （未声明） | null |
| 静态目录穿越尝试 -> 404 | `GET /../demo_core.py` | 404 | UNRESOLVED | ROUTE_NOT_FOUND | ROUTE_NOT_FOUND / VHS-E011 / ROUTE_NOT_FOUND | （未声明） | null |
| 未知路由 -> 404 | `GET /api/vhs/nothing` | 404 | UNRESOLVED | ROUTE_NOT_FOUND | ROUTE_NOT_FOUND / VHS-E011 / ROUTE_NOT_FOUND | （未声明） | null |

| CLI 命令 | 退出码 | operation | s0d_status | prediction |
|---|---|---|---|---|
| `python -B demo_cli.py station DEMO_TARGET_A` | 0 | STATION_LOOKUP | BLOCKED | null |
| `python -B demo_cli.py network DEMO_TARGET_A` | 0 | NETWORK_QUERY | CONDITIONAL | null |
| `python -B demo_cli.py audit DEMO_TARGET_A` | 0 | ADMISSION_AUDIT | BLOCKED | null |
| `python -B demo_cli.py demo DEMO_TARGET_A --start 2020-01-01 --end 2020-01-14` | 0 | SYNTHETIC_DEMO | SYNTHETIC_DEMO_ONLY | null |
| `python -B demo_cli.py predict DEMO_TARGET_A` | 3 | PREDICT_REQUEST | NOT_AUTHORIZED | null |
| `python -B demo_cli.py predict DEMO_TARGET_A --mode hindcast --model xxx --extra authorized=true` | 3 | PREDICT_REQUEST | NOT_AUTHORIZED | null |
| `python -B demo_cli.py predict DEMO_NOT_EXIST` | 1 | PREDICT_REQUEST | UNKNOWN_STATION | null |
| `python -B demo_cli.py station DEMO_NOT_EXIST` | 1 | STATION_LOOKUP | UNKNOWN_STATION | null |
