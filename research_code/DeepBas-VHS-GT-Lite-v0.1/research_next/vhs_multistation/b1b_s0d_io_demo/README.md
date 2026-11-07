# VHS-NEXT-B1B-S0D｜DeepBas 虚拟水文站输入/输出功能原型（SYNTHETIC_DEMO_ONLY · PROPOSED）

日期：2026-10-17（Asia/Singapore, UTC+8）。执行：Grok Bot（代用户 bean）。

> **全部为合成数据。** 本目录中的站点、坐标、河网、面积、QC/许可/拓扑状态、时间序列都是虚构的，不对应任何真实水文站，不是水文预测。
> **接口为 PROPOSED。** 只是本地原型提议，**不是 DeepBas 官方协议**，没有接入、也没有修改 DeepBas 前端/后端/数据库/部署。

## 1. 这个原型回答什么问题（VERIFIED：均有自动测试与真实运行输出）

| 功能 | 用户输入 | 模块执行 | 返回 |
|---|---|---|---|
| F1 站点信息 | station_id（可选 dataset_id、dataset_version） | 输入校验 → 查合成登记表 → 跑 F2/F3 汇总 | 站点标识、CRS（EPSG:4326，轴序 [纬度, 经度]，单位：度）、流域信息、数据来源、准入状态、阻断原因、证据等级；不存在 → `UNKNOWN_STATION`(VHS-E002)；非法 → `INVALID_REQUEST`(VHS-E001/E003/E011) |
| F2 上游河网 | 目标站 ID（+ 合成有向图） | 反向 BFS 求全部可达上游、正向 BFS 求下游、无向 BFS 求弱连通分量、三色 DFS 检测环、不确定边沿路径传播 | 上游节点及路径边序列、下游、同水系非上游、不连通对照候选、环路、不确定性、拓扑状态 |
| F3 数据质量与科学准入 | 站点 ID（合成 QC 元数据、许可、拓扑认证、目标 Q 角色来自登记表） | 显式合成规则表 R01–R08（PROPOSED/SYNTHETIC），取最差 | 元数据展示状态 + 科学准入状态（PASS/CONDITIONAL/BLOCKED/UNKNOWN）与逐条原因；预测授权恒 NOT_AUTHORIZED |
| F4 预测权限 | 目标站 ID、时间范围、任意附加字段 | 一律拒绝；越权字段（authorized/mode/model/force…）被忽略并列出 | `s0d_status=NOT_AUTHORIZED`、`prediction=null`、HTTP 403 |
| 合成演示 | station_id、start、end | 确定性公式（正弦 + 固定种子伪随机） | 序列只在 `synthetic_display_data`（单位 SYN_UNIT，非 m3/s）；`prediction` 仍为 null |
| F5 网页 | 选择站点/功能/日期，点击执行 | fetch 本机服务；服务不可用时回退内嵌离线快照 | JSON 查看区、状态/阻断原因、合成河网 SVG、合成序列 SVG |

## 2. 运行命令（Windows PowerShell，完整可复制）

```powershell
cd E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\research_next\vhs_multistation\b1b_s0d_io_demo
chcp 65001
$env:PYTHONDONTWRITEBYTECODE = "1"
$PY = "E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe"

& $PY -B demo_cli.py station DEMO_TARGET_A
& $PY -B demo_cli.py network DEMO_TARGET_A
& $PY -B demo_cli.py audit   DEMO_TARGET_A
& $PY -B demo_cli.py demo    DEMO_TARGET_A --start 2020-01-01 --end 2020-01-14
& $PY -B demo_cli.py predict DEMO_TARGET_A
& $PY -B demo_cli.py predict DEMO_TARGET_A --mode hindcast --model xxx --extra authorized=true --extra force=1
& $PY -B demo_cli.py station DEMO_NOT_EXIST
& $PY -B demo_cli.py network DEMO_CYCLE_X --graph synthetic_data\cycle_graph.json
& $PY -B demo_cli.py list

# 本地服务（只绑定 127.0.0.1；Ctrl+C 停止）
& $PY -B demo_server.py --port 8765

# 自动测试（42 项）
& $PY -B tests\test_demo.py

# 重新生成合成数据导出/离线快照、输入输出示例
& $PY -B tools\build_artifacts.py
& $PY -B tools\gen_io_examples.py
```

CLI 退出码：0 正常；1 错误响应；3 NOT_AUTHORIZED（预测被拒绝，属预期）。

## 3. 浏览器地址

- 在线（需先启动服务）：**http://127.0.0.1:8765/**
- 强制离线预览：http://127.0.0.1:8765/?offline=1 ，或直接双击打开 `index.html`（file://，自动进入"离线预览"，数据来自 `offline_snapshot.js`，由程序生成）。

## 4. HTTP 接口（PROPOSED，非 DeepBas 官方协议）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | index.html（另白名单：`/index.html`、`/app.js`、`/offline_snapshot.js`；其余静态路径一律 404） |
| GET | `/api/vhs/stations/{station_id}` | F1；可选查询参数 `dataset_id`、`dataset_version` |
| GET | `/api/vhs/stations/{station_id}/network` | F2 |
| GET | `/api/vhs/stations/{station_id}/audit` | F3 |
| GET | `/api/vhs/synthetic-demo?station_id=&start=&end=` | 合成演示（日期 YYYY-MM-DD；窗口 2020-01-01..2020-12-31；最长 92 天） |
| POST | `/api/vhs/predict` | F4；JSON 体，如 `{"target_station_id":"DEMO_TARGET_A"}`；恒 403 NOT_AUTHORIZED |

响应头含 `X-VHS-Protocol-Status: PROPOSED_NOT_DEEPBAS_OFFICIAL`、`X-VHS-Data-Class: SYNTHETIC_DEMO_ONLY`、严格 CSP。请求体上限 64 KB（超限 413）；JSON 解析错误 → INVALID_REQUEST；未知查询参数、重复参数 → INVALID_REQUEST；不支持的方法 → 405。日志为结构化 JSON，经旧契约 `assert_log_safe` 与 NSE/KGE 词过滤，不记录查询串原文。

所有成功响应都是 B1B-S0 旧契约 `virtual_station_status` 信封（经旧 `vhs_contract.validate_response` 校验），功能细节在 `s0d` 字段；错误响应为旧 `error` 结构，`error.code` 为旧码，`error.alias` 为新别名。详见 `compat_report.md`。

## 5. 合成站点（`demo_cli.py list`）

- 主图 `SYNTHETIC_MAIN_GRAPH`：`DEMO_TARGET_A`（目标）；上游 `DEMO_MID_1`、`DEMO_HEAD_1`、`DEMO_TRIB_1`、`DEMO_TRIB_2`（snapping 未认证边 E02）、`DEMO_TRIB_T`（直接汇入目标）、`DEMO_CANAL_SRC`（人工输水边 E09）；下游 `DEMO_DOWN_1`、`DEMO_OUTLET`；同水系非上游 `DEMO_TRIB_DS`、`DEMO_CANAL_BASIN_OUT`；独立水系 `DEMO_CTRL_1`、`DEMO_CTRL_2`、`DEMO_CTRL_NEAR`（地理上离目标最近，但不连通）。
- 环路测试图：`DEMO_CYCLE_X/Y/Z/W`（X→Z→Y→X 环）。
- 准入场景：`DEMO_QC_IDEAL`、`DEMO_QC_LICENSE_UNKNOWN`、`DEMO_QC_SNAP_UNCERT`、`DEMO_QC_GAPS`、`DEMO_QC_MISSING`、`DEMO_QC_UNKNOWN_FIELDS`。

## 6. 文件

| 文件 | 作用 |
|---|---|
| `demo_core.py` | 核心逻辑（F1–F4、合成序列、出口闸门）；只读 import 旧 `b1b_s0_deepbas_mvp/vhs_contract.py` |
| `demo_data.py` | 纯合成站点/河网/QC 登记表 |
| `demo_cli.py` / `demo_server.py` | CLI / 本地 HTTP 服务 |
| `index.html` + `app.js` + `offline_snapshot.js` | 单页演示（无框架无外链）+ 离线快照 |
| `synthetic_data/*.json` | 合成图与站点导出（SYNTHETIC） |
| `io_examples.json` / `io_examples.md` | 真实运行录制的输入输出示例（SYNTHETIC_DEMO_ONLY） |
| `tests/test_demo.py`、`tests/mini_schema.py`、`tests/test_run_output.txt` | 自动测试与实际执行日志 |
| `smoke/` | 用户电脑上真实启动服务的端到端冒烟日志与服务日志 |
| `tools/` | 完整性快照、产物生成、示例录制工具 |
| `integrity/` | 开发前后旧目录快照（路径/大小/mtime/SHA-256） |
| `compat_report.md` / `integrity_report.md` | 兼容性报告 / 完整性验证报告 |

## 7. 范围与限制

- VERIFIED：CLI、服务、42 项自动测试在用户电脑 `.venv` Python 3.14.7 上实际运行通过；服务只监听 127.0.0.1。
- VERIFIED（运行位置：助手 box，非用户电脑）：`node --check app.js` 语法通过；headless Chrome 渲染在线/离线页面、demo/predict/不存在站点三种交互，SVG 河网与序列图可见。**用户电脑上未做浏览器渲染验证**（未安装 node，无浏览器自动化）。
- 未实现（UNKNOWN/PROPOSED）：真实站点登记、真实河网/snapping、真实 QC 与许可判定、任何真实或回顾性流量预测、模型、评分、DeepBas 平台对接、身份认证、生产部署。
- F3 规则表与日期窗口、92 天上限均为演示用合成设定，**不是真实科学阈值**。
- 防泄漏为程序策略级（键名/文本模式），不是 OS 级隔离。



## R1 更新（VHS-NEXT-B1B-S0D-R1，追加；以上原文未删改）

> **接口状态：PROPOSED —— 非 DeepBas 官方协议，未完成正式集成。** 全部数据 SYNTHETIC（合成），`prediction` 恒为 null。
> `evidence_level=PROPOSED` / `certification_status=NOT_CERTIFIED`：PROPOSED 只表示"提议中的关系/接口"，**不等于数据已获科学认证**。

### 四个状态字段（D3）
`science_stage`（科学阶段，恒 METADATA_ONLY）· `data_mode`（SYNTHETIC）· `admission_status`（合成规则下的准入结论）· `operation`（本次调用类型）。`s0d_status` 仍保留，但已标为废弃别名。

### HTTP 语义（D6）
400 请求不合法 · 404 站点/数据集/路由不存在（UNKNOWN_STATION 等）· **403 仅用于合法且存在站点的预测请求（NOT_AUTHORIZED）** · 405 方法不允许 · 413 请求体超过 64 KiB（另有 411、414）。400/404 响应不包含 `prediction_authorized`。POST 必须带 `Content-Type: application/json`。

### 坐标（D7）
EPSG:4326，载荷 `coordinates=[lat, lon]`（`axis_order="lat,lon"`），网页画图：x ← 经度（向东增大），y ← 纬度翻转（向北向上）。映射函数在 `geo_map.js`。

### R1 命令（Windows PowerShell，在 D 目录下运行）
```powershell
$D = 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\research_next\vhs_multistation\b1b_s0d_io_demo'
$PY = 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
Set-Location -LiteralPath $D
$env:PYTHONDONTWRITEBYTECODE = '1'
& $PY -B tests\test_r1.py                 # 旧 42 项 + R1 新增项
& $PY -B demo_server.py --port 8765       # 浏览器打开 http://127.0.0.1:8765/ ，Ctrl+C 停止
& $PY -B demo_cli.py predict DEMO_TARGET_A   # 403 NOT_AUTHORIZED，prediction=null
& $PY -B tools\gen_io_examples_r1.py      # 重新生成 io_examples_r1.json / .md
```
```powershell
curl.exe -s -i http://127.0.0.1:8765/api/vhs/stations/DEMO_TARGET_A
curl.exe -s -i -X POST -H "Content-Type: application/json" --data "{\"target_station_id\":\"DEMO_TARGET_A\"}" http://127.0.0.1:8765/api/vhs/predict
```

### R1 新增文件
`interface_decisions.md`（D1–D8）· `incident_audit.md`（INC-1/2/3）· `integrity_report_r1.md` · `schema_draft\`（v0.2 草案，未生效）· `geo_map.js` · `io_examples_r1.json/.md` · `tests\test_r1.py`、`tests\axis_ref.py`、`tests\fixtures\axis_cases.json`、`tests\js\test_geo_map.js` · `tests\test_run_output_r1.txt` · `smoke\smoke_test_log_r1.txt` · `tools\integrity_snapshot_r1.py`、`tools\gen_io_examples_r1.py` · `backup_pre_r1\`（修改前备份）。
