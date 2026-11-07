"""P6A role-separated admission -> frozen inference -> independent scoring. Never fit."""
import csv,json,hashlib,calendar,collections,math,sys,time
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');LAB=R.parent;P4=LAB/'p4_final_reconstruction';P=R/'p6';E=R/'external'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cr(p,delimiter=',',encoding='utf-8-sig',comments=False):
 with Path(p).open(encoding=encoding,newline='') as f:return list(csv.DictReader((l for l in f if not l.startswith('#') and l.strip()) if comments else f,delimiter=delimiter))
def cw(p,rows):
 with Path(p).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def prev(dt):y,m=map(int,dt.split('-'));return f'{y if m>1 else y-1}-{m-1 if m>1 else 12:02d}'
def attempt(event,**kw):
 with (P/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'event':event,'execution_UTC':time.strftime('%Y-%m-%dT%H:%M:%S%z'),**kw},allow_nan=False)+'\n')
def seal(folder):
 lines=[f'{sha(p)}  {p.relative_to(folder).as_posix()}\n' for p in sorted(folder.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'];(folder/'SHA256SUMS.txt').write_text(''.join(lines),encoding='utf-8')
def verify(folder):
 for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():h,n=line.split('  ',1);assert sha(folder/n)==h,n
def admit():
 assert not (P/'P6_ADMISSION_FROZEN.json').exists(),'ADMISSION_ALREADY_FROZEN'
 from pyproj import Geod
 protocol=jl(P/'P6_PROTOCOL_FROZEN.json');snapshot=jl(P4/'source/SNAPSHOT.json');oldstations=jl(R/'evidence/P6_ORIGINAL_STATION_METADATA.json');newstations=cr(E/'estreams_gauging_stations.csv')
 top=next(r for r in cr(E/'CAMELS_CAMELS_CH_topographic_attributes.csv',encoding='latin-1',comments=True) if r['gauge_id']=='2304')
 camels=cr(E/'CAMELS_CAMELS_CH_obs_based_2304.csv');assert 'discharge_vol(m3/s)' in camels[0]
 # Intake reduces Q tokens to support/missing booleans; no numerical Q passed to inference.
 qmeta=collections.defaultdict(list)
 for r in camels:
  dt=r['date'][:7]
  if '2018-01'<=dt<='2019-12':qmeta[dt].append({'date':r['date'],'present':r['discharge_vol(m3/s)'].strip().lower() not in {'','nan','na','-999','-999.0','null'}})
 met={};support=[];identity=[];sourcepin={};monthly_presence={};wanted={'CH000097','DEBY0480','DEBY0802'}
 # Derived monthly indices are intake evidence only, never the primary labels.
 with (E/'monthly_streamflow_mean.csv').open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);cols=reader.fieldnames
  print('ESTREAMS_MONTHLY_COLUMNS',cols[:6],flush=True)
  if any(k in cols for k in wanted):
   datekey=cols[0]
   for row in reader:
    dt=row[datekey][:7]
    if '2018-01'<=dt<='2020-12':monthly_presence[dt]={k:row.get(k,'').strip().lower() not in {'','nan','na','null'} for k in wanted}
  else:print('MONTHLY_LONG_FORMAT_NOT_USED',cols[:8])
 for old in oldstations:
  g=old['gauge_id'];country='CH' if g==818 else 'DE';nr=next(r for r in newstations if r['gauge_id']==old['official_gauge_id'] and r['gauge_country']==country)
  _,_,dist=Geod(ellps='WGS84').inv(*old['coordinates_wgs84'],float(nr['lon']),float(nr['lat']))
  row={'gauge_id':g,'LamaH_name':old['name'],'official_gauge_id':old['official_gauge_id'],'estreams_id':nr['basin_id'],'estreams_name':nr['gauge_name'],'provider':nr['gauge_provider'],'gauge_flag':nr['gauge_flag'],'old_area_km2':old['area_km2'],'new_area_km2':float(nr['area_official']),'coordinate_difference_m':dist,'source_start':nr['start_date'],'source_end':nr['end_date'],'daily_q_quality_flag':'ABSENT_IN_CAMELS_PROVIDER_RELEASE' if g==818 else 'OFFICIAL_CHECKED_Q_NOT_OBTAINED','migration_status':'NO_RELOCATION_ASSERTION_POSSIBLE_FROM_AVAILABLE_METADATA','identity_status':'EXACT_OFFICIAL_CODE_AREA_COORDINATE_MATCH' if dist<100 else 'EXACT_CODE_WITH_ROUNDED_COORDINATE_METADATA','name_discrepancy':g==688}
  if g==818:
   assert top['gauge_id']=='2304';_,_,dtop=Geod(ellps='WGS84').inv(*old['coordinates_wgs84'],float(top['gauge_lon']),float(top['gauge_lat']))
   row.update(CAMELS_coordinate_difference_m=dtop,CAMELS_name=top['gauge_name'],CAMELS_area_km2=float(top['area']),CAMELS_country=top['country']);assert dtop<=1000 and abs(float(top['area'])/old['area_km2']-1)<.02
  identity.append(row)
  src=Path(snapshot['source_paths'][str(g)]['MET']);assert sha(src)==snapshot['source_files'][str(src)];sourcepin[str(src)]=sha(src)
  daily=collections.defaultdict(list)
  for rr in cr(src,';'):
   dt=f'{int(rr["YYYY"]):04d}-{int(rr["MM"]):02d}'
   if '2017-12'<=dt<='2019-12':daily[dt].append(rr)
  mm={}
  for dt,rr in sorted(daily.items()):
   y,m=map(int,dt.split('-'));n=calendar.monthrange(y,m)[1];ps=[float(x['prec']) for x in rr];ts=[float(x['2m_temp_mean']) for x in rr];ok=len(rr)==n and len({int(x['DD']) for x in rr})==n and all(math.isfinite(v) and v>=0 and v!=-999 for v in ps) and all(math.isfinite(v) and v!=-999 for v in ts)
   mm[dt]={'date':dt,'gauge_id':g,'P':sum(ps) if ok else None,'T':sum(ts)/n if ok else None,'expected_days':n,'actual_days':len(rr),'met_complete':ok}
  met[str(g)]=[{k:r[k] for k in ['date','gauge_id','P','T']} for r in mm.values()]
  # Exact overlap with the frozen P4 monthly conversion confirms unchanged units/aggregation.
  oldweather=[w for w in cr(P4/'source/weather.csv') if int(w['gauge_id'])==g and w['date']=='2017-12'][0]
  assert mm['2017-12']['P']==float(oldweather['P']) and mm['2017-12']['T']==float(oldweather['T'])
  for y in [2018,2019]:
   for m in range(1,13):
    dt=f'{y}-{m:02d}';cur=mm[dt];met_ok=cur['met_complete'] and mm[prev(dt)]['met_complete'];qs=qmeta.get(dt,[]) if g==818 else [];expected=calendar.monthrange(y,m)[1];q_ok=g==818 and len(qs)==expected and len({r['date'] for r in qs})==expected and all(r['present'] for r in qs)
    support.append({'gauge_id':g,'date':dt,'expected_days':expected,'P_T_complete':met_ok,'previous_P_date':prev(dt),'Q_daily_rows':len(qs) if g==818 else None,'Q_full_day_support':q_ok,'estreams_monthly_present':monthly_presence.get(dt,{}).get(nr['basin_id']),'eligible':bool(met_ok and q_ok),'quality_tier':'PROVIDER_CURATED_NO_DAILY_FLAGS_DESCRIPTIVE' if g==818 else 'BLOCKED_PRIMARY_DAYCOUNT_QC_NOT_VERIFIED','reason':'ADMITTED_QUALIFIED_PUBLIC_OBSERVATIONS' if q_ok else 'OFFICIAL_DAILY_Q_NOT_OBTAINED; ESTREAMS_MONTHLY_DAYCOUNTS_UNAVAILABLE'})
 cw(P/'P6_STATION_IDENTITY.csv',[{k:r.get(k) for k in sorted(set().union(*(r.keys() for r in identity)))} for r in identity]);cw(P/'P6_MONTHLY_SUPPORT.csv',support);jw(P/'P6_MET_ONLY_INPUTS.json',met)
 sources=[E/'CAMELS_CH_RECORD.json',E/'CAMELS_CAMELS_CH_obs_based_2304.csv',E/'CAMELS_CAMELS_CH_topographic_attributes.csv',E/'ESTREAMS_1_4_RECORD.json',E/'estreams_gauging_stations.csv']
 sourcepin.update({str(p):sha(p) for p in sources})
 ids=[f'LAMAH_CE_PUBLIC_V1:{r["gauge_id"]}:{r["date"]}' for r in support if r['eligible']]
 admission={'classification':'P6A_QUALIFIED_DESCRIPTIVE_EXTERNAL_TEMPORAL_VALIDATION','protocol_hash':sha(P/'P6_PROTOCOL_FROZEN.json'),'frozen_models':protocol['frozen_models'],'sample_ids':ids,'support_hash':sha(P/'P6_MONTHLY_SUPPORT.csv'),'met_only_hash':sha(P/'P6_MET_ONLY_INPUTS.json'),'source_hashes':sourcepin,'Q_numeric_values_available_to_prediction':False,'new_Q_sources':{'818':str(E/'CAMELS_CAMELS_CH_obs_based_2304.csv')},'units':{'Q':'m3/s','P':'mm/month','T':'degC'},'quality_limit':'CAMELS provider-curated measured data; per-day checked/suspect flags absent, not equivalent to LamaH ckhs1; P6 descriptive only','excluded_gauges':{'611':'official download failed; monthly day counts not verified','688':'official download blocked/notready; EStreams name conflicts resolved by exact official code/coordinates, but day counts still unavailable'},'no_score_based_selection':True}
 assert len(ids)>=12
 jw(P/'P6_ADMISSION_FROZEN.json',admission);attempt('ADMISSION_FROZEN',sample_months=len(ids),gauges=sorted({int(i.split(':')[1]) for i in ids}),scores_seen=False);print('ADMITTED',len(ids),'month samples; label values not passed to inference',flush=True)

def predict():
 run=P/'runs/P6A_V2_2018_2019';assert not run.exists(),'IMMUTABLE_RUN_EXISTS';run.mkdir(parents=True)
 admission=jl(P/'P6_ADMISSION_FROZEN.json');assert admission['protocol_hash']==sha(P/'P6_PROTOCOL_FROZEN.json');assert admission['met_only_hash']==sha(P/'P6_MET_ONLY_INPUTS.json')
 reads=[]
 def audit(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)):
   name=str(args[0]);reads.append(name)
   if any(x in name for x in ['CAMELS_CH_obs_based','monthly_streamflow_mean.csv','D_gauges']) or ('GKD_' in name and '.csv' in name):raise RuntimeError('PREDICTION_ROLE_LABEL_READ_DENIED')
 sys.addaudithook(audit)
 sys.path.insert(0,str(P4/'code'));from inference import load_model
 met=jl(P/'P6_MET_ONLY_INPUTS.json');out=[];loaded={}
 for sid in admission['sample_ids']:
  _,g,dt=sid.split(':');g=int(g);y,mo=map(int,dt.split('-'))
  for mid in ['C0+PT','P2-L1']:
   key=(g,mid)
   if key not in loaded:
    path=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');m=load_model(path);expected=next(r for r in admission['frozen_models'] if r['gauge_id']==g and Path(r['path']).name==mid.replace('+','_'));assert m.hash==expected['model_hash'];loaded[key]=m
   m=loaded[key];assert m.meta['train_cutoff']<'2018-01';pred=m.predict_month(met[str(g)],y,mo)
   out.append({'experiment':'PUBLIC_DATA_P6A_TEMPORAL_EXTERNAL_VALIDATION','sample_id':sid,'source_snapshot_id':'P6A-'+sha(P/'P6_ADMISSION_FROZEN.json')[:20],'model_training_snapshot':m.meta['snapshot_id'],'training_cutoff':m.meta['train_cutoff'],'actual_training_end':m.meta['actual_train_end'],'prediction_kind':'POST2017_TEMPORAL_HOLDOUT_QUALIFIED_DESCRIPTIVE','task':'RECONSTRUCTION_WITH_OBSERVED_MET',**pred})
 cw(run/'P6_PREDICTIONS_WITHOUT_QOBS.csv',out)
 commitment={'protocol_hash':sha(P/'P6_PROTOCOL_FROZEN.json'),'admission_hash':sha(P/'P6_ADMISSION_FROZEN.json'),'prediction_file_hash':sha(run/'P6_PREDICTIONS_WITHOUT_QOBS.csv'),'records':len(out),'sample_months':len(admission['sample_ids']),'gauges':sorted({r['gauge_id'] for r in out}),'models_loaded':len(loaded),'fit_calls':0,'test_Q_read_by_prediction':False,'prediction_role_denies_label_file_open':True,'prediction_code_hash':sha(Path(__file__)),'complete_before_scoring':True}
 jw(run/'COMMITMENT.json',commitment);jw(run/'PREDICTION_READ_AUDIT.json',{'opened_files':sorted(set(reads)),'label_read_attempts':0,'Q_available_to_predict_function':False});seal(run);jw(P/'P6_PREDICTION_SEAL.json',{'SHA256SUMS':sha(run/'SHA256SUMS.txt'),'COMMITMENT':sha(run/'COMMITMENT.json'),'scoring_started':False});attempt('PREDICTIONS_SEALED',**commitment);print('PREDICTIONS_SEALED',len(out),'records; fit0; noQobs read',flush=True)

def metrics(y,p):
 y=np.asarray(y,float);p=np.asarray(p,float);assert len(y) and y.shape==p.shape and np.isfinite(y).all() and np.isfinite(p).all();err=p-y;sy=float(np.std(y));sp=float(np.std(p));sst=float(sum((y-y.mean())**2));den=float(sum(y));values={'n':len(y),'MSE':float(np.mean(err**2)),'RMSE':float(np.sqrt(np.mean(err**2))),'MAE':float(np.mean(abs(err))),'NSE':1-float(sum(err**2))/sst if sst>0 else None,'PBIAS':100*float(sum(err))/den if abs(den)>1e-12 else None,'KGE_r':float(np.corrcoef(y,p)[0,1]) if sy>0 and sp>0 and len(y)>1 else None,'KGE_alpha':sp/sy if sy>0 else None,'KGE_beta':float(p.mean()/y.mean()) if abs(float(y.mean()))>1e-12 else None};values['KGE']=1-math.sqrt(sum((values[k]-1)**2 for k in ['KGE_r','KGE_alpha','KGE_beta'])) if all(values[k] is not None for k in ['KGE_r','KGE_alpha','KGE_beta']) else None;values['NSE_reason']=None if values['NSE'] is not None else 'CONSTANT_OBSERVATION';values['KGE_reason']=None if values['KGE'] is not None else 'UNDEFINED_KGE_COMPONENT';return values

def score():
 pred_dir=P/'runs/P6A_V2_2018_2019';verify(pred_dir);pin=jl(P/'P6_PREDICTION_SEAL.json');assert pin['SHA256SUMS']==sha(pred_dir/'SHA256SUMS.txt');admission=jl(P/'P6_ADMISSION_FROZEN.json');commit=jl(pred_dir/'COMMITMENT.json');assert commit['admission_hash']==sha(P/'P6_ADMISSION_FROZEN.json') and commit['protocol_hash']==sha(P/'P6_PROTOCOL_FROZEN.json');assert commit['prediction_code_hash']==sha(Path(__file__))
 out=P/'runs/P6A_V2_2018_2019_SCORING';assert not out.exists();out.mkdir();attempt('SCORING_ROLE_STARTED',prediction_seal_hash=pin['SHA256SUMS'])
 labels={}
 for g,path in admission['new_Q_sources'].items():
  assert sha(path)==admission['source_hashes'][path];groups=collections.defaultdict(list)
  for r in cr(path):
   dt=r['date'][:7]
   if f'LAMAH_CE_PUBLIC_V1:{g}:{dt}' in admission['sample_ids']:groups[dt].append(float(r['discharge_vol(m3/s)']))
  for dt,vals in groups.items():
   y,mo=map(int,dt.split('-'));assert len(vals)==calendar.monthrange(y,mo)[1] and all(math.isfinite(v) and v>=0 for v in vals),'NUMERIC_Q_SUPPORT_CONTRADICTION_ABORT_NO_RESELECTION';labels[int(g),dt]=sum(vals)/len(vals)
 preds=cr(pred_dir/'P6_PREDICTIONS_WITHOUT_QOBS.csv');rows=[];coverage=[];comparison=[];support=collections.Counter()
 for g in sorted({int(r['gauge_id']) for r in preds}):
  for mid in ['C0+PT','P2-L1']:
   data=sorted([r for r in preds if int(r['gauge_id'])==g and r['model_id']==mid],key=lambda r:r['date'])
   for r in data:support[(g,mid,r['support_class'])]+=1
   for subset in ['ALL','2018','2019','DJF','MAY_JUNE']:
    rr=[r for r in data if subset=='ALL' or subset==r['date'][:4] or subset=='DJF' and int(r['date'][5:]) in [12,1,2] or subset=='MAY_JUNE' and int(r['date'][5:]) in [5,6]]
    if not rr:continue
    y=np.array([labels[g,r['date']] for r in rr])
    for variant,key in [('raw','q_hat_raw'),('nonnegative','q_hat_nonnegative')]:
     m=metrics(y,[float(r[key]) for r in rr]);rows.append({'gauge_id':g,'model_id':mid,'subset':subset,'prediction':variant,'quality_tier':'PROVIDER_CURATED_NO_DAILY_FLAGS_DESCRIPTIVE',**m})
    for nominal in [80,90]:
     valid=[r for r in rr if r[f'lower{nominal}'] and r[f'upper{nominal}']];yy=np.array([labels[g,r['date']] for r in valid]);lo=np.array([float(r[f'lower{nominal}']) for r in valid]);hi=np.array([float(r[f'upper{nominal}']) for r in valid]);a=1-nominal/100
     coverage.append({'gauge_id':g,'model_id':mid,'subset':subset,'nominal':nominal/100,'n':len(valid),'coverage':float(np.mean((yy>=lo)&(yy<=hi))) if len(valid) else None,'mean_width':float(np.mean(hi-lo)) if len(valid) else None,'mean_interval_score':float(np.mean((hi-lo)+2/a*np.maximum(lo-yy,0)+2/a*np.maximum(yy-hi,0))) if len(valid) else None,'undefined_reason':None if len(valid) else 'NO_DEFINED_FROZEN_INTERVAL'})
  for subset in ['ALL','2018','2019','DJF','MAY_JUNE']:
   c=next(r for r in rows if r['gauge_id']==g and r['model_id']=='C0+PT' and r['subset']==subset and r['prediction']=='raw');l=next(r for r in rows if r['gauge_id']==g and r['model_id']=='P2-L1' and r['subset']==subset and r['prediction']=='raw');assert c['n']==l['n'];comparison.append({'gauge_id':g,'subset':subset,'n':c['n'],'MSE_C0PT':c['MSE'],'MSE_L1':l['MSE'],'MSE_skill':1-l['MSE']/c['MSE'] if c['MSE']>0 else None})
 cw(out/'P6_METRICS.csv',rows);cw(out/'P6_INTERVAL_DIAGNOSTICS.csv',coverage);cw(out/'P6_MODEL_COMPARISON.csv',comparison);cw(out/'P6_INPUT_SUPPORT.csv',[{'gauge_id':g,'model_id':mid,'support_class':s,'months':n} for (g,mid,s),n in support.items()]);jw(out/'SCORING_PROVENANCE.json',{'prediction_seal_hash':pin['SHA256SUMS'],'admission_hash':sha(P/'P6_ADMISSION_FROZEN.json'),'protocol_hash':sha(P/'P6_PROTOCOL_FROZEN.json'),'Q_source_hashes':{p:admission['source_hashes'][p] for p in admission['new_Q_sources'].values()},'Qobs_exported':False,'label_months':len(labels),'prediction_rows':len(preds),'new_fit_calls':0,'scope':'One basin / two years, source quality not day-flag-certified; descriptive temporal external evidence only','metric_code_hash':sha(Path(__file__))});seal(out)
 overall=[r for r in rows if r['subset']=='ALL' and r['prediction']=='raw'];status={'stations':[{'gauge_id':818,'status':'P6_DESCRIPTIVE_COMPLETED_2018_2019','quality':'PROVIDER_CURATED_NO_DAILY_FLAGS','months':24,'independent_of_V2_training_cutoff':True,'metrics':overall},{'gauge_id':611,'status':'BLOCKED_OFFICIAL_DAILY_Q_DAYCOUNT_NOT_VERIFIED'},{'gauge_id':688,'status':'BLOCKED_OFFICIAL_DAILY_Q_DAYCOUNT_NOT_VERIFIED'}],'business_certification':'NOT_CERTIFIED','fit_calls':0,'prediction_records':len(preds),'scored_stations':1,'teacher_Q_read':False,'new_period':'2018-2019','production_display':'NOT_GRANTED'};jw(P/'P6_STATUS.json',status);attempt('P6_INDEPENDENT_SCORING_COMPLETE',prediction_records=len(preds),label_months=len(labels),stations=1,fit_calls=0,scope='QUALIFIED_DESCRIPTIVE');print(json.dumps({'overall':overall,'comparison':comparison,'coverage_ALL':[r for r in coverage if r['subset']=='ALL']},ensure_ascii=False,indent=2))

if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='admit':admit()
 elif mode=='predict':predict()
 elif mode=='score':score()
 else:raise SystemExit('admit | predict | score')
