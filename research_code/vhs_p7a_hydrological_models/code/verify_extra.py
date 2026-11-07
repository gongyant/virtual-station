"""Independent direct equations for transforms, fixed predictions and metrics. No fit."""
from common import *
checks=[]
def ck(n,v):checks.append({'name':n,'passed':bool(v)});assert v,n
def near(a,b):return bool(np.allclose(a,b,rtol=1e-11,atol=1e-11))
def direct(y,p):
 e=p-y;sy=np.std(y);sp=np.std(p);r=np.corrcoef(y,p)[0,1] if sy>0 and sp>0 else None
 out={'MSE':float(np.mean(e*e)),'RMSE':float(np.sqrt(np.mean(e*e))),'MAE':float(np.mean(abs(e))),'NSE':float(1-np.sum(e*e)/np.sum((y-y.mean())**2)) if sy>0 else None,'PBIAS':float(100*e.sum()/y.sum()) if abs(y.sum())>1e-12 else None}
 if r is not None and abs(y.mean())>1e-12:out['KGE']=float(1-np.sqrt((r-1)**2+(sp/sy-1)**2+(p.mean()/y.mean()-1)**2))
 else:out['KGE']=None
 return out
def main():
 cache=readj(ROOT/'cache/TRAINING_ONLY_2017.json');pars=readj(ROOT/'evidence/OUTER_PARAMETERS.json');folds={f['fold_id']:f for f in readj(ROOT/'evidence/FOLDS_DETAIL.json')}
 for par in pars:
  g=par['gauge_id'];rec=par['record'];c=folds[par['fold_id']]['cutoff'];tr=[r for r in cache[str(g)] if r['year']<=c]
  ck('no_outer_future_label_'+par['fold_id']+rec['model_id'],max(r['date'] for r in tr)<folds[par['fold_id']]['validation_start'])
  for month in range(1,13):
   rr=[r for r in tr if r['month']==month];cl=np.mean([r['Q'] for r in rr]);stored=rec['climate'][month-1] if rec['model_id']=='C0' else rec['parameters']['monthly_climatology'][month-1]
   ck('training_only_month_climate_'+par['fold_id']+rec['model_id']+str(month),near(cl,stored))
   if rec['model_id']=='C0':continue
   x=np.array([[r[f'MEM_{rec["rho"]}'] if k=='MEM' else r[k] for k in rec['fields']] for r in rr])
   ck('training_only_mu_'+par['fold_id']+rec['model_id']+str(month),near(x.mean(0),rec['transform']['monthly_mean'][month-1]))
   ck('training_only_sd_'+par['fold_id']+rec['model_id']+str(month),near(x.std(0,ddof=1),rec['transform']['monthly_sample_std'][month-1]))
 # Independent scalar recursions over all actual calendar months, no Q values from P6 needed.
 de=rows(LAB/'vhs_p6d_failure_diagnostics/P6D_PREDICTION_DECOMPOSITION.csv');weather={g:{} for g in GAUGES}
 for r in rows(P4/'source/weather.csv'):
  g=int(r['gauge_id'])
  if g in weather and r['date']<='2017-12' and r['P'] and r['T']:weather[g][r['date']]=(float(r['P']),float(r['T']))
 for r in de:
  if r['model_id']=='P2-L1':weather[int(r['gauge_id'])][r['date']]=(float(r['P_raw']),float(r['T_raw']))
 models={(r['gauge_id'],r['model_id']):readj(r['model_path']) for r in readj(ROOT/'P7A_MODEL_REGISTRY.json')['research_models']};states={}
 for (g,mid),m in models.items():
  if mid!='P7-MEM':continue
  rho=m['rho'];state=None;last=None;prior_n=0;ss={}
  for date,(p,t) in sorted(weather[g].items()):
   if last!=prev(date):state=None;prior_n=0
   if state is not None and prior_n>=24:ss[date]=state
   state=p if state is None else rho*state+(1-rho)*p;last=date;prior_n+=1
  states[g]=ss
 hp=rows(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv');maxerr=0
 for r in hp:
  g=int(r['gauge_id']);date=r['date'];mid=r['model_id'];m=models[g,mid];mi=int(r['month'])-1
  vals={'P':weather[g][date][0],'T':weather[g][date][1],'L1':weather[g][prev(date)][0],'MEM':states[g][date]}
  mu=m['transform']['monthly_mean'][mi];sd=m['transform']['monthly_sample_std'][mi];constant=m['transform']['monthly_constant'][mi];z=[0 if constant[j] else (vals[k]-mu[j])/sd[j] for j,k in enumerate(m['fields'])]
  pp=m['parameters']['monthly_climatology'][mi]+sum(a*b for a,b in zip(z,m['parameters']['beta_standardized']));err=abs(pp-float(r['qsim_raw']));maxerr=max(maxerr,err)
  ck('historical_fixed_model_reconstruction_'+str(g)+date+mid,err<1e-10*max(1,abs(pp)))
 cv=rows(ROOT/'P7A_CV_PREDICTIONS.csv');lookup={(int(g),r['sample_id']):r['Q'] for g,rs in cache.items() for r in rs}
 for r in rows(ROOT/'P7A_STATION_MODEL_METRICS.csv'):
  g=int(r['gauge_id']);rs=[a for a in cv if int(a['gauge_id'])==g and a['model_id']==r['model_id']];y=np.array([lookup[g,a['sample_id']] for a in rs]);p=np.array([float(a['qsim_raw']) for a in rs]);met=direct(y,p)
  for k,v in met.items():ck('independent_CV_metric_'+str(g)+r['model_id']+k,near(v,float(r[k])) if v is not None else r[k]=='')
 # Exposed observations are read by this independent verifier only, never a training role.
 obs={(int(r['gauge_id']),r['date']):float(r['Qobs']) for r in rows(LAB/'vhs_p6d_failure_diagnostics/P6D_MONTHLY_PAIRED_ERRORS.csv')}
 for r in rows(ROOT/'P7A_HISTORICAL_EXPOSED_COMPARISON.csv'):
  g=int(r['gauge_id']);period=r['period'];rs=[a for a in hp if int(a['gauge_id'])==g and a['model_id']==r['model_id'] and (period=='2018_2020' or period=='2018_2019' and a['year'] in ['2018','2019'] or a['year']==period)]
  y=np.array([obs[g,a['date']] for a in rs]);p=np.array([float(a['qsim_raw']) for a in rs]);p=np.maximum(p,0) if r['analysis']=='NONNEGATIVE_SECONDARY' else p;met=direct(y,p)
  for k,v in met.items():ck('independent_exposed_metric_'+str(g)+period+r['model_id']+r['analysis']+k,near(v,float(r[k])) if v is not None else r[k]=='')
 put(ROOT/'evidence/ADDITIONAL_INDEPENDENT_VERIFICATION.json',{'passed':len(checks),'failed':0,'fit_calls':0,'max_historical_prediction_reconstruction_error':maxerr,'checks':checks,'independently_checked':['train-only climate/mu/sd','calendar memory recursion','all2592 historical predictions','direct NSE/KGE/MAE/RMSE/MSE/PBIAS equations']})
 print('additional independent checks',len(checks),'max historical error',maxerr,flush=True)
if __name__=='__main__':main()
