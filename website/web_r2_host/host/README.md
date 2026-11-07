# VHS v0.6 · 虚拟水文站四层科研平台

> 打开网站后十秒内应当理解：**研究区域在哪里 → 使用哪些数据 → 采用什么模型 → 模拟得到什么 → 模型效果究竟怎么样。**
> 结果层是本版最高优先级；没有模型运行，就不出现任何模拟曲线或评估数字。

独立目录：E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform
基线：v0.5.1（Codex P0/P1 修复版，476 项测试通过）→ 本版在其上重构信息架构，未重新引入旧漏洞。

## 1. 启动 / 停止

~~~powershell
powershell -ExecutionPolicy Bypass -File run_vhs.ps1      # 后台启动 127.0.0.1:8775
powershell -ExecutionPolicy Bypass -File stop_vhs.ps1     # 按 PID 文件停止（仅本实例）
~~~

浏览器打开 <http://127.0.0.1:8775/>。
8772(v0.4) / 8773(v0.5) / 8774(v0.5.1) 不受影响；脚本会拒绝占用这些端口。

前置：Python 3.12+（脚本依次尝试 VHS_PYTHON、DSH 运行时、WorkBuddy 运行时、PATH 上的 python）。
纯标准库实现，无第三方依赖、无网络访问、仅绑定回环地址。

## 2. 四层信息架构（一级导航）

| 一级入口 | 页面 | 本轮真实功能 |
| --- | --- | --- |
| 研究概览 | #/overview | 研究区域与任务、固定河段 vs 浏览测站、空间概览、核心水文过程线、模型状态、四层入口 |
| 空间图层 | #/layers | 五类图层树（河网/DEM/水文站/气象站/行政区）、状态分离、真实 EPSG:3035 站点地图（LamaH）、站点点选摘要、合成预览隔离 |
| 数据层 | #/data | 数据目录、时间覆盖矩阵、站点历史（流量/气象/水量平衡）、遥感、统计年鉴、文献、质量与科研证据 |
| 模型层 | #/model | 架构卡片与状态定义、参数配置（可保存 JSON）、运行工作流（8 步 + 403 门禁） |
| 结果层 | #/results | 站点结果（大图过程线）、模型评估（N/A 空状态）、空间结果（接口契约）、科研报告（Markdown/MD 下载） |

子页面（二级）：
- 数据层：站点历史数据 / 遥感数据 / 统计年鉴 / 文献材料 / 质量与科研证据
- 模型层：模型架构 / 参数配置 / 运行方式
- 结果层：站点结果 / 模型评估 / 空间结果 / 科研报告
- 质量证据：QC 错误码可过滤、可分页、可展开，来源文件 SHA-256 与单位状态集中呈现

## 3. 双研究区独立管理

| 项 | SYRDARYA | LAMAHCE |
| --- | --- | --- |
| 命名空间 | SYRDARYA:16037 | LAMAHCE:58 |
| CRS | GIS_PENDING（不套用欧洲坐标系） | EPSG:3035（投影米） |
| 授权模式 | 老师提供 CSV，只读本地展示 | 开放元数据 |
| 可展示序列 | 月 Q / 年 W / 气象 / 遥感 / 水量平衡 | 无（sealed_runoff 未授权） |
| 可绘制空间数据 | 无（不编造站点/河流/DEM） | 882 个真实投影站点 |

数据接口按数据集隔离：跨数据集取号直接 400/404，不按数字匹配（SYRDARYA:16037 与 LAMAHCE:58 永远不是同一站）。

## 4. 空间状态：两个概念必须分开

- **GIS_DISPLAY_READY**：真实空间数据已加载，可以画在地图上。
- **HYDROLOGICALLY_CERTIFIED**：水文物理关系（上下游 / 连接 / 控制）已审核。

本版：LamaH-CE 站点坐标为 GIS_DISPLAY_READY，但上下游关系仍是 GRAPH_TENTATIVE，认证数为 0；
Syr Darya 全部图层 GIS_DISPLAY_NOT_AVAILABLE。合成预览单独成卡、单独坐标系（LOCAL_SYNTHETIC_BOX_0_100），
标注 SYNTHETIC_PREVIEW_ONLY，与真实地图彻底分开。

## 5. 结果层为什么是空的（真实科研状态）

- MODEL_EXECUTION = NOT_AUTHORIZED，prediction = null
- Qsim = null，预测区间 = null，模型运行记录 = null
- NSE / KGE / RMSE / MAE / PBIAS 全部 N/A，状态 NOT_EVALUATED
- 空间预测图层为空，状态 PREDICTION_LAYER_NOT_AVAILABLE
- 观测曲线是真实源表原值；缺测月份留空（MISSING / NO_RECORD_YEAR），不补零、不插值

后端的门禁无法只用前端绕过：GET/POST /api/v6/model/execute 与 /api/vhs/predict 一律 403。

## 6. 测试与截图

~~~powershell
python -B tools\run_all.py            # 12 个套件，结果写 logs\test_summary.json
python -B tools\shots.py              # 真实浏览器截图 + 路由自检（写 screenshots\、logs\ui_smoke.json）
~~~

本机实测：**521 / 521 通过，0 fail，0 skip**（含继承的 v0.5.1 回归与安全套件）。\nSHA256SUMS_v0.6.txt 覆盖代码/文档/测试/截图（logs/ 为运行期证据，单独留存 logs/test_summary.json 与 logs/integrity_v06.json）。
浏览器套件用系统已安装 Chrome（headless + 一次性 profile，仅回环），不下载任何东西。

截图（screenshots/）：
v06_01_overview_syrdarya.png、v06_02_overview_lamahce.png、v06_03_layers_syrdarya.png、
v06_04_layers_lamahce_map.png、v06_05_data_catalog.png、v06_06_data_history_flow.png、
v06_07_data_history_wb.png、v06_08_data_remote.png、v06_09_data_quality.png、
v06_10_data_yearbook.png、v06_11_model_architecture.png、v06_12_model_config.png、
v06_13_model_workflow.png、v06_14_results_station.png、v06_15_results_evaluation.png、
v06_16_results_spatial.png、v06_17_results_report.png、v06_18_results_lamahce.png、
v06_19_layers_800px.png、v06_20_results_report_800px.png，
以及交互截图 v06_ui_01..12（含点选站点摘要、配置保存、403 拒绝）。

## 7. 文件结构

~~~text
server.py                 HTTP 服务（v0.5 路由 + /api/v6 四层路由 + 403 门禁）
platform_v06.py           四层平台 API（概览/图层/数据/模型/结果/证据）
vhs_core.py               LamaH-CE 开放元数据存储（882 站）
syrdarya_adapter.py       Syr Darya 六文件只读适配器（不可变快照 + QC）
syr_api.py                /api/vhs/datasets/* 历史/遥感/平衡/质量/科研
science_views.py          科研口径（QC 闭合、双分母、α 残余、单位）
provenance_snapshot.py    快照与哈希校验（fail closed）
http_policy.py            Host/Origin/CORS/安全头
static_guard.py           静态文件白名单与路径逃逸防护
static/                   index.html + styles.css + app.js + 5 个 view_*.js
tests/                    12 个套件（继承 10 + 新增 2）
tools/run_all.py          一键测试；tools/shots.py 截图；tools/cdp.py 浏览器驱动
research/, research_ready/, manifest/, pilot/   科研目录与研究资格产物
docs/                     完成报告、授权清单、科研基线下一步
logs/, screenshots/       测试与截图证据
~~~

## 8. 与 v0.5 的界面 / 功能改进

1. 一级导航从“工作台 + 分页签”改为 **概览 / 空间 / 数据 / 模型 / 结果** 五段科研叙事。
2. 首页首屏给出研究区、任务、固定河段、浏览测站、空间概览、核心过程线、模型状态，十秒可读。
3. 结果层升级为一级入口并默认进入站点结果大图；过程线、评估、空间、报告四个子页。
4. 新增时间覆盖矩阵（40 站 × 11 离散年份 + 气象/遥感/水量平衡变量行），空格不是零值。
5. 新增统计年鉴 / 文献材料目录契约（未授权即如实为空，不生成论文条目）。
6. 新增模型参数配置器（输入/输出/时滞/训练测试年份/正则/种子/版本）并可保存 JSON。
7. 新增模型运行 8 步工作流，运行按钮返回后端 403 原文。
8. 新增科研报告页（Markdown 渲染 + 下载），逐项标注“未执行”。
9. QC 详情下沉到二级页面，支持错误码/严重度过滤与分页。
10. 保留并回归验证：静态目录越界防护、Host/Origin 策略、双数据集不混用、α 情景残余分列、单位 UNKNOWN 不臆造、缺测不画 0、800px 不横向溢出、前进后退同步。

## 9. 本轮没有做的事（明确边界）

- 没有训练、评分、推理任何真实径流模型；没有生成任何模拟值。
- 没有读取 sealed_runoff / quarantine / 未授权的 GIS 矢量、DEM 或统计年鉴内容。
- 没有修改 v0.5 / v0.4 / 老师原始 CSV / 历史科研报告 / DeepBas 主工程。
- 没有引入新的外部依赖或联网请求。

详见 docs/COMPLETION_REPORT.md、docs/DATA_AND_AUTHORIZATION_REQUEST.md、docs/SCIENCE_BASELINE_NEXT.md。
