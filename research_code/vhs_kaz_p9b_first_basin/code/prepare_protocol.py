from common import *
import numpy as np,geopandas as gpd,pyogrio
gis=read(ROOT/'evidence/GIS_SUMMARY.json');ca=read(ROOT/'evidence/CA_DATA_AUDIT.json');bulletin=read(ROOT/'evidence/BULLETIN_Q_ADMISSION.json');s=pd.read_csv(ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv');g=pd.read_csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str})
drivers=[]
for r in s.itertuples():drivers.append(dict(candidate_id=r.candidate_id,role=r.engineering_role,catchment_state=r.catchment_state,point_catchment_certified=False,proxy_area_km2=r.proxy_geodesic_area_km2,foreign_proxy_area_km2=r.foreign_proxy_area_km2,grid_cells=r.grid_cells,weights_file='data/ERA5_LAND_PROXY_AREA_WEIGHTS.csv',weights_status='COMPUTED_PROXY_ONLY_NOT_ADMITTED',ERA5_values_status='NOT_DOWNLOADED',P_unit_contract='monthlysum_mm;nativehourlytp_m*1000_aftercorrectdeaccumulation',T_unit_contract='monthlymean_degC;hourlyK-273.15',aggregation='areaweightedhourly->UTCdaily->monthly;noimplicitgaps;realprecedingcalendarmonth',time_window='NOT_SELECTED_NO_ADMITTED_TARGET_Q',static_status='sourceorders,topology,andoutletproxyavailable;pointterrainandlandcoverunverified',training_admission='P10_NOT_READY'))
csv(ROOT/'P9B_BASIN_DRIVERS_STATUS.csv',drivers)
coords=gpd.GeoDataFrame(g,geometry=gpd.points_from_xy(g.longitude,g.latitude),crs=4326);coords.to_file(ROOT/'P9B_FIRST_BASIN_GIS.gpkg',layer='provisional_gauges49',driver='GPKG',engine='pyogrio')
# Explicit source conflict, not a silent switch to a neighboring station.
qc=pd.read_csv(ROOT/'data/KAZ_CA_SERIES_QC_SUMMARY.csv');qc['review']='16390:qual_duplicates=0andqual_wb=0 require review;qual_consistency=0meanspersistent andqual_order=0notapplicable, not failed';csv(ROOT/'data/KAZ_CA_SERIES_QC_SUMMARY.csv',qc)
exposure=[dict(source='P9A/P9B49metadata',exposure='coordinates,names,areas,topology',target_Q_exposed='No historicalQinP9A'),dict(source='CA-dischargev1.0',exposure='all297metadata+seriesdates;numericQonlyKAZ16390',target_Q_exposed='492monthly1980-2020Arysoutsidefirstbasin;sourceQnotuned'),dict(source='officialbulletin2023',exposure='all194pagesparsed;Table4visualQA;252reportedmonthvalues2021-03to2024-02',target_Q_exposed='5provisionallylinked49stations180months;36Lepsyconflictingrowsretained;annual/seasonalaggregatesalsoexposed'),dict(source='EuropeP6/P7',exposure='oldresearchknown;2018-2020exposedandwholearchivesparsed',target_Q_exposed='Not Kazakhstan test evidence'),dict(source='futureKazakhholdout',exposure='NOT_ACQUIRED_OR_CERTIFIED',target_Q_exposed='FUTURE_HOLDOUT_NOT_AVAILABLE;2024notclaimedunexposed')]
csv(ROOT/'P9B_LABEL_EXPOSURE_LEDGER.csv',exposure)
protocol=dict(version='KAZ_P10_DESIGN_P9B_FROZEN_BEFORE_MODEL_FIT',task='RECONSTRUCTION_WITH_OBSERVED_MET',target_basin='Balkhash-Alakol',current_Q_primary_admitted_stations=0,current_execution='P10_NOT_READY',future_holdout='FUTURE_HOLDOUT_NOT_AVAILABLE',
 target_Q_exclusion='alltargetQandderivedQandWremovedfromdonorfit,preprocessing,seasonaltemplates,hyperparametersanddonorselection;scoreprocessjoinslabelsonlyafterpredictionseal',
 primary_Q_rules=['realstationidentityandmigrationhistoryresolved','explicitresearch/trainingpermissionandunits','observedmonthlymeansandcalendarsemanticsconfirmed','notimputed;rowQCresolved;sourceflagsreviewed','atleast8completecalendar-yearspergauge;atleast8gaugesin3predefinedtributarygroupsforcandidateprimarystudy'],
 thresholds_are_design_choices_not_proven_facts=True,short_record_rule='retainforlimiteddescriptiveanalysisafteridentity/license/QCadmission;notprimaryconfirmatoryset',
 sample_freeze='ID/date/QC/coveragebeforemodelscores;intersectionallcandidatemodelsupport;noscore-basedstationormonthremoval',
 schemes=['LEAVE_ONE_GAUGE_OUT','LEAVE_ONE_GAUGE_OUT_REMOVE_ALL_NESTED_UP_DOWN_DONORS','LEAVE_TRIBUTARY_OR_SUBBASIN_GROUP_OUT','FORWARD_EXPANDING_YEAR_BLOCKS'],
 temporal_rule='date-onlycommonqualifiedwindow;last2completeyearsofpre-holdoutarchiveassealeddevelopment-timeblock;earlier>=5completeyearstrainandnext2yearstestexpanding;insufficientblocks->descriptiveonly;genuinelyfutureunexposedcustodiedseparately',
 inner_selection='nestedyearanddonor/networkgroupfoldsinsideoutertrainingonly;noscalingorfittingontargetlabels',
 donor_rules='geographicrankordrainage/climatesimilarityfrommetadataonly;removeconnectedup/downandnestedcatchmentdonorsinstrictscheme;weightslearnedonlydonortrain',
 baselines=['DONOR_MONTHLY_CLIMATOLOGY','NEAREST_GEOGRAPHIC_DONOR','AREA_NORMALIZED_DONOR_TRANSFER_IF_EXACT_AREA_VALID','STATIC_AND_TRAIN_CLIMATE_SIMILARITY_TRANSFER','LOW_DIMENSION_REGIONAL_SHARED_RIDGE_CONDITIONAL_SUPPORT'],
 area_transfer='Qtarget=Qdonor*Atarget/Adonor;normalizey_mmday=86.4*Q_m3s/area_km2;rejectzero/missing/proxyunadmittedarea',
 ridge_grid=[.01,.1,1,10,100],ridge_rule='one-SEstrongerregularization;innerdonorandyearblocks',
 P7_MEM='futurelegitimatereregionalizeddonorversiononly;noEuropeantargetcalibratedcoefficients',
 metrics=['NSE','KGEandcomponents','RMSE','MAE','PBIAS','MSEskill_againstsame_support_donorbaseline','stationpassfraction','DJF','MAY_JUNE','highlow_trainquantiles'],
 uncertainty='gauge-equalandnetworkgroup-aware;yearblocks;nosignificanceclaimswithinsufficientindependentgroups;N/Awithreason',
 future_test='independentcustodianverifiesprovenanceandpriorreading;lockID/date/QC/driverprotocolandmodel;sealpredictionsbeforeopenQ;2021-2024bulletinnotblind',fit_calls=0)
js(ROOT/'P9B_P10_VALIDATION_PROTOCOL.json',protocol)
md('P9B_P10_VALIDATION_PROTOCOL.md','''# P10科学验证预注册设计（尚未启动）

当前标志Q_NOT_ADMITTED / P10_NOT_READY。本文件和同名JSON冻结的是科学规则，不是宣称已有可执行49折或已获数据许可。当前首流域主样本合格站0，实际训练/调参/评分均0。

目标任务为已观测目标月气象的月流量历史重建，不是提前预报。主研究暂定至少8个合格实站、3个预先确定支流组，每站至少8个完整日历年；这是研究设计门槛，不是客观证明的样本规律。3个水文年公报抄录即使算术一致，也不满足主研究年数，且尚有身份、许可、QC与月均定义问题。短记录只可另行标注描述性探索，不混入确认性主集。

空间协议依次为留一站、完全排除上下游嵌套供体的留站、整支流/子流域成组遮蔽。分组由河网及集水区决定，不由NSE选择。目标站全部时期Q及W/反演量/目标Q衍生属性不得进入训练、季节模板、归一化、供体选择或调参；目标历史Q气候态不是PUB合法基线。允许仅由供体训练Q形成供体月气候态。

基线包括供体季节气候态、地理最近供体、精确面积准入后面积归一化供体、静态和训练期气候相似性供体、支持足够时的低维共享Ridge。面积归一化采用86.4Q/A(mm/day)，新点转回m³/s；未经准入的出口代理面积不得用于主试验。Ridge网格0.01/0.1/1/10/100，内层按供体网络组及年份选择one-SE更强正则。P7-MEM以后需重新构建供体区域化，不能移用欧洲站点校准系数。

时间窗仅依据实际Q日期/QC/气象覆盖确定后再冻结：在合格档案内保留末2个完整年为开发期时间块，更早至少5年训练、后续2年验证，扩展窗口；无法形成足够块则只做描述性。真正未来确认集须另外由独立保管者锁定未解析、未评分、未参与选型的新资料。公报2021—2024及本轮解析的统计资料已暴露，2024不得冒充未接触测试集；现无可确认未来盲集。

所有标准化、月气象气候态、静态相似性尺度及超参数仅在外层训练供体与日期内拟合。允许无Q月份真实外生P/T和真实上月P，不能从缺测年份推导Q。相同模型比较相同站/月/标签；先封存预测，再由独立评分进程连接Q。季节、年度与逐站负NSE全部保留；不直接混合跨站m³/s²误差。主要报告站点等权和水系组描述，NSE/KGE分量、RMSE/MAE/PBIAS、相对同支持基线MSE技能；样本/分母不足返回N/A而非0。

软件验收、数据图完整或算术合计一致不代表业务认证、因果识别或独立水文验证。正式P10实施前须用真实已准入站点生成并封存实际折ID、样本哈希、协议版本和数据使用范围；本轮不执行。
''')
md('P9B_DATA_USE_REQUEST_ZH.md','''# 提交实际数据负责人的最小申请材料（未发送）

拟研究巴尔喀什—阿拉湖流域月径流重建及无资料站验证，仅本地非业务科研。请求提供所附49站对应的正式站码、河名、坐标及精度、建停/迁站史与面积定义；优先核验14004、14011、14118、14160、14561及14419面积479/484km²矛盾。

请求可合法研究使用的连续月平均Q（或日均Q及完整聚合规则），优先>=8完整年：单位m³/s、年月/日界、缺测编码、逐日/月QC、修订/插补标记、源版本及原始记录日期。另请解释公报Table4 pp177–179的月Q与年度求和定义、Lepsy6月值重复年度合计的来源冲突；所述统计时段不等同于我们已获得全部原始Q。

请明确允许的读取、训练/调参、留站和时间验证、预测/参数保存、观测叠图及再发布范围、署名方式与联系流程。我们不会将公开网页访问视为无限训练/再分发许可，也不会使用受限教师Q代替。本申请文本未自动提交或发送，无虚构批准人、许可号或有效期。
''')
js(ROOT/'evidence/PREPARED_STATUS.json',dict(Q_status='Q_NOT_ADMITTED',P10='P10_NOT_READY',official_monthly_reported_rows=252,linked_to49_rows=180,public_CA_outside_basin_months=492,proxy_only_catchments=30,unique_proxy_hosts=int(s.source_host_HYBAS_L12.nunique()),exact_point_catchments=0,grid_weight_rows=gis['proxy_weight_rows'],ERA5_values_downloaded=0,fit_calls=0))
event('P10_protocol_and_drivers_prepared',protocol_sha256=digest(ROOT/'P9B_P10_VALIDATION_PROTOCOL.json'),Q_status='Q_NOT_ADMITTED',fit_calls=0)
