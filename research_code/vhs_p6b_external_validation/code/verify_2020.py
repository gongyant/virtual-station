import sys,json,math,calendar
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,sha,readcsv
P=R/'runs/P6B_ID818_2020';S=R/'runs/P6B_ID818_2020_SCORING';checks=[]
def ck(name,value,**kw):checks.append({'name':name,'pass':bool(value),**kw});assert value,(name,kw)
for root in [P,S]:
 for l in (root/'SHA256SUMS.txt').read_text().splitlines():h,n=l.split('  ',1);ck('2020seal:'+root.name+'/'+n,sha(root/n)==h)
a=jl(R/'P6B_2020_ADMISSION_FROZEN.json');par=jl(R/'driver/ARCO_LEGACY_PARITY_RESULT.json');ck('60of60_original_hourly_chain_parity',par['months_passed']==60 and par['same_processing_2020_admitted']);ck('hourly_source_equivalence',par['original_hourly_equivalence']['pass']);ck('2020_parity_binding',a['parity_result_hash']==sha(R/'driver/ARCO_LEGACY_PARITY_RESULT.json'));ck('parent_protocol_binding',a['parent_protocol_hash']==sha(R/'P6B_FROZEN_PROTOCOL.json'));ck('met_hash_binding',a['met_hash']==sha(R/'driver/ID818_2020_MET_ONLY.json'));ck('measured_Q_source_hash',a['new_Q_hash']==sha(a['new_Q_file']));ck('fit0',jl(P/'COMMITMENT.json')['fit_calls']==0);ck('2020_no_label_read_predictor',jl(P/'PREDICTION_READ_AUDIT.json')['Q_label_read_attempts']==0)
pred=readcsv(P/'P6B_2020_PREDICTIONS_WITHOUT_QOBS.csv');met=jl(R/'driver/ID818_2020_MET_ONLY.json');ck('24_unique_predictions',len(pred)==len({(x['model_id'],x['date']) for x in pred})==24);ck('12_real_test_months',len({r['date'] for r in pred})==12);ck('no_Qobs_column',not any('qobs' in k.lower() for k in pred[0]));ck('lag_is_original_2019_12',met[0]==next(r for r in jl(R/'driver/MET_ONLY_2018_2019.json')['818'] if r['date']=='2019-12'))
sys.path.insert(0,str(P4/'code'));from inference import load_model
diff=[]
for mid in ['C0+PT','P2-L1']:
 m=load_model(P4/'models/V2/ID_818'/mid.replace('+','_'));dd=sorted([r for r in pred if r['model_id']==mid],key=lambda r:r['date']);ck('2020_train_labels_strictly_before_test:'+mid,m.meta['actual_train_end']<'2020-01')
 for r in dd:
  p=m.predict_month(met,2020,int(r['date'][5:]));diff.append(abs(p['q_hat_raw']-float(r['q_hat_raw'])));assert p['input_hash']==r['input_hash']
ck('24_predictions_exact_recompute',max(diff)==0,max_difference=max(diff))
daily=readcsv(a['new_Q_file']);groups={}
for r in daily:
 if r['date'].startswith('2020-'):groups.setdefault(r['date'][:7],[]).append(float(r['discharge_vol(m3/s)']))
ck('366_real_finite_nonnegative_days',sum(map(len,groups.values()))==366 and all(all(math.isfinite(v) and v>=0 for v in vv) for vv in groups.values()));labels={dt:sum(v)/len(v) for dt,v in groups.items()};rows=readcsv(S/'P6B_2020_METRICS.csv');cis=readcsv(S/'P6B_2020_INTERVALS.csv');maxdiff=0.;cidiff=0.
for mid in ['C0+PT','P2-L1']:
 dd=sorted([r for r in pred if r['model_id']==mid],key=lambda r:r['date']);y=np.array([labels[r['date']] for r in dd]);p=np.array([float(r['q_hat_raw']) for r in dd]);err=p-y;yc=y-y.mean();pc=p-p.mean();mse=float(err@err/12);cor=float(yc@pc/math.sqrt((yc@yc)*(pc@pc)));al=math.sqrt(float((pc@pc)/(yc@yc)));be=float(p.mean()/y.mean());ind={'MSE':mse,'RMSE':math.sqrt(mse),'MAE':float(sum(abs(err))/12),'NSE':1-float((err@err)/(yc@yc)),'KGE_r':cor,'KGE_alpha':al,'KGE_beta':be,'KGE':1-math.sqrt((cor-1)**2+(al-1)**2+(be-1)**2),'PBIAS':100*float((p.sum()-y.sum())/y.sum())};row=next(r for r in rows if r['model_id']==mid and r['subset']=='ALL' and r['prediction']=='raw')
 for k,v in ind.items():maxdiff=max(maxdiff,abs(v-float(row[k])))
 for lev in [80,90]:
  lo=np.array([float(r[f'lower{lev}']) for r in dd]);hi=np.array([float(r[f'upper{lev}']) for r in dd]);width=hi-lo;coverage=sum((lo<=y)&(y<=hi))/12;score=float(np.mean(width+np.maximum(lo-y,0)*2/(1-lev/100)+np.maximum(y-hi,0)*2/(1-lev/100)));ci=next(r for r in cis if r['model_id']==mid and r['subset']=='ALL' and float(r['nominal'])==lev/100)
  for k,v in [('coverage',coverage),('mean_width',float(width.mean())),('interval_score',score)]:cidiff=max(cidiff,abs(v-float(ci[k])))
ck('2020_independent_metrics_match',maxdiff<1e-10,max_difference=maxdiff);ck('2020_independent_intervals_match',cidiff<1e-10,max_difference=cidiff)
if (R/'P6B_NEW_PREDICTIONS_WITHOUT_QOBS.csv').exists():
 unified=readcsv(R/'P6B_NEW_PREDICTIONS_WITHOUT_QOBS.csv');ck('merged1176_unique_model_sample_keys',len(unified)==len({(r['sample_id'],r['model_id']) for r in unified})==1176);ck('merged_no_Qobs',not any('qobs' in k.lower() for k in unified[0]));old=readcsv(R/'runs/P6B_EHYD_2018_2019/P6B_PREDICTIONS_WITHOUT_QOBS.csv');expected={(r['sample_id'],r['model_id']):(r['q_hat_raw'],r['model_hash'],r['input_hash']) for r in old+pred};ck('merged_identity_values_match_both_immutable_runs',all(expected[r['sample_id'],r['model_id']]==(r['q_hat_raw'],r['model_hash'],r['input_hash']) for r in unified));cross=readcsv(R/'P6B_STATION_CROSSWALK_FINAL.csv');ck('27station_final_crosswalk_588_months',len(cross)==27 and sum(int(r['independent_scored_months_P6B']) for r in cross)==588)
base=jl(R/'P6B_TEST_RESULTS.json');base['tests']=[r for r in base['tests'] if not r['name'].startswith('2020:')];base['tests'].extend({'name':'2020:'+x['name'],**{k:v for k,v in x.items() if k!='name'}} for x in checks);base['total']=len(base['tests']);base['passed']=sum(r['pass'] for r in base['tests']);base['failed']=base['total']-base['passed'];jw(R/'P6B_TEST_RESULTS.json',base);jw(R/'P6B_2020_VERIFICATION.json',{'tests':checks,'passed':len(checks),'max_prediction_recompute_diff':max(diff),'max_metric_difference':maxdiff,'max_interval_difference':cidiff,'software_pass_not_QC_certification':True});print('2020_CHECKS',len(checks),'ALL_PASS','TOTAL',base['passed'])
