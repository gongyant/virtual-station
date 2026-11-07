from acquire import *
import pandas as pd,numpy as np,platform,importlib.metadata
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def out(name,x):pd.DataFrame(x).to_csv(ROOT/name,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
def md(name,text):(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')
if __name__=='__main__':
 wb=read(ROOT/'evidence/WB_Q_COMPUTATION_SUMMARY.json');catch=read(ROOT/'evidence/TAUTURGEN_D8_RESULT.json');grid=read(ROOT/'evidence/TAUTURGEN_DRIVER_GRID.json');met=read(ROOT/'driver/QALIGNED2000_2015_NUMERIC_VALIDATION.json')
 e2=read(ROOT/'exploratory_temporal/run/E2_INDEPENDENT_VERIFICATION.json');assert e2['failed']==0
 scores=pd.read_csv(ROOT/'exploratory_temporal/run/E2_TEMPORAL_METRICS.csv',dtype={'year':str});main=scores[(scores.variant=='RAW')&(scores.year=='ALL')].set_index('model_id')
 admissions=pd.read_csv(ROOT/'P9C_GAUGE_Q_ADMISSION.csv',dtype={'source_station_id':str})
 admissions['record_kind']=np.where(admissions.source_station_id=='Unnamed: 77','UNNAMED_SOURCE_EXPORT_COLUMN_NOT_A_GAUGE',np.where(admissions.source_station_id=='30001','NAMED_SERIES_WITHOUT_STATION_METADATA','SOURCE_STATION'))
 admissions.loc[admissions.source_station_id=='Unnamed: 77','Q_admission']='NOT_A_GAUGE'
 admissions.loc[admissions.source_station_id=='30001','Q_admission']='NO_STATION_IDENTITY_METADATA_NOT_ADMITTED'
 admissions.loc[admissions.source_station_id=='10195','Q_admission']='OBSERVED_SOURCE_DESCRIPTIVE_NUMERIC_QC;PRIMARY_DAILY_QC_PENDING'
 admissions.loc[admissions.source_station_id=='10195','E2']='EXPLORATORY_TEMPORAL_READY_EXECUTED_LIMITED_C0_C0PT'
 out('P9C_GAUGE_Q_ADMISSION.csv',admissions)
 cross=pd.read_csv(ROOT/'P9C_HISTORICAL_STATION_CROSSWALK.csv',dtype={'source_station_id':str,'nearest_P9B_station_code':str})
 cross['name_area_historical_candidate_P9B']=cross.source_station_id.map({'10014':'14118','2314400':'14200','2314600':'14419|14421','10195':'14187'})
 cross['crosswalk_note']=cross.source_station_id.map({'10014':'SameSarytogai/7370km2contextbut14.535kmcoordinateconflict;noassumedmigration',
  '2314400':'SameTalgar/444km2contextbut9.718kmcoordinateconflict;noassumedmigration',
  '2314600':'Nearestcoordinateis14446Koksu1590km2;Tekelicity479vs484contextsuggests14419/14421butriver/coordinateidentityambiguous;notforced',
  '10195':'Tauturgenname/614km2and38.113mcoordinateagreement;researchprovisionalnotofficialcertification'})
 out('P9C_HISTORICAL_STATION_CROSSWALK.csv',cross)
 existing=pd.read_csv(OLD/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});existing['new_WB_strong_provisional_link']=existing.station_code.map({'14187':'10195'}).fillna('NONE')
 existing['new_WB_Q_formal_P10_admitted']=False;out('data/P9C_EXISTING49_LINK_STATUS.csv',existing)
 sources=[dict(source='NCDC_10.12072/ncdc.nieer.db3337.2023',url='https://www.ncdc.ac.cn/portal/metadata/46593408-b951-42d8-b23f-1c79a7342f08',
  acquisition='PUBLIC_METADATA_WEB_VERIFIED;LOCAL_REQUESTS_REMOTE_CLOSED;LOGIN_APPLY_REQUIRED;XLS_NOT_ACQUIRED',license='CC_BY4.0_LISTED;DELIVERY_REQUIRES_APPLICATION',
  claimed_stations=180,actual_stations_acquired=0,actual_target_complete_months=0,file='NOT_AVAILABLE',observed_status='metadata says manually observed daily Q averaged monthly;actual file and rowQC not verified',
  limitation='180/131catalogueclaimsnotactualcountoralltargetbasin;translatednamesneedoriginalagency/countryandcoordinatechecks'),
 dict(source='WB0064229v2',url='https://datacatalog.worldbank.org/search/dataset/0064229/central-asia-flood-hazard-discharge-data',
  acquisition='DAILY_CSV_13822527BYTES_AND_STATION_CSV_3156BYTES_ACQUIRED_HTTP200',license='PUBLIC_CC_BY4.0_WB_CATALOGUE',
  claimed_stations=None,actual_stations_acquired=75,actual_target_complete_months=705,file='source/data_daily_discharge.csv',
  observed_status='Official reportp24declaresdailyobservedQfromGRDC/localinstitutes;notTOPKAPIoutput;perstationoriginalsource/fill/QCnotprovided',
  limitation='UNDECLARED_MIDNIGHT_TIME_FIELD_NORMALIZED;76namedQseries75metadata;publisher_schema_confirmation_pending;System.IO.MemoryStreamfooter22bytes;APIHTTP200invalidresource_directfileworks;4targetlocations57numericstationyearsnotprimaryadmission'),
 dict(source='ZENODO17075252v1',url='https://zenodo.org/records/17075252',acquisition='191514BYTES_XLSX_MD5_VERIFIED',license='CC_BY4.0_ZENODO_API',
  claimed_stations=13,actual_stations_acquired=13,actual_target_complete_months=0,file='source/Water_cycle_components_in_BLB.xlsx',
  observed_status='ANNUAL_RUNOFF_MM_1950_2014;REGRESSION_INFILL_MIX;NO_RAW_OBSERVED_ROW_MASK',
  limitation='846annualrunoffvalues;Kashi2015extravalueand1950-2021annualclimate;notmonthlym3/sQ;notindependentobservations;do_not_reconstructlabels'),
 dict(source='Kazhydromet_database_and_cadastre',url='https://meteo.kazhydromet.kz/database_hydro/',acquisition='DATABASE_READ_TIMEOUT;OFFICIAL_CADASTRE_HTTP200_LOGIN_REQUIRED',license='OFFICIAL_TERMS_NOT_CONFIRMED',
  claimed_stations=None,actual_stations_acquired=0,actual_target_complete_months=0,file='source/KAZ_OFFICIAL_CADASTRE.html',observed_status='NO_NEW_RAW_Q_ACQUIRED',
  limitation='2024newsopenaccessclaimnotcurrentanonymousdownload;noAPIguessingorloginbypass'),
 dict(source='P9B_official_bulletin_reference',url='https://www.kazhydromet.kz/en/water-resources/',acquisition='READ_ONLY_EXISTING_NO_REDOWNLOAD',license='P9B_UNRESOLVED_BULK_REUSE',
  claimed_stations=7,actual_stations_acquired=0,actual_target_complete_months=252,file=str(OLD/'data/P9B_BULLETIN_MONTHLY_Q_TRANSCRIPTION.csv'),observed_status='REPORTED252;NOT_NEW_ACQUISITION;36LEPSYCONFLICTS_REMAIN',
  limitation='nohistoricalconcatenationwithWB;2021-2024alreadyexposed')]
 out('P9C_NEW_Q_SOURCE_RESULTS.csv',sources)
 catchrows=[]
 for r in cross.itertuples():
  pilot=r.source_station_id=='10195'
  catchrows.append(dict(record_kind='NEW_HISTORICAL_Q_GAUGE',station_id=r.source_station_id,source_name=r.source_name,
   status=catch['delineation_status'] if pilot else 'NOT_DELINEATED_IDENTITY_COORDINATE_CONFLICT',
   source_area_km2=r.source_area_km2,delineated_area_km2=catch['delineated_geodesic_area_km2'] if pilot else None,
   area_relative_error=catch['relative_area_error'] if pilot else None,field_exact_area_verified=False,native_raster_point_delineation=pilot,
   resolution_arcsec=3 if pilot else None,ACC_count_verified=catch['matches_source_ACC'] if pilot else False,
   upstream_boundary_complete_in_D8=not catch['source_window_edge_touched'] if pilot else False,foreign_upstream_area_km2=catch['foreign_upstream_area_km2'] if pilot else None,
   limitation='3sgrid/snap104m/identityprovisional;notcertified;physicaldiversionsunknown' if pilot else 'Resolvehistoricalstationcoordinate/sourceidentitybeforeoutletchoice'))
 legacy=pd.read_csv(OLD/'P9B_CATCHMENT_DELINEATION_STATUS.csv')
 for r in legacy.itertuples():catchrows.append(dict(record_kind='P9B_ENGINEERING_CANDIDATE_READONLY',station_id=r.candidate_id,source_name=None,status=r.catchment_state,
  source_area_km2=r.proxy_host_attribute_UP_AREA_km2,delineated_area_km2=None,area_relative_error=None,field_exact_area_verified=False,native_raster_point_delineation=False,
  resolution_arcsec=None,ACC_count_verified=False,upstream_boundary_complete_in_D8=False,foreign_upstream_area_km2=r.foreign_proxy_area_km2,
  limitation='ExistingL12outletproxyonly;notupgraded;hostconflictandduplicatedproxyretained'))
 out('P9C_CATCHMENT_VALIDATION.csv',catchrows)
 drivers=[]
 for r in cross.itertuples():
  pilot=r.source_station_id=='10195'
  drivers.append(dict(station_id=r.source_station_id,source='ERA5_LAND_OFFICIAL_CDS_ARCO' if pilot else 'NOT_DOWNLOADED',
   status='ACTUAL_Q_ALIGNED192MONTHS_VALIDATED_EXPLORATORY' if pilot else 'NOT_READY_NO_ADMITTED_CATCHMENT',
   first_month='2000-01' if pilot else None,last_month='2015-12' if pilot else None,actual_complete_months=192 if pilot else 0,
   actual_complete_days=5844 if pilot else 0,weighted_cells=14 if pilot else 0,leap_days=4 if pilot else 0,
   precipitation='m=>mm;alreadydeaccumulated;intervalendminus1h;UTCmonthsum',temperature='K=>degC;24hdaymean=>monthmean',
   aggregation='newD8catchmentgeodesicareaweights;noEuropeanweights;noQ-basedchoices',
   numeric_precipitation_QC='tinynegative[-.001,0)mm/h=>0onlyinderivedphysicalP;rawPpreserved;monthlycorrection<=.000186mm' if pilot else 'N/A',
   prior_calendar_month='TRUE2000-12availablefor2001-01;2000-01L1unsupported' if pilot else 'NOT_AVAILABLE',
   field_certification='NOT_CERTIFIED',pre1950_support='ERA5_LAND_NOT_AVAILABLE_BEFORE1950'))
 out('P9C_ERA5_LAND_DRIVER_RESULTS.csv',drivers)
 out('data/P9C_STATIC_ATTRIBUTE_ADMISSION.csv',[dict(station_id='10195',attribute=k,value=v,unit=u,status=s,source=source) for k,v,u,s,source in [
  ('longitude',77.616,'degree','SOURCE_METADATA','WBstations'),('latitude',43.337,'degree','SOURCE_METADATA','WBstations'),
  ('reported_area',614,'km2','SOURCE_METADATA_NOT_NEW_SURVEY','WBstations/P9Bareaagreement'),('D8_delineated_area',catch['delineated_geodesic_area_km2'],'km2','NUMERICALLY_VALIDATED_RASTER','HydroSHEDSDIR_ACC3s'),
  ('mean_elevation',None,'m','NOT_PREPARED','CON_DEM_NOT_DOWNLOADED'),('mean_slope',None,'degree','NOT_PREPARED','CON_DEM_NOT_DOWNLOADED'),
  ('land_cover',None,'fraction','NOT_PREPARED','NO_NEW_SOURCE_ADMITTED'),('glacier_fraction',None,'fraction','NOT_PREPARED','NO_NEW_SOURCE_ADMITTED'),
  ('reservoir_diversion_influence',None,None,'NOT_CERTIFIED','NO_PHYSICAL_CERTIFICATION')]])
 ncdc=dict(url=sources[0]['url'],DOI='10.12072/ncdc.nieer.db3337.2023',claimed_station_count=180,claimed_river_count=131,
  description_period='1912-2000partialyears',file_title='1912-2000年（部分年份）中亚地区哈萨克斯坦河流逐月平均流量数据.xls',claimed_size='1.4MiB',
  listed_license='CCBY4.0',access_mode='LoginToApply',source_claim='monthly averages of manually observed daily discharge',
  content_obtained_via='official metadata rendered by web tool;localHTTPclosed;not rawHTML downloaded',actual_XLS_received=False,
  actual_units_rowQC_originalnames_and_station_country='NOT_VERIFIED_UNTIL_FILE',citation='ShenYongping2021;DOIregistered2023;acknowledgeNationalCryosphereDesertDataCenter')
 js(ROOT/'evidence/NCDC_WEB_METADATA_VERIFIED.json',ncdc)
 md('P9C_NCDC_AND_OFFICIAL_DATA_REQUEST_ZH.md','''# 长期实测Q申请与操作说明（草稿，未提交/未发送）

## NCDC：由实际申请人操作

打开 https://www.ncdc.ac.cn/portal/metadata/46593408-b951-42d8-b23f-1c79a7342f08 ，核对DOI10.12072/ncdc.nieer.db3337.2023及1.4MiB XLS。以本人账号通过“登录申请/Login to Apply”办理；若无账号按官网注册。不要把密码或验证码交给脚本。本轮未登录、未申请、未下载受控XLS。元数据标CC BY4.0不意味着跳过文件交付申请。

申请文字：
本人[姓名、单位和真实项目由申请人填写]拟研究巴尔喀什—阿拉湖流域月流量重建与无资料站交叉验证。申请上述长期逐月实测Q及配套测站原名/站码/坐标、历史迁站与启闭记录、原始机构/年鉴出处、单位、缺失码、实测/估算/插补标记和质量说明。仅在获准范围内开展本地数据QC、供体站训练、目标站Q完全遮蔽的验证与论文署名引用；不会以插补/重建Q作为独立实测标签。请确认文件是否完整、每站覆盖和许可范围，是否允许保存派生统计/参数/预测以及所需引用。此段为申请草稿，不代表已获许可。

批准后用官网显示的下载按钮取得原始XLS，保持原名原字节；将文件路径、下载日期和许可/审批说明交接。不要改名覆盖P9B/P9C封存文件。后续在新任务目录计算SHA256、读取真实工作表、逐站按坐标/原名/河名/面积匹配，再统计8站/3组/8年；不能把元数据180站当成180条可用本国序列。元数据“部分年份”不保证所有站连续1912–2000；1950年前缺ERA5-Land，单列覆盖缺口。

## Kazhydromet

官方 https://www.kazhydromet.kz/en/post/2526 是2024年开放档案的新闻。其指向的 https://www.kazhydromet.kz/ru/gidrologiya/gosudarstvennyy-vodnyy-kadastr-poverhnostnye-vody 当前显示仅授权登录用户可访问；公开database_hydro请求超时。本轮没有绕过。由实际负责人在官网账号及正式服务渠道申请地表水年鉴/历史日均或月均Q。

优先核验：14187 Turgen–Tauturgen；14118 Charyn–Sarytogai；14200 Talgar；Tekeli城市附近14419/14421（须先明确河名和站址，不能强行等同WB2314600）。请求WB10195/10014/2314400/2314600与官方原码的关系、日期/日界、迁站、单位和逐日QC；说明Sarytogai/Talgar坐标分别相差约14.5/9.7km、Tekeli存在河名/面积/位置歧义。原P9B五个公报关联站及Lepsy合计冲突请求解释，不能用新资料拼接伪连续历史。

原始许可文件、公开下载与源方回复均原样归档。本轮未自动向任何机构发送邮件或申请。
''')
 md('P9C_P10_READINESS.md',f'''# 数据分级与P10启动判定

当前最高达到 **E2_EXPLORATORY_TEMPORAL_READY（单站、开发用途、带QC限制）**，并已完成有限C0/C0+PT实验；**E3 / P10_PUB_READY 未达到，P10_NOT_READY**。

- E1：实际下载WB日Q与75站目录。4个首流域位置得到705个完整站月、57个完整站年（数值完整，不代表逐日业务QC认证）。13工作表辅助Excel为年尺度重建混合，原始实测行掩码缺失，独立实测标签准入0。
- E2：10195与14187相距38.113m、同为614km²，研究身份暂定；D8面积594.923km²，误差−3.107%，ACC94895像元一致、未截断、14格点面积权重真实计算；2000–2015已有192月P/T。公开WB CC-BY支持本次本地研究；缺少逐日源QC/原始机构逐站链、日界和迁站证明仍是限制，不宣称官方认证。
- E3冻结目标：8站、3预定义支流组、各8完整年及其他完整准入。现有数值长度达标仅4站；坐标/面积紧密佐证只有1站；完成实际栅格边界及驱动仅1站；正式QC/迁站/目标Q遮蔽折与未暴露保管测试集尚不具备。不能把这些维度合并成4个或8个正式准入站，也不调低原P9B门槛。

E2训练2001–2011（131个完整月，2003-07缺8天不插补）/评价2012–2015（48月）；alpha100事前固定、无调参。两模型96条有效预测，预测进程禁读评分标签；封存后单独评分。C0 NSE={main.loc['C0','NSE']:.6f}、KGE={main.loc['C0','KGE']:.6f}；C0+PT NSE={main.loc['C0+PT','NSE']:.6f}、KGE={main.loc['C0+PT','KGE']:.6f}，MSE技能相对C0={main.loc['C0+PT','MSE_skill_vs_C0']*100:.3f}%。这是已知站在已观测目标月气象下的开发期时间重建，不是提前预报或PUB，不是全新盲测。

下一阶段：NCDC/官方长期Q交付与身份/QC核验→达到8站/3组及各8年→对合格站逐一D8边界与P/T准入、静态属性→冻结目标站Q完全排除/嵌套供体剔除/子流域组/向前时间折→独立保管未来标签→另行移交P10。当前候选虚拟点可预测数仍0，不能把本轮实站预测算成新VHS。
''')
 md('P9C_SCI_EVIDENCE_UPDATE.md',f'''# SCI证据更新

新增可支撑事实：合法公开观测来源长期Q现已取得，首流域4站705完整站月/57数值完整站年；Tauturgen具备独立栅格点位划分和192月与Q年代对齐的真实ERA5-Land驱动；首次该已知站固定时间开发比较，C0+PT相对C0 MSE技能{main.loc['C0+PT','MSE_skill_vs_C0']*100:.3f}%，绝对NSE仅{main.loc['C0+PT','NSE']:.6f}。两模型每年及非负次分析全部保留，不能宣称普遍高精度。模型数学只读复用公开P2代码，新参数不覆盖P4/P7。

新增不能支撑的主张：尚无哈萨克斯坦严格无资料站精度、全国可用虚拟站数量或密度实增；4站不等于8站主协议、1个已知站不等于跨流域独立样本。新数据已经为QC解析，不能称未来盲测。ERA5为再分析、目标月气象已知，非预报。3角秒边界有分辨率/吸附误差，非业务认证。尚不识别融雪、地下水、调度等物理原因。

方法增补：把source raw/QC/delineation/forcing/temporal-development/PUB区分。WB CSV的错误尾行和站点坐标冲突、Zenodo年重建而非月实测的否定证据应进入数据流程图与补充表；P9B的252公报月值与36Lepsy冲突、P7-SL失败、P7-MEM时间块退步和欧洲PUB跨区不足保留，不用新结果覆盖。

数据引用：WB Central Asia flood hazard discharge data，0064229，2023-07-21元数据/v2直接文件，CC-BY4.0；观测来源与TOPKAPI模型输出区别参见随附官方技术报告PDF24页。NCDC Shen Yongping，2021，DOI10.12072/ncdc.nieer.db3337.2023（仅已核验元数据，未取文件）；Gan Guojing，2025，DOI10.5281/zenodo.17075252（年重建混合，非独立Q）；HydroSHEDS v1.1 DIR/ACC，技术文档v1.4第18页；ERA5-Land CDS ARCO与Muñoz-Sabater等2021 DOI10.5194/essd-13-4349-2021。旧P9A论文大纲未修改。

补充实验仍必要：按真实身份/支流独立组实施PUB供体迁移基线与目标Q全排除；剔除嵌套上下游供体；固定时序开发/未来保管测试；源QC敏感性；不同驱动与边界精度误差；负NSE与不确定性。不得把本轮单站气象对照写成全国方法精度。
''')
 md('P9C_COMPLETION_REPORT_ZH.md',f'''# KAZ-P9C完成报告

本轮完成实际长期Q获取、原字节和许可保存、日Q→月Q计算、4站身份交叉核查、1个真实D8点位划分、真实小时气象下载及有限真实基线实验。最高E2，P10仍NOT_READY。旧研究与教师数据、网站权限不改。

## 1. 新Q文件与完整年份

WB data_daily_discharge.csv实际13822527字节，SHA256 `{sha(ROOT/'source/data_daily_discharge.csv')}`；站点目录3156字节，SHA256 `{sha(ROOT/'source/stations_daily_discharge.csv')}`。31,047个真实日期、1936–2020；75个位置目录，76个具名Q列及漏表头的午夜时间字段，30001缺目录；末尾空表头吸收了这一偏移，不能把时间或末列另当一个站。两个文件均被源端追加22bytes System.IO.MemoryStream；原字节保存，日流量非日期尾行独立隔离，站名尾缀仅在派生目录清除。完整月要求实际日历每一天有限非负、不插补、不丢真实零；重复/峰值只警示。−9999缺测保持缺测。

首流域4站：10014 SARYTOGAI 286完整月/23完整年；2314400 TALGAR 120月/10年；2314600 TEKELI 120月/10年；10195 Tauturgen179月/14年。共705站月/57站年，这是数值完整性，不是逐日QC认证；每站实际年份和连续月区间见准入表和年度表，未拼接不同年代。官方技术报告区分每日观测来源与TOPKAPI模拟。源逐站机构、填补和QC标记不全，保留限制。

NCDC仅官方元数据可核验，标180站/131河流、1.4MiB XLS、CC-BY4.0，需本人登录申请；本轮无XLS，不能算已取得180站。指定本机检索未找到，申请说明未发送。其1950年前驱动缺口保留。Kazhydromet数据库超时、档案页现需登录，不绕过。

Zenodo下载191514bytes/官方MD5通过；13表各72年气候行（1950–2021），径流846个年值（12表1950–2014，Kashi_tuohai另保留2015年1值）、单位mm。原实测窗口只描述站点年份，不提供逐行实测/填补掩码，绝不把重建年值当月实测Q。P9B原252月/36冲突和暴露记录保留，未重新拼接。

## 2. 与原49站关系

10195–14187：38.113m，均614km²，研究用临时佐证，非官方认证。Sarytogai同名/7370km²却相距14.535km；Talgar同名/444km²却相距9.718km；Tekeli有城名/479与484km²线索，但最近点是Koksu14446/1590km²，另14419/14421需原河名/断面核验。不同来源矛盾全部保留，未按字符串或放宽距离强制匹配。

## 3. 新点位汇水区

新增官方n40e070 DIR43291031bytes、ACC121869859bytes，单10°瓦片，ZIP CRC通过，不下载全亚洲。Tauturgen实际3角秒D8反向连通94,895像元，与源ACC一致，未触窗边；面积594.922566km²，比源614km²低3.107%。出水口距WB点103.839m。独立像元面积与多边形面积相对差7.83e−9；跨境面积0（仅此小流域，不意味着Ili其他点无境外上游）。这是~90m栅格点位划分，不是实地精确边界或物理认证。

保留首次失败：源GeoTIFF原点7e−15度浮点差；初始ACC错误假设+1，经官方技术文档18页确认从1计数并原样归档失败产物；格点交叠GeometryCollection漏掉部分多边形导致11.035%面积缺口，修复后14格点守恒误差1.31e−9。均在模型评分前修复，不调整出水口或面积门槛。

旧D175源host4121234170不包含点，实际点所在L12是4121234690，另层保存，不能自动用任何出口代理冒充点位边界。D500/D525共享代理仍是不同点，精确面积差N/A；新D8试点不替全部30候选完成划分。

## 4. 实际P/T

官方CDS正常API凭据只在内存使用，未写入项目。1965试点1235135bytes与1964–1978档17929781bytes是实际取得的历史气象，但不对应正确10195Q年代，保留不用于有效拟合。随后取得2000–2015档19121321bytes，官方MD5通过：140,280源小时、5,844完整日/192月、4闰日。两段合计372个唯一实际气象月，1965试点重叠不另加。新D8几何面积权重，不移用欧洲权重。K→°C，m→mm；ARCO已反累计，不重复差分；降水区间结束时间−1h后UTC日/月累计，温度24h均值/月均，无缺日填补。2001年1月前月2000年12月真实存在，2000年1月前月缺口单列。

极小NetCDF负降水触发初始严格QC失败：按ECMWF原厂说明冻结派生物理P规则，原始小时及带符号月累计保存，[-0.001,0)mm/h才在派生量置0，低于界限阻断；不是把缺测当0。本次最小−0.000044762mm/h，最大月修正0.000185662mm。两种独立聚合顺序P差≤5.69e−14mm、T差≤7.11e−15°C。旧P9B33710权重仍不等于实际气象值。

## 5. 有限真实模型实验

明确标记KAZ_KNOWN_GAUGE_TEMPORAL_DEVELOPMENT_P9C_E2。1站、C0和C0+PT，训练2001–2011各131个完整月，评价2012–2015各48月，共96条有效预测。1次Ridge.fit及1次月气候态估计，无调参；alpha100在新模型评分前冻结。旧P2数学只读复用，未改公式或覆盖P4/P7。预测角色只读训练Q与测试P/T，读取测试Q的实际尝试被拒绝；预测封存后独立评分。参数重构和数值指标复核41通过/0失败。

C0：NSE {main.loc['C0','NSE']:.6f}，KGE {main.loc['C0','KGE']:.6f}，RMSE {main.loc['C0','RMSE']:.6f}，MAE {main.loc['C0','MAE']:.6f} m³/s，PBIAS {main.loc['C0','PBIAS']:.3f}%。
C0+PT：NSE {main.loc['C0+PT','NSE']:.6f}，KGE {main.loc['C0+PT','KGE']:.6f}，RMSE {main.loc['C0+PT','RMSE']:.6f}，MAE {main.loc['C0+PT','MAE']:.6f} m³/s，PBIAS {main.loc['C0+PT','PBIAS']:.3f}%。MSE技能{main.loc['C0+PT','MSE_skill_vs_C0']*100:.3f}%，这不是百分比准确率。原始与非负次分析、逐年全部保留，不刷分。

总体高估约20%，且本例气象增强MSE退步；不能宣称气象增益，也不能归因于融雪/调度。数据QC已接触测试年代Q，此为开发期外时间比较，不是完全盲测。使用已观测目标月气象，非提前预报；仍有源日界、逐日QC、迁站与分辨率限制。

## 6. P10判定

P10_NOT_READY。数值长度达标4/8，完成D8/P/T仅1站；3个可靠支流独立组、严格身份/QC、静态特征、嵌套供体剔除与目标Q全部遮蔽实际折、未来未暴露标签保管均未齐。正式主协议不放宽。没有把外流域CA或重建Q补成8站。

## 7. 全国扩展剩余阶段

先取得并准入本国长期实测站→逐站可靠边界/P/T/静态属性→真实LOSO、剔除嵌套供体及子流域组遮蔽和时间外验证→锁定未参与选型的未来/外部Q→候选点适用域与不确定性准入后推理→按实际生成的候选/可预测/研究准入数量分别统计全国等效密度。本轮实际已知站预测不能计为新虚拟站，正式虚拟站新增0。

历史哈希及完整交付验证见P9C_INDEPENDENT_QA.json、evidence/HISTORY_FINAL_CHECK.json与SHA256SUMS.txt；只读命令见复现指南。本轮不改网站，不使用教师Q，不启动P10。
''')
 md('P9C_REPRODUCTION_GUIDE.md',f'''# 复现与交付映射

原环境 `{sys.executable}`，Python -B -X utf8；仅官方PDF的只读解析使用现有bundled pypdf，未安装依赖。源目录有原文件、SHA256及官方下载记录；P9B/P8不被覆盖。所有新脚本在code。

只读验证（不重新下载、拟合、评分或修改封存）：
```powershell
& '{sys.executable.replace(chr(92),'/')}' -B -X utf8 '{(ROOT/'code/verify_delivery.py').as_posix()}'
```

实际依赖顺序：acquire.py→wb_discover.py/wb_fetch.py→download_resources.py→q_admission.py；extract_report.py使用bundledPython；hydro_sources.py→hydro_tiles.py→download_rasters.py→catchment.py→weights_repair.py（本轮初版修复，未来新目录的已修正catchment.py不需此修复）→cds_driver.py submit/poll PILOT1965→aggregate_driver.py PILOT1965→cds_driver.py submit/poll LONG1964_1978→aggregate_driver.py LONG1964_1978→纠正源time字段→QALIGNED2000_2015下载/聚合→prepare_e2_protocol.py（实际已在评分前冻结）→e2_prepare.py→e2_predict.py→e2_score.py→auxiliary.py/reports.py→verify_science.py→seal.py。执行时间与失败恢复见RUN_ATTEMPTS.jsonl，不建议在旧目录顺序盲重跑。

新计算必须设置VHS_P9C_OUTPUT到同一公开根目录下新的独立目录，复制已获合法来源及哈希、保留协议，再有意重算；不应原地改封存。CDS凭据仅从用户本地标准配置在内存读取，项目无私钥/口令；没有权限会保留拒绝，不绕过或伪造授权。世界银行API预览返回HTTP200但资源无效，真实Q来自官方页面嵌入元数据的明确CSV下载链接；不是猜测受限API。

关键文件：P9C_NEW_Q_SOURCE_RESULTS是来源及取得状态；P9C_GAUGE_Q_ADMISSION区分数值完整/描述性/E2/P10；P9C_MONTHLY_Q_QC保留所有4站年月和缺失状态；crosswalk保留冲突与备选对应，49原点状态见data/P9C_EXISTING49_LINK_STATUS.csv；catchment CSV+GIS为新点位与旧代理分级；driver结果及driver/真实日月CSV为ERA5实际数值，不是代理权重。SourceNames、CODE与跨境身份未认证的不强行合并。

exploratory_temporal/run为唯一新拟合产物：MODEL_PARAMETERS、E2_PREDICTIONS、逐年/总体E2_TEMPORAL_METRICS、角色审计、先预测封存及41项独立复核和单独SHA。评分标签与预测输入在不同cache文件；P9C整体和单站run分别封存。没有重新运行P0–P7或P10。

所有历史SHA检验为只读，源表错误和初版失败并未当作通过。NCDC文件、其他3站驱动、正式8站PUB、未来盲测、现场精确边界和全国虚拟站预测仍NOT_AVAILABLE。
''')
 js(ROOT/'P9C_FINAL_STATUS.json',dict(task='KAZ_P9C',data_level='E2_EXPLORATORY_TEMPORAL_READY_DEVELOPMENT_ONLY',P10='P10_NOT_READY',
  new_WB_target_stations=4,numeric_complete_station_months=705,numeric_complete_station_years=57,
  strong_provisional_existing49_links=1,official_identity_certifications=0,raster_point_delineations_validated=1,field_exact_catchments_verified=0,
  actual_driver_stations=1,actual_driver_months=192,raw_hourly_source=140280,full_days=5844,
  E2_real_fitted_models=2,E2_Ridge_fit_method_calls=1,E2_climatology_estimates=1,E2_prediction_records=96,E2_train_months_per_model=131,E2_test_months_per_model=48,
  E2_C0_NSE=float(main.loc['C0','NSE']),E2_C0_KGE=float(main.loc['C0','KGE']),E2_C0PT_NSE=float(main.loc['C0+PT','NSE']),E2_C0PT_KGE=float(main.loc['C0+PT','KGE']),E2_C0PT_MSE_skill=float(main.loc['C0+PT','MSE_skill_vs_C0']),
  formal_P10_fit_calls=0,formal_PUB_predictions=0,new_virtual_stations_prediction_available=0,NCDC_XLS_acquired=False,reconstructed_Q_used_for_training=False,
  teacher_Q_reads=0,website_changes=0,old_models_modified=False,future_holdout='FUTURE_HOLDOUT_NOT_AVAILABLE'))
 js(ROOT/'evidence/ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),packages={p:importlib.metadata.version(p) for p in ['pandas','numpy','geopandas','pyogrio','shapely','rasterio','xarray','netCDF4','openpyxl']},dependencies_installed=False))

 erratum="""# 重要更正与有效版本

初次将CSV日期后的00.00时间字段误作第一站Q，导致整列错位；原655站月/40站年、120预测和旧分数全部撤回，不可引用。旧代码、缓存、参数与run及其SHA原样保留于evidence/rejected_column_alignment和exploratory_temporal_REJECTED_COLUMN_ALIGNMENT，状态INVALID_SOURCE_COLUMN_ALIGNMENT。

现统一按date+source_midnight_time+76站Q读取：31047个日期行第二字段均为00.00，末列有有效流量，原始字节不改。结构证据支持归一化，但仍待源方正式字段确认。有效数据为4站705完整站月/57数值完整站年；10195真实Q是2001–2015，2003-07缺8天，不插补。

有效E2在新分数前按覆盖冻结：最后4完整年2012–2015评价48月，此前2001–2011全部完整月训练131月；alpha100不变、不调参。2个有效模型96预测；错列2模型120预测明确作废。实际Ridge.fit总计2次、气候态估计总计2次，其中各1次属于作废尝试；不能把全部216记录合并成成果。旧1964–1978气象仍真实，但不用于有效拟合。有效结果不支持本例气象增益，保留负技能。

本轮最高是E2探索开发、带源字段/身份/日界/QC限制，不是P10、严格PUB、盲测或业务认证；新虚拟站预测数仍0。

"""
 for name in ['P9C_COMPLETION_REPORT_ZH.md','P9C_P10_READINESS.md','P9C_SCI_EVIDENCE_UPDATE.md','P9C_REPRODUCTION_GUIDE.md']:
  file=ROOT/name;file.write_text(erratum+file.read_text(encoding='utf-8'),encoding='utf-8')
 state=read(ROOT/'P9C_FINAL_STATUS.json');state.update(data_level='E2_EXPLORATORY_TEMPORAL_READY_SCHEMA_NORMALIZED_QC_LIMITED',source_schema_normalized=True,publisher_schema_confirmation=False,rejected_schema_models=2,rejected_schema_predictions=120,total_Ridge_fit_method_calls=2,total_climatology_estimates=2,other_actual_met_months=180,unique_actual_met_months=372)
 js(ROOT/'P9C_FINAL_STATUS.json',state)
 with (ROOT/'P9C_NCDC_AND_OFFICIAL_DATA_REQUEST_ZH.md').open('a',encoding='utf-8') as f:
  f.write('\n世界银行字段核验草稿（未发送）：官方目录data@worldbank.org，询问0064229v2日CSV漏time表头/午夜00.00字段/末空表头、System.IO.MemoryStream尾串、30001缺目录、逐站机构QC和日界。当前按结构统一归一化，源方字段确认尚待；不将之伪装为正式认证。\n')
 event(stage='P9C_reports_complete',level='E2_DEVELOPMENT_ONLY',P10='NOT_READY',real_known_gauge_predictions=96,virtual_predictions=0)
