# SCI论文准备大纲（作者审阅用，非完成稿）

## Provisional titles

1. **Temporal reconstruction and spatial transfer of parsimonious monthly runoff models: evidence and limits for virtual gauging**（当前最可辩护）
2. **Diagnosing seasonal rainfall-memory gains and spatial transfer failures in monthly runoff reconstruction**
3. **Evidence-based admission of virtual hydrological stations from river networks and gauged-basin validation**（需要补齐KAZ连续Q后再考虑主标题）

## Abstract outline

Problem: temporal skill at calibrated gauges does not establish prediction at ungauged locations.
Design: compare seasonality-matched meteorological models, fixed-model temporal tests, additive diagnostics and target-label-excluded spatial transfer; keep Kazakhstan network readiness separate from runoff validation.
Finding to substantiate: rainfall-memory improvements coexist with seasonal failures and weaker macro-region transfer. Use one temporal aggregate and one spatial result rather than listing all runs.
Boundary: European observed-meteorology reconstruction; exposed historical development periods; no validated Kazakhstan ungauged accuracy or operational certification.
Implication: admit virtual stations using explicit source, feature, spatial-validation and uncertainty evidence, rather than counting geometry points as functioning gauges.

## 结果优先的证据链

1. **同季节结构下的气象增量**：P1/P2季节消融与固定前月P；需从各封存run补充公平共同样本表，不能直接比较不同月份的NSE。河流重建使用目标月已观测P/T，不称提前预报。
2. **时间外增量及失效**：P6D24站、864配对站月、1728旧预测；36月合并21/24正技能、站点等权+9.46%。2020仍8站全年L1负NSE，冬季相对增益与绝对失效分开；这些不是864个独立流域。
3. **可重构解释**：P6D加法项误差最大7.1054e-15 m³/s，说明变换及贡献数值可审计，不能证明降雪、水库或取水的因果机制。
4. **针对性模型升级**：P7-MEM内部开发22/24站改善、等权+3.56%；P7-SL未通过晋升（均值-0.34%），必须保留。P7最终<=2017标签，2018–2020为已暴露后验对照；FUTURE_HOLDOUT_NOT_AVAILABLE，不能当最终独立确认。
5. **真正移除目标Q后的空间退化**：既有EUROPEAN_PUB_DEVELOPMENT最近邻迁移，留站且排除嵌套供体中位NSE=0.216、KGE=0.415；留宏观水系中位NSE=-0.512、KGE=0.152。它是欧洲开发证据，不是KAZ精度；同一24站及重用时期也不是全新确认集。所有其他方法及负分保留原表。
6. **哈萨克斯坦应用准入**：P8/P9A132620来源河段、659769.848km、ORD_CLAS1–10、334混合公开坐标、237临时匹配及20工程点；全国预测可用/研究准入均0。这是空间数据准备结果，不是全国流量模型成绩。

## 章节框架

1. Introduction：稀疏网络需求；已知站时间重建与PUB的逻辑差距；明确研究问题，不声称首次解决全国VHS。
2. Data：LamaH-CE公开观测及ERA5-Land；eHYD/CAMELS-CH的新时期来源与质量差异；HydroRIVERS/Natural Earth/Zenodo研究流域/QazSu元数据及再利用边界。
3. Methods：共同样本、训练折内变换、LOYO/前向块、目标Q完全遮蔽和嵌套供体排除；站点等权指标；不可变来源与准入状态；空间与时间依赖处理。
4. Results：先报告同结构增量，再时间失效，再空间转移失败；KAZ数据准入另设小节或补充材料，避免将软件/地图当核心预测创新。
5. Discussion：低维记忆的适用范围、固定模板局限、数据版本及QC、跨区域气候/调节差异；机制仅列候选解释。
6. Conclusion：可重现的有界结果及未解决PUB边界，不能写“实现全国高精度虚拟站”。

## 候选创新点与证据等级

- 有季节表达对照的前期P增量及失效分解：已有数值证据；是否相对文献新颖仍需系统检索，禁止“首次”措辞。
- 将时间外校准站技能与无目标Q空间转移严格分开：已有欧洲开发证据，跨宏观区负结果必须报告。
- 河网、身份、驱动、预测、研究准入分层：P9A有实际GIS证据，但目前只能作为可复用数据准入方法，缺KAZ真实Q/PUB验证。
- 全国高精度、真实水量损失归因、业务预警：**不受现有证据支持**。

## 图表—源表映射

- Fig1 数据/协议与暴露时间轴：P6/P7冻结协议、P7A_FINAL_STATUS.json、KAZ_N1_FROZEN_PROTOCOL.json。
- Fig2 时间重建与季节失败：P6C_PRIMARY_2020_METRICS.csv、P6C_MODEL_COMPARISON.csv、P6D_STATION_YEAR_FAILURES.csv。
- Fig3 数值贡献与误差集中：P6D_PREDICTION_DECOMPOSITION.csv、P6D_MONTHLY_PAIRED_ERRORS.csv；负面站点按预声明案例，不按高分选图。
- Fig4 升级消融与空间转移：P7A_ABLATION_RESULTS.csv及pub/EU_PUB_SUMMARY.csv；分开开发/后验/空间协议，不合并其样本数。
- FigS1 KAZ七级及>7地图：本轮figures/P9A_MAP_ORD_CLAS.*、P9A_ORDER_1_TO_7.csv。
- FigS2 站点与首流域：figures/P9A_FIRST_BASIN_MAP.*、P9A_GAUGE_IDENTITY_CROSSWALK.csv及P9A_FIRST_BASIN_PILOT_CANDIDATES.csv。
- TableS来源/声明：P9A_SCI_EVIDENCE_INDEX.csv（实际路径、SHA及逐项限制）。

## 必补实验及作者决定

优先补齐KAZ首流域连续合法Q/P/T及严格PUB；冻结目标遮蔽、供体/拓扑排除与静态属性基线，至少包含最近邻、相似性迁移和简单区域共享。P7-MEM只有在供体区域化后才能参与PUB，禁止复用目标站Q校准参数。另需独立保管未来/外部Q、无接触暴露台账与先预测后评分；现有2021+整档解析暴露史不可忽略。

统计以站点/水系及年份分块，报告负NSE、相对技能、效应与不确定性，不能用“准确率XX%”或相关月份膨胀样本。本轮不计算新显著性。补充面积缩放/供体气候态、季节与记忆去除消融、来源日界/QC敏感性；独立测试不能用于调参或区间再标定。

术语固定：VHS=Virtual Hydrological Station；PUB=prediction in ungauged basins；TEMPORAL_RECONSTRUCTION为已知站历史Q校准；GEOMETRIC_PROVISIONAL不译为官方认证；ORD_CLAS/ORD_STRA均为河流等级，HYBAS_L12为Pfafstetter流域层级；MSE skill为相对基线误差下降，不是普适预测精度。

数据与代码声明待办：HydroRIVERS及八流域DOI/署名、LamaH-CE10.5281/zenodo.5153305及原研究引用、eHYD/CAMELS-CH来源与再分发范围、QazSu坐标再利用许可逐项核实。不要把内部本地审计包自动公开。参考文献须后续检索并逐条核验，本提纲未虚构引用或完成新颖性检索。作者须审核证据与论证；这份大纲不是已通过同行评审的完整稿。
