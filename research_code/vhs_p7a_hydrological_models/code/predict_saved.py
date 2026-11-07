"""Saved P7 research models: pure weather-only inference, no fitting or Q argument."""
from common import *
import datetime,argparse
def predict_weather(model,weather,dates,*,units):
 if units!={'P':'mm/month','T':'degC'}:raise ValueError('INPUT_UNIT_MISMATCH')
 if model['model_id'] not in ['C0+PT','P2-L1','P7-MEM']:raise ValueError('UNPROMOTED_OR_UNKNOWN_MODEL')
 for date,w in weather.items():
  datetime.datetime.strptime(date,'%Y-%m')
  if set(w)!={'P','T'}:raise ValueError('ONLY_EXTERNAL_P_T_ALLOWED_NO_Q')
  if not np.isfinite([w['P'],w['T']]).all() or w['P']<0:raise ValueError('INVALID_WEATHER')
 mem=memory(weather,model['rho'],24) if model['model_id']=='P7-MEM' else {}
 out=[]
 for date in dates:
  if date not in weather or prev(date) not in weather:raise ValueError('MISSING_ACTUAL_CALENDAR_WEATHER')
  if model['model_id']=='P7-MEM' and date not in mem:raise ValueError('MEM_REQUIRES_24_PRIOR_VALID_MONTHS')
  mi=int(date[-2:])-1;raw={'P':weather[date]['P'],'T':weather[date]['T'],'L1':weather[prev(date)]['P'],'MEM':mem.get(date)}
  mu=model['transform']['monthly_mean'][mi];sd=model['transform']['monthly_sample_std'][mi];constant=model['transform']['monthly_constant'][mi]
  z=[0. if constant[j] else (raw[k]-mu[j])/sd[j] for j,k in enumerate(model['fields'])]
  contrib={k:float(z[j]*model['parameters']['beta_standardized'][j]) for j,k in enumerate(model['fields'])};base=model['parameters']['monthly_climatology'][mi];q=float(base+sum(contrib.values()))
  out.append({'date':date,'qsim_raw':q,'qsim_nonnegative':max(q,0),'seasonal_baseline':base,'feature_contributions':contrib,'prediction_kind':'RECONSTRUCTION_WITH_OBSERVED_MET','fit_calls':0,'model_status':'RESEARCH_CANDIDATE_NOT_PRODUCTION'})
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--model',required=True);ap.add_argument('--weather-csv',required=True);ap.add_argument('--dates',required=True,help='comma separated YYYY-MM');ap.add_argument('--output',required=True);a=ap.parse_args()
 if pathlib.Path(a.output).exists():raise FileExistsError('Will not overwrite an existing prediction artifact')
 rr=rows(a.weather_csv)
 if set(rr[0])!={'date','P','T'}:raise ValueError('WEATHER_CSV_SCHEMA_REQUIRES_date_P_T_ONLY')
 if len({r['date'] for r in rr})!=len(rr):raise ValueError('DUPLICATE_WEATHER_DATE')
 weather={r['date']:{'P':float(r['P']),'T':float(r['T'])} for r in rr};model=readj(a.model)
 put(a.output,{'model_sha256':sha(a.model),'weather_sha256':sha(a.weather_csv),'records':predict_weather(model,weather,a.dates.split(','),units={'P':'mm/month','T':'degC'}),'fit_calls':0})
if __name__=='__main__':main()
