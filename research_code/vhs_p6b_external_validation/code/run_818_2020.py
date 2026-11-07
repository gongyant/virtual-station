"""Conditional2020 frozen inference and separate scoring, only after60-month legacy parity."""
import sys,json,csv,calendar,math,time,importlib.util
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,cw,sha,readcsv
PR=R/'runs/P6B_ID818_2020';SC=R/'runs/P6B_ID818_2020_SCORING'
def seal(p):(p/'SHA256SUMS.txt').write_text(''.join(f'{sha(f)}  {f.relative_to(p).as_posix()}\n' for f in sorted(p.rglob('*')) if f.is_file() and f.name!='SHA256SUMS.txt'),encoding='utf-8')
def verify(p):
 for line in (p/'SHA256SUMS.txt').read_text().splitlines():h,n=line.split('  ',1);assert sha(p/n)==h,n
def event(name,**kw):
 with (R/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'event':name,**kw})+'\n')
if sys.argv[1]=='freeze2020':
 parity=jl(R/'driver/ARCO_LEGACY_PARITY_RESULT.json');assert parity['same_processing_2020_admitted'] and parity['months_passed']==60,'LEGACY_PARITY_NOT_ADMITTED';assert not (R/'P6B_2020_ADMISSION_FROZEN.json').exists()
 src=L/'vhs_r2u1_p6a/external/CAMELS_CAMELS_CH_obs_based_2304.csv';q=readcsv(src);presence=[r for r in q if r['date'].startswith('2020-')];assert len(presence)==366 and len({r['date'] for r in presence})==366 and all(r['discharge_vol(m3/s)'].strip().lower() not in {'','nan','na','-999','-999.0','null'} for r in presence)
 met=[r for r in jl(R/'driver/ARCO_LEGACY_MONTHLY_MET_2015_2020.json') if r['date'].startswith('2020-')];old=readcsv(R/'driver/MET_ONLY_2018_2019.json') if False else jl(R/'driver/MET_ONLY_2018_2019.json')['818'];lag=next(r for r in old if r['date']=='2019-12');met=[lag,*met];assert len(met)==13;jw(R/'driver/ID818_2020_MET_ONLY.json',met)
 parent=jl(R/'P6B_FROZEN_PROTOCOL.json');models=[r for r in parent['frozen_models'] if r['gauge_id']==818];assert len(models)==2
 protocol={'parent_protocol_hash':sha(R/'P6B_FROZEN_PROTOCOL.json'),'parity_result_hash':sha(R/'driver/ARCO_LEGACY_PARITY_RESULT.json'),'gauge_id':818,'official_id':'FOEN2304','period':['2020-01','2020-12'],'frozen_models':models,'met_hash':sha(R/'driver/ID818_2020_MET_ONLY.json'),'new_Q_file':str(src),'new_Q_hash':sha(src),'quality':'PROVIDER_CURATED_NO_DAILY_FLAGS_DESCRIPTIVE','expected_Q_days':366,'nominal_intervals':[80,90],'scores_seen':False,'fit_calls_allowed':0,'task':'RECONSTRUCTION_WITH_OBSERVED_MET','driver_2020_MIR_change':'documented by source, interpretation caveat; not Q-calibrated correction','Q_used_as_feature':False}
 jw(R/'P6B_2020_ADMISSION_FROZEN.json',protocol);event('ID818_2020_ADMISSION_FROZEN',protocol_hash=sha(R/'P6B_2020_ADMISSION_FROZEN.json'),full_overlap_passed=60);print('2020_ADMISSION_FROZEN')
elif sys.argv[1]=='predict2020':
 assert not PR.exists();PR.mkdir();a=jl(R/'P6B_2020_ADMISSION_FROZEN.json');assert sha(R/'driver/ID818_2020_MET_ONLY.json')==a['met_hash'];reads=[]
 def audit(e,args):
  if e=='open' and isinstance(args[0],(str,bytes)):
   name=str(args[0]);reads.append(name)
   if any(v in name for v in ['CAMELS_CH_obs_based','_file5.txt','D_gauges','monthly_streamflow_mean.csv']):raise RuntimeError('PREDICTION_ROLE_Q_READ_DENIED')
 sys.addaudithook(audit);sys.path.insert(0,str(P4/'code'));from inference import load_model
 met=jl(R/'driver/ID818_2020_MET_ONLY.json');pred=[]
 for mid in ['C0+PT','P2-L1']:
  path=P4/'models/V2/ID_818'/mid.replace('+','_');m=load_model(path);assert m.hash==next(r for r in a['frozen_models'] if Path(r['path']).name==path.name)['model_hash'];assert m.meta['actual_train_end']<'2020-01'
  for mo in range(1,13):pred.append({'experiment':'PUBLIC_DATA_P6B_EXTERNAL_TEMPORAL_VALIDATION','sample_id':f'LAMAH_CE_PUBLIC_V1:818:2020-{mo:02d}','prediction_kind':'POST2017_TEMPORAL_HOLDOUT_QUALIFIED_DESCRIPTIVE','task':'RECONSTRUCTION_WITH_OBSERVED_MET','training_snapshot':m.meta['snapshot_id'],'actual_train_end':m.meta['actual_train_end'],**m.predict_month(met,2020,mo)})
 cw(PR/'P6B_2020_PREDICTIONS_WITHOUT_QOBS.csv',pred);jw(PR/'COMMITMENT.json',{'admission_hash':sha(R/'P6B_2020_ADMISSION_FROZEN.json'),'prediction_file_hash':sha(PR/'P6B_2020_PREDICTIONS_WITHOUT_QOBS.csv'),'code_hash':sha(__file__),'records':24,'models_loaded':2,'sample_months':12,'fit_calls':0,'Q_read_by_predictor':False,'predictions_sealed_before_scoring':True});jw(PR/'PREDICTION_READ_AUDIT.json',{'opened_files':sorted(set(reads)),'Q_label_read_attempts':0});seal(PR);event('ID818_2020_PREDICTIONS_SEALED',records=24,fit_calls=0,seal_hash=sha(PR/'SHA256SUMS.txt'));print('SEALED_24_PREDICTIONS_FIT0')
elif sys.argv[1]=='score2020':
 verify(PR);commit=jl(PR/'COMMITMENT.json');a=jl(R/'P6B_2020_ADMISSION_FROZEN.json');assert commit['admission_hash']==sha(R/'P6B_2020_ADMISSION_FROZEN.json') and commit['code_hash']==sha(__file__);assert not SC.exists();SC.mkdir();event('ID818_2020_SCORING_STARTED',prediction_seal=sha(PR/'SHA256SUMS.txt'));assert sha(a['new_Q_file'])==a['new_Q_hash'];groups={}
 for r in readcsv(a['new_Q_file']):
  if r['date'].startswith('2020-'):groups.setdefault(r['date'][:7],[]).append(float(r['discharge_vol(m3/s)']))
 labels={}
 for dt,vals in groups.items():assert len(vals)==calendar.monthrange(2020,int(dt[5:]))[1] and all(math.isfinite(v) and v>=0 for v in vals);labels[dt]=sum(vals)/len(vals)
 assert len(labels)==12
 spec=importlib.util.spec_from_file_location('frozen_p6a_metrics',L/'vhs_r2u1_p6a/code/p6_pipeline.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 rows=[];ci=[];comparison=[];pred=readcsv(PR/'P6B_2020_PREDICTIONS_WITHOUT_QOBS.csv')
 for mid in ['C0+PT','P2-L1']:
  for sub in ['ALL','2020','DJF','MAM','JJA','SON','MAY_JUNE']:
   seasons={'DJF':[12,1,2],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'MAY_JUNE':[5,6]};rr=[r for r in pred if r['model_id']==mid and (sub in ['ALL','2020'] or int(r['date'][5:]) in seasons[sub])];y=np.array([labels[r['date']] for r in rr])
   for variant,key in [('raw','q_hat_raw'),('nonnegative','q_hat_nonnegative')]:rows.append({'gauge_id':818,'model_id':mid,'quality_tier':a['quality'],'period':'2020','subset':sub,'prediction':variant,**module.metrics(y,[float(r[key]) for r in rr])})
   for lev in [80,90]:
    lo=np.array([float(r[f'lower{lev}']) for r in rr]);hi=np.array([float(r[f'upper{lev}']) for r in rr]);alpha=1-lev/100;ci.append({'gauge_id':818,'model_id':mid,'subset':sub,'nominal':lev/100,'n':len(rr),'coverage':float(np.mean((y>=lo)&(y<=hi))),'mean_width':float(np.mean(hi-lo)),'interval_score':float(np.mean(hi-lo+2/alpha*np.maximum(lo-y,0)+2/alpha*np.maximum(y-hi,0)))})
 for sub in ['ALL','2020','DJF','MAM','JJA','SON','MAY_JUNE']:
  c=next(r for r in rows if r['model_id']=='C0+PT' and r['subset']==sub and r['prediction']=='raw');l=next(r for r in rows if r['model_id']=='P2-L1' and r['subset']==sub and r['prediction']=='raw');comparison.append({'gauge_id':818,'subset':sub,'n':c['n'],'MSE_skill':1-l['MSE']/c['MSE'] if c['MSE']>0 else None,'MSE_C0PT':c['MSE'],'MSE_L1':l['MSE']})
 cw(SC/'P6B_2020_METRICS.csv',rows);cw(SC/'P6B_2020_INTERVALS.csv',ci);cw(SC/'P6B_2020_COMPARISON.csv',comparison);jw(SC/'SCORING_PROVENANCE.json',{'prediction_seal':sha(PR/'SHA256SUMS.txt'),'admission_hash':commit['admission_hash'],'Q_source_hash':a['new_Q_hash'],'metrics_implementation_hash':sha(L/'vhs_r2u1_p6a/code/p6_pipeline.py'),'fit_calls':0,'raw_Qobs_exported':False,'scored_months':12,'quality':a['quality']});seal(SC);event('ID818_2020_SCORING_COMPLETE',records=24,months=12,fit_calls=0);print(json.dumps({'overall':[r for r in rows if r['subset']=='ALL' and r['prediction']=='raw'],'comparisons':comparison,'intervals':[r for r in ci if r['subset']=='ALL']},indent=2))
