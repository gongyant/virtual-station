"""Scalar independent diagnostic verification; no models trained or changed."""
from p6d_common import *
from statistics import mean,pstdev
sys.stdout.reconfigure(encoding='utf-8');checks=[]
def ck(n,b,detail=None):checks.append({'name':n,'pass':bool(b),'detail':detail})
def met(y,p):
 if not y:return {'n':0,**{k:None for k in ['MSE','RMSE','MAE','NSE','KGE','PBIAS','Qobs_mean','Qsim_mean','bias_MSE','centered_MSE']}}
 ym,pm=mean(y),mean(p);sy,sp=pstdev(y),pstdev(p);er=[pp-yy for yy,pp in zip(y,p)];mse=mean([e*e for e in er]);rho=sum((yy-ym)*(pp-pm) for yy,pp in zip(y,p))/(len(y)*sy*sp) if sy and sp else None
 return {'n':len(y),'MSE':mse,'RMSE':math.sqrt(mse),'MAE':mean([abs(e) for e in er]),'NSE':1-mse/sy**2 if sy else None,'KGE':1-math.sqrt((rho-1)**2+(sp/sy-1)**2+(pm/ym-1)**2) if sy and sp and ym else None,'PBIAS':100*mean(er)/ym if ym else None,'Qobs_mean':ym,'Qsim_mean':pm,'bias_MSE':mean(er)**2,'centered_MSE':mean([(e-mean(er))**2 for e in er])}
rows=cr(R/'P6D_MONTHLY_PAIRED_ERRORS.csv');dec=cr(R/'P6D_PREDICTION_DECOMPOSITION.csv');fail=cr(R/'P6D_STATION_YEAR_FAILURES.csv');season=cr(R/'P6D_SEASONAL_AND_DRIFT.csv');interval=cr(R/'P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv');a=jl(C/'P6C_ADMISSION_FROZEN.json');protocol=jl(R/'P6D_DIAGNOSTIC_PROTOCOL.json');pred={}
for path in [B/'runs/P6B_EHYD_2018_2019/P6B_PREDICTIONS_WITHOUT_QOBS.csv',C/'P6C_2020_PREDICTIONS.csv']:
 for r in cr(path):pred[int(r['gauge_id']),r['date'],r['model_id']]=r
ck('864_UNIQUE_PAIRED',len(rows)==len({r['sample_id'] for r in rows})==864);ck('1728_UNIQUE_DECOMP',len(dec)==len({(r['gauge_id'],r['date'],r['model_id']) for r in dec})==1728)
# independent raw provider parser validates every exported monthly label.
for gg,path in a['sources'].items():
 g=int(gg);monthly={}
 for line in Path(path).read_text(encoding='latin1').split('Werte:',1)[1].splitlines():
  tokens=line.split(';')
  if len(tokens)<2:continue
  try:d=datetime.strptime(tokens[0].strip(),'%d.%m.%Y %H:%M:%S');q=float(tokens[1].strip().replace(',','.'))
  except ValueError:continue
  if d.year in [2018,2019,2020]:monthly.setdefault(d.strftime('%Y-%m'),[]).append(q)
 for r in rows:
  if int(r['gauge_id'])!=g:continue
  ck('QOBS_'+r['sample_id'],near(sum(monthly[r['date']])/len(monthly[r['date']]),r['Qobs']))
for r in rows:
 g=int(r['gauge_id']);q=float(r['Qobs']);c=float(r['Qsim_C0PT']);l=float(r['Qsim_L1']);ec,el=c-q,l-q;change=l-c
 ck('MONTHLY_ERROR_'+r['sample_id'],all(near(x,r[k]) for x,k in [(ec,'error_C0PT'),(el,'error_L1'),(ec*ec,'SE_C0PT'),(el*el,'SE_L1'),(ec*ec-el*el,'delta_SE_C0_minus_L1'),(-2*ec*change-change*change,'delta_SE_C0_minus_L1')]))
 ck('FROZEN_PREDICTIONS_'+r['sample_id'],near(c,pred[g,r['date'],'C0+PT']['q_hat_raw']) and near(l,pred[g,r['date'],'P2-L1']['q_hat_raw']))
 terms=sum(float(r[k]) for k in ['delta_prediction_lag_term','delta_prediction_currentP_term','delta_prediction_currentT_term','delta_prediction_seasonal_term']);ck('DELTA_TERM_SUM_'+r['sample_id'],near(terms,change))
for d in dec:
 g=int(d['gauge_id']);mid=d['model_id'];folder=P4/'models/V2'/f'ID_{g}'/mid.replace('+','_');meta=jl(folder/'model.json');r=pred[g,d['date'],mid];i=int(d['month'])-1
 with np.load(folder/'arrays.npz',allow_pickle=False) as z:
  co=[]
  for j,f in enumerate(meta['fields']):
   raw=float(d['lag_P_raw' if f=='L1' else f+'_raw']);zz=0. if z['constant'][i,j] else (raw-z['mu'][i,j])/z['sd'][i,j];co.append(zz*z['beta'][j]);ck('TERM_'+d['gauge_id']+d['date']+mid+f,near(co[-1],d[f+'_contribution']))
  pp=float(z['climate'][i])+sum(co);ck('INDEPENDENT_PREDICT_'+d['gauge_id']+d['date']+mid,near(pp,r['q_hat_raw']) and near(pp,d['qsim_reconstructed']) and meta['snapshot_id']==r['model_training_snapshot'])
def select(g,period,quality='MAIN_DESCRIPTIVE',subset='ALL'):
 out=[];months=protocol['seasons'].get(subset,list(range(1,13)))
 for r in rows:
  if int(r['gauge_id'])!=g or int(r['month']) not in months or quality=='STRICT_SENSITIVITY' and r['strict_sensitivity_eligible']!='True':continue
  y=int(r['year']);ok=str(y)==period or period=='2018_2019' and y<2020 or period=='2018_2020'
  if ok:out.append(r)
 return out
for r in fail:
 ss=select(int(r['gauge_id']),r['period'],r['quality_tier']);yc=[float(x['Qobs']) for x in ss];co=met(yc,[float(x['Qsim_C0PT']) for x in ss]);lo=met(yc,[float(x['Qsim_L1']) for x in ss]);skill=1-lo['MSE']/co['MSE'] if ss and co['MSE'] else None;ok=near(skill,r['MSE_skill']) and int(r['n'])==len(ss)
 for prefix,mm in [('C0PT',co),('L1',lo)]:
  for k,v in mm.items():
   if k=='n':continue
   ok=ok and near(v,r[prefix+'_'+k])
 ck('YEAR_POOLED_'+r['gauge_id']+r['period']+r['quality_tier'],ok)
 if ss:ck('MSE_IDENTITY_'+r['gauge_id']+r['period']+r['quality_tier'],near(mean([float(x['delta_SE_C0_minus_L1']) for x in ss]),co['MSE']-lo['MSE']))
for r in season:
 ss=select(int(r['gauge_id']),r['period'],subset=r['subset']);pkey='Qsim_C0PT' if r['model_id']=='C0+PT' else 'Qsim_L1';mm=met([float(x['Qobs']) for x in ss],[float(x[pkey]) for x in ss]);ck('SEASON_'+r['gauge_id']+r['period']+r['model_id']+r['subset'],all(near(v,r[k]) for k,v in mm.items() if k!='n') and int(r['n'])==len(ss))
for r in interval:
 ss=select(int(r['gauge_id']),r['period'],r['quality_tier'],r['subset']);lev=round(float(r['nominal'])*100);width=[];score=[];covered=[];yy=[]
 for s in ss:
  p=pred[int(r['gauge_id']),s['date'],r['model_id']]
  if not p[f'lower{lev}'] or not p[f'upper{lev}']:continue
  q=float(s['Qobs']);lo,hi=float(p[f'lower{lev}']),float(p[f'upper{lev}']);w=hi-lo;covered.append(float(lo<=q<=hi));width.append(w);yy.append(q);score.append(w+(2/(1-lev/100)*(lo-q) if q<lo else 2/(1-lev/100)*(q-hi) if q>hi else 0))
 ck('INTERVAL_'+r['gauge_id']+r['model_id']+r['quality_tier']+r['period']+r['subset']+str(lev),all(near(mean(v) if v else None,r[k]) for v,k in [(covered,'coverage'),(width,'mean_width_m3s'),(score,'mean_interval_score_m3s')]) and near(mean(width)/mean(yy) if yy and mean(yy) else None,r['width_divided_by_Qobs_mean']))
# exact archived score comparison prevents silently changing P6B/P6C definitions.
for source,period in [(B/'P6B_ALL_STATION_METRICS.csv','2018_2019'),(C/'P6C_ALL_STATION_METRICS.csv','2020')]:
 for old in cr(source):
  if int(old['gauge_id']) not in protocol['gauge_ids'] or old['quality_tier']!='DESCRIPTIVE_ARCHIVE' or old['prediction']!='raw':continue
  if source.parent==B and old.get('cohort')!='EHYD_24_2018_2019':continue
  if old['subset'] in ['ALL','2018','2019','2020']:
   per=period if old['subset']=='ALL' else old['subset'];rr=next((r for r in fail if r['gauge_id']==old['gauge_id'] and r['period']==per and r['quality_tier']=='MAIN_DESCRIPTIVE'),None);prefix='C0PT_' if old['model_id']=='C0+PT' else 'L1_';ok=rr is not None and all(near(rr[prefix+k] if rr[prefix+k]!='' else None,old[k]) for k in ['NSE','KGE','MSE','RMSE','MAE','PBIAS'])
  elif old['subset'] in protocol['seasons']:
   rr=next(r for r in season if r['gauge_id']==old['gauge_id'] and r['period']==period and r['model_id']==old['model_id'] and r['subset']==old['subset']);ok=all(near(rr[k] if rr[k]!='' else None,old[k]) for k in ['NSE','KGE','MSE','RMSE','MAE','PBIAS'])
  else:continue
  ck('ARCHIVED_SCORE_'+source.parent.name+old['gauge_id']+old['model_id']+old['subset'],ok)
ck('2020_MAIN_288',len([r for r in rows if r['year']=='2020'])==288);strict=[r for r in rows if r['year']=='2020' and r['strict_sensitivity_eligible']=='True'];ck('2020_CONSERVATIVE_132',len(strict)==132);ck('2020_CONSERVATIVE_FULLYEAR_4',sum(sum(r['gauge_id']==str(g) for r in strict)==12 for g in protocol['gauge_ids'])==4)
before=jl(R/'evidence/HISTORY_BEFORE.json');histbad=[]
for path,h in before.items():
 ok=sha(path)==h
 if not ok:histbad.append(path)
ck('HISTORY_P0_P6C_AND_ORIGINAL_WEB_CODE',not histbad,{'entries':len(before),'changed':histbad});jw(R/'evidence/HISTORY_AFTER.json',{'checked':len(before),'unchanged':len(before)-len(histbad),'changed':histbad});extract=jl(R/'P6D_EXTRACTION_CHECKS.json');ck('FIT_CALLS_0',extract['fit_calls']==0);ck('DECOMPOSITION_TOLERANCE',extract['max_prediction_reconstruction_abs_error']<1e-10)
jw(R/'P6D_INDEPENDENT_VERIFICATION.json',{'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'checks':checks,'fit_calls':0,'history_entries_unchanged':len(before)-len(histbad)});print('VERIFY',sum(c['pass'] for c in checks),'PASS',sum(not c['pass'] for c in checks),'FAIL')
if any(not c['pass'] for c in checks):print([c for c in checks if not c['pass']][:20]);sys.exit(1)
