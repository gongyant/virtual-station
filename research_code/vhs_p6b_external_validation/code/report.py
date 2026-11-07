import csv,json,sys,shutil,collections,math,time
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,cw,sha,readcsv
sys.stdout.reconfigure(encoding='utf-8');SC=R/'runs/P6B_EHYD_2018_2019_SCORING';PR=R/'runs/P6B_EHYD_2018_2019';metrics=readcsv(SC/'P6B_ALL_STATION_METRICS.csv');comp=readcsv(SC/'P6B_MODEL_COMPARISON.csv');par=jl(R/'driver/DRIVER_PARITY_RESULT.json');cross=readcsv(R/'P6B_STATION_CROSSWALK.csv');overall=[r for r in comp if r['subset']=='ALL' and r['quality_tier']=='DESCRIPTIVE_ARCHIVE'];ci=readcsv(R/'P6B_INTERVAL_STATION_SUMMARY.csv');tests=jl(R/'P6B_TEST_RESULTS.json');hist=jl(R/'HISTORICAL_INTEGRITY_REPORT.json')
def write(name,text):(R/name).write_text(text.strip()+'\n',encoding='utf-8')
for name in ['P6B_ALL_STATION_METRICS.csv','P6B_INTERVAL_DIAGNOSTICS.csv','P6B_MODEL_COMPARISON.csv','P6B_REGION_SUMMARY.csv']:shutil.copyfile(SC/name,R/name)
finalcross=[]
for x in cross:
 r=dict(x);r['crosswalk_role']='FINAL_STATUS_SUPPLEMENT; original admission crosswalk unchanged';r['P_T_2020']='CDS_ACQUIRED_BUT_ORIGINAL_PROCESSING_NOT_FULLY_REPRODUCED' if r['gauge_id']=='818' else 'NOT_ACQUIRED_SAME_PROCESSING';r['independent_scored_months_P6B']=24 if r['country']=='AUT' else 0
 if r['gauge_id'] in ['611','688']:
  r['Q_complete_months_2018']=None;r['Q_complete_months_2019']=None;r['Q_complete_months_2020']=None;r['reason']='GKD_CUSTOM_RANGE_REQUIRES_EMAIL;PUBLIC_FULL_ARCHIVE_REQUEST_REJECTED;NO_BYPASS;actual_daily_support_unknown'
 if r['gauge_id']=='818':r['reason']='2018_2019_ALREADY_P6A;2020_MONTHLY_PRODUCT_PARITY_FAILED15of60;LEGACY_HOURLY_RECOVERY_PENDING'
 finalcross.append(r)
cw(R/'P6B_STATION_CROSSWALK_FINAL.csv',finalcross)
stations_lines='\n'.join(f"- ID{r['gauge_id']}：C0+PT NSE={float(r['NSE_C0PT']):.6f}，L1 NSE={float(r['NSE_L1']):.6f}、KGE={float(r['KGE_L1']):.6f}，MSE技能={100*float(r['MSE_skill']):+.2f}%。" for r in overall)
median={mid:{k:float(np.median([float(r[k]) for r in metrics if r['model_id']==mid and r['subset']=='ALL' and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw'])) for k in ['NSE','KGE']} for mid in ['C0+PT','P2-L1']}
write('P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md',f'''# P6B：2018–2019年24站固定模型独立验证

本轮新增24个奥地利已校准公开流域、576个独立站点—月份、1152条真实预测。48个原P4-V2模型加载并评价，fit调用0。先封存预测，再由独立角色读取官方实测Q评分。不是LOYO，不是无资料站，也不是提前流量预报；任务为RECONSTRUCTION_WITH_OBSERVED_MET。

原P6A的818站24个月未重复计入。本轮与P6A合计25站、600站月、1200条预测；同站月份不是独立流域，部分测站有嵌套与同水系依赖。宏观水系为Rhine5站、Danube17站、Elbe2站，不能称24个统计独立重复。

## 总体事实

- L1相对C0+PT：19/24站正MSE技能；站等权平均+7.3512%，中位+7.6236%。没有跨站混合m³/s平方误差计算单一技能。
- 2018年18/24站改善，站均+6.6686%；2019年19/24，站均+8.0239%。
- 冬季DJF只有9/24站改善，站均−13.8252%、中位−6.2699%；5–6月20/24站改善，站均+7.3453%、中位+15.1147%。冬季失败重复，5–6月旧负结果未普遍重复。
- C0+PT站点中位NSE={median['C0+PT']['NSE']:.6f}、KGE={median['C0+PT']['KGE']:.6f}；L1中位NSE={median['P2-L1']['NSE']:.6f}、KGE={median['P2-L1']['KGE']:.6f}。
- 失败站与负值全部保留：L1负技能ID185、377、455、512、545；ID343、455的L1 NSE仍为负。

## 质量限制与敏感性

主分析是OFFICIAL_ARCHIVE_NO_PER_DAY_QC_WITH_FOOTNOTES描述性样本。官方日均[m³/s]，全日数、唯一日期、非空非负、精确官方站码、面积及坐标已核查；BMN坐标使用官方BEV EPSG31257/58/59，24站距离均<50m。

eHYD未提供逐日checked/suspect列；导出未明确日界UTC偏移。使用provider自然日的月均，未伪造UTC认证或LamaH ckhs等价性。官方站点备注存在补充水位推算、冰影响、长期调节等，逐条保留。

冻结CSV中的STRICT_SENSITIVITY实际是“排除任何适用OWF-Q备注月份”的保守广义敏感性；它也会排除长期人工影响等水文背景，不能冒称逐日质量认证。258个月分布16站，只有11站达到至少12月汇总支持；这11站10站正技能，站均+7.3642%。它与主分析站点集合不同，不能据此宣称普遍性或更高质量样本全部成功。认证严格样本数量为0。

## 全24站成绩

{stations_lines}

## 跨时期与机制边界

ID171新期L1技能+27.97%仍正；ID185由旧V1较强增益变为−4.85%。ID378/383新期L1 NSE为0.543820/0.546890；ID455仍−0.486694，PBIAS+61.54%，新Q均值较保存训练均值低29.81%。ID533新期L1技能仅+0.84%，不能把高绝对NSE等同于显著气象增量。

旧V1与新V2训练窗和模型版本不同，以上只是交叉版本/时期描述，不能把变化全部归因于时间。另存2015–2017新旧观测来源重叠差异，未据此重新筛样或改旧成绩。

L1共527个IN_SUPPORT站月，其中109个月绝对误差仍大于保存训练均值的一半；这一误差阈值仅为事后描述，未用于准入。IN_SUPPORT是协变量范围诊断，不能保证预测准确。

## 区间

L1名义80%区间的站等权覆盖87.15%，90%覆盖93.92%；C0+PT分别89.41%、95.49%。总体偏保守的描述仍成立，但单站不保证覆盖：L1的90%区间在ID533仅19/24=79.17%，ID6/22为83.33%。每站宽度、Interval Score及季节值见P6B_INTERVAL_DIAGNOSTICS.csv，未做新校准。

## 尚未完成

ID818的2020：月产品路线60月仅45月通过冻结容差，不能用它评分。已恢复官方小时处理代码并申请真实小时复现，完整60月一致性与2020同口径驱动尚未验收。ID611/688：官方自定义时段要求邮件，完整归档请求被Request Rejected，未绕过，未评分。没有P7拟合、SHRINK/SNOW、网站修改、教师数据读取。

所有结果是公开有历史Q校准流域的两年描述性时间外证据，不支持总体显著性、业务认证、严格无资料站或具体取水/融雪因果主张。
''')
write('P6B_DATA_ADMISSION_REPORT_ZH.md',f'''# P6B数据准入实录

原27站逐一调查：24AUT、2DEU、1CHE。最初准入冻结表P6B_STATION_CROSSWALK.csv绑定不可变run；最终补充表P6B_STATION_CROSSWALK_FINAL.csv更新德国访问和2020驱动状态，原冻结表不改。

## 实际新增

24个奥地利站各取得官方eHYD日均Q文件及原站资料，2018、2019、2020年各12完整月，三年1096天/站。2020这些Q尚不评分，因尚无同口径气象。2018–2019复用原快照全流域ERA5L日资料，576站月通过共同支持，1152预测已完成。

站点匹配使用HZB码、河名/站名、面积和BMN坐标。24站坐标差0.14–49.91m，未以名称相同直接匹配。初次实现误用了无假东距的GK CRS，导致全部拒绝；纠正为BEV定义BMN31257/58/59后重算，原失败记录保留，没有改变500m或5%面积阈值，也没有先看分数挑站。

## 质量

官方文件必须为Abfluss,I,Mit,T和[m³/s]，每日00:00全日数且无Lücke或重复。文件编号5已实查；编号3等为水位/极值，未作标签。数值Q仅在预测封存后进入评分。未自动延续“上一个有效日”跨缺档。

逐日QC列及UTC日界未获独立认证，所以主样本为描述性官方归档，非逐日质量认证。广义排除Q备注敏感性258个月，16站有值、11站>=12月；备注也包含人工影响背景，因此不得解释成完全等价的严格QC样本。见P6B_SOURCE_Q_FOOTNOTES.csv。

## 德国与瑞士

611=10035801 Dillingen/Donau，688=16602303 Stegen/Amper，沿用P6A官方坐标/面积证据；本轮再次真实请求。GKD自定义三年请求返回“需要有效邮箱”，未发邮件；官方完整归档选项两个站均Request Rejected，收到即停止。最新服务错误见external/GKD_NEW_ATTEMPTS_*.json。未用EStreams2018-01/2020-02零散月拼成连续Q。

818=FOEN2304，原27站中唯一瑞士站。CAMELS-CH observation_based日Q与P6A保持同源；2020有366天已取得，未当作simulation_based。2018–2019已在P6A评分，本轮不重复计入新增。

## 来源/许可

- 官方eHYD https://ehyd.gv.at/ ：现行网站Impressum注明非商业用途可在署名且无特别限制时转载，不是CC-BY通用商业再发布许可；本地科研处理保留BMLUK/Hydrographischer Dienst署名，不发布原始Qobs批量数据。官网JS原文、来源URL和SHA已保留。
- 官方年鉴 https://wasser.gv.at/hydjb/ ：公开年鉴和多年CSV访问路径；没有代替本人发送资料申请。
- CAMELS-CH v0.9 https://zenodo.org/records/15025258 ：原P6A记录与测站2304实测文件哈希继续有效，未再次下载或替换。
- ECMWF CDS ERA5-Land https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land ：真实凭据获取，私钥/令牌未复制到交付。具体输入和任务身份见driver下请求/结果记录。

FINAL表德国完整月数null表示未知未取得；原冻结表0仅为当次取得并核实完整月计数，不表示官方不存在记录。
''')
write('P6B_ERA5_DRIVER_PARITY_REPORT.md',f'''# ID818 ERA5-Land 2020：实际获取与口径核验

真实取得：2020月均P/T、2020全年366天UTC00累计降水（含2021-01-01边界）、2020-01-01小时P/T，以及2015–2019全60月官方月产品。没有下载全欧洲或E-OBS大包，未使用站点单点替代流域聚合。CDS本机已有可用凭据，真实返回jobID；未保存密钥。获取不是受NOT_GRANTED阻断。

## 原始处理定义

从LamaH v1.0日尺度原归档提取Basins_A、Grid_ERA5L及原R代码。818全上游面积约55.8km²，四格点交叠归一权重约0.404593、0.065437、0.322540、0.207431；使用EPSG3035实际面交叠，不是站点最近格点。

原Timeseries_met_ERA5L.R先将交叠面积转整数平方米，按小时反累计降水（01UTC重置，其他小时差分），P由m转mm、T由K转°C；P时间减一小时对齐区间起点。随后对流域小时P取两位、小时T取一位；Transform_timeseries_hourly_to_daily.R再按UTC日求P和/T均值，并将日P两位、日T一位输出。月P累计、月T按真实日数平均。源码中可插值最多3个气象小时缺口，本轮未开启插值，缺失不能当0。

原2019年末脚本还复制最后一个小时降水作为边界补齐。独立复现必须显式记录这个源处理边界，不能给2020伪造小时值。2020年1月L1必须使用原已发布2019-12降水。

## 已完成的60月检验：月产品路线未通过

在比较前冻结容差：月P绝对误差<=0.18mm，P>=36mm时相对误差<=0.5%；月T<=0.052°C。最初误读文件精度的候选容差已在取到新气象前纠正并留档，没有按Q成绩修改。

60月通过{par['months_passed']}月，失败15月。P最大绝对误差{par['max_P_absolute_error_mm']:.9f}mm，平均有符号差{par['mean_P_signed_error_mm']:.9f}mm；T最大误差{par['max_T_absolute_error_C']:.9f}°C，60月全通过。全部差异见driver/P6B_ERA5_OVERLAP_MONTHLY_PARITY.csv。

虽然官方月平均产品来自ERA5L原小时资料，但“先小时取整后聚合”与“先聚合后转换”不交换。不得放宽容差或偏差订正后冒称已严格复现。2020月产品P与独立UTC00日累计的月和最大差仅{par['max_2020_P_daily_monthly_discrepancy_mm']:.9f}mm，说明获取/单位/日累计内部基本一致，仍不能证明等价旧LamaH取整链。

## 原小时路线

已冻结ORIGINAL_LEGACY_IMPLEMENTATION_FROZEN.json并申请2015年1–2月四格点原小时P/T。任务、校验与实际状态见driver/CDS_LEGACY_STATUS.json；如已有独立小时复现结果则见driver/ORIGINAL_HOURLY_PARITY_RESULT.json。没有把部分月份验收扩大成60月通过。

## 结论

2020同口径准入仍未完成，未读取2020Q进行评分，0条2020模型预测/0条评分。主要障碍已经从“无数据”收窄为恢复原小时取整链并完成全60月重叠验收。官方CDS单请求大小/队列限制及真实失败均保留；批量提交已停止，后续必须顺序请求等待完成。

ECMWF还注明2020-01-01更换MIR气象强迫插值包；即便重叠通过，也需保留高山地区潜在小不连续的源方说明，不将它直接当成本流域预测误差原因。
''')
write('P7_RESEARCH_DECISION.md','''# P7研究决策：暂不训练新模型

新24站19站L1改善，支持保留P2-L1并强制并列C0+PT基线；不能凭站点多数正技能宣布通用模型。冬季9/24改善，均值技能−13.83%，是重复出现的、值得独立检验的薄弱环节。5–6月20/24改善，原负结论不宜泛化。

优先完成P6B剩余驱动工作：严格恢复官方小时取整链、60月验收，再对818的2020单独冻结预测/评分；补足德国官方checked日Q与日界/QC认证。取得数据后的新run不能覆盖本轮。

模型研究仅提出两个小方向，尚不选型、不fit：

1. 对ID455等检查流量均值漂移与固定月份模板偏移；若独立开发资料支持，可比较受约束、训练期内估计的气候异常基线或时间变化响应。
2. 针对重复冬季失败，在独立开发时段比较前期储存记忆模型与固定L1，避免同时枚举融雪阈值和大量滞后。

ID378/383不再在新期普遍失败、ID185增益转负，显示当前没有单一已识别的跨站水文机制。人工调节/积雪/地下水不能由残差直接确定。源站备注可作为来源信息，不能替代因果检验。

P6A和P6B的2018–2019成绩现在已被查看，任何利用它们选模型的P7都不得再把相同资料称为全新确认性测试。最终检验应使用未参与选型的新时期或独立网络组，并预先冻结。
''')
write('SOURCE_LICENSE_AND_DOWNLOADS.md','''# 来源与许可

奥地利：BMLUK / Hydrographie Österreichs / Hydrographische Landesdienste，https://ehyd.gv.at/ 。本地保存官网提供的非商业研究资料、站点说明和下载回执。现行版权说明可在external/ehyd_main.js的Impressum组件复核，非商业转载须署名并服从特定限制；没有把它标为CC-BY，也没有赋予原始Q无限商业再分发许可。所下载原始文件保留在external供本地证据核验，默认不发布。

瑞士：CAMELS-CH v0.9，DOI https://doi.org/10.5281/zenodo.15025258 ，测站2304的observation_based资料继续沿用P6A合法原件及许可记录，不使用simulation_based标签。

ERA5-Land：Copernicus Climate Change Service, Climate Data Store / ECMWF，小时产品DOI https://doi.org/10.24381/cds.e2161bac ，月产品官方目录https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-monthly-means 。具体产品许可和元数据响应见driver/CDS_*PRODUCT_METADATA.json与external/CDS_era5land_process.json；CDS网站现显示CC-BY。生产方式、2020MIR变化见https://confluence.ecmwf.int/display/CKB/ERA5-Land%3A+data+documentation 。没有在日志保存CDS密钥，也没有复制.cdsapirc。

LamaH-CE v1.0：DOI https://doi.org/10.5281/zenodo.5153305 ，Klingler, Schulz, Herrnegger (2021), https://doi.org/10.5194/essd-13-4529-2021 。使用现有独立合法快照的CC BY-SA4.0数据及官方处理代码，原作者署名保留；衍生处理代码中的直接移植也应保留相应署名/共享条件。

德国：GKD Bayern，https://www.gkd.bayern.de/ 。只保存公开请求/拒绝证据，没有成功取得新的checked日Q，不宣称其新Q许可或完整覆盖已核实。未填写虚构邮箱或发送消息。

下载回执包括实际URL、HTTP状态、文件长度/哈希或CDS jobID。被官方拒绝的请求也保留。两站自定义时段要求邮箱，完整归档被Request Rejected；不绕过控制。
''')
write('P6B_REPRODUCTION_GUIDE.md',r'''# 运行与复核

使用已有环境，不安装依赖：

```powershell
$py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
$root='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation'
& $py -B "$root\code\verify_delivery.py"
& $py -B "$root\code\analyze_verify.py"
```

analyze_verify.py只加载保存参数复算1152预测、用封存后的观测来源独立核对指标，fit0；会更新本轮的检查/描述性诊断文件，不改不可变runs或历史文件。需要保持整个交付封存字节不变时只运行verify_delivery.py。

已封存run禁止覆盖。run_fixed.py的predict/score入口均带目录存在拒绝；不通过删除run重跑。需要新的数据/期间时建立单独的新run并绑定独立冻结协议。

driver任务复核：code/hourly_legacy_worker.py poll只查询原任务与下载结果，不追加任务；如数据已完成，可执行code/legacy_parity.py复算所取得的重叠日/月。它不是2020评分入口，不能把部分重叠通过当成全60月通过。code/historical_attempts目录保存曾失败的批量下载脚本，仅作历史证据，不应重新运行；CDS要求顺序任务。

没有网站、服务端口、教师数据授权或P4模型改动，因此回滚不涉及原服务：停止使用新目录即可。若需清理新目录应先保留不可变runs与来源哈希，不删除任何历史目录。
''')
status={'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','new_legal_model_stations':24,'new_independent_station_months':576,'new_predictions':1152,'models_loaded_and_evaluated':48,'fit_calls':0,'cumulative_with_P6A':{'stations':25,'station_months':600,'prediction_records':1200},'positive_MSE_skill_stations':19,'station_equal_mean_skill':.07351207395192277,'station_median_skill':.07623550620155767,'descriptive_Q_quality_only':True,'certified_strict_months':0,'strict_broad_footnote_sensitivity_months':258,'strict_broad_footnote_sensitivity_min12_stations':11,'ID818_2020':'NOT_SCORED_FULL_LEGACY_DRIVER_PARITY_NOT_YET_VERIFIED','2020_monthly_driver_file_obtained':True,'2020_monthly_route_parity':{'passed':45,'total':60},'German_611_688':'BLOCKED_CUSTOM_EMAIL_REQUIRED_AND_FULL_ARCHIVE_REQUEST_REJECTED','P7_trained':False,'teacher_Q_read':False,'website_changed':False,'historical_changed':hist['changed'],'tests':{'passed':tests['passed'],'total':tests['total']}}
jw(R/'P6B_FINAL_STATUS.json',status)
write('P6B_COMPLETION_REPORT_ZH.md',f'''# P6B交付总览

比P6A实际新增24个合法公开模型站、576个独立站月、1152条真实预测；48个原V2模型评价，fit0。连同原818站2018–2019年24月，累计25站600站月1200预测。27站身份和数据调查全部完成，未把未取得德国Q或2020驱动记作成功评分。

主结果：L1 19/24站改善，站等权MSE技能+7.35%，中位+7.62%；冬季9/24改善，站均−13.83%；5–6月20/24改善。原始、非负次分析、逐年/季节/高低流量指标与区间Score均在P6B_ALL_STATION_METRICS.csv及相关CSV中。完整解释见P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md。

较严格的“任何Q备注月份均排除”敏感性只有258月，16站有值、11站>=12月；它包含对调节背景的保守排除，不能视作逐日QC认证。严格认证样本0。官网原始日Q没有逐日QC字段，日界UTC偏移尚未独立认证。

2020官方气象已真实取得。月产品路线60月45通过、15失败，温度全部通过；已从原LamaH归档恢复官方小时取整代码并继续小范围实算。没有全60月原链通过证据，818的2020未评分。不能把完整月气象“存在”等同于旧驱动“同口径”。德国两站服务要求邮箱或Request Rejected，未绕过。

77项实际数值/来源/封存复核通过；1152条预测从保存参数重算最大差0，独立48模型指标和区间再计算一致。9个历史根、1582个历史文件未变化。没有教师Q读取、fit、P7或网页改动。

交付入口：P6B_DATA_ADMISSION_REPORT_ZH.md、P6B_ERA5_DRIVER_PARITY_REPORT.md、P6B_STATION_CROSSWALK_FINAL.csv、P6B_FROZEN_PROTOCOL.json、P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md、P7_RESEARCH_DECISION.md、P6B_REPRODUCTION_GUIDE.md。不可变预测和评分各自位于runs下，均有独立SHA256SUMS。

下一步首先是完整恢复小时驱动并完成2015–2019全60月验收，以及解决官方Q日界/质量条件；不应以增加新模型代替这些具体问题。P6A/B已查看的2018–2019资料不能再次冒称P7全新最终测试。
''')
print('REPORTS_WRITTEN',json.dumps(status,ensure_ascii=False))
