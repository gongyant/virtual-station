"""Frozen prediction diagnostics only. No model estimation or historical executor imports."""
from pathlib import Path
from datetime import date, timedelta
import csv, json, hashlib, ast, sys
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
R1=HERE.parent/'s1a_r1'
REPORTS=ROOT/'research_next/vhs_transfer/reports'
IDENTITY='POST_HOC_EXPLORATORY_DIAGNOSTIC'
YEARS=(1981,1982,1983)
STATES=('LOW','MID','HIGH')
RTOL=1e-12
ATOL=1e-10
REPLAY_ATOL=1e-12
PREFIX='vhs_next_s1a_r2_'

def read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f: return list(csv.DictReader(f))
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def write(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/(PREFIX+name+'.csv')).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def close(a,b):
    assert np.allclose(a,b,rtol=RTOL,atol=ATOL), (a,b)
def dates(a,b):
    return np.arange(np.datetime64(a),np.datetime64(b)+np.timedelta64(1,'D'))
def month(d): return d.astype('datetime64[M]').astype(int)%12+1
def block(d): return ((d-d.astype('datetime64[Y]').astype('datetime64[D]')).astype(int)//30)
def labels(x,q):
    assert q[0]<q[1]
    z=np.where(x<=q[0],'LOW',np.where(x>=q[1],'HIGH','MID'))
    assert sum(np.sum(z==s) for s in STATES)==len(x)
    return z

def protected():
    h=load(R1/'integrity_before.json')['hashes']
    for k,v in load(R1/'delivery_manifest.json').items(): h[k]=v['sha256']
    for name,key in [('prediction_freeze.json','files'),('s1a_r1_execution_manifest.json','frozen_hashes'),('views_manifest.json','files')]:
        h.update(load(R1/name)[key])
    p=R1/'delivery_manifest.json';h[p.relative_to(ROOT).as_posix()]=sha(p)
    for k,v in h.items():
        if sha(ROOT/k)!=v: raise RuntimeError('FROZEN HASH MISMATCH: '+k)
    return h

def windows(up,anchors):
    return np.column_stack([np.array([np.mean([up[str(d-np.timedelta64(i,'D'))] for i in range(1,w+1)]) for d in anchors]) for w in (1,7,30)])
def reconstruct(up,p,target,anchors):
    if p['calendar']=='monthly': b=np.array(p['target_climate'])[month(target)-1]
    else:
        # Development target calendars are non-leap; donor leap handling belongs only to source windows.
        doy=(target-target.astype('datetime64[Y]').astype('datetime64[D]')).astype(int)
        phi=2*np.pi*doy/365
        b=np.column_stack([np.ones(len(phi)),np.sin(phi),np.cos(phi),np.sin(2*phi),np.cos(2*phi)])@np.array(p['target_climate'])
    x=(windows(up,anchors)-np.array(p['upstream_monthly_climate'])[month(anchors)-1])/np.array(p['upstream_scale'])
    return np.maximum(b,0),np.maximum(b+x@np.array(p['beta']),0)

def pair(y,b,p):
    n=len(y)
    if not n: return {k:None for k in ('RMSE0','RMSE1','MAE0','MAE1','Bias0','Bias1','SSE0','SSE1','DeltaSSE','relative_RMSE_gain','bias_MSE_contribution','variance_MSE_contribution','MSE_difference')}|{'n':0}
    e0=b-y;e1=p-y;s0=float(e0@e0);s1=float(e1@e1)
    bias=float(e0.mean()**2-e1.mean()**2);var=float(e0.var()-e1.var())
    close(s0/n-s1/n,bias+var)
    return dict(n=n,RMSE0=float(np.sqrt(s0/n)),RMSE1=float(np.sqrt(s1/n)),MAE0=float(np.mean(abs(e0))),MAE1=float(np.mean(abs(e1))),Bias0=float(e0.mean()),Bias1=float(e1.mean()),SSE0=s0,SSE1=s1,DeltaSSE=s0-s1,relative_RMSE_gain=1-np.sqrt(s1/s0) if s0 else None,bias_MSE_contribution=bias,variance_MSE_contribution=var,MSE_difference=(s0-s1)/n)

def orthogonal(d,y,b,p,meta):
    rows=[]; between=[0.,0.];within=[0.,0.]
    for k in np.unique(block(d)):
        mask=block(d)==k; errors=[(b-y)[mask],(p-y)[mask]]
        r=meta|dict(block=int(k),start=str(d[mask][0]),end=str(d[mask][-1]),n=int(mask.sum()))
        for j,e in enumerate(errors):
            be=float(len(e)*e.mean()**2);wi=float(np.sum((e-e.mean())**2));cross=float(2*e.mean()*np.sum(e-e.mean()))
            close(float(e@e),be+wi)
            assert abs(cross)<=ATOL+RTOL*float(e@e), (cross,float(e@e))
            r.update({f'SSE_between{j}':be,f'SSE_within{j}':wi,f'cross_term{j}':cross,f'Bias{j}':float(e.mean())})
            between[j]+=be;within[j]+=wi
        r['DeltaSSE_between']=r['SSE_between0']-r['SSE_between1'];r['DeltaSSE_within']=r['SSE_within0']-r['SSE_within1']
        rows.append(r)
    close(pair(y,b,p)['DeltaSSE'],between[0]-between[1]+within[0]-within[1])
    return rows,dict(SSE_between0=between[0],SSE_between1=between[1],SSE_within0=within[0],SSE_within1=within[1],DeltaSSE_between=between[0]-between[1],DeltaSSE_within=within[0]-within[1])

def stratify(y,b,p,groups,meta):
    annual=pair(y,b,p)['DeltaSSE'];delta=(b-y)**2-(p-y)**2;absolute=float(np.sum(abs(delta)))
    stable=abs(annual)>max(ATOL,0.01*absolute)
    rows=[]
    for kind,z in groups.items():
        total=0
        for state in STATES:
            mask=z==state; m=pair(y[mask],b[mask],p[mask]);v=m['DeltaSSE'] or 0.;total+=v
            rows.append(meta|dict(grouping=kind,stratum=state,conditioning='OUTCOME_CONDITIONED_POST_HOC' if kind=='outcome' else 'KNOWN_UPSTREAM_STATE_POST_HOC',small_cell=m['n']<10,annual_DeltaSSE=annual,total_absolute_daily_contribution=absolute,annual_signed_share=v/annual if stable else None,annual_share_suppressed=not stable,share_of_total_absolute_contribution=v/absolute if absolute else None)|m)
        close(total,annual)
    return rows

def influence(d,y,b,p,groups,meta):
    delta=(b-y)**2-(p-y)**2;absolute=abs(delta);order=np.argsort(-absolute,kind='stable');annual=float(delta.sum());den=float(absolute.sum())
    neff=den**2/float(delta@delta) if np.any(delta) else None
    common=meta|dict(annual_DeltaSSE=annual,positive_total=float(delta[delta>0].sum()),negative_total=float(delta[delta<0].sum()),total_absolute=den,N_eff_contribution_days=neff)
    out=[]
    for n in (5,10,20):
        ix=order[:n];out.append(common|dict(record='top_summary',top_n=n,DeltaSSE=float(delta[ix].sum()),absolute_share=float(absolute[ix].sum()/den) if den else None))
    for rank,i in enumerate(order[:20],1):
        out.append(common|dict(record='top_day',rank=rank,date=str(d[i]),month=int(month(d)[i]),observed=float(y[i]),baseline=float(b[i]),augmented=float(p[i]),outcome=groups['outcome'][i],exante=groups['exante'][i],DeltaSSE=float(delta[i]),contribution_sign=int(np.sign(delta[i])),absolute_share=float(absolute[i]/den) if den else None))
    for k in np.unique(block(d)):
        ix=block(d)==k;remaining=float(delta[~ix].sum())
        out.append(common|dict(record='leave_one_block_out',block=int(k),start=str(d[ix][0]),end=str(d[ix][-1]),removed_n=int(ix.sum()),removed_DeltaSSE=float(delta[ix].sum()),remaining_DeltaSSE=remaining,sign_changed=bool(np.sign(remaining)!=np.sign(annual))))
    return out

def monthly(d,y,b,p,groups,meta):
    rows=[]
    for kind,z in groups.items():
        for m in range(1,13):
            for state in STATES:
                ix=(month(d)==m)&(z==state);v=pair(y[ix],b[ix],p[ix])
                rows.append(meta|dict(grouping=kind,stratum=state,month=m,small_cell=v['n']<10)|v)
    return rows

def synthetic_tests():
    y=np.array([1.,2.,3.,4.]);b=np.array([1.,3.,2.,7.]);p=np.array([2.,2.,4.,5.])
    close(pair(y,b,p)['MSE_difference'],2.)
    assert labels(np.array([1.,2.,3.,4.]),[2.,3.]).tolist()==['LOW','LOW','HIGH','HIGH']
    d=dates('1981-01-29','1981-02-01');_,m=orthogonal(d,y,b,p,{})
    close(m['DeltaSSE_between']+m['DeltaSSE_within'],8.)
    a=np.array(['1980'+str(x)[4:] for x in dates('1981-02-28','1981-03-01')],dtype='datetime64[D]')
    assert str(a[1])=='1980-03-01' and (a[1]-a[0]).astype(int)==2
    assert str(a[1]-np.timedelta64(1,'D'))=='1980-02-29'
    assert len(dates('1981-01-31','1981-12-31'))==335
    return ['bias_variance_identity','threshold_boundaries_partition','calendar_block_identity','leap_month_day_window','common_support_count']

def main():
    if (HERE/'analysis_complete.json').exists(): raise RuntimeError('Completed diagnostics are sealed; no automatic overwrite')
    # Verify every inherited listed digest before reading numerical values.
    h=protected();dump('integrity_before.json',dict(files=len(h),hashes=h))
    dump('diagnostic_contract.json',dict(identity=IDENTITY,fit_calls=0,year_swap_support='Jan31-Dec31,335',main_support=365,displacement_support=275,donors=list(range(1978,1984)),block_days=30,block_origin='Jan1',small_cell_n_less_than=10,rtol=RTOL,atol=ATOL,replay_rtol=RTOL,replay_atol=REPLAY_ATOL,annual_share_guard='abs(annual DeltaSSE) <= max(1e-10, .01 * sum abs daily DeltaSSE)',thresholds='train-only Q20/Q90; same real-aligned masks for all controls',new_models=False))
    tests=synthetic_tests()
    up={r['date']:float(r['Q_input_byblk']) for r in read(R1/'views/feature_view.csv')}
    params={(r['fold'],r['comparison']):r for r in load(R1/'fitted_parameters.json')}
    pred={};scored={}
    for r in read(R1/'s1a_r1_predictions.csv'): pred.setdefault((int(r['fold']),r['comparison']),[]).append(r)
    for r in read(R1/'scored_daily_view.csv'): scored.setdefault((int(r['fold']),r['comparison']),[]).append(r)
    oldmetrics=read(R1/'s1a_r1_fold_metrics.csv')+read(R1/'s1a_r1_f2_sensitivity.csv')+read(R1/'s1a_r1_placebo_metrics.csv')
    metricchecks=[]
    for r in oldmetrics:
        key=(int(r['fold']),r['comparison']);a=scored[key];v=pair(*[np.array([float(z[k]) for z in a]) for k in ('observed','baseline','augmented')])
        for new,old in [('RMSE0','baseline_RMSE'),('RMSE1','augmented_RMSE'),('MAE0','baseline_MAE'),('MAE1','augmented_MAE'),('Bias0','baseline_Bias'),('Bias1','augmented_Bias'),('relative_RMSE_gain','relative_RMSE_gain')]: close(v[new],float(r[old]))
        metricchecks.append(dict(fold=key[0],comparison=key[1],verified=True))
    # Read existing bootstrap, never resample.
    bootstrap=read(R1/'s1a_r1_bootstrap_summary.csv');assert len(bootstrap)==256
    folds={};thresholds=[];replay=[];audit=[]
    for yr in YEARS:
        a=scored[yr,'past_only'];d=np.array([r['date'] for r in a],dtype='datetime64[D]');y=np.array([float(r['observed']) for r in a]);assert len(d)==365
        train=read(R1/f'views/fit_labels_F{yr}.csv');q=np.quantile([float(r['Q_target_dsk']) for r in train],[.2,.9]);u=np.quantile([up[str(np.datetime64(r['date'])-np.timedelta64(1,'D'))] for r in train],[.2,.9])
        close(q[0],params[yr,'past_only']['train_low_threshold'])
        groups=dict(outcome=labels(y,q),exante=labels(np.array([up[str(x-np.timedelta64(1,'D'))] for x in d]),u))
        thresholds.append(dict(fold=yr,train_start=train[0]['date'],train_end=train[-1]['date'],train_n=len(train),target_Q20=float(q[0]),target_Q90=float(q[1]),upstream_tminus1_Q20=float(u[0]),upstream_tminus1_Q90=float(u[1])))
        models={}
        for comp in ('past_only','f2'):
            s=scored[yr,comp];pr=pred[yr,comp];assert [r['date'] for r in s]==[str(x) for x in d]
            close(y,[float(r['observed']) for r in s])
            b=np.array([float(r['baseline']) for r in s]);p=np.array([float(r['augmented']) for r in s])
            close(b,[float(r['q_baseline']) for r in pr]);close(p,[float(r['q_prediction']) for r in pr])
            rb,rp=reconstruct(up,params[yr,comp],d,d)
            if not (np.allclose(rb,b,rtol=RTOL,atol=REPLAY_ATOL) and np.allclose(rp,p,rtol=RTOL,atol=REPLAY_ATOL)): raise RuntimeError('REAL REPLAY MISMATCH: STOP BEFORE SWAPS')
            replay.append(dict(fold=yr,model=comp,n=365,max_abs_baseline=float(max(abs(rb-b))),max_abs_prediction=float(max(abs(rp-p)))))
            models[comp]=(b,p)
        support=d[d>=np.datetime64(f'{yr}-01-31')];assert len(support)==335
        for donor in range(1978,1984):
            anchors=np.array([str(donor)+str(x)[4:] for x in support],dtype='datetime64[D]');w=windows(up,anchors);assert w.shape==(335,3) and np.isfinite(w).all()
            audit.append(dict(target=yr,donor=donor,n=335,anchor_start=str(anchors[0]),anchor_end=str(anchors[-1]),history_start=str(anchors[0]-np.timedelta64(30,'D')),month_day_equal=all(str(x)[4:]==str(z)[4:] for x,z in zip(support,anchors)),march1_anchor=f'{donor}-03-01',leap_rule='donor actual history includes Feb29 if within window; no target Feb29'))
        folds[yr]=(d,y,groups,models)
    dump('pre_swap_validation.json',dict(PASS=True,replay=replay,donor_window_audit=audit,synthetic_tests=tests,r1_metric_checks=metricchecks,bootstrap_rows_read=len(bootstrap)))
    # ALL full-year replay and donor legality gates passed before any swapped predictions.
    flow=[];exante=[];daily=[];influ=[];four=[];blocks=[];months=[];totals=[]
    swap_predictions=[];swap_metrics=[];swap_strata=[];swap_months=[];swap_blocks=[];displacement=[]
    for yr,(d,y,groups,models) in folds.items():
        for comp,(b,p) in models.items():
            meta=dict(identity=IDENTITY,fold=yr,model=comp,support='MAIN_365')
            v=pair(y,b,p);totals.append(meta|v)
            s=stratify(y,b,p,groups,meta);flow += [r for r in s if r['grouping']=='outcome'];exante += [r for r in s if r['grouping']=='exante']
            months+=monthly(d,y,b,p,groups,meta)
            ob,om=orthogonal(d,y,b,p,meta);blocks+=ob;totals[-1].update(om)
            influ+=influence(d,y,b,p,groups,meta)
            for i,x in enumerate(d):
                daily.append(meta|dict(date=str(x),month=int(month(d)[i]),block=int(block(d)[i]),outcome=groups['outcome'][i],exante=groups['exante'][i],observed=float(y[i]),baseline=float(b[i]),augmented=float(p[i]),e0=float(b[i]-y[i]),e1=float(p[i]-y[i]),DeltaSSE=float((b[i]-y[i])**2-(p[i]-y[i])**2)))
            for kind,z in (('overall',np.repeat('ALL',len(d))),*groups.items()):
                for state in (('ALL',) if kind=='overall' else STATES):
                    ix=z==state
                    for cell,x in (('A' if comp=='past_only' else 'C',b),('B' if comp=='past_only' else 'D',p)):
                        m=pair(y[ix],x[ix],x[ix]);pv=pair(y[ix],b[ix],p[ix])
                        four.append(meta|dict(cell=cell,grouping=kind,stratum=state,n=int(ix.sum()),RMSE=m['RMSE0'],MAE=m['MAE0'],Bias=m['Bias0'],SSE=m['SSE0'],pair_DeltaSSE=pv['DeltaSSE'],pair_relative_RMSE_gain=pv['relative_RMSE_gain'],small_cell=int(ix.sum())<10))
            ix=d>=np.datetime64(f'{yr}-01-31');sd=d[ix];sy=y[ix];sb=b[ix];sg={k:z[ix] for k,z in groups.items()}
            for donor in range(1978,1984):
                anchor=np.array([str(donor)+str(x)[4:] for x in sd],dtype='datetime64[D]');rb,sp=reconstruct(up,params[yr,comp],sd,anchor);close(rb,sb)
                if donor==yr: close(sp,p[ix])
                smeta=dict(identity=IDENTITY,fold=yr,model=comp,support='YEAR_SWAP_335',donor=donor,real_aligned=donor==yr,noncausal_negative_control=donor!=yr,parameter_sha256=sha(R1/'fitted_parameters.json'))
                ob,om=orthogonal(sd,sy,sb,sp,smeta);swap_blocks+=ob;swap_metrics.append(smeta|pair(sy,sb,sp)|om)
                swap_strata+=stratify(sy,sb,sp,sg,smeta);swap_months+=monthly(sd,sy,sb,sp,sg,smeta)
                for j,x in enumerate(sd):
                    swap_predictions.append(smeta|dict(date=str(x),donor_anchor=str(anchor[j]),outcome=sg['outcome'][j],exante=sg['exante'][j],observed=float(sy[j]),baseline=float(sb[j]),augmented=float(sp[j])))
        for (fold,comp),a in scored.items():
            if fold!=yr or not comp.startswith('placebo_'): continue
            pd=np.array([r['date'] for r in a],dtype='datetime64[D]');assert np.array_equal(pd,d[:275])
            py,pb,pp=[np.array([float(r[k]) for r in a]) for k in ('observed','baseline','augmented')];close(py,y[:275]);pg={k:z[:275] for k,z in groups.items()}
            meta=dict(identity=IDENTITY,fold=yr,model=comp,k=params[yr,comp]['k'],support='DISPLACEMENT_275')
            ob,om=orthogonal(pd,py,pb,pp,meta);blocks+=ob;displacement.append(meta|dict(record='overall')|pair(py,pb,pp)|om)
            displacement += [r|dict(record='stratum') for r in stratify(py,pb,pp,pg,meta)]
            months+=monthly(pd,py,pb,pp,pg,meta);influ+=influence(pd,py,pb,pp,pg,meta)
    ranks=[]
    for yr in YEARS:
        for comp in ('past_only','f2'):
            rows=[r for r in swap_metrics if r['fold']==yr and r['model']==comp]
            allsets=[('overall','ALL',rows,'RMSE1'),('orthogonal','between',rows,'SSE_between1'),('orthogonal','within',rows,'SSE_within1')]
            for kind in ('outcome','exante'):
                for state in STATES: allsets.append((kind,state,[r for r in swap_strata if r['fold']==yr and r['model']==comp and r['grouping']==kind and r['stratum']==state],'RMSE1'))
            for kind,state,rs,key in allsets:
                real=next(r for r in rs if r['donor']==yr);donors=[r for r in rs if r['donor']!=yr];assert len(donors)==5
                if real[key] is None: ranks.append(dict(fold=yr,model=comp,grouping=kind,stratum=state,metric=key,n=0,rank=None,donors_better=None));continue
                value=real[key];tol=max(ATOL,RTOL*abs(value));better=sum(r[key]<value-tol for r in donors);ties=sum(abs(r[key]-value)<=tol for r in donors)
                gains=[r['relative_RMSE_gain'] for r in donors] if key=='RMSE1' else []
                ranks.append(dict(fold=yr,model=comp,grouping=kind,stratum=state,metric=key,n=real['n'],rank=1+better,donors_better=better,donor_ties=ties,donor_gain_min=min(gains) if gains else None,donor_gain_median=float(np.median(gains)) if gains else None,donor_gain_max=max(gains) if gains else None,real_value=value))
    for name,rows in [('flow_strata',flow),('exante_strata',exante),('delta_sse',daily),('influence',influ),('four_cell_baselines',four),('orthogonal_blocks',blocks),('monthly_strata',months),('annual_metrics',totals),('thresholds',thresholds),('year_swap_predictions',swap_predictions),('year_swap_metrics',swap_metrics),('year_swap_strata',swap_strata),('year_swap_monthly_strata',swap_months),('year_swap_orthogonal_blocks',swap_blocks),('year_swap_ranks',ranks),('displacement_reanalysis',displacement)]: write(name,rows)
    assert len(swap_metrics)==36 and len(swap_predictions)==12060 and len(displacement)==39*7
    # AST audit of the numerical implementation: no estimator/solver calls and no historical executor import.
    tree=ast.parse(Path(__file__).read_text(encoding='utf-8'))
    prohibited={'fit','fit_model','ols','lstsq','pinv','minimize','polyfit','curve_fit'}
    calls=[n.func.attr if isinstance(n.func,ast.Attribute) else n.func.id if isinstance(n.func,ast.Name) else '' for n in ast.walk(tree) if isinstance(n,ast.Call)]
    assert not prohibited.intersection(calls)
    final=protected();assert final==h
    dump('analysis_complete.json',dict(identity=IDENTITY,status='PASS',protected_files=len(h),changed_files=[],real_model_fit_calls=0,synthetic_tests=tests,r1_metrics_verified=len(metricchecks),year_swap_arms=36,year_swap_prediction_rows=12060,main_support=365,swap_support=335,placebo_support=275,all_donors_reported=True,parameter_sha256=sha(R1/'fitted_parameters.json'),code_sha256=sha(__file__),raw_directory_writes=0,limitations='Bounded inherited hash inventory; no full historical rescan or adversarial sandbox proof.'))
    print(json.dumps(load(HERE/'analysis_complete.json'),ensure_ascii=False))

if __name__=='__main__': main()
