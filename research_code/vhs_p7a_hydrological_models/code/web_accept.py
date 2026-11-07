"""Live original-host acceptance, identity joins and refusals, no fitting or scoring."""
from common import *
import urllib.request,urllib.parse,urllib.error
BASE='http://127.0.0.1:8794';checks=[]
def ck(name,v):checks.append({'name':name,'passed':bool(v)})
def api(path,q=None,method='GET'):
 url=BASE+path+('?' +urllib.parse.urlencode(q) if q else '')
 req=urllib.request.Request(url,method=method,data=b'{}' if method=='POST' else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=15) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
def main():
 code,h=api('/api/vhs/health');ck('original_v06_host_live',code==200 and h['app_version']=='0.6.0');ck('teacher_not_mounted',h['datasets']['SYRDARYA']=='SOURCE_MISSING' and not h['r2_candidate']['teacher_source_mounted'])
 code,c=api('/api/v6/candidate-public/catalog');ck('old54models_retained',code==200 and len(c['models'])==54);ck('old27stations_retained',len(c['stations'])==27)
 code,new=api('/api/v6/candidate-public/research/catalog',{'dataset':'LAMAH_CE_PUBLIC_V1'});ck('27_catalog',code==200 and len(new['stations'])==27);ck('24_external_cohort',sum(s['P6_external_station'] for s in new['stations'])==24)
 src=rows(LAB/'vhs_p6d_failure_diagnostics/P6D_STATION_YEAR_FAILURES.csv');paired=rows(LAB/'vhs_p6d_failure_diagnostics/P6D_MONTHLY_PAIRED_ERRORS.csv')
 for period,scope in new['periods'].items():
  n=0
  for g in GAUGES:
   q={'dataset':'LAMAH_CE_PUBLIC_V1','station':f'LAMAH_CE_PUBLIC_V1:{g}','period':period,'snapshot':scope['source_snapshot_id'],'model':'P2-L1'}
   st,d=api('/api/v6/candidate-public/research/station',q);ck(f'{g}_{period}_read',st==200);n+=len(d.get('records',[]))
   ck(f'{g}_{period}_no_default_Qobs',all('Qobs' not in r for r in d['records']))
   expected=next(r for r in src if int(r['gauge_id'])==g and r['period']==period and r['quality_tier']=='MAIN_DESCRIPTIVE');ck(f'{g}_{period}_exact_period_identity',len(d['metrics'])==1);m=d['metrics'][0]
   for field in ['L1_NSE','L1_KGE','C0PT_NSE','C0PT_KGE','MSE_skill','L1_top1_SSE_fraction']:
    ck(f'{g}_{period}_{field}',abs(float(m[field])-float(expected[field]))<1e-12)
   expectedbydate={r['date']:r for r in paired if int(r['gauge_id'])==g}
   for r in d['records']:ck(f'prediction_{g}_{r["date"]}_{period}',r['Qsim_L1']==float(expectedbydate[r['date']]['Qsim_L1']))
   ck(f'{g}_{period}_decomposition_count',len(d['decomposition'])==2*len(d['records']))
   ck(f'{g}_{period}_preserved_reach_boundary',d['reach_status']=='REACH_PREDICTION_NOT_AVAILABLE')
  ck(period+'_coverage_count',n=={'2018_2019':576,'2020':288,'2018_2020':864}[period])
 q={'dataset':'LAMAH_CE_PUBLIC_V1','station':'LAMAH_CE_PUBLIC_V1:171','model':'P2-L1','period':'2020','snapshot':new['periods']['2020']['source_snapshot_id']}
 st,d=api('/api/v6/candidate-public/research/station',{**q,'local_qobs':'1'});ck('local_single_station_observation_scope',st==200 and len(d['records'])==12 and all('Qobs' in r and r['gauge_id']==171 for r in d['records']))
 for name,extra,expected in [('wrong_snapshot',{'snapshot':new['periods']['2018_2019']['source_snapshot_id']},409),('teacher_dataset',{'dataset':'SYRDARYA'},403),('wrong_station',{'station':'SYRDARYA:171'},400),('unreleased_model',{'model':'P7-MEM'},400),('bulk_export',{'format':'csv','local_qobs':'1'},403),('invalid_window',{'start':'2020-13'},400)]:
  st,d=api('/api/v6/candidate-public/research/station',{**q,**extra});ck(name,st==expected)
 for g in [611,688,818]:
  st,d=api('/api/v6/candidate-public/research/station',{**q,'station':f'LAMAH_CE_PUBLIC_V1:{g}'});ck('no_false_zero_'+str(g),st==200 and d['status']=='NOT_EVALUATED' and not d['metrics'] and not d['records'])
 for path,method in [('/api/v6/public/catalog','GET'),('/api/v6/candidate-public/research/execute','GET'),('/api/v6/candidate-public/research/export','GET'),('/api/v6/model/execute','POST'),('/api/vhs/predict','POST')]:
  st,d=api(path,q,method);ck('403_'+path,st==403)
 # Frozen V1 scores and V2 applications are not merged with P6.
 st,v1=api('/api/v6/candidate-public/results/evaluation',{'dataset':'LAMAH_CE_PUBLIC_V1','snapshot':c['releases']['TEMPORAL_HOLDOUT']['source_snapshot_id'],'kind':'TEMPORAL_HOLDOUT','model':'P2-L1'})
 ck('V1_25_valid_evaluations',st==200 and sum(r['evaluation_status']!='NOT_EVALUATED' for r in v1['records'])==25)
 ck('V1_negative_scores_not_hidden',all(next(r for r in v1['records'] if int(r['gauge_id'])==g)['NSE']<0 for g in [378,383,455]))
 reg=readj(LAB/'vhs_web_r1_public_results_bridge/PUBLIC_MODEL_REGISTRY.json')
 for r in reg['models']:
  p=pathlib.Path(r['artifact_path']);ck('frozen_model_json_'+str(r['gauge_id'])+r['model_id'],sha(p/'model.json')==r['model_json_hash'])
  with np.load(p/'arrays.npz',allow_pickle=False) as a:ck('load_finite_arrays_'+str(r['gauge_id'])+r['model_id'],all(np.isfinite(a[k]).all() for k in a.files))
 result={'passed':sum(c['passed'] for c in checks),'failed':sum(not c['passed'] for c in checks),'checks':checks,'fit_calls':0,'scoring_calls':0,'host':'ORIGINAL_V06_CANDIDATE_8794','production_display_permission':'NOT_GRANTED','teacher_Q_mounted':False,'new_results_are_frozen_display_not_new_experiments':True,'browser_checks':'separate evidence/BROWSER_ACCEPTANCE.json'}
 put(WEB/'WEB_S1_ACCEPTANCE.json',result);print(json.dumps({k:v for k,v in result.items() if k!='checks'}),flush=True)
 assert result['failed']==0,[c for c in checks if not c['passed']]
if __name__=='__main__':main()
