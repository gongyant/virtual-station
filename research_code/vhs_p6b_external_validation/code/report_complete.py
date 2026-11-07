"""Final result-centred P6B reports after the conditionally admitted2020 run."""
import json,sys,collections
from pathlib import Path
from admit import R,L,P4,jl,jw,cw,sha,readcsv
sys.stdout.reconfigure(encoding='utf-8');S=R/'runs/P6B_ID818_2020_SCORING';A=R/'runs/P6B_EHYD_2018_2019_SCORING';P=R/'runs/P6B_ID818_2020';par=jl(R/'driver/ARCO_LEGACY_PARITY_RESULT.json');assert par['same_processing_2020_admitted'];tests=jl(R/'P6B_TEST_RESULTS.json');hist=jl(R/'HISTORICAL_INTEGRITY_REPORT.json')
def write(n,s):(R/n).write_text(s.strip()+'\n',encoding='utf-8')
draft=R/'evidence/PRE_2020_COMPLETION_DRAFT_REPORTS';draft.mkdir(exist_ok=True)
for name in ['P6B_COMPLETION_REPORT_ZH.md','P6B_ERA5_DRIVER_PARITY_REPORT.md','P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md','P6B_DATA_ADMISSION_REPORT_ZH.md','P7_RESEARCH_DECISION.md','P6B_REPRODUCTION_GUIDE.md']:
 p=R/name
 if p.exists() and not (draft/name).exists():(draft/name).write_bytes(p.read_bytes())
old=readcsv(A/'P6B_ALL_STATION_METRICS.csv');new=readcsv(S/'P6B_2020_METRICS.csv')
cw(R/'P6B_ALL_STATION_METRICS.csv',[{**r,'cohort':'EHYD_24_2018_2019','period':'2018-2019'} for r in old]+[{**r,'cohort':'CAMELS_818_2020','region':'Inn above Salzach'} for r in new])
for filename,oldname,newname in [('P6B_INTERVAL_DIAGNOSTICS.csv','P6B_INTERVAL_DIAGNOSTICS.csv','P6B_2020_INTERVALS.csv'),('P6B_MODEL_COMPARISON.csv','P6B_MODEL_COMPARISON.csv','P6B_2020_COMPARISON.csv')]:
 rr=[{**r,'cohort':'EHYD_24_2018_2019','period':'2018-2019'} for r in readcsv(A/oldname)]+[{**r,'cohort':'CAMELS_818_2020','period':'2020','region':'Inn above Salzach','quality_tier':'PROVIDER_CURATED_NO_DAILY_FLAGS_DESCRIPTIVE'} for r in readcsv(S/newname)];cw(R/filename,rr)
predold=readcsv(R/'runs/P6B_EHYD_2018_2019/P6B_PREDICTIONS_WITHOUT_QOBS.csv');prednew=readcsv(P/'P6B_2020_PREDICTIONS_WITHOUT_QOBS.csv');pred=[{**r,'cohort':'EHYD_24_2018_2019'} for r in predold]+[{**r,'cohort':'CAMELS_818_2020'} for r in prednew];assert len(pred)==len({(r['sample_id'],r['model_id']) for r in pred})==1176;cw(R/'P6B_NEW_PREDICTIONS_WITHOUT_QOBS.csv',pred)
cross=readcsv(R/'P6B_STATION_CROSSWALK_FINAL.csv')
for r in cross:
 if r['gauge_id']=='818':r.update(P_T_2020='ORIGINAL_HOURLY_CHAIN_PARITY_60_OF_60_PASS_WITHIN_FROZEN_TOLERANCE',independent_scored_months_P6B=12,reason='2020_SCORED_QUALIFIED_DESCRIPTIVE;2018_2019_REMAIN_P6A_ONLY')
cw(R/'P6B_STATION_CROSSWALK_FINAL.csv',cross)
status={'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','new_stations_beyond_P6A':24,'stations_scored_this_round':25,'new_independent_station_months':588,'new_predictions':1176,'saved_models_loaded_and_evaluated_this_round':50,'fit_calls':0,'cohorts':{'EHYD_24_2018_2019':{'stations':24,'months':576,'predictions':1152,'positive_skill_stations':19,'equal_station_mean_skill':.07351207395192277,'median_skill':.07623550620155767},'CAMELS_818_2020':{'stations':1,'months':12,'predictions':24,'MSE_skill':.08118005422433427}},'cumulative_with_P6A':{'stations':25,'station_months':612,'prediction_records':1224},'strict_QC_certified_months':0,'broad_any_Q_footnote_exclusion_sensitivity':{'months':258,'stations_with_any':16,'stations_with_at_least12':11,'not_equivalent_to_daily_QC_certification':True},'driver_parity':{'raw_monthly_route':'FAILED_45_OF60_RETAINED','original_hourly_chain':'PASS60_OF60_WITH_UNCHANGED_TOLERANCES','max_P_mm':par['max_monthly_P_error_mm'],'max_T_C':par['max_monthly_T_error_C']},'2020_scoring':'COMPLETED_ID818_ONLY','German_611_688':'BLOCKED_EMAIL_REQUIRED_AND_REQUEST_REJECTED_NO_BYPASS','Austrian_24_2020':'Q_OBTAINED_BUT_SAME_PROCESSING_MET_NOT_YET_ACQUIRED','P7_trained':False,'teacher_Q_read':False,'website_changed':False,'historical_changed':hist['changed'],'tests':{'passed':tests['passed'],'total':tests['total']}}
jw(R/'P6B_FINAL_STATUS.json',status)
write('P6B_ERA5_DRIVER_PARITY_REPORT.md',f'''# ID818：2020年ERA5-Land驱动已准入并完成评分

原处理链2015–2019全60个月通过事先冻结的一致性门槛，最大月降水误差{par['max_monthly_P_error_mm']:.9f}mm，最大月均温误差{par['max_monthly_T_error_C']:.9f}°C。不是逐值位级完全一致；容差没有在看到Q成绩后放宽，没有偏差订正。

## 原流域与格点

从独立合法LamaH-CE v1.0日尺度归档提取官方Basins_A、Grid_ERA5L及四份气象处理R代码。818全上游约55.8km²；四个ERA5L格点4051/4157/4052/4158的交叠权重约0.404593/0.065437/0.322540/0.207431。按原R代码先将交叠面积取整数平方米后归一化。没有使用测站单点。

## 恢复的原算法

1. 原小时ERA5L累计降水按01UTC重置、其他小时差分，由m转mm；区间时间标签减1小时；T由K转°C。
2. 对四格点作原面交叠面积加权。
3. 流域小时P先保留0.01mm、小时T先保留0.1°C。
4. 按UTC自然日P求和/T求平均，再对日P取两位、日T取一位。
5. 月P累计，月T按完整真实日数平均。2020有366完整日。

原R代码允许线性补最多3个气象小时缺口，本次不启用插值；原代码2019年末复制最后一小时P的特例仅在历史重叠复现中原样记录。2020最后一小时使用真实2021-01-01 00UTC输入，不造边界。2020-01的L1取原冻结2019-12降水。

## 实际下载与验证

官方CDS已有本地合法凭据。小时产品最初受单任务大小与队列限制；失败任务保留，停止批量提交并顺序处理。先取得原产品2015年1–2月四格点小时P/T。

随后采用官方ERA5-Land ARCO优化长时间序列：2015-01-01至2021-01-01，最终四格点ZIP为2,567,057字节，官方MD5与本地一致，SHA256=54e2a460f1a31a64240d371a368c9562721fc3c70ff6d7a906622baae6737bdf。返回两个NetCDF，各2×2原格点、52,632个唯一小时；坐标和四格点身份逐一断言。精确零宽边界曾因浮点索引NoData，修正为仅外扩0.001度以包括原四格点，未改变流域权重或增加气象站点。

ARCO降水已经逐小时反累计，未重复差分。先与独立原小时产品对照1415小时：T最大差0.000030518°C，小时P最大差0.000000233mm，通过预先固定的0.0001阈值。随后按原代码取整/日聚合，全60个月通过：P门槛0.18mm/月、T门槛0.052°C，P>=36mm时相对差<=0.5%。逐月结果见driver/ARCO_LEGACY_60_MONTH_PARITY.csv。

## 保留的负尝试

官方月平均产品先前60月仅45月通过，最大P差0.229931mm；这份失败结果保留于driver/DRIVER_PARITY_RESULT.json。原因可追溯到小时取整与聚合不可交换。没有用失败月产品产生2020评分。

Python两次DNS失败后，使用Windows默认HTTP/TLS查询同一任务并下载成功；未修改DNS、代理或证书设置。凭据仅在内存使用，不复制.cdsapirc、不打印密钥。

## 独立验证与限制

P6B_2020_ADMISSION_FROZEN.json冻结模型、来源、12个月与质量限制后，先封存24条预测，再读取CAMELS-CH2020年366日实测Q评分。fit0。源方注明2020-01-01开始MIR强迫插值包变化；即使历史重叠通过，也保留这一源产品变更限制，不据此直接归因模型误差。

官方说明：https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries ，https://confluence.ecmwf.int/pages/viewpage.action?pageId=699689224 。
''')
report=(R/'P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md').read_text(encoding='utf-8');start=report.find('## 尚未完成');start=start if start>=0 else report.index('## ID818的2020年：独立的新run')
report=report[:start]+'''## ID818的2020年：独立的新run

恢复原小时气象处理链后，60/60重叠月通过既定门槛。使用原模型，不fit、不调alpha；先封存24条预测，再读取366日真实Q并形成12个月标签。原P6A的2018–2019成绩不变。

- C0+PT：NSE0.305132，KGE0.489794，RMSE0.366766m³/s，MAE0.282247m³/s，PBIAS−3.2378%。
- P2-L1：NSE0.361542，KGE0.532014，RMSE0.351564m³/s，MAE0.256713m³/s，PBIAS−2.2174%。
- L1相对C0+PT的总体MSE技能+8.1180%；DJF−55.2317%（3月，基准MSE0.012147），5–6月+11.1432%（2月）。季节小样本只作描述。
- L1的KGE分量r=0.847304、变异性比1.441818、均值比0.977826。均值偏差小，但预测变幅仍较大。
- 两模型80%、90%经验区间均覆盖12/12个月；L1平均宽度1.210286/2.030163m³/s，Interval Score分别同宽度。不能凭12个月100%覆盖认定已校准。

与P6A相同V2模型2018–2019的L1 NSE0.691223、RMSE0.474596相比，2020的NSE下降而RMSE更小，说明评价标签变异性不同，不能只按NSE把变化解释成绝对误差增大。P6A的相对技能+2.72%，2020+8.12%，冬季在两个时期仍退步。

本轮合计新增588站月、1176预测；新增24个此前未评分站，另扩展已评818的2020年。连同原P6A，累计25站612站月1224预测。24站2018–2019与单站2020必须分开汇总，不生成跨不同时段、跨站原始m³/s平方误差的单一成绩。

## 仍受阻与未执行

611/688官方自定义时段要求有效邮箱，完整归档请求Request Rejected；没有发送邮件、绕过访问控制或用EStreams零散月拼接。24个奥地利站2020年Q已取得，但本轮只恢复了818的2020流域气象，因此这些站2020未评分。没有P7、SHRINK/SNOW拟合、网页修改或教师Q读取。

所有结果是公开有历史Q校准流域的描述性时间外证据；缺少逐日QC认证及部分日界说明，不支持总体统计显著性、业务认证、严格无资料站或取水/融雪因果主张。
''';write('P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md',report)
data=(R/'P6B_DATA_ADMISSION_REPORT_ZH.md').read_text(encoding='utf-8').replace('2020这些Q尚不评分，因尚无同口径气象。','奥地利24站2020这些Q尚不评分，因未为它们恢复同口径气象；818的2020另见下文。')
if '2020经四格点原小时链60月验收后' not in data:data=data.replace('2018–2019已在P6A评分，本轮不重复计入新增。','2018–2019已在P6A评分，本轮不重复计入新增；2020经四格点原小时链60月验收后，新增12月、24预测，独立run已评分。')
write('P6B_DATA_ADMISSION_REPORT_ZH.md',data)
write('P7_RESEARCH_DECISION.md','''# P7：保留固定L1对照，暂不训练

新增奥地利24站中19站总体MSE改善，支持继续保留P2-L1，同时强制并列C0+PT。冬季9/24改善且站均技能−13.83%；818在2020总体+8.12%，但冬季−55.23%。这是重复出现的薄弱环节，尚不能推断融雪或水库原因。

失败模式不统一：ID455均值较训练低29.81%、模型PBIAS+61.54%；818在2020均值比0.9778接近1，而变异性比1.4418，主要统计问题偏向幅度。ID378/383的新期并非持续严重失败，ID185的L1增量转负。不能凭一个站决定通用模型。

下一优先级：扩展奥地利24站的2020及以后同口径流域驱动、明确官方Q的日界与逐日质量；解决德国官方checked日Q。818的驱动恢复已完成，不再把它当作当前阻断。

若进入小型P7开发，仅考虑两个预先冻结方向：均值/季节模板漂移的受约束异常模型，以及少量前期储存记忆。应使用独立开发资料验证问题是否真实存在；没有稳定跨站规律前保持旧模型，不堆叠变量或复杂网络。

P6A/B的2018–2019及818的2020成绩现已查看。凡利用这些结果选型的P7，不能再把同期资料称为全新最终确认性测试；应保留未参与选型的新时期或独立网络组。此轮P7 fit0。
''')
write('P6B_COMPLETION_REPORT_ZH.md',f'''# P6B已完成：24个新增站及818的2020年独立验证

本轮比P6A新增24个合法公开模型站、588个独立站月、1176条真实预测。50个原P4-V2保存模型加载并评价，fit调用0。原27站逐一形成来源/身份/完整日数/质量/气象准入记录。

两组分开报告：

- 奥地利24站2018–2019：576站月、1152预测；L1在19/24站改善，站等权MSE技能+7.35%，中位+7.62%；DJF9/24改善、站均−13.83%，5–6月20/24改善。L1站中位NSE0.543917、KGE0.592867。
- 818的2020：12月、24预测；C0+PT NSE0.305132/KGE0.489794，L1 NSE0.361542/KGE0.532014，相对MSE技能+8.12%，冬季仍−55.23%。所有原始/非负预测、负结果、逐年/季节/区间成绩保留。

连同原P6A，不重复计数地累计25站、612站月、1224预测。同一站的月份不是独立流域；三个宏观水系样本不均衡并有网络依赖，不声称总体统计显著。

## 驱动恢复真实完成

原月平均产品路线45/60月通过，失败记录保留；恢复官方小时取整顺序及整数面积权重后，原四格点60/60月通过预先冻结门槛。最大月P差0.11mm、月T差0.00645°C，未放宽容差、未偏差订正。2020使用完整真实小时和实际跨年边界，L1上月来自原2019-12。先封存2020预测，再读取独立Q评分。

## 质量与受阻项

新Q为合法官方/公开实测归档，但未取得逐日QC认证，eHYD日界UTC偏移未独立认证。描述性主结果与258月“排除任一Q备注”广义敏感性分开；该敏感性包含对人工影响背景的排除，不是逐日QC认证，只有11站>=12月。认证严格样本仍0。

611/688：自定义时段要求有效邮箱、完整归档Request Rejected，未绕过未评分。奥地利24站2020已有Q但本轮未取得对应同口径驱动，未评分。

## 验证与保护

{tests['passed']}/{tests['total']}项真实来源、数值和封存检查通过；1176预测全部由保存参数独立重算，最大差0；指标及区间独立复核一致。9个历史根的1582个封存文件未变化，P6A成绩不变。无教师Q读取、fit、网页更改或P7训练。软件PASS不等于水文学认证。

主要文件：P6B_INDEPENDENT_VALIDATION_REPORT_ZH.md、P6B_ERA5_DRIVER_PARITY_REPORT.md、P6B_STATION_CROSSWALK_FINAL.csv、P6B_ALL_STATION_METRICS.csv、P6B_NEW_PREDICTIONS_WITHOUT_QOBS.csv。四个不可变run目录各有独立SHA256SUMS。

下一步是其他站2020及以后驱动和官方QC/日界，而非重新训练已有模型。P7如使用本轮结果选型，必须另留未参与选择的检验资料。
''')
write('P6B_REPRODUCTION_GUIDE.md',r'''# P6B复核与复现

现有环境（不安装依赖）：

```powershell
$py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
$root='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation'
& $py -B "$root\code\verify_delivery.py"
```

该入口完全只读，不联网、不fit、不预测、不评分，验证整个交付SHA。

完整算法复核代码：analyze_verify.py独立重算24站1152预测及指标；verify_2020.py重算818站24预测、366日观测指标和区间；arco_legacy_parity.py按原官方代码核对1415小时与60个月。它们fit0，但会写验证/诊断文件。若要求交付目录字节保持不变，应复制到独立复核目录并仅在副本调整R输出路径后运行；历史L/P4输入只读。

run_fixed.py predict/score和run_818_2020.py freeze2020/predict2020/score2020是已经实际调用的执行入口；现有不可变run存在时拒绝覆盖。不得删除run强行重跑。新资料必须新run、新冻结输入与独立来源绑定。

四格点CDS任务已完成，无待轮询或隐含下载进程。code中的早期批量请求脚本只作失败历史证据，不应重跑；CDS要求顺序提交等待完成。本轮官方NetCDF容器和原R处理代码都已随来源证据保存，通常无需再次下载。

没有修改网站或端口、P4模型、教师授权。回滚无需改原服务；停止使用新目录即可。不要删除历史科研文件。
''')
jw(R/'driver/DRIVER_ACQUISITION_FINAL_STATUS.json',{'current':'COMPLETE_SAME_PROCESSING_ADMITTED','CDS_official_jobID':'b4f0398a-466c-43c3-b6de-af4fbc211a5c','official_status':'successful','download_file_hash':par['CDS_ARCO_file_hash'],'legacy_parity_result_hash':sha(R/'driver/ARCO_LEGACY_PARITY_RESULT.json'),'failed_monthly_route_retained':True,'network_DNS_failure_retained':True,'credentials_saved':False,'no_pending_jobs_in_this_delivery':True})
lic=(R/'SOURCE_LICENSE_AND_DOWNLOADS.md').read_text(encoding='utf-8')
if 'ee82e357' not in lic:lic+='\n最终用于2020的优化时间序列产品为官方ERA5-Land ARCO，DOI https://doi.org/10.24381/ee82e357 ，四格点公开资料按源方许可署名。未以测站单点替代全流域输入；先对照原小时字段，再按原作者代码处理。\n'
write('SOURCE_LICENSE_AND_DOWNLOADS.md',lic)
print(json.dumps(status,ensure_ascii=False,indent=2))
