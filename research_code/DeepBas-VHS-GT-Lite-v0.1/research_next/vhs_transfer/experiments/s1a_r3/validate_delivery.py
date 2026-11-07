"""Post-score independent checks, then bounded artifact sealing; no model fit."""
from common import *
import ast
def main():
    m=verify_inputs();seal=load(H/'prediction_freeze.json')
    for p,v in seal['files'].items():assert sha(ROOT/p)==v
    events=[json.loads(x) for x in (H/'execution_events.jsonl').read_text(encoding='utf-8').splitlines()]
    started=[i for i,x in enumerate(events) if x['event']=='FIT_STARTED'];freeze=next(i for i,x in enumerate(events) if x['event']=='ALL_PREDICTIONS_FROZEN');opened=next(i for i,x in enumerate(events) if x['event']=='EVALUATION_LABELS_OPENED');assert len(started)==6 and max(started)<freeze<opened and all(not x.get('development_labels_opened',False) for x in events[:opened])
    predictions=read(H/(P+'predictions.csv'));sw=read(H/(P+'year_swap_predictions.csv'));assert len(predictions)==4380 and len(sw)==6030
    old=read(R1/'s1a_r1_predictions.csv');obs={(int(r['fold']),r['date']):float(r['observed']) for r in read(R1/'scored_daily_view.csv') if r['comparison']=='past_only'}
    pars={(r['fold'],r['model']):r for r in load(H/'fitted_parameters.json')};up,p,t=feature_sources();errors=[];metrics=read(H/(P+'fold_metrics.csv'));cg=read(H/(P+'conditional_gain.csv'));ss=read(H/(P+'exante_strata.csv'))
    for yr in (1981,1982,1983):
        d=days(f'{yr}-01-01',f'{yr}-12-31');train=days('1978-01-31',f'{yr-1}-12-31');y=np.array([obs[yr,str(z)] for z in d]);allpred={}
        for model in ('M0','M1','M2','M3'):
            rr=[r for r in predictions if int(r['fold'])==yr and r['model']==model];assert [r['date'] for r in rr]==[str(x) for x in d];a=np.array([float(r['prediction']) for r in rr]);allpred[model]=a;e=a-y
            mm=next(r for r in metrics if int(r['fold'])==yr and r['model']==model)
            check(np.sqrt(np.mean(e**2)),float(mm['RMSE']));check(np.mean(abs(e)),float(mm['MAE']));check(e.sum(),float(mm['numeric_annual_sum_error']));check(100*e.sum()/y.sum(),float(mm['PBIAS']));check(1-(e@e)/np.sum((y-y.mean())**2),float(mm['NSE']))
            if model in ('M0','M1'):
                oldrows=[r for r in old if int(r['fold'])==yr and r['comparison']=='past_only'];check(a,[float(r['q_baseline' if model=='M0' else 'q_prediction']) for r in oldrows])
            else:
                par=pars[yr,model];cl=np.array(par['met_monthly_climate']);scale=np.array(par['met_scale']);met=(np.column_stack([windows(p,d,(7,)),windows(t,d,(7,))])-cl[months(d)])/scale
                q=(windows(up,d,(1,7,30))-np.array(par['upstream_monthly_climate'])[months(d)])/np.array(par['upstream_scale']);x=met if model=='M2' else np.column_stack([met,q]);raw=np.array(par['target_climate'])[months(d)]+x@np.array(par['beta']);check(a,np.maximum(raw,0));errors.append(float(max(abs(a-np.maximum(raw,0)))))
        state=np.array([r['exante_state'] for r in predictions if int(r['fold'])==yr and r['model']=='M0']);threshold=np.quantile([up[str(x-np.timedelta64(1,'D'))] for x in train],[.2,.9]);u=np.array([up[str(x-np.timedelta64(1,'D'))] for x in d]);expected=np.where(u<=threshold[0],'LOW',np.where(u>=threshold[1],'HIGH','MID'));assert np.array_equal(state,expected)
        for aug,base in load(H/(P+'frozen_protocol.json'))['comparisons']:
            comp=aug+'_vs_'+base;metric=next(r for r in cg if int(r['fold'])==yr and r['comparison']==comp);ds=float(np.sum((allpred[base]-y)**2-(allpred[aug]-y)**2));check(ds,float(metric['DeltaSSE']));check(ds,float(metric['DeltaSSE_between'])+float(metric['DeltaSSE_within']));group=[r for r in ss if int(r['fold'])==yr and r['comparison']==comp];assert sum(int(r['n']) for r in group)==365;check(ds,sum(float(r['DeltaSSE']) for r in group))
        par=pars[yr,'M3'];cd=d[30:];met=(np.column_stack([windows(p,cd,(7,)),windows(t,cd,(7,))])-np.array(par['met_monthly_climate'])[months(cd)])/np.array(par['met_scale'])
        for donor in range(1978,1984):
            rr=[r for r in sw if int(r['fold'])==yr and int(r['donor'])==donor];assert len(rr)==335 and [r['date'] for r in rr]==[str(x) for x in cd]
            anchors=np.array([str(donor)+str(x)[4:] for x in cd],dtype='datetime64[D]');assert [r['donor_anchor'] for r in rr]==[str(x) for x in anchors]
            q=(windows(up,anchors,(1,7,30))-np.array(par['upstream_monthly_climate'])[months(anchors)])/np.array(par['upstream_scale']);raw=np.array(par['target_climate'])[months(cd)]+np.column_stack([met,q])@np.array(par['beta']);check(np.maximum(raw,0),[float(r['prediction']) for r in rr]);check(allpred['M2'][30:],[float(r['M2_prediction']) for r in rr]);assert [r['exante_state'] for r in rr]==list(state[30:])
    diagnostics=read(H/'feature_diagnostics.csv');assert len(diagnostics)==6
    bs=read(H/(P+'bootstrap_summary.csv'));assert len(bs)==256 and {r['circular'] for r in bs}=={'True','False'}
    for r in bs:assert float(r['gain_lower'])<=float(r['gain_upper']) and int(r['replicates'])==10000
    for f in ('score_results.py','build_reports.py','validate_delivery.py'):
        tree=ast.parse((H/f).read_text(encoding='utf-8'));calls=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '' for n in ast.walk(tree) if isinstance(n,ast.Call)];assert not {'pinv','fit','fit_model','lstsq','ols'}.intersection(calls)
    verify_inputs();count=load(H/'integrity_before.json')['files'];report=dict(status='PASS',R3_DATA_GATE='PASS',R3_CONDITIONAL_ANALYSIS_COMPLETE=True,NEW_BLIND_TEST_PERFORMED=False,STRICT_ZERO_SHOT_CLAIM=False,HISTORICAL_FILES_CHANGED=False,protected_files=count,changed_files=[],real_OLS_fits=6,M0_M1_refits=0,main_rows=4380,main_model_years=12,swap_rows=6030,swap_arms=18,bootstrap_rows=256,all_predictions_before_evaluation=True,max_replay_abs=max(errors),all_donors_and_years_retained=True,source_and_execution_hashes_unchanged=True)
    dump('delivery_validation.json',report)
    txt=f'''# VHS-NEXT-S1A-R3｜验证报告

身份：{IDENTITY}。执行/来源/数值验证PASS不同于稳定科学增量得到确认。

数据门槛PASS：实际NetCDF2191日、P/T变量定义、单位、UTC边界、增量流域、175项面积权重、保存日网格P/T加权重现、S0来源SHA均核对；无目标Q进入所检查强迫生成链。没有重跑原始下载或大规模历史审计。P7固定7日平均与旧P_inc_7d总和差异在fit前明确报告，未更换窗口。

全部{count}个定向历史/来源保护文件执行前后SHA一致。S0/S0.1/R0/R1/R2、E4/E5及论文清单内冻结项未改；M0/M1逐日期复用原预测，未重新拟合。R3公式/输入/日期/环境及全部脚本哈希在fit前冻结。

4项CPU人工合成检查通过。每折M2/M3共同train=1066/1431/1796日、dev365日，训练月均/尺度、满秩2/5及最晚t−1检查通过。气象均值/尺度仅训练，Q尺度及目标月均原样复用R1。无截距、ridge、窗口、lag、谐波搜索。6次真实OLS事件先于全局预测封存，封存先于独立评分器打开标签；评分后0次fit。4380行主预测和6030行swap预测参数/预测SHA保持不变。

独立复核12组RMSE/MAE/NSE/PBIAS/年数值和误差、12个配对DeltaSSE与状态分层加总、块SSE守恒。主预测冻结参数重建最大绝对差{max(errors):.3g}；18组335日swap全部重建，目标P7/T7和M2参照不变、真实mask不变、month-day正确、各donor同参同日。未遗漏1981/1982不利结果或1980donor，未跨365/335日排名。

30日块Jan1锚定、年末5日，cross-term容差1e−10+1e−12*SSE；between+within严格加总。全部四对照的10000次30/60日circular/noncircular条件bootstrap共256行，固定seed；无p值、无2%确认性标准。估计条件数/SVD/VIF/beta全部报告，无因诊断值修改模型。

评分/报告/验证源码AST无fit/pinv/OLS调用，模型worker不导入评分器、不读取开发目标视图。角色边界为可检查的进程/代码隔离，不是对抗性OS沙箱；历史标签先前已暴露的事实保留。新增写入仅R3及命名R3报告，未写原始数据目录、未运行旧finalizer/模型/GPU任务。

未生成图件不影响要求的CSV/报告交付；所有指定文件均实际生成，没有空文件冒充成功。全部可复现中间参数、台账、事件、源码、配置、环境及SHA在R3目录。顺序preflight→fit_predict→score_results→build_reports→validate_delivery；预检查/拟合/评分都有一次执行保护，禁止在封存目录自动覆盖重跑，独立复现需新目录和后续授权。

R3结束即停止，不开展GNN/Muskingum/lag搜索/S1B/S1C/GPU/E5I1。

`R3_DATA_GATE=PASS`

`R3_CONDITIONAL_ANALYSIS_COMPLETE=true`

`NEW_BLIND_TEST_PERFORMED=false`

`STRICT_ZERO_SHOT_CLAIM=false`

`HISTORICAL_FILES_CHANGED=false`
'''
    (REPORTS/(P+'validation_report.md')).write_text(txt,encoding='utf-8')
    (REPORTS/(P+'status.txt')).write_text('VHS-NEXT-S1A-R3 COMPLETE_STOPPED\nR3_DATA_GATE=PASS\nR3_CONDITIONAL_ANALYSIS_COMPLETE=true\nNEW_BLIND_TEST_PERFORMED=false\nSTRICT_ZERO_SHOT_CLAIM=false\nHISTORICAL_FILES_CHANGED=false\nREAL_OLS_FITS=6\nAWAITING_NEXT_USER_AUTHORIZATION=true\n',encoding='utf-8')
    files=[p for p in H.glob('*') if p.is_file() and p.name!='delivery_manifest.json']+[REPORTS/(P+n) for n in ('forcing_lineage.md','results.md','limitations.md','validation_report.md','status.txt')]
    dump('delivery_manifest.json',{p.relative_to(ROOT).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)})
    print(report)
if __name__=='__main__':main()
