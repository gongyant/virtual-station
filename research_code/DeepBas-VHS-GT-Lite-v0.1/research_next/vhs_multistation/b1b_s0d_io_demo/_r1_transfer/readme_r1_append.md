
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
