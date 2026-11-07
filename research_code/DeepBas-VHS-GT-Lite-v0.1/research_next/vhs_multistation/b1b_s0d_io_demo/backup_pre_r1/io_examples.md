# S0D 输入输出示例摘要（SYNTHETIC_DEMO_ONLY；PROPOSED）

由 `tools/gen_io_examples.py` 于 2026-10-17T13:21:13+0800 在 PC-20260821NZLG（Python 3.14.7）实际运行生成；完整响应见 `io_examples.json`。

| 场景 | 请求 | HTTP | s0d_status | error.alias / code | prediction |
|---|---|---|---|---|---|
| F1 合法合成站点 | `GET /api/vhs/stations/DEMO_TARGET_A` | 200 | BLOCKED | - | null |
| F1 不存在站点 -> UNKNOWN_STATION | `GET /api/vhs/stations/DEMO_NOT_EXIST` | 404 | UNKNOWN_STATION | UNKNOWN_STATION / VHS-E002 | null |
| F1 非法输入 -> INVALID_REQUEST | `GET /api/vhs/stations/bad%20id%3B` | 400 | INVALID_REQUEST | INVALID_REQUEST / VHS-E003 | null |
| F1 未登记数据集版本 -> UNKNOWN_DATASET | `GET /api/vhs/stations/DEMO_TARGET_A?dataset_version=9.9` | 404 | UNKNOWN_DATASET | UNKNOWN_DATASET / VHS-E004 | null |
| F2 上游河网（主干+支流+人工输水+snap 不确定） | `GET /api/vhs/stations/DEMO_TARGET_A/network` | 200 | CONDITIONAL | - | null |
| F2 环路测试图 -> CYCLE_DETECTED | `GET /api/vhs/stations/DEMO_CYCLE_X/network` | 200 | BLOCKED | - | null |
| F3 准入：目标 Q 封存 + 许可未知 + snap 未认证 | `GET /api/vhs/stations/DEMO_TARGET_A/audit` | 200 | BLOCKED | - | null |
| F3 准入：数据完整但许可未知（不能 PASS） | `GET /api/vhs/stations/DEMO_QC_LICENSE_UNKNOWN/audit` | 200 | UNKNOWN | - | null |
| F3 准入：QC 缺失 | `GET /api/vhs/stations/DEMO_QC_MISSING/audit` | 200 | UNKNOWN | - | null |
| 合成演示序列 | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-14` | 200 | SYNTHETIC_DEMO_ONLY | - | null |
| 合成演示：start>end | `GET /api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-14&end=2020-01-01` | 400 | INVALID_REQUEST | INVALID_REQUEST / VHS-E011 | null |
| F4 预测请求（普通） | `POST /api/vhs/predict` | 403 | NOT_AUTHORIZED | - | null |
| F4 预测请求（试图越权：authorized/mode/model/force） | `POST /api/vhs/predict` | 403 | NOT_AUTHORIZED | - | null |
| F4 预测请求（换成准入 PASS 的合成站） | `POST /api/vhs/predict` | 403 | NOT_AUTHORIZED | - | null |
| F4 预测请求（JSON 解析错误） | `POST /api/vhs/predict` | 400 | NOT_AUTHORIZED | INVALID_REQUEST / VHS-E011 | null |
| 静态目录穿越尝试 | `GET /../demo_core.py` | 404 | ROUTE_NOT_FOUND | ROUTE_NOT_FOUND / VHS-E011 | null |

| CLI 命令 | 退出码 | s0d_status | prediction |
|---|---|---|---|
| `python -B demo_cli.py station DEMO_TARGET_A` | 0 | BLOCKED | null |
| `python -B demo_cli.py network DEMO_TARGET_A` | 0 | CONDITIONAL | null |
| `python -B demo_cli.py audit DEMO_TARGET_A` | 0 | BLOCKED | null |
| `python -B demo_cli.py demo DEMO_TARGET_A --start 2020-01-01 --end 2020-01-14` | 0 | SYNTHETIC_DEMO_ONLY | null |
| `python -B demo_cli.py predict DEMO_TARGET_A` | 3 | NOT_AUTHORIZED | null |
| `python -B demo_cli.py station DEMO_NOT_EXIST` | 1 | UNKNOWN_STATION | null |
