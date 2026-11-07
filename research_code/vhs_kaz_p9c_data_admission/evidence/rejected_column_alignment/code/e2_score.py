from acquire import *
import numpy as np,pandas as pd,types
D=ROOT/'exploratory_temporal';run=D/'run'
if __name__=='__main__':
 if (run/'SHA256SUMS.txt').exists():raise RuntimeError('E2 run sealed; do not rescore inplace')
 seal=json.loads((run/'PREDICTIONS_SEALED_BEFORE_SCORE.json').read_text(encoding='utf-8'));assert sha(run/'E2_PREDICTIONS.csv')==seal['prediction_sha256']
 binding=json.loads((D/'E2_INPUT_BINDING.json').read_text(encoding='utf-8'));assert sha(D/'cache/SCORE_LABELS_ONLY.json')==binding['cache_hashes']['SCORE_LABELS_ONLY.json']
 runtime=types.ModuleType('public_runtime')
 def admit_metric(y,p,synthetic):assert not synthetic and len(y)==len(p) and np.isfinite(y).all() and np.isfinite(p).all()
 runtime.admit_metric=admit_metric;sys.modules['public_runtime']=runtime;sys.path.insert(0,str(ROOT.parent/'code/vendor_public'))
 from vhs_sci.evaluate import metric_bundle
 labels=pd.DataFrame(json.loads((D/'cache/SCORE_LABELS_ONLY.json').read_text(encoding='utf-8'))['rows'])
 pred=pd.read_csv(run/'E2_PREDICTIONS.csv');assert not pred[['sample_id','model_id']].duplicated().any()
 paired=pred.merge(labels,on=['sample_id','year','month'],validate='many_to_one');assert len(paired)==120
 metrics=[];checks=[]
 for variant,col in [('RAW','qsim_raw'),('NONNEGATIVE_SECONDARY','qsim_nonnegative')]:
  for year in ['ALL',1973,1974,1975,1976,1977]:
   for modelid in ['C0','C0+PT']:
    d=paired[(paired.model_id==modelid)&((paired.year==year) if year!='ALL' else True)];y=d.Q.values;p=d[col].values
    m=metric_bundle(y,p,synthetic=False);row=dict(model_id=modelid,variant=variant,year=year,n=len(d),**{k:v['value'] for k,v in m.items()},undefined_reason='|'.join(f'{k}:{v["reason_code"]}' for k,v in m.items() if v['reason_code']))
    b=paired[(paired.model_id=='C0')&((paired.year==year) if year!='ALL' else True)].sort_values('sample_id');d=d.sort_values('sample_id');assert d.sample_id.tolist()==b.sample_id.tolist()
    mse0=float(np.mean((b[col]-b.Q)**2));row['MSE_skill_vs_C0']=1-row['MSE']/mse0 if mse0>0 else None
    independentNSE=1-np.sum((p-y)**2)/np.sum((y-y.mean())**2);independentRMSE=np.sqrt(np.mean((p-y)**2))
    checks.extend([dict(check=f'{variant}_{year}_{modelid}_NSE',passed=bool(abs(independentNSE-row['NSE'])<1e-10)),dict(check=f'{variant}_{year}_{modelid}_RMSE',passed=bool(abs(independentRMSE-row['RMSE'])<1e-10))]);metrics.append(row)
 # Frozen parameter reconstruction, independent of any scoring label values.
 par=json.loads((run/'MODEL_PARAMETERS.json').read_text(encoding='utf-8'));features=pd.DataFrame(json.loads((D/'cache/TEST_FEATURES_ONLY.json').read_text(encoding='utf-8'))['rows']);ix=features.month.values-1
 record=par['C0+PT'];mu=np.array(record['transform']['monthly_mean']);sd=np.array(record['transform']['monthly_sample_std']);constant=np.array(record['transform']['monthly_constant']);z=np.where(constant[ix],0,(features[['P','T']].values-mu[ix])/np.where(constant[ix],1,sd[ix]))
 rebuilt=np.array(record['parameters']['monthly_climatology'])[ix]+z@np.array(record['parameters']['beta_standardized']);original=pred[pred.model_id=='C0+PT'].qsim_raw.values
 error=float(np.max(abs(rebuilt-original)));checks.append(dict(check='parameter_reconstruction_without_test_Q',passed=error<1e-10,maximum_absolute_difference=error))
 pd.DataFrame(metrics).to_csv(run/'E2_TEMPORAL_METRICS.csv',index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
 js(run/'E2_INDEPENDENT_VERIFICATION.json',dict(passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks,score_after_prediction_seal=True,
  no_test_Q_in_predict_process=True,prediction_records=len(pred),train_n_per_model=96,test_n_per_model=60,real_fitted_models=2,
  task='KAZ_KNOWN_GAUGE_TEMPORAL_DEVELOPMENT_P9C_E2',P10_PUB_executed=False,future_blind_test=False))
 assert all(x['passed'] for x in checks)
 (run/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.name}\n' for p in sorted(run.iterdir()) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
 print(pd.DataFrame(metrics).query("year=='ALL'").to_string(index=False));event(stage='E2_separate_real_Q_scoring_complete',records=len(pred),models=2,checks_passed=len(checks),checks_failed=0,P10_started=False)
