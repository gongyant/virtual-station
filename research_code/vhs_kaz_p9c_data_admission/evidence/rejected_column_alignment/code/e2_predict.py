from acquire import *
import numpy as np,types,importlib.util,time
D=ROOT/'exploratory_temporal';LAB=ROOT.parent
if __name__=='__main__':
 binding=json.loads((D/'E2_INPUT_BINDING.json').read_text(encoding='utf-8'));protocol=json.loads((D/'E2_PROTOCOL_FROZEN.json').read_text(encoding='utf-8'))
 assert protocol['alpha']==100 and protocol['model_scope']==['C0','C0+PT']
 def admit_input(x):
  assert x.snapshot==binding['snapshot'] and set(x.values)=={'P','T'}
  assert len(set(x.ids))==len(x.ids) and all(np.isfinite(v).all() for v in x.values.values())
 def admit_train(x,y):
  admit_input(x);assert max(x.years)<=1972 and min(x.years)>=1965 and len(y)==len(x.ids) and np.isfinite(y).all() and np.all(y>=0)
 runtime=types.ModuleType('public_runtime');runtime.admit_input=admit_input;runtime.admit_training_matrix=admit_train
 sys.modules['public_runtime']=runtime;sys.path.insert(0,str(LAB/'code/vendor_public'))
 src=LAB/'p2_antecedent_snow_features/P2_MODEL_CODE/models.py'
 spec=importlib.util.spec_from_file_location('p9c_frozen_public_p2_math',src);modelmod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=modelmod;spec.loader.exec_module(modelmod)
 run=D/'run';run.mkdir(exist_ok=False)
 allowed={str((D/p).resolve()).lower() for p in ['cache/TRAINING_ONLY.json','cache/TEST_FEATURES_ONLY.json']};reads=set()
 def hook(kind,args):
  if kind!='open' or not isinstance(args[0],(str,bytes)):return
  path=Path(args[0]).resolve();s=str(path).lower();mode=args[1]
  reading=mode is None or isinstance(mode,str) and 'r' in mode
  if not reading:return
  if s in allowed or path.is_relative_to(run.resolve()):reads.add(str(path));return
  if path.is_relative_to(LAB.resolve()) or 'vhs_workbuddy' in s or '\\data\\' in s and 'deepbas-vhs' in s:
   raise PermissionError('E2_PREDICTION_ROLE_READ_DENIED')
 sys.addaudithook(hook)
 train=json.loads((D/'cache/TRAINING_ONLY.json').read_text(encoding='utf-8'));test=json.loads((D/'cache/TEST_FEATURES_ONLY.json').read_text(encoding='utf-8'))
 def inputs(rows):return modelmod.Inputs(tuple(r['sample_id'] for r in rows),np.array([r['year'] for r in rows]),np.array([r['month'] for r in rows]),{k:np.array([r[k] for r in rows]) for k in ['P','T']},binding['snapshot'],False)
 tx,vx=inputs(train['rows']),inputs(test['rows']);assert max(tx.years)<min(vx.years)
 y=np.array([r['Q'] for r in train['rows']]);admit_train(tx,y)
 clock=time.perf_counter();climate=np.array([y[tx.months==m].mean() for m in range(1,13)]);c0=climate[vx.months-1]
 model=modelmod.MonthlyWeatherRidge('C0+PT',alpha=100).fit(tx,y);pt=model.predict(vx);again=model.predict(vx);assert np.array_equal(pt,again)
 denied=False
 try:(D/'cache/SCORE_LABELS_ONLY.json').read_text(encoding='utf-8')
 except PermissionError:denied=True
 assert denied
 rows=[]
 for modelid,pred in [('C0',c0),('C0+PT',pt)]:
  for r,z in zip(test['rows'],pred):rows.append(dict(sample_id=r['sample_id'],year=r['year'],month=r['month'],model_id=modelid,qsim_raw=float(z),qsim_nonnegative=float(max(z,0)),prediction_kind='KNOWN_GAUGE_TEMPORAL_DEVELOPMENT',train_max_year=1972,snapshot=binding['snapshot']))
 import csv
 with (run/'E2_PREDICTIONS.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 params={'C0':dict(monthly_climatology=climate.tolist(),train_n=len(y),train_years=list(range(1965,1973))), 'C0+PT':model.record()}
 js(run/'MODEL_PARAMETERS.json',params)
 js(run/'PREDICTION_ROLE_AUDIT.json',dict(read_files=sorted(reads),test_Q_read=False,attempt_to_open_score_label_file_blocked=denied,
  deterministic_predictions=True,real_fitted_models=2,Ridge_fit_method_calls=1,seasonal_climatology_estimates=1,
  fit_rows_per_model=len(y),test_rows_per_model=len(test['rows']),source_math_used_readonly=str(src),elapsed_seconds=time.perf_counter()-clock))
 js(run/'PREDICTIONS_SEALED_BEFORE_SCORE.json',dict(prediction_sha256=sha(run/'E2_PREDICTIONS.csv'),parameters_sha256=sha(run/'MODEL_PARAMETERS.json'),records=len(rows),test_Q_read=False))
 event(stage='E2_actual_predictions_sealed',fitted_models=2,Ridge_fit_calls=1,C0_estimates=1,prediction_records=len(rows),test_Q_read=False,P10_started=False)
