from common import *
import numpy as np,pyogrio,shutil,re
def md(name,text):(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')
orders=pd.read_csv(ROOT/'P9A_ORDER_1_TO_7.csv');top=read(ROOT/'evidence/TOPOLOGY_AUDIT.json');boundary=read(ROOT/'evidence/BOUNDARY_TOPOLOGY_COUNTS.json');s=read(ROOT/'evidence/CANDIDATE_SCREENING_SUMMARY.json');qa=read(ROOT/'P9A_INDEPENDENT_QA.json');history=read(ROOT/'evidence/HISTORY_FINAL_CHECK.json')
if (ROOT/'evidence/COMBINED_INDEPENDENT_QA.json').exists():
    combined=read(ROOT/'evidence/COMBINED_INDEPENDENT_QA.json');qa['passed']=combined['passed'];qa['failed']=combined['failed']
gauges=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});chain=pd.read_csv(ROOT/'P9A_UPSTREAM_CHAIN_LENGTH.csv');basins=pd.read_csv(ROOT/'P9A_FIRST_BASIN_COMPARISON.csv');c=pd.read_csv(ROOT/'P9A_VHS_CANDIDATE_SCREENING.csv')
source_basin_map={1:8,2:2,3:6,4:5,5:7,6:4,7:3,8:1}
gauges['QazSu_source_basin_research_id']=gauges.source_basin_id.map(source_basin_map)
gauges['source_basin_vs_geometric_basin_agreement']=np.where(gauges.QazSu_source_basin_research_id==gauges.nearest_basin_id,'AGREES_AFTER_NAMESPACE_CROSSWALK','DISAGREES_OR_UNASSIGNED_REVIEW_REQUIRED')
gauges['river_name_identity_verified']=False
csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',gauges)
reasons=gauges.loc[~gauges.primary_500m_geometric_match,'reason_codes'].str.split('|',regex=False).explode().value_counts()
csv(ROOT/'P9A_GAUGE_UNMATCHED_REASONS.csv',[dict(reason_code=k,records=int(v),count_basis='nonexclusive; among97 not geometrically admitted') for k,v in reasons.items()])
flags=read(ROOT/'evidence/ORDER_VIEW_CHECKS.json')
for r in flags:r['passed']=str(r['passed']).lower()=='true'
js(ROOT/'evidence/ORDER_VIEW_CHECKS.json',flags)
# Evidence index contains published aggregates and actual paths, never new Q or model fitting.
items=[
 ('P6B','vhs_p6b_external_validation/P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md','new-period source and quality context','Temporal validation; not a Kazakhstan or new ungauged result'),
 ('P6C','vhs_p6c_2020_validation/P6C_PRIMARY_2020_METRICS.csv','24stations2020 frozen fixed-model performance','NegativeNSE retained; eHYD dayQC/date limitations'),
 ('P6C','vhs_p6c_2020_validation/P6C_MODEL_COMPARISON.csv','paired2020 L1 gain versusC0+PT','Same24stations; not24 independent basins'),
 ('P6D','vhs_p6d_failure_diagnostics/P6D_FINAL_STATUS.json','24stations864months1728predictions; decomposition','Posthoc diagnostic; no new independent test months'),
 ('P6D','vhs_p6d_failure_diagnostics/P6D_STATION_YEAR_FAILURES.csv','station/year negative results and concentration','Do not average annual NSE'),
 ('P6D','vhs_p6d_failure_diagnostics/P6D_PREDICTION_DECOMPOSITION.csv','additive reconstruction and true transform space','Not causal attribution'),
 ('P6D','vhs_p6d_failure_diagnostics/P6D_RESEARCH_REPORT_ZH.md','21/24 positive36month skills; station-equal9.46%','Observed target-month meteorology reconstruction, not forecast'),
 ('P7A','vhs_p7a_hydrological_models/P7A_FINAL_STATUS.json','development and promotion numbers','2018–2020 historical comparison exposed; future holdout unavailable'),
 ('P7A','vhs_p7a_hydrological_models/P7A_STATION_MODEL_METRICS.csv','blocked pre2017 development metrics','Known-gauge calibration; not PUB'),
 ('P7A','vhs_p7a_hydrological_models/P7A_PROMOTION_DECISION.json','P7SL failed; P7MEM passed development gate','Research gate not operational certification'),
 ('EU_PUB','vhs_kaz_n1_national_virtual_stations/pub/EU_PUB_SUMMARY.csv','strict targetQ masking; LOSO and macro-region comparisons','EUROPEAN_PUB_DEVELOPMENT; historical periods exposed, no Kazakhstan accuracy'),
 ('EU_PUB','vhs_kaz_n1_national_virtual_stations/pub/TARGET_MASK_AUDIT.json','target-label isolation evidence','Not a new Kazakhstan benchmark'),
 ('P8','vhs_kaz_p8_river_chain_statistics/P8_PROVENANCE.json','source/datum/boundary/ID provenance','Research boundaries not official cadastral survey'),
 ('P8','vhs_kaz_p8_river_chain_statistics/P8_SPATIAL_QA.json','length conservation independent checks','GIS QA not scientific model admission')]
evidence=[]
for phase,rel,claim,limit in items:
    p=LAB/rel
    evidence.append(dict(phase=phase,path=str(p),exists=p.is_file(),sha256=sha(p) if p.is_file() else None,supports=claim,limitation=limit,evidence_grade='FROZEN_ARTIFACT_VERIFIED' if p.is_file() else 'NOT_AVAILABLE'))
for name,claim in [('P9A_ORDER_1_TO_7.csv','domestic complete individual orders'),('P9A_UPSTREAM_CHAIN_LENGTH.csv','source graph chain distances with interior offsets'),('P9A_VHS_CANDIDATE_SCREENING.csv','topology geometry screening; no simulatedQ'),('P9A_FIRST_BASIN_PILOT_CANDIDATES.csv','20actual engineering points; not20formalVHS')]:
    p=ROOT/name;evidence.append(dict(phase='P9A',path=str(p),exists=True,sha256=sha(p),supports=claim,limitation='Not Kazakhstan runoff validation',evidence_grade='NEW_ACTUAL_GIS_COMPUTATION'))
csv(ROOT/'P9A_SCI_EVIDENCE_INDEX.csv',evidence)
p7=read(LAB/'vhs_p7a_hydrological_models/P7A_FINAL_STATUS.json');pub=pd.read_csv(N1/'pub/EU_PUB_SUMMARY.csv');pubsel=pub[pub.model_id=='GEOGRAPHIC_DONOR_TRANSFER']
qreadiness=[dict(dataset='Kazhydromet current network',state='COUNTS_VERIFIED_442_394',Q_time_series='NOT_ACQUIRED',coordinate_coverage='394 official membership not reconciled',QC='NOT_AVAILABLE',license='NOT_ESTABLISHED',reason='Official map and hydrological DB timed out; page itself200'),dict(dataset='QazSu archived334records',state='PUBLIC_COORDINATES_AUDITED',Q_time_series='CURRENT_MEAN_SNAPSHOT_NOT_TRAINING_SERIES',coordinate_coverage='334mixed-type points;237geometric provisional',QC='NO_CONTINUOUS_DAILY_QC',license='NO_EXPLICIT_BULK_REUSE_LICENSE_VERIFIED',reason='No historical start/end or identity certification'),dict(dataset='HydroRIVERS',state='SOURCE_AND_TOPOLOGY_AVAILABLE',Q_time_series='DIS_AV_CMS_MODELED_CLIMATOLOGY_NOT_OBSERVED_Q',coordinate_coverage='132620domesticsourceIDs',QC='SOURCE_GEOMETRY_QA_ONLY',license='HydroSHEDS source terms and attribution retained',reason='No Q labels'),dict(dataset='Pilot full-upstreamP/T',state='NOT_ACQUIRED',Q_time_series='N/A',coordinate_coverage='Exact point catchments not delineated',QC='NOT_AVAILABLE',license='REQUIRES_LAWFUL_FORCING_ACCESS',reason='European ERA5 pipeline is implementation evidence, not Kazakhstan forcing coverage')]
csv(ROOT/'P9A_Q_AND_DRIVER_READINESS.csv',qreadiness)
grade_lines='\n'.join(f"| {int(r.order_value)} | {int(r.source_reaches):,} | {r.length_km:,.3f} |" for r in orders[orders.order_scheme=='ORD_CLAS'].itertuples())
pilot=basins[basins.geometry_pilot].iloc[0]
md('P9A_FIRST_BASIN_READINESS.md',f'''# 首流域：Balkhash–Alakol（巴尔喀什—阿拉湖）

结论：工程几何试点已就绪，水文训练/全国预测未准入。选择不依据模型分数；八流域均未取得合格连续Q与同源P/T，因此不能称本流域的水文资料最齐全。按冻结的“临时匹配站数量最大，其次候选数量，最后流域id”规则，本流域49个临时匹配站最多，选出20个实际工程点。

- 原池415点，拓扑与几何筛选162点，确定性选取20点；完整八流域比较见P9A_FIRST_BASIN_COMPARISON.csv。
- 49站身份为GEOMETRIC_PROVISIONAL，官方成员认证0；QazSu站名/河名及站码保留，但HydroRIVERS无河名无法完成独立河名互证，迁站/启闭时间未知。
- 连续Q时段：N/A_NOT_ACQUIRED；单位、逐日QC、日界和允许训练/导出条款均未建立。当前/均值字段不作为历史标签。
- 全上游P/T：NOT_ACQUIRED；ERA5-Land聚合实现可在以后复用，但未对本流域实际格点、面积权重及2019等历史覆盖做准入。准确点位集水区尚未划定。
- 河网及属性：全球NEXT_DOWN闭包可用、源几何端点审计通过；有UPLAND_SKM出口代理及CATCH_SKM，尚无点位精确集水面积。跨境上游保留，详见点位逐行标志；不只以国界内支流计算。
- 候选表保留站id、坐标、HYRIV_ID、ORD_CLAS/ORD_STRA、上游面积下界和出口代理、路径/累计长度、关联实站码、距离及未准入原因。
- 预期空间验证：目标站Q从供体训练、季节模板、标准化及调参完全移除；先做留站及剔除嵌套供体，再做河网/子流域成组遮蔽。每个供体/目标要先验证拓扑与观测定义。
- 预期时间验证：训练期内部按完整年份分块，另保留独立保管、此前未解析/评分/选型的外部时期；欧洲已暴露2018–2020不替代哈萨克斯坦盲集。
- P9B首项：取得该流域官方站码—河名—坐标—汇水面积—迁站史清单、合法连续Q与QC/单位/日界，并明确数据许可；再划定20点精确上游集水区，构建同口径P/T并绑定快照。
- P10启动条件：Q/P/T、静态特征、权限/许可、分组与未暴露时段全部冻结后才开展PUB。当前不得加载欧洲站点校准参数冒充哈萨克斯坦新点模型。

该20点仅从既有AS瓦片几何池中筛选，原池对Ertis、Yesil没有候选，绝不代表这两个流域没有可选断面；本轮不重建全国候选池来制造更大的数量。

20点均为ORD_CLAS=1，沿同一条一级主链分布，是上下游链路工程试点，不是20个独立集水区或有代表性的全流域验证样本。后续空间验证必须整链/子流域成组排除，不能把这些嵌套点当独立重复。
''')
lo=pubsel[pubsel.scheme=='LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS'].iloc[0];ma=pubsel[pubsel.scheme=='LEAVE_MACRO_REGION_OUT'].iloc[0]
md('P9A_SCI_PAPER_OUTLINE.md',f'''# SCI论文准备大纲（作者审阅用，非完成稿）

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
4. **针对性模型升级**：P7-MEM内部开发22/24站改善、等权+{p7['promotion']['P7-MEM']['station_mean_skill']*100:.2f}%；P7-SL未通过晋升（均值{p7['promotion']['P7-SL']['station_mean_skill']*100:.2f}%），必须保留。P7最终<=2017标签，2018–2020为已暴露后验对照；FUTURE_HOLDOUT_NOT_AVAILABLE，不能当最终独立确认。
5. **真正移除目标Q后的空间退化**：既有EUROPEAN_PUB_DEVELOPMENT最近邻迁移，留站且排除嵌套供体中位NSE={lo.NSE_median:.3f}、KGE={lo.KGE_median:.3f}；留宏观水系中位NSE={ma.NSE_median:.3f}、KGE={ma.KGE_median:.3f}。它是欧洲开发证据，不是KAZ精度；同一24站及重用时期也不是全新确认集。所有其他方法及负分保留原表。
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
''')
md('P9A_COMPLETE_REPORT_ZH.md',f'''# KAZ-P9A实际交付

本轮完成七级及更高序级拆分、实站元数据交叉表、全球上游拓扑与河段内偏移、1230点复筛、20点单流域工程名单及SCI证据大纲。未训练、未生成流量预测或评分、未访问教师受限Q、未修改网站/403/原有模型。

## 全国七级和更高序级（主统计ORD_CLAS）

| 级别 | 唯一来源河段数 | 国内长度km |
| --- | ---: | ---: |
{grade_lines}

合计132620来源河段、659769.848365624km。1–7级独立列出，8/9/10级保留；STRA另有1–8级。原全球文件实际CLAS1–14、STRA1–10，见P9A_GLOBAL_SOURCE_ORDER_AUDIT.csv；其中全球长度列为原LENGTH_KM属性，不能当本轮国内几何重测。国内两序级均无缺失，源值不在裁剪后重算。

八研究流域分配656125.986603km，未归属3643.861767km另表；原六子集519964.242091km。所有序级均有全国、八流域及六子集表；ORD_CLAS与ORD_STRA不能混加。继承P8含拜科努尔主权国界、同一河段跨流域切分及唯一来源HYRIV_ID。HydroBASINS/Pfafstetter是流域层级，不能称“河流七级”。

## 实站与真实数据缺口

官方当前页面重新下载200成功，列442监测点，其中394河流、38湖泊、10海洋；381常年、61季节。页面未注明统计基准年，访问UTC见source/DOWNLOAD_LOG.json，不和2024年数字混用。

334条QazSu混合记录保留原站码、名称、河名、坐标、类型推断及源哈希；237临时几何匹配，7歧义，90其他未准入。官方现役成员认证0；不得把237称为正式认证站，也不能394−334解释缺失人数。334条GeoJSON为经度/纬度，x/y属性为纬度/经度且仅4位小数，半末位容差核对334/334；原坐标未更改。

原500m吸附与10m歧义规则未放宽。站点对应HYRIV_ID、流域及两序级见交叉表；QazSu与研究流域id映射显式分离。HydroRIVERS无河名，名称/河名不能独立互证；坐标匹配不构成迁站史或业务认证。现役官方交互地图与水文数据库实链分别访问超时；一个猜测归档路由返回站内404，已保留并改跟网页实链，未视为有效资料。未取得连续历史Q、单位、QC、日界或明确批量再利用许可，当前均值/实时Q不转为训练标签。

## 上游拓扑与三种链长

从已有8477883条全球唯一源图实际提取1435目标河段的104594条上游闭包，DAG104594全部处理，0循环、0超过100m的端点不连通；全球NEXT_DOWN引用缺失0。国内有549条源下游链接离开国内ID集，全球仍有对应，不能在裁剪边界当源头。国内终点/内流/多片段统计另见P9A_TOPOLOGY_BOUNDARY_AUDIT.csv及evidence/BOUNDARY_TOPOLOGY_COUNTS.json。

237个临时站分别输出①同ORD_CLAS唯一连续主河道源端到站路径；②最远源头到站路径；③全部连通上游河段累计长度。主路径不是上游分支求和，也不保证与官方命名河流源头一致。全部使用全球跨境上游与WGS84几何长度，处理站点所在源河段内偏移，不能直接套用出口DIST_UP/UPLAND。{int(chain.cross_border_upstream.sum())}站有国外上游长度。图内链长可算不等于自然水系完整认证：10km²/0.1m³/s产品门槛、15角秒、单NEXT_DOWN无法表示所有分流/调水及人工渠。河段出口面积仍是代理，不填充点位精确面积。

1230点保留，557有向连到临时站，40点在已取得河流站5km范围内；519通过本轮几何与拓扑规则。14个同源河段情形另用河段内偏移判别上下游，不能只比较ID。首流域Balkhash–Alakol有49临时站、415旧池点、162个本轮几何合格点，确定性选20工程点。新点驱动可用0、预测可用0、研究准入0。旧候选池最初只有亚洲瓦片，Ertis/Yesil候选0是输入池覆盖缺口，不是全国潜力为0。其余官方站位置未知，5km排除仍仅针对已取得子集。

首批20点均为一级且位于同一主链，是工程试点，不是20个独立流域。327条QazSu流域标签经命名空间换算后与几何归属一致，另7条不一致或未归属，显式保留复核状态，不强行修改原属性。

## SCI与下一阶段

已读实际P6/P7/P8及欧洲PUB封存证据并保存逐文件SHA索引。建议论文聚焦时间增量、失效诊断和严格空间转移的差距，KAZ作为数据准入应用；不把欧洲校准站的NSE转为哈萨克斯坦无资料精度。P7-MEM通过开发门槛但未来盲集未建立；P7-SL失败、负NSE及空间转移负结果必须保留。详见P9A_SCI_PAPER_OUTLINE.md。

P9B下一步只需优先拿到首流域可信实站身份、合法连续Q及QC/单位/日界/许可，再划定精确点位集水区和同源气象；随后另获研究安排开展P10空间/时间验证。当前不能开始全国正式VHS预测。

## 实际验证、失败和边界

最终独立GIS/数值复核{qa['passed']}通过/{qa['failed']}失败；独立WGS84 Vincenty抽查{qa['independent_length_sample_n']}条，最大长度差{qa['max_length_error_km']:.12g}km；全国与流域分段长度守恒在0.0001km内。旧科研与网站历史SHA256 {history['passed']}/{history['checked']}一致。

首轮独立QA有1项失败：ID97063的未分段投影与原P8分段投影相差0.008857m，保留失败表与代码，改用真实P8分段输入后原严格容差通过，未改吸附阈值。坐标属性精度/投影修订均有日志。图形为真实数据4类、PDF/SVG/300dpiPNG；静态检查、PDF字形和人工视觉复核见图形QA。缺PyMuPDF时自动碰撞审计记NOT_AUDITABLE，不当通过。图件是研究/组会版，不宣称某期刊终稿或业务认证。

已完成：分级、拓扑链长、身份交叉表、工程点、地图/GPKG、SCI大纲及复核。受阻：官方394逐站成员与迁站史、合法历史Q/QC/单位/日界、坐标批量发布许可、点位精确集水区及同源P/T。未执行：任何模型fit/predict/评分、P9B/P10、教师Q读取、网站或发布权限变更。fit_calls=0，Q_scoring_calls=0。
''')
md('P9A_REPRODUCTION_GUIDE.md',f'''# P9A复现与文件映射

Python：{sys.executable}。使用已有环境与-B，不安装依赖。运行ROOT={ROOT.as_posix()}。

只验证当前交付（不重跑任何模型）：
```powershell
& '{sys.executable.replace(chr(92),'/')}' -B '{(ROOT/'code/verify_delivery.py').as_posix()}'
```

分析脚本按依赖顺序：init_orders.py → source_audit.py → topology.py → extra_audit.py → screening.py → verify.py → figures.py → figure_qa.py → finalize.py → verify_extra.py → finalize.py → 人工视觉核验 → seal.py。数据/统计复现须在新的空目录，通过VHS_P9A_OUTPUT环境变量指向独立工作路径，复制code后调用这些脚本；init_orders.py会拒绝已有新GPKG，不能把本封存目录当可覆盖工作目录。source_audit.py包含有限官方网络请求；仅重复数值时使用本次已封存来源快照、跳过网络并复制crosswalk来源，保持sha一致。外部HTML是访问时点证据，日后页面变化应新建快照，不能强求网络内容字节相等。

实际执行及恢复：RUN_ATTEMPTS.jsonl与evidence/CORRECTION_LOG.json、PROTOCOL_REVISION.json、INITIAL_FAILED_P9A_INDEPENDENT_QA.json、verify_initial_failed.py。coordinate_revision.py/repair_checks.py是本次开发恢复工具，不是正常复现必跑步骤，不可对冻结目录重用。源协议初版已留存；最终明确使用P8的LAEA(lat0=48,lon0=68)，所有最终长度为WGS84测地线。

文件映射：P9A_ORDER_1_TO_7.csv含两序级所有实际国内值及>7独立行；八/六表每种序级单独求和；UNASSIGNED另表不吞掉。P9A_SEVEN_ORDER_NETWORK.gpkg继承四个原层，加ORD_CLAS和ORD_STRA各1–7及gt7注册SQL视图，再加qazsu_identity_audit/candidate_screening/first_basin_pilot。视图各需GIS软件支持SQLite视图；已通过pyogrio读取及数值核验。

P9A_UPSTREAM_CHAIN_LENGTH.csv只含237临时站；其余97未几何准入，不生成伪链长。data/CANDIDATE_CHAIN_METRICS.csv为1230原点的独立派生；data/GLOBAL_UPSTREAM_CLOSURE.csv与P9A_UPSTREAM_SOURCE_GEOMETRY.gpkg保留原全局节点和几何；TOPOLOGY_ARRAYS.npz为可再算缓存。三个链长的定义、源阈值、跨境范围与精确集水面积缺口见正式报告。

图件：figures/P9A_MAP_ORD_CLAS.*、P9A_MAP_ORD_STRA.*、P9A_ORDER_LENGTHS.*、P9A_FIRST_BASIN_MAP.*。source.json给输入与脚本；单数据面板，alignment为NOT_APPLICABLE，不计通过多面板审计。数值QA与图形QA、历史保护是不同验收维度。

所有新代码、结果、公开访问日志和历史保护记录纳入SHA256SUMS.txt。清单自身不自引用；独立verify_delivery.py检查清单和受保护历史，stdout即实际检查数。RUN_ATTEMPTS在封存后不得追加；需要后续运行则新建任务目录。

数据许可：HydroRIVERS/NaturalEarth/Zenodo边界原来源及属性随P8继承，见P9A_RESULT_PROVENANCE.json。QazSu原坐标及派生匹配仅本地研究核验；未取得明确批量再发布许可，不自动上传此包或站点层到公众网站。无教师Q、无模型加载/拟合、无网站权限操作。
''')
md('P9A_DATA_DICTIONARY.md','''# 核心字段与状态

- ORD_CLAS：HydroRIVERS经典主支流等级，主链1、其支流2等；ORD_STRA：Strahler头水1、同级汇流升阶，两者数值含义不同。HYBAS_L12为Pfafstetter流域层级，不能用来重命名两种河流等级。
- length_km：P8国界/分流域裁剪的WGS84测地线长度；SOURCE_REACH_LENGTH_KM为原始近似属性。GLOBAL_SOURCE_ORDER_AUDIT的source_LENGTH_KM_sum只用于源属性对照。
- national_reaches.HYRIV_ID唯一；basin_fragments.HYRIV_ID可合法重复，fragment_id唯一，不能按片段行数重建NEXT_DOWN节点。
- source_to_station_mainstem_km：沿同ORD_CLAS唯一上游路径至源数据起点，加站点所在源河段的上游部分；没有保证是官方命名源头。
- longest_headwater_to_station_km：从所有上游路径取最长者，加站点源河段上游部分；all_upstream_connected_length_km为所有上游支线求和，不是两点距离。
- upstream_foreign_length_km：源全球闭包中境外部分，已扣除站点所在河段下游部分；cross_border_upstream阈值0.001km，仅抑制浮点几何碎屑，不认证水文跨境管理。
- topology_complete_within_source_product：数据图及端点核验的范围内完整；不证明小沟、渠道、分流、真实季节性或调水记录齐全。
- source_basin_id属于QazSu命名空间，nearest_basin_id属于研究多边形；QazSu_source_basin_research_id显式映射。7条不一致/未归属保留复核，不改原属性。
- station_type_inferred来自名称，不是官方认证类型；official_certification全部NOT_CONFIRMED。
- geometry_state、reason_codes是继承旧池属性；candidate_status和screening_reason_codes为P9A新状态与原因。TOPOLOGY_AND_GEOMETRY_SCREENED仍不是FEATURES_AVAILABLE、VIRTUAL_PREDICTION_AVAILABLE或RESEARCH_ADMITTED。
- source_upstream_area_outlet_proxy_km2和source_upstream_area_lower_bound_km2为来源出口代理/选址下界，不是点位精确集水面积。exact_point_catchment_area_km2保持N/A。
- has_directed_gauge_connection为实际NEXT_DOWN可达性证据；同河段的14种情形由上游偏移判别方向，不把MAIN_RIV相同当可达。可达不等于有合法Q或有模型泛化能力。
- N/A表示未取得、不可核实或不适用；不替换为0。只有真实核验的数量0，如本轮训练次数、已取得连续Q序列、正式VHS数量，才用0。
''')
js(ROOT/'P9A_RESULT_PROVENANCE.json',dict(protocol_sha256=sha(ROOT/'P9A_FROZEN_PROTOCOL.json'),input_inventory=read(ROOT/'evidence/INPUT_INVENTORY.json'),P8_source_provenance_path=str(P8/'P8_PROVENANCE.json'),P8_source_provenance_sha256=sha(P8/'P8_PROVENANCE.json'),boundary='SOVEREIGNT Kazakhstan union including Baykonur; inherited',basin_DOI='10.5281/zenodo.17077776',HydroRIVERS_technical_source='https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf',source_license_status='Source-specific original terms/attribution retained; QazSu bulk reuse not established',fit_calls=0,Q_scoring_calls=0,original_station_or_model_sources_modified=False))
js(ROOT/'P9A_FINAL_STATUS.json',dict(task='KAZ_P9A',status='GIS_AND_PAPER_OUTLINE_COMPLETED_HYDROLOGICAL_MODELING_BLOCKED',national_reaches=132620,national_length_km=659769.8483656237,ORD_CLAS_values=list(range(1,11)),ORD_STRA_values=list(range(1,9)),QazSu_records=334,provisional_gauges=237,official_gauges_identity_certified=0,continuous_Kazakhstan_Q_series_acquired=0,chain_lengths_computed=237,upstream_closure_reaches=top['closure_reaches'],**s,fit_calls=0,Q_scoring_calls=0,teacher_Q_reads=0,web_modified=False,independent_checks_passed=qa['passed'],independent_checks_failed=qa['failed'],historical_files_unchanged=history['passed'],P9B_started=False,P10_started=False))
# Refresh station GIS attributes after namespace/identity augmentation, preserving all original source data.
import geopandas as gpd
gpd.GeoDataFrame(gauges,geometry=gpd.points_from_xy(gauges.longitude,gauges.latitude),crs=4326).to_file(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='qazsu_identity_audit',driver='GPKG',engine='pyogrio')
event('reports_written',evidence_index_entries=len(evidence),missing_evidence_entries=sum(not r['exists'] for r in evidence),fit_calls=0,Q_scoring_calls=0)
