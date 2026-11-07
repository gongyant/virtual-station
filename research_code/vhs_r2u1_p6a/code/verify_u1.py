"""Targeted R2U1 scientific/interface acceptance, not a general platform audit."""
import base64,csv,hashlib,json,socket,sys,time,urllib.request,urllib.error,urllib.parse,shutil
from pathlib import Path
import numpy as np
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');R2=R.parent/'vhs_web_r2_host_integration';URL='http://127.0.0.1:8793';DS='LAMAH_CE_PUBLIC_V1';tests=[]
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jw(n,v):(R/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def test(name,ok,**kw):tests.append({'name':name,'passed':bool(ok),**kw});print(('PASS ' if ok else 'FAIL ')+name,flush=True)
def api(path,qs=None,post=None):
 req=urllib.request.Request(URL+path+('?'+urllib.parse.urlencode(qs) if qs else ''),data=json.dumps(post).encode() if post is not None else None,headers={'Content-Type':'application/json'})
 try:
  with urllib.request.urlopen(req,timeout=20) as f:return f.status,json.load(f)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
code,h=api('/api/vhs/health');test('new_original_host_candidate_8793',code==200 and h['r2_candidate']['host_root']==str(R/'host'));test('teacher_Q_unmounted',not h['r2_candidate']['teacher_source_mounted'])
_,cat=api('/api/v6/candidate-public/catalog');test('global_frozen_result_counts_unchanged',cat['counts']=={'released_stations':27,'released_models':54,'V1_stations':25,'V1_unique_months':899,'V1_predictions':1798,'V2_application_predictions':648,'masked_predictions':24,'true_gap_predictions':0})
q={'dataset':DS,'kind':'TEMPORAL_HOLDOUT','snapshot':cat['releases']['TEMPORAL_HOLDOUT']['source_snapshot_id'],'station':DS+':2','model':'P2-L1'}
for kind,g,start,end,n in [('TEMPORAL_HOLDOUT',2,'2015-01','2015-03',3),('FINAL_MODEL_APPLICATION',611,'2016-01','2016-12',12),('MASKED_GAP_EVALUATION',9,'2016-01','2016-12',0)]:
 scope={**q,'kind':kind,'snapshot':cat['releases'][kind]['source_snapshot_id'],'station':DS+':'+str(g),'start':start,'end':end};code,d=api('/api/v6/candidate-public/selection-source',scope);test('selection_source_'+kind,code==200 and d['selected_records']==n and d['prediction_kind']==kind and d['global_counts']==cat['counts'])
for change,status in [({'snapshot':'metadata-alias'},409),({'dataset':'SYRDARYA'},403),({'station':'SYRDARYA:16039'},400),({'start':'2016-15','end':'2016-12'},400)]:
 code,d=api('/api/v6/candidate-public/selection-source',{**q,'start':'2015-01','end':'2017-12',**change});test('u1_scope_reject_'+str(change),code==status)
test('production_display_still_403',api('/api/v6/public/catalog')[0]==403);test('dynamic_run_still_403',api('/api/v6/model/execute',post={'dataset':DS})[0]==403);test('Qobs_export_still_403',api('/api/v6/candidate-public/export',q)[0]==403)
_,d=api('/api/v6/candidate-public/diagnostics',q);test('no_cross_station_diagnostic_rows',len(d['records'])==72 and all(r['gauge_id']==2 and r['prediction_kind']=='TEMPORAL_HOLDOUT' for r in d['records']))
summary=jl(R/'diagnostics/DIAGNOSTIC_SUMMARY.json');test('2446_frozen_predictions_exact_reproduction',summary['frozen_prediction_reproductions']==2446 and summary['max_reproduction_abs_error']==0);test('108_alpha_oneSE_mechanism_recomputed',summary['alpha_model_count']==108 and summary['alpha_selected_counts']=={'100.0':108} and summary['all_oneSE_selections_recomputed_correctly']);test('standardization_zero_leakage_mechanism',summary['max_mu_error']==0 and summary['max_sd_error']==0 and summary['max_standardized_training_month_mean']<1e-10)
test('old_V1_scores_unchanged',summary['old_metric_max_NSE_reproduction_error']<1e-12)
for g,status in [(818,'P6_DESCRIPTIVE_COMPLETED_2018_2019'),(611,'BLOCKED_OFFICIAL_DAILY_Q_DAYCOUNT_NOT_VERIFIED'),(2,'NOT_RUN_NOT_IN_P6A_COHORT')]:
 _,d=api('/api/v6/candidate-public/research-status',{**q,'station':DS+':'+str(g)});test('P6_status_distinct_'+str(g),d['P6']['status']==status and d['business_certification']=='NOT_CERTIFIED')
sys.path.insert(0,str(R/'code'));import p6_pipeline as pipe
test('new_metric_manual_control',pipe.metrics([1,2,3],[1,2,3])['NSE']==1 and pipe.metrics([1,2,3],[1,2,3])['KGE']==1)
test('undefined_metric_not_zero',pipe.metrics([0,0],[1,1])['NSE'] is None and pipe.metrics([0,0],[1,1])['KGE'] is None)
pred=R/'p6/runs/P6A_V2_2018_2019';score=R/'p6/runs/P6A_V2_2018_2019_SCORING';pipe.verify(pred);pipe.verify(score)
commit=jl(pred/'COMMITMENT.json');seal=jl(R/'p6/P6_PREDICTION_SEAL.json');test('P6_prediction_commit_verified_before_scoring',commit['records']==48 and commit['fit_calls']==0 and not commit['test_Q_read_by_prediction'] and sha(pred/'SHA256SUMS.txt')==seal['SHA256SUMS']);test('P6_old_models_not_tuned',commit['prediction_code_hash']==sha(R/'code/p6_pipeline.py'))
# Independent arithmetic check of P6 aggregates from frozen prediction rows and exact Q daily source.
rows=pipe.cr(pred/'P6_PREDICTIONS_WITHOUT_QOBS.csv');obs=pipe.cr(R/'external/CAMELS_CAMELS_CH_obs_based_2304.csv');groups={}
for r in obs:
 if '2018-01'<=r['date'][:7]<='2019-12':groups.setdefault(r['date'][:7],[]).append(float(r['discharge_vol(m3/s)']))
met=pipe.cr(score/'P6_METRICS.csv')
for mid in ['C0+PT','P2-L1']:
 rr=sorted([r for r in rows if r['model_id']==mid],key=lambda r:r['date']);y=np.array([np.mean(groups[r['date']]) for r in rr]);p=np.array([float(r['q_hat_raw']) for r in rr]);metric=next(r for r in met if r['model_id']==mid and r['subset']=='ALL' and r['prediction']=='raw');nse=1-sum((p-y)**2)/sum((y-y.mean())**2);test('P6_independent_score_recompute_'+mid,abs(nse-float(metric['NSE']))<1e-12)
 # Independent direct calculation of all reported metrics and interval scores.
 rcoef=float(np.corrcoef(y,p)[0,1]);ratio=float(np.std(p)/np.std(y));bias_ratio=float(np.mean(p)/np.mean(y));kge=1-float(np.linalg.norm([rcoef-1,ratio-1,bias_ratio-1]));pbias=100*float(np.mean(p)-np.mean(y))/float(np.mean(y))
 test('P6_KGE_and_PBIAS_independent_'+mid,abs(kge-float(metric['KGE']))<1e-12 and abs(pbias-float(metric['PBIAS']))<1e-12)
 covrows=pipe.cr(score/'P6_INTERVAL_DIAGNOSTICS.csv')
 for nominal in [80,90]:
  lo=np.array([float(r[f'lower{nominal}']) for r in rr]);hi=np.array([float(r[f'upper{nominal}']) for r in rr]);a=1-nominal/100;IS=np.mean([u-l+((2/a)*(l-v) if v<l else (2/a)*(v-u) if v>u else 0) for v,l,u in zip(y,lo,hi)]);ref=next(z for z in covrows if z['model_id']==mid and z['subset']=='ALL' and float(z['nominal'])==nominal/100)
  test('P6_interval_score_independent_'+mid+'_'+str(nominal),abs(IS-float(ref['mean_interval_score']))<1e-12)
proof=[]
sys.path.insert(0,str(R/'host/tools'));from cdp import Browser
s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close();b=Browser(r'C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe',str(R/'runtime/browser-profile'),port)
def goto(route,marker,extra=''):
 b.goto(URL+'/?u1='+str(time.time_ns())+'#/'+route+'?dataset='+DS+extra);ok=b.wait("!!document.querySelector('#r2Station') && !document.querySelector('#view .loading') && document.body.innerText.includes("+json.dumps(marker)+")",timeout=25)
 if not ok:print('PAGE_ERROR',b.eval("document.querySelector('#view').innerText"))
 return ok
def shot(name):
 b.viewport(1440,1000);height=b.call('Page.getLayoutMetrics')['cssContentSize']['height'];raw=b.call('Page.captureScreenshot',format='png',captureBeyondViewport=True,clip={'x':0,'y':0,'width':1440,'height':min(height,5000),'scale':1});p=R/'screenshots'/name;p.write_bytes(base64.b64decode(raw['data']));proof.append({'file':name,'sha256':sha(p),'url':b.eval('location.href')})
try:
 test('UI_spatial_real_page',goto('layers','科研状态分离','&station='+DS+':378'));shot('02_AFTER_spatial_unique_states.png')
 test('risk_fields_render_exactly_once',b.eval("(()=>{let s=document.querySelector('#side').innerText;return s.split('V1评价状态').length===2&&s.split('V1误差风险').length===2;})()"))
 test('risk_does_not_imply_certification',b.eval("document.querySelector('#side').innerText.includes('NEGATIVE_NSE')&&document.querySelector('#side').innerText.includes('NOT_CERTIFIED')&&document.querySelector('#side').innerText.includes('2018年后新时期验证')"))
 test('UI_data_source_real_page',goto('data','当前选择的关联来源','&station='+DS+':2&start=2015-01&end=2015-03'));shot('03_AFTER_source_V1_selection.png')
 test('current_source_highlight_V1',b.eval("document.querySelector('[data-current-source]').dataset.currentSource==='TEMPORAL_HOLDOUT' && document.querySelector('#view').innerText.includes('1798预测 / 899站月')"))
 b.eval("var k=document.querySelector('#r2Kind');k.value='FINAL_MODEL_APPLICATION';k.dispatchEvent(new Event('change'))")
 test('switch_V2_updates_identity_and_current_counts',b.wait("!!document.querySelector('[data-current-source]') && document.querySelector('[data-current-source]').dataset.currentSource==='FINAL_MODEL_APPLICATION' && document.querySelector('#view').innerText.includes('648应用预测') && document.querySelector('#r2Start').value==='2016-01'"));shot('04_AFTER_source_V2_selection.png')
 b.eval("var st=document.querySelector('#r2Station');st.value='LAMAH_CE_PUBLIC_V1:611';st.dispatchEvent(new Event('change'))")
 test('source_summary_updates_when_station_changes',b.wait("!!document.querySelector('[data-current-source]') && document.querySelector('#view').innerText.includes('LAMAH_CE_PUBLIC_V1:611 / P2-L1')"))
 test('UI_decomposition_real_page',goto('results','季节模板与气象修正','&station='+DS+':533'));shot('05_AFTER_prediction_decomposition.png')
 test('decomposition_has_baseline_PT_L1_and_actual_difference',b.eval("document.querySelector('#view').innerText.includes('直接L1贡献')&&document.querySelector('#view').innerText.includes('实际L1−C0PT')&&document.querySelector('#view').innerText.includes('108个均为100')"))
 test('P6_status_visible_only_for_evaluated_station',goto('layers','科研状态分离','&station='+DS+':818') and b.eval("document.querySelector('#side').innerText.includes('P6_DESCRIPTIVE_COMPLETED_2018_2019')&&document.querySelector('#side').innerText.includes('NOT_CERTIFIED')"));shot('06_AFTER_P6_descriptive_status.png')
 test('unscored611_stays_unscored',goto('results','NO_ELIGIBLE_TEST_SUPPORT','&station='+DS+':611'))
 b.eval("VHS.setDataset('LAMAHCE');true");test('dataset_switch_clears_public_state',b.wait("VHS.state.dataset==='LAMAHCE'&&!document.querySelector('#r2Station')&&!document.querySelector('#view .loading')"))
 test('no_uncaught_browser_errors',not b.errors(),errors=b.errors())
finally:b.close()
shutil.copyfile(R2/'screenshots/05_original_host_spatial_layer.png',R/'screenshots/01_BEFORE_frozen_R2_spatial.png');jw('evidence/BROWSER_EVIDENCE.json',{'after':proof,'before':{'source':str(R2/'screenshots/05_original_host_spatial_layer.png'),'sha256':sha(R/'screenshots/01_BEFORE_frozen_R2_spatial.png'),'kind':'copied immutable R2 actual browser screenshot'}})
before=jl(R/'evidence/HISTORY_BEFORE.json');changes=[];n=0
for root,v in before.items():
 for rel,hsh in v['files'].items():
  n+=1;p=Path(root)/rel
  if not p.exists() or sha(p)!=hsh:changes.append(str(p))
 if sha(Path(root)/v['manifest'])!=v['manifest_sha256']:changes.append(str(Path(root)/v['manifest']))
test('all_P0_P5_R1_R2_frozen_hashes_unchanged',not changes,files=n,changes=changes);jw('evidence/HISTORY_AFTER.json',{'checked_files':n,'changed':changes,'root_manifests':8})
result={'total':len(tests),'passed':sum(t['passed'] for t in tests),'failed':sum(not t['passed'] for t in tests),'tests':tests,'software_test_pass_is_not_scientific_validation':True,'P6_qualified_scored_stations':1,'fit_calls':0};jw('R2U1_P6A_TEST_RESULTS.json',result);print('RESULT',result['passed'],result['total']);raise SystemExit(bool(result['failed']))
