"""Evidence-backed delivery reports, exact code diff, and hashes. No training."""
import calendar,collections,csv,difflib,hashlib,html,json,math,re,shutil,sys
from pathlib import Path
import numpy as np
from pyproj import Transformer,Geod
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');R2=R.parent/'vhs_web_r2_host_integration';P4=R.parent/'p4_final_reconstruction';P=R/'p6';D=R/'diagnostics';E=R/'external'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def cr(p,enc='utf-8-sig'):
 with Path(p).open(encoding=enc,newline='') as f:return list(csv.DictReader(f))
def iter_csv(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:yield from csv.DictReader(f)
def jw(name,v):(R/name).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def write(name,s):(R/name).write_text(s,encoding='utf-8')
def cw(name,rows):
 with (R/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
summary=jl(D/'DIAGNOSTIC_SUMMARY.json');comp=cr(D/'V1_DESCRIPTIVE_MODEL_COMPARISON.csv');stability=cr(D/'V1_STABILITY_DIAGNOSTICS.csv');templates=cr(D/'PREDICTION_TEMPLATE_SUMMARY.csv');alphas=cr(D/'ALPHA_108_MODEL_AUDIT.csv');cal=cr(D/'INTERVAL_CALIBRATION_MECHANISM.csv');p6comp=cr(P/'runs/P6A_V2_2018_2019_SCORING/P6_MODEL_COMPARISON.csv');p6metrics=cr(P/'runs/P6A_V2_2018_2019_SCORING/P6_METRICS.csv');p6interval=cr(P/'runs/P6A_V2_2018_2019_SCORING/P6_INTERVAL_DIAGNOSTICS.csv')
# Primary FOEN coordinates resolve the apparent >500 m offset from rounded CAMELS/EStreams lat/lon.
txt=html.unescape(re.sub('<[^>]+>',' ',(E/'FOEN_2304_STATION.html').read_text(encoding='utf-8')));match=re.search(r"Koordinaten der Station\s+([0-9']+)\s*/\s*([0-9']+)",txt);assert match
east,north=[int(x.replace("'",'')) for x in match.groups()];wgs=Transformer.from_crs(2056,4326,always_xy=True).transform(east,north);old=next(s for s in jl(R/'evidence/P6_ORIGINAL_STATION_METADATA.json') if s['gauge_id']==818);dist=Geod(ellps='WGS84').inv(*old['coordinates_wgs84'],*wgs)[2]
identity_supp={'gauge_id':818,'official_gauge_id':'2304','primary_source':'https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen-und-daten/2304','source_hash':sha(E/'FOEN_2304_STATION.html'),'primary_EPSG2056':[east,north],'transformed_WGS84':list(wgs),'distance_to_LamaH_m':dist,'rounded_CAMELS_EStreams_distance_m':542.4428437731848,'interpretation':'two-decimal metadata rounding is not station relocation evidence; primary coordinates agree within13m','relocation_history':'No relocation event record obtained; do not assert absence of historical migration','performed_after_scoring':'identity continuity supplement only, no sample or metric changes'};jw('p6/P6_PRIMARY_COORDINATE_CONTINUITY.json',identity_supp)
rows=[]
for r in iter_csv(E/'monthly_streamflow_mean.csv'):
 dt=r[''][:7]
 if '2018-01'<=dt<='2020-12':
  for g,bid in [(818,'CH000097'),(611,'DEBY0480'),(688,'DEBY0802')]:
   token=r.get(bid,'');rows.append({'gauge_id':g,'estreams_id':bid,'date':dt,'monthly_index_present':token.lower() not in {'','nan','na'},'primary_admitted':False,'reason':'DERIVED_MONTHLY_DAYCOUNT_QC_NOT_AVAILABLE','source_file_hash':sha(E/'monthly_streamflow_mean.csv') if not rows else rows[0]['source_file_hash']})
cw('p6/P6_ESTREAMS_MONTHLY_AVAILABILITY.csv',rows)
camels=cr(E/'CAMELS_CAMELS_CH_obs_based_2304.csv');daycounts=collections.Counter(r['date'][:4] for r in camels if r['date'][:4] in ['2018','2019','2020'])
inventory=[{'gauge_id':g,'ERA5_Land_2018_2019_months':24,'ERA5_Land_2020_months':0,'official_new_daily_Q_2018_2019_days':730 if g==818 else 0,'official_new_daily_Q_2020_days':366 if g==818 else 0,'EStreams_2018_2020_monthly_indices_present':sum(r['monthly_index_present'] for r in rows if r['gauge_id']==g),'P6_scored_months':24 if g==818 else 0,'Q_unit':'m3/s confirmed CAMELS column' if g==818 else 'Monthly index units require additional provider-method verification; not scored','status':'QUALIFIED_DESCRIPTIVE_COMPLETED' if g==818 else 'BLOCKED_PRIMARY_DAYCOUNT_QC'} for g in [818,611,688]];cw('p6/P6_DATA_AVAILABILITY.csv',inventory)
write('P6_DATA_ADMISSION_REPORT_ZH.md',f'''# P6新数据准入与身份核查

本轮日期：2026-11-02（Asia/Singapore）。协议在新模型评分前冻结，哈希 `{sha(P/'P6_PROTOCOL_FROZEN.json')}`。没有重新训练或修改alpha。

三站的原始LamaH-CE ERA5-Land文件均已存在，并逐日覆盖至2019-12-31。按原P4代码同样规则得到2018–2019每站24个完整月：prec以日值mm累计、2m_temp_mean以°C日均值取月均；每月必须有完整且唯一的日历日。2017-12聚合与原P4月表逐值相同，L1取真实前一自然月。未使用E-OBS，未下载11.3GB气象包，未取得同处理口径2020气象，因此2020不评分。

## 已取得的真实Q与身份

- ID818：瑞士FOEN/BAFU官方2304站，Ova dal Fuorn / Zernez-Punt la Drossa；通过CAMELS-CH v0.9正式发布的observation_based文件取得实测discharge_vol(m3/s)，没有读取simulation_based模型Q。文件覆盖1981–2020，2018/2019/2020分别有{daycounts['2018']}/{daycounts['2019']}/{daycounts['2020']}个日记录。集水面积55.3km²一致。CAMELS/EStreams两位小数坐标导致542.4米表观差异；FOEN原始EPSG:2056坐标{east}/{north}转WGS84后与LamaH点相距{dist:.2f}米，支持同一站点身份。未获得历史迁站事件记录，不能声称整个历史从未迁站。
- ID611：德国Dillingen / Donau，官方10035801，EStreams DEBY0480；站码、11378.7km²面积一致，坐标差3.92米。已取得EStreams月均Q索引，官方已检查日均Q下载未成功（实际网络/DNS失败记录已保留）。月索引没有逐月有效日数，不能伪装成完整日均资料。
- ID688：德国Stegen / Amper，官方16602303，EStreams DEBY0802；站码、993.4km²面积一致，坐标差4.63米。EStreams名称写成Landsberg am Lech，与官方Stegen不一致；官方HND/GKD主站记录、站码和坐标支持这是区县名称混入，而非仅凭名称判定。官方Q任务已提交，但未获得文件，后续实际页面出现Request Rejected；未绕过该拒绝。月索引同样缺有效日数和逐日QC。

EStreams月索引文件的实际非空覆盖与目录并不相同：818在2018–2020有{inventory[0]['EStreams_2018_2020_monthly_indices_present']}个月；611/688分别只有{inventory[1]['EStreams_2018_2020_monthly_indices_present']}/{inventory[2]['EStreams_2018_2020_monthly_indices_present']}个月，而不是目录终止日期所暗示的连续覆盖。精确月份见P6_ESTREAMS_MONTHLY_AVAILABILITY.csv。原始月索引成员已通过ZIP CRC32核验并记录SHA256。仅定向下载约57.9MB压缩成员，没有下载2.3GB整个索引包。它们没有进入本轮主评分；不要把“下载到了月索引”误写成“完成严格Q准入”。

## 质量分层与许可

CAMELS-CH正式发布没有逐日checked/suspect标志；本轮仅在完整日历月、数值有限非负的条件下，按预冻结协议允许**有质量限制的描述性P6验证**。它不等价于旧LamaH ckhs=1，不是业务认证，也不是QC完全无疑的确认性测试。FOEN站页的当前冬季结冰警告只支持需要核查历史QC这一风险，不能断言2018/2019误差由结冰导致。

CAMELS-CH 15025258/v0.9 API声明CC BY 4.0（原始来源FOEN/BAFU）；EStreams 17598150/v1.4 API声明CC BY-NC 4.0，其气象为E-OBS，本轮没有使用；原LamaH-CE和ERA5-Land继续沿用冻结来源与署名记录。不同许可没有互相覆盖，新增源文件不经网页批量导出。

官方依据：[CAMELS-CH发布](https://zenodo.org/records/15025258)、[EStreams v1.4](https://zenodo.org/records/17598150)、[FOEN2304](https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen-und-daten/2304)、[官方Stegen站](https://www.hnd.bayern.de/pegel/isar/stegen-16602303/stammdaten)。精确文件/字节范围/CRC/SHA256在external的下载回执与目录记录中。整个大归档MD5未通过局部下载重新验证，不能声称验证了完整归档。
''')
case_lines=[]
for g in [2,9,533,185,171,378,383,455]:
 r=next(x for x in templates if x['version']=='V1' and x['model_id']=='P2-L1' and int(x['gauge_id'])==g);c=next(x for x in comp if x['subset']=='ALL' and int(x['gauge_id'])==g);s=next(x for x in stability if int(x['gauge_id'])==g)
 case_lines.append(f'- ID{g}：模板—L1预测相关={float(r["correlation_prediction_vs_template"]):.4f}；气象修正RMS/模板标准差={float(r["correction_RMS_to_template_std"]):.3f}；L1相对C0+PT的MSE技能={float(c["MSE_skill"])*100:+.2f}%；改善年份{s["positive_years"]}/{s["n_years"]}；删除任一年后增益仍为正={s["jackknife_all_remaining_improvements_positive"]}。')
peak_lines=[]
allpeaks=cr(D/'YEARLY_PREDICTED_PEAKS.csv')
for g in [2,9,533,185,378,383]:
 pp=[r for r in allpeaks if r['version']=='V1' and r['model_id']=='P2-L1' and int(r['gauge_id'])==g]
 peak_lines.append('- ID'+str(g)+'：'+'；'.join(f'{r["year"]}年峰值{int(r["peak_month"])}月/{float(r["predicted_peak"]):.3f}m³/s，预测年均{float(r["annual_predicted_mean"]):.3f}m³/s' for r in pp)+'。')
season_lines=[]
for sub in ['DJF','MAY_JUNE']:
 vals=[float(x['MSE_skill']) for x in comp if x['subset']==sub];season_lines.append(f'- {sub}：{sum(x>0 for x in vals)}/{len(vals)}站正技能；流域等权平均{np.mean(vals)*100:+.2f}%，中位数{np.median(vals)*100:+.2f}%。不能跨站混合m³/s²误差。')
write('FROZEN_PREDICTION_DECOMPOSITION_REPORT_ZH.md',f'''# 冻结模型季节结构与气象增量

分类：DESCRIPTIVE_FROZEN_V1_V2_DIAGNOSTICS_NOT_P6。模型与alpha均冻结；原P4-V1的2015–2017成绩不改写；V2的2016应用不作独立验证。

## 为什么不同年份曲线相似

模型精确形式为训练期十二个月独立Q均值 + 按同月训练气候态标准化的气象异常乘固定系数。月份均值每年完全重复，所有年际差异都必须经过P/T（L1另加真实上月P）修正进入。它没有显式土壤/积雪状态、随时间变化的月截距或当前目标Q反馈。

只读加载108个原保存模型，用冻结天气复算V1的1798条与V2的648条预测，总计2446条；最大绝对误差为0。训练气象月均值和ddof=1标准差逐值复现，月内标准化均值最大绝对值{summary['max_standardized_training_month_mean']:.3g}，没有发现该处实现错误。只对预测做分解，没有重新fit。

V1的25个L1模型预测与固定模板相关中位数{summary['median_V1_L1_template_correlation']:.4f}，但“模板压制全部站点气象”不成立：有些失败站的气象修正本身就大于模板季节幅度。各站、各月、各年峰值和年均变化全部保存在CSV，不只挑高分案例。

{chr(10).join(case_lines)}

各年实际冻结预测的峰值与年均（不是实测峰值）：

{chr(10).join(peak_lines)}

“P2-L1−C0+PT”是两个已保存模型的实际差值，包含直接L1项，也包含加入L1以后P/T系数和标准化块的重新分配。它不等于单独beta_L1*z_L1，更不能直接解释成前月降水的物理因果效应。

## 哪些旧结果支持气象增量

50个V1站—模型组合中，43个相对其冻结训练季节模板降低MSE；25站中15站的L1优于C0+PT。ID171/185三年均改善，jackknife删除任一年后仍正；ID185有约80.54%的绝对年度差异集中于一个年份，应保留强敏感性限制。ID9两年改善且jackknife仍正。ID2总体仅+1.11%，只有一年改善，不能作为稳定增量案例。

ID533的L1绝对NSE约0.9745，但MSE比C0+PT增加3.72%，比单独冻结模板增加12.77%；高NSE主要受到很强季节周期和较大总方差支持，不能推出气象带来增益。ID378/383/455的V1平均观测分别约1.177/0.539/0.604m³/s，L1预测均值约2.212/1.020/0.939m³/s；系统性水平偏差足以造成负NSE，前月项未纠正这一变化。这里可以识别的是统计偏差和时期漂移，不能识别为水库、融雪、冰川或人工调度的确定原因。

## 季节退步与区间

{chr(10).join(season_lines)}

DJF季节内观测方差小，单个月份的相对误差、固定偏移和测量质量问题都可能放大技能差异；5–6月高流量/峰值偏差需要状态记忆与源QC证据。当前这些是待检验假设，不是已发现的具体水文机制。V1分季节、逐年MSE、峰值月份、绝对贡献全部可复算。

区间每季只有12个主12月遮蔽残差，来源至多四个年度块；90%有限样本秩ceil(13×0.9)=12，直接使用最大绝对残差，80%秩=11。432个站—模型—版本—季节组合全部如此，288个还乘以大于1的历史P3 kappa，因此区间容易宽且对一个残差敏感。这是可验证的校准构造关系；没有通过重标定来人为变窄。

主要输出：FROZEN_PREDICTION_DECOMPOSITION.csv、MONTHLY_METEOROLOGICAL_CONTRIBUTIONS.csv、YEARLY_PREDICTED_PEAKS.csv、PREDICTION_TEMPLATE_SUMMARY.csv、V1_DESCRIPTIVE_MODEL_COMPARISON.csv、V1_YEAR_CONTRIBUTIONS.csv及INTERVAL_CALIBRATION_MECHANISM.csv（均在diagnostics）。旧V1标签只用于本轮描述性复核899个合法站月，未进入任何新模型拟合或选择。
''')
max_loss_delta=max((float(r['loss_at100'])/float(r['minimum_loss'])-1)*100 for r in alphas);minshrink=min(float(r['shrink_eigen_min']) for r in alphas);maxshrink=max(float(r['shrink_eigen_max']) for r in alphas)
write('ALPHA_108_MECHANISM_REPORT_ZH.md',f'''# 108个alpha和折内标准化机制

108=27站×2模型×V1/V2两版本，仅54个V2是当前正式保存模型。108个selected_alpha全部100，确实是冻结网格[0.01,0.1,1,10,100]的上边界。

只读复算每个模型保存的nested_CV记录：104个best_alpha=10，4个best_alpha=100；按最优平均年度损失加该最优候选的标准误构造cutoff，再在容许集合中选最大alpha，108个选择均与原记录一致。100相对最小CV损失的最大增加约{max_loss_delta:.3f}%，都在one-SE范围内。程序没有把100硬写成模型输出，也没有证据表明气象项全被归零。

数学目标是||y−训练月均Q−Zβ||² + α||β||²；Z按同月训练资料中心化、ddof=1标准化；不惩罚月截距。增强矩阵SVD求解，未把alpha误当成标准差；也没有采用按样本数归一化后的另一套alpha定义。对每个模型，从train_ids和冻结气象重建mu/sd，最大误差0；月内Z均值最大绝对值{summary['max_standardized_training_month_mean']:.3g}。系数单位为每标准差m³/s，原始P/T/L1单位下斜率按beta/sd逐月记录。

Z'Z特征值给出的岭收缩因子λ/(λ+100)在本批模型所有方向约为{minshrink:.3f}–{maxshrink:.3f}，不是“alpha=100就等于没学气象”。共同选择100来自本轮固定有限网格、平坦CV损失和one-SE偏好强收缩的组合；在上边界不能推出100是连续参数空间的最优值，也不能据此看旧测试分数扩展网格。

本轮没有运行新的CV、没有求解替代beta、没有扩大候选网格、没有重训。完整108行证据在diagnostics/ALPHA_108_MODEL_AUDIT.csv，逐月系数和标准化尺度在COEFFICIENT_SCALE_BY_MONTH.csv。
''')
overall=[r for r in p6metrics if r['subset']=='ALL' and r['prediction']=='raw'];metric_lines=[]
for r in overall:metric_lines.append(f'- {r["model_id"]}：NSE={float(r["NSE"]):.6f}，KGE={float(r["KGE"]):.6f}，RMSE={float(r["RMSE"]):.6f}m³/s，MAE={float(r["MAE"]):.6f}m³/s，PBIAS={float(r["PBIAS"]):+.3f}%。KGE r/alpha/beta={float(r["KGE_r"]):.6f}/{float(r["KGE_alpha"]):.6f}/{float(r["KGE_beta"]):.6f}。')
skill_lines=[f'- {r["subset"]}：L1相对C0+PT的MSE技能={float(r["MSE_skill"])*100:+.3f}%（n={r["n"]}月）。' for r in p6comp]
interval_lines=[f'- {r["model_id"]} {round(float(r["nominal"])*100)}%区间：覆盖={float(r["coverage"])*100:.2f}%，均宽={float(r["mean_width"]):.4f}m³/s，平均Interval Score={float(r["mean_interval_score"]):.4f}m³/s。' for r in p6interval if r['subset']=='ALL']
write('P6_INDEPENDENT_VALIDATION_REPORT_ZH.md',f'''# P4-V2的2018–2019独立时间评分：仅ID818，描述性且有质量限制

本轮日期：2026-11-02（Asia/Singapore）。分类PUBLIC_DATA_P6A_TEMPORAL_EXTERNAL_VALIDATION，任务RECONSTRUCTION_WITH_OBSERVED_MET。不是提前流量预报、不是锡尔河实验、不是三个完全独立流域的验证。

固定原P4-V2 C0+PT与P2-L1；训练截止2017-12，测试2018-01至2019-12。协议、模型哈希与24个合法月在评分前冻结；加载两个原模型，fit调用0。独立进程只读P/T和模型参数，审计钩子拒绝打开任何新Q源文件；48条预测及原冻结80%/90%区间先封存，再由单独评分步骤加载730个新观测日，形成24个月标签。Qobs未批量写入结果CSV。

## 实际成绩

{chr(10).join(metric_lines)}

{chr(10).join(skill_lines)}

总MSE小幅改善，但KGE略有退步；2018和冬季退步，增益不能称稳定或普遍。两个模型48个站—模型—月输入均为IN_SUPPORT，这只说明协变量处在冻结经验支持范围，不能等同于已通过水文或业务认证。

{chr(10).join(interval_lines)}

L1的80%区间95.83%覆盖、90%区间100%覆盖，90%均宽约2.03m³/s。这与既有保守区间构造一致，但仅24个月不能确认过覆盖或失配，也不能证明覆盖率定理；本轮不据此调整区间。DJF相对技能下降52.19%的同时，绝对MSE只由约0.00635增至0.00966m⁶/s²，必须同时看绝对尺度，不能只看百分比。

## 限制、失败与未执行

新Q来自CAMELS-CH官方observation_based发布，但无逐日QC标志，不能冒充原LamaH ckhs=1。主站原坐标与FOEN坐标相距约{dist:.2f}米，身份可核验；未得到历史迁站事件记录。仅一个流域、两年，不作有效性普遍性或正式显著性主张，不用两年bootstrap包装可靠区间。

611/688没有满足原冻结质量要求的官方日均Q，因此没有推理或评分；EStreams月索引的存在不是放宽完整日历月质量条件的理由。2020已取得818实测Q，但没有同处理口径的ERA5-Land驱动，不执行。没有针对新分数改alpha、模型、窗口或日期，没有回头重训P4。

48条预测在p6/runs/P6A_V2_2018_2019；评分和区间诊断在独立p6/runs/P6A_V2_2018_2019_SCORING，分别有SHA256SUMS。COMMITMENT、PREDICTION_READ_AUDIT、P6_PREDICTION_SEAL、SCORING_PROVENANCE与RUN_ATTEMPTS组成实际执行证据。
''')
# Exact candidate delta against frozen R2; no deployment into R2.
modified=[];patch=[]
for p in sorted((R/'host').rglob('*')):
 rel=p.relative_to(R/'host')
 if not p.is_file() or any(x in {'logs','tmp','var','__pycache__'} for x in rel.parts):continue
 old=R2/'host'/rel
 if old.exists() and sha(old)!=sha(p):
  modified.append(rel.as_posix())
  if p.suffix in {'.py','.js','.css','.html','.ps1'}:patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8-sig').splitlines(True),p.read_text(encoding='utf-8-sig').splitlines(True),fromfile='R2/'+rel.as_posix(),tofile='R2U1/'+rel.as_posix()))
write('R2U1_CODE_DIFF.patch',''.join(patch));jw('R2U1_CODE_DIFF.json',{'baseline':str(R2/'host'),'candidate':str(R/'host'),'modified':modified,'historical_writes':0})
write('R2U1_FIELD_COMPARISON.md','''# 修复前后字段与原因

冻结R2空间卡片里“V1评价状态”“V1误差风险”各出现5次。根因为生成器以保留在替换后字符串中的“输入支持”作为锚点，每次再运行都插入同一对字段；不是新增了五份独立风险评估。

R2U1从冻结R2基线生成独立副本，按明确起止边界整体替换该卡片；生成器再次运行不会累加。两字段各只出现一次。历史V1是否可评分、实际NSE/KGE、当前气象输入支持、经验区间评价、2018年后P6是否完成、业务认证六个维度分开显示。NOT_CERTIFIED保留，负NSE没有改成正常。

数据页全局四类清单的1798/899、648、24、0不变；另加当前站/模型/类别/时间窗的精确快照、发布ID和关联记录数，匹配来源行高亮。切换V1/V2同时更新当前来源与数量，不能把V2应用当独立成绩。

预测页使用冻结模型的真实十二月均值与气象项分解，单列直接L1贡献及实际L1−C0PT差值；展示用的相关和修正RMS清楚标记为该版本完整封存期，避免误认成局部筛选期统计。

修复前截图来自R2冻结验收产物，不伪造“前”状态；修复后截图在8793实际候选页面生成。路径和SHA256见evidence/BROWSER_EVIDENCE.json。
''')
write('RUN_AND_ROLLBACK.md',f'''# 运行、复核与回滚

候选主站：http://127.0.0.1:8793/#/overview?dataset=LAMAH_CE_PUBLIC_V1

```powershell
& '{R}/start_host.ps1'
& 'E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/.venv/Scripts/python.exe' -B '{R}/code/verify_u1.py'
& '{R}/stop_host.ps1'
```

只停止8793的已记录实际服务PID并检查UTC启动时刻和health身份；R2的8792、R1的8791与原8775不由本轮脚本管理。回滚只需停止8793，未替换R2文件。生产display仍NOT_GRANTED，正式接口、动态执行与Qobs导出保留403，教师Q未挂载。

P6复核可只读执行code/verify_u1.py；不要再次运行已经完成的admit/predict/score来覆盖原run，代码会拒绝覆盖。要做独立复现，先选新的独立输出目录并保持本轮协议、源文件和模型哈希一致。新拟合和调参不属于本轮。

本轮新增代码在code/，候选代码在host/；R2U1_CODE_DIFF.patch给出精确差异。运行日志、Chrome profile、PID记录位于runtime和host/logs/tmp/var，为可变运行区，关键验收已复制到evidence。根SHA256SUMS封存其余交付文件；独立P6预测与评分各自另有manifest。
''')
write('NEXT_EXPERIMENT_DECISION.md','''# 下一阶段决策

不把P6的小幅总MSE改善升级为L1稳定有效。保留C0+PT和L1为并列固定参照，不重训或扩大alpha网格来刷2015–2019分数。ID818新验证显示冬季退步、年度符号不一致；旧V1的严重失败站显示明显时期均值偏移，不能仅用季节曲线高NSE证明气象机制。

第一优先级是补齐611/688的官方日均Q及质量标志，并取得更多不同水系的2018年后Q；已有2020 Q不能在缺同源气象时硬做预测。所有新增观测继续使用已发布模型，形成新的独立run。

模型机制研究应先检查固定月截距对时期漂移/基流变化的适应不足、寒季测量QC与储水记忆；如开展新的简单状态模型或积雪/土壤记忆模型，提前固定有限公式和训练范围，不回到已经看过的2018–2019当最终独立测试。P2-SNOW既有负结果保留，不临时调0°C阈值和窗口。新的方法选择之后需要未使用的更晚年份与同源ERA5-Land驱动作为最终检验。

区间优先研究按年度块独立校准的稳定性与Interval Score，不以降低宽度为唯一目标；四年度块导致每季只有12个残差且90%取最大残差这一限制，不能靠网页状态PASS解决。当前不推进GNN/LSTM/Transformer或无资料站泛化主张。
''')
print('Reports, primary-coordinate continuity, data inventory and exact R2U1 diff written')
