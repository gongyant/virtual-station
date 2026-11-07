# VHS v0.6 完成报告（含完整性校验与验收对照）

- 交付日期：2026-10-25（Asia/Singapore）
- 新版本目录：E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform
- 开发基线：v0.5.1_codex_fixes（Codex P0/P1 修复版，476 项测试通过）——先核对后采用，未重新引入旧漏洞
- 运行地址：http://127.0.0.1:8775/
- 本机环境：Windows，Python 3.12.14，Chrome（headless CDP），仅回环访问

## 0. 一句话结论

四层信息架构（研究概览 / 空间图层 / 数据层 / 模型层 / 结果层）已落地为可运行网站；
结果层成为一级入口并以大尺寸观测过程线为首屏主体；**没有任何模拟值、评估指标或空间预测被编造**，
所有空白都以明确状态呈现（NOT_AUTHORIZED / NOT_GENERATED / NOT_EVALUATED / PREDICTION_LAYER_NOT_AVAILABLE）。

## 1. 基线核对（阶段 A）

| 检查 | 结论 |
| --- | --- |
| v0.5.1 是否存在且经过测试 | 存在；logs/test_summary.json 记录 476/476 通过；含静态路径越界与 Host/Origin 修复 |
| 是否采用为基线 | 采用。复制其全部后端模块、测试、research_ready 与 manifest，版本号升至 0.6.0 |
| 旧漏洞是否重新出现 | 未出现：static_guard/http_policy 原样继承并被 v0.6 安全用例再次验证（V42–V46、78 项 v0.5.1 安全套件） |
| 允许读取的数据 | 仅老师提供的六个 Syr Darya CSV（只读）+ LamaH-CE 开放元数据；未打开 sealed_runoff/quarantine/未授权 GIS/年鉴内容 |
| 写入范围 | 仅 v0.6 新目录；v0.4、v0.5、v0.5.1、老师原始 CSV 一字节未改（见第 6 节） |

## 2. 四层架构与真实功能（阶段 B/C）

| 层 | 页面 | 真实数据/行为 | 明确为空的状态 |
| --- | --- | --- | --- |
| 研究概览 | #/overview | 研究区域、任务类型、固定河段 16037→16039、浏览测站切换、空间概览、核心过程线、模型状态、五入口 | LamaH 侧无授权序列 |
| 空间图层 | #/layers | 五类图层树（19 个图层定义）、状态双轨、LamaH 882 个 EPSG:3035 真点位可点选、站点点选摘要 + 跳转 | Syr Darya 五类图层全部 GIS_DISPLAY_NOT_AVAILABLE；DEM/气象站/行政区未授权 |
| 数据层 | #/data | 数据目录、40 站×11 年覆盖矩阵、月流量/年径流（源值 vs 派生值）、气象月聚合、水量平衡 α 情景与残余分列、遥感 A–G/KZDAM、QC 分页过滤、文件 SHA-256 | 统计年鉴 NOT_READ、文献 0 条（不生成条目） |
| 模型层 | #/model | SYR-B0/B1/B2 卡片、状态定义、8 类后续架构标注 NOT_IMPLEMENTED、参数配置可编辑并保存 JSON、8 步工作流 | 训练/评估/执行全部 NOT_AUTHORIZED |
| 结果层 | #/results | 站点大图观测过程线（缺测留空）、评估指标 N/A 空状态、空间结果契约、科研报告（Markdown 渲染 + 下载） | Qsim=null、PI=null、NSE/KGE/RMSE/MAE/PBIAS=N/A、空间预测层为空 |

二级页面：站点历史 / 遥感 / 统计年鉴 / 文献 / 质量与证据 / 模型架构 / 参数配置 / 运行方式 / 站点结果 / 模型评估 / 空间结果 / 科研报告。

## 3. 结果层（设计重点）实现要点

1. **视觉顺序**：当前研究任务 → 大尺寸观测过程线 → 观测摘要 KPI → 年径流源值/派生值 → 下一步入口；右侧为口径摘要。
2. **过程线组件**：观测为唯一真实曲线；Qsim 图例存在但明确标注“未生成”；红底表示该年无记录（NO_RECORD_YEAR）；底部短竖线表示序号占位嫌疑（保留原值、不绘制）；缺失值断线而不归零。
3. **指标组件**：五个指标全部 N/A + NOT_EVALUATED，并展示每个指标必须携带的 model_version / dataset_version / period / common_sample_ids（当前均 null）。
4. **空间结果**：先给统一字段契约（含 qsim、qsim_status、model_version、uncertainty），再明确“真实模拟结果尚未产生”。
5. **报告**：11 节结构，已执行部分（研究区、数据来源与哈希、质量摘要、版本）与未执行部分（训练、评估、模拟、不确定性）逐项分离；可复制 Markdown、可下载 .md。

## 4. 界面与交互改进（阶段 D）

- 一级导航由工作台改为一句话科研叙事；结果层置为高亮入口。
- 右侧摘要栏固定显示数据集/CRS/快照/权限域/模型状态，首页不再铺开数百条诊断。
- 哈希路由：前进/后退保持图层与内容同步（浏览器套件 B18 验证）。
- 选择器带真实年份/测站；α 与半宽切换即时重算且“固定源残余 vs 情景残余”分列（B12 验证）。
- 图表坐标轴标题水平放置、单位 UNKNOWN 明确标注；表格容器横向滚动，800px 下 6 个关键页面零横向溢出（B19）。
- 站点点选后在地图下方出现摘要面板（名称/河流/区域/面积/观测期/上下游数/候选状态/坐标），并提供数据层与结果层跳转（B06）。
- QC 列表支持错误码与严重度过滤、25 条分页、来源文件 SHA-256 展示（B13）。

## 5. 全部测试结果（阶段 E）

命令：python -B tools\run_all.py → logs\test_summary.json

| 套件 | 结果 |
| --- | --- |
| test_feature_lineage | 53 / 53 |
| test_syrdarya_synthetic | 38 / 38 |
| test_gis_synthetic | 23 / 23 |
| test_provenance_snapshots | 32 / 32 |
| test_http_boundaries | 78 / 78 |
| test_lamahce_regression | 80 / 80 |
| test_syrdarya_api | 58 / 58 |
| test_science_views | 33 / 33 |
| test_regression_v05 | 50 / 50 |
| test_research_ready | 10 / 10 |
| test_v06_api（新增） | 46 / 46 |
| test_v06_ui（新增，真实 Chrome） | 20 / 20 |
| **合计** | **521 / 521，0 fail，0 skip** |

浏览器路由自检（tools/shots.py）：20 条路由全部渲染成功、0 报错、0 横向溢出；真实截图 32 张。

新增测试覆盖的关键点：四层路由与状态、双数据集隔离、缺测不归零、α 残余分列、配置保存与谱系违规拒绝、
GET/POST 执行门禁 403、报告“未执行”标注、静态路径逃逸、UI 交互（数据切换、点选、过滤、保存、403、前进后退、800px）。

## 6. 完整性校验（不得修改既有成果）

tools/integrity.py 结果（logs/integrity_v06.json，SHA256SUMS_v0.6.txt 共 108 个代码/文档/测试/截图文件；logs/ 为运行期证据，单独留存）：

| 对象 | 文件数 | 本次会话改动 |
| --- | --- | --- |
| v0.4 | 25 | 0 |
| v0.5（v0.5_syrdarya_integration） | 36 | 0 |
| v0.5.1（基线） | 91（按其自带 SHA256SUMS 逐项核对） | 0 |
| 老师原始 CSV（6 个 pin） | 6 | 0 |
| v0.6 新目录 | 108（全部哈希登记，不含运行期 logs/tmp） | 新建 |

预存差异 3 项（均早于本次会话开始时间 2026-10-24T23:49:55+08:00，非本次改动）：
v0.5 的 logs/access.log、v0.5.1 的 logs/access.log（运行期追加日志）与 v0.5.1 的 progress.md（交付后补记），
其 mtime 分别为 2026-10-24 20:34、15:20、15:21（本地时间），早于会话开始。

## 7. 本轮仍未执行的事项（不做假）

1. 未训练任何模型（SYR-B0/B1/B2 仅有接口与谱系检查）。
2. 未产生 Qsim、预测区间、空间预测图层、任何 NSE/KGE/RMSE/MAE/PBIAS 数值。
3. 未读取 sealed_runoff / quarantine；LamaH-CE 无序列可展示。
4. 未读取未授权的 GIS 矢量、DEM、统计年鉴内容与文献库。
5. 未引入外部依赖、未联网、未改变任何科研冻结结果。

## 8. 验收自检（对应任务书 A–H）

| 项 | 状态 | 证据 |
| --- | --- | --- |
| A 启动命令与地址 | 完成 | run_vhs.ps1 → http://127.0.0.1:8775/ |
| B 四层真实功能 | 完成 | 第 2 节表格 + 截图 |
| C 首页与结果层截图 | 完成 | screenshots/v06_01..20、v06_ui_01..12 |
| D 与 v0.5 的改进 | 完成 | README 第 8 节 + 第 4 节 |
| E 全部测试结果 | 完成 | 521/521，第 5 节 |
| F 未执行的模型与结果 | 完成 | 第 7 节，页面同步显示 |
| G 后续真实 GIS 最小任务 | 完成 | docs/DATA_AND_AUTHORIZATION_REQUEST.md |
| H 后续科研基线最小任务 | 完成 | docs/SCIENCE_BASELINE_NEXT.md |

## 9. 复现步骤

~~~powershell
cd E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform
powershell -ExecutionPolicy Bypass -File run_vhs.ps1     # 启动 8775
python -B tools\run_all.py                               # 521 项测试
python -B tools\shots.py                                 # 20 页截图与自检
python -B tools\integrity.py                             # 完整性校验 + SHA256SUMS
powershell -ExecutionPolicy Bypass -File stop_vhs.ps1    # 停止
~~~
