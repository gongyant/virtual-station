"""Final derived-table/source-data audit; no model execution."""
from p6d_common import *
from statistics import mean,median
import shutil
sys.stdout.reconfigure(encoding='utf-8');checks=[]
def ck(name,b,detail=None):checks.append({'name':name,'pass':bool(b),'detail':detail})
rows=cr(R/'P6D_MONTHLY_PAIRED_ERRORS.csv');season=cr(R/'P6D_SEASONAL_AND_DRIFT.csv');intervals=cr(R/'P6D_INTERVAL_AND_QC_DIAGNOSTICS.csv');ids=jl(R/'P6D_DIAGNOSTIC_PROTOCOL.json')['gauge_ids']
for r in cr(R/'P6D_MONTH_OF_YEAR_LOSS_SHARES.csv'):
 shares=[];col='SE_C0PT' if r['model_id']=='C0+PT' else 'SE_L1'
 for g in ids:
  ss=[x for x in rows if x['year']==r['year'] and int(x['gauge_id'])==g];den=sum(float(x[col]) for x in ss)
  if den:shares.append(sum(float(x[col]) for x in ss if x['month']==r['month'])/den)
 ck('MONTH_SHARE_'+r['year']+r['model_id']+r['month'],near(mean(shares),r['mean_station_annual_SSE_share']) and near(median(shares),r['median_station_annual_SSE_share']))
for r in cr(R/'P6D_FAILURE_TYPE_SUMMARY.csv'):
 ss=[s for s in season if s['period']==r['period'] and s['subset']==r['subset'] and s['model_id']=='P2-L1'];both=sum(float(s['NSE'])<0 and float(s['MSE_skill_L1_vs_C0PT'])<0 for s in ss);rel=sum(float(s['NSE'])>=0 and float(s['MSE_skill_L1_vs_C0PT'])<0 for s in ss);ab=sum(float(s['NSE'])<0 and float(s['MSE_skill_L1_vs_C0PT'])>=0 for s in ss);ck('FAILURE_TYPE_'+r['period']+r['subset'],both==int(r['both_relative_and_absolute_failure']) and rel==int(r['relative_only']) and ab==int(r['absolute_only_despite_gain']))
for r in cr(R/'P6D_INTERVAL_STATION_EQUAL_SUMMARY.csv'):
 expected={'2018_2019':24,'2020':12,'2018_2020':36}[r['period']];ss=[s for s in intervals if all(s[k]==r[k] for k in ['period','quality_tier','subset','model_id','nominal']) and int(s['n'])>0 and (r['subset']!='ALL' or int(s['n'])==expected)];ok=len(ss)==int(r['stations'])
 for key in ['coverage','mean_width_m3s','mean_interval_score_m3s','width_divided_by_Qobs_mean','width_divided_by_Qobs_std','interval_score_divided_by_Qobs_mean']:
  vv=[float(s[key]) for s in ss if s[key]!=''];ok=ok and near(mean(vv) if vv else None,r['station_equal_mean_'+key]) and near(median(vv) if vv else None,r['station_median_'+key])
 ck('INTERVAL_AGG_'+':'.join(r[k] for k in ['period','quality_tier','subset','model_id','nominal']),ok)
for fig in jl(R/'P6D_FIGURE_PROVENANCE.json'):
 ck('FIGURE_SCRIPT_'+fig['name'],sha(R/'code/figures.py')==fig['script_sha256'])
 for file,h in {**fig['sources'],**fig['files']}.items():ck('FIGURE_SOURCE_HASH_'+fig['name']+file,sha(R/file)==h)
 alignment=jl(R/'figure_qa'/f'{fig["name"]}.alignment.json');ck('FIGURE_ALIGNMENT_FILE_'+fig['name'],not any(str(v)=='FIX BEFORE DELIVERY' for v in alignment.values()))
hist=jl(R/'evidence/HISTORY_BEFORE.json');changed=[p for p,h in hist.items() if sha(p)!=h];ck('FINAL_HISTORY_UNCHANGED',not changed,{'checked':len(hist),'changed':changed});before=sha(R/'SHA256SUMS.txt');oldlines=(R/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines();oldbad=[n for h,n in (x.split('  ',1) for x in oldlines) if sha(R/n)!=h];ck('EXISTING_DELIVERY_HASHES',not oldbad,oldbad)
# The verifier itself is a final new delivery file, deliberately absent from the prior seal.
report={'passed':sum(c['pass'] for c in checks),'failed':sum(not c['pass'] for c in checks),'checks':checks,'history_entries_unchanged':len(hist)-len(changed),'fit_calls':0,'models_executed':0,'prior_manifest_hash':before};jw(R/'P6D_DELIVERY_VERIFICATION.json',report)
if report['failed']:print([c for c in checks if not c['pass']]);sys.exit(1)
shutil.copy2(R/'SHA256SUMS.txt',R/'evidence/PRE_DELIVERY_REVIEW_SHA256SUMS.txt');status=jl(R/'P6D_FINAL_STATUS.json');status['delivery_checks']={'passed':report['passed'],'failed':report['failed']};jw(R/'P6D_FINAL_STATUS.json',status);event('P6D_FINAL_DELIVERY_VERIFIED',passed=report['passed'],failed=report['failed'],history_unchanged=len(hist),fit_calls=0);seal(R);print('FINAL_DELIVERY',report['passed'],'PASS',report['failed'],'FAIL');print('ROOT_MANIFEST_SHA256',sha(R/'SHA256SUMS.txt'))
