# KAZ-N1复核与运行

现有环境：`E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`；新目录：`E:\VHS_Public_Baseline_Lab\vhs_kaz_n1_national_virtual_stations`。不安装依赖。所有命令使用`-B`避免在冻结目录产生字节码。

## 已实际运行的计算入口

执行顺序为`intake.py`（官方快照/历史初检）→`assets.py`（资产/协议冻结）→`gis_candidates.py`（真实GIS）→`pub_prepare.py`（训练/评分角色分离缓存）→`pub_train_predict.py`（126次回归拟合/48次气候态估计及9216条预测封存）→`pub_score.py`（独立评分）→`results.py`（导师答案/密度/缺口）→`web_prepare.py`（复制原主站候选）→`verify.py`（独立数值重构）→`web_verify.py`（实际HTTP验收）→浏览器页面验收→`finalize.py`。

实际脚本调用形式为`& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_kaz_n1_national_virtual_stations\code\<入口>.py'`。源码根常量在`code/intake.py`，缓存源路径与哈希在`pub/CACHE_SOURCE_PINS.json`。旧文件只读。

## 本次封存后的只读复核命令

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_kaz_n1_national_virtual_stations\code\verify_delivery.py'
```

该命令只计算交付、历史、GIS及WEB输入SHA256，不fit、不评分、不联网。`verify.py`可以用保存参数重构全部预测和直接核算指标，但会覆盖本轮已有数值复核JSON，故正式封存后应在另一个输出副本中运行；不应在本run中重跑完整流水线。训练和评分入口已增加已有封存产物拒绝规则。日后复现实验须复制代码/来源证据到新根目录并修改副本的ROOT，使用相同冻结协议和输入哈希；不得覆盖本目录，也不得据此扩大教师/GRDC权限。

## 数据与分析口径

官方网络442、河流394为现页事实；统计年未注明。国土面积2,724,900 km²固定。GIS用真实AS瓦片、NaturalEarth概化边界、LAEA48N68E，固定25km河网距离、保守上游面积≥1000km²、2km边界缓冲、3km节点分隔；1230点只属初筛，无当前实站去重/完整汇水区/8大管理流域归属，正式N_candidate=0。

欧洲PUB按两种空间遮蔽方案，各24站×48测试月。供体Q≤2013，目标评分2014–2017，所有候选均固定Ridge100，无事后筛选。目标Q隔离的逐任务定义见`KAZ_N1_Q_MASK_SCOPE_CLARIFICATION.md`。两方案、四方法和同水系站点不是独立重复；所有负NSE及原始负预测保留，非负为次分析。常数预测导致不可定义的KGE以空值及原因码表示。

## 核心文件映射

导师四问：`KAZ_N1_SUPERVISOR_ANSWER_ZH.md`；组会科学结果：`KAZ_N1_GROUP_MEETING_SUMMARY.md`；官方证据：`source/SOURCE_LOG.json`及HTML；合法性/缺口：`KAZ_N1_DATA_READINESS.csv`；真实几何：`KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson`；全部预测/指标：`KAZ_N1_UG_PREDICTIONS.csv`、`KAZ_N1_UG_VALIDATION_METRICS.csv`；逐年/冬季/5–6月与水系：`pub/EU_PUB_*METRICS.csv`、`pub/EU_PUB_MACRO_SUMMARY.csv`；每折模型参数：`pub/models`；真实拟合：`pub/FIT_CALLS.csv`；缺失交付原因：`KAZ_N1_DELIVERABLE_AVAILABILITY.json`；页面截图/AX：`evidence/browser`。
