from predict_saved import *
def main():
 model=readj(ROOT/'models/ID_2/P7-MEM/model.json');weather={}
 for r in rows(P4/'source/weather.csv'):
  if r['gauge_id']=='2' and r['P'] and r['T'] and r['date']<='2017-12':weather[r['date']]={'P':float(r['P']),'T':float(r['T'])}
 for r in rows(LAB/'vhs_p6d_failure_diagnostics/P6D_PREDICTION_DECOMPOSITION.csv'):
  if r['gauge_id']=='2' and r['model_id']=='P2-L1':weather[r['date']]={'P':float(r['P_raw']),'T':float(r['T_raw'])}
 expected={r['date']:float(r['qsim_raw']) for r in rows(ROOT/'P7A_HISTORICAL_PREDICTIONS_WITHOUT_QOBS.csv') if r['gauge_id']=='2' and r['model_id']=='P7-MEM'}
 checks=[]
 pred=predict_weather(model,weather,sorted(expected),units={'P':'mm/month','T':'degC'});checks.append({'name':'saved_entry_reproduces36_sealed_predictions','passed':all(abs(r['qsim_raw']-expected[r['date']])<1e-11 for r in pred)})
 cases=[('reject_Q_input',{d:{**v,**({'Q':1} if d=='2020-01' else {})} for d,v in weather.items()},{'P':'mm/month','T':'degC'},'2020-01'),('reject_wrong_units',weather,{'P':'m/month','T':'K'},'2020-01'),('reject_missing_calendar_lag',{d:v for d,v in weather.items() if d!='2019-12'},{'P':'mm/month','T':'degC'},'2020-01'),('reject_insufficient_warmup',{d:v for d,v in weather.items() if d>='2019-01'},{'P':'mm/month','T':'degC'},'2020-01')]
 for name,w,u,date in cases:
  try:predict_weather(model,w,[date],units=u);denied=False
  except ValueError:denied=True
  checks.append({'name':name,'passed':denied})
 put(ROOT/'evidence/SAVED_PREDICTION_ENTRY_TESTS.json',{'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'fit_calls':0,'checks':checks});assert all(c['passed'] for c in checks)
 print('saved weather-only entry checks',len(checks),'passed')
if __name__=='__main__':main()
