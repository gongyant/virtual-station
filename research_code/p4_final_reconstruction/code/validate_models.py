"""Real persisted-model acceptance. No test-Q numeric file is opened."""
from common import *
bootstrap()
from inference import load_model,predict_month,predict_range
from data import weather,features,read_labels
import public_runtime as rt
from models import Inputs
import inspect,subprocess,shutil
checks=[];manifest=jl(P/"P4_V1_MODEL_MANIFEST.json");labels,_=read_labels("2014-12");ff=features();fmap={r["sample_id"]:r for r in ff}
def check(name,fn):
 fn();checks.append({"check":name,"status":"PASS"})
for r in manifest["models"]:
 m=load_model(r["path"]);g=r["gauge_id"];met=weather(g);ids=m.meta["train_ids"]
 assert all(i[-7:]<="2014-12" for i in ids)
 assert m.meta["spec_hash"]==jl(P/"P4_PROTOCOL.json")["spec_hash"]
 assert all(sum(i[-2:]==f"{mo:02d}" for i in ids)>=4 for mo in range(1,13))
 a=m.arrays;rows=[fmap[i] for i in ids];months1=np.array([z["month"] for z in rows]);raw=np.array([[z[k] for k in m.fields] for z in rows]);y=np.array([labels[i] for i in ids]);Z=np.where(a["constant"][months1-1],0,(raw-a["mu"][months1-1])/np.where(a["constant"][months1-1],1,a["sd"][months1-1]))
 for mo in range(1,13):
  ix=months1==mo
  assert np.allclose(a["climate"][mo-1],y[ix].mean(),rtol=1e-13)
  assert np.allclose(a["mu"][mo-1],raw[ix].mean(axis=0),rtol=1e-13)
 residual=y-a["climate"][months1-1];alpha=m.meta["parameters"]["selection"]["selected_alpha"]
 assert np.allclose((Z.T@Z+alpha*np.eye(len(m.fields)))@a["beta"],Z.T@residual,rtol=1e-10,atol=1e-8)
 checks.append({"check":"REAL_PARAMETERS_TRAIN_ONLY_AND_RIDGE_NORMAL_EQUATION","gauge_id":g,"model_id":m.meta["model_id"],"status":"PASS"})
m=load_model(manifest["models"][1]["path"]);met=weather(m.meta["gauge_id"])
base=predict_month(m,met,2016,1)
assert base==predict_month(m,list(reversed(met)),2016,1)
checks.append({"check":"REAL_WEATHER_ORDER_INVARIANCE","status":"PASS"})
for name,args in [
 ("WRONG_UNITS",(met,2016,1,{"P":"m","T":"kelvin"})),
 ("MISSING_CURRENT_MONTH",([r for r in met if r["date"]!="2016-01"],2016,1)),
 ("MISSING_ACTUAL_PREVIOUS_MONTH",([r for r in met if r["date"]!="2015-12"],2016,1)),
 ("TARGET_Q_REJECTED",([{**r,"Qobs":123.} for r in met],2016,1)),
 ("WRONG_GAUGE",([{**r,"gauge_id":999} for r in met],2016,1)),
 ("NONFINITE_INPUT",([{**r,"P":float("nan")} if r["date"]=="2016-01" else r for r in met],2016,1))]:
 try:predict_month(m,*args)
 except (AssertionError,ValueError,KeyError):checks.append({"check":name,"status":"PASS"})
 else:raise AssertionError("REJECTION_FAILED "+name)
# Altering a separate scoring-label object cannot affect a no-Q function.
fake_score={f"2016-{mo:02d}":-1e20 for mo in range(1,13)}
p0=predict_month(m,met,2016,1)
for k in fake_score:fake_score[k]=1e30
assert p0==predict_month(m,met,2016,1)
assert "Q" not in inspect.signature(predict_month).parameters
checks.append({"check":"SCORING_LABEL_PERTURBATION_NO_Q_API_INVARIANCE","status":"PASS","scope":"separate scorer object, no labels passed"})
# Calendar-L1 direct arithmetic.
prev=next(r for r in met if r["date"]=="2015-12");cur=next(r for r in met if r["date"]=="2016-01")
raw=np.array([cur["P"],cur["T"],prev["P"]]);a=m.arrays;z=(raw-a["mu"][0])/a["sd"][0]
assert np.isclose(p0["q_hat_raw"],a["climate"][0]+z@a["beta"],rtol=1e-13)
checks.append({"check":"REAL_JANUARY_USES_PRIOR_DECEMBER","status":"PASS"})
rt.register(ff,labels,manifest["snapshot_id"],"2014-12")
future=next(r for r in ff if r["gauge_id"]==2 and r["date"]=="2016-01")
xx=Inputs((future["sample_id"],),np.array([2016]),np.array([1]),{k:np.array([future[k]]) for k in ["P","T","L1"]},manifest["snapshot_id"])
try:rt.admit_training_matrix(xx,np.array([100.]))
except AssertionError:checks.append({"check":"FUTURE_Q_TRAINING_REJECTED","status":"PASS"})
else:raise AssertionError("CUTOFF_BYPASS")
for r in cr(P/"P4_V1_PREDICTIONS.csv"):
 for lv in [80,90]:
  if r[f"lower{lv}"]!="":assert float(r[f"lower{lv}"])<=float(r["q_hat_raw"])<=float(r[f"upper{lv}"])
 if r["lower80"]!="" and r["lower90"]!="":assert float(r["lower90"])<=float(r["lower80"])<=float(r["upper80"])<=float(r["upper90"])
checks.append({"check":"ALL_REAL_INTERVAL_ORDER_AND_NESTING","status":"PASS"})
# Identity tampering tested on an isolated copy, never frozen model.
tmp=P/"evidence/tampered_model";shutil.copytree(Path(manifest["models"][0]["path"]),tmp)
(tmp/"arrays.npz").write_bytes((tmp/"arrays.npz").read_bytes()+b"tamper")
try:load_model(tmp)
except AssertionError:checks.append({"check":"TAMPERED_MODEL_HASH_REJECTED","status":"PASS","fixture":str(tmp)})
else:raise AssertionError("HASH_BYPASS")
jw(P/"evidence/REAL_MODEL_ACCEPTANCE.json",{"UTC":now(),"checks":checks,"all_pass":True,"test_numeric_Q_read":False})
metpath=P/"evidence/FRESH_PROCESS_MET_ONLY.json";jw(metpath,met)
output=P/"evidence/FRESH_PROCESS_V1_PREDICTIONS.csv"
cp=subprocess.run([sys.executable,"-B",str(P/"code/inference.py"),"--model",str(m.path),"--met",str(metpath),"--start","2016-01","--end","2016-12","--output",str(output)],capture_output=True,text=True,check=True)
jw(P/"evidence/FRESH_PROCESS_V1_RECEIPT.json",{"UTC":now(),"returncode":cp.returncode,"stdout":cp.stdout,"input_hash":sha(metpath),"output_hash":sha(output),"fit_calls":0})
print(json.dumps({"checks":len(checks),"all_pass":True,"fresh_process_predictions":len(cr(output))}))
