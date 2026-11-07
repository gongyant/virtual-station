from acquire import *
import pandas as pd,numpy as np
if __name__=='__main__':
 d=ROOT/'exploratory_temporal';cache=d/'cache';cache.mkdir(exist_ok=True)
 p=json.loads((d/'E2_PROTOCOL_FROZEN.json').read_text(encoding='utf-8'))
 val=json.loads((ROOT/'driver/LONG1964_1978_NUMERIC_VALIDATION.json').read_text(encoding='utf-8'));assert val['passed'] and val['months_complete']==180
 catch=json.loads((ROOT/'evidence/TAUTURGEN_D8_RESULT.json').read_text(encoding='utf-8'));assert catch['matches_source_ACC'] and catch['relative_area_error']<=.10
 q=pd.read_csv(ROOT/'P9C_MONTHLY_Q_QC.csv',dtype={'source_station_id':str});q=q[(q.source_station_id=='10195')&q.year.between(1965,1977)].copy()
 assert len(q)==156 and q.complete_month.all() and np.isfinite(q.Q_m3s).all() and q.Q_m3s.ge(0).all()
 met=pd.read_csv(ROOT/'driver/P9C_TAUTURGEN_LONG1964_1978_MONTHLY.csv');df=q.merge(met[['year','month','P_mm','T_C']],on=['year','month'],validate='one_to_one').sort_values(['year','month'])
 assert len(df)==156 and np.isfinite(df[['P_mm','T_C']]).all().all()
 snapshot=hashlib.sha256('|'.join([sha(ROOT/'source/data_daily_discharge.csv'),sha(ROOT/'driver/ERA5L_LONG1964_1978.bin'),sha(d/'E2_PROTOCOL_FROZEN.json')]).encode()).hexdigest()
 training=[];features=[];labels=[]
 for r in df.itertuples():
  item=dict(sample_id=f'WB10195|{r.year:04d}-{r.month:02d}',year=int(r.year),month=int(r.month),P=float(r.P_mm),T=float(r.T_C))
  if r.year in p['training_years']:training.append({**item,'Q':float(r.Q_m3s)})
  else:features.append(item);labels.append(dict(sample_id=item['sample_id'],Q=float(r.Q_m3s),year=item['year'],month=item['month']))
 assert len(training)==96 and len(features)==60 and len(labels)==60
 for name,rows in [('TRAINING_ONLY.json',training),('TEST_FEATURES_ONLY.json',features),('SCORE_LABELS_ONLY.json',labels)]:js(cache/name,dict(snapshot=snapshot,rows=rows))
 js(d/'E2_INPUT_BINDING.json',dict(dataset_id='KAZ_PUBLIC_WB0064229_TAUTURGEN',snapshot=snapshot,protocol_sha256=sha(d/'E2_PROTOCOL_FROZEN.json'),
  source_Q_sha256=sha(ROOT/'source/data_daily_discharge.csv'),driver_sha256=sha(ROOT/'driver/ERA5L_LONG1964_1978.bin'),
  train_rows=96,test_rows=60,source_QC='NOT_DAILY_CERTIFIED;PUBLIC_OBSERVATION_SOURCE_NUMERIC_QC_ONLY',P10_ready=False,
  cache_hashes={name:sha(cache/name) for name in ['TRAINING_ONLY.json','TEST_FEATURES_ONLY.json','SCORE_LABELS_ONLY.json']}))
 event(stage='E2_role_caches_prepared',train_rows=96,test_rows=60,snapshot=snapshot,P10_started=False)
