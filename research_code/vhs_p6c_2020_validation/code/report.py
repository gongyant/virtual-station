from p6c_common import *
import shutil
sys.stdout.reconfigure(encoding='utf-8');S=R/'runs/P6C_2020_SCORING';P=R/'runs/P6C_2020_PREDICTION';verify(S);verify(P)
def num(x,dp=4):return 'N/A' if x in ['',None] else f'{float(x):.{dp}f}'
def pct(x):return 'N/A' if x in ['',None] else f'{100*float(x):.2f}%'
def md(name,s):(R/name).write_text(s,encoding='utf-8')
metricsrows=readcsv(S/'P6C_ALL_STATION_METRICS.csv');comp=readcsv(S/'P6C_MODEL_COMPARISON.csv');cis=readcsv(S/'P6C_INTERVAL_DIAGNOSTICS.csv');summary=readcsv(S/'P6C_REGION_SUMMARY.csv');failure=readcsv(S/'P6C_FAILURE_DIAGNOSTICS.csv');ad=jl(R/'P6C_ADMISSION_FROZEN.json');commit=jl(P/'COMMITMENT.json');tests=jl(R/'P6C_INDEPENDENT_VERIFICATION.json');parity=jl(R/'driver/ALL24_PARITY_RESULT.json');oldc=readcsv(B/'P6B_MODEL_COMPARISON.csv');oldm=readcsv(B/'P6B_ALL_STATION_METRICS.csv')
for name in ['P6C_ALL_STATION_METRICS.csv','P6C_INTERVAL_DIAGNOSTICS.csv','P6C_MODEL_COMPARISON.csv','P6C_REGION_SUMMARY.csv','P6C_FAILURE_DIAGNOSTICS.csv','P6C_FIXED_DAY_SHIFT_SENSITIVITY.csv']:shutil.copy2(S/name,R/name)
shutil.copy2(P/'P6C_2020_PREDICTIONS.csv',R/'P6C_2020_PREDICTIONS.csv');cw(R/'P6C_PRIMARY_2020_METRICS.csv',[r for r in metricsrows if r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['subset']=='ALL' and r['prediction']=='raw'])
comparisons=[]
yearly=[]
for r in oldm:
 if r.get('cohort')=='EHYD_24_2018_2019' and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw' and r['subset'] in ['2018','2019']:
  yearly.append({k:r.get(k) for k in ['gauge_id','region','model_id','subset','n','MSE','RMSE','MAE','NSE','KGE','PBIAS','Qobs_mean','Qsim_mean']})
for r in metricsrows:
 if r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw' and r['subset']=='2020':yearly.append({k:r.get(k) for k in ['gauge_id','region','model_id','subset','n','MSE','RMSE','MAE','NSE','KGE','PBIAS','Qobs_mean','Qsim_mean']})
cw(R/'P6C_YEARLY_2018_2020.csv',yearly)
for c in comp:
 if c['quality_tier']!='DESCRIPTIVE_ARCHIVE' or c['prediction']!='raw':continue
 old=next((r for r in oldc if r['gauge_id']==c['gauge_id'] and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['subset']==c['subset'] and r.get('cohort')=='EHYD_24_2018_2019'),None)
 if not old:continue
 comparisons.append({'gauge_id':c['gauge_id'],'region':c['region'],'subset':c['subset'],'n_2018_2019':old['n'],'n_2020':c['n'],'skill_2018_2019':old['MSE_skill'],'skill_2020':c['MSE_skill'],'skill_change':float(c['MSE_skill'])-float(old['MSE_skill']) if c['MSE_skill'] and old['MSE_skill'] else None,'NSE_C0PT_2018_2019':old['NSE_C0PT'],'NSE_C0PT_2020':c['NSE_C0PT'],'NSE_L1_2018_2019':old['NSE_L1'],'NSE_L1_2020':c['NSE_L1'],'KGE_C0PT_2018_2019':old['KGE_C0PT'],'KGE_C0PT_2020':c['KGE_C0PT'],'KGE_L1_2018_2019':old['KGE_L1'],'KGE_L1_2020':c['KGE_L1']})
cw(R/'P6C_VS_2018_2019.csv',comparisons);cw(R/'P6C_SEASONAL_FAILURE_DIAGNOSTICS.csv',[r for r in comparisons if r['subset'] in ['DJF','MAM','JJA','SON','MAY_JUNE']])
downloads=[jl(p) for p in sorted((R/'driver').glob('T*_DOWNLOAD.json'))];nbytes=sum(d['bytes'] for d in downloads);primary=[c for c in comp if c['quality_tier']=='DESCRIPTIVE_ARCHIVE' and c['prediction']=='raw' and c['subset']=='ALL'];positive=sum(float(c['MSE_skill'])>0 for c in primary);mean_skill=float(np.mean([float(c['MSE_skill']) for c in primary]));median=float(np.median([float(c['MSE_skill']) for c in primary]));winter=[c for c in comp if c['quality_tier']=='DESCRIPTIVE_ARCHIVE' and c['prediction']=='raw' and c['subset']=='DJF'];summer=[c for c in comp if c['quality_tier']=='DESCRIPTIVE_ARCHIVE' and c['prediction']=='raw' and c['subset']=='MAY_JUNE'];strictn=len(ad['strict_sensitivity_ids']);strictstations=len({s.split(':')[0] for s in ad['strict_sensitivity_ids']});strictfull=sum(all(f'{g}:2020-{m:02d}' in ad['strict_sensitivity_ids'] for m in range(1,13)) for g in {int(s.split(':')[0]) for s in ad['descriptive_ids']})
annual=[]
for c in sorted(primary,key=lambda c:int(c['gauge_id'])):
 annual.append(f"- ID{c['gauge_id']}：C0+PT NSE {num(c['NSE_C0PT'])}、KGE {num(c['KGE_C0PT'])}；L1 NSE {num(c['NSE_L1'])}、KGE {num(c['KGE_L1'])}；MSE技能 {pct(c['MSE_skill'])}。")
regionlines=[]
for r in summary:
 if r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw' and r['subset']=='ALL':regionlines.append(f"- {r['region']}：{r['positive_stations']}/{r['stations']}站正技能，站点等权均值{pct(r['equal_station_mean_skill'])}，中位数{pct(r['station_median_skill'])}。")
focus=[]
for g in [185,377,455,512,545,533]:
 for subset in ['ALL','DJF','MAY_JUNE']:
  r=next((r for r in comparisons if int(r['gauge_id'])==g and r['subset']==subset),None)
  if r:focus.append(f"- ID{g} {subset}：2018–2019技能{pct(r['skill_2018_2019'])} → 2020技能{pct(r['skill_2020'])}；L1 NSE {num(r['NSE_L1_2018_2019'])} → {num(r['NSE_L1_2020'])}。")
cilines=[]
for mid in ['C0+PT','P2-L1']:
 for lev in [.8,.9]:
  rr=[r for r in cis if r['model_id']==mid and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['subset']=='ALL' and float(r['nominal'])==lev];cilines.append(f"- {mid} 名义{lev:.0%}：站点等权覆盖率{pct(np.mean([float(r['coverage']) for r in rr]))}，宽度/区间分数按站保存在P6C_INTERVAL_DIAGNOSTICS.csv；不混合不同流域量纲平方误差。")
negative={mid:sum(float(r['NSE'])<0 for r in metricsrows if r['model_id']==mid and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw' and r['subset']=='ALL' and r['NSE']) for mid in ['C0+PT','P2-L1']}
strictsummary=next(r for r in summary if r['quality_tier']=='STRICT_SENSITIVITY' and r['prediction']=='raw' and r['region']=='ALL' and r['subset']=='ALL')
boundary=readcsv(S/'P6C_FIXED_DAY_SHIFT_SENSITIVITY.csv');boundarysummary=[]
for r in boundary:
 base=next(b for b in boundary if b['gauge_id']==r['gauge_id'] and b['model_id']==r['model_id'] and b['calendar_day_shift']=='0');boundarysummary.append({'gauge_id':r['gauge_id'],'model_id':r['model_id'],'calendar_day_shift':r['calendar_day_shift'],'n':r['n'],'NSE':r['NSE'],'NSE_difference_from_provider_calendar':float(r['NSE'])-float(base['NSE']) if r['NSE'] and base['NSE'] else None,'MSE':r['MSE'],'MSE_relative_difference':float(r['MSE'])/float(base['MSE'])-1 if base['MSE'] and float(base['MSE'])>0 else None,'NOT_timezone_correction':True})
cw(R/'P6C_DAY_SHIFT_SUMMARY.csv',boundarysummary)
midlines=[]
for mid in ['C0+PT','P2-L1']:
 rr=[r for r in metricsrows if r['model_id']==mid and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw' and r['subset']=='ALL'];midlines.append(f"- {mid}：站点中位NSE {num(np.median([float(r['NSE']) for r in rr]))}，中位KGE {num(np.median([float(r['KGE']) for r in rr]))}。")
md('P6C_DRIVER_PARITY_REPORT.md',f'''# P6C 原口径气象驱动验证

通过官方CDS ERA5-Land hourly time-series接口下载{len(downloads)}个紧凑区域包，共{nbytes:,}字节。仅请求2m temperature和total precipitation，日期2015-01-01至2021-01-01，覆盖177个实际所需格点；请求矩形含333个格点，不是单点流域替代。官方下载回执、job ID、MD5、SHA256和NetCDF原始成员均保存于driver。

使用P6B冻结官方A全上游几何、原格点及交叠面积整数截断归一权重。ARCO降水已经反累计，绝不再次差分；降水时间戳减1h。小时流域加权后P取0.01mm、T取0.1°C；日P求和取0.01mm、T平均取0.1°C；月累计P、按完整日平均T。每年2020有366天×24小时。2019最终小时仅在历史重叠验证按原脚本填补规则复现，2020边界使用真实2021-01-01 00UTC。2020-01前月P来自已冻结原2019-12。

先验证ID2、377、533、171共4个代表站；全部通过后才处理其余站。全24站共1440个历史站月，实际通过{sum(s['pass_months'] for s in parity)}；门槛未改：每月P绝对差≤0.18mm、T绝对差≤0.052°C，P≥36mm时相对差≤0.005。最大月P差{max(s['max_P_abs_mm'] for s in parity):.8f}mm，最大月T差{max(s['max_T_abs_C'] for s in parity):.8f}°C。详情见driver/ALL24_HISTORICAL_PARITY.csv。数值容差通过表示按P6B契约一致，不能声称逐位完全相同。

复用P6B已验证ARCO与原小时产品的一致性证据，未重复反累计。官方产品DOI：10.24381/ee82e357；CC-BY。来源：https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries?tab=overview 。首次Windows IWR下载缓慢后中断，保留记录并通过标准TLS的系统curl下载同一job结果；未更改代理、证书、下载范围或权限。
''')
md('P6C_EXTERNAL_VALIDATION_REPORT_ZH.md',f'''# P6C：24站2020固定模型外部时间验证

实际新增{commit['stations']}站的{commit['sample_months']}个独立测试站月、{commit['prediction_records']}条模型预测；加载48个P4-V2模型，fit_calls=0。这里没有新增模型站点，新增的是这24个奥地利站的2020年独立时期。既有ID818-2020不重复计入。P6B的588个新增站月加本轮后为876站月、1752预测；连同P6A ID818-2018–2019累计为900站月、1800预测。

## 主要结果（raw、描述性归档）

P2-L1在{positive}/{len(primary)}站降低C0+PT的MSE；站点等权平均技能{pct(mean_skill)}，中位数{pct(median)}。C0+PT有{negative['C0+PT']}站NSE<0，L1有{negative['P2-L1']}站NSE<0，全部保留。不同流域原始MSE不汇合成单一技能。

{chr(10).join(regionlines)}

{chr(10).join(midlines)}

## 全部24站

{chr(10).join(annual)}

完整NSE、KGE及分量、MSE、RMSE、MAE、PBIAS、均值和相对技能见P6C_PRIMARY_2020_METRICS.csv；所有质量层、季度、高低流量和nonnegative见P6C_ALL_STATION_METRICS.csv。单位为来源m³/s，MSE为(m³/s)²。

## 季节、历史失败及年际变化

DJF正技能{sum(float(c['MSE_skill'])>0 for c in winter)}/{len(winter)}站，等权平均{pct(np.mean([float(c['MSE_skill']) for c in winter]))}；5–6月正技能{sum(float(c['MSE_skill'])>0 for c in summer)}/{len(summer)}站，等权平均{pct(np.mean([float(c['MSE_skill']) for c in summer]))}。DJF是2020年1/2/12月，非单个连续冬季；3月或2个月子集的NSE/KGE可能极不稳定。

{chr(10).join(focus)}

逐站2018–2019对比见P6C_VS_2018_2019.csv。2020只有1个新年度，不能对跨年稳健性作强推断；同水系站点可能嵌套或共享气候，未把24站当作24个独立重复进行显著性检验。高低流量阈值固定来自各模型训练期Q20/Q80，空子集明确N/A。年度误差集中度仅报告最坏月和最高3月SSE占比，不将一年的数据称为多年年度稳定性。

## 区间、支持与质量

{chr(10).join(cilines)}

区间沿用P4季节经验半宽，没有用新Q校准。每站每季区间宽度及Interval Score、输入支持状态和训练均值漂移均保留；IN_SUPPORT不是低误差或业务可靠性的保证。负预测的nonnegative次分析预先固定，不用次分析替换raw主结论。

主分析{commit['sample_months']}站月来自eHYD日均归档，2020每站366个有限非负真实日值，不填补。保守STRICT_SENSITIVITY剩{strictn}站月、{strictstations}站有至少1月、{strictfull}站完整12月；排除每个适用OWF-Q附注月份（含长期调节背景），因此可能过度保守，不能等同逐日QC认证。完整名单及附注见P6C_STATION_ADMISSION.csv。

保守敏感性完整年度{strictsummary['positive_stations']}/{strictsummary['stations']}站正技能，等权平均{pct(strictsummary['equal_station_mean_skill'])}，中位数{pct(strictsummary['station_median_skill'])}。部分月份仍保留原始结果，但不纳入完整年度汇总；该子集不是随机抽样，不能视为主样本的无偏认证替代。

eHYD导出说明值适用到下个时间戳/缺口，日期为每日00:00，但未找到足以将这些24站每日Q认证为UTC自然日的专门证据。已固定±1日的月标签边界诊断，不选择得分最佳的平移，也不将其冒称真实时区换算。缺少小时Q不能精确重建UTC日均；主成绩按提供方原日期不变。

P6B曾把含2020的整份Q归档解析进内存，本轮准入也需检查数值质量，所以这不是完全盲测。24站2020模型成绩在预测封存前没有用于筛选、调参或改变门槛；本轮预测进程禁止打开Q源，预测封存后在另一进程评分，独立复核验证。所有模型仍训练至2017年及以前。

## 数值与历史保护

独立标量预测、独立日均Q解析、全部指标/技能/区间重算和来源检查：{tests['passed']}通过、{tests['failed']}失败；1888个历史文件保持哈希不变。详见P6C_INDEPENDENT_VERIFICATION.json及evidence/HISTORY_AFTER.json。软件检查通过不等同于模型预测有效、站点质量认证或物理机制确认。

## P6D决策

已具备开展固定模型误差诊断的样本基础：对同一24站2018–2020逐站检查均值漂移、季节模板、气象贡献、误差集中度和区间失配。优先检查185/377/455/512/545及冬季533/545。不得把误差直接归因为积雪、水库、地下水或调度；这些仍需独立机制证据。P6D应冻结诊断口径，不能在已评分资料上调参后再称独立测试；本轮没有启动P7训练。
''')
md('P6C_COMPLETION_REPORT_ZH.md',f'''# P6C交付状态

完成：24站身份及原全上游格点权重绑定；2020 Q366日检查；官方下载{len(downloads)}个小时P/T包；4代表站及全24站历史60月一致性；冻结准入及预测；48个原模型加载；{commit['prediction_records']}预测、{commit['sample_months']}站月独立评分；raw/nonnegative、季度/季节/高低流量、区间、固定日偏移、2018–2019逐站对比；独立复核{tests['passed']}通过/{tests['failed']}失败；历史1888文件未变。

限制/未完成：逐日QC认证、eHYD24站日界与UTC的精确认证、真正新的独立流域和多年度统计确认。保守敏感性{strictn}站月不是认证集。未训练、未调参、未读取教师Q、未修改网站或历史文件、未启动P7。

主要报告：P6C_EXTERNAL_VALIDATION_REPORT_ZH.md。完整指标：P6C_ALL_STATION_METRICS.csv，48行主指标：P6C_PRIMARY_2020_METRICS.csv。预测及评分子目录各自封存，根SHA256SUMS.txt列出全部新文件SHA256。所有成功和中断记录保留于RUN_ATTEMPTS.jsonl及driver/CDS_ATTEMPTS.jsonl。

新增公开资料：2015–2020全上游所需177格点2变量，下载矩形共333格点，{nbytes:,}字节。历史重叠仅气象验证，未重训历史模型。核心协议SHA256：{sha(R/'P6C_FROZEN_PROTOCOL.json')}。
''')
md('P6C_REPRODUCTION_GUIDE.md',f'''# 复核方法

使用既有环境 `{sys.executable}`，始终`-B`。历史路径只读。先验证根SHA256SUMS.txt，随后运行：

```powershell
& '{sys.executable}' -B '{R / 'code/verify.py'}'
```

verify只复核已有固定预测和评分，不fit。它会重写P6C复核证据；如需严格只读核验，直接按SHA清单计算即可。driver.py representatives/all复算小时链，不读取Q；不应覆盖已交付封存文件，应先复制整个P6C到新目录并相应设置p6c_common.R。run_fixed.py predict、score各有禁止覆盖目录检查，分别先封存预测、后读取Q。不要删除已存在run以刷成绩。CDS脚本仅用本机已有配置，凭据不在交付包内；所有已取得数据可离线重算。

原始数据和模型哈希记录于P6C_ADMISSION_FROZEN.json、预测COMMITMENT.json、driver下载回执；许可复用P6B/SOURCE_LICENSE_AND_DOWNLOADS.md，ERA5-Land新增产品为CC-BY、DOI10.24381/ee82e357。保留Copernicus/ECMWF、LamaH-CE与eHYD/BMLUK署名，不批量导出日/月Qobs。
''')
md('P6C_DAY_BOUNDARY_EVIDENCE.md','''# 日界证据与限制

直接证据：24份eHYD file5归档表头定义日均Abfluss、m³/s、每日00:00日期，并说明区间值持续到下一时间戳或缺口；表头未列UTC偏移。P6B身份和来源归档只读复用。

本轮核查官方 https://wasser.gv.at/hydjb/index.xhtml （2026-11-02）：提供eHYD长期站点元数据与CSV入口、法定公开来源说明；未发现24份file5具体UTC日界认证。官方eHYD旧PDF https://ehyd.gv.at/assets/eHYD/pdf/Aktuelle_Daten.pdf 当前404，记录为失败来源；不能用搜索缓存冒充已取得证据。

官方MEZ/MEZ夏令时通用说明及其他参数的观测规则不能直接证明本批流量归档的时区。也不能借用瑞士BAFU说明认证奥地利eHYD。故保持PROVIDER_CALENDAR_DAY / UTC_NOT_CERTIFIED。

协议在评分前固定±1日敏感性：保持原预测，分别用每天标注日期-1/0/+1天的源Q求月均；仅为月边界鲁棒性诊断，既不等于精确±1小时时区换算，也不将得分最佳偏移替换主结果。源日序列没有小时变化，无法精确还原UTC月均。
''')
manifest={'experiment':'PUBLIC_DATA_FIXED_MODEL_P6C','stations':commit['stations'],'new_station_months':commit['sample_months'],'new_predictions':commit['prediction_records'],'fit_calls':0,'model_count':48,'driver_packages':len(downloads),'driver_download_bytes':nbytes,'driver_required_grid_cells':177,'parity_station_months':1440,'parity_passed':sum(p['pass_months'] for p in parity),'positive_skill_stations':positive,'mean_station_skill':mean_skill,'median_station_skill':median,'strict_sensitivity_months':strictn,'QC_certified_months':0,'checks_passed':tests['passed'],'checks_failed':tests['failed'],'historical_files_unchanged':tests['historical_files_unchanged'],'protocol_hash':sha(R/'P6C_FROZEN_PROTOCOL.json'),'prediction_seal':sha(P/'SHA256SUMS.txt'),'scoring_seal':sha(S/'SHA256SUMS.txt'),'status':'COMPLETED_QUALIFIED_DESCRIPTIVE_EXTERNAL_VALIDATION','no_teacher_data':True,'no_web_changes':True,'P6D_ready':'DESCRIPTIVE_DIAGNOSTICS_ONLY'};jw(R/'P6C_FINAL_STATUS.json',manifest);event('P6C_REPORT_COMPLETE',**manifest);seal(R);print(json.dumps(manifest,indent=2));print('ROOT_SHA_MANIFEST',sha(R/'SHA256SUMS.txt'))
