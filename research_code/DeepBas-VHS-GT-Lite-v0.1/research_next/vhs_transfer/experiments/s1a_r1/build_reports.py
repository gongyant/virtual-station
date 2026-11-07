"""Read sealed R1 outputs, audit arithmetic, and deliver Chinese reports. No refits."""
import ast
import numpy as np
from common import *

def number(r,k): return float(r[k])
def pct(x): return f'{100*x:+.3f}%'

def main():
    frozen=verify_freeze()
    params=load(HERE/'fitted_parameters.json')
    metric_rows=read_csv(HERE/'s1a_r1_fold_metrics.csv')+read_csv(HERE/'s1a_r1_f2_sensitivity.csv')+read_csv(HERE/'s1a_r1_placebo_metrics.csv')
    boot=read_csv(HERE/'s1a_r1_bootstrap_summary.csv')
    summary=load(HERE/'evaluation_summary.json')
    events=[json.loads(r) for r in (HERE/'execution_events.jsonl').read_text('utf-8').splitlines()]
    daily=read_csv(HERE/'scored_daily_view.csv')
    grouped={}
    for r in daily: grouped.setdefault((int(r['fold']),r['comparison']),[]).append(r)
    # Independent output arithmetic audit only, using already-scored daily view.
    # Does not open source labels, fit parameters, repeat bootstrap, or generate new predictions.
    audit_errors=[]
    for r in metric_rows:
        dd=grouped[(int(r['fold']),r['comparison'])]
        y=np.array([float(v['observed']) for v in dd]); p0=np.array([float(v['baseline']) for v in dd]); p1=np.array([float(v['augmented']) for v in dd])
        e0=p0-y; e1=p1-y; rm0=np.sqrt(np.mean(e0**2)); rm1=np.sqrt(np.mean(e1**2))
        checks={'baseline_RMSE':rm0,'augmented_RMSE':rm1,'relative_RMSE_gain':1-rm1/rm0,
                'baseline_MAE':np.mean(abs(e0)),'augmented_MAE':np.mean(abs(e1)),
                'baseline_PBIAS':100*e0.sum()/y.sum(),'augmented_PBIAS':100*e1.sum()/y.sum()}
        if any(not np.isclose(number(r,k),v,rtol=1e-12,atol=1e-12) for k,v in checks.items()):
            audit_errors.append((r['fold'],r['comparison']))
    if audit_errors: raise RuntimeError({'numeric_audit':audit_errors})
    before=load(HERE/'integrity_before.json')
    changed=[k for k,v in before['hashes'].items() if sha(ROOT/k)!=v]
    seal=load(HERE/'prediction_freeze.json')
    seal_changes=[k for k,v in seal['files'].items() if sha(ROOT/k)!=v]
    fits=[i for i,e in enumerate(events) if e['event']=='FIT_STARTED']
    scores=[i for i,e in enumerate(events) if e['event']=='SCORE_COMPLETE']
    eval_i=[i for i,e in enumerate(events) if e['event']=='EVALUATION_LABELS_OPENED']
    freeze_i=[i for i,e in enumerate(events) if e['event']=='ALL_PREDICTIONS_FROZEN']
    protocol_order=(len(fits)==48 and len(scores)==48 and len(eval_i)==1 and len(freeze_i)==1 and max(fits)<freeze_i[0]<eval_i[0]<min(scores))
    if changed or seal_changes or not protocol_order: raise RuntimeError('Integrity or evaluation order failed')
    integrity={'phase':'VHS-NEXT-S1A-R1','targeted_historical_files_checked':before['files'],
        'changed_historical_files':changed,'prediction_parameter_config_seal_changes':seal_changes,
        'authority_files_and_code_hashes_unchanged':True,'input_sha256_matches':True,
        'full_S0_rescan':False,'large_frozen_assets':'prior integrity records reused; not all assets rehashed',
        'S0_original_snapshot_files':2398,'evaluation_only_after_all_predictions_frozen':protocol_order,
        'fits':len(fits),'score_groups':len(scores),'refits_after_evaluation':0,
        'GPU':False,'historical_results_changed':False,'E5I1':False}
    dump(HERE/'s1a_r1_integrity_report.json',integrity)
    ledger=[]
    for p in params:
        year=p['fold']; k=p['k']; same=p['family']=='SAME_DAY'; offset=29 if same else 30
        upperlag=0 if same else 1
        tr_start=np.datetime64('1978-01-31'); tr_end=np.datetime64(f'{year-1}-12-31')
        def shift(d,n): return str(np.datetime64(d)-np.timedelta64(n,'D'))
        ledger.append({'fold':year,'comparison':p['comparison'],'target_parameter_role':'training supervision only',
            'target_parameter_start':str(tr_start),'target_parameter_end':str(tr_end),'target_parameter_n':p['source_parameter_fit_n'],
            'beta_target_start':p['fit_start'],'beta_target_end':p['fit_end'],'beta_target_n':p['fit_n'],
            'source_moments_anchor_start':str(tr_start),'source_moments_anchor_end':str(tr_end),
            'source_moments_raw_min':shift(tr_start,offset),'source_moments_raw_max':shift(tr_end,upperlag),
            'beta_source_raw_min':shift(p['fit_start'],k+offset),'beta_source_raw_max':shift(p['fit_end'],k+upperlag),
            'prediction_source_raw_min':shift(p['dev_start'],k+offset),'prediction_source_raw_max':shift(p['dev_end'],k+upperlag),
            'evaluation_target_start':p['dev_start'],'evaluation_target_end':p['dev_end'],'evaluation_n':p['dev_n'],
            'role':p['role'],'code_hashes':frozen['frozen_hashes'],'environment_sha256':sha(HERE/'environment.json')})
    dump(HERE/'data_role_ledger.json',ledger)
    placebo=[r for r in metric_rows if r['family']=='PLACEBO']
    curve=[]; response=[]
    for k in load(HERE/'execution_config.json')['placebo_k']:
        rr=[r for r in placebo if int(r['k'])==k]
        curve.append({'k':k,'gain_1981':number(rr[0],'relative_RMSE_gain'),'gain_1982':number(rr[1],'relative_RMSE_gain'),
            'gain_1983':number(rr[2],'relative_RMSE_gain'),'macro_equal_year_gain':float(np.mean([number(r,'relative_RMSE_gain') for r in rr]))})
    write_csv(HERE/'s1a_r1_placebo_curve.csv',curve,exclusive=False)
    for year in (1981,1982,1983):
        g={int(r['k']):number(r,'relative_RMSE_gain') for r in placebo if int(r['fold'])==year}
        near=np.mean([g[k] for k in (-7,-3,0,3,7)]); far=np.mean([g[k] for k in (-90,-60,60,90)])
        response.append({'year':year,'aligned_gain':g[0],'near_mean_gain':float(near),'far_mean_gain':float(far),
            'near_minus_far':float(near-far),'far_over_aligned':float(far/g[0]) if g[0]>0 else None,
            'aligned_minus_each_far':{str(k):g[0]-g[k] for k in (-90,-60,60,90)},
            'positive_minus_negative':{str(k):g[k]-g[-k] for k in (3,7,14,30,60,90)}})
    dump(HERE/'placebo_response_summary.json',response)
    # Original protocol's equal-year summaries and pooled auxiliary metrics.
    # Pooling below is only deterministic descriptive arithmetic, NEVER bootstrap.
    macro_rows=[]; pooled_rows=[]
    for comparison in summary['comparisons']:
        rr=[r for r in metric_rows if r['comparison']==comparison]
        macro={'comparison':comparison,'years':3,'weighting':'equal year',
               'relative_RMSE_gain':float(np.mean([number(r,'relative_RMSE_gain') for r in rr])),
               'DeltaNSE':float(np.mean([number(r,'DeltaNSE') for r in rr])),
               'worst_gain_year':min(rr,key=lambda r:number(r,'relative_RMSE_gain'))['fold'],
               'worst_augmented_RMSE_year':max(rr,key=lambda r:number(r,'augmented_RMSE'))['fold']}
        for prefix in ('baseline','augmented'):
            for key in ('RMSE','MAE','NSE','Bias','PBIAS','numeric_daily_sum_error','low_RMSE',
                        'abs_peak_date_error_days','peak_amplitude_error'):
                vals=[number(r,prefix+'_'+key) for r in rr if r[prefix+'_'+key]!='']
                macro[prefix+'_'+key]=float(np.mean(vals)) if len(vals)==3 else None
        macro_rows.append(macro)
        dd=[d for d in daily if d['comparison']==comparison]
        y=np.array([float(d['observed']) for d in dd])
        record={'comparison':comparison,'n':len(dd),'identity':'pooled auxiliary; autocorrelated days, not independent replicates'}
        for prefix in ('baseline','augmented'):
            p=np.array([float(d[prefix]) for d in dd]); e=p-y
            record.update({prefix+'_RMSE':float(np.sqrt(np.mean(e**2))),prefix+'_MAE':float(np.mean(abs(e))),
                prefix+'_NSE':float(1-np.sum(e**2)/np.sum((y-y.mean())**2)),
                prefix+'_Bias':float(e.mean()),prefix+'_PBIAS':float(100*e.sum()/y.sum())})
        pooled_rows.append(record)
    write_csv(HERE/'s1a_r1_macro_metrics.csv',macro_rows,exclusive=False)
    write_csv(HERE/'s1a_r1_pooled_auxiliary.csv',pooled_rows,exclusive=False)
    diag=read_csv(HERE/'s1a_r1_feature_diagnostics.csv')
    def ci(comp,block,circular=True,scope='MACRO_EQUAL_YEAR'):
        return next(r for r in boot if r['comparison']==comp and int(r['block_days'])==block and r['circular']==str(circular) and r['scope']==scope)
    def interval(r): return f"[{100*number(r,'gain_lower'):+.3f}%, {100*number(r,'gain_upper'):+.3f}%]"
    def family_text(family):
        text=''
        for r in metric_rows:
            if r['family']!=family: continue
            text+=f"- {r['fold']}：RMSE {number(r,'baseline_RMSE'):.6f} → {number(r,'augmented_RMSE'):.6f}；增益 {pct(number(r,'relative_RMSE_gain'))}；DeltaNSE {number(r,'DeltaNSE'):+.6f}。\n"
        return text
    base='身份：PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS。全部年份曾被历史研究接触；STRICT_ZERO_SHOT=false，INDEPENDENT_FINAL_TEST=false，CAUSAL_TRANSPORT_IDENTIFIED=false。单位仅为项目Q数值单位；日均/原始单位/水文日界/发布时刻/供数方未证实，不换算物理m³。\n\n'
    results='# VHS-NEXT-S1A-R1｜真实回顾性增量信息评价\n\n'+base
    results+='**主实验未通过预定实践规则。** Past-only两年退化、一年改善，宏平均为负，30/60日原始条件CI均跨0；不据此证明所有上游信息或非线性方法无效。\n\n'
    results+='## 1. Past-only主结果与完整支持\n\n'+family_text('PAST_ONLY')+'\n'
    results+=f"三年等权宏平均相对RMSE增益 **{pct(summary['comparisons']['past_only']['decision']['macro_relative_gain'])}**。每折真实支持365日；train=1066/1431/1796日，从1978-01-31开始。\n\n"
    results+='全部指标的等权年度宏平均见s1a_r1_macro_metrics.csv；pooled辅助见s1a_r1_pooled_auxiliary.csv。pooled仅描述性合并，不把日样本当独立重复，也不跨年拼接bootstrap；它不替代预定宏平均判定。\n\n'
    results+='原始规则依次为：三年均改善 **FAIL**；宏平均≥2% **FAIL**；30/60日circular条件95%CI下界>0 **FAIL**；PBIAS/低流代价门槛 **无越界**。综合MIXED_OR_UNCERTAIN，MAIN_DEVELOPMENT_GAIN_SUPPORTED=false；不能用1983单年或Same-day替代主结论。\n\n'
    results+='## 2. Same-day次要制度\n\n'+family_text('SAME_DAY')+'\n'
    results+=f"三年等权宏平均 {pct(summary['comparisons']['same_day']['decision']['macro_relative_gain'])}，同样不通过稳定实践规则。结果单独分组，不和Past-only混排；真实当天可用性未认证。\n\n"
    results+='## 3. 条件性Bootstrap\n\n每年内部独立配对抽样，10000次、seed20261011、固定30/60日；区间不是未来年份泛化区间，不覆盖训练估计、历史探索或跨年依赖。不报告总体显著性p值。\n\n'
    for comp,label in (('past_only','Past-only'),('same_day','Same-day'),('f2','F2')):
        results+=label+'三年等权宏平均相对RMSE增益95%CI：\n\n'
        for circular in (True,False):
            results+=f"- {'原始circular' if circular else '非环绕敏感性'}：30日 {interval(ci(comp,30,circular))}；60日 {interval(ci(comp,60,circular))}。\n"
        results+='\n'
    results+='非环绕区间也跨0，未改变主不确定性判断；两种方法均完整保留，未选择有利CI。全部16个预定配对对照的逐年及宏平均CI见bootstrap CSV；不同位移的区间不构成独立重复或经校正的显著性检验。\n\n'
    results+='## 4. 固定F2平滑季节敏感性\n\n'+family_text('F2')+'\n'
    results+=f"F2-only相对F2+同一monthly上游异常，宏平均 {pct(summary['comparisons']['f2']['decision']['macro_relative_gain'])}。仍为两年退化、一年改善；1981低流RMSE恶化 {pct(next(number(r,'low_RMSE_relative_change') for r in metric_rows if r['family']=='F2' and r['fold']=='1981'))}，超过5%门槛，NOT_ROBUST_USEFULNESS。没有复用Fourier6系数或搜索谐波。该敏感性不支持稳定增量，也不能单独判定月阶梯不足是唯一原因。\n\n"
    results+='## 5. 时间错位Placebo\n\n所有k在共同train=886/1251/1616日拟合beta，在共同开发Jan1..Oct2共275日评分；目标月气候态及源月份统计仍用原完整合法train。k=0也重新拟合、同掩码评分。下列数值不能与主365日结果直接比较。负k为非因果未来上游诊断。\n\n'
    for r in curve:
        results+=f"- k={r['k']:+d}：1981 {pct(r['gain_1981'])}；1982 {pct(r['gain_1982'])}；1983 {pct(r['gain_1983'])}；等权宏平均 {pct(r['macro_equal_year_gain'])}。\n"
    results+='\n真实对齐k=0分别为−11.225%、−0.282%、+8.014%，宏平均−1.164%。固定+30及+60日均在三年保留正点估计增益；其中+60为+2.862%、+2.428%、+6.957%，宏平均+4.082%。这些是固定网格的描述结果，不是新lag选择、不视为最佳传播时间，也不将2%主阈值移作placebo显著性标准。\n\n'
    for r in response:
        results+=f"{r['year']}：near均值−far均值={pct(r['near_minus_far'])}；far均值={pct(r['far_mean_gain'])}；far/aligned="+(f"{r['far_over_aligned']:.3f}" if r['far_over_aligned'] is not None else 'NA（aligned≤0）')+'。\n\n'
    results+='near固定{-7,-3,0,3,7}，far固定{-90,-60,60,90}。正负不对称逐对数字及g(0)-各far见placebo_response_summary.json。1983有局部近零改善，但1981/1982不复现，且远错位仍保留能力；没有跨年一致的真实对齐优势，L2_NOT_ESTABLISHED。共同天气、残留季节、慢变状态和自相关未排除。\n\n'
    results+='![固定错位的逐年增益曲线](../experiments/s1a_r1/s1a_r1_placebo_gain.png)\n\n图中各点为预定13个位移的逐年点估计，均为275日支持；空心点为未来上游诊断，实心点为k≥0。连线仅引导读图，不插值选择lag；不展示CI，条件CI在CSV。\n\n'
    results+='## 6. 共线性与系数\n\n'
    for r in diag:
        if r['family']=='PAST_ONLY':
            results+=f"- {r['fold']}：标准化beta=({number(r,'beta_1'):.6f}, {number(r,'beta_7'):.6f}, {number(r,'beta_30'):.6f})；条件数={number(r,'condition_number'):.6f}；VIF={r['VIF']}。\n"
    results+='\n三列满秩，未触发尺度或秩停止条件；三折beta全为正，但7日系数明显变化。标准差随折变化，标准化系数大小不能直接当固定物理效应；相关/SVD/VIF和所有对照系数完整保留，未删窗或加入ridge。\n\n'
    results+='## 7. 最差年份、洪峰与低流\n\n'
    for r in metric_rows:
        if r['family']=='PAST_ONLY':
            results+=f"- {r['fold']}：低流RMSE {number(r,'baseline_low_RMSE'):.6f} → {number(r,'augmented_low_RMSE'):.6f}（{pct(number(r,'low_RMSE_relative_change'))}）；洪峰日期误差 {int(r['baseline_peak_date_error_days']):+d} → {int(r['augmented_peak_date_error_days']):+d}日；峰值误差 {number(r,'baseline_peak_amplitude_error'):+.6f} → {number(r,'augmented_peak_amplitude_error'):+.6f}；绝对PBIAS变化 {number(r,'abs_PBIAS_worsening_pp'):+.6f}个百分点。\n"
    results+='\n最差增益年1981：RMSE恶化10.487%，峰日由晚34日恶化至晚55日，虽低流与总量偏差改善也不能掩盖整体失败。1982仍严重低估洪峰，1983峰日与RMSE改善但峰值明显偏低。主模型三年均无非负裁剪；F2/所有placebo的裁剪及月偏差完整列入CSV。洪峰只为日期索引/数值诊断，不是实测传播时滞。\n\n'
    results+='## 8. 证据边界与下一轮竞争解释\n\n没有获得跨三年稳定的L1增量证据；1983单年呈现条件开发改善，不能升格为总体稳定L1。L2未建立，L3/L4不能确认。TRANSPORT_INTERPRETATION_NOT_ESTABLISHED。负结果不证明上游没有任何信息，也不证明更复杂方法有效。\n\n'
    results+='下一轮最值得审查的单个竞争解释：**上游异常主要是慢变水文状态代理，而非可跨年稳定复现的日级同步信息**。远错位保留增益、年度方向分化与系数变化与此相容，但本轮没有识别其原因。未来必须另行授权并冻结检验，不据本轮曲线优化lag或立即开启新模型。\n\n'
    results+='## 9. 完整性与可复现交付\n\n'
    results+=f"{before['files']}个定向历史保护文件及已封存预测/参数/config哈希无变化。原始数据、E4/E5、论文、S0/S0.1/R0均未修改；无GPU、E5I1、Own-Past、R1/R2/Fourier6重拟合或未授权搜索。48个固定对照拟合，14010行预测，48组指标，256行bootstrap区间；全部预测先于开发标签评分封存。\n\n"
    results+='[执行清单](../experiments/s1a_r1/s1a_r1_execution_manifest.json)、[预测封存](../experiments/s1a_r1/prediction_freeze.json)、[逐次事件](../experiments/s1a_r1/execution_events.jsonl)、[完整数据角色台账](../experiments/s1a_r1/data_role_ledger.json)、[主指标](../experiments/s1a_r1/s1a_r1_fold_metrics.csv)、[Bootstrap](../experiments/s1a_r1/s1a_r1_bootstrap_summary.csv)、[完整性](../experiments/s1a_r1/s1a_r1_integrity_report.json)。\n\n本阶段完成后停止，等待新的用户批准。\n'
    (REPORTS/'vhs_next_s1a_r1_results.md').write_text(results,'utf-8')
    failure='# VHS-NEXT-S1A-R1｜失败分析\n\n'+base
    failure+='主实验未通过不是执行失败：所有计划年份/条件均保留，未改模型、窗口、阈值或支持。1981负增益最大，1982近零但略退化，1983改善不能补足“三年均改善”要求；宏平均及两种原始CI均不通过。\n\n'
    failure+='低流与绝对PBIAS改善不等于全年日级误差或洪峰拟合改善。1981主峰日期进一步偏晚，1982/1983峰值低估仍大。F2也未带来稳定上游增量，并在1981触发低流代价。各年逐月有符号偏差及裁剪原样保存，没有删除失败月或年。\n\n'
    failure+='安慰剂k=0的共同支持结果同样两年不改善；+30/+60仍有正增益，1983局部近零优势未在另外两年复现。不能把+60改为新主窗口，也不能用负位移的结果宣称提前预测或排除共同天气。当前固定13个对照不能认证任何最优时滞或物理传播速度。\n\n'
    failure+='VIF约2–4.2、条件数约3.9，三列满秩，没有数值秩故障证据；系数尤其7日项随折变化，且尺度变化使单系数机制解释不成立。跨年映射漂移、季节内相位/低频状态、共同气象、观测口径等均为未区分的解释。当前最值得单独研究的是慢变水文状态代理假说；本轮没有开展新检验。\n\n'
    failure+='只有三个相邻开发年且历史已暴露。CI条件于已拟合参数及年份，不覆盖训练参数估计与历史选择；circular年末/年初连接及noncircular边界权重均有限制。未认证单位/日界/发布时刻继续限制物理与业务解释。结果最多保留1983单年条件性预测改善，不建立跨年稳定L1或L2，更不能L3/L4。\n\n'
    failure+='本轮禁止且未执行：补删年份、调窗/lag/ridge/谐波、目标Own-Past输入、GNN/Muskingum搜索、S1B/S1C、新标签测试、旧论文结果覆盖。\n'
    (REPORTS/'vhs_next_s1a_r1_failure_analysis.md').write_text(failure,'utf-8')
    qa=load(HERE/'figure_qa_summary.json')
    if not all(r['returncode']==0 for r in qa): raise RuntimeError('Figure QA failed')
    for name in ('s1a_r1_placebo_gain','s1a_r1_conditional_gain','s1a_r1_residuals'):
        if load(HERE/f'{name}.collision.json')['verdict']!='PASS': raise RuntimeError('Figure collisions unresolved')
    validation={'execution_complete':True,'substantive_protocol_conflicts':False,
        'source_sha256_verified':True,'whitelist_columns_only':True,'fit_views_separated_from_evaluation':True,
        'frozen_predictions_before_all_scoring':protocol_order,'numeric_audit_groups':len(metric_rows),
        'numeric_audit_mismatch':audit_errors,'expected_prediction_rows':14010,'actual_prediction_rows':seal['prediction_rows'],
        'fits':len(fits),'evaluation_groups':len(scores),'bootstrap_rows':len(boot),
        'bootstrap_reps':10000,'bootstrap_seed':20261011,'block_days':[30,60],'circular_and_noncircular':True,
        'targeted_historical_files_unchanged':before['files'],'frozen_predictions_parameters_unchanged':True,
        'new_executor_synthetic_tests':load(HERE/'executor_synthetic_tests.json'),
        'figures_qa_pass':True,'source_scorer_no_fit_calls':True,'scientific_hypothesis_pass':summary['main_practical_pass'],
        'meaning':'Execution/identity/integrity/numeric PASS; primary stable incremental gain NOT supported'}
    tree=ast.parse((HERE/'score_results.py').read_text('utf-8'))
    function_names={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)}
    if function_names.intersection({'fit_model','fit_same_day','ols'}): raise RuntimeError('Scorer fitting path found')
    dump(HERE/'delivery_validation.json',validation)
    validation_md='# VHS-NEXT-S1A-R1｜执行与交付验证\n\n'+base
    validation_md+=f"执行/数值/完整性验证PASS；科研主实践规则未通过，二者严格分开。新增4项CPU合成检查通过，沿用哈希未变的R0数值模块及22项原测试证据，没有改写R0测试结果。\n\n"
    validation_md+=f"输入SHA匹配；2191个连续源日、每折train=1066/1431/1796、完整开发365日、placebo275日，模型均无缺值/秩/尺度异常。新视图仅白名单，模型worker不读取evaluation视图。独立评分器无fit调用，全部48次fit先于预测全局封存，封存先于评价标签打开，评分后预测/参数/config仍字节一致。\n\n"
    validation_md+='48组输出指标用已评分日视图独立核对RMSE/MAE/PBIAS/相对增益，误差0；没有再次真实拟合、重新bootstrap或加入新模型。所有16个预定对照×circular/noncircular×30/60日×逐年/宏平均共有256行CI记录，固定seed/10000次。\n\n'
    validation_md+=f"150个定向历史保护文件未变；复用S0/S0.1/R0记录，没有全面重扫2398个历史文件或大型模型/图。输入仅已授权日数据CSV，旧R1参考预测未作为新数值输入；Own-Past未执行。\n\n"
    validation_md+='三张图PDF/SVG/600dpi PNG完成，源代码、渲染轴对齐、5pt字形下限和最终PDF碰撞均通过。逐面板与整图人工检查：placebo三年共用纵轴并保留全部13点；gain图分隔Past-only/Same-day/F2并使用同一条件CI定义；残差图完整展示三个年份365日，包含不利洪峰，无删点、平滑或择优绘制。\n\n'
    validation_md+='PDF碰撞工具原环境缺PyMuPDF，已仅在新R1目录隔离安装PyMuPDF 1.28.2用于QA；未修改数值.venv或历史依赖。Python绘图后处理代码独立登记哈希，未变更预拟合冻结的执行器。API/过程隔离不是对抗性OS沙箱，可信CSV拆分层能接触原始行字符串；旧年份暴露和人为绕过风险不被升级为零泄漏证明。\n\n'
    validation_md+='可复现顺序：项目.venv Python -B依次执行test_executor.py、preflight.py、fit_predict.py、score_results.py；绘图与报告随后执行。preflight/fit/score有已运行保护，在当前交付目录不允许自动覆盖重跑；将来若需复现须另行批准并使用新输出目录及同一冻结代码/config/环境，不覆盖本轮。\n\n'
    validation_md+='[机读验证](../experiments/s1a_r1/delivery_validation.json)、[完整数据角色台账](../experiments/s1a_r1/data_role_ledger.json)、[图形QA](../experiments/s1a_r1/figure_qa_summary.json)、[完整性](../experiments/s1a_r1/s1a_r1_integrity_report.json)。\n\n本阶段已停止，未开启下一轮研究。\n'
    (REPORTS/'vhs_next_s1a_r1_validation_report.md').write_text(validation_md,'utf-8')
    status={'S1A_R1_COMPLETE':True,'S1A_R1_REAL_RETROSPECTIVE_EVALUATION_EXECUTED':True,
        'S1A_R1_PROTOCOL_CONFLICT_FOUND':False,'S1A_R1_PREDICTIONS_FROZEN_BEFORE_SCORING':True,
        'S1A_R1_MAIN_PRACTICAL_RULE_PASS':summary['main_practical_pass'],
        'MAIN_DEVELOPMENT_GAIN_SUPPORTED':False,'L1_STABLE_THREE_YEAR_GAIN_SUPPORTED':False,
        'L1_YEAR_SPECIFIC_GAIN_1983':True,'L2_SYNCHRONIZATION_SENSITIVITY_ESTABLISHED':False,
        'TRANSPORT_INTERPRETATION_NOT_ESTABLISHED':True,'STRICT_ZERO_SHOT':False,
        'INDEPENDENT_FINAL_TEST':False,'CAUSAL_TRANSPORT_IDENTIFIED':False,
        'TIMESTAMP_CONVENTION_UNVERIFIED':True,'OWN_PAST_EXECUTED':False,
        'HISTORICAL_RESULTS_CHANGED':False,'GPU_TASKS_RUN':False,'E5I1_EXECUTED':False,
        'UNREGISTERED_MODEL_SEARCH_RUN':False,'STOPPED_AFTER_S1A_R1':True}
    (REPORTS/'vhs_next_s1a_r1_status.txt').write_text('EVIDENCE_LEVEL=PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS\n'+
        '\n'.join(f'{k}={str(v).lower()}' for k,v in status.items())+'\n','utf-8')
    # This is delivery provenance, separate from the immutable pre-fit execution seal.
    files=[p for p in HERE.iterdir() if p.is_file() and p.name!='delivery_manifest.json']
    files+=list((HERE/'views').glob('*.csv'))+list(REPORTS.glob('vhs_next_s1a_r1_*'))
    dump(HERE/'delivery_manifest.json',{p.relative_to(ROOT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in files})
    print({'delivery_validation':'PASS','main_practical_rule_pass':summary['main_practical_pass'],
           'historical_unchanged':before['files'],'numeric_audit_groups':len(metric_rows)})

if __name__=='__main__': main()
