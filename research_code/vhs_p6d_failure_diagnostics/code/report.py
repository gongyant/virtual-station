from p6d_common import *
import statistics,shutil,platform,importlib.metadata
sys.stdout.reconfigure(encoding='utf-8');fail=cr(R/'P6D_STATION_YEAR_FAILURES.csv');season=cr(R/'P6D_SEASONAL_AND_DRIFT.csv');rows=cr(R/'P6D_MONTHLY_PAIRED_ERRORS.csv');delta=cr(R/'P6D_PREDICTION_DIFFERENCE_TERMS.csv');dec=cr(R/'P6D_PREDICTION_DECOMPOSITION.csv');template=cr(R/'P6D_TEMPLATE_AND_PEAK_DIAGNOSTICS.csv');interval=cr(R/'P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv');summary=cr(R/'P6D_STATION_EQUAL_SUMMARY.csv');tests=jl(R/'P6D_INDEPENDENT_VERIFICATION.json');extract=jl(R/'P6D_EXTRACTION_CHECKS.json');qa=jl(R/'P6D_FIGURE_AUTOMATED_QA.json');ids=jl(R/'P6D_DIAGNOSTIC_PROTOCOL.json')['gauge_ids']
def md(n,s):(R/n).write_text(s,encoding='utf-8')
def n(x,k=4):return 'N/A' if x in ['',None] else f'{float(x):.{k}f}'
def pct(x):return 'N/A' if x in ['',None] else f'{float(x)*100:.2f}%'
def fr(g,p):return next(r for r in fail if r['gauge_id']==str(g) and r['period']==p and r['quality_tier']=='MAIN_DESCRIPTIVE')
def sr(g,p,s='DJF',mid='P2-L1'):return next(r for r in season if r['gauge_id']==str(g) and r['period']==p and r['subset']==s and r['model_id']==mid)
# Loss share summary normalizes each station-year first, never pools raw discharge MSE.
monthshares=[]
for year in ['2018','2019','2020']:
 for model,col in [('C0+PT','SE_C0PT'),('P2-L1','SE_L1')]:
  for mo in range(1,13):
   vv=[]
   for g in ids:
    rr=[r for r in rows if r['gauge_id']==str(g) and r['year']==year];den=sum(float(r[col]) for r in rr)
    if den:vv.append(sum(float(r[col]) for r in rr if int(r['month'])==mo)/den)
   monthshares.append({'year':year,'month':mo,'model_id':model,'stations_with_defined_SSE':len(vv),'mean_station_annual_SSE_share':statistics.mean(vv) if vv else None,'median_station_annual_SSE_share':statistics.median(vv) if vv else None,'cross_basin_raw_MSE_pooled':False})
cw(R/'P6D_MONTH_OF_YEAR_LOSS_SHARES.csv',monthshares)
types=[]
for period in ['2018','2019','2020','2018_2019','2018_2020']:
 for subset in ['ALL','DJF','MAM','JJA','SON','MAY_JUNE']:
  rr=[r for r in season if r['period']==period and r['subset']==subset and r['model_id']=='P2-L1'];both=sum(float(r['MSE_skill_L1_vs_C0PT'])<0 and float(r['NSE'])<0 for r in rr);relonly=sum(float(r['MSE_skill_L1_vs_C0PT'])<0 and float(r['NSE'])>=0 for r in rr);absonly=sum(float(r['MSE_skill_L1_vs_C0PT'])>=0 and float(r['NSE'])<0 for r in rr);types.append({'period':period,'subset':subset,'stations':len(rr),'both_relative_and_absolute_failure':both,'relative_only':relonly,'absolute_only_despite_gain':absonly,'neither_failure':len(rr)-both-relonly-absonly,'mean_station_skill':statistics.mean(float(r['MSE_skill_L1_vs_C0PT']) for r in rr),'median_station_skill':statistics.median(float(r['MSE_skill_L1_vs_C0PT']) for r in rr)})
cw(R/'P6D_FAILURE_TYPE_SUMMARY.csv',types)
neg20=[r['gauge_id'] for r in fail if r['period']=='2020' and r['quality_tier']=='MAIN_DESCRIPTIVE' and float(r['MSE_skill'])<0];neg36=[r['gauge_id'] for r in fail if r['period']=='2018_2020' and r['quality_tier']=='MAIN_DESCRIPTIVE' and float(r['MSE_skill'])<0];abs36=[r['gauge_id'] for r in fail if r['period']=='2018_2020' and r['quality_tier']=='MAIN_DESCRIPTIVE' and float(r['L1_NSE'])<0];wj=next(r for r in types if r['period']=='2020' and r['subset']=='DJF');top=[r for r in fail if r['period']=='2020' and r['quality_tier']=='MAIN_DESCRIPTIVE'];top1=statistics.median(float(r['L1_top1_SSE_fraction']) for r in top);top3=statistics.median(float(r['L1_top3_SSE_fraction']) for r in top);topmonths=sorted([r for r in monthshares if r['year']=='2020' and r['model_id']=='P2-L1'],key=lambda r:r['mean_station_annual_SSE_share'],reverse=True)[:3]
lagrat=[]
for g in ids:
 dd=[r for r in dec if r['gauge_id']==str(g) and r['model_id']=='P2-L1' and r['year']=='2020'];lagrat.append(statistics.mean(abs(float(r['L1_contribution'])) for r in dd)/float(dd[0]['train_Q_std']))
yearlines=[]
for r in summary:
 if r['macro']=='ALL':yearlines.append(f"- {r['period']}：{r['positive_skill_stations']}/{r['stations']}站正技能，站点等权平均{pct(r['mean_station_skill'])}，中位数{pct(r['median_station_skill'])}；L1绝对负NSE站数{r['L1_negative_NSE_stations']}。")
case=[]
for g in [171,185,255,343,383,455,533,545]:
 r=fr(g,'2020');case.append(f"- ID{g}：全年L1 NSE {n(r['L1_NSE'])}，相对技能{pct(r['MSE_skill'])}；最大误差月{r['L1_worst_month']}占全年SSE {pct(r['L1_top1_SSE_fraction'])}，前三月占{pct(r['L1_top3_SSE_fraction'])}；最大增量损害月{r['largest_harm_month']}。")
identity=[]
for g in [455,171]:
 for period in ['2018_2019','2020']:
  r=fr(g,period);identity.append(f"- ID{g} {period}：MSE改善 = {n(r['delta_MSE_alignment_term'],6)} − {n(-float(r['delta_MSE_change_cost']),6)} = {n(r['mean_delta_MSE'],6)}；技能{pct(r['MSE_skill'])}。")
r171=next(r for r in rows if r['gauge_id']=='171' and r['date']=='2020-03');r455=fr(455,'2020');m171=fr(171,'2020');wintercases=[]
for g in [533,545,383,2,9]:
 r=sr(g,'2020');wintercases.append(f"- ID{g}：L1技能{pct(r['MSE_skill_L1_vs_C0PT'])}，NSE {n(r['NSE'])}；RMSE {n(r['RMSE'])} m³/s，对应观测标准差仅{n(r['Qobs_std'])} m³/s；平均误差{n(r['bias'])} m³/s，偏差平方占MSE {pct(r['bias_squared_share_of_MSE'])}；幅度状态{r['amplitude_class']}。")
templines=[]
for g in [533,545,171,455]:
 r=next(r for r in template if r['gauge_id']==str(g) and r['model_id']=='P2-L1' and r['period']=='2020');templines.append(f"- ID{g}：预测与季节模板相关{n(r['prediction_template_correlation'])}；气象总修正RMS {n(r['weather_correction_RMS'])} m³/s，季节模板标准差{n(r['seasonal_template_std'])} m³/s；前月P项平均绝对贡献{n(r['L1_contribution_mean_abs'])} m³/s。")
contriblines=[]
for g in [455,171]:
 r=next(r for r in delta if r['gauge_id']==str(g) and r['period']=='2020');contriblines.append(f"- ID{g}：前月P项RMS {n(r['lag_term_RMS'])} m³/s，总预测差RMS {n(r['RMS_prediction_change'])} m³/s；当月P/T项差值RMS分别{n(r['currentP_term_RMS'])}/{n(r['currentT_term_RMS'])} m³/s；季节项差为{n(r['seasonal_term_RMS'])}。")
cilines=[]
cisummary=[]
for period,expected in [('2018_2019',24),('2020',12),('2018_2020',36)]:
 for quality in ['MAIN_DESCRIPTIVE','STRICT_SENSITIVITY']:
  for subset in ['ALL','DJF','MAM','JJA','SON','MAY_JUNE']:
   for mid in ['C0+PT','P2-L1']:
    for lev in ['0.8','0.9']:
     rr=[r for r in interval if r['period']==period and r['quality_tier']==quality and r['subset']==subset and r['model_id']==mid and r['nominal']==lev and int(r['n'])>0 and (subset!='ALL' or int(r['n'])==expected)];s={'period':period,'quality_tier':quality,'subset':subset,'model_id':mid,'nominal':lev,'stations':len(rr),'full_period_required_for_ALL':True,'spatial_independence_assumed':False}
     for key in ['coverage','mean_width_m3s','mean_interval_score_m3s','width_divided_by_Qobs_mean','width_divided_by_Qobs_std','interval_score_divided_by_Qobs_mean']:
      vv=[float(r[key]) for r in rr if r[key]!=''];s['station_equal_mean_'+key]=statistics.mean(vv) if vv else None;s['station_median_'+key]=statistics.median(vv) if vv else None;s['defined_stations_'+key]=len(vv)
     cisummary.append(s)
cw(R/'P6D_INTERVAL_STATION_EQUAL_SUMMARY.csv',cisummary)
for mid in ['C0+PT','P2-L1']:
 for lev in ['0.8','0.9']:
  rr=[r for r in interval if r['period']=='2020' and r['subset']=='ALL' and r['quality_tier']=='MAIN_DESCRIPTIVE' and r['model_id']==mid and r['nominal']==lev];cilines.append(f"- {mid} 名义{float(lev):.0%}：站点等权覆盖{pct(statistics.mean(float(r['coverage']) for r in rr))}；宽度/本站观测标准差的站点中位数{n(statistics.median(float(r['width_divided_by_Qobs_std']) for r in rr),2)}。")
ap=cr(R/'P6D_RHINE_APRIL_2020.csv');apr=[r for r in ap if r['model_id']=='P2-L1'];aprline='；'.join(f"ID{r['gauge_id']} T_z={n(r['T_z'],3)}、P_z={n(r['P_z'],3)}、{r['support_class']}" for r in apr)
evidence=[]
def ev(id,grade,claim,source,limit):evidence.append({'evidence_id':id,'grade':grade,'claim':claim,'source':source,'limitation':limit,'posthoc':True,'causal_certification':False})
ev('E01','CONFIRMED_NUMERICAL','864 paired station-months and1728 exact fixed prediction decompositions, fit0','P6D_MONTHLY_PAIRED_ERRORS.csv; P6D_EXTRACTION_CHECKS.json','No new forecast or new independent validation run')
ev('E02','CONFIRMED_NUMERICAL',f'2020 negative L1 skills {neg20}; pooled36 negative skills {neg36}','P6D_STATION_YEAR_FAILURES.csv','Pooled36 NSE recomputed, not mean yearlyNSE; correlated stations')
ev('E03','CONFIRMED_NUMERICAL','ID455 gain reversal is increased alignment benefit, not larger correction amplitude','P6D_PREDICTION_DIFFERENCE_TERMS.csv:455','Algebra explains error reduction; not physical causation')
ev('E04','CONFIRMED_NUMERICAL','ID171 March2020 is worst-error and largest negative gain month; correction cost exceeds total-year alignment benefit','P6D_MONTHLY_PAIRED_ERRORS.csv:171:2020-03','No proof of a particular hydrological event')
ev('E05','CONFIRMED_NUMERICAL','ID533/545 winter absolute NSE failures persist despite positive relative skills; low target variance amplifies NSE','P6D_SEASONAL_AND_DRIFT.csv:2020:DJF','Three noncontiguous calendar-year winter months; bias and centered errors both matter')
ev('E06','CONFIRMED_NUMERICAL','ID383 winter relative failure with positiveNSE, ID2/9 have both relative and absolute failures','P6D_SEASONAL_AND_DRIFT.csv:2020:DJF','Loss classifications are descriptive, not certified risk labels')
ev('E07','CONFIRMED_NUMERICAL','Four of five Rhine L1 models show Apr2020 temperature z>3; ID10 is just below threshold','P6D_RHINE_APRIL_2020.csv','Conditional anomaly relative to old train April; not proof of cause or physical event')
ev('E08','CONFIRMED_NUMERICAL','2020 interval coverage exceeds nominal while widths are multiple observed standard deviations','P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv','Network/time dependence; no test-based interval recalibration')
ev('E09','CONFIRMED_NUMERICAL','ID255 all12 2020 months IN_SUPPORT but annual NSE negative','P6D_INPUT_SUPPORT_ERRORS.csv:255:2020','Input distribution membership is not output reliability')
ev('H01','CANDIDATE_EXPLANATION','A fixed seasonal template plus constrained weather response may underrepresent interannual state changes','P6D_TEMPLATE_AND_PEAK_DIAGNOSTICS.csv; F1; F4','May test only in development folds; high correlation alone is not failure proof')
ev('H02','CANDIDATE_EXPLANATION','Season-dependent lag response or storage-memory mismatch could contribute to winter/MayJune contrast','P6D_FAILURE_TYPE_SUMMARY.csv; P6D_PREDICTION_DIFFERENCE_TERMS.csv','No lag/season coefficients re-estimated; not a proven hydrological mechanism')
ev('H03','CANDIDATE_EXPLANATION','Mean and amplitude drift are consistent with selected station failures','P6D_SEASONAL_AND_DRIFT.csv','Train/newQ source-vintage, quality and day-boundary differences are alternative explanations')
for id,mechanism in [('U01','snow/melt'),('U02','reservoir/dispatch/abstraction'),('U03','groundwater/glacier'),('U04','specific Apr2020 meteorological event')]:ev(id,'UNRESOLVED_PHYSICAL_MECHANISM',mechanism+' cannot be attributed from these linear terms alone','P6D_SEASONAL_AND_DRIFT.csv','Needs independent physical/state/operational evidence; not inferred as fact')
cw(R/'P6D_EVIDENCE_GRADE.csv',evidence)
md('P6D_RESEARCH_REPORT_ZH.md',f'''# P6D：2018–2020固定模型失效机制诊断

本轮是看过P6B/P6C成绩后的后验描述性诊断，不是新的预注册确认性检验，不新增真实训练或预测成绩。研究任务仍为观测气象驱动的月末历史重建，不是提前一个月预报。范围为原24个奥地利站、864个真实配对站月、1728条既有预测；只加载48个原P4-V2模型，fit_calls=0，模型/alpha/区间参数不变。

## 1. 增量是否持续

{chr(10).join(yearlines)}

2020失去增益站为{', '.join(neg20)}；36个月合并负技能站为{', '.join(neg36)}，合并负NSE只剩ID{', '.join(abs36)}。合并后的较好NSE不能消除2020单年/冬季失败：跨年均值差使合并SST变化，本报告从36条原记录重算，绝不平均年度NSE。ID171从2018–2019的+27.97%转为2020的−15.21%；ID455则由−11.92%转为+56.76%。相关站点和三年并非独立统计重复，没有总体显著性或跨流域普适结论。

## 2. 哪些月份造成主要损失

2020各站L1最坏单月占全年SSE的中位数为{pct(top1)}，前三个月占比中位数{pct(top3)}。先按每站全年SSE归一化、再站点等权汇总，最集中的三个日历月为{', '.join(str(r['month'])+'月('+pct(r['mean_station_annual_SSE_share'])+')' for r in topmonths)}。不能直接混合不同流域m³/s平方误差。

{chr(10).join(case)}

ID171在2020-03的Qobs为{n(r171['Qobs'])}、C0+PT为{n(r171['Qsim_C0PT'])}、L1为{n(r171['Qsim_L1'])} m³/s；L1变化{n(r171['prediction_change_L1_minus_C0'])}，当月平方误差改善量{n(r171['delta_SE_C0_minus_L1'])}（负值表示变坏），该月占L1全年SSE {pct(m171['L1_top1_SSE_fraction'])}。这是定位损失的数值事实，不是事件机制证明。

## 3. 为什么ID455、171反转

固定定义e=C0+PT−Qobs、d=L1−C0+PT，则逐月改善恒等于e²−(e+d)²=−2ed−d²。前项量化改变量与基线误差是否对准，后一项是改变量平方的代价，二者按同一月份平均。这里的代价是误差恒等式中的预测差平方，不是Ridge训练正则罚项。

{chr(10).join(identity)}

ID455的改变量平方代价在两时期接近，但对准基线误差的收益从0.013795增加到0.159236，因而转正；ID171对准收益从0.354375降至0.031633，而代价仍约0.15，因而转负。此结论无需改变模型即可由配对误差恒等式验证，不能据此断言水库、积雪或调度改变。

## 4. 冻结模型真实贡献

全部模型使用保存的12月climate及按月mu/sd，常数特征按原规则z=0；raw预测=climate+beta_P×zP+beta_T×zT（L1另加beta_L1×zL1）。本轮最大重构绝对误差{extract['max_prediction_reconstruction_abs_error']:.3g} m³/s。贡献单位为m³/s，beta本身在标准化空间；P6D_PREDICTION_DECOMPOSITION.csv另列每月原始单位有效斜率，不能把标准化系数直接当物理响应。

两模型差异必须包含前月P项、当月P/T项差和季节项差；同一固定变换下加法值明确，但相关变量的物理因果贡献并不唯一，未生成SHAP、未把回归项当作真实水文通量。

{chr(10).join(contriblines)}

2020前月P项的平均绝对值除以本站训练Q标准差，24站中位数{n(statistics.median(lagrat))}，范围{n(min(lagrat))}–{n(max(lagrat))}；这表示幅度，不代表独立解释率。

{chr(10).join(templines)}

季节模板每年重复、气象项为有限幅度的异常修正，因此某些年度曲线相似。高相关本身不证明失败：ID533全年NSE很高但冬季失败；相同季节背景下小的校正方向差也能改变MSE。P6D_TEMPLATE_AND_PEAK_DIAGNOSTICS.csv保留每站逐年观测/预测峰值月份和幅度、异常相关性及模板MSE，未以高分筛选展示站点。

## 5. 冬季失效与分布漂移

2020 DJF共有{wj['both_relative_and_absolute_failure']}站同时相对/绝对失败，{wj['relative_only']}站仅相对失败，{wj['absolute_only_despite_gain']}站虽相对改善但绝对NSE失败。DJF指该年1、2、12月，不是连续水文冬季；MAY_JUNE只有两个月。

{chr(10).join(wintercases)}

ID533的冬季观测方差仅为训练期同样日历月份方差的{pct(sr(533,'2020')['NSE_denominator_ratio_to_train_same_calendar'])}，ID545为{pct(sr(545,'2020')['NSE_denominator_ratio_to_train_same_calendar'])}。小分母放大NSE，但不是“只有分母问题”：533仍有正偏差及过大预测波动；545误差中大部分属于去均值后的形状/幅度失配。ID2/9冬季低估和波动不足；ID383冬季相对技能差却有正NSE，不能混作绝对失败。

训练Q均值/方差、按月气象异常及各季偏差平方占MSE均见P6D_SEASONAL_AND_DRIFT.csv。描述性漂移阈值已标为后验，不是新任务准入门槛。训练Q来自原LamaH，测试Q来自eHYD归档；P6B的2015–2017来源连续性证据只读复用。源版本、日期归属、QC差异仍可能参与均值差异，不能直接称为气候或人工调度变化。

2020-04 Rhine：{aprline}。四站警示由当月T相对训练期4月mu/sd超过3触发；ID10仅2.979，仍IN_SUPPORT。当前P偏低，但均未到|z|>3；前月P也未超阈值。共同警示的算法原因已确认，具体气象事件和径流机制未获独立证明。

## 6. 区间、QC及输入支持

{chr(10).join(cilines)}

覆盖高于名义值且宽度较大，与区间保守相符；24站单年及相关月份不足以认证长期覆盖率。完整宽度、按Q均值/标准差归一化宽度及Interval Score均保留；两模型站点等权均值与中位数另存P6D_INTERVAL_STATION_EQUAL_SUMMARY.csv，ALL完整时期门槛保留，季节严格子集仍注明实际n。没有使用测试Q调整半宽。

2020主分析288站月全部保留；STRICT_SENSITIVITY为132站月，只有4站完整12月，其余不补齐、不当认证集。P6D_DATE_BOUNDARY_FIXED_SENSITIVITY.csv逐值复用原±1日结果，不选择最优偏移，不将日平移当成精确时区换算。日均Q的UTC界及逐日QC仍未认证；气象历史1440站月符合原容差，不等于2020物理生产同质性已全面认证。

IN_SUPPORT不是准确性保证：ID255在2020所有12月均IN_SUPPORT，但L1全年NSE仍−2.0682。P6D_INPUT_SUPPORT_ERRORS.csv提供按站、时期及支持状态的误差；空状态N/A，未把没有风险警示当作可靠性认证。

## 7. 证据等级与P7决策

P6D_EVIDENCE_GRADE.csv逐条区分CONFIRMED_NUMERICAL、CANDIDATE_EXPLANATION、UNRESOLVED_PHYSICAL_MECHANISM。已证实的是误差位置、标准化特征项及偏差/波动失配；固定季节模板和季节相关记忆响应是候选解释。积雪、水库、取水、地下水、冰川或特定事件不能从这些回归项中识别。

已有证据足以制定小型P7开发假设，但不足以认定通用替代模型。优先在≤2017训练资料的按年份内外验证中检验：①前月P响应是否需要少量预先限定的季节交互；②固定模板的残差均值和幅度失配是否能由合法前期状态解释；③区间过宽是否源于训练期季节校准样本和误差异质性。不得用2018–2020 Q重新标定再称独立测试，也不应并行枚举大量窗口刷分。

未来测试应由独立保管者锁定尚未参与评分、调参或诊断设计的新时期/新流域，先冻结模型、名单、驱动口径和区间规则，再封存预测、后开放Q评分。不能直接把2021以后称为完全盲集：既有P6B/P6C解析器曾转换整份归档；P6D初版独立核验器也在筛年份前转换了归档数值，未用于2021+评分或分析，已保留初版并改成先按年过滤。本轮的正式分析仍仅使用2018–2020。真正盲测宜使用外部保管、尚未取得或接触的新归档时段（例如2024以后，须另核实实际覆盖/许可）；若用已有2021–2023，只能在暴露台账明确后称未评分留出时期，不夸称未接触标签。

## 8. 复核与交付限制

提取/数值约束检查{extract['passed']}通过/{extract['failed']}失败；独立标量、历史成绩对照和哈希核验{tests['passed']}通过/{tests['failed']}失败；{tests['history_entries_unchanged']}项历史文件与原v0.6代码哈希未变，未读取教师Q。四类图均由真实表生成，面板对齐及PDF字形检查通过。标准自动PDF碰撞检查{qa['not_auditable']}项因PyMuPDF缺失不可审计，未计为通过；已逐图视觉检查并修复日期标签裁切，未安装依赖。绘图初版源预检的字体/动态导出识别/220dpi问题已修正，最终源检查通过。

所有CSV中Qobs限本地公开数据研究使用：本轮明确要求逐月配对导出，不构成eHYD原始观测的无限再分发许可。本轮没有新增独立评分站月、没有训练、没有改网站/403/权限、没有启动P7或宣称业务认证。
''')
md('P6D_REPRODUCTION_GUIDE.md',f'''# P6D复现与文件映射

实际运行环境：{sys.executable}。工作目录：{R}。所有历史输入只读。未联网、未下载数据、未安装依赖。

实际运行的计算命令（均已执行，不是计划）：

```powershell
& '{sys.executable}' -B '{R/'code/extract.py'}'
& '{sys.executable}' -B '{R/'code/analyze.py'}'
& '{sys.executable}' -B '{R/'code/verify.py'}'
& '{sys.executable}' -B '{R/'code/figures.py'}'
& '{sys.executable}' -B '{R/'code/figure_qa.py'}'
& '{sys.executable}' -B '{R/'code/report.py'}'
```

不要在已封存P6D上重新执行写出命令。重新计算时先复制P6D到一个新研究目录，设置`$env:VHS_P6D_OUTPUT='新目录绝对路径'`，然后按上列顺序运行新目录code中的脚本；该变量只改变输出位置，P4/P6B/P6C输入不变。verify也写新目录核验结果。若只要只读验收，按根SHA256SUMS.txt逐文件核对，不运行生成器。fit/partial_fit等在提取进程内被拒绝，未导入原训练入口。

文件映射：P6D_MONTHLY_PAIRED_ERRORS.csv=864个主配对月；P6D_STATION_YEAR_FAILURES.csv=年度/24月/36月、主与严格子集；P6D_PREDICTION_DECOMPOSITION.csv=1728模型月真实项；P6D_SEASONAL_AND_DRIFT.csv=季节和训练参照；P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv=冻结区间与QC；P6D_EVIDENCE_GRADE.csv=分级结论。额外表保留预测差各项、模板/峰值、支持状态、Rhine4月、固定日期敏感性和归一化月份损失。

四类图：F1_MONTHLY_PREDICTIONS（用户指定8案例的36月曲线）、F2_ERROR_CONTRIBUTION（455/171逐月与累计贡献）、F3_SEASONAL_SKILL_AND_FAILURE（24站相对/绝对季节失败）、F4_FEATURE_CONTRIBUTIONS（455/171原模型项与差值项）。每图有PDF/SVG/300dpi PNG，源数据在figure_source_data，脚本为code/figures.py，输入/脚本/图哈希在P6D_FIGURE_PROVENANCE.json。图只表达原始点或描述性配对量，不包含置信区间/显著性主张。

质量限制：没有逐日QC和UTC认证；STRICT不是业务认证；季节n=2/3指标不稳定；网络站点相关；已有标签暴露必须记账。自动PDF碰撞审查依赖PyMuPDF，本环境缺失，NOT_AUDITABLE不能算PASS。图渲染、PDF字形及对齐采用现有Python；不使用R或AI生成数值/图片替代。

来源：LamaH-CE v1.0（Klingler, Schulz, Herrnegger 2021，DOI10.5281/zenodo.5153305，CC BY-SA4.0），Copernicus/ECMWF ERA5-Land（新小时来源DOI10.24381/ee82e357，CC-BY），Hydrographie Österreichs/BMLUK/eHYD归档。许可与署名继续沿用P6B/P6C来源说明，Qobs输出限本地研究。教师数据与SYRDARYA分支没有参与。
''')
env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{k:importlib.metadata.version(k) for k in ['numpy','matplotlib','Pillow']}};jw(R/'evidence/ENVIRONMENT.json',env)
visual=[]
for fig in jl(R/'P6D_FIGURE_PROVENANCE.json'):
 for i,panel in enumerate(fig['panels']):visual.append({'figure':fig['name'],'panel':chr(97+i),'unique_claim':panel,'center_summary':'raw observations/predictions or explicit matched differences','spread_interval':'none, raw descriptive values; not stochastic inferential aggregates','replicate_unit':'calendar month within station; stations may be network dependent','labels_legend':'reviewed in final300dpi PNG, dates repaired, units and sign stated','panel_alignment':'PASS saved alignment JSON','standard_PDF_collision':'NOT_AUDITABLE: PyMuPDF unavailable','manual_visual_readability':'PASS','causal_inference':False})
cw(R/'P6D_FIGURE_VISUAL_QA.csv',visual)
status={'experiment':'PUBLIC_DATA_POSTHOC_P6D_DIAGNOSTICS','status':'COMPLETED_DIAGNOSTICS_WITH_DECLARED_LIMITATIONS','stations':24,'paired_station_months':864,'frozen_predictions_explained':1728,'models_loaded':48,'fit_calls':0,'new_independent_test_months':0,'max_additive_reconstruction_abs_error':extract['max_prediction_reconstruction_abs_error'],'extraction_checks':{'passed':extract['passed'],'failed':extract['failed']},'independent_checks':{'passed':tests['passed'],'failed':tests['failed']},'history_entries_unchanged':tests['history_entries_unchanged'],'figure_classes':4,'figure_source_pdftext_checks':{'passed':qa['passed'],'failed':qa['failed'],'not_auditable':qa['not_auditable']},'figure_alignment_passed':4,'score_selection_or_interval_recalibration':False,'teacher_Q_read':False,'web_modified':False,'P7_started':False,'P7_research_design_ready':True,'P7_future_blind_test_reserved':False,'future_label_exposure_limit':'P6B/P6C whole-archive numeric parser and initial P6D verifier; later-period scores not analyzed; need independent holdout custody','scientific_limits':['posthoc','one shared24station cohort','small seasonal denominators','sourceQ vintage and dayQC/UTC uncertainty','mechanisms not identified'],'protocol_hash':sha(R/'P6D_DIAGNOSTIC_PROTOCOL.json'),'history_before_hash':sha(R/'evidence/HISTORY_BEFORE.json')};jw(R/'P6D_FINAL_STATUS.json',status);event('P6D_REPORT_COMPLETE',**status);seal(R);print(json.dumps(status,indent=2));print('P6D_MANIFEST_SHA256',sha(R/'SHA256SUMS.txt'))
