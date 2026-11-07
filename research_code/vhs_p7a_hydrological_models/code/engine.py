"""P7A <=2017-only expanding-window model comparison. No P6 labels are importable."""
from common import *
import sys,types,importlib.util,time,collections,traceback
SNAP='P7A_TRAINING_CACHE_2017';AUDIT_READS=set();FIT_LOG=[]
def admit_input(x):
 assert x.snapshot==SNAP and len(x.ids)==len(set(x.ids)) and len(x.ids)>0,'INPUT_IDENTITY'
 assert all(int(i[-7:-3])<=2017 for i in x.ids),'FUTURE_Q_OR_FEATURE_ID_FORBIDDEN'
 assert all(np.isfinite(v).all() and len(v)==len(x.ids) for v in x.values.values()),'NONFINITE_FEATURE'
def admit_training(x,y):
 admit_input(x);assert len(y)==len(x.ids) and np.isfinite(y).all() and (y>=0).all(),'INVALID_TRAIN_LABEL'
def admit_metric(y,p,synthetic):
 assert len(y)==len(p) and np.isfinite(y).all() and np.isfinite(p).all()
rt=types.ModuleType('public_runtime');rt.admit_input=admit_input;rt.admit_training_matrix=admit_training;rt.admit_metric=admit_metric
sys.modules['public_runtime']=rt
sys.path.insert(0,str(LAB/'code/vendor_public'))
spec=importlib.util.spec_from_file_location('frozen_p2_math',LAB/'p2_antecedent_snow_features/P2_MODEL_CODE/models.py')
old=importlib.util.module_from_spec(spec);sys.modules[spec.name]=old;spec.loader.exec_module(old)
old.FIELDS['P7-SL']=('P','T','L1','COLD_L1');old.FIELDS['P7-MEM']=('P','T','MEM')
from vhs_sci.evaluate import metric_bundle
def metric(y,p):
 m=metric_bundle(y,p,synthetic=False)
 return {**{k:v['value'] for k,v in m.items()},'undefined_reason':';'.join(f'{k}:{v["reason_code"]}' for k,v in m.items() if v['reason_code']),'n':len(y),'Qobs_mean':float(np.mean(y)),'Qsim_mean':float(np.mean(p))}
def install_training_read_boundary():
 allowed={str((ROOT/p).resolve()).lower() for p in ['cache/TRAINING_ONLY_2017.json','P7A_FROZEN_PROTOCOL.json','evidence/FREEZE.json','evidence/FOLDS_DETAIL.json','evidence/SOURCE_PINS.json','P7A_CV_PREDICTIONS.csv','evidence/FIT_CALLS.csv','P7A_PROMOTION_DECISION.json']}
 allowed.add(str((P4/'source/observation_metadata.csv').resolve()).lower())
 def hook(event,args):
  if event!='open' or not isinstance(args[0],(str,bytes)):return
  p=pathlib.Path(args[0]).resolve();s=str(p).lower();mode=args[1] or ''
  reading=isinstance(mode,str) and ('r' in mode or mode=='')
  if not reading:return
  if 'vhs_workbuddy' in s:raise PermissionError('TEACHER_WORKSPACE_FORBIDDEN')
  if str(LAB).lower() in s:
   if s in allowed or s.startswith(str(ROOT/'code').lower()) or s.startswith(str(ROOT/'models').lower()) or s.startswith(str(LAB/'code/vendor_public').lower()) or s==str(LAB/'p2_antecedent_snow_features/P2_MODEL_CODE/models.py').lower():AUDIT_READS.add(str(p))
   else:raise PermissionError('TRAINING_ROLE_READ_DENIED: '+str(p))
 sys.addaudithook(hook)
def inputs(rs,rho=.25):
 return old.Inputs(tuple(r['sample_id'] for r in rs),np.array([r['year'] for r in rs]),np.array([r['month'] for r in rs]),{**{k:np.array([r[k] for r in rs],float) for k in ['P','T','L1','COLD_L1']},'MEM':np.array([r[f'MEM_{rho}'] for r in rs])},SNAP,False)
def fit_predict(model,train,valid,alpha=100,rho=.25,context=None):
 t=time.perf_counter();y=np.array([r['Q'] for r in train]);tx=inputs(train,rho);vx=inputs(valid,rho)
 if model=='C0':
  admit_training(tx,y);cl=np.array([y[tx.months==m].mean() for m in range(1,13)]);pred=cl[vx.months-1]
  record={'model_id':model,'climate':cl.tolist(),'train_ids_hash':digest(tx.ids),'fields':[],'alpha':None}
 else:
  obj=old.MonthlyWeatherRidge(model,alpha=float(alpha)).fit(tx,y);pred=obj.predict(vx);record=obj.record();record.update(alpha=alpha,rho=rho if model=='P7-MEM' else None)
 FIT_LOG.append({**(context or {}),'model_id':model,'alpha':None if model=='C0' else alpha,'rho':rho if model=='P7-MEM' else None,'train_n':len(train),'validation_n':len(valid),'train_max_date':max(r['date'] for r in train),'validation_min_date':min(r['date'] for r in valid),'train_ids_hash':digest(tx.ids),'validation_ids_hash':digest(vx.ids),'elapsed_s':time.perf_counter()-t})
 return pred,record
def tune(model,train,cutoff,ctx):
 trace=[]
 for rho in ([.25,.5,.75] if model=='P7-MEM' else [.25]):
  for a in [.01,.1,1,10,100]:
   loss=[]
   for c in [cutoff-6,cutoff-4,cutoff-2]:
    tx=[r for r in train if r['year']<=c];vx=[r for r in train if c<r['year']<=c+2]
    assert len(vx)==24 and max(r['year'] for r in tx)<min(r['year'] for r in vx)
    pred,_=fit_predict(model,tx,vx,a,rho,{**ctx,'level':'inner','inner_cutoff':c})
    loss.append(float(np.mean((pred-np.array([r['Q'] for r in vx]))**2)))
   trace.append({'rho':rho if model=='P7-MEM' else None,'alpha':a,'block_MSE':loss,'mean':float(np.mean(loss)),'SE':float(np.std(loss,ddof=1)/np.sqrt(3))})
 best=min(trace,key=lambda r:(r['mean'],r['alpha'],r['rho'] or 0));threshold=best['mean']+best['SE'];tol=1e-12*max(1,abs(threshold))
 eligible=[r for r in trace if r['mean']<=threshold+tol];chosen=sorted(eligible,key=lambda r:(-r['alpha'],r['rho'] or 0))[0]
 return chosen,{'candidates':trace,'best':best,'oneSE_threshold':threshold,'selection':chosen,'rule':'largest alpha within one SE; then shortest memory rho'}
def unit_tests():
 checks=[]
 def ck(n,v):checks.append({'name':n,'passed':bool(v)});assert v,n
 ck('calendar_lag_cross_year',prev('1994-01')=='1993-12')
 w={f'{y}-{m:02d}':{'P':float(y-1980+m),'T':0} for y in range(1981,1985) for m in range(1,13)}
 mm=memory(w,.75);ck('24_prior_month_warmup',min(mm)=='1983-01')
 w2={k:dict(v) for k,v in w.items()};w2['1984-01']['P']=99999
 ck('future_weather_cannot_change_past_memory',all(mm[k]==memory(w2,.75)[k] for k in mm if k<='1984-01'))
 w2['1982-12']['P']=None;ck('missing_weather_resets_state',not memory(w2,.75))
 rs=[]
 for y in range(1983,1998):
  for m in range(1,13):
   p=(y-1980)*(1+m/20);l=(y-1980)*(2+m/20);t=m+(y%4)
   rs.append({'sample_id':f'PUBLIC_SYNTHETIC_TEST:{y}-{m:02d}','date':f'{y}-{m:02d}','year':y,'month':m,'Q':m+(.2*(y-1980)),'P':p,'T':t,'L1':l,'COLD_L1':l if m in [11,12,1,2,3] else 0,**{f'MEM_{r}':l for r in [.25,.5,.75]}})
 tx=inputs(rs);y=np.array([r['Q'] for r in rs]);o=old.MonthlyWeatherRidge('P7-SL',100).fit(tx,y);z=o.transform(tx)
 ck('SL_exact_requested_Icold_zL1',np.allclose(z[:,3],z[:,2]*np.isin(tx.months,[11,12,1,2,3]),rtol=0,atol=1e-13))
 ck('SL_one_extra_coefficient',len(o.beta)==4)
 ck('month_anomalies_train_centered',max(abs(z[tx.months==m].mean(0)).max() for m in range(1,13))<1e-12)
 ck('solver_matches_closed_form',np.allclose(o.beta,np.linalg.solve(z.T@z+100*np.eye(4),z.T@(y-o.climate[tx.months-1])),atol=1e-12))
 pred=o.predict(tx);ck('additive_reconstruction',np.max(abs(pred-(o.climate[tx.months-1]+z@o.beta)))<1e-12)
 # No test label is in predict signature, nor in feature values.
 ck('prediction_no_label_argument',list(__import__('inspect').signature(o.predict).parameters)==['features_test'])
 bad=inputs(rs);bad.ids=tuple(i.replace('1983','2020') for i in bad.ids)
 try:admit_input(bad);denied=False
 except AssertionError:denied=True
 ck('future_label_ids_rejected',denied)
 for path in [LAB/'vhs_p6d_failure_diagnostics/P6D_MONTHLY_PAIRED_ERRORS.csv',LAB/'vhs_p6b_external_validation/P6B_ALL_STATION_METRICS.csv']:
  try:open(path).close();denied=False
  except PermissionError:denied=True
  ck('training_role_denies_'+path.name,denied)
 put(ROOT/'P7A_UNIT_TEST_RESULTS.json',{'passed':len(checks),'failed':0,'checks':checks,'classification':'SYNTHETIC_ENGINE_CHECKS_NOT_HYDROLOGICAL_RESULTS'})
 old.FIT_EVENTS.clear();FIT_LOG.clear()
def main():
 if (ROOT/'SHA256SUMS.txt').exists():raise FileExistsError('FROZEN_P7A_NO_REFIT_OR_OVERWRITE; set VHS_P7A_OUTPUT to a fresh directory')
 install_training_read_boundary();protocol=readj(ROOT/'P7A_FROZEN_PROTOCOL.json');freeze=readj(ROOT/'evidence/FREEZE.json')
 assert sha(ROOT/'P7A_FROZEN_PROTOCOL.json')==freeze['protocol_hash']
 assert sha(ROOT/'cache/TRAINING_ONLY_2017.json')==protocol['training_cache_sha256']
 unit_tests();data=readj(ROOT/'cache/TRAINING_ONLY_2017.json');folds=readj(ROOT/'evidence/FOLDS_DETAIL.json')
 region={int(r['gauge_id']):(r['region'],r['macro']) for r in rows(P4/'source/observation_metadata.csv')}
 predrows=[];params=[];tunes=[];failures=[];attempt={'attempt_id':'P7A-'+utc().replace(':',''),'started':utc(),'status':'RUNNING','protocol_hash':freeze['protocol_hash']}
 with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(attempt)+'\n')
 if '--resume-summary-only' in sys.argv:
  # Resume the bookkeeping failure after fitting; never refit or change predictions.
  predrows=rows(ROOT/'P7A_CV_PREDICTIONS.csv')
  for r in predrows:
   for k in ['gauge_id','year','month']:r[k]=int(r[k])
   for k in ['qsim_raw','qsim_nonnegative']:r[k]=float(r[k])
  FIT_LOG.extend(rows(ROOT/'evidence/FIT_CALLS.csv'));failures=[f for f in folds if not f['admitted']]
  assert len(predrows)==sum(f['validation_n']*len(MODELS) for f in folds if f['admitted'])
  attempt['resumed_without_any_refit']=True
 else:
  for j,fold in enumerate(folds):
   if not fold['admitted']:failures.append(fold);continue
   g=fold['gauge_id'];cutoff=fold['cutoff'];rs=data[str(g)];train=[r for r in rs if r['year']<=cutoff];valid=[r for r in rs if cutoff<r['year']<=cutoff+2];ctx={'gauge_id':g,'fold_id':fold['fold_id']}
   for model in MODELS:
    chosen,trace=({'alpha':100,'rho':None},None) if model=='C0' else tune(model,train,cutoff,ctx)
    p,record=fit_predict(model,train,valid,chosen['alpha'],chosen['rho'] or .25,{**ctx,'level':'outer'})
    params.append({**ctx,'record':record,'train_start':train[0]['date'],'train_end':train[-1]['date'],'test_start':valid[0]['date'],'test_end':valid[-1]['date']})
    if trace:tunes.append({**ctx,'model_id':model,**trace})
    ph=digest(record)
    for r,z in zip(valid,p):predrows.append({**ctx,'model_id':model,'sample_id':r['sample_id'],'date':r['date'],'year':r['year'],'month':r['month'],'qsim_raw':float(z),'qsim_nonnegative':float(max(z,0)),'parameter_hash':ph,'prediction_kind':'TRAIN_PERIOD_FORWARD_VALIDATION','region':region[g][0],'macro':region[g][1]})
   if j%12==0:print('outer station-fold',j+1,'/',len(folds),'fits',len(FIT_LOG),flush=True)
  csvout(ROOT/'P7A_CV_PREDICTIONS.csv',predrows);put(ROOT/'evidence/OUTER_PARAMETERS.json',params);put(ROOT/'evidence/INNER_CV_LOG.json',tunes);csvout(ROOT/'evidence/FIT_CALLS.csv',FIT_LOG);put(ROOT/'evidence/REJECTED_COVERAGE_FOLDS.json',failures)
 # Final metrics are a separate step after the complete predictions have been sealed.
 put(ROOT/'evidence/CV_PREDICTIONS_SEALED.json',{'sha256':sha(ROOT/'P7A_CV_PREDICTIONS.csv'),'n':len(predrows),'created_utc':utc(),'future_Q_read':False})
 metrows=[];seasonrows=[];lookup={(g,r['sample_id']):r['Q'] for g,rs in data.items() for r in rs}
 for g in GAUGES:
  for subset,months in [('ALL',list(range(1,13))),('DJF',[1,2,12]),('MAY_JUNE',[5,6])]:
   for model in MODELS:
    rr=[r for r in predrows if r['gauge_id']==g and r['model_id']==model and r['month'] in months]
    if not rr:continue
    y=np.array([lookup[(str(g),r['sample_id'])] for r in rr]);p=np.array([r['qsim_raw'] for r in rr]);base={r['sample_id']:r for r in predrows if r['gauge_id']==g and r['model_id']=='P2-L1'}
    b=np.array([base[r['sample_id']]['qsim_raw'] for r in rr]);den=np.mean((b-y)**2)
    item={'gauge_id':g,'macro':region[g][1],'model_id':model,'subset':subset,**metric(y,p),'skill_vs_P2L1':float(1-np.mean((p-y)**2)/den) if den>0 else None,'negative_predictions':int(sum(p<0)),'validation_years':';'.join(map(str,sorted({r['year'] for r in rr})))}
    (metrows if subset=='ALL' else seasonrows).append(item)
 csvout(ROOT/'P7A_STATION_MODEL_METRICS.csv',metrows);csvout(ROOT/'P7A_SEASONAL_COMPARISON.csv',seasonrows)
 blockrows=[];yearrows=[]
 for fold in folds:
  if not fold['admitted']:continue
  g=fold['gauge_id'];rr=[r for r in predrows if r['fold_id']==fold['fold_id']];base={r['sample_id']:r for r in rr if r['model_id']=='P2-L1'}
  for model in MODELS:
   for year in ['ALL']+sorted({r['year'] for r in rr}):
    a=[r for r in rr if r['model_id']==model and (year=='ALL' or r['year']==year)];y=np.array([lookup[(str(g),r['sample_id'])] for r in a]);p=np.array([r['qsim_raw'] for r in a]);b=np.array([base[r['sample_id']]['qsim_raw'] for r in a]);den=np.mean((b-y)**2)
    item={'gauge_id':g,'fold_id':fold['fold_id'],'cutoff':fold['cutoff'],'year':year,'model_id':model,**metric(y,p),'skill_vs_P2L1':float(1-np.mean((p-y)**2)/den) if den else None}
    (blockrows if year=='ALL' else yearrows).append(item)
 csvout(ROOT/'P7A_OUTER_BLOCK_METRICS.csv',blockrows);csvout(ROOT/'P7A_YEARLY_METRICS.csv',yearrows)
 promotion={};summary=[]
 for model in ['P7-SL','P7-MEM']:
  rr=[r for r in metrows if r['model_id']==model];skills=np.array([r['skill_vs_P2L1'] for r in rr]);winter=[r['skill_vs_P2L1'] for r in seasonrows if r['model_id']==model and r['subset']=='DJF']
  blocks={str(c):float(np.mean([r['skill_vs_P2L1'] for r in blockrows if r['model_id']==model and r['cutoff']==c])) for c in protocol['outer_cutoffs']}
  macros={m:float(np.mean([r['skill_vs_P2L1'] for r in rr if r['macro']==m])) for m in sorted({r['macro'] for r in rr})}
  checks={'station_n':len(rr)>=20,'mean_skill':float(skills.mean())>=.01,'median':float(np.median(skills))>0,'positive_fraction':float(np.mean(skills>0))>=2/3,'blocks':sum(v>0 for v in blocks.values())>=4,'winter_floor':float(np.mean(winter))>=-.02,'macro_floor':min(macros.values())>=-.02}
  item={'model_id':model,'promoted':all(checks.values()),'checks':checks,'station_n':len(rr),'positive_stations':int(sum(skills>0)),'station_mean_skill':float(skills.mean()),'station_median_skill':float(np.median(skills)),'winter_mean_skill':float(np.mean(winter)),'macro_skill':macros,'block_skill':blocks,'negative_NSE_stations':sum(r['NSE'] is not None and r['NSE']<0 for r in rr)}
  promotion[model]=item;summary.append(item)
 put(ROOT/'P7A_PROMOTION_DECISION.json',promotion)
 ablation=[]
 for model,base in [('P7-SL','P2-L1'),('P7-MEM','C0+PT')]:
  for g in GAUGES:
   a=next(r for r in metrows if r['model_id']==model and r['gauge_id']==g);b=next(r for r in metrows if r['model_id']==base and r['gauge_id']==g)
   ablation.append({'gauge_id':g,'full_model':model,'removed_feature_reference':base,'ablation_method':'reuse same-fold identical-support fitted baseline; no extra fit','full_MSE':a['MSE'],'ablated_MSE':b['MSE'],'feature_skill':1-a['MSE']/b['MSE'],'full_beta_n':4 if model=='P7-SL' else 3,'ablated_beta_n':3 if base=='P2-L1' else 2,'rho_discrete_candidates':3 if model=='P7-MEM' else 0})
 csvout(ROOT/'P7A_ABLATION_RESULTS.csv',ablation)
 status={'experiment':'PUBLIC_DATA_EXPLORATORY_P7A','status':'TRAIN_PERIOD_CV_COMPLETED','started_utc':attempt['started'],'completed_utc':utc(),'trained_stations':len(GAUGES),'outer_fits':sum(r['level']=='outer' for r in FIT_LOG),'inner_fits':sum(r['level']=='inner' for r in FIT_LOG),'all_fits':len(FIT_LOG),'per_model_outer':dict(collections.Counter(r['model_id'] for r in FIT_LOG if r['level']=='outer')),'CV_prediction_records':len(predrows),'unique_validation_station_months':len({(r['gauge_id'],r['sample_id']) for r in predrows}),'rejected_coverage_folds':len(failures),'future_Q_reads':0,'train_max_date':max(r['train_max_date'] for r in FIT_LOG),'promotion':promotion,'historical_exposed_scoring':'NOT_RUN_PENDING_PROMOTION_HANDOFF','future_holdout':'FUTURE_HOLDOUT_NOT_AVAILABLE','default_model':'P2-L1_UNCHANGED','production_authorization':'NOT_GRANTED'}
 put(ROOT/'evidence/TRAINING_ROLE_AUDIT.json',{'read_boundary':'deny all public Lab except pinned <=2017 cache/protocol/metadata and frozen code; teacher workspace denied','opened_public_files':sorted(AUDIT_READS),'future_Q_reads':0,'label_cache_hash_verified':True,'training_all_labels_max_year':2017,'protocol_hash':freeze['protocol_hash']})
 put(ROOT/'P7A_FINAL_STATUS.json',status)
 with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({**attempt,'status':'CV_COMPLETED','completed':utc(),'fits':len(FIT_LOG)})+'\n')
 print(json.dumps(status,ensure_ascii=False),flush=True)
if __name__=='__main__':
 try:main()
 except Exception:
  if not (ROOT/'SHA256SUMS.txt').exists():(ROOT/'evidence/TRAINING_FAILURE.txt').write_text(traceback.format_exc(),encoding='utf-8')
  raise
