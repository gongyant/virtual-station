"""Freeze forward validation BEFORE any P7 fitting or scoring."""
from common import *
import calendar,collections,shutil,platform,sys
assert not (ROOT/'P7A_FROZEN_PROTOCOL.json').exists(),'Already frozen; do not overwrite'
for r in [ROOT,WEB]:r.mkdir(exist_ok=True,parents=True)
d=LAB/'vhs_p6d_failure_diagnostics'
history=readj(d/'evidence/HISTORY_BEFORE.json')
for line in (d/'SHA256SUMS.txt').read_text().splitlines():
 h,rel=line.split('  ',1);history[str(d/rel)]=h
history[str(d/'SHA256SUMS.txt')]=sha(d/'SHA256SUMS.txt')
check=verify_history(history);assert not check['failed'],check['failed'][:5]
for r in [ROOT,WEB]:put(r/'evidence/HISTORY_BEFORE.json',history);put(r/'evidence/HISTORY_INITIAL_CHECK.json',check)
snap=readj(P4/'source/SNAPSHOT.json');features=rows(P4/'source/features.csv');weather=rows(P4/'source/weather.csv')
metadata=rows(P4/'source/observation_metadata.csv')
print('metadata columns',list(metadata[0]),flush=True)
pins={str(P4/'source'/n):sha(P4/'source'/n) for n in ['SNAPSHOT.json','features.csv','weather.csv','observation_metadata.csv']}
cache={};admission=[];folds=[];modelregistry=[];sourcechecks=[]
for g in GAUGES:
 metas=[readj(P4/f'models/V2/ID_{g}/{m}/model.json') for m in ['C0_PT','P2-L1']]
 assert metas[0]['train_ids']==metas[1]['train_ids']
 for model,meta in zip(['C0_PT','P2-L1'],metas):
  path=P4/f'models/V2/ID_{g}/{model}/model.json';pins[str(path)]=sha(path)
  a=path.parent/'arrays.npz';pins[str(a)]=sha(a)
  modelregistry.append({'gauge_id':g,'model_id':meta['model_id'],'version':meta['version'],'snapshot_id':meta['snapshot_id'],'path':str(path),'sha256':sha(path),'arrays_sha256':sha(a),'actual_train_start':meta['actual_train_start'],'actual_train_end':meta['actual_train_end'],'train_cutoff':meta['train_cutoff'],'n':len(meta['train_ids']),'fields':meta['fields'],'unit':'m3/s public observed discharge','status':'FROZEN_REFERENCE_NOT_OVERWRITTEN'})
 qp=pathlib.Path(snap['source_paths'][str(g)]['Q']);assert sha(qp)==snap['source_files'][str(qp)]
 groups=collections.defaultdict(list);future_dates=[]
 # Date checked BEFORE numeric Q conversion. Source is original LamaH, never eHYD/P6.
 with qp.open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f,delimiter=';'):
   y,m,day=int(r['YYYY']),int(r['MM']),int(r['DD'])
   if y>2017:future_dates.append(f'{y}-{m:02d}-{day:02d}');continue
   groups[f'{y}-{m:02d}'].append((day,r['qobs'],r['ckhs']))
 assert not future_dates,'SOURCE_CONTAINS_FUTURE_Q_DATES_STOP'
 q={}
 for date,rs in groups.items():
  y,m=map(int,date.split('-'));n=calendar.monthrange(y,m)[1]
  if len(rs)!=n or len({r[0] for r in rs})!=n:continue
  try:vals=[float(r[1]) for r in rs if r[2]=='1']
  except ValueError:continue
  if len(vals)==n and all(np.isfinite(v) and v>=0 for v in vals):q[date]=sum(vals)/n
 ids=metas[0]['train_ids'];labels={i:q[i[-7:]] for i in ids}
 assert digest(labels)==metas[0]['train_label_hash'],'P4_LABEL_REPRODUCTION_MISMATCH'
 sourcechecks.append({'gauge_id':g,'Q_source':str(qp),'sha256':sha(qp),'latest_Q_date':max(groups),'future_Q_rows':len(future_dates),'p4_label_hash_exact':True})
 w={}
 for r in weather:
  if int(r['gauge_id'])!=g or r['date']>'2017-12':continue
  w[r['date']]={k:float(r[k]) if r[k] else None for k in ['P','T']}
 mem={str(r):memory(w,r) for r in [.25,.5,.75]}
 fs=[]
 for r in features:
  if int(r['gauge_id'])!=g or r['sample_id'] not in labels:continue
  date=r['date'];assert date<='2017-12' and r['L1_date']==prev(date)
  assert abs(float(r['L1'])-w[prev(date)]['P'])<1e-9
  if not all(date in mm for mm in mem.values()):continue
  fs.append({'sample_id':r['sample_id'],'date':date,'year':int(r['year']),'month':int(r['month']),'Q':labels[r['sample_id']],'P':float(r['P']),'T':float(r['T']),'L1':float(r['L1']),'COLD_L1':float(r['L1']) if int(r['month']) in [11,12,1,2,3] else 0.,**{f'MEM_{rho}':mm[date] for rho,mm in mem.items()}})
 fs.sort(key=lambda r:r['date']);cache[str(g)]=fs
 for cutoff in [1996,2001,2006,2011,2015]:
  train=[r for r in fs if r['year']<=cutoff];test=[r for r in fs if cutoff<r['year']<=cutoff+2]
  counts=collections.Counter(r['year'] for r in train);complete=sum(v==12 for v in counts.values())
  months=collections.Counter(r['month'] for r in train)
  inner=[]
  for c in [cutoff-6,cutoff-4,cutoff-2]:
   it=[r for r in train if r['year']<=c];iv=[r for r in train if c<r['year']<=c+2]
   good=sum(v==12 for v in collections.Counter(r['year'] for r in it).values())>=8 and len(iv)==24
   inner.append({'cutoff':c,'train_n':len(it),'validation_n':len(iv),'admitted':good})
  valid=complete>=10 and min(months.values())>=8 and len(test)==24 and all(x['admitted'] for x in inner)
  folds.append({'gauge_id':g,'fold_id':f'ID{g}_TRAIN_{cutoff}_VALID_{cutoff+1}_{cutoff+2}','cutoff':cutoff,'train_start':train[0]['date'],'train_end':train[-1]['date'],'train_n':len(train),'validation_start':f'{cutoff+1}-01','validation_end':f'{cutoff+2}-12','validation_n':len(test),'train_ids_hash':digest([r['sample_id'] for r in train]),'validation_ids_hash':digest([r['sample_id'] for r in test]),'inner':inner,'admitted':valid,'reason':'OK' if valid else 'PREDEFINED_COVERAGE_FAILURE_NO_SCORE_BASED_REMOVAL'})
 admission.append({'gauge_id':g,'old_train_start':metas[0]['actual_train_start'],'old_train_end':metas[0]['actual_train_end'],'old_n':len(ids),'common_start':fs[0]['date'],'common_end':fs[-1]['date'],'common_n':len(fs),'removed_for_24_month_weather_initialization':len(ids)-len(fs),'admitted_outer_folds':sum(f['admitted'] for f in folds if f['gauge_id']==g),'P_unit':'mm/month sum daily','T_unit':'degC month mean daily','Q_unit':'m3/s','lag':'previous calendar month','source_Q_quality':'all calendar days, finite nonnegative, ckhs=1','historical_Q_exposure':'2018-2020 USED_IN_P6_DESIGN_NOT_BLIND; 2021-2024 ARCHIVE_PARSED_NO_SCORES','new_future_holdout':'FUTURE_HOLDOUT_NOT_AVAILABLE'})
put(ROOT/'cache/TRAINING_ONLY_2017.json',cache)
put(ROOT/'evidence/SOURCE_CHECKS.json',sourcechecks)
put(ROOT/'evidence/SOURCE_PINS.json',pins)
put(ROOT/'P7A_REFERENCE_MODEL_REGISTRY.json',modelregistry)
csvout(ROOT/'P7A_DATA_ADMISSION.csv',admission)
put(ROOT/'evidence/FOLDS_DETAIL.json',folds);csvout(ROOT/'P7A_CV_FOLDS.csv',[{k:v for k,v in f.items() if k!='inner'} for f in folds])
protocol={'experiment':'PUBLIC_DATA_EXPLORATORY_P7A','created_utc':utc(),'task':'RECONSTRUCTION_WITH_OBSERVED_MET','gauges':GAUGES,'models':MODELS,'Q_cutoff':'2017-12','source_snapshot':snap['snapshot_base'],'training_cache_sha256':sha(ROOT/'cache/TRAINING_ONLY_2017.json'),'folds_hash':sha(ROOT/'evidence/FOLDS_DETAIL.json'),'alpha':[.01,.1,1,10,100],'rho':[.25,.5,.75],'cold_months':[11,12,1,2,3],'MEM':'M_t=rho*M_(t-1)+(1-rho)*P_t; feature=M_(t-1); initialize first valid month M=P; 24 prior valid months required; reset on gap; no Q state updates','SL':'C0+PT+beta_L*z(L1)+gamma*I_cold*z(L1); one extra beta, no extra month intercept','outer_cutoffs':[1996,2001,2006,2011,2015],'validation':'next two full calendar years; no random splits; common support for all five models','inner':'three expanding blocks cutoffs outer-6,-4,-2; next two years, >=8 complete training years; all transforms refit per block','fallback':'reject coverage-failed fold before scoring; minimum3 outer folds per station and20 stations for promotion; no score-based dropping','selection':'mean inner block raw MSE; best mean plus its sample SE; largest eligible alpha; MEM tie choose smallest eligible rho at that alpha','primary':'station equal mean MSE_skill vs newly fitted P2-L1 on same outer months','secondary':['NSE','KGE and components','RMSE','MAE','PBIAS','DJF same-calendar Jan Feb Dec','MAY_JUNE','raw and fixed nonnegative','year and region descriptive','loss concentration'],'promotion_design_thresholds_not_objective_truth':{'min_eligible_stations':20,'min_station_mean_skill':.01,'median_skill_strictly_positive':True,'fraction_positive_at_least':2/3,'positive_outer_blocks_at_least':4,'winter_station_mean_skill_at_least':-.02,'each_macro_mean_skill_at_least':-.02},'ablation':{'P7-SL_without_interaction':'reuse identical-support P2-L1 predictions','P7-MEM_without_memory':'reuse identical-support C0+PT predictions'},'historical_exposed_comparison':'only globally promoted new candidates, final models frozen first, predictions sealed without Q, separate scorer later; POST_HOC_EXPOSED_2018_2020_NOT_BLIND','default_model':'P2-L1_UNCHANGED','future_holdout':'NOT_AVAILABLE_NO_UNSEEN_Q_CERTIFIED','exposure':'P6D retrospective diagnoses informed these model choices; <=2017 historical prior experiments also exposed; CV is developmental evidence not final independent confirmation','training_label_role':'original public LamaH Q only, never P6/eHYD/teacher Q','environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform()},'software_permission_is_not_business_certification':True}
put(ROOT/'P7A_FROZEN_PROTOCOL.json',protocol)
put(ROOT/'evidence/FREEZE.json',{'protocol_hash':sha(ROOT/'P7A_FROZEN_PROTOCOL.json'),'frozen_before_any_P7_model_scoring':True,'created_utc':utc()})
print('PREPARED',len(folds),'folds',sum(f['admitted'] for f in folds),'admitted; history',check['passed'],'cache months',sum(map(len,cache.values())),flush=True)
