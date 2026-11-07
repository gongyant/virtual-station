"""Once-only six authorized OLS fits. Train-label views only; never loads scored_daily_view."""
from common import *
def main():
    verify_inputs()
    if (H/'fit_started.json').exists() or (H/'prediction_freeze.json').exists():raise RuntimeError('Already started; do not auto refit')
    dump('fit_started.json',dict(once_only=True,time=datetime.now(timezone.utc).isoformat()))
    up,p,t=feature_sources();pars={(r['fold'],r['comparison']):r for r in load(R1/'fitted_parameters.json')}
    old=read(R1/'s1a_r1_predictions.csv');output=[];swap=[];parameters=[];diagnostics=[];ledger=[]
    for yr in (1981,1982,1983):
        train=days('1978-01-31',f'{yr-1}-12-31');dev=days(f'{yr}-01-01',f'{yr}-12-31');par=pars[yr,'past_only']
        view=read(R1/f'views/fit_labels_F{yr}.csv');assert [r['date'] for r in view]==[str(d) for d in train]
        labels=np.array([float(r['Q_target_dsk']) for r in view]);assert np.isfinite(labels).all() and (labels>=0).all()
        climate=np.array(par['target_climate']);check(climate,np.array([labels[months(train)==m].mean() for m in range(12)]))
        residual=labels-climate[months(train)]
        mt,md,qt,qd,met_cl,met_scale=transform(up,p,t,train,dev,par)
        baseline=climate[months(dev)];oldpred=[r for r in old if int(r['fold'])==yr and r['comparison']=='past_only'];assert [r['date'] for r in oldpred]==[str(d) for d in dev]
        check(baseline,[float(r['q_baseline_raw']) for r in oldpred]);replay=baseline+qd@np.array(par['beta']);check(np.maximum(replay,0),[float(r['q_prediction']) for r in oldpred])
        raw={'M0':np.array([float(r['q_baseline_raw']) for r in oldpred]),'M1':np.array([float(r['q_prediction_raw']) for r in oldpred])};beta3=None
        for model,x,xd in [('M2',mt,md),('M3',np.column_stack([mt,qt]),np.column_stack([md,qd]))]:
            singular=require_rank(x,x.shape[1]);event('FIT_STARTED',fold=yr,model=model,train_start=str(train[0]),train_end=str(train[-1]),n=len(train),development_labels_opened=False)
            beta=np.linalg.pinv(x,rcond=1e-12)@residual;raw[model]=baseline+xd@beta
            if not np.isfinite(raw[model]).all():raise RuntimeError('Nonfinite output: STOP')
            cor=np.corrcoef(x,rowvar=False);vif=np.diag(np.linalg.inv(cor));condition=float(singular[0]/singular[-1])
            diagnostics.append(dict(fold=yr,model=model,features='P7,T7'+(',W1,W7,W30' if model=='M3' else ''),condition=condition,singular_values=json.dumps(singular.tolist()),VIF=json.dumps(vif.tolist()),correlation_matrix=json.dumps(cor.tolist()),beta=json.dumps(beta.tolist()),signs=json.dumps(np.sign(beta).tolist()),warning=bool(condition>30 or np.any(vif>10))))
            param=dict(fold=yr,model=model,beta=beta.tolist(),feature_order=['P7','T7']+(['W1','W7','W30'] if model=='M3' else []),target_climate=climate.tolist(),met_monthly_climate=met_cl.tolist(),met_scale=met_scale.tolist(),upstream_monthly_climate=par['upstream_monthly_climate'],upstream_scale=par['upstream_scale'],train_start=str(train[0]),train_end=str(train[-1]),train_n=len(train),dev_n=len(dev))
            parameters.append(param)
            if model=='M3':beta3=beta
            event('FIT_AND_PREDICT_COMPLETE',fold=yr,model=model,development_labels_opened=False)
        thresholds=np.quantile(np.array([up[str(d-np.timedelta64(1,'D'))] for d in train]),[.2,.9]);state=np.where(np.array([up[str(d-np.timedelta64(1,'D'))] for d in dev])<=thresholds[0],'LOW',np.where(np.array([up[str(d-np.timedelta64(1,'D'))] for d in dev])>=thresholds[1],'HIGH','MID'))
        for model in ('M0','M1','M2','M3'):
            for i,d in enumerate(dev):output.append(dict(fold=yr,date=str(d),model=model,prediction=float(max(raw[model][i],0)),raw_prediction=float(raw[model][i]),exante_state=state[i],upstream_tminus1_Q20=float(thresholds[0]),upstream_tminus1_Q90=float(thresholds[1]),identity=IDENTITY))
        # Real replay before swapped source generation, with target P/T and all parameters held fixed.
        common=dev[30:];assert len(common)==335
        selfq=(windows(up,common,(1,7,30))-np.array(par['upstream_monthly_climate'])[months(common)])/np.array(par['upstream_scale']);selfraw=baseline[30:]+np.column_stack([md[30:],selfq])@beta3;check(selfraw,raw['M3'][30:])
        event('M3_REAL_REPLAY_PASS_BEFORE_SWAPS',fold=yr,max_abs=float(max(abs(selfraw-raw['M3'][30:]))))
        for donor in range(1978,1984):
            anchors=np.array([str(donor)+str(d)[4:] for d in common],dtype='datetime64[D]');zq=(windows(up,anchors,(1,7,30))-np.array(par['upstream_monthly_climate'])[months(anchors)])/np.array(par['upstream_scale']);r=baseline[30:]+np.column_stack([md[30:],zq])@beta3
            for i,d in enumerate(common):swap.append(dict(fold=yr,date=str(d),donor=donor,donor_anchor=str(anchors[i]),real_aligned=donor==yr,prediction=float(max(r[i],0)),raw_prediction=float(r[i]),M2_prediction=float(max(raw['M2'][30+i],0)),exante_state=state[30+i],target_P7_T7_fixed=True,identity=IDENTITY))
        ledger.append(dict(fold=yr,train_label_view=str((R1/f'views/fit_labels_F{yr}.csv').relative_to(ROOT)),train_label_sha256=sha(R1/f'views/fit_labels_F{yr}.csv'),train_start=str(train[0]),train_end=str(train[-1]),train_n=len(train),development_start=str(dev[0]),development_end=str(dev[-1]),development_n=len(dev),development_target_access=False,past_feature_max_date='target t-1',met_feature_min_date='target t-7',Q_feature_min_date='target t-30',M0_M1_reused=True,source_model_sha256=sha(R1/'fitted_parameters.json')))
    write(P+'predictions.csv',output);write(P+'year_swap_predictions.csv',swap);write('feature_diagnostics.csv',diagnostics);dump('fitted_parameters.json',parameters);dump('data_role_ledger.json',ledger)
    verify_inputs();files=[H/(P+'predictions.csv'),H/(P+'year_swap_predictions.csv'),H/'fitted_parameters.json',H/'feature_diagnostics.csv',H/'data_role_ledger.json']
    dump('prediction_freeze.json',dict(fits=6,main_rows=len(output),swap_rows=len(swap),frozen_at=datetime.now(timezone.utc).isoformat(),development_labels_opened=False,files={p.relative_to(ROOT).as_posix():sha(p) for p in files}))
    event('ALL_PREDICTIONS_FROZEN',fits=6,main_rows=len(output),swap_rows=len(swap),development_labels_opened=False);print(dict(fits=6,main_rows=len(output),swap_rows=len(swap),predictions_frozen=True))
if __name__=='__main__':main()
