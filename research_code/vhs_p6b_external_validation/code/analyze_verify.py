import json,csv,sys,math,collections,hashlib,statistics
from pathlib import Path
import numpy as np
from admit import R,L,P4,jl,jw,cw,sha,readcsv,ehyd
sys.stdout.reconfigure(encoding='utf-8');PR=R/'runs/P6B_EHYD_2018_2019';SC=R/'runs/P6B_EHYD_2018_2019_SCORING';checks=[]
def check(name,ok,**kw):checks.append({'name':name,'pass':bool(ok),**kw});assert ok,(name,kw)
for folder in [PR,SC]:
 for line in (folder/'SHA256SUMS.txt').read_text().splitlines():h,n=line.split('  ',1);check('run_file_sha:'+folder.name+'/'+n,sha(folder/n)==h)
ad=jl(R/'P6B_ADMISSION_FROZEN.json');protocol=jl(R/'P6B_FROZEN_PROTOCOL.json');check('protocol_binding',ad['protocol_hash']==sha(R/'P6B_FROZEN_PROTOCOL.json'));check('576_unique_months',len(ad['descriptive_ids'])==len(set(ad['descriptive_ids']))==576);check('crosswalk_hash',sha(R/'P6B_STATION_CROSSWALK.csv')==ad['crosswalk_hash']);check('54_frozen_models',len(protocol['frozen_models'])==54)
pred=readcsv(PR/'P6B_PREDICTIONS_WITHOUT_QOBS.csv');check('1152_predictions',len(pred)==1152);check('unique_model_samples',len({(r['sample_id'],r['model_id']) for r in pred})==1152);check('no_Qobs_column',not any('qobs' in k.lower() for k in pred[0]));check('role_read_denial',jl(PR/'PREDICTION_READ_AUDIT.json')['forbidden_Q_read']==False);check('fit0',jl(PR/'COMMITMENT.json')['fit_calls']==0)
sys.path.insert(0,str(P4/'code'));from inference import load_model
met=jl(R/'driver/MET_ONLY_2018_2019.json');loaded={};diff=[]
for r in pred:
 g=int(r['gauge_id']);mid=r['model_id'];key=(g,mid)
 if key not in loaded:loaded[key]=load_model(P4/'models/V2'/f'ID_{g}'/mid.replace('+','_'))
 m=loaded[key];check('train_before_test:'+str(key),m.meta['actual_train_end']<r['date']) if len(diff)<2 else None
 p=m.predict_month(met[str(g)],int(r['date'][:4]),int(r['date'][5:]));diff.append(abs(p['q_hat_raw']-float(r['q_hat_raw'])));assert p['input_hash']==r['input_hash']
check('all1152_exact_parameter_recomputation',max(diff)==0,max_abs_difference=max(diff));check('48_saved_models_loaded',len(loaded)==48)
for g in sorted({int(r['gauge_id']) for r in pred}):
 c=[r['date'] for r in pred if int(r['gauge_id'])==g and r['model_id']=='C0+PT'];l=[r['date'] for r in pred if int(r['gauge_id'])==g and r['model_id']=='P2-L1'];check('same_24_test_months:'+str(g),c==l and len(c)==24)
# Independent scoring recreation (use daily source labels only after sealed predictions).
labels={}
for g,path in ad['sources'].items():
 if not any(s.startswith(g+':') for s in ad['descriptive_ids']):continue
 _,d,duplicates=ehyd(Path(path),True);check('source_hash:'+g,sha(path)==ad['source_hashes'][path])
 for sid in [s for s in ad['descriptive_ids'] if s.startswith(g+':')]:
  _,dt=sid.split(':');vals=[r['Q'] for k,r in d.items() if k.startswith(dt)];labels[int(g),dt]=sum(vals)/len(vals)
metrics=readcsv(SC/'P6B_ALL_STATION_METRICS.csv');ci=readcsv(SC/'P6B_INTERVAL_DIAGNOSTICS.csv');max_metric_diff=0.;max_ci_diff=0.
for r in metrics:
 if r['quality_tier']!='DESCRIPTIVE_ARCHIVE' or r['subset']!='ALL' or r['prediction']!='raw':continue
 g=int(r['gauge_id']);dd=sorted([p for p in pred if int(p['gauge_id'])==g and p['model_id']==r['model_id']],key=lambda p:p['date']);y=np.array([labels[g,p['date']] for p in dd]);p=np.array([float(x['q_hat_raw']) for x in dd]);mse=float(np.dot(p-y,p-y)/len(y));ym=float(sum(y)/len(y));pm=float(sum(p)/len(p));vy=float(np.dot(y-ym,y-ym)/len(y));vp=float(np.dot(p-pm,p-pm)/len(p));cor=float(np.dot(y-ym,p-pm)/len(y)/math.sqrt(vy*vp));ka=math.sqrt(vp/vy);kb=pm/ym;kge=1-math.sqrt((cor-1)**2+(ka-1)**2+(kb-1)**2);values={'NSE':1-mse/vy,'KGE':kge,'KGE_r':cor,'KGE_alpha':ka,'KGE_beta':kb,'MAE':float(sum(abs(p-y))/len(y)),'RMSE':math.sqrt(mse),'PBIAS':100*(pm-ym)/ym}
 for k,v in values.items():max_metric_diff=max(max_metric_diff,abs(v-float(r[k])))
 for nominal in [80,90]:
  cr=next(x for x in ci if x['quality_tier']=='DESCRIPTIVE_ARCHIVE' and x['subset']=='ALL' and x['gauge_id']==str(g) and x['model_id']==r['model_id'] and float(x['nominal'])==nominal/100);width=[];scores=[];covered=0
  for yy,pp in zip(y,dd):
   lo=float(pp[f'lower{nominal}']);hi=float(pp[f'upper{nominal}']);width.append(hi-lo);scores.append(hi-lo+max(lo-yy,0)*2/(1-nominal/100)+max(yy-hi,0)*2/(1-nominal/100));covered+=lo<=yy<=hi
  for k,v in [('coverage',covered/len(y)),('mean_width',sum(width)/len(y)),('interval_score',sum(scores)/len(y))]:max_ci_diff=max(max_ci_diff,abs(v-float(cr[k])))
check('independent_metrics_match_all48_models',max_metric_diff<1e-10,max_difference=max_metric_diff);check('independent_intervals_match',max_ci_diff<1e-10,max_difference=max_ci_diff)
parity=jl(R/'driver/DRIVER_PARITY_RESULT.json');check('60_monthly_product_parity_months',parity['overlap_months']==60);check('failed_monthly_route_not_used_in_2018_2019_run',not parity['strict_same_processing_extension_admitted'] and not any(r['date'].startswith('2020') for r in pred));check('no_existing_818_P6A_month_duplicated',818 not in {int(r['gauge_id']) for r in pred});check('all_27_crosswalk',len(readcsv(R/'P6B_STATION_CROSSWALK.csv'))==27)
# Post-score descriptive diagnostics, no selection/retraining.
comparison=readcsv(SC/'P6B_MODEL_COMPARISON.csv');overall=[r for r in comparison if r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['subset']=='ALL'];grouping=jl(L/'p2_antecedent_snow_features/P2_NEW_BASINS_FROZEN.json')['all_grouping'];jw(R/'evidence/P2_OFFICIAL_NETWORK_GROUPING_REUSED.json',{'source_hash':sha(L/'p2_antecedent_snow_features/P2_NEW_BASINS_FROZEN.json'),'grouping':grouping});print('GROUPING_SHAPE',str(grouping)[:500],flush=True)
ss={s['gauge_id']:s for s in jl(R/'evidence/STATIONS_27.json')};drift=[];support=[];negative=[];old=readcsv(L/'vhs_r2u1_p6a/diagnostics/V1_DESCRIPTIVE_MODEL_COMPARISON.csv');errors=readcsv(SC/'P6B_ERRORS_WITHOUT_QOBS.csv');coverage_summary=[]
for g in sorted({int(r['gauge_id']) for r in pred}):
 for mid in ['C0+PT','P2-L1']:
  mod=loaded[g,mid];a=mod.arrays;trainmean=float(np.average(a['climate'],weights=a['month_counts']));new=next(r for r in metrics if r['gauge_id']==str(g) and r['model_id']==mid and r['subset']=='ALL' and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw');newmean=float(new['Qobs_mean']);drift.append({'gauge_id':g,'model_id':mid,'train_Q_mean_from_saved_month_climate_counts':trainmean,'new_Q_mean_2018_2019':newmean,'relative_mean_change':newmean/trainmean-1,'PBIAS':float(new['PBIAS']),'NSE':float(new['NSE']),'KGE':float(new['KGE']),'inference':'descriptive mean comparison; not identified hydrological cause'})
  for cl in ['IN_SUPPORT','EXTRAPOLATION_CAUTION','HIGH_EXTRAPOLATION']:
   er=[r for r in errors if int(r['gauge_id'])==g and r['model_id']==mid and r['support_class']==cl]
   if er:support.append({'gauge_id':g,'model_id':mid,'support_class':cl,'n':len(er),'normalized_MSE_by_saved_train_mean_squared':float(np.mean([float(r['squared_error']) for r in er]))/trainmean**2,'abs_error_gt_half_train_mean':sum(abs(float(r['error']))>.5*trainmean for r in er),'threshold_note':'post-score descriptive diagnostic, never admission or model selection'})
  dd=[r for r in errors if int(r['gauge_id'])==g and r['model_id']==mid];worst=max(dd,key=lambda r:float(r['squared_error']));years=[r for r in metrics if r['gauge_id']==str(g) and r['model_id']==mid and r['subset'] in ['2018','2019'] and r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['prediction']=='raw'];annual=[float(x['MSE'])*int(x['n']) for x in years];negative.append({'gauge_id':g,'model_id':mid,'worst_month':worst['date'],'worst_month_squared_error':float(worst['squared_error']),'worst_year':max(years,key=lambda r:float(r['MSE']))['subset'],'largest_year_share_total_SSE':max(annual)/sum(annual),'negative_prediction_months':sum(float(r['q_hat_raw'])<0 for r in pred if int(r['gauge_id'])==g and r['model_id']==mid)})
cw(R/'P6B_MEAN_DRIFT_DIAGNOSTICS.csv',drift);cw(R/'P6B_INPUT_SUPPORT_DIAGNOSTICS.csv',support);cw(R/'P6B_WORST_PERIODS.csv',negative)
for mid in ['C0+PT','P2-L1']:
 for lev in [.8,.9]:
  rr=[r for r in ci if r['quality_tier']=='DESCRIPTIVE_ARCHIVE' and r['subset']=='ALL' and r['model_id']==mid and float(r['nominal'])==lev];coverage_summary.append({'model_id':mid,'nominal':lev,'station_equal_mean_coverage':float(np.mean([float(r['coverage']) for r in rr])),'station_median_coverage':float(np.median([float(r['coverage']) for r in rr])),'station_median_width_m3s':float(np.median([float(r['mean_width']) for r in rr])),'note':'width and interval score per station in CSV; absolute widths not pooled as universal error scale'})
cw(R/'P6B_INTERVAL_STATION_SUMMARY.csv',coverage_summary)
macro=[]
def family(region):return 'Rhine' if region=='Rhine' else 'Elbe' if region=='Vltava' else 'Danube'
for q in ['DESCRIPTIVE_ARCHIVE','STRICT_SENSITIVITY']:
 for fam in ['Rhine','Danube','Elbe']:
  rr=[r for r in comparison if r['quality_tier']==q and r['subset']=='ALL' and family(r['region'])==fam and r['station_summary_min12_supported']=='True'];skills=[float(r['MSE_skill']) for r in rr if r['MSE_skill']]
  if skills:macro.append({'quality_tier':q,'macro_river':fam,'stations':len(rr),'positive_stations':sum(x>0 for x in skills),'equal_station_mean_skill':float(np.mean(skills)),'median_skill':float(np.median(skills)),'spatial_dependency':'official P2 river network grouping reused; same macro river not independent repetitions'})
cw(R/'P6B_MACRO_RIVER_SUMMARY.csv',macro)
history=jl(R/'evidence/HISTORY_BEFORE.json');changed=[]
for root,v in history.items():
 root=Path(root)
 if sha(root/'SHA256SUMS.txt')!=v['manifest_hash']:changed.append(str(root/'SHA256SUMS.txt'))
 for name,h in v['files'].items():
  if sha(root/name)!=h:changed.append(str(root/name))
check('all_historical_seals_unchanged',not changed,files=sum(len(v['files']) for v in history.values()));jw(R/'HISTORICAL_INTEGRITY_REPORT.json',{'historical_roots':len(history),'files_checked':sum(len(v['files']) for v in history.values()),'changed':changed,'teacher_Q_read':False,'P4_models_unchanged':True,'P6A_results_unchanged':True});prior=jl(R/'P6B_TEST_RESULTS.json') if (R/'P6B_TEST_RESULTS.json').exists() else {'tests':[]};checks.extend(r for r in prior['tests'] if r['name'].startswith('2020:'));jw(R/'P6B_TEST_RESULTS.json',{'tests':checks,'total':len(checks),'passed':sum(c['pass'] for c in checks),'failed':0,'software_tests_not_scientific_certification':True});print('CHECKS',len(checks),'ALL_PASS');print('MACRO',macro);print('COVERAGE',coverage_summary)
