"""Independent scalar reconstruction and label parser, does not reuse scorer metrics."""
from p6c_common import *
from statistics import mean,pstdev
from datetime import datetime
import platform,importlib.metadata
sys.stdout.reconfigure(encoding='utf-8');checks=[]
def ck(name,ok,detail=None):checks.append({'name':name,'pass':bool(ok),'detail':detail})
def near(a,b):return (a is None and b in ['',None]) or (a is not None and b not in ['',None] and math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-10))
def independent(y,p):
 n=len(y)
 if not n:return {k:None for k in ['MSE','RMSE','MAE','NSE','PBIAS','KGE','KGE_r','KGE_alpha','KGE_beta','Qobs_mean','Qsim_mean']}
 ym,pm=mean(y),mean(p);sy,sp=pstdev(y),pstdev(p);err=[pp-yy for yy,pp in zip(y,p)];mse=mean([e*e for e in err]);r=sum((yy-ym)*(pp-pm) for yy,pp in zip(y,p))/(n*sy*sp) if sy and sp else None;aa=sp/sy if sy else None;bb=pm/ym if ym else None
 return {'MSE':mse,'RMSE':math.sqrt(mse),'MAE':mean([abs(e) for e in err]),'NSE':1-mse/(sy*sy) if sy else None,'PBIAS':100*mean(err)/ym if ym else None,'KGE':1-math.sqrt((r-1)**2+(aa-1)**2+(bb-1)**2) if all(v is not None for v in [r,aa,bb]) else None,'KGE_r':r,'KGE_alpha':aa,'KGE_beta':bb,'Qobs_mean':ym,'Qsim_mean':pm}
a=jl(R/'P6C_ADMISSION_FROZEN.json');predroot=R/'runs/P6C_2020_PREDICTION';scoreroot=R/'runs/P6C_2020_SCORING';verify(predroot);verify(scoreroot);ck('PREDICTION_AND_SCORE_SEALS',True)
pred=readcsv(predroot/'P6C_2020_PREDICTIONS.csv');met=jl(R/'driver/MET_ONLY_2019_12_2020.json');labels={};times={}
for gg,path in a['sources'].items():
 g=int(gg);body=Path(path).read_text(encoding='latin1').split('Werte:',1)[1];days={}
 for line in body.splitlines():
  if ';' not in line:continue
  dt,tok=line.split(';',1)
  try:d=datetime.strptime(dt.strip(),'%d.%m.%Y %H:%M:%S');q=float(tok.strip().replace(',','.'))
  except ValueError:continue
  days[d.strftime('%Y-%m-%d')]=q
 for mo in range(1,13):
  sid=f'{g}:2020-{mo:02d}'
  if sid not in a['descriptive_ids']:continue
  yy=[days[f'2020-{mo:02d}-{day:02d}'] for day in range(1,calendar.monthrange(2020,mo)[1]+1)];labels[g,f'2020-{mo:02d}']=mean(yy)
for g in sorted({int(r['gauge_id']) for r in pred}):
 mapp={r['date']:r for r in met[str(g)]}
 for mid in ['C0+PT','P2-L1']:
  folder=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');meta=jl(folder/'model.json');npred=0
  with np.load(folder/'arrays.npz',allow_pickle=False) as z:
   for r in pred:
    if int(r['gauge_id'])!=g or r['model_id']!=mid:continue
    month=int(r['date'][5:]);i=month-1;prev=f'2020-{month-1:02d}' if month>1 else '2019-12';vals=[mapp[prev if f=='L1' else r['date']]['P' if f=='L1' else f] for f in meta['fields']];zz=[0. if z['constant'][i,j] else (v-z['mu'][i,j])/z['sd'][i,j] for j,v in enumerate(vals)];pp=float(z['climate'][i])+sum(v*float(b) for v,b in zip(zz,z['beta']));ck(f'PREDICT_{g}_{mid}_{month}',near(pp,r['q_hat_raw']) and near(max(0,pp),r['q_hat_nonnegative']));npred+=1
   ck(f'MODEL_{g}_{mid}_FIXED_ID',meta['actual_train_end']<'2020-01' and meta['train_cutoff']<'2018-01' and npred==12)
metricsrows=readcsv(scoreroot/'P6C_ALL_STATION_METRICS.csv');mmkeys=['MSE','RMSE','MAE','NSE','PBIAS','KGE','KGE_r','KGE_alpha','KGE_beta','Qobs_mean','Qsim_mean'];months={'Q1':[1,2,3],'Q2':[4,5,6],'Q3':[7,8,9],'Q4':[10,11,12],'DJF':[12,1,2],'MAM':[3,4,5],'JJA':[6,7,8],'SON':[9,10,11],'MAY_JUNE':[5,6]}
def selected(g,mid,quality,subset):
 meta=jl(P4/'models/V2'/f'ID_{g}'/mid.replace('+','_')/'model.json');out=[]
 for r in pred:
  if int(r['gauge_id'])!=g or r['model_id']!=mid or quality=='STRICT_SENSITIVITY' and r['strict_sensitivity_eligible']!='True':continue
  q=labels[g,r['date']];m=int(r['date'][5:]);ok=subset in ['ALL','2020'] or subset in months and m in months[subset] or subset=='LOW_TRAIN_Q20' and q<=meta['Q20'] or subset=='HIGH_TRAIN_Q80' and q>=meta['Q80']
  if ok:out.append(r)
 return sorted(out,key=lambda r:r['date'])
for mr in metricsrows:
 g=int(mr['gauge_id']);rr=selected(g,mr['model_id'],mr['quality_tier'],mr['subset']);y=[labels[g,r['date']] for r in rr];p=[float(r['q_hat_raw' if mr['prediction']=='raw' else 'q_hat_nonnegative']) for r in rr];computed=independent(y,p);bad=[k for k in mmkeys if not near(computed[k],mr[k])];ck('METRICS_'+':'.join(mr[k] for k in ['gauge_id','model_id','quality_tier','subset','prediction']),len(rr)==int(mr['n']) and not bad,bad)
for ir in readcsv(scoreroot/'P6C_INTERVAL_DIAGNOSTICS.csv'):
 g=int(ir['gauge_id']);lev=round(float(ir['nominal'])*100);rr=[r for r in selected(g,ir['model_id'],ir['quality_tier'],ir['subset']) if r[f'lower{lev}'] and r[f'upper{lev}']];cov=[];width=[];scores=[]
 for r in rr:
  lo,hi=float(r[f'lower{lev}']),float(r[f'upper{lev}']);q=labels[g,r['date']];cov.append(float(lo<=q<=hi));width.append(hi-lo);scores.append((hi-lo)+(2/(1-lev/100)*(lo-q) if q<lo else 2/(1-lev/100)*(q-hi) if q>hi else 0))
 ck('INTERVAL_'+':'.join(ir[k] for k in ['gauge_id','model_id','quality_tier','subset','nominal']),all(near(mean(v) if v else None,ir[k]) for v,k in [(cov,'coverage'),(width,'mean_width'),(scores,'interval_score')]))
for c in readcsv(scoreroot/'P6C_MODEL_COMPARISON.csv'):
 def find(mid):return next(r for r in metricsrows if r['model_id']==mid and all(r[k]==c[k] for k in ['gauge_id','quality_tier','subset','prediction']))
 cc,ll=find('C0+PT'),find('P2-L1');skill=1-float(ll['MSE'])/float(cc['MSE']) if cc['MSE'] and float(cc['MSE'])>0 else None;ck('SKILL_'+':'.join(c[k] for k in ['gauge_id','quality_tier','subset','prediction']),near(skill,c['MSE_skill']))
audit=jl(predroot/'PREDICTION_READ_AUDIT.json');ck('NO_LABEL_READ_DURING_PREDICT',not audit['Q_label_read'] and not any('_file5.txt' in p or '_file1.txt' in p for p in audit['opened_files']));ck('FIT_CALLS_ZERO',audit['fit_calls']==0);ck('UNIQUE_PREDICTION_IDENTITIES',len({(r['sample_id'],r['model_id']) for r in pred})==len(pred));ck('NO_QOBS_PREDICTION_EXPORT',not any(k.lower() in {'q','qobs','y','target'} for k in pred[0]));ck('MET_KEYS_NO_LABELS',all(set(r)=={'gauge_id','date','P','T'} for rr in met.values() for r in rr))
commit=jl(predroot/'COMMITMENT.json')
events=[json.loads(line) for line in (R/'RUN_ATTEMPTS.jsonl').read_text().splitlines()];seal_event=next(e for e in events if e['event']=='PREDICTIONS_SEALED');score_event=next(e for e in events if e['event']=='SCORING_STARTED');ck('PREDICTION_SEAL_PRECEDES_SCORING',seal_event['utc']<=score_event['utc'] and events.index(seal_event)<events.index(score_event));ck('JANUARY_LAG_PREVIOUS_CALENDAR_MONTH',all(any(r['date']=='2019-12' for r in rr) for rr in met.values()))
for n,h in commit['code_hashes'].items():ck('CODE_UNCHANGED_'+n,sha(R/'code'/n)==h)
history=jl(R/'evidence/HISTORY_BEFORE.json');unchanged=0;failed=[]
for root,rec in history.items():
 for n,h in rec['files'].items():
  ok=sha(Path(root)/n)==h;unchanged+=ok
  if not ok:failed.append(str(Path(root)/n))
 ck('HISTORY_'+Path(root).name,sha(Path(root)/'SHA256SUMS.txt')==rec['manifest_hash'] and not any(str(Path(root))==str(Path(f).parent) for f in failed))
ck('ALL_HISTORICAL_FILES_UNCHANGED',not failed,{'unchanged':unchanged,'failed':failed});jw(R/'evidence/HISTORY_AFTER.json',{'files_checked':unchanged+len(failed),'unchanged':unchanged,'failed':failed,'manifest_sources':{root:rec['manifest_hash'] for root,rec in history.items()}})
for receipt in (R/'driver').glob('T*_DOWNLOAD.json'):
 d=jl(receipt);ck('CDS_DOWNLOAD_'+d['tile_id'],d['completed'] and sha(d['file'])==d['sha256'] and hashlib.md5(Path(d['file']).read_bytes()).hexdigest()==d['official_result_checksum'].zfill(32))
jw(R/'P6C_INDEPENDENT_VERIFICATION.json',{'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'checks':checks,'independent_scalar_prediction_and_metric_verification':True,'historical_files_unchanged':unchanged,'fit_calls':audit['fit_calls']});jw(R/'evidence/ENVIRONMENT.json',{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{k:importlib.metadata.version(k) for k in ['numpy','xarray','netCDF4','shapely','pyproj']}})
print('VERIFY',sum(c['pass'] for c in checks),'PASS',sum(not c['pass'] for c in checks),'FAIL','HISTORY',unchanged)
if any(not c['pass'] for c in checks):print([c for c in checks if not c['pass']][:10]);sys.exit(1)
