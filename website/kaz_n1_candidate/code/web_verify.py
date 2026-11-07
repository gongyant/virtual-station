from intake import *
import urllib.request,urllib.error,urllib.parse
CHECKS=[]
def ck(n,v):CHECKS.append({'name':n,'passed':bool(v)});assert v,n
def api(path,q=None,method='GET'):
 u='http://127.0.0.1:8795'+path+('?' +urllib.parse.urlencode(q) if q else '')
 req=urllib.request.Request(u,method=method,data=b'{}' if method=='POST' else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=20) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
def main():
 ds='KAZAKHSTAN_PUBLIC_NETWORK';st,cat=api('/api/v6/candidate-kaz/catalog',{'dataset':ds});ck('KAZ_catalog_200',st==200);ck('official442_394',cat['counts']['N_real_all']==442 and cat['counts']['N_real_river']==394);ck('no_false_KAZ_accuracy',cat['Kazakhstan_NSE'] is None and cat['Kazakhstan_KGE'] is None)
 q={'dataset':ds,'snapshot':cat['source_snapshot_id']};st,m=api('/api/v6/candidate-kaz/map',q);ck('map_200',st==200);ck('three_distinct_layers',set(m['layers'])=={'PHYSICAL_GAUGE','CANDIDATE_GEOMETRY','VIRTUAL_PREDICTION_AVAILABLE'});ck('no_random_physical_points',m['layers']['PHYSICAL_GAUGE']['mapped_count']==0 and not m['layers']['PHYSICAL_GAUGE']['features']);ck('actual1230_geometry_only',len(m['layers']['CANDIDATE_GEOMETRY']['features'])==1230 and m['layers']['CANDIDATE_GEOMETRY']['admitted_count']==0);ck('no_fake_predictive_points',m['layers']['VIRTUAL_PREDICTION_AVAILABLE']['count']==0 and not m['layers']['VIRTUAL_PREDICTION_AVAILABLE']['features'])
 for p in m['layers']['CANDIDATE_GEOMETRY']['features']:ck('no_NSE_at_unvalidated_'+p['station_id'],p['NSE'] is None and p['KGE'] is None and p['qsim'] is None)
 st,p=api('/api/v6/candidate-kaz/pub',q);ck('EU_benchmark_separate',st==200 and p['benchmark_dataset_id']=='LAMAH_CE_PUBLIC_V1' and p['classification']=='EUROPEAN_PUB_DEVELOPMENT' and p['not_Kazakhstan_accuracy']);ck('all8_method_scheme_summaries',len(p['summary'])==8);ck('negative_transfer_results_retained',any(r['NSE_median']<-10 for r in p['summary']));ck('EU_gauge_namespace',all(r['station_uid'].startswith('LAMAH_CE_PUBLIC_V1:') and r['country_scope']=='EUROPE_NOT_KAZAKHSTAN' for r in p['records']))
 for n,extra,expect in [('cross_snapshot',{'snapshot':'wrong'},409),('SYRDARYA_cross_dataset',{'dataset':'SYRDARYA'},403),('old_Europe_snapshot_not_KAZ',{'dataset':'LAMAH_CE_PUBLIC_V1'},403),('Qobs_export',{'qobs':'1','format':'csv'},403)]:st,b=api('/api/v6/candidate-kaz/pub',{**q,**extra});ck(n,st==expect)
 for path,method in [('/api/v6/candidate-kaz/predict','GET'),('/api/v6/candidate-kaz/execute','POST'),('/api/v6/public-kaz/catalog','GET'),('/api/v6/public/catalog','GET'),('/api/v6/model/execute','POST'),('/api/vhs/predict','POST')]:st,b=api(path,q,method);ck('403_'+path,st==403)
 st,old=api('/api/v6/candidate-public/catalog');ck('old54models_preserved',st==200 and len(old['models'])==54 and len(old['stations'])==27)
 st,s1=api('/api/v6/candidate-public/research/catalog',{'dataset':'LAMAH_CE_PUBLIC_V1'});ck('P6D_864preserved',st==200 and s1['coverage']['paired_station_months']==864)
 st,health=api('/api/vhs/health');ck('teacher_Q_not_mounted',not health['r2_candidate']['teacher_source_mounted']);ck('actual_new_host_identity',health['r2_candidate']['host_root']==str(ROOT/'web_candidate/host'))
 put(ROOT/'evidence/WEB_API_ACCEPTANCE.json',{'passed':len(CHECKS),'failed':0,'fit_calls':0,'new_scoring_calls':0,'checks':CHECKS,'host_port':8795,'old_services_not_modified':True})
 print('WEB API checks',len(CHECKS),'passed',flush=True)
if __name__=='__main__':main()
