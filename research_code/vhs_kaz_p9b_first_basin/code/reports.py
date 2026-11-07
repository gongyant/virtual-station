from common import *
import numpy as np,shutil
s=pd.read_csv(ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv');qa=read(ROOT/'P9B_INDEPENDENT_QA.json');ca=read(ROOT/'evidence/CA_DATA_AUDIT.json');b=read(ROOT/'evidence/BULLETIN_Q_ADMISSION.json');g=pd.read_csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});gis=read(ROOT/'evidence/GIS_SUMMARY.json');history=read(ROOT/'evidence/HISTORY_FINAL_CHECK.json');p7=read(LAB/'vhs_p7a_hydrological_models/P7A_FINAL_STATUS.json')
references=read(ROOT/'sci/VERIFIED_REFERENCE_METADATA.json')
reftext='\n'.join(f"- {r['doi']}: {r.get('title',['NOT_VERIFIED'])[0] if isinstance(r.get('title'),list) else r.get('title','NOT_VERIFIED')}. https://doi.org/{r['doi']} — metadata verified={r['verified']}" for r in references)
claims=[dict(claim='Balkhash-Alakol has publicly reported monthlyQ in officialbulletin',evidence='data/P9B_BULLETIN_MONTHLY_Q_TRANSCRIPTION.csv',grade='ACTUAL_TRANSCRIPTION_NOT_TRAINING_ADMISSION',limitation='252reportedrows;180provisional49linked;36sourceconflicts;license/QC/definitionpending'),dict(claim='20originalpoints+10tributaryalternativeshaveoutlet-proxycatchments',evidence='P9B_CATCHMENT_DELINEATION_STATUS.csv',grade='ACTUAL_GIS_PROXY',limitation='30records29uniquehosts;0exactpointcatchments;onehostpointconflict'),dict(claim='NationalvirtualpredictionaccuracyinKazakhstan',evidence='NONE',grade='NOT_AVAILABLE',limitation='NoKazakhstantrainingorvalidationexecuted'),dict(claim='P7MEMdevelopmentgain',evidence=str(LAB/'vhs_p7a_hydrological_models/P7A_FINAL_STATUS.json'),grade='EUROPEAN_KNOWN_GAUGE_DEVELOPMENT',limitation='Last2015blocknegative;exposed2018-2020posthoc;notPUBorKazakhstan'),dict(claim='P7SLfailedpromotion',evidence=str(LAB/'vhs_p7a_hydrological_models/P7A_PROMOTION_DECISION.json'),grade='FROZEN_NEGATIVE_RESULT',limitation='Do not omit'),dict(claim='EuropeanPUBmacroregiontransferweak',evidence=str(LAB/'vhs_kaz_n1_national_virtual_stations/pub/EU_PUB_SUMMARY.csv'),grade='EUROPEAN_PUB_DEVELOPMENT',limitation='NotindependentKazakhaccuracy;negativeNSEretained')]
csv(ROOT/'sci/CLAIM_EVIDENCE_MAP.csv',claims)
md('sci/01_RESEARCH_QUESTION_AND_METHODS_DRAFT.md','''# Manuscript working draft — Methods

**Research question:** Can meteorological memory gains at calibrated gauges survive target-label exclusion and geographically structured validation, and what data evidence is required before admitting a virtual gauge in a transboundary endorheic basin?

## Draft: completed data preparation

We separated temporal reconstruction at previously calibrated gauges from prediction at locations whose discharge labels are excluded. The Kazakhstan pilot covers the Balkhash–Alakol water-management basin. Public river and sub-basin geometry was processed independently of the frozen European model experiments. We did not fit or select a hydrological model during this data-admission stage.

The P9A HydroRIVERS network and station crosswalk were verified against their SHA256 manifests. The 49 selected coordinates remained provisional matches rather than certified station identities. Original station codes, names, coordinate sources, nearest source reach identifiers and match distances were retained. Cross-source corroboration used manually reviewed river and locality names and, where available, independently published catchment areas. A documentary statistics period was not treated as an acquired discharge series, a commissioning date or a migration history. Conflicting areas remained explicit source conflicts.

Directed river relationships were derived from unique HydroRIVERS reach identifiers and their downstream links, following the hydrographic framework described by Lehner and Grill (2013). Distances included the within-reach distance between the upstream endpoint and each snapped site. A path from a headwater to a site was distinguished from the summed lengths of all connected upstream branches. Transboundary upstream geometry was retained. Scalar downstream routing was not assumed to establish actual bifurcations, diversions, reservoirs or changing lake connections.

Because a complete, compatible hydrologically conditioned DEM and flow-direction raster was unavailable, we did not label the candidate catchments exact. We assembled the HydroBASINS L12 upstream union terminating at each reach-assigned source sub-basin outlet. An interior river point can have a different watershed from that outlet. We therefore reported the unresolved host-unit area, whether the source host polygon contains the point, source-area discrepancies, duplicated proxies and cross-border area. Removing the host polygon does not generally establish a strict lower bound on the point catchment, because tributaries can join within that unit.

Thirty candidate records comprise the 20 original main-chain points and ten alternatives selected from different directed tributary paths using fixed geometry rules. Neither a candidate count nor a valid polygon constituted hydrological admission. Nominal ERA5-Land grid-cell intersections were calculated for outlet proxies only. The resulting normalized area weights are preparatory objects and were not used as certified point-catchment forcings or to train a model. ERA5-Land is a reanalysis product rather than a local gauge observation (Muñoz-Sabater et al., 2021).

## Draft: prospective P10 analysis, not yet executed

P10 will compare donor climatology, geographic donor transfer, area-normalized donor transfer, static-and-climate similarity transfer and, conditional on data support, a low-dimensional shared model. All target discharge, target-derived statistics and target seasonal templates will be removed before training and tuning. European station-specific coefficients will not be transferred as if calibrated for Kazakhstan. Training-fold transformations and donor selection will use eligible donor data only.

The design distinguishes leave-one-gauge-out, nested-donor exclusion, tributary-group masking and forward year blocks. A future independent label set must be held by a separate custodian, with predictions sealed before scoring. Reported 2021–2024 values and aggregates inspected in this stage cannot be relabeled unseen confirmation data. NSE, KGE and their components will be reported with explicit baselines; they do not share an interchangeable zero-skill interpretation (Knoben et al., 2019). Related gauges and seasons will not be treated as independent basin replicates.

## 中文核对

以上前半段描述本轮实际处理，P10部分明确使用将来时。没有宣称模型已完成哈萨克斯坦验证，没有将出口代理称点位精确边界，没有把年度月Q求和当年平均。发表前须补齐真实Q许可/QC、精确或经验证误差可接受的汇水区及同源P/T；作者需核对论证和数据披露范围。
''')
md('sci/02_DATA_AND_EXPERIMENT_PROTOCOL_DRAFT.md','''# Draft: Data and experimental protocol

The CA-discharge v1.0 GeoPackage was retrieved from Zenodo record8147591 and verified against its published MD5. It is distributed under CC-BY4.0. Its station, basin, discharge and quality-flag layers were inspected separately; long-term norm discharge was not treated as a historical time series. Marti et al. (2023) describe the yearbook provenance and preprocessing. All six records labeled KAZ lie outside the selected basin. The acquired Sayram–Tasarik monthly series therefore supplies no target-basin training labels. Source quality flags and possible preprocessing were retained, rather than describing every numeric entry as an untouched daily observation.

The official Kazakhstan bulletin supplied reported monthly figures for March2021–February2024. We transcribed the printed table without correction, verified numeric entries against independently extracted PDF word positions, mapped water-year labels to calendar months and checked printed seasonal and annual sums using tolerances derived solely from displayed precision. The Lepsy records with internal inconsistencies were retained as rejected evidence. Public document availability did not establish unrestricted model-training or redistribution rights. Matching five named sites provisionally to the coordinate catalogue did not certify station codes, positions or relocation histories.

Data admission precedes model evaluation. For the prospective primary study, the design proposes at least eight admitted gauges in three predefined tributary groups, each with at least eight complete calendar years. These are design choices, not empirically established thresholds. Short, unresolved or imputed records cannot be silently promoted to the primary set. All models must use identical legal station-month support. Negative scores, source conflicts and failed folds must remain visible.

This project has already inspected European temporal and spatial development results. Its known-gauge memory-model improvement is not evidence of Kazakhstan ungauged accuracy. The unsuccessful P7-SL variant, the negative final time block of P7-MEM, and weak macro-region donor transfer must accompany positive results. The Kazakhstan P10 design has not been executed, and no truly independent future target set has yet been obtained.

## Data Availability — draft

CA-dischargev1.0 is available from https://doi.org/10.5281/zenodo.8147591 under its deposited CC-BY4.0 terms. HydroRIVERS and HydroBASINS are reused under the HydroSHEDS terms and required attribution, accessible through https://www.hydrosheds.org/. Official bulletin material was accessed through https://www.kazhydromet.kz/en/water-resources/. Its data-use and redistribution scope remains to be clarified with the provider; local extraction is not a grant to republish an entire third-party archive. The generated GIS proxies, source audit and protocol are preserved locally with source hashes; no public repository deposition or new DOI is claimed. Restricted teacher data are not included.

## Code availability — draft

P9B acquisition, geometry, transcription and verification scripts are preserved in the local delivery code directory with SHA256 manifests. No public repository URL has been assigned. Candidate driver values and P10 model outputs do not yet exist and are not described as available.
''')
md('sci/03_LITERATURE_OVERLAP_AND_REQUIRED_EXPERIMENTS.md',f'''# 文献重合、负结果与投稿前必补项

已核实参考文献（见VERIFIED_REFERENCE_METADATA.json，DOI元数据5/5）：
{reftext}

- Marti et al.已有中亚年鉴整理、站点定位、流域及源QC；本轮不能把公开数据库下载、已有站点汇编或CHELSA提取说成首创。
- Lehner和Grill已有全球拓扑与分级方法；HydroBASINS上游合并和测长是复用，不是新河网算法。
- ERA5-Land已是标准再分析资料；使用P/T与面积加权本身不构成预测创新。
- Apel et al.(2018)已有中亚简洁统计模型、前期气象/水文预测因子和验证。我们的目标月气象历史重建不等于其季节预报，加入前期信息也不能单独宣称首次。
- NSE/KGE解释应遵循明确基线；Knoben等已说明二者零基准不同。不能以某个正KGE或相对技能百分比冒充普适准确率。

本次是定向引用核实与重合清单，不是全面新颖性检索，未声称穷尽文献。

已有必须保留的负面证据：P7-SL开发均值技能{p7['promotion']['P7-SL']['station_mean_skill']*100:.3f}%且未晋升；P7-MEM最后2015时间块{p7['promotion']['P7-MEM']['block_skill']['2015']*100:.3f}%；欧洲PUB留宏观区域最近邻迁移中位NSE约-0.512。上述均是欧洲开发/已暴露证据，不能转写为哈萨克斯坦已验证精度。

投稿前必须完成：①本国真实Q身份/许可/QC及月均定义；②点位汇水区与流向、湖库/引水边界检查；③同源P/T及历史一致性；④目标Q全时期遮蔽、供体基线和嵌套供体排除；⑤整支流留出和独立时间块；⑥季节/记忆消融与不确定性；⑦另由保管者保存的新确认标签；⑧按水系依赖报告完整负NSE与失败，不按成绩删站。

图源/许可：本轮地图来自实际计算GIS及P9A，未复制论文图片；官方PDF页渲染仅核验，不作为自有科学图公开发布。CA相关派生须署名并说明处理；QazSu坐标批量重发条款及官方月Q训练/再分发许可待核实。旧P6/P7图的源码/源表由原清单指向，未修改。
''')
md('P9B_SCI_WRITING_PROGRESS.md','''# SCI并行写作实际进展

已新建sci目录，未改P9A原大纲。已完成一句话研究问题、CLAIM_EVIDENCE_MAP.csv、方法初稿、数据与实验协议初稿、Data/Code Availability草稿、五篇真实DOI核验记录、文献可能重合/图源许可/必补实验清单。草稿采用通用SCI研究论文框架，方法已执行部分与P10待执行部分明确分开；不是已完成SCI论文或独立验证声明。

欧洲负结果、P7-MEM最后时间块退步、P7-SL失败及PUB跨区域不足均保留。新发现的官方Q仅源抄录，仍未模型准入；不填充哈萨克斯坦NSE或显著性。写作下一步依赖本国真实数据准入和P10实验，不能靠网页或代理几何代替。
''')
md('P9B_FIRST_BASIN_READINESS.md',f'''# 巴尔喀什—阿拉湖启动条件

**Q_NOT_ADMITTED；P10_NOT_READY。** 本轮取得真实来源，但尚无可直接用于正式训练的首流域标签。

已取得：官方194页公报与7站×36月=252条原样抄录，其中5个具河名/站址/面积互证的临时点对应180月；6站216月算术合计在印刷精度内一致，Lepsy36月存在内在冲突全部保留。仅3个水文年、2个完整日历年，逐日QC、月均定义、迁站史、正式代码/坐标认证及训练/再利用条款仍未建立。公报的63个河流站是该报告口径，不等于当前49点目录已完成63站核对。

CA-discharge24.6MB、CC-BY4.0、官方MD5已验证：KAZ6点都在Arys，本流域0；唯一国内16390有492月真实来源记录，但在流域外且源QC重复/水量平衡标志失败需复查，不能换成首流域训练数据。

实站：49条坐标与P9A一致；11条得到官方文字/河名或面积上下文支持，依旧不是官方身份认证。14419面积QazSu479与公报484km²明确SOURCE_CONFLICT，不改任一源。建停/迁站和完整原始Q仍未知，统计时段不是本轮已获连续序列。

空间：20原主链点与10个互补支流候选，30条L12出口代理记录、29个唯一host，1点不在源指定host内。准确点位汇水区0；既有13份FABDEM仅局部且无完整匹配D8，不能据此声称完成精确划分。上游境外面积保留，主链最大代理194362.892km²，其中境外约58244.686km²；不能截去境外再算驱动。

驱动：33710条0.1度名义格点交叠权重已真实计算，但仅PROXY_ONLY；ERA5实际P/T新值下载0，正式点位驱动准入0。区域欧洲旧权重未移用。源属性面积与几何面积最大相对差{s.proxy_area_relative_difference.max()*100:.3f}%；格点交叠与完整代理测地面积最大差{qa['grid_area_partition_max_relative_error']*100:.5f}%独立记录，不称精确面积守恒。

下一步可实际启动：向数据负责人核验5个已抄录站原始月均Q和更多历史、QC/单位/日界/许可，优先解释Lepsy源冲突及14419面积差；取得匹配流向/水文DEM或经验证的点位集水区，重新检查源host冲突；之后才下载目标时段ERA5并验证处理。申请材料见P9B_DATA_USE_REQUEST_ZH.md，未自动发送。P10实际折须在准入后生成，本轮只冻结协议，不把49个元数据点冒称49个合格验证站。
''')
md('P9B_COMPLETION_REPORT_ZH.md',f'''# KAZ-P9B完成报告

本轮实际下载、解析、转录、GIS计算与独立复核已完成；停于首流域准入和P10准备，未训练、未预测、未评分、未动网站或教师数据。

## 已真实完成

1. 复用P9A/P8公开源与拓扑，初始及最终受保护清单{history['checked']}文件SHA一致。独立新目录保存全部代码、来源、运行日志、GIS和报告。
2. CA-dischargev1.0官方GPKG24576000bytes，MD5 e0ba6664aaec3e0b27138abdfd4ba263，SHA256 03e2ff19002d6f5c53663495f1419b8ce9ed451bda669e55bafb3c521bf15e2a。实际297gauges/295位置、136时序CODE/134规范化地点及244632行，不能把网页135直接当抽取数；4个suffix别名用原码+res映射，计数差异保留。KAZ只有6站，首流域0。未下载11.8GB原始包或228MB脚本包。
3. 合法公开CA国内16390 Arys-Sayram/Tasarik，1980-2020有492个有限非负月记录，m³/s、无年月重复。源qual_duplicates/qual_wb为0且可能含未逐条标识插补，需复查；位于流域外，不用来替代本流域样本。
4. 官方水文数据库正常公开请求25秒读取超时，未绕过。官方公报页及14,157,668bytes PDF已取得，SHA256 c1f577215647109a6d10827e4d34991fa041e2af0365f0c3a3f2f0063c4d9141，194页解析并渲染附录核对。真实抄录252站月、7站/3个水文年，5站180月可与49点作临时语境关联；216站月表内合计可按印刷舍入解释，Lepsy36站月源冲突保留，不改值、不补齐。所有这些仍Q_NOT_ADMITTED。
5. 49站逐项交叉表保留原码/坐标/河段/等级/距离，增加来源、English官方文字、统计时段及缺口；11条有官方上下文，未升级正式认证；14419面积479/484km²冲突保留。报告称63站与49混合来源/不同口径不可直接减法认证。
6. 实算20点及其到49站的网络关系，并从已筛选池选择10个不同支流路径替代点，保持500m吸附、5km已知站排除、3km点间距及面积下界规则。30代理记录、29唯一host；原20点190对全部嵌套，且1对host代理相同，不能当20个独立流域。
7. 原HydroBASINSAS12上游全闭包合并，不在国界截去境外汇水区，记录面积及host局部不确定性。主链代理范围85756.674–194362.892km²；出口代理不是精确点面积。1点host不包含标为SOURCE_CONFLICT。独立复核还发现{qa['alternate_proxy_nested_pairs']}对备选的代理包含关系，河网不同路径不自动等于集水区空间独立。
8. 实算33710条ERA5名义0.1度格点面积权重、{gis['unique_ERA5_grid_centres']}个唯一格心，均仅PROXY_ONLY。未取得本轮ERA5P/T数值，未移用欧洲权重。13个DEM头检查显示局部覆盖/无匹配全流域D8，不伪造精确划分。
9. 冻结P10科学协议和暴露账本，完成SCI问题、方法/数据/协议初稿、声明草稿、证据映射、5篇DOI核验与重合/补充实验清单；保留P7-SL失败、P7-MEM时间块退步、欧洲PUB负结果。

## 验证与真实失败

独立数值/来源/转录/图关系实现检查{qa['passed']}通过、{qa['failed']}失败；252个抄录值另由PDF字词坐标逐一复核。来源表内算术QC为{qa['source_arithmetic_QC_passed']}通过、{qa['source_arithmetic_QC_failed']}失败，后者是数据源问题而不是被抹去的软件失败。实现正确地标记冲突不等于数据质量全通过。最后历史{history['passed']}/{history['checked']}一致。

下载曾在22749144字节网络读取处截断，本地保留22020096字节；同一官方公开文件Range206补2555904字节后MD5通过。日志UTC字段冲突、只读WAL访问、空日期列类型问题和源论文PDF中断均有恢复说明；没有修改网络设置、证书、数据库头或原Q。原SCI论文PDF未下载成功，文献内容经官方网页/PDF网络工具核验，DOI元数据5/5保存，不将未取得文件写成成功。

## 已有但尚未准入

252条公报月Q、其中180条关联原49点；492条CA外流域月Q；30个出口代理/33710权重；49个临时站。未满足原始观测、单位/月均定义、逐日/月QC、迁站与站点码认证、许可、点位边界和训练年数的组合准入。它们不是可训练样本或正式VHS。

## 缺失/阻塞

首流域连续合格Q、明确训练/保存/再发布范围；正式站码/坐标/迁站记录；足够历史和独立供体组；完整兼容水文DEM/D8或已认证点位边界；同口径P/T实际值和一致性；真正未暴露未来标签。Q_NOT_ADMITTED / P10_NOT_READY，FUTURE_HOLDOUT_NOT_AVAILABLE。

## 下一阶段允许推进

可以继续源方数据核验、精确流向/集水区和气象资料准入；实际数据齐备后冻结样本和真实折，再另行安排P10。不能把本轮已解析2021–2024公报当盲集，不能把公开文档访问当业务认证或全国1000站模拟。fit_calls=0，模型预测/评分调用0，正式VHS=0。
''')
md('P9B_REPRODUCTION_GUIDE.md',f'''# 复现及文件映射

数值/GIS环境：{sys.executable}，-B；无需安装。仅官方PDF读取/渲染使用现成bundled pypdf/pdfplumber/PDFium，未改变科研Python环境。

只读验证封存：
```powershell
& '{sys.executable.replace(chr(92),'/')}' -B '{(ROOT/'code/verify_delivery.py').as_posix()}'
```

数据生成依赖：acquire.py（初始保护/小文件）→必要时resume_download.py（只执行一次合法HTTP Range恢复）→gis.py→q_audit.py→bulletin_sources.py→extract_bulletin.py/render_bulletin.py（bundledPDF读取）→bulletin_admission.py→ca_key_audit.py→prepare_protocol.py→verify.py→reports.py→figures.py/figure_qa.py→人工查看→seal.py。仅在独立新目录设置VHS_P9B_OUTPUT后重算，不能覆盖已封存目录。GIS脚本会拒绝已存在的新GIS文件。当前来源皆本地，可复制已获快照及哈希后跳过网络；外部页面会变，重访须新快照。

注意bulletin_admission.py为人工原样转录矩阵，不是模型或合成数据；独立verify.py从PDF字词位置读数，校验所有252值与真实月份。Lepsy36冲突行保留不修改。CA时序仅公开KAZ16390被读取数值，其余按日期/分辨率统计，不访问任何教师文件。GeoPackage使用immutable只读，不能通过改WAL头解决警告。CA数据为CC-BY4.0，官方公报/QazSu完整再发布及训练范围未确认，交付仅本地研究，不自动上传网站。

GIS为P9B_FIRST_BASIN_GIS.gpkg，候选、首流域、49点、源集水区出口代理及CA其他本国流域分层。P9B_CATCHMENT_DELINEATION_STATUS是点位精度/面积/跨境限制；P9B_CANDIDATE_NETWORK_RELATIONSHIPS是有向关系和内河段距离；权重data/ERA5_LAND_PROXY_AREA_WEIGHTS是准备值，不是ERA5实测或重分析值本体。

P9B_AVAILABLE_Q_INVENTORY逐来源/站/分辨率列出本流域与流域外；统计时段不等同于已取得原始Q，N/A不改0。P10JSON/MD冻结设计而非已执行折。暴露台账单列2021–2024月值及整本公报，未来保管机制尚未具备。

所有实际命令、下载、恢复和质量问题见RUN_ATTEMPTS.jsonl、source各DOWNLOAD记录及evidence/FAILURE_RECOVERY_LOG.json；独立QA见P9B_INDEPENDENT_QA.json；软件检查与数据源6项算术失败分开报告。最终SHA256SUMS覆盖代码、来源、GIS、CSV、图、报告和证据（清单自身不自引用）。
''')
failures=[dict(issue='eventUTCkeycollision',evidence='initialacquireTypeError',resolution='renameeventtimestamp;retainresumeevent;nohistoricdatachanged'),dict(issue='officialsmallfileIncompleteRead',wire_bytes=22749144,local_partial_bytes=22020096,resolution='HTTP206bytes22020096-24575999;MD5verified'),dict(issue='sourcearticlePDFtransfertruncated',wire_bytes=3455651,remaining=1613475,resolution='notclaimeddownloaded;primaryPDFwebreadandDOImetadataverified'),dict(issue='readonlyWALdatabase',resolution='SQLiteimmutable1/GDALIMMUTABLEYES;fileMD5unchanged;noheaderrewrite'),dict(issue='N/Adatefloatdtype',resolution='explicitobjectdatecolumns;idempotentbulletininventory;Qunchanged'),dict(issue='Lepsymonthsconflictwithsourceannualsum',resolution='36literalmonthsretainedandquarantined;nomodeluse'),dict(issue='CA135documentedvs134actualbaseQlocations',resolution='raw136CODEs/134locationsrecorded;notforcedto135'),dict(issue='sourcehostpointoutsidepolygon',resolution='1candidateflaggedSOURCE_CONFLICT;exactareaN/A'),dict(issue='consoleGBK/quotinginspectionerrors',resolution='UTF8stdoutandstandalonescripts;nodatachanges')]
js(ROOT/'evidence/FAILURE_RECOVERY_LOG.json',failures)
js(ROOT/'P9B_FINAL_STATUS.json',dict(task='KAZ_P9B',completed_data_preparation=True,Q_status='Q_NOT_ADMITTED',P10_status='P10_NOT_READY',fit_calls=0,prediction_calls=0,score_calls=0,teacher_Q_reads=0,web_changed=False,CA_public_KAZ_months=492,official_reported_target_months=252,provisionally_linked49_months=180,source_conflicting_months=36,official49certified=0,official_context_corroborated49=11,original_engineering_candidates=20,alternate_engineering_candidates=10,outlet_proxy_records=30,unique_proxy_hosts=29,exact_point_catchments=0,ERA5_weight_rows=33710,ERA5_values_downloaded=0,numeric_QA_passed=qa['passed'],numeric_QA_failed=qa['failed'],source_QC_failed=qa['source_arithmetic_QC_failed'],history_unchanged=history['passed'],future_holdout='FUTURE_HOLDOUT_NOT_AVAILABLE',formal_VHS=0,P10_started=False))
with (ROOT/'P9B_COMPLETION_REPORT_ZH.md').open('a',encoding='utf-8') as f:
    f.write('\n## 地图及验收边界\n\n两张真实GIS研究地图提供PDF、SVG及300dpi PNG，输入哈希见figures/FIGURE_INPUT_PROVENANCE.json。最终图人工查看；字形下限检查通过。自动碰撞检查因当前环境无PyMuPDF为NOT_AUDITABLE，未安装依赖，不宣称通过或期刊终稿验收。地图不是模型预测，所有点继续保留准入状态。\n\n独立PDF读取器最初因单位与数值文字的6pt垂直偏移及跨页首行漏读而失败，已修复读取器，未改抄录值；失败次数与最终通过数保留在RUN_ATTEMPTS.jsonl。最终所有252个值逐项匹配源PDF。\n')
event('reports_and_SCI_drafts_complete',Q_status='Q_NOT_ADMITTED',P10='P10_NOT_READY',fit_calls=0)
