"""Separate real-label scorer after PUB predictions are sealed; no model fitting."""
from intake import *
import numpy as np,types,sys
rt=types.ModuleType('public_runtime')
def admit_metric(y,p,synthetic):assert len(y)==len(p) and np.isfinite(y).all() and np.isfinite(p).all()
rt.admit_metric=admit_metric;sys.modules['public_runtime']=rt;sys.path.insert(0,str(LAB/'code/vendor_public'))
from vhs_sci.evaluate import metric_bundle
def metric(y,p):
 bundle=metric_bundle(y,p,synthetic=False)
 return {**{k:v['value'] for k,v in bundle.items()},'n':len(y),'reason':'|'.join(f'{k}:{v["reason_code"]}' for k,v in bundle.items() if v['reason_code'])}
def main():
 if (ROOT/'pub/EU_PUB_FINAL_STATUS.json').exists():raise FileExistsError('SEALED_PUB_SCORES_EXIST: use verify.py for independent numerical verification')
 seal=readj(ROOT/'pub/PREDICTIONS_SEALED.json');assert sha(ROOT/'KAZ_N1_UG_PREDICTIONS.csv')==seal['sha256']
 with (ROOT/'KAZ_N1_UG_PREDICTIONS.csv').open(encoding='utf-8-sig') as f:preds=list(csv.DictReader(f))
 assert len(preds)==len({(r['scheme'],r['gauge_id'],r['date'],r['model_id']) for r in preds})
 labels={g:readj(ROOT/f'pub/cache/score/ID_{g}.json') for g in readj(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json')['PUB']['stations']}
 rows=[];years=[];seasons=[];checks=[]
 for scheme in sorted({r['scheme'] for r in preds}):
  for g in labels:
   allrs=[r for r in preds if r['scheme']==scheme and int(r['gauge_id'])==g];base={r['date']:float(r['qsim_raw']) for r in allrs if r['model_id']=='DONOR_CLIMATOLOGY_BASELINE'}
   for model in sorted({r['model_id'] for r in allrs}):
    for subset,mo,yy in [('ALL',range(1,13),None),('DJF',[1,2,12],None),('MAY_JUNE',[5,6],None)]+[(str(y),range(1,13),y) for y in range(2014,2018)]:
     rr=[r for r in allrs if r['model_id']==model and r['date'] in labels[g] and int(r['month']) in mo and (yy is None or int(r['year'])==yy)];y=np.array([labels[g][r['date']] for r in rr]);p=np.array([float(r['qsim_raw']) for r in rr]);b=np.array([base[r['date']] for r in rr]);den=float(np.mean((b-y)**2))
     for kind,pp in [('RAW_PRIMARY',p),('NONNEGATIVE_SECONDARY',np.maximum(p,0))]:
      mm=metric(y,pp);item={'experiment':'EUROPEAN_PUB_DEVELOPMENT','country_scope':'EUROPE_NOT_KAZAKHSTAN','scheme':scheme,'gauge_id':g,'macro':rr[0]['macro'],'model_id':model,'subset':subset,'analysis':kind,**mm,'MSE_skill_vs_donor_climate':1-mm['MSE']/den if den>0 else None,'negative_raw_predictions':int(sum(p<0)),'validation_status':'SPATIAL_MASK_DEVELOPMENT_PREVIOUSLY_EXPOSED_DATES_NOT_BLIND'}
      (rows if subset=='ALL' else seasons if yy is None else years).append(item)
      # Independent direct error equation, no implementation-mirroring fit tests.
      assert abs(mm['MSE']-float(np.dot(pp-y,pp-y)/len(y)))<=1e-10*max(1,mm['MSE']);checks.append(True)
 csvout(ROOT/'KAZ_N1_UG_VALIDATION_METRICS.csv',rows);csvout(ROOT/'pub/EU_PUB_YEARLY_METRICS.csv',years);csvout(ROOT/'pub/EU_PUB_SEASONAL_METRICS.csv',seasons)
 summaries=[]
 for scheme in sorted({r['scheme'] for r in rows}):
  for model in sorted({r['model_id'] for r in rows}):
   rr=[r for r in rows if r['scheme']==scheme and r['model_id']==model and r['analysis']=='RAW_PRIMARY'];ns=np.array([r['NSE'] for r in rr]);kg=np.array([r['KGE'] for r in rr]);sk=np.array([r['MSE_skill_vs_donor_climate'] for r in rr]);rr2=[r for r in seasons if r['scheme']==scheme and r['model_id']==model and r['analysis']=='RAW_PRIMARY' and r['subset']=='DJF']
   summaries.append({'experiment':'EUROPEAN_PUB_DEVELOPMENT','scheme':scheme,'model_id':model,'gauges':len(rr),'station_months':sum(r['n'] for r in rr),'NSE_mean':float(np.mean(ns)),'NSE_median':float(np.median(ns)),'KGE_median':float(np.median(kg)),'positive_NSE_count':int(sum(ns>0)),'positive_KGE_count':int(sum(kg>0)),'skill_mean_station_equal':float(sk.mean()),'skill_median':float(np.median(sk)),'positive_skill_count':int(sum(sk>0)),'DJF_positive_NSE_count':sum(r['NSE']>0 for r in rr2),'not_independent_Kazakhstan_accuracy':True})
 csvout(ROOT/'pub/EU_PUB_SUMMARY.csv',summaries)
 macro=[]
 for scheme in sorted({r['scheme'] for r in rows}):
  for model in sorted({r['model_id'] for r in rows}):
   for group in sorted({r['macro'] for r in rows}):
    rr=[r for r in rows if r['scheme']==scheme and r['model_id']==model and r['macro']==group and r['analysis']=='RAW_PRIMARY'];macro.append({'scheme':scheme,'model_id':model,'macro':group,'n_gauges':len(rr),'median_NSE':float(np.median([r['NSE'] for r in rr])),'mean_skill':float(np.mean([r['MSE_skill_vs_donor_climate'] for r in rr])),'inference':'DESCRIPTIVE_ONLY_NOT_INDEPENDENT_REPLICATES'})
 csvout(ROOT/'pub/EU_PUB_MACRO_SUMMARY.csv',macro)
 status={'classification':'EUROPEAN_PUB_DEVELOPMENT','methods':4,'target_gauges':24,'spatial_mask_schemes':2,'prediction_records':len(preds),'unique_station_test_months_per_scheme':len({(r['gauge_id'],r['date']) for r in preds}),'regression_fit_calls':seal['fit_calls'],'donor_climate_fits':seal['climatology_baseline_fits'],'score_process_fit_calls':0,'prediction_process_target_Q_reads':seal['target_Q_reads'],'prediction_process_test_Q_reads':seal['test_period_Q_reads'],'intentional_forbidden_Q_open_tests':seal['intentional_guard_rejections'],'metric_equation_checks':len(checks),'N_Kazakhstan_labels':0,'Kazakhstan_NSE':None,'Kazakhstan_KGE':None,'Kazakhstan_accuracy_status':'NOT_VALIDATED','all_negative_scores_retained':True,'predictions_sealed_before_Q_scoring':True}
 put(ROOT/'pub/EU_PUB_FINAL_STATUS.json',status);print(json.dumps(status),flush=True);print(json.dumps(summaries,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
