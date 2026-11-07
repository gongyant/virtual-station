"""Frozen-model decomposition and alpha/uncertainty audit. No fit, no new tuning."""
import csv,json,hashlib,sys,calendar,collections,math
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');LAB=R.parent;P4=LAB/'p4_final_reconstruction';D=R/'diagnostics'
sys.path.insert(0,str(P4/'code'))
from inference import load_model
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def cr(p,delimiter=','):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f,delimiter=delimiter))
def jw(n,x):(D/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cw(n,rows):
 with (D/n).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def corr(a,b):
 return float(np.corrcoef(a,b)[0,1]) if len(a)>1 and np.std(a)>1e-14 and np.std(b)>1e-14 else None
def mean(a):return float(np.mean(a))
bundle=jl(LAB/'vhs_web_r1_public_results_bridge/data/bundle.json');snapshot=jl(P4/'source/SNAPSHOT.json')
features=cr(P4/'source/features.csv');FM={r['sample_id']:r for r in features};weather=cr(P4/'source/weather.csv');WM=collections.defaultdict(dict)
for r in weather:
 WM[int(r['gauge_id'])][r['date']]={k:float(r[k]) if r[k] else None for k in ['P','T']}
models={};alpha=[];coef=[];calibration=[];reload=[];decomp=[]
for version in ['V1','V2']:
 for g in sorted(s['gauge_id'] for s in bundle['stations']):
  for mid in ['C0+PT','P2-L1']:
   path=P4/'models'/version/f'ID_{g}'/mid.replace('+','_');m=load_model(path);models[version,g,mid]=m;meta=m.meta;a=m.arrays
   grid=meta['nested_CV'];alphas=[r['alpha'] for r in grid];best=min(grid,key=lambda r:(r['mean_year_MSE_raw'],r['alpha']));cut=best['mean_year_MSE_raw']+best['standard_error'];tol=meta['parameters']['selection']['comparison_tolerance'];selected=max(r['alpha'] for r in grid if r['mean_year_MSE_raw']<=cut+tol)
   assert alphas==[.01,.1,1.,10.,100.] and selected==meta['parameters']['selection']['selected_alpha']
   ids=meta['train_ids'];raw=np.array([[float(FM[i][k]) for k in m.fields] for i in ids]);months=np.array([int(FM[i]['month'])-1 for i in ids]);Z=np.where(a['constant'][months],0,(raw-a['mu'][months])/np.where(a['constant'][months],1,a['sd'][months]))
   cent=max(float(np.max(abs(Z[months==mm].mean(axis=0)))) for mm in range(12));eigen=np.linalg.eigvalsh(Z.T@Z)
   recompute_mu=max(float(np.max(abs(raw[months==mm].mean(axis=0)-a['mu'][mm]))) for mm in range(12));recompute_sd=max(float(np.max(abs(raw[months==mm].std(axis=0,ddof=1)-a['sd'][mm]))) for mm in range(12))
   alpha.append({'version':version,'gauge_id':g,'model_id':mid,'alpha':selected,'best_alpha':best['alpha'],'at_grid_upper_boundary':selected==max(alphas),'oneSE_candidates':','.join(str(r['alpha']) for r in grid if r['mean_year_MSE_raw']<=cut+tol),'loss_at100':grid[-1]['mean_year_MSE_raw'],'minimum_loss':best['mean_year_MSE_raw'],'oneSE_cutoff':cut,'upper_grid_margin':cut-grid[-1]['mean_year_MSE_raw'],'training_months':len(ids),'center_maxabs':cent,'mu_reproduction_maxabs':recompute_mu,'sd_reproduction_maxabs':recompute_sd,'gram_eigen_min':float(min(eigen)),'gram_eigen_max':float(max(eigen)),'shrink_eigen_min':float(min(eigen/(eigen+selected))),'shrink_eigen_max':float(max(eigen/(eigen+selected))),'model_hash':m.hash})
   for j,k in enumerate(m.fields):
    for mm in range(12):coef.append({'version':version,'gauge_id':g,'model_id':mid,'month':mm+1,'feature':k,'training_mean':float(a['mu'][mm,j]),'training_std_ddof1':float(a['sd'][mm,j]),'constant':bool(a['constant'][mm,j]),'beta_per_standard_deviation':float(a['beta'][j]),'slope_per_raw_unit':float(a['beta'][j]/a['sd'][mm,j]) if not a['constant'][mm,j] else None})
   for season,c in m.calibration.items():
    n=c['n_OOF_primary12'];row={'version':version,'gauge_id':g,'model_id':mid,'season':season,**c,'rank80':math.ceil((n+1)*.8),'rank90':math.ceil((n+1)*.9),'90_uses_max_abs_residual':math.ceil((n+1)*.9)==n,'mean_monthly_Q_climate':mean(a['climate'])};calibration.append(row)
cw('ALPHA_108_MODEL_AUDIT.csv',alpha);cw('COEFFICIENT_SCALE_BY_MONTH.csv',coef);cw('INTERVAL_CALIBRATION_MECHANISM.csv',calibration)
for r in bundle['predictions']:
 if r['prediction_kind'] not in ['TEMPORAL_HOLDOUT','FINAL_MODEL_APPLICATION']:continue
 version='V1' if r['prediction_kind']=='TEMPORAL_HOLDOUT' else 'V2';g=r['gauge_id'];mid=r['model_id'];m=models[version,g,mid];a=m.arrays;mm=r['month']-1;dt=f'{r["year"]}-{r["month"]:02d}';prev=f'{r["year"] if r["month"]>1 else r["year"]-1}-{r["month"]-1 if r["month"]>1 else 12:02d}'
 raw=np.array([WM[g][prev]['P'] if k=='L1' else WM[g][dt][k] for k in m.fields]);z=np.where(a['constant'][mm],0,(raw-a['mu'][mm])/np.where(a['constant'][mm],1,a['sd'][mm]));terms=z*a['beta'];baseline=float(a['climate'][mm]);pred=float(baseline+sum(terms));error=abs(pred-r['qsim_raw'])
 assert error<1e-10*max(1,abs(r['qsim_raw'])),('RELOAD_MISMATCH',g,mid,dt,error)
 row={'version':version,'prediction_kind':r['prediction_kind'],'gauge_id':g,'model_id':mid,'date':dt,'year':r['year'],'month':r['month'],'seasonal_baseline':baseline,'P_contribution':float(terms[0]),'T_contribution':float(terms[1]),'L1_contribution':float(terms[2]) if len(terms)>2 else 0.,'total_meteorological_correction':float(sum(terms)),'qsim_frozen':r['qsim_raw'],'qsim_recomputed':pred,'reproduction_abs_error':error,'model_hash':m.hash}
 decomp.append(row);reload.append(error)
cw('FROZEN_PREDICTION_DECOMPOSITION.csv',decomp)
jw('FROZEN_RECOMPUTATION_LOG.json',{'fit_calls':0,'prediction_count':len(decomp),'max_abs_error':max(reload),'tolerance':'1e-10*max(1,abs(Qsim))','frozen_outputs_unchanged':True,'P4_V1_prediction_hash':sha(P4/'P4_V1_PREDICTIONS.csv'),'R1_bundle_hash':sha(LAB/'vhs_web_r1_public_results_bridge/data/bundle.json')})
# Old labels only; independent new P6 labels are not opened here.
V1=[r for r in decomp if r['version']=='V1'];needed={(r['gauge_id'],r['date']) for r in V1};labels={}
for g in sorted({g for g,dt in needed}):
 groups=collections.defaultdict(list)
 for rr in cr(snapshot['source_paths'][str(g)]['Q'],';'):
  dt=f'{int(rr["YYYY"]):04d}-{int(rr["MM"]):02d}'
  if (g,dt) in needed:groups[dt].append(rr)
 for dt,rr in groups.items():
  y,mo=map(int,dt.split('-'));expected=calendar.monthrange(y,mo)[1];assert len(rr)==expected and len({int(x['DD']) for x in rr})==expected and all(x['ckhs']=='1' for x in rr)
  vals=[float(x['qobs']) for x in rr];assert all(math.isfinite(v) and v>=0 for v in vals);labels[g,dt]=sum(vals)/expected
assert len(labels)==899
summaries=[];monthly=[];peaks=[];comparison=[];yearly=[];cases=[]
for version in ['V1','V2']:
 for g in sorted({r['gauge_id'] for r in decomp if r['version']==version}):
  rr=[r for r in decomp if r['version']==version and r['gauge_id']==g];by={mid:sorted([r for r in rr if r['model_id']==mid],key=lambda r:r['date']) for mid in ['C0+PT','P2-L1']}
  assert [r['date'] for r in by['C0+PT']]==[r['date'] for r in by['P2-L1']]
  for mid,rs in by.items():
   pred=np.array([r['qsim_frozen'] for r in rs]);base=np.array([r['seasonal_baseline'] for r in rs]);inc=pred-base;num=len(rs)
   row={'version':version,'gauge_id':g,'model_id':mid,'n':num,'correlation_prediction_vs_template':corr(pred,base),'meteorological_correction_abs_mean':mean(abs(inc)),'meteorological_correction_RMS':float(np.sqrt(mean(inc**2))),'template_std':float(np.std(base)),'prediction_std':float(np.std(pred)),'correction_RMS_to_template_std':float(np.sqrt(mean(inc**2))/np.std(base)) if np.std(base)>0 else None}
   if version=='V1':
    obs=np.array([labels[g,r['date']] for r in rs]);sse=float(sum((pred-obs)**2));base_sse=float(sum((base-obs)**2));den=float(sum((obs-obs.mean())**2));row.update({'frozen_NSE':1-sse/den if den>0 else None,'MSE_skill_over_template':1-sse/base_sse if base_sse>0 else None,'mean_bias':mean(pred-obs),'observed_mean':mean(obs),'predicted_mean':mean(pred),'MSE':sse/num,'template_MSE':base_sse/num,'anomaly_corr_fixed_training_template':corr(pred-base,obs-base)})
   summaries.append(row)
   for mo in range(1,13):
    rs_m=[r for r in rs if r['month']==mo]
    if not rs_m:continue
    data={'version':version,'gauge_id':g,'model_id':mid,'month':mo,'n':len(rs_m),'mean_abs_P_contribution':mean([abs(r['P_contribution']) for r in rs_m]),'mean_abs_T_contribution':mean([abs(r['T_contribution']) for r in rs_m]),'mean_abs_L1_contribution':mean([abs(r['L1_contribution']) for r in rs_m]),'mean_total_correction':mean([r['total_meteorological_correction'] for r in rs_m]),'mean_abs_total_correction':mean([abs(r['total_meteorological_correction']) for r in rs_m])}
    monthly.append(data)
   for y in sorted({r['year'] for r in rs}):
    yr=[r for r in rs if r['year']==y];peak=max(yr,key=lambda r:r['qsim_frozen']);clpeak=max(yr,key=lambda r:r['seasonal_baseline']);peaks.append({'version':version,'gauge_id':g,'model_id':mid,'year':y,'peak_month':peak['month'],'predicted_peak':peak['qsim_frozen'],'seasonal_template_peak_month':clpeak['month'],'annual_predicted_mean':mean([r['qsim_frozen'] for r in yr]),'annual_template_mean':mean([r['seasonal_baseline'] for r in yr])})
  delta=np.array([b['qsim_frozen']-a['qsim_frozen'] for a,b in zip(by['C0+PT'],by['P2-L1'])]);baseline_diff=max(abs(a['seasonal_baseline']-b['seasonal_baseline']) for a,b in zip(by['C0+PT'],by['P2-L1']))
  assert baseline_diff<1e-12
  if version=='V1':
   for subset in ['ALL','DJF','MAY_JUNE']+[str(y) for y in [2015,2016,2017]]:
    pairs=[(a,b) for a,b in zip(by['C0+PT'],by['P2-L1']) if subset=='ALL' or subset=='DJF' and a['month'] in [12,1,2] or subset=='MAY_JUNE' and a['month'] in [5,6] or subset==str(a['year'])]
    if not pairs:continue
    obs=np.array([labels[g,a['date']] for a,b in pairs]);c=np.array([a['qsim_frozen'] for a,b in pairs]);l=np.array([b['qsim_frozen'] for a,b in pairs]);cm=mean((c-obs)**2);lm=mean((l-obs)**2)
    comparison.append({'gauge_id':g,'subset':subset,'n':len(pairs),'MSE_C0PT':cm,'MSE_L1':lm,'MSE_skill':1-lm/cm if cm else None,'mean_L1_minus_C0PT':mean(l-c),'mean_abs_L1_minus_C0PT':mean(abs(l-c)),'bias_C0PT':mean(c-obs),'bias_L1':mean(l-obs),'observed_mean':mean(obs),'predicted_C0PT_mean':mean(c),'predicted_L1_mean':mean(l)})
   improvements=[]
   for y in [2015,2016,2017]:
    pairs=[(a,b) for a,b in zip(by['C0+PT'],by['P2-L1']) if a['year']==y]
    if pairs:
     gain=sum((a['qsim_frozen']-labels[g,a['date']])**2-(b['qsim_frozen']-labels[g,b['date']])**2 for a,b in pairs);improvements.append((y,gain));yearly.append({'gauge_id':g,'year':y,'SSE_improvement_L1':gain})
   total=sum(v for y,v in improvements);jack=[total-v for y,v in improvements]
   cases.append({'gauge_id':g,'positive_years':sum(v>0 for y,v in improvements),'n_years':len(improvements),'total_SSE_improvement':total,'jackknife_all_remaining_improvements_positive':all(x>0 for x in jack),'largest_absolute_year_share':max(abs(v) for y,v in improvements)/sum(abs(v) for y,v in improvements) if sum(abs(v) for y,v in improvements)>0 else None,'max_single_month_abs_model_delta':float(max(abs(delta))),'mean_abs_model_delta':mean(abs(delta))})
# Different summary schemas across V1/V2 normalized for CSV.
fields=sorted(set().union(*(r.keys() for r in summaries)));summaries=[{k:r.get(k) for k in fields} for r in summaries]
cw('PREDICTION_TEMPLATE_SUMMARY.csv',summaries);cw('MONTHLY_METEOROLOGICAL_CONTRIBUTIONS.csv',monthly);cw('YEARLY_PREDICTED_PEAKS.csv',peaks);cw('V1_DESCRIPTIVE_MODEL_COMPARISON.csv',comparison);cw('V1_YEAR_CONTRIBUTIONS.csv',yearly);cw('V1_STABILITY_DIAGNOSTICS.csv',cases)
frozen_eval={(int(r['gauge_id']),r['model_id']):float(r['NSE']) for r in cr(P4/'P4_V1_EVALUATION.csv') if r['prediction']=='raw'}
errs=[abs(r['frozen_NSE']-frozen_eval[r['gauge_id'],r['model_id']]) for r in summaries if r['version']=='V1'];assert max(errs)<1e-12
result={'classification':'DESCRIPTIVE_FROZEN_V1_V2_DIAGNOSTICS_NOT_P6','fit_calls':0,'frozen_prediction_reproductions':len(decomp),'max_reproduction_abs_error':max(reload),'old_test_label_months':899,'old_metric_max_NSE_reproduction_error':max(errs),'alpha_model_count':len(alpha),'alpha_selected_counts':dict(collections.Counter(str(r['alpha']) for r in alpha)),'CV_best_alpha_counts':dict(collections.Counter(str(r['best_alpha']) for r in alpha)),'all_oneSE_selections_recomputed_correctly':True,'max_standardized_training_month_mean':max(r['center_maxabs'] for r in alpha),'max_mu_error':max(r['mu_reproduction_maxabs'] for r in alpha),'max_sd_error':max(r['sd_reproduction_maxabs'] for r in alpha),'calibration_n_counts':dict(collections.Counter(str(r['n_OOF_primary12']) for r in calibration)),'rank90_max_residual_count':sum(r['90_uses_max_abs_residual'] for r in calibration),'kappa_gt1_count':sum(r['kappa'] is not None and r['kappa']>1 for r in calibration),'v1_positive_L1_basins':sum(r['subset']=='ALL' and r['MSE_skill']>0 for r in comparison),'v1_positive_template_improvement_models':sum(r['version']=='V1' and r['MSE_skill_over_template']>0 for r in summaries),'median_V1_L1_template_correlation':float(np.median([r['correlation_prediction_vs_template'] for r in summaries if r['version']=='V1' and r['model_id']=='P2-L1']))}
jw('DIAGNOSTIC_SUMMARY.json',result)
# No individual Qobs enters the UI diagnostic bundle.
jw('UI_DECOMPOSITION.json',{'summary':result,'records':decomp,'station_summary':summaries,'alpha':alpha,'stability':cases,'comparison':comparison,'calibration':calibration,'definition':'L1-C0PT includes direct L1 plus refitted contemporaneous P/T coefficient effects. No causal attribution.'})
print(json.dumps(result,ensure_ascii=False,indent=2));print('REPRESENTATIVE_SKILLS',json.dumps([r for r in comparison if r['gauge_id'] in [2,9,533,185,171,378,383,455] and r['subset']=='ALL'],ensure_ascii=False))
