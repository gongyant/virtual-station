"""Independent scorer. Prediction and parameter seals are verified before labels open.

No fit_model or fit_same_day import/call; no prediction or parameter writes.
"""
import numpy as np
from common import *
from data_roles import evaluation_views
from methods_v2 import positions, score, block_indices, primary_decision

def bootstrap(years,block,circular):
    rng=np.random.default_rng(20261011); gs=[]; ns=[]; annual=[]
    for d,y,p0,p1 in years:
        idx=block_indices(d,block,10000,rng,circular=circular)
        r0=np.sqrt(np.mean((p0[idx]-y[idx])**2,axis=1))
        r1=np.sqrt(np.mean((p1[idx]-y[idx])**2,axis=1))
        if np.any(r0==0): raise ValueError('Zero bootstrap baseline RMSE')
        g=(r0-r1)/r0
        yy=y[idx]; sst=np.sum((yy-yy.mean(axis=1)[:,None])**2,axis=1)
        dn=len(d)*(r0*r0-r1*r1)/sst if np.all(sst>0) else None
        gs.append(g); ns.append(dn)
        point0=np.sqrt(np.mean((p0-y)**2)); point1=np.sqrt(np.mean((p1-y)**2))
        annual.append({'scope':str(d[0])[:4],'gain_point':float(1-point1/point0),
            'gain_lower':float(np.quantile(g,0.025)),'gain_upper':float(np.quantile(g,0.975)),
            'DeltaNSE_lower':float(np.quantile(dn,0.025)) if dn is not None else None,
            'DeltaNSE_upper':float(np.quantile(dn,0.975)) if dn is not None else None})
    macro=np.mean(gs,axis=0); mn=np.mean(ns,axis=0) if all(v is not None for v in ns) else None
    annual.append({'scope':'MACRO_EQUAL_YEAR','gain_point':float(np.mean([v['gain_point'] for v in annual])),
            'gain_lower':float(np.quantile(macro,0.025)),'gain_upper':float(np.quantile(macro,0.975)),
            'DeltaNSE_lower':float(np.quantile(mn,0.025)) if mn is not None else None,
            'DeltaNSE_upper':float(np.quantile(mn,0.975)) if mn is not None else None})
    return annual

def main():
    frozen=verify_freeze()
    if (HERE/'evaluation_summary.json').exists(): raise RuntimeError('Already scored: no automatic repeat')
    views=evaluation_views() # Separate process; all global predictions are already sealed.
    rows=read_csv(HERE/'s1a_r1_predictions.csv')
    params={(p['fold'],p['comparison']):p for p in load(HERE/'fitted_parameters.json')}
    groups={}
    for r in rows: groups.setdefault((int(r['fold']),r['comparison']),[]).append(r)
    metrics=[]; daily=[]; contrasts={}; yearly_scores={}
    for (year,comparison),rr in groups.items():
        dates=np.array([r['date'] for r in rr],dtype='datetime64[D]')
        family=rr[0]['family']; k=int(rr[0]['k']); expected=views[year].dates[:-90] if family=='PLACEBO' else views[year].dates
        if not np.array_equal(dates,expected): raise ValueError('Unexpected scoring support')
        pp=params[(year,comparison)]
        p0=np.array([float(r['q_baseline']) for r in rr]); p1=np.array([float(r['q_prediction']) for r in rr])
        raw0=np.array([float(r['q_baseline_raw']) for r in rr]); raw1=np.array([float(r['q_prediction_raw']) for r in rr])
        if k<0 and rr[0]['information_role']!='NONCAUSAL_FUTURE_UPSTREAM_PLACEBO': raise ValueError('Future placebo role failure')
        y=views[year].q[positions(views[year].dates,dates)]
        m0=score(views[year],dates,p0,pp['train_low_threshold']); m1=score(views[year],dates,p1,pp['train_low_threshold'])
        if m0['RMSE']==0: raise ValueError('Undefined relative gain')
        residual=y-raw0; residual_sst=np.sum((residual-residual.mean())**2)
        record={'fold':year,'comparison':comparison,'family':family,'k':k,'information_role':rr[0]['information_role'],
            'fit_start':pp['fit_start'],'fit_end':pp['fit_end'],'fit_n':pp['fit_n'],
            'score_start':str(dates[0]),'score_end':str(dates[-1]),'score_n':len(dates),
            'peak_scope':'PARTIAL_YEAR_COMMON_MASK' if family=='PLACEBO' else 'FULL_YEAR',
            'relative_RMSE_gain':float((m0['RMSE']-m1['RMSE'])/m0['RMSE']),
            'DeltaNSE':m1['NSE']-m0['NSE'] if m1['NSE'] is not None and m0['NSE'] is not None else None,
            'abs_PBIAS_worsening_pp':abs(m1['PBIAS'])-abs(m0['PBIAS']) if m0['PBIAS'] is not None and m1['PBIAS'] is not None else None,
            'low_RMSE_relative_change':m1['low_RMSE']/m0['low_RMSE']-1 if m0['low_RMSE'] not in (None,0) and m1['low_RMSE'] is not None else None,
            'baseline_clip_count':int(np.sum(raw0<0)),'augmented_clip_count':int(np.sum(raw1<0)),
            'baseline_clip_rate':float(np.mean(raw0<0)),'augmented_clip_rate':float(np.mean(raw1<0)),
            'baseline_clip_delta_sum':float(np.sum(p0-raw0)),'augmented_clip_delta_sum':float(np.sum(p1-raw1)),
            'unclipped_augmented_RMSE':float(np.sqrt(np.mean((raw1-y)**2))),
            'residual_SSE':float(np.sum((p1-y)**2)),
            'residual_R2':float(1-np.sum((p1-y)**2)/residual_sst) if residual_sst>0 else None}
        for prefix,m in (('baseline',m0),('augmented',m1)):
            for key,value in m.items(): record[prefix+'_'+key]=json.dumps(value) if isinstance(value,dict) else value
        metrics.append(record)
        contrasts.setdefault(comparison,[]).append((dates,y,p0,p1))
        yearly_scores.setdefault(comparison,[]).append((m0,m1))
        for i,d in enumerate(dates):
            daily.append({'fold':year,'comparison':comparison,'date':str(d),'observed':float(y[i]),
                'baseline':float(p0[i]),'augmented':float(p1[i]),'training_calendar':float(raw0[i]),
                'observed_anomaly':float(residual[i]),'predicted_anomaly':float(p1[i]-raw0[i])})
        event('SCORE_COMPLETE',fold=year,comparison=comparison,score_start=str(dates[0]),score_end=str(dates[-1]),score_n=len(dates),
              label_role='evaluation only; predictions and parameters immutable',
              prediction_freeze_sha256=sha(HERE/'prediction_freeze.json'),code_hashes=frozen['frozen_hashes'])
    for year in (1981,1982,1983):
        kk=[r for r in metrics if r['fold']==year and r['family']=='PLACEBO']
        if len(kk)!=13 or len({(r['score_start'],r['score_end'],r['score_n'],r['fit_start'],r['fit_end'],r['fit_n']) for r in kk})!=1:
            raise ValueError('Placebo fit/score masks differ')
        comparisons=[groups[(year,r['comparison'])] for r in kk]
        if any([r['q_baseline'] for r in g]!=[r['q_baseline'] for r in comparisons[0]] for g in comparisons[1:]):
            raise ValueError('Placebo baselines differ')
    write_csv(HERE/'s1a_r1_fold_metrics.csv',[r for r in metrics if r['family'] in ('PAST_ONLY','SAME_DAY')])
    write_csv(HERE/'s1a_r1_placebo_metrics.csv',[r for r in metrics if r['family']=='PLACEBO'])
    write_csv(HERE/'s1a_r1_f2_sensitivity.csv',[r for r in metrics if r['family']=='F2'])
    write_csv(HERE/'scored_daily_view.csv',daily)
    boot=[]
    for comparison,years in contrasts.items():
        for circular in (True,False):
            for block in (30,60):
                result=bootstrap(years,block,circular)
                boot.extend({'comparison':comparison,'circular':circular,'block_days':block,'replicates':10000,'seed':20261011,**r} for r in result)
        print('Bootstrap complete: '+comparison,flush=True)
    write_csv(HERE/'s1a_r1_bootstrap_summary.csv',boot)
    summary={}
    for comparison,ss in yearly_scores.items():
        ci=[]
        for block in (30,60):
            b=next(r for r in boot if r['comparison']==comparison and r['circular'] and r['block_days']==block and r['scope']=='MACRO_EQUAL_YEAR')
            ci.append([b['gain_lower'],b['gain_upper']])
        decision=primary_decision([a for a,b in ss],[b for a,b in ss],*ci)
        summary[comparison]={'decision':decision,'macro_metrics':{
             'baseline_RMSE':float(np.mean([a['RMSE'] for a,b in ss])),
             'augmented_RMSE':float(np.mean([b['RMSE'] for a,b in ss])),
             'DeltaNSE':float(np.mean([b['NSE']-a['NSE'] for a,b in ss]))},
             'annual_scores':[{'baseline':a,'augmented':b} for a,b in ss]}
    prediction_seal=load(HERE/'prediction_freeze.json')
    for k,v in prediction_seal['files'].items():
        if sha(ROOT/k)!=v: raise RuntimeError('Scorer modified a frozen prediction/parameter/view record')
    dump(HERE/'evaluation_summary.json',{'phase':'VHS-NEXT-S1A-R1','identity':'PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS',
        'comparisons':summary,'no_overall_p_values':True,'conditional_CI_only':True,
        'main_practical_pass':summary['past_only']['decision']['decision']=='CONSISTENT_DEVELOPMENT_GAIN' and
                              summary['past_only']['decision']['robust_usefulness']=='NO_PRESET_COST_EXCEEDANCE'},exclusive=True)
    event('ALL_EVALUATION_COMPLETE',metrics=len(metrics),bootstrap_rows=len(boot),fits_after_score=0,
          prediction_seal_unchanged=True)
    print({'scored_contrasts':len(contrasts),'metrics_rows':len(metrics),'bootstrap_rows':len(boot),
           'past_only_decision':summary['past_only']['decision']})

if __name__=='__main__': main()
