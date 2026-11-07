# P9A复现与文件映射

Python：E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe。使用已有环境与-B，不安装依赖。运行ROOT=E:/VHS_Public_Baseline_Lab/vhs_kaz_p9a_network_station_audit。

只验证当前交付（不重跑任何模型）：
```powershell
& 'E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/.venv/Scripts/python.exe' -B 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p9a_network_station_audit/code/verify_delivery.py'
```

分析脚本按依赖顺序：init_orders.py → source_audit.py → topology.py → extra_audit.py → screening.py → verify.py → figures.py → figure_qa.py → finalize.py → verify_extra.py → finalize.py → 人工视觉核验 → seal.py。数据/统计复现须在新的空目录，通过VHS_P9A_OUTPUT环境变量指向独立工作路径，复制code后调用这些脚本；init_orders.py会拒绝已有新GPKG，不能把本封存目录当可覆盖工作目录。source_audit.py包含有限官方网络请求；仅重复数值时使用本次已封存来源快照、跳过网络并复制crosswalk来源，保持sha一致。外部HTML是访问时点证据，日后页面变化应新建快照，不能强求网络内容字节相等。

实际执行及恢复：RUN_ATTEMPTS.jsonl与evidence/CORRECTION_LOG.json、PROTOCOL_REVISION.json、INITIAL_FAILED_P9A_INDEPENDENT_QA.json、verify_initial_failed.py。coordinate_revision.py/repair_checks.py是本次开发恢复工具，不是正常复现必跑步骤，不可对冻结目录重用。源协议初版已留存；最终明确使用P8的LAEA(lat0=48,lon0=68)，所有最终长度为WGS84测地线。

文件映射：P9A_ORDER_1_TO_7.csv含两序级所有实际国内值及>7独立行；八/六表每种序级单独求和；UNASSIGNED另表不吞掉。P9A_SEVEN_ORDER_NETWORK.gpkg继承四个原层，加ORD_CLAS和ORD_STRA各1–7及gt7注册SQL视图，再加qazsu_identity_audit/candidate_screening/first_basin_pilot。视图各需GIS软件支持SQLite视图；已通过pyogrio读取及数值核验。

P9A_UPSTREAM_CHAIN_LENGTH.csv只含237临时站；其余97未几何准入，不生成伪链长。data/CANDIDATE_CHAIN_METRICS.csv为1230原点的独立派生；data/GLOBAL_UPSTREAM_CLOSURE.csv与P9A_UPSTREAM_SOURCE_GEOMETRY.gpkg保留原全局节点和几何；TOPOLOGY_ARRAYS.npz为可再算缓存。三个链长的定义、源阈值、跨境范围与精确集水面积缺口见正式报告。

图件：figures/P9A_MAP_ORD_CLAS.*、P9A_MAP_ORD_STRA.*、P9A_ORDER_LENGTHS.*、P9A_FIRST_BASIN_MAP.*。source.json给输入与脚本；单数据面板，alignment为NOT_APPLICABLE，不计通过多面板审计。数值QA与图形QA、历史保护是不同验收维度。

所有新代码、结果、公开访问日志和历史保护记录纳入SHA256SUMS.txt。清单自身不自引用；独立verify_delivery.py检查清单和受保护历史，stdout即实际检查数。RUN_ATTEMPTS在封存后不得追加；需要后续运行则新建任务目录。

数据许可：HydroRIVERS/NaturalEarth/Zenodo边界原来源及属性随P8继承，见P9A_RESULT_PROVENANCE.json。QazSu原坐标及派生匹配仅本地研究核验；未取得明确批量再发布许可，不自动上传此包或站点层到公众网站。无教师Q、无模型加载/拟合、无网站权限操作。
