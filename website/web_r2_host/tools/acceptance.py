"""R2 host integration acceptance. Reads frozen results only; no fit or scoring."""
import base64, collections, hashlib, json, os, socket, subprocess, sys, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode

ROOT=Path(r'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration')
R1=ROOT.parent/'vhs_web_r1_public_results_bridge'
DS='LAMAH_CE_PUBLIC_V1'
HOST='http://127.0.0.1:8792'
def jl(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jw(p,x): Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
checks=[]
def check(name,passed,**detail):
    checks.append(dict(name=name,passed=bool(passed),**detail))
    print(('PASS ' if passed else 'FAIL ')+name,flush=True)
def req(path,q=None,body=None):
    url=HOST+path+('?' + urlencode(q) if q else '')
    r=Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
    try:
        with urlopen(r,timeout=40) as f:return f.status,json.load(f)
    except HTTPError as e:return e.code,json.load(e)
def run():
    code,health=req('/api/vhs/health')
    jw(ROOT/'evidence/R2_LIVE_HEALTH.json',health)
    check('original_v06_host_8792_running',code==200 and health['r2_candidate']['host_root']==str(ROOT/'host'))
    check('teacher_Q_not_mounted',health['r2_candidate']['teacher_source_mounted'] is False)
    check('old_LAMAHCE_metadata_still_882_gauges',health['loaded']['stations']==882)
    code,cat=req('/api/v6/candidate-public/catalog')
    check('public_catalog_in_original_host',code==200 and len(cat['models'])==54 and len(cat['stations'])==27)
    check('no_fabricated_production_grant',cat['production_display_permission']=='NOT_GRANTED')
    for path in ['/api/v6/public/catalog','/api/v6/public/results/station']:
        code,d=req(path,{'dataset':DS,'GRANTED':'true','verified':'true'})
        check('production_permission_403_'+path,code==403 and d['status']=='PUBLIC_RESULT_DISPLAY_NOT_AUTHORIZED')
    for path in ['/api/v6/model/execute','/api/v6/candidate-public/execute','/api/v6/public/execute']:
        code,d=req(path,body={'dataset':DS,'authorized':True})
        check('dynamic_execution_403_'+path,code==403)
    for path in ['/api/v6/model/execute','/api/vhs/predict']:
        code,d=req(path,body={'dataset':'SYRDARYA','authorized':True})
        check('teacher_permission_403_'+path,code==403)
    for path in ['/api/v6/overview','/api/v6/layers','/api/v6/data/catalog','/api/v6/model/registry','/api/v6/results/station']:
        code,d=req(path,{'dataset':'LAMAHCE'})
        check('original_metadata_route_'+path,code==200,actual_status=code)
    for kind,release in cat['releases'].items():
        q=dict(dataset=DS,kind=kind,snapshot=release['source_snapshot_id'],model='P2-L1',station=DS+':2')
        for change,expected in [({'snapshot':'old-metadata-snapshot'},409),({'dataset':'SYRDARYA'},403),({'dataset':'LAMAHCE'},409),({'station':'SYRDARYA:16039'},400),({'model':'P5-SHRINK'},400)]:
            code,d=req('/api/v6/candidate-public/results/station',{**q,**change})
            check('scope_rejection_'+kind+'_'+next(iter(change))+'_'+str(next(iter(change.values()))),code==expected,actual_status=code)
        code,d=req('/api/v6/candidate-public/results/station',q)
        check('frozen_predictions_'+kind,code==200 and all(r['prediction_kind']==kind for r in d['records']) and d['qobs'] is None)
        check('no_reach_prediction_'+kind,d['reach_id'] is None and d['geometry'] is None and d['reach_status']=='REACH_PREDICTION_NOT_AVAILABLE')
    q=dict(dataset=DS,kind='TEMPORAL_HOLDOUT',snapshot=cat['releases']['TEMPORAL_HOLDOUT']['source_snapshot_id'],model='P2-L1')
    code,ev=req('/api/v6/candidate-public/results/evaluation',q)
    scored=[r for r in ev['records'] if r['NSE'] is not None]
    check('25_V1_evaluated_and_899_station_months',len(scored)==25 and sum(r['n_months'] for r in scored)==899)
    for g in [611,688]:
        r=next(r for r in ev['records'] if r['gauge_id']==g)
        check('unscored_NA_'+str(g),r['NSE'] is None and r['KGE'] is None and r['evaluation_status']=='NOT_EVALUATED')
    for g in [378,383,455]:
        r=next(r for r in scored if r['gauge_id']==g)
        check('negative_NSE_retained_'+str(g),r['NSE']<0,NSE=r['NSE'])
    app={**q,'kind':'FINAL_MODEL_APPLICATION','snapshot':cat['releases']['FINAL_MODEL_APPLICATION']['source_snapshot_id']}
    code,d=req('/api/v6/candidate-public/results/evaluation',app)
    check('V2_application_not_V1_evaluation',code==409 and d['status']=='APPLICATION_NOT_INDEPENDENT_EVALUATION')
    code,d=req('/api/v6/candidate-public/export',q)
    check('Qobs_export_refused',code==403)
    code,geo=req('/api/v6/candidate-public/results/spatial',{**q,'date':'2016-01'})
    from pyproj import Transformer
    t=Transformer.from_crs(4326,3035,always_xy=True)
    errors=[]
    for f in geo['features']:
        xy=t.transform(*f['geometry']['coordinates']);official=f['properties']['coordinates_epsg3035']
        errors.append(max(abs(xy[i]-official[i]) for i in [0,1]))
    check('27_official_projected_points_roundtrip',len(errors)==27 and max(errors)<.02,max_error_metres=max(errors))
    check('spatial_25_scores_and_zero_reaches',geo['layers']['evaluation']['count']==25 and geo['layers']['reach']['count']==0)
    sys.path.insert(0,str(R1/'code'))
    from bridge import PublicResultsBridge
    bridge=PublicResultsBridge(); bridge.validate_sources()
    bundle=bridge.bundle; registry=bridge.registry
    counts=collections.Counter(r['prediction_kind'] for r in bundle['predictions'])
    check('all_2470_frozen_records_exact_counts',dict(counts)=={'TEMPORAL_HOLDOUT':1798,'FINAL_MODEL_APPLICATION':648,'MASKED_GAP_EVALUATION':24},counts=dict(counts))
    identities=[(r['dataset_id'],r['source_snapshot_id'],r['model_release_id'],r['station_uid'],r['model_id'],r['prediction_kind'],r['year'],r['month']) for r in bundle['predictions']]
    check('no_duplicate_or_cross_snapshot_sample_keys',len(identities)==len(set(identities)) and all(k[0]==DS for k in identities))
    check('no_true_gap_rows',not any(r['prediction_kind']=='TRUE_GAP_RECONSTRUCTION' for r in bundle['predictions']))
    check('registry_exact_R1_copy',sha(ROOT/'R2_PUBLIC_RESULT_REGISTRY.json')==sha(R1/'PUBLIC_MODEL_REGISTRY.json'))
    check('no_Qobs_fields_in_prediction_payloads',all(not any(k.lower() in ('qobs','q_obs','y_obs') for k in r) for r in bundle['predictions']))
    sys.path.insert(0,str(ROOT/'host'))
    from r2_public import R2HostGateway
    gate=R2HostGateway(candidate_local=False)
    check('candidate_namespace_disabled_without_explicit_switch',gate.handle('/api/v6/candidate-public/catalog',{})[0]==403)
    gate.candidate_local=True;gate.bridge.pin='invalid-test-pin-in-memory-only'
    check('source_mismatch_refused_even_for_catalog',gate.handle('/api/v6/candidate-public/catalog',{})[0]==409)
    gate=R2HostGateway(candidate_local=True)
    check('duplicate_query_rejected',gate.handle('/api/v6/candidate-public/catalog',{'dataset':[DS,'SYRDARYA']})[0]==400)
    expected={r['gauge_id']:r for r in bundle['evaluation'] if r['model_id']=='P2-L1'}
    check('all_25_metrics_identical_to_frozen_import',all(all(r[k]==expected[r['gauge_id']][k] for k in ['NSE','KGE','RMSE','MAE','PBIAS']) for r in scored))
    cp=subprocess.run([sys.executable,'-B',str(ROOT.parent/'p5_robustness_and_external_validation/code/p5_cli.py'),'verify-release'],capture_output=True,text=True,timeout=120)
    receipt={'returncode':cp.returncode,'stdout':cp.stdout,'stderr':cp.stderr,'command':'p5_cli.py verify-release (load/hash only; no predict, fit or scoring)'}
    jw(ROOT/'evidence/R2_54_MODEL_LOAD_RECEIPT.json',receipt)
    check('54_saved_models_load_without_fit',cp.returncode==0 and json.loads(cp.stdout)['models_verified']==54 and json.loads(cp.stdout)['fit_calls']==0)
    synthetic=jl(ROOT/'host/logs/test_summary_partial.json')
    check('146_original_synthetic_regressions',synthetic['totals']['pass']==146 and synthetic['totals']['fail']==0)
    jw(ROOT/'evidence/R2_INHERITED_SYNTHETIC_REGRESSION.json',synthetic)
    browser_tests(cat)
    consistency={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'counts':dict(counts),'V1_stations':25,'V1_station_months':899,'V2_saved_models':54,'V2_stations':27,'true_gaps':0,'fit_calls':0,'new_predictions':0,'rescoring_calls':0,'metrics_source':'Frozen WEB-R1 bundle; exact imported V1 scores','teacher_Q_read':False,'production_display_permission':'NOT_GRANTED','R1_bundle_sha256':sha(R1/'data/bundle.json'),'R1_registry_sha256':sha(R1/'PUBLIC_MODEL_REGISTRY.json')}
    jw(ROOT/'R2_SCIENTIFIC_RESULT_CONSISTENCY.json',consistency)
    before=jl(ROOT/'evidence/HISTORY_BEFORE.json');after={};bad=[];n=0
    for root,info in before.items():
        changes=[]
        for rel,h in info['files'].items():
            p=Path(root)/rel;n+=1
            if not p.is_file() or sha(p)!=h:changes.append(rel);bad.append(str(p))
        after[root]={'listed_files':len(info['files']),'changed':changes}
    jw(ROOT/'evidence/HISTORY_AFTER.json',after)
    check('all_frozen_history_files_unchanged',not bad,files=n,changes=bad)
    result={'timestamp':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'total':len(checks),'passed':sum(r['passed'] for r in checks),'failed':sum(not r['passed'] for r in checks),'checks':checks,'scope':'R2 original v0.6 local candidate, not production approval','host':HOST,'inherited_synthetic_assertions':146}
    jw(ROOT/'R2_INTEGRATION_TEST_RESULTS.json',result)
    print(json.dumps({k:result[k] for k in ['total','passed','failed']},ensure_ascii=False))
    return result['failed']

def browser_tests(cat):
    sys.path.insert(0,str(ROOT/'host/tools'))
    from cdp import Browser
    s=socket.socket();s.bind(('127.0.0.1',0));port=s.getsockname()[1];s.close()
    b=Browser(r'C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe',str(ROOT/'runtime/browser-profile'),port)
    proof=[];seq=0
    def goto(route,marker,extra=''):
        nonlocal seq
        seq+=1
        b.goto(HOST+f'/?r2check={seq}#/'+route+'?dataset='+DS+extra)
        okay=b.wait("!!document.querySelector('#r2Station') && document.querySelector('#view').innerText.includes("+json.dumps(marker)+")",timeout=25)
        if not okay: print('PAGE_FAILURE',route,b.eval("document.querySelector('#view').innerText"),flush=True)
        check('browser_page_'+route+'_'+str(seq),okay)
        return okay
    def shot(name):
        b.viewport(1440,1000)
        size=b.call('Page.getLayoutMetrics')['cssContentSize']
        d=b.call('Page.captureScreenshot',format='png',captureBeyondViewport=True,clip={'x':0,'y':0,'width':1440,'height':min(size['height'],4200),'scale':1})
        p=ROOT/'screenshots'/name;p.write_bytes(base64.b64decode(d['data']))
        proof.append({'file':str(p.relative_to(ROOT)),'sha256':sha(p),'url':b.eval('location.href'),'title':b.eval('document.title')})
    try:
        goto('model','54模型');shot('01_original_host_model_layer.png')
        check('original_header_nav_and_single_selector',b.eval("document.querySelectorAll('#nav a').length===5 && document.querySelectorAll('#dsSwitch button').length===3 && document.querySelectorAll('#r2Station').length===1 && document.querySelectorAll('iframe').length===0"))
        check('model_table_54',b.eval("document.querySelectorAll('#view tbody tr').length===54"))
        b.eval("document.querySelector('#r2Execute').click()")
        check('browser_execute_still_403',b.wait("document.querySelector('#r2ExecResult').textContent.includes('403')"))
        goto('results','原V1逐年指标');shot('02_original_host_station_results.png')
        raw=b.eval("document.querySelector('#view polyline').getAttribute('points')")
        b.eval("var e=document.querySelector('#r2Model');e.value='C0+PT';e.dispatchEvent(new Event('change'))")
        check('model_switch_updates_curve_and_metrics',b.wait("!!document.querySelector('#view polyline') && VHS.state.publicModel==='C0+PT' && document.querySelector('#view polyline').getAttribute('points')!=="+json.dumps(raw)))
        check('shared_state_persists_navigation',b.eval("VHS.go('layers');true") and b.wait("!!document.querySelector('.r2-mapdot') && document.querySelector('#r2Model').value==='C0+PT'"))
        goto('results/evaluation','V1独立时间外评价');shot('03_original_host_model_evaluation.png')
        check('browser_all_27_score_rows_with_negative_NSE',b.eval("document.querySelectorAll('#view tbody tr').length===27 && document.querySelectorAll('#view .negative').length>=3 && document.querySelector('#view').innerText.includes('NOT_EVALUATED')"))
        goto('results','NO_ELIGIBLE_TEST_SUPPORT','&station='+DS+':611')
        check('611_no_fake_zero_metrics',b.eval("document.querySelector('#view').innerText.includes('NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT')"))
        goto('results','FINAL_MODEL_APPLICATION','&kind=FINAL_MODEL_APPLICATION&start=2016-01&end=2016-12')
        check('V2_curve_12_not_new_OOF',b.eval("document.querySelectorAll('#view svg circle').length===12 && document.querySelector('#view').innerText.includes('不是新的独立测试')"))
        shot('04_original_host_V2_application.png')
        goto('results','MASKED_GAP_EVALUATION','&kind=MASKED_GAP_EVALUATION&start=2016-01&end=2016-12')
        check('masked_curve_not_true_gap',b.eval("document.querySelectorAll('#view svg circle').length===12 && document.querySelector('#view').innerText.includes('不是真正历史缺档')"))
        goto('layers','EPSG:3035');shot('05_original_host_spatial_layer.png')
        check('27_station_points_no_reach_flow',b.eval("document.querySelectorAll('.r2-mapdot').length===27 && document.querySelector('#view').innerText.includes('REACH_PREDICTION_NOT_AVAILABLE')"))
        check('equal_projected_map_scale_in_both_axes',b.eval("(()=>{let a=document.querySelectorAll('.r2-mapdot'),p=a[0],q=a[10],sx=(q.cx.baseVal.value-p.cx.baseVal.value)/(Number(q.dataset.epsgX)-Number(p.dataset.epsgX)),sy=(q.cy.baseVal.value-p.cy.baseVal.value)/(Number(q.dataset.epsgY)-Number(p.dataset.epsgY));return Math.abs(sx+sy)<1e-10;})()"))
        b.eval("document.querySelector('[data-r2-mapstation=\"LAMAH_CE_PUBLIC_V1:378\"]').dispatchEvent(new MouseEvent('click'))")
        check('map_click_uses_shared_station_state',b.wait("VHS.state.station==='LAMAH_CE_PUBLIC_V1:378' && !!document.querySelector('.r2-mapdot.selected') && document.querySelector('#r2Station').value==='LAMAH_CE_PUBLIC_V1:378'"))
        goto('results/report','P4/P5科研报告');shot('06_original_host_research_report.png')
        b.eval("document.querySelector('[data-r2-report=license]').click()")
        check('license_attribution_visible',b.wait("!!document.querySelector('.r2-report') && document.querySelector('.r2-report').textContent.includes('CC BY-SA')"))
        shot('07_original_host_license.png')
        # A delayed response issued under public dataset must never cache or repaint old metadata.
        b.eval("VHS.clearCache(); window.r2OriginalFetch=window.fetch; window.fetch=function(u,o){var p=r2OriginalFetch(u,o);return String(u).includes('candidate-public')?p.then(r=>new Promise(resolve=>setTimeout(()=>resolve(r),700))):p;}; VHS.go('overview');true")
        b.eval("VHS.setDataset('LAMAHCE');true")
        okay=b.wait("VHS.state.dataset==='LAMAHCE' && !document.querySelector('#view .loading') && !document.querySelector('#r2Station')",timeout=25)
        time.sleep(1)
        check('dataset_switch_discards_delayed_public_response',okay and b.eval("VHS.state.dataset==='LAMAHCE' && !document.querySelector('#r2Station') && !Array.from(VHS.cache.keys()).some(k=>k.includes('candidate-public')) && !document.querySelector('#view .err')"))
        shot('08_original_host_legacy_metadata.png')
        b.eval("window.fetch=window.r2OriginalFetch;VHS.setDataset('SYRDARYA');true")
        check('original_teacher_module_explicitly_unmounted',b.wait("document.querySelector('#view').innerText.includes('TEACHER_SOURCE_NOT_MOUNTED_IN_CANDIDATE')"))
        goto('overview','公开流域历史校准');shot('09_original_host_overview.png')
        b.viewport(760,1000)
        check('narrow_layout_has_no_document_overflow',b.eval("document.documentElement.scrollWidth<=780"))
        check('no_uncaught_browser_exceptions',not b.errors(),errors=b.errors())
        jw(ROOT/'evidence/R2_BROWSER_EVIDENCE.json',{'screenshots':proof,'runtime_errors':b.errors(),'no_training_or_scoring':True})
    finally:b.close()

if __name__=='__main__':raise SystemExit(run())
