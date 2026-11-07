import sys,subprocess,urllib.request,urllib.error,urllib.parse,ast,socket
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/"code"))
from core import *
sys.path.insert(0,str(BASE/"tools"));import cdp
checks=[]
def ck(n,v,**kw):assert v,n;checks.append({"name":n,"pass":True,**kw})
def req(path,body=None):
 try:
  with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8791"+path,data=body,headers={"Content-Type":"application/json"} if body else {}),timeout=10) as r:return r.status,json.loads(r.read())
 except urllib.error.HTTPError as e:return e.code,json.loads(e.read())
st,_=req("/api/public/catalog?dataset=SYRDARYA");ck("final_server_catalog_rejects_wrong_dataset",st==403)
st,_=req("/api/v6/public/model/execute",json.dumps({"status":"GRANTED","authorized":True,"dataset":"LAMAH_CE_PUBLIC_V1"}).encode());ck("JSON_flags_do_not_grant_execution",st==403)
for code in [P5/"code/p5_cli.py",P4/"release/P4_PUBLIC_V2/runtime/inference.py"]:
 tree=ast.parse(code.read_text(encoding="utf-8"))
 ck("inference_code_no_fit_call_"+code.name,not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ["fit","fit_transform"] for n in ast.walk(tree)))
met=jl(P5/"runs/P5_A_SAVED_MODEL_APPLICATION/MET_2.json")
fixtures={"missing_previous_calendar_P":[r for r in met if r["date"]!="2015-12"],"target_Q_field":[{**r,"Qobs":-123.456} for r in met],"cross_dataset_field":[{**r,"dataset_id":"SYRDARYA"} for r in met]}
for name,data in fixtures.items():
 path=BASE/"runtime"/(name+".json");path.write_text(json.dumps(data),encoding="utf-8");out=BASE/"runtime"/("REJECTED_"+name+".csv")
 args=[sys.executable,"-B",str(P5/"code/p5_cli.py"),"predict","--station","2","--model","P2-L1","--start","2016-01","--end","2016-12","--met",str(path),"--output",str(out)]
 cp=subprocess.run(args,capture_output=True,text=True);ck("isolated_CLI_"+name,cp.returncode!=0 and not out.exists())
args=[sys.executable,"-B",str(P5/"code/p5_cli.py"),"predict","--station","6","--model","P2-L1","--start","2016-01","--end","2016-12","--met",str(P5/"runs/P5_A_SAVED_MODEL_APPLICATION/MET_2.json"),"--output",str(BASE/"runtime/REJECTED_WRONG_GAUGE.csv")]
cp=subprocess.run(args,capture_output=True,text=True);ck("isolated_CLI_wrong_known_gauge",cp.returncode!=0 and "WRONG_GAUGE" in cp.stderr)
with socket.socket() as s:s.bind(("127.0.0.1",0));port=s.getsockname()[1]
b=cdp.Browser(r"C:\Users\Administrator\AppData\Local\Google\Chrome\Application\chrome.exe",str(BASE/"tmp/final_browser"),port)
try:
 b.viewport(1440,1050);b.goto("http://127.0.0.1:8791/?final=1#/results?tab=station")
 ck("final_UI_interval_table",b.wait("window.WEBR1&&WEBR1.ready&&document.querySelector('#view').textContent.includes('平均区间宽度')",20))
 def fullshot(name):
  size=b.call("Page.getLayoutMetrics")["cssContentSize"];result=b.call("Page.captureScreenshot",format="png",captureBeyondViewport=True,clip={"x":0,"y":0,"width":min(size["width"],1440),"height":min(size["height"],4500),"scale":1});import base64;(BASE/"evidence"/name).write_bytes(base64.b64decode(result["data"]))
 fullshot("10_station_full.png")
 b.goto("http://127.0.0.1:8791/?final=2#/results?tab=spatial");ck("final_spatial_render",b.wait("WEBR1.ready&&!!document.querySelector('.mapdot')",15));fullshot("11_spatial_full.png")
 # Drive all actual station layers, not only initial NSE.
 for mode in ["qsim","coverage","width","applicability"]:
  b.eval("document.querySelector('#mapmode').value="+json.dumps(mode)+";document.querySelector('#mapmode').dispatchEvent(new Event('change'))")
  ck("actual_spatial_layer_"+mode,b.wait("WEBR1.ready&&WEBR1.state.mapmode==="+json.dumps(mode)+"&&document.querySelectorAll('.mapdot').length===27",15))
 b.goto("http://127.0.0.1:8791/?final=3#/results?tab=models");b.wait("WEBR1.ready",15);b.eval("document.querySelector('#execute').click()")
 ck("browser_execute_gate_visible",b.wait("document.querySelector('#executionResult').textContent.includes('403 MODEL_EXECUTION_NOT_AUTHORIZED')",10));fullshot("12_execution_gate.png")
 ck("final_UI_no_JS_exception",not any(e.get("method")=="Runtime.exceptionThrown" for e in b.events))
finally:b.close()
old=jl(BASE/"INTEGRATION_TEST_RESULTS.json");jw(BASE/"evidence/INITIAL_44_TESTS.json",old);old["checks"]+=checks;old["count"]=len(old["checks"]);old["browser_screenshots"]=12;old["UTC"]=now()
(BASE/"INTEGRATION_TEST_RESULTS.json").write_text(json.dumps(old,ensure_ascii=False,indent=2),encoding="utf-8")
jw(BASE/"evidence/FINAL_ADDITIONAL_ACCEPTANCE.json",{"checks":checks,"all_pass":True,"server_reloaded":True})
print(json.dumps({"additional_checks":len(checks),"total_checks":old["count"],"screenshots":12}))
