"""Actual API, saved-model and browser acceptance for isolated preview."""
import sys,subprocess,urllib.request,urllib.error,time,socket
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"code"))
from core import *
from bridge import PublicResultsBridge,V06PublicResultsHook
sys.path.insert(0,str(BASE/"tools"));import cdp
BASEURL="http://127.0.0.1:8791"
checks=[]
def check(name,ok,**extra):
 assert ok,name;checks.append({"name":name,"pass":True,**extra})
def request(path,method="GET",headers=None,body=None):
 try:
  with urllib.request.urlopen(urllib.request.Request(BASEURL+path,data=body,method=method,headers=headers or {}),timeout=20) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
b=PublicResultsBridge();ds=DS;releases=b.releases
import urllib.parse
def q(kind="TEMPORAL_HOLDOUT",**extra):
 return urllib.parse.urlencode({"dataset":DS,"kind":kind,"snapshot":releases[kind]["source_snapshot_id"],"model":"P2-L1",**extra})
st,health=request("/api/health");check("preview_is_separate_from_production",st==200 and health["production_deployed"] is False)
# Existing site code was not imported, so teacher adapter could not be initialized.
check("no_teacher_adapter_import","syrdarya_adapter" not in sys.modules)
refs={(m["prediction_kind"],m["gauge_id"],m["model_id"]):m for key in ["models","evaluation_models","masked_evaluation_models"] for m in b.registry[key]}
for r in b.bundle["predictions"]:
 m=refs[r["prediction_kind"],r["gauge_id"],r["model_id"]]
 assert r["dataset_id"]==DS and r["source_snapshot_id"]==m["source_snapshot_id"] and r["model_release_id"]==m["model_release_id"] and r["model_hash"]==m["model_hash"] and r["station_uid"]==f'{DS}:{r["gauge_id"]}'
check("all_prediction_snapshot_model_station_foreign_keys",True,records=2470)
check("unique_prediction_keys",len({r["prediction_key"] for r in b.bundle["predictions"]})==2470)
check("54_models_27_station_mapping",len(b.registry["models"])==54 and len({m["gauge_id"] for m in b.registry["models"]})==27)
check("V1_only25_scored_sites",len({r["gauge_id"] for r in b.bundle["evaluation"]})==25 and len(b.bundle["evaluation"])==50)
check("V1_899_unique_months_and1798_predictions",len({(r["gauge_id"],r["year"],r["month"]) for r in b.bundle["predictions"] if r["prediction_kind"]=="TEMPORAL_HOLDOUT"})==899)
check("V2_not_evaluation_eligible",all(not r["evaluation_eligible"] and r["evaluation_run_id"] is None for r in b.bundle["predictions"] if r["prediction_kind"]=="FINAL_MODEL_APPLICATION"))
check("SHRINK_not_released",all(r["model_id"]!="P5-L1-SHRINK" for r in b.registry["models"]))
st,data=request("/api/public/results?"+q(station=DS+":2"));check("real_station_series_served",st==200 and len(data["records"])==36 and data["records"][0]["qsim_raw"] is not None)
st,none=request("/api/public/evaluation?"+q(station=DS+":611"));check("unscored_station_NA_not_zero",st==200 and none["status"]=="NOT_EVALUATED" and none["reason"]=="NO_ELIGIBLE_TEST_SUPPORT" and all(v is None for v in none["metrics"].values()))
st,neg=request("/api/public/evaluation?"+q(station=DS+":378"));check("negative_NSE_preserved",st==200 and neg["records"][0]["NSE"]<0)
for path,code in [
 ("/api/public/results?"+q(station="SYRDARYA:2"),400),
 ("/api/public/results?"+q(station=DS+":2",dataset="SYRDARYA"),403),
 ("/api/public/results?"+q(station=DS+":2",snapshot="lamah-metadata-old"),409),
 ("/api/public/evaluation?"+q("FINAL_MODEL_APPLICATION",station=DS+":2"),409),
 ("/api/public/export?what=Qobs",403)]:
 st,_=request(path);check("reject_"+path.split("?")[0]+"_"+str(len(checks)),st==code)
st,_=request("/api/v6/model/execute",method="POST",body=b"{}");check("HTTP_execute_stays403",st==403)
st,_=request("/api/vhs/predict");check("legacy_predict_stays403",st==403)
st,_=request("/api/public/catalog",headers={"Origin":"https://invalid.example"});check("cross_origin_rejected",st==403)
st,_=request("/api/public/catalog",headers={"Host":"invalid.example"});check("host_rebinding_rejected",st==403)
st,space=request("/api/public/spatial?"+q());check("spatial_point_layers_only",st==200 and len(space["features"])==27 and space["layers"]["reach"]["status"]=="REACH_PREDICTION_NOT_AVAILABLE" and all(f["geometry"]["type"]=="Point" and f["properties"]["reach_id"] is None for f in space["features"]))
from pyproj import Transformer
tr=Transformer.from_crs(4326,3035,always_xy=True);err=[]
for f in space["features"]:
 x,y=tr.transform(*f["geometry"]["coordinates"]);a,bp=f["properties"]["coordinates_epsg3035"];err.append(max(abs(x-a),abs(y-bp)))
check("EPSG3035_roundtrip",max(err)<.02,max_error_metres=max(err))
check("no_observed_Q_in_prediction_import",all(not any(k.lower() in ["qobs","qobs_m3s"] for k in r) for r in b.bundle["predictions"]))
check("production_hook_default_refuses_display",V06PublicResultsHook(b).handle("/api/v6/public/catalog",{})[0]==403)
check("legacy_routes_not_hijacked",V06PublicResultsHook(b).handle("/api/v6/results/station",{}) is None)
# Actual isolated P5 CLI: model verification opens all54; no inference fitter is imported.
py=sys.executable;cli=P5/"code/p5_cli.py"
p=subprocess.run([py,"-B",str(cli),"verify-release"],capture_output=True,text=True,check=True)
receipt=json.loads(p.stdout);check("all54_actual_models_load",receipt["models_verified"]==54 and receipt["fit_calls"]==0)
jw(BASE/"evidence/CLI_VERIFY_RELEASE.json",receipt)
met=P5/"runs/P5_A_SAVED_MODEL_APPLICATION/MET_2.json";out=BASE/"evidence/ISOLATED_CLI_PREDICTIONS.csv"
args=[py,"-B",str(cli),"predict","--station","2","--model","P2-L1","--start","2016-01","--end","2016-12","--met",str(met),"--output",str(out)]
p=subprocess.run(args,capture_output=True,text=True,check=True);d=json.loads(p.stdout);check("isolated_real_saved_model_inference_no_fit",d["n"]==12 and d["fit_calls"]==0)
jw(BASE/"evidence/CLI_PREDICTION_RECEIPT.json",d)
for name,modified in [("wrong_units",args+["--temp-unit","K"]),("wrong_station",args[:])]:
 if name=="wrong_station":modified[modified.index("--station")+1]="99999"
 modified=modified[:];modified[modified.index("--output")+1]=str(BASE/"runtime"/("SHOULD_NOT_EXIST_"+name+".csv"))
 p=subprocess.run(modified,capture_output=True,text=True);check("CLI_"+name+"_refused",p.returncode!=0 and not Path(modified[modified.index("--output")+1]).exists())
# Browser evidence: all real pages rendered from HTTP response.
def freeport():
 with socket.socket() as s:s.bind(("127.0.0.1",0));return s.getsockname()[1]
chrome=r"C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe"
browser=cdp.Browser(chrome,str(BASE/"tmp/browser_profile"),freeport());shots=[]
try:
 browser.viewport(1440,1000)
 routes=[("01_station","station",2,"TEMPORAL_HOLDOUT"),("02_failure_ID378","station",378,"TEMPORAL_HOLDOUT"),("03_evaluation","evaluation",2,"TEMPORAL_HOLDOUT"),("04_spatial_error","spatial",2,"TEMPORAL_HOLDOUT"),("05_V2_application","station",2,"FINAL_MODEL_APPLICATION"),("06_license","report",2,"TEMPORAL_HOLDOUT"),("07_models","models",2,"TEMPORAL_HOLDOUT")]
 for i,(name,tab,g,kind) in enumerate(routes):
  url=BASEURL+"/?view="+str(i)+"#/results?"+urllib.parse.urlencode({"tab":tab,"station":DS+":"+str(g),"kind":kind})
  browser.goto(url)
  check("browser_render_"+name,browser.wait("window.WEBR1&&WEBR1.ready&&document.querySelector('#view').textContent.length>50",20))
  text=browser.eval("document.querySelector('#view').textContent")
  if name=="06_license":
   browser.eval("Array.from(document.querySelectorAll('[data-report]')).find(e=>e.dataset.report==='license').click()");browser.wait("document.querySelector('.reporttext')&&document.querySelector('.reporttext').textContent.includes('LamaH')",15)
  if name=="02_failure_ID378":check("browser_negative_NSE_visible","-3.257" in text)
  if name=="03_evaluation":check("browser_unscored_NA_visible","NO_ELIGIBLE_TEST_SUPPORT" in text or "NOT_EVALUATED" in text)
  browser.screenshot(str(BASE/"evidence"/(name+".png")));shots.append({"page":name,"url":url,"screenshot":name+".png","rendered":True})
 # Actual dataset switch clears chart, spatial points and prior payload.
 browser.eval("document.querySelector('#dataset').value='SYRDARYA';document.querySelector('#dataset').dispatchEvent(new Event('change'))")
 check("dataset_switch_clears_public_content",browser.wait("WEBR1.ready&&WEBR1.last===null&&!document.querySelector('#view svg')&&document.querySelector('#view').textContent.includes('MODEL_EXECUTION_NOT_AUTHORIZED')",10))
 browser.screenshot(str(BASE/"evidence/08_dataset_isolation.png"))
 browser.eval("document.querySelector('#dataset').value='LAMAH_CE_PUBLIC_V1';document.querySelector('#dataset').dispatchEvent(new Event('change'))")
 check("switch_back_correct_public_dataset",browser.wait("WEBR1.ready&&document.querySelector('#view').textContent.includes('54个')",10))
 browser.viewport(800,1000);browser.goto(BASEURL+"/?mobile=1#/results?tab=evaluation");browser.wait("WEBR1.ready",15)
 check("narrow_view_no_document_overflow",browser.eval("document.documentElement.scrollWidth<=document.documentElement.clientWidth+1"))
 browser.screenshot(str(BASE/"evidence/09_narrow_evaluation.png"))
 errors=[e for e in browser.errors() if "403" not in e];check("no_browser_JS_errors",len(errors)==0,errors=errors)
finally:browser.close()
jw(BASE/"evidence/BROWSER_ACCEPTANCE.json",{"pages":shots,"all_pass":True})
after=history();before=jl(BASE/"evidence/HISTORY_BEFORE.json")
check("all_historical_manifests_unchanged",after==before)
jw(BASE/"evidence/HISTORY_AFTER.json",after)
jw(BASE/"INTEGRATION_TEST_RESULTS.json",{"UTC":now(),"all_pass":True,"checks":checks,"count":len(checks),"production_deployed":False,"source_Qobs_read":False,"models_retrained":0,"isolated_CLI_inference_records":12,"browser_screenshots":9})
print(json.dumps({"all_pass":True,"checks":len(checks),"screenshots":9,"production_deployed":False}))
