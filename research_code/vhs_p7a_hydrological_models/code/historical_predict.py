"""Independent inference role: no fit import, no external Q reads, seal before scoring."""
from common import *
import sys
def main():
 if (ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv').exists():raise FileExistsError('Will not overwrite sealed historical predictions')
 reg=readj(ROOT/'P7A_MODEL_REGISTRY.json');models=reg['research_models']
 d=LAB/'vhs_p6d_failure_diagnostics';metfile=d/'P6D_PREDICTION_DECOMPOSITION.csv'
 # This frozen table has P/T/lag, coefficients and TRAIN-period statistics; no external Qobs.
 forbidden=['P6D_MONTHLY_PAIRED_ERRORS.csv','P6D_STATION_YEAR_FAILURES.csv']
 reads=set()
 def guard(event,args):
  if event=='open' and isinstance(args[0],(str,bytes)):
   s=str(pathlib.Path(args[0]).resolve());mode=args[1] or ''
   if isinstance(mode,str) and ('r' in mode or not mode):
    if any(n in s for n in forbidden) or 'vhs_workbuddy' in s.lower():raise PermissionError('PREDICT_ROLE_Q_FORBIDDEN')
    if str(LAB) in s:reads.add(s)
 sys.addaudithook(guard)
 rs=rows(metfile);assert 'Qobs' not in rs[0]
 weather=collections_weather={g:{} for g in GAUGES}
 for r in rows(P4/'source/weather.csv'):
  g=int(r['gauge_id'])
  if g in weather and r['date']<='2017-12' and r['P'] and r['T']:weather[g][r['date']]={'P':float(r['P']),'T':float(r['T'])}
 for r in rs:
  if r['model_id']=='P2-L1':weather[int(r['gauge_id'])][r['date']]={'P':float(r['P_raw']),'T':float(r['T_raw'])}
 out=[];support=[]
 for entry in models:
  g=entry['gauge_id'];p=pathlib.Path(entry['model_path']);assert sha(p)==entry['sha256'];m=readj(p);rho=entry['rho'];mem=memory(weather[g],rho) if rho else None
  mu=np.array(m['transform']['monthly_mean']);sd=np.array(m['transform']['monthly_sample_std']);constant=np.array(m['transform']['monthly_constant']);beta=np.array(m['parameters']['beta_standardized']);cl=np.array(m['parameters']['monthly_climatology'])
  for date,w in sorted(weather[g].items()):
   if not '2018-01'<=date<='2020-12':continue
   year,month=map(int,date.split('-'));mi=month-1
   raw={'P':w['P'],'T':w['T'],'L1':weather[g][prev(date)]['P'],'MEM':mem[date] if mem is not None else None}
   x=np.array([raw[k] for k in m['fields']]);z=np.where(constant[mi],0,(x-mu[mi])/np.where(constant[mi],1,sd[mi]));pred=float(cl[mi]+z@beta)
   out.append({'gauge_id':g,'date':date,'year':year,'month':month,'model_id':entry['model_id'],'qsim_raw':pred,'qsim_nonnegative':max(pred,0),'seasonal_baseline':float(cl[mi]),'met_contribution':float(z@beta),'lag_memory_date':prev(date),'rho':rho,'model_hash':entry['sha256'],'prediction_kind':'POSTHOC_EXPOSED_2018_2020_NOT_BLIND','fit_calls':0})
   support.append({'gauge_id':g,'date':date,'model_id':entry['model_id'],'max_abs_z':float(max(abs(z))),'constant_departure':bool(np.any(constant[mi]&(abs(x-mu[mi])>1e-12))),'input_hash':digest(raw),'source_met_file_hash':sha(metfile)})
 assert len(out)==24*36*3
 csvout(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv',out);csvout(ROOT/'P7A_HISTORICAL_INPUT_SUPPORT.csv',support)
 put(ROOT/'evidence/HISTORICAL_PREDICTION_SEAL.json',{'created_utc':utc(),'sha256':sha(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv'),'n':len(out),'fit_calls':0,'external_Q_read':False,'opened_public_files':sorted(reads),'met_source_hash':sha(metfile),'model_registry_hash':sha(ROOT/'P7A_MODEL_REGISTRY.json'),'classification':'EXPOSED_PERIOD_DESCRIPTION_NOT_INDEPENDENT_VALIDATION','intervals':'NOT_GENERATED_NO_TEST_Q_RECALIBRATION'})
if __name__=='__main__':main()
