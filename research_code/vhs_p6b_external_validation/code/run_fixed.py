"""Frozen P4-V2 inference, then separately opened provider observed Q. No fit."""
import sys,json,csv,hashlib,math,calendar,collections,time
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,cw,sha,ehyd,readcsv
sys.stdout.reconfigure(encoding='utf-8');PRED=R/'runs/P6B_EHYD_2018_2019';SCORE=R/'runs/P6B_EHYD_2018_2019_SCORING'
def event(name,**kw):
 with (R/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'event':name,**kw})+'\n')
def seal(d):
 (d/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in sorted(d.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
def verify(d):
 for line in (d/'SHA256SUMS.txt').read_text().splitlines():h,n=line.split('  ',1);assert sha(d/n)==h,n
def metrics(y,p):
 y=np.array(y,float);p=np.array(p,float);e=p-y;sy=float(y.std());sp=float(p.std());sst=float(sum((y-y.mean())**2));mean=float(y.mean());out={'n':len(y),'MSE':float(np.mean(e**2)),'RMSE':float(np.sqrt(np.mean(e**2))),'MAE':float(np.mean(abs(e))),'NSE':1-float(sum(e**2))/sst if sst>0 else None,'PBIAS':100*float(sum(e))/float(sum(y)) if abs(sum(y))>1e-12 else None,'KGE_r':float(np.corrcoef(y,p)[0,1]) if sy>0 and sp>0 and len(y)>1 else None,'KGE_alpha':sp/sy if sy>0 else None,'KGE_beta':float(p.mean())/mean if abs(mean)>1e-12 else None,'Qobs_mean':mean,'Qsim_mean':float(p.mean())}
 out['KGE']=1-math.sqrt(sum((out[k]-1)**2 for k in ['KGE_r','KGE_alpha','KGE_beta'])) if all(out[k] is not None for k in ['KGE_r','KGE_alpha','KGE_beta']) else None;out['undefined_reason']='UNDEFINED_VARIANCE_MEAN_OR_CORRELATION' if any(out[k] is None for k in ['NSE','KGE','PBIAS']) else None;return out
if sys.argv[1]=='predict':
 assert not PRED.exists();PRED.mkdir();a=jl(R/'P6B_ADMISSION_FROZEN.json');assert a['protocol_hash']==sha(R/'P6B_FROZEN_PROTOCOL.json');assert a['met_file_hash']==sha(R/'driver/MET_ONLY_2018_2019.json');event('PREDICTION_STARTED',admission_hash=sha(R/'P6B_ADMISSION_FROZEN.json'),fit_calls=0)
 reads=[]
 def audit(e,args):
  if e=='open' and isinstance(args[0],(str,bytes)):
   name=str(args[0]);reads.append(name)
   if any(x in name for x in ['_file5.txt','_file1.txt','CAMELS_CH_obs_based','monthly_streamflow_mean.csv','D_gauges']):raise RuntimeError('PREDICTION_ROLE_LABEL_READ_DENIED')
 sys.addaudithook(audit);sys.path.insert(0,str(P4/'code'));from inference import load_model
 met=jl(R/'driver/MET_ONLY_2018_2019.json');protocol=jl(R/'P6B_FROZEN_PROTOCOL.json');models={};out=[]
 for sid in a['descriptive_ids']:
  g,dt=sid.split(':');g=int(g);y,m=map(int,dt.split('-'))
  for mid in ['C0+PT','P2-L1']:
   key=(g,mid)
   if key not in models:
    folder=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');mod=load_model(folder);expected=next(x for x in protocol['frozen_models'] if x['gauge_id']==g and Path(x['path']).name==folder.name);assert mod.hash==expected['model_hash'];models[key]=mod
   mod=models[key];assert mod.meta['train_cutoff']<'2018-01';pred=mod.predict_month(met[str(g)],y,m)
   out.append({'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','sample_id':'LAMAH_CE_PUBLIC_V1:'+sid,'prediction_kind':'POST2017_TEMPORAL_HOLDOUT_QUALIFIED_DESCRIPTIVE','task':'RECONSTRUCTION_WITH_OBSERVED_MET','quality_tier':'PROVIDER_DAILY_ARCHIVE','strict_sensitivity_eligible':sid in a['strict_sensitivity_ids'],'model_training_snapshot':mod.meta['snapshot_id'],'actual_train_end':mod.meta['actual_train_end'],**pred})
 assert len(out)==2*len(a['descriptive_ids']);cw(PRED/'P6B_PREDICTIONS_WITHOUT_QOBS.csv',out);jw(PRED/'PREDICTION_READ_AUDIT.json',{'opened_files':sorted(set(reads)),'forbidden_Q_read':False});jw(PRED/'COMMITMENT.json',{'protocol_hash':sha(R/'P6B_FROZEN_PROTOCOL.json'),'admission_hash':sha(R/'P6B_ADMISSION_FROZEN.json'),'code_hash':sha(__file__),'prediction_hash':sha(PRED/'P6B_PREDICTIONS_WITHOUT_QOBS.csv'),'predictions':len(out),'sample_months':len(a['descriptive_ids']),'stations':len({i.split(':')[0] for i in a['descriptive_ids']}),'models_loaded':len(models),'fit_calls':0,'sealed_before_scoring':True});seal(PRED);event('PREDICTIONS_SEALED',records=len(out),seal_hash=sha(PRED/'SHA256SUMS.txt'));print('SEALED_PREDICTIONS',len(out),'FIT0')
elif sys.argv[1]=='score':
 verify(PRED);assert not SCORE.exists();commit=jl(PRED/'COMMITMENT.json');assert commit['code_hash']==sha(__file__);assert commit['admission_hash']==sha(R/'P6B_ADMISSION_FROZEN.json');SCORE.mkdir();event('SCORING_STARTED',prediction_seal=sha(PRED/'SHA256SUMS.txt'));a=jl(R/'P6B_ADMISSION_FROZEN.json');labels={};monthly=[];ids=set(a['descriptive_ids'])
 for g,path in a['sources'].items():
  if not any(s.startswith(g+':') for s in ids):continue
  assert sha(path)==a['source_hashes'][path];_,day,dups=ehyd(Path(path),values=True)
  for sid in [s for s in ids if s.startswith(g+':')]:
   _,dt=sid.split(':');y,m=map(int,dt.split('-'));days=[f'{dt}-{d:02d}' for d in range(1,calendar.monthrange(y,m)[1]+1)];qs=[day[d]['Q'] for d in days];assert all(v is not None and math.isfinite(v) and v>=0 for v in qs),'Q_NUMERIC_CONTRADICTION_ABORT_NO_RESELECTION';labels[int(g),dt]=sum(qs)/len(qs)
 pred=readcsv(PRED/'P6B_PREDICTIONS_WITHOUT_QOBS.csv');rows=[];cis=[];comparisons=[];support=[];residuals=[];ss={s['gauge_id']:s for s in jl(R/'evidence/STATIONS_27.json')}
 for g in sorted({int(r['gauge_id']) for r in pred}):
  region=ss[g]['original_attributes']['region']
  for mid in ['C0+PT','P2-L1']:
   data=sorted([r for r in pred if int(r['gauge_id'])==g and r['model_id']==mid],key=lambda r:r['date']);model=jl(P4/'models/V2'/f'ID_{g}'/mid.replace('+','_')/'model.json');q20=model['Q20'];q80=model['Q80']
   for r in data:
    dt=r['date'];err=float(r['q_hat_raw'])-labels[g,dt];residuals.append({'gauge_id':g,'model_id':mid,'date':dt,'error':err,'squared_error':err**2,'support_class':r['support_class'],'max_abs_z':r['max_abs_z'],'strict_sensitivity_eligible':r['strict_sensitivity_eligible']})
   for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
    dd=data if quality=='DESCRIPTIVE_ARCHIVE' else [r for r in data if r['strict_sensitivity_eligible']=='True']
    for subset in ['ALL','2018','2019','DJF','MAM','JJA','SON','MAY_JUNE','LOW_TRAIN_Q20','HIGH_TRAIN_Q80']:
     months={'DJF':[12,1,2],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'MAY_JUNE':[5,6]}
     rr=[r for r in dd if subset=='ALL' or subset==r['date'][:4] or subset in months and int(r['date'][5:]) in months[subset] or subset=='LOW_TRAIN_Q20' and labels[g,r['date']]<=q20 or subset=='HIGH_TRAIN_Q80' and labels[g,r['date']]>=q80]
     if not rr:continue
     y=np.array([labels[g,r['date']] for r in rr]);base={'gauge_id':g,'region':region,'model_id':mid,'quality_tier':quality,'subset':subset,'station_summary_min12_supported':len(rr)>=12}
     for variant,key in [('raw','q_hat_raw'),('nonnegative','q_hat_nonnegative')]:rows.append({**base,'prediction':variant,**metrics(y,[float(r[key]) for r in rr])})
     for lev in [80,90]:
      good=[r for r in rr if r[f'lower{lev}'] and r[f'upper{lev}']];yy=np.array([labels[g,r['date']] for r in good]);lo=np.array([float(r[f'lower{lev}']) for r in good]);hi=np.array([float(r[f'upper{lev}']) for r in good]);alpha=1-lev/100;cis.append({**base,'nominal':lev/100,'n':len(good),'coverage':float(np.mean((yy>=lo)&(yy<=hi))) if good else None,'mean_width':float(np.mean(hi-lo)) if good else None,'interval_score':float(np.mean(hi-lo+2/alpha*np.maximum(lo-yy,0)+2/alpha*np.maximum(yy-hi,0))) if good else None,'reason':None if good else 'NO_DEFINED_INTERVAL'})
  for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
   for subset in ['ALL','2018','2019','DJF','MAM','JJA','SON','MAY_JUNE','LOW_TRAIN_Q20','HIGH_TRAIN_Q80']:
    c=next((r for r in rows if r['gauge_id']==g and r['model_id']=='C0+PT' and r['quality_tier']==quality and r['subset']==subset and r['prediction']=='raw'),None);l=next((r for r in rows if r['gauge_id']==g and r['model_id']=='P2-L1' and r['quality_tier']==quality and r['subset']==subset and r['prediction']=='raw'),None)
    if not c or not l:continue
    assert c['n']==l['n'];comparisons.append({'gauge_id':g,'region':region,'quality_tier':quality,'subset':subset,'n':c['n'],'MSE_skill':1-l['MSE']/c['MSE'] if c['MSE']>0 else None,'MSE_C0PT':c['MSE'],'MSE_L1':l['MSE'],'NSE_C0PT':c['NSE'],'NSE_L1':l['NSE'],'KGE_C0PT':c['KGE'],'KGE_L1':l['KGE'],'station_summary_min12_supported':c['n']>=12})
 cw(SCORE/'P6B_ALL_STATION_METRICS.csv',rows);cw(SCORE/'P6B_INTERVAL_DIAGNOSTICS.csv',cis);cw(SCORE/'P6B_MODEL_COMPARISON.csv',comparisons);cw(SCORE/'P6B_ERRORS_WITHOUT_QOBS.csv',residuals)
 summary=[]
 for quality in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
  for region in ['ALL',*sorted({c['region'] for c in comparisons})]:
   for subset in ['ALL','2018','2019','DJF','MAY_JUNE']:
    rr=[c for c in comparisons if c['quality_tier']==quality and c['subset']==subset and (region=='ALL' or c['region']==region) and c['MSE_skill'] is not None and (subset!='ALL' or c['station_summary_min12_supported'])]
    if rr:summary.append({'quality_tier':quality,'region':region,'subset':subset,'stations':len(rr),'positive_stations':sum(c['MSE_skill']>0 for c in rr),'equal_station_mean_skill':float(np.mean([c['MSE_skill'] for c in rr])),'station_median_skill':float(np.median([c['MSE_skill'] for c in rr])),'dependency_note':'stations within river network not independent; no significance test'})
 cw(SCORE/'P6B_REGION_SUMMARY.csv',summary);jw(SCORE/'SCORING_PROVENANCE.json',{'protocol_hash':commit['protocol_hash'],'admission_hash':commit['admission_hash'],'prediction_seal_hash':sha(PRED/'SHA256SUMS.txt'),'Q_sources':{p:a['source_hashes'][p] for p in a['sources'].values()},'new_sample_months':len(labels),'predictions':len(pred),'fit_calls':0,'raw_Qobs_exported':False,'quality_limits':a['quality_limit']});seal(SCORE);event('SCORING_COMPLETE',stations=len({k[0] for k in labels}),months=len(labels),predictions=len(pred),fit_calls=0);print(json.dumps([s for s in summary if s['region']=='ALL'],indent=2))
