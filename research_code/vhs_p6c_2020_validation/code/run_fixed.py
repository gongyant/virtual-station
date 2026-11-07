"""Separate frozen prediction and label-scoring CLI; never fit."""
from p6c_common import *
from datetime import timedelta
sys.stdout.reconfigure(encoding='utf-8');PRED=R/'runs/P6C_2020_PREDICTION';SCORE=R/'runs/P6C_2020_SCORING'
def predict():
 assert not PRED.exists();a=jl(R/'P6C_ADMISSION_FROZEN.json');assert a['protocol_hash']==sha(R/'P6C_FROZEN_PROTOCOL.json') and a['admission_hash']==sha(R/'P6C_STATION_ADMISSION.csv') and a['met_hash']==sha(R/'driver/MET_ONLY_2019_12_2020.json');PRED.mkdir();event('PREDICTION_STARTED',admission=sha(R/'P6C_ADMISSION_FROZEN.json'))
 reads=[];calls=[]
 def audit(ev,args):
  if ev=='open' and isinstance(args[0],(str,bytes)):
   n=str(args[0]);reads.append(n)
   if any(s in n for s in ['_file5.txt','_file1.txt','D_gauges','sealed_runoff','quarantine','CAMELS_CH_obs_based','monthly_streamflow_mean']):raise RuntimeError('PREDICTION_LABEL_READ_DENIED')
 def profile(frame,ev,arg):
  if ev=='call' and frame.f_code.co_name in {'fit','fit_transform','partial_fit','lstsq','_fit'}:calls.append(frame.f_code.co_filename);raise RuntimeError('FIT_FORBIDDEN')
 sys.addaudithook(audit);sys.setprofile(profile);sys.path.insert(0,str(P4/'code'));from inference import load_model
 met=jl(R/'driver/MET_ONLY_2019_12_2020.json');models={};out=[]
 for sid in a['descriptive_ids']:
  g,dt=sid.split(':');g=int(g);year,month=map(int,dt.split('-'))
  for mid in ['C0+PT','P2-L1']:
   key=(g,mid)
   if key not in models:
    folder=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');pin=next(p for p in a['models'] if p['gauge_id']==g and Path(p['path'])==folder)
    for n,h in pin['files'].items():assert sha(folder/n)==h
    model=load_model(folder);assert model.hash==pin['model_hash'];assert model.meta['train_cutoff']<'2018-01';models[key]=model
   model=models[key];p=model.predict_month(met[str(g)],year,month)
   out.append({'experiment':'PUBLIC_DATA_FIXED_MODEL_P6C','sample_id':f'LAMAH_CE_PUBLIC_V1:{sid}','prediction_kind':'POST2017_TEMPORAL_HOLDOUT_QUALIFIED_DESCRIPTIVE','task':'RECONSTRUCTION_WITH_OBSERVED_MET','strict_sensitivity_eligible':sid in a['strict_sensitivity_ids'],'model_training_snapshot':model.meta['snapshot_id'],'actual_train_end':model.meta['actual_train_end'],**p})
 sys.setprofile(None);assert not calls;assert len(out)==2*len(a['descriptive_ids']);assert len({(r['sample_id'],r['model_id']) for r in out})==len(out);cw(PRED/'P6C_2020_PREDICTIONS.csv',out)
 jw(PRED/'PREDICTION_READ_AUDIT.json',{'opened_files':sorted(set(reads)),'Q_label_read':False,'fit_calls':len(calls)});jw(PRED/'COMMITMENT.json',{'protocol_hash':a['protocol_hash'],'admission_hash':sha(R/'P6C_ADMISSION_FROZEN.json'),'model_pins':a['models'],'code_hash':sha(__file__),'code_hashes':{p.name:sha(p) for p in (R/'code').glob('*.py')},'met_hash':a['met_hash'],'prediction_hash':sha(PRED/'P6C_2020_PREDICTIONS.csv'),'stations':len({r['gauge_id'] for r in out}),'sample_months':len(a['descriptive_ids']),'prediction_records':len(out),'fit_calls':0,'sealed_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sealed_before_scoring':True,'prior_Q_archive_exposure':True});seal(PRED);event('PREDICTIONS_SEALED',records=len(out),sha256=sha(PRED/'SHA256SUMS.txt'));print('PREDICTIONS_SEALED',len(out),'FIT_CALLS0')
def score():
 verify(PRED);assert not SCORE.exists();a=jl(R/'P6C_ADMISSION_FROZEN.json');commit=jl(PRED/'COMMITMENT.json');assert commit['admission_hash']==sha(R/'P6C_ADMISSION_FROZEN.json') and commit['code_hash']==sha(__file__);SCORE.mkdir();event('SCORING_STARTED',prediction_seal=sha(PRED/'SHA256SUMS.txt'));labels={};daymaps={}
 for g,path in a['sources'].items():
  assert sha(path)==a['source_hashes'][path];_,day,dups=ehyd(Path(path),values=True);daymaps[int(g)]=day
  for sid in a['descriptive_ids']:
   gg,dt=sid.split(':')
   if gg!=g:continue
   nd=calendar.monthrange(2020,int(dt[5:]))[1];qs=[day[f'{dt}-{d:02d}']['Q'] for d in range(1,nd+1)];assert all(v is not None and math.isfinite(v) and v>=0 for v in qs),'Q_CONTRADICTION_ABORT_NOT_RESELECT';labels[int(g),dt]=sum(qs)/nd
 pred=readcsv(PRED/'P6C_2020_PREDICTIONS.csv');station={int(s['gauge_id']):s for s in readcsv(R/'P6C_STATION_ADMISSION.csv')};rows=[];intervals=[];failure=[];boundary=[]
 subsets={'ALL':None,'2020':None,'Q1':[1,2,3],'Q2':[4,5,6],'Q3':[7,8,9],'Q4':[10,11,12],'DJF':[12,1,2],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'MAY_JUNE':[5,6],'LOW_TRAIN_Q20':None,'HIGH_TRAIN_Q80':None}
 for g in sorted({int(r['gauge_id']) for r in pred}):
  for mid in ['C0+PT','P2-L1']:
   data=sorted([r for r in pred if int(r['gauge_id'])==g and r['model_id']==mid],key=lambda r:r['date']);meta=jl(P4/'models/V2'/f'ID_{g}'/mid.replace('+','_')/'model.json');q20,q80=meta['Q20'],meta['Q80']
   with np.load(P4/'models/V2'/f'ID_{g}'/mid.replace('+','_')/'arrays.npz',allow_pickle=False) as aa:train_mean=float(np.average(aa['climate'],weights=aa['month_counts']))
   errs=[(float(r['q_hat_raw'])-labels[g,r['date']])**2 for r in data];total=sum(errs);iw=int(np.argmax(errs));failure.append({'gauge_id':g,'model_id':mid,'region':station[g]['region'],'worst_month':data[iw]['date'],'worst_month_squared_error':errs[iw],'worst_month_SSE_fraction':errs[iw]/total if total else None,'top3_months_SSE_fraction':sum(sorted(errs)[-3:])/total if total else None,'negative_raw_predictions':sum(float(r['q_hat_raw'])<0 for r in data),'IN_SUPPORT_months':sum(r['support_class']=='IN_SUPPORT' for r in data),'training_Qmean':train_mean,'2020_Qmean':float(np.mean([labels[g,r['date']] for r in data])),'mean_shift_ratio':float(np.mean([labels[g,r['date']] for r in data]))/train_mean if train_mean else None})
   for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
    dd=data if quality=='DESCRIPTIVE_ARCHIVE' else [r for r in data if r['strict_sensitivity_eligible']=='True']
    for subset,months in subsets.items():
     rr=[r for r in dd if (months is not None and int(r['date'][5:]) in months) or (months is None and subset in {'ALL','2020'}) or (subset=='LOW_TRAIN_Q20' and labels[g,r['date']]<=q20) or (subset=='HIGH_TRAIN_Q80' and labels[g,r['date']]>=q80)]
     base={'gauge_id':g,'region':station[g]['region'],'model_id':mid,'quality_tier':quality,'subset':subset,'period':'2020','station_summary_min12_supported':len(rr)>=12}
     for variant,key in [('raw','q_hat_raw'),('nonnegative','q_hat_nonnegative')]:
      mm=metrics([labels[g,r['date']] for r in rr],[float(r[key]) for r in rr]) if rr else {'n':0,**{k:None for k in ['MSE','RMSE','MAE','NSE','PBIAS','KGE_r','KGE_alpha','KGE_beta','Qobs_mean','Qsim_mean','KGE']},'undefined_reason':'NO_ELIGIBLE_SUBSET_MONTHS'}
      rows.append({**base,'prediction':variant,**mm})
     for lev in [80,90]:
      good=[r for r in rr if r[f'lower{lev}'] and r[f'upper{lev}']];yy=np.array([labels[g,r['date']] for r in good]);lo=np.array([float(r[f'lower{lev}']) for r in good]);hi=np.array([float(r[f'upper{lev}']) for r in good]);alpha=1-lev/100
      intervals.append({**base,'nominal':lev/100,'n':len(good),'coverage':float(np.mean((yy>=lo)&(yy<=hi))) if good else None,'mean_width':float(np.mean(hi-lo)) if good else None,'interval_score':float(np.mean(hi-lo+2/alpha*np.maximum(lo-yy,0)+2/alpha*np.maximum(yy-hi,0))) if good else None,'undefined_reason':None if good else 'NO_DEFINED_INTERVAL_OR_SUBSET'})
   for shift in [-1,0,1]:
    yy=[];pp=[]
    for r in data:
     dt=r['date'];nd=calendar.monthrange(2020,int(dt[5:]))[1];days=[(datetime(2020,int(dt[5:]),d)+timedelta(days=shift)).strftime('%Y-%m-%d') for d in range(1,nd+1)];qs=[daymaps[g].get(d,{}).get('Q') for d in days]
     if all(v is not None and math.isfinite(v) and v>=0 for v in qs):yy.append(sum(qs)/nd);pp.append(float(r['q_hat_raw']))
    boundary.append({'gauge_id':g,'model_id':mid,'calendar_day_shift':shift,'interpretation':'fixed +/-1 day diagnostic, NOT measured hourly timezone conversion; no best-shift selection',**metrics(yy,pp)})
 comparisons=[]
 for c in rows:
  if c['model_id']!='C0+PT':continue
  l=next(r for r in rows if r['gauge_id']==c['gauge_id'] and r['model_id']=='P2-L1' and all(r[k]==c[k] for k in ['quality_tier','subset','prediction']));assert l['n']==c['n']
  comparisons.append({**{k:c[k] for k in ['gauge_id','region','quality_tier','subset','prediction','n','station_summary_min12_supported']},'MSE_skill':1-l['MSE']/c['MSE'] if c['MSE'] is not None and c['MSE']>0 else None,'MSE_C0PT':c['MSE'],'MSE_L1':l['MSE'],'NSE_C0PT':c['NSE'],'NSE_L1':l['NSE'],'KGE_C0PT':c['KGE'],'KGE_L1':l['KGE'],'undefined_reason':c['undefined_reason'] or l['undefined_reason']})
 summary=[]
 for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
  for variant in ['raw','nonnegative']:
   for region in ['ALL',*sorted({r['region'] for r in comparisons})]:
    for subset in subsets:
     rr=[r for r in comparisons if r['quality_tier']==quality and r['prediction']==variant and r['subset']==subset and (region=='ALL' or r['region']==region) and r['MSE_skill'] is not None and (subset not in ['ALL','2020'] or r['station_summary_min12_supported'])]
     summary.append({'quality_tier':quality,'prediction':variant,'region':region,'subset':subset,'stations':len(rr),'positive_stations':sum(r['MSE_skill']>0 for r in rr),'equal_station_mean_skill':float(np.mean([r['MSE_skill'] for r in rr])) if rr else None,'station_median_skill':float(np.median([r['MSE_skill'] for r in rr])) if rr else None,'reason':None if rr else 'NO_ELIGIBLE_STATIONS','dependency_note':'network-related stations and one new year; no significance claim'})
 skills={(c['gauge_id'],c['quality_tier'],c['subset'],c['prediction']):c['MSE_skill'] for c in comparisons}
 for r in rows:r['MSE_skill_vs_C0PT']=0. if r['model_id']=='C0+PT' and r['MSE'] is not None and r['MSE']>0 else skills[(r['gauge_id'],r['quality_tier'],r['subset'],r['prediction'])] if r['model_id']=='P2-L1' else None
 cw(SCORE/'P6C_ALL_STATION_METRICS.csv',rows);cw(SCORE/'P6C_INTERVAL_DIAGNOSTICS.csv',intervals);cw(SCORE/'P6C_MODEL_COMPARISON.csv',comparisons);cw(SCORE/'P6C_REGION_SUMMARY.csv',summary);cw(SCORE/'P6C_FAILURE_DIAGNOSTICS.csv',failure);cw(SCORE/'P6C_FIXED_DAY_SHIFT_SENSITIVITY.csv',boundary)
 jw(SCORE/'SCORING_PROVENANCE.json',{'prediction_seal':sha(PRED/'SHA256SUMS.txt'),'Q_sources':{p:a['source_hashes'][p] for p in a['sources'].values()},'sample_months':len(labels),'prediction_records':len(pred),'fit_calls':0,'raw_Qobs_exported':False,'prior_Q_archive_exposure':True,'QC_limits':a['QC_limit']});seal(SCORE);event('SCORING_COMPLETE',stations=len({k[0] for k in labels}),months=len(labels),records=len(pred),fit_calls=0)
 print(json.dumps([r for r in summary if r['region']=='ALL' and r['prediction']=='raw' and r['subset'] in ['ALL','DJF','MAY_JUNE']],indent=2))
if __name__=='__main__':
 try:globals()[sys.argv[1]]()
 except Exception as ex:event('FAILED',stage=sys.argv[1],reason=str(ex));raise
