"""Independent scoring process; no parameter estimation or fit code imports."""
from common import *
def metric(y,p):
    e=p-y;den=float(np.sum((y-y.mean())**2));sse=float(e@e)
    return dict(n=len(y),RMSE=float(np.sqrt(np.mean(e**2))),MAE=float(np.mean(abs(e))),NSE=1-sse/den if den else None,Bias=float(e.mean()),PBIAS=float(100*e.sum()/y.sum()) if y.sum() else None,SSE=sse,numeric_annual_sum_error=float(e.sum()))
def paired(y,b,p):
    m0=metric(y,b);m1=metric(y,p);return dict(n=len(y),RMSE0=m0['RMSE'],RMSE1=m1['RMSE'],MAE0=m0['MAE'],MAE1=m1['MAE'],Bias0=m0['Bias'],Bias1=m1['Bias'],PBIAS0=m0['PBIAS'],PBIAS1=m1['PBIAS'],SSE0=m0['SSE'],SSE1=m1['SSE'],DeltaSSE=m0['SSE']-m1['SSE'],relative_RMSE_gain=1-m1['RMSE']/m0['RMSE'],DeltaNSE=(m1['NSE']-m0['NSE']) if m1['NSE'] is not None and m0['NSE'] is not None else None,numeric_annual_sum_error0=m0['numeric_annual_sum_error'],numeric_annual_sum_error1=m1['numeric_annual_sum_error'])
def orth(d,y,b,p,meta):
    block=(d-d.astype('datetime64[Y]').astype('datetime64[D]')).astype(int)//30;rows=[];tot={'between0':0.,'between1':0.,'within0':0.,'within1':0.}
    for k in np.unique(block):
        ix=block==k;r=meta|dict(block=int(k),start=str(d[ix][0]),end=str(d[ix][-1]),n=int(ix.sum()))
        for j,e in enumerate(((b-y)[ix],(p-y)[ix])):
            be=float(len(e)*e.mean()**2);wi=float(np.sum((e-e.mean())**2));cr=float(2*e.mean()*np.sum(e-e.mean()));check(e@e,be+wi);assert abs(cr)<=1e-10+1e-12*float(e@e)
            r.update({f'between{j}':be,f'within{j}':wi,f'cross{j}':cr});tot[f'between{j}']+=be;tot[f'within{j}']+=wi
        r['DeltaSSE_between']=r['between0']-r['between1'];r['DeltaSSE_within']=r['within0']-r['within1'];rows.append(r)
    tot['DeltaSSE_between']=tot['between0']-tot['between1'];tot['DeltaSSE_within']=tot['within0']-tot['within1'];check(paired(y,b,p)['DeltaSSE'],tot['DeltaSSE_between']+tot['DeltaSSE_within']);return rows,tot
def boot(y,pairs,L,circular,rng,reps=10000):
    n=len(y);out=[[] for _ in pairs];dn=[[] for _ in pairs]
    for start in range(0,reps,500):
        size=min(500,reps-start);st=rng.integers(0,n if circular else n-L+1,size=(size,int(np.ceil(n/L))));idx=(st[:,:,None]+np.arange(L)).reshape(size,-1)[:,:n]
        if circular:idx%=n
        yy=y[idx];den=np.sum((yy-yy.mean(axis=1,keepdims=True))**2,axis=1)
        for j,(b,p) in enumerate(pairs):
            s0=np.sum((b[idx]-yy)**2,axis=1);s1=np.sum((p[idx]-yy)**2,axis=1);out[j].extend(1-np.sqrt(s1/s0));dn[j].extend((s0-s1)/den)
    return np.array(out),np.array(dn)
def main():
    verify_inputs();seal=load(H/'prediction_freeze.json')
    for p,v in seal['files'].items():assert sha(ROOT/p)==v
    if (H/'scoring_resumed.json').exists() or (H/'scoring_complete.json').exists():raise RuntimeError('Scoring repair already started; no repeat')
    dump('scoring_resumed.json',dict(prediction_freeze_sha256=sha(H/'prediction_freeze.json'),repair_manifest_sha256=sha(H/'scoring_repair_manifest.json')));event('EVALUATION_LABELS_OPENED',prediction_freeze_sha256=sha(H/'prediction_freeze.json'))
    # Evaluation observations enter only this separate scorer after global prediction sealing.
    observations={(int(r['fold']),r['date']):float(r['observed']) for r in read(R1/'scored_daily_view.csv') if r['comparison']=='past_only'}
    rows=read(H/(P+'predictions.csv'));sw=read(H/(P+'year_swap_predictions.csv'));cfg=load(H/(P+'frozen_protocol.json'));comparisons=cfg['comparisons'];foldmetrics=[];gains=[];strata=[];blocks=[];swapmetrics=[];swapstrata=[];ranks=[];monthly=[];bs=[];cache={}
    for yr in (1981,1982,1983):
        d=days(f'{yr}-01-01',f'{yr}-12-31');y=np.array([observations[yr,str(x)] for x in d]);assert np.isfinite(y).all() and (y>=0).all();models={};states=None
        for model in ('M0','M1','M2','M3'):
            a=[r for r in rows if int(r['fold'])==yr and r['model']==model];assert [r['date'] for r in a]==[str(x) for x in d]
            pred=np.array([float(r['prediction']) for r in a]);raw=np.array([float(r['raw_prediction']) for r in a]);z=np.array([r['exante_state'] for r in a]);states=z if states is None else states;assert np.array_equal(z,states);models[model]=pred
            foldmetrics.append(dict(fold=yr,model=model,support='MAIN_365',identity=IDENTITY,clip_n=int((raw<0).sum()),clip_rate=float((raw<0).mean()),clip_delta_sum=float((pred-raw).sum()),raw_RMSE=float(np.sqrt(np.mean((raw-y)**2))))|metric(y,pred))
        cache[yr]=(y,[(models[b],models[a]) for a,b in comparisons])
        for aug,base in comparisons:
            comp=aug+'_vs_'+base;b=models[base];p=models[aug];meta=dict(fold=yr,comparison=comp,support='MAIN_365',identity=IDENTITY);bl,tot=orth(d,y,b,p,meta);blocks+=bl;gains.append(meta|paired(y,b,p)|tot)
            for state in ('LOW','MID','HIGH'):
                ix=states==state;assert ix.any();strata.append(meta|dict(stratum=state)|paired(y[ix],b[ix],p[ix]))
            check(sum(r['DeltaSSE'] for r in strata if r['fold']==yr and r['comparison']==comp),gains[-1]['DeltaSSE'])
            for m in range(12):
                ix=months(d)==m;monthly.append(meta|dict(month=m+1)|paired(y[ix],b[ix],p[ix]))
        sd=d[30:];sy=y[30:];b=models['M2'][30:]
        for donor in range(1978,1984):
            a=[r for r in sw if int(r['fold'])==yr and int(r['donor'])==donor];assert [r['date'] for r in a]==[str(x) for x in sd];p=np.array([float(r['prediction']) for r in a]);check(b,[float(r['M2_prediction']) for r in a]);assert np.array_equal([r['exante_state'] for r in a],states[30:])
            if donor==yr:check(p,models['M3'][30:])
            meta=dict(fold=yr,model='M3',comparison='M3_swap_vs_M2',donor=donor,real_aligned=donor==yr,support='YEAR_SWAP_335',identity=IDENTITY);bl,tot=orth(sd,sy,b,p,meta);blocks+=bl;swapmetrics.append(meta|paired(sy,b,p)|tot)
            for state in ('LOW','MID','HIGH'):
                ix=states[30:]==state;swapstrata.append(meta|dict(stratum=state)|paired(sy[ix],b[ix],p[ix]))
            for m in range(12):
                ix=months(sd)==m;monthly.append(meta|dict(month=m+1)|paired(sy[ix],b[ix],p[ix]))
        for scope,key,rr in [('overall','RMSE1',[r for r in swapmetrics if r['fold']==yr]),('between','between1',[r for r in swapmetrics if r['fold']==yr]),('within','within1',[r for r in swapmetrics if r['fold']==yr])]+[(state,'RMSE1',[r for r in swapstrata if r['fold']==yr and r['stratum']==state]) for state in ('LOW','MID','HIGH')]:
            real=next(r for r in rr if r['donor']==yr);don=[r for r in rr if r['donor']!=yr];tol=1e-10+1e-12*abs(real[key]);better=sum(r[key]<real[key]-tol for r in don);ties=sum(abs(r[key]-real[key])<=tol for r in don);gg=[r['relative_RMSE_gain'] for r in don]
            ranks.append(dict(fold=yr,scope=scope,rank=1+better,donors_better=better,ties=ties,donor_gain_min=min(gg),donor_gain_median=float(np.median(gg)),donor_gain_max=max(gg)))
    for circular in (True,False):
        for L in (30,60):
            byyear=[];dnbyyear=[];rng=np.random.default_rng(20261011)
            for yr in (1981,1982,1983):
                y,pairs=cache[yr];g,dn=boot(y,pairs,L,circular,rng);byyear.append(g);dnbyyear.append(dn)
                for j,(aug,base) in enumerate(comparisons):
                    lo,hi=np.quantile(g[j],[.025,.975]);dl,du=np.quantile(dn[j],[.025,.975]);bs.append(dict(comparison=aug+'_vs_'+base,scope=yr,block_days=L,circular=circular,replicates=10000,seed=20261011,gain_lower=float(lo),gain_upper=float(hi),DeltaNSE_lower=float(dl),DeltaNSE_upper=float(du)))
            gm=np.mean(byyear,axis=0);dm=np.mean(dnbyyear,axis=0)
            for j,(aug,base) in enumerate(comparisons):
                lo,hi=np.quantile(gm[j],[.025,.975]);dl,du=np.quantile(dm[j],[.025,.975]);bs.append(dict(comparison=aug+'_vs_'+base,scope='MACRO_EQUAL_YEAR',block_days=L,circular=circular,replicates=10000,seed=20261011,gain_lower=float(lo),gain_upper=float(hi),DeltaNSE_lower=float(dl),DeltaNSE_upper=float(du)))
    macro=[]
    for aug,base in comparisons:
        rr=[r for r in gains if r['comparison']==aug+'_vs_'+base];keys=['relative_RMSE_gain','DeltaNSE','DeltaSSE','RMSE0','RMSE1','MAE0','MAE1','Bias0','Bias1','PBIAS0','PBIAS1','numeric_annual_sum_error0','numeric_annual_sum_error1','DeltaSSE_between','DeltaSSE_within']
        macro.append(dict(comparison=aug+'_vs_'+base,scope='MACRO_EQUAL_YEAR',worst_year=min(rr,key=lambda r:r['relative_RMSE_gain'])['fold'],improved_years=sum(r['relative_RMSE_gain']>0 for r in rr))|{k:float(np.mean([r[k] for r in rr])) for k in keys})
    for n,a in [('fold_metrics',foldmetrics),('conditional_gain',gains),('exante_strata',strata),('orthogonal_blocks',blocks),('year_swap_metrics',swapmetrics),('year_swap_strata',swapstrata),('year_swap_ranks',ranks),('monthly_metrics',monthly),('bootstrap_summary',bs),('macro_metrics',macro)]:write(P+n+'.csv',a)
    for p,v in seal['files'].items():assert sha(ROOT/p)==v
    verify_inputs();event('SCORING_COMPLETE',historical_changes=0,fits_after_label_open=0)
    dump('scoring_complete.json',dict(status='PASS',comparisons=len(gains),bootstrap_rows=len(bs),swap_arms=len(swapmetrics),prediction_hashes_unchanged=True))
    print(macro)
if __name__=='__main__':main()
