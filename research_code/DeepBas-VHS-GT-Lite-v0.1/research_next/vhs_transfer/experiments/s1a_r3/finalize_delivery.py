"""Transparent post-score repair audit and final R3 sealing; no estimation or resampling."""
from common import *
import ast
def main():
    verify_inputs();validation=load(H/'delivery_validation.json');assert validation['status']=='PASS'
    for name,code,key in [('scoring_repair_manifest.json','score_results_v2.py','repaired_code_sha256'),('validation_repair_manifest.json','validate_delivery_v2.py','repaired_validator_sha256')]:
        assert sha(H/code)==load(H/name)[key]
    for p,v in load(H/'prediction_freeze.json')['files'].items():assert sha(ROOT/p)==v
    original=(H/'score_results.py').read_text(encoding='utf-8');repaired=(H/'score_results_v2.py').read_text(encoding='utf-8')
    expected=original.replace("DeltaNSE=m1['NSE']-m0['NSE']", "DeltaNSE=(m1['NSE']-m0['NSE']) if m1['NSE'] is not None and m0['NSE'] is not None else None").replace("if (H/'scoring_started.json').exists():raise RuntimeError('Scoring already started; no automatic repeat')", "if (H/'scoring_resumed.json').exists() or (H/'scoring_complete.json').exists():raise RuntimeError('Scoring repair already started; no repeat')").replace("dump('scoring_started.json',dict(prediction_freeze_sha256=sha(H/'prediction_freeze.json')))", "dump('scoring_resumed.json',dict(prediction_freeze_sha256=sha(H/'prediction_freeze.json'),repair_manifest_sha256=sha(H/'scoring_repair_manifest.json')))")
    assert expected==repaired
    bootstrap=read(H/(P+'bootstrap_summary.csv'));assert len(bootstrap)==64 and validation['bootstrap_rows']==64
    monthly=read(H/(P+'monthly_metrics.csv'));jan=[r for r in monthly if r['support']=='YEAR_SWAP_335' and r['month']=='1'];assert len(jan)==18 and all(r['n']=='1' and r['DeltaNSE']=='' for r in jan)
    up,p,t=feature_sources();parameters=load(H/'fitted_parameters.json');normal=[]
    for par in parameters:
        yr=par['fold'];tr=days('1978-01-31',f'{yr-1}-12-31');labels=np.array([float(r['Q_target_dsk']) for r in read(R1/f'views/fit_labels_F{yr}.csv')]);base=np.array(par['target_climate'])[months(tr)];raw=np.column_stack([windows(p,tr,(7,)),windows(t,tr,(7,))]);cl=np.stack([raw[months(tr)==m].mean(axis=0) for m in range(12)]);anomaly=raw-cl[months(tr)];scale=anomaly.std(axis=0);check(cl,par['met_monthly_climate']);check(scale,par['met_scale']);x=anomaly/scale
        if par['model']=='M3':x=np.column_stack([x,(windows(up,tr,(1,7,30))-np.array(par['upstream_monthly_climate'])[months(tr)])/np.array(par['upstream_scale'])])
        residual=labels-base;grad=x.T@(residual-x@np.array(par['beta']));ratio=float(np.linalg.norm(grad)/(np.linalg.norm(x)*np.linalg.norm(residual)));assert ratio<1e-12;normal.append(dict(fold=yr,model=par['model'],relative_normal_equation_residual=ratio))
    # Independently recompute every swap metric from already sealed predictions and original evaluation labels.
    obs={(int(r['fold']),r['date']):float(r['observed']) for r in read(R1/'scored_daily_view.csv') if r['comparison']=='past_only'}
    predictions=read(H/(P+'year_swap_predictions.csv'));metrics=read(H/(P+'year_swap_metrics.csv'));strata=read(H/(P+'year_swap_strata.csv'))
    for m in metrics:
        rr=[r for r in predictions if r['fold']==m['fold'] and r['donor']==m['donor']];y=np.array([obs[int(r['fold']),r['date']] for r in rr]);b=np.array([float(r['M2_prediction']) for r in rr]);a=np.array([float(r['prediction']) for r in rr]);delta=(b-y)**2-(a-y)**2;check(delta.sum(),float(m['DeltaSSE']));check(np.sqrt(np.mean((a-y)**2)),float(m['RMSE1']));sg=[r for r in strata if r['fold']==m['fold'] and r['donor']==m['donor']];assert sum(int(r['n']) for r in sg)==335;check(delta.sum(),sum(float(r['DeltaSSE']) for r in sg));check(delta.sum(),float(m['DeltaSSE_between'])+float(m['DeltaSSE_within']))
    # Add model-level equal-year means, never pooled or treated as independent replicates.
    fm=read(H/(P+'fold_metrics.csv'));macro=[]
    for model in ('M0','M1','M2','M3'):
        rr=[r for r in fm if r['model']==model];macro.append(dict(model=model,scope='MACRO_EQUAL_YEAR',identity=IDENTITY)|{key:float(np.mean([float(r[key]) for r in rr])) for key in ('RMSE','MAE','NSE','Bias','PBIAS','SSE','numeric_annual_sum_error','raw_RMSE','clip_rate')})
    write(P+'model_macro_metrics.csv',macro)
    errortext='''

## 执行问题与透明修正记录

首次评分在year-swap的1月单日单元（Jan31）遇到NSE未定义，原评分器对None作减法而停止；没有输出完整评分、没有改动或重新拟合模型。保留原冻结score_results.py及原scoring_started标记，另存score_results_v2.py，仅将未定义DeltaNSE设NA，并使用独立一次恢复标记。修正版SHA在执行前记录于scoring_repair_manifest.json；全部预测与原执行代码SHA仍保持不变。该单日单元其他误差指标可定义，日期没有删除。

首次交付校验误沿用R1的256行bootstrap期待值，R3实际只有4对照×4种block/circular模式×4个年度/宏平均scope=64行。数据输出正确，不重采样。保留原冻结validate_delivery.py，修正版validate_delivery_v2.py把断言、报告和机读计数统一为实际64行，独立哈希见validation_repair_manifest.json。两处均为评分/交付边界实现错误，不是数据缺失、泄漏、秩或模型准入异常；修正后没有继续拟合（新增fit=0），不改变模型、窗口、参数、日期或评价定义。

最终额外检查：逐项代码差异限定NA处理/恢复标记；18条Jan31交换单元n=1、DeltaNSE=NA保留；6套参数训练正态方程残差与训练气象中心/尺度复核；18组swap的RMSE/DeltaSSE/状态加总独立复核。复现应使用冻结原执行器加两份明确版本的评分/验证修正，不覆盖原冻结源码。
'''
    vp=REPORTS/(P+'validation_report.md');text=vp.read_text(encoding='utf-8');text=text.replace('顺序preflight→fit_predict→score_results→build_reports→validate_delivery','最终顺序preflight→fit_predict→score_results_v2（保留原中断记录）→build_reports→validate_delivery_v2→finalize_delivery');text+=errortext
    footer='\n`R3_DATA_GATE=PASS`\n\n`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`\n\n`NEW_BLIND_TEST_PERFORMED=false`\n\n`STRICT_ZERO_SHOT_CLAIM=false`\n\n`HISTORICAL_FILES_CHANGED=false`\n\n完成并停止，等待下一次批准。\n'
    vp.write_text(text+footer,encoding='utf-8')
    rp=REPORTS/(P+'results.md');text=rp.read_text(encoding='utf-8');text+='''

## 解释核对与执行说明

指定P7/T7相对Monthly-only为−4.775%/−4.177%/+2.586%，宏平均−2.122%，没有跨年稳定的季节外气象收益。气象条件化后上游增量为−9.607%/−1.171%/+6.139%，宏平均−1.546%；全部30/60日circular/noncircular宏平均区间跨0。1981两种块误差均恶化；1982损失几乎全部来自between；1983 between改善80959.61被within恶化5629.61部分抵消。

注意条件LOW收益的对照分母：M3相对M2在LOW改善36.85%/24.13%/29.82%，但M2的LOW基线误差较高，M3相对旧M1的LOW RMSE反而恶化11.79%/0.39%/0.88%。不能把较弱M2对照下的较大百分比当成超过原上游模型的低状态进步。

条件数约1.10–4.05，VIF约1.01–4.25，没有触发数值共线警示；但M3温度系数跨折−1.311/−0.232/+1.076，降水系数8.020/5.033/0.137变化明显。满秩和小VIF不保证跨年系数稳定，更不能把符号解释为气温物理过程。

气象固定后真实上游年度swap名次仍为6/6、5/6、1/6；1983局部线索保留而非跨年复现。由于指定气象控制本身并不充分且预测效用不稳定，不能部分排除所有共同气象驱动；只能限定所测P7/T7线性表示下的条件结果。

执行发生单日月份NSE的NA处理错误及校验器bootstrap行数错误，原脚本保留，明确版本修正后完成评分/验证，全部封存预测未变，没有再次拟合。详见validation_report执行问题记录及两个repair_manifest。全部指定交付文件均生成，附加model_macro_metrics.csv提供四模型各指标三年等权均值。
''';rp.write_text(text+footer,encoding='utf-8')
    validation.update(bootstrap_rows=64,post_freeze_scoring_repair_disclosed=True,post_freeze_validation_repair_disclosed=True,additional_real_fits_after_repair=0,normal_equation_checks=normal,swap_metric_checks=18,one_day_month_cells_preserved=18)
    dump('delivery_validation.json',validation);verify_inputs()
    files=[p for p in H.glob('*') if p.is_file() and p.name!='delivery_manifest.json']+[REPORTS/(P+n) for n in ('forcing_lineage.md','results.md','limitations.md','validation_report.md','status.txt')]
    dump('delivery_manifest.json',{p.relative_to(ROOT).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)})
    print(dict(status='COMPLETE_STOPPED',delivery_files=len(files),historical_protected=validation['protected_files'],fit_calls=6,additional_fits_after_repairs=0,bootstrap_rows=64))
if __name__=='__main__':main()
