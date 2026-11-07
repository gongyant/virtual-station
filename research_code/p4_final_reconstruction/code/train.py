"""Actual fits use P2 frozen math. Final and masked-block fits are separate identities."""
from common import *
bootstrap()
import public_runtime as rt
import models as mathmodels
from models import Inputs,MonthlyWeatherRidge
from data import features,read_labels,weather
from inference import load_model,predict_month
import time,platform,traceback
from collections import defaultdict
SPEC=jl(P/"P4_PROTOCOL.json");SPLIT=jl(P/"P4_TEST_SPLIT_FROZEN.json");SRC=jl(P/"source/SNAPSHOT.json")
MODELS=["C0+PT","P2-L1"];META=cr(P/"source/observation_metadata.csv");FEATS=features();FM={r["sample_id"]:r for r in FEATS}
def xof(ids,snapshot):
 r=[FM[i] for i in ids];return Inputs(tuple(ids),np.array([v["year"] for v in r]),np.array([v["month"] for v in r]),{k:np.array([v[k] for v in r]) for k in ["P","T","L1"]},snapshot)
def frozen_folds(g,cutoff):
 dates=sorted(r["date"] for r in META if int(r["gauge_id"])==g and r["date"]<=cutoff and r["source_status"]=="OBS_ACCEPTED" and sid(g,r["date"]) in FM)
 ds=set(dates);years=[y for y in sorted({int(d[:4]) for d in dates}) if all(f"{y}-{m:02d}" in ds for m in range(1,13))]
 chosen=sorted({years[round(q*(len(years)-1))] for q in [.2,.4,.6,.8]})
 out=[{"fold_id":f"ID{g}_L12_{y}","length":12,"primary":True,"test_ids":[sid(g,f"{y}-{m:02d}") for m in range(1,13)]} for y in chosen]
 for length in [3,6,24]:
  for d in dates:
   if d<"1989-01":continue
   y,m=map(int,d.split("-"));last=y*12+m-1+length-1;end=f"{last//12}-{last%12+1:02d}"
   block=list(months(d,end))
   if all(t in ds for t in block):
    out.append({"fold_id":f"ID{g}_L{length}_{d}","length":length,"primary":False,"test_ids":[sid(g,t) for t in block]});break
 return out
def freeze_folds():
 plan={v:{str(s["gauge_id"]):frozen_folds(s["gauge_id"],cut) for s in SPLIT["splits"]} for v,cut in [("V1","2014-12"),("V2","2017-12")]}
 jw(P/"P4_PSEUDOGAP_FOLDS_FROZEN.json",{"UTC":now(),"test_scores_seen":False,"metadata_only":True,"folds":plan})
 jw(P/"P4_UNCERTAINTY_CONTRACT.json",SPEC["interval"])
def calibrate(g,mid,preds,p3):
 out={}
 for ss in ["DJF","MAM","JJA","SON"]:
  rr=[r["prediction"]-r["Qobs"] for r in preds if r["primary"] and season(int(r["date"][5:]))==ss and r["model_id"]==mid]
  tr=[float(r["Qsim_raw_m3s"])-float(r["Qobs_m3s"]) for r in p3 if int(r["gauge_id"])==g and r["model_id"]==mid and season(int(r["month"]))==ss]
  scale=float(np.sqrt(np.mean(np.square(rr)))) if rr else None
  status="INSUFFICIENT_SEASONAL_SAMPLE" if len(rr)<8 else "ZERO_RESIDUAL_SCALE" if scale<=1e-15 else "NO_TRANSFER_SUPPORT" if len(tr)<8 else "CALIBRATED"
  kappa=max(1,float(np.sqrt(np.mean(np.square(tr))))/scale) if status=="CALIBRATED" else None
  row={"status":status,"n_OOF_primary12":len(rr),"n_P3_forward":len(tr),"OOF_RMSE":scale,"kappa":kappa,"P3_not_independent":True}
  for level in [80,90]:
   rank=math.ceil((len(rr)+1)*level/100)
   if status=="CALIBRATED" and rank<=len(rr):
    quant=float(np.sort(np.abs(rr)/scale)[rank-1]);row[f"normalized_quantile{level}"]=quant;row[f"halfwidth{level}"]=quant*scale*kappa
   else:
    row[f"halfwidth{level}"]=None
    if status=="CALIBRATED":row["status"]="UNDEFINED_QUANTILE"
  out[ss]=row
 return out
def save_model(path,m,x,cal,g,version,cutoff,fit_seconds,snapshot,labelhash):
 path.mkdir(parents=True,exist_ok=False);Z=m.transform(x);precision=np.linalg.inv(Z.T@Z+m.selected_alpha*np.eye(len(m.fields)));lv=np.einsum("ij,jk,ik->i",Z,precision,Z)
 counts=np.array([sum(x.months==mm) for mm in range(1,13)])
 arrays={"climate":m.climate,"mu":m.mu,"sd":m.sd,"constant":m.constant,"beta":m.beta,"precision":precision,"leverage_q99":np.array(float(np.quantile(lv,.99))),"month_counts":counts,"Z_q01":np.quantile(Z,.01,axis=0),"Z_q99":np.quantile(Z,.99,axis=0)}
 np.savez(path/"arrays.npz",**arrays)
 info={**m.record(),"dataset":"LAMAH_CE_PUBLIC_V1","gauge_id":g,"release_version":version,"train_cutoff":cutoff,"actual_train_start":min(x.ids)[-7:],"actual_train_end":max(x.ids)[-7:],"train_ids":list(x.ids),"train_ids_chronological_hash":digest(list(x.ids)),"train_label_hash":labelhash,"spec_hash":SPEC["spec_hash"],"protocol_hash":sha(P/"P4_PROTOCOL.json"),"snapshot_id":snapshot,"math_sha256":SPEC["spec"]["math_sha256"],"implementation_files":{p.name:sha(p) for p in [Path(__file__),P/"code/public_runtime.py",P/"code/inference.py",P/"code/data.py",P/"code/common.py"]},"environment":{"python":sys.version,"numpy":np.__version__,"platform":platform.platform()},"fit_seconds":fit_seconds,"calibration":cal,"input_units":{"P":"mm/month","T":"degC"},"output_unit":"m3/s","support_definition":SPEC["risk"],"npz_sha256":sha(path/"arrays.npz"),"created_UTC":now(),"zero_std":"unchanged P2 flags ->zero anomaly; unseen departure high risk","missing":"reject, never zero","Q20":float(np.quantile([rt.LABELS[i] for i in x.ids],.2)),"Q80":float(np.quantile([rt.LABELS[i] for i in x.ids],.8))}
 jw(path/"model.json",info);seal(path);return {"gauge_id":g,"model_id":m.model_id,"path":str(path),"model_hash":sha(path/"SHA256SUMS.txt"),"train_months":len(x.ids),"snapshot_id":snapshot,"spec_hash":SPEC["spec_hash"]}
def fit_model(g,mid,trainids,heldids,snapshot,context):
 rt.set_outer_train(trainids);mathmodels.FIT_CONTEXT.clear();mathmodels.FIT_CONTEXT.update(context)
 tx=xof(trainids,snapshot);y=rt.read_training(trainids);start=time.perf_counter();m=MonthlyWeatherRidge(mid).fit(tx,y);elapsed=time.perf_counter()-start
 return m,tx,elapsed
def run(version):
 cutoff="2014-12" if version=="V1" else "2017-12";run=P/"runs"/("PUBLIC_DATA_FINAL_P4_"+version);run.mkdir(exist_ok=False)
 commit=P/"runs/PUBLIC_DATA_FINAL_P4_V1/prediction_bundle"
 labels,status=read_labels(cutoff,commit if version=="V2" else None)
 # Provisional metadata sample contract is confirmed numerically, not silently changed.
 for row in META:
  if row["date"]<=cutoff and row["source_status"]=="OBS_ACCEPTED":
   assert row["sample_id"] in labels,"METADATA_NUMERIC_Q_CONFLICT_ABORT"
 snapshot=SRC["snapshot_base"]+"-"+version+"-"+digest({k:v for k,v in labels.items()})[:12]
 rt.register(FEATS,labels,snapshot,cutoff);p3=cr(P3/"P3_TEST_PREDICTIONS.csv")
 plans=jl(P/"P4_PSEUDOGAP_FOLDS_FROZEN.json")["folds"][version];preds=[];finals=[];cals={};numeric_tests=[];totalinner=totalouter=0;crossrecords=[]
 attempt(version+"_TRAIN_STARTED",snapshot=snapshot)
 for s in SPLIT["splits"]:
  g=int(s["gauge_id"]);allids=sorted(i for i in labels if i in FM and FM[i]["gauge_id"]==g)
  mathmodels.FIT_EVENTS.clear();local=[];finalmodels={}
  assert all(i[-7:]<=cutoff for i in allids) and all(sum(FM[i]["month"]==mm for i in allids)>=4 for mm in range(1,13))
  for mid in MODELS:
   m,x,sec=fit_model(g,mid,allids,[],snapshot,{"version":version,"gauge_id":g,"kind":"FINAL"})
   finalmodels[mid]=(m,x,sec)
  for fold in plans[str(g)]:
   held=fold["test_ids"];train=[i for i in allids if i not in set(held)];assert set(train).isdisjoint(held) and set(held)<=set(allids)
   for mid in MODELS:
    m,x,sec=fit_model(g,mid,train,held,snapshot,{"version":version,"gauge_id":g,"kind":"PSEUDOGAP","fold_id":fold["fold_id"]})
    raw=m.predict(xof(held,snapshot))
    # Connect held Q only after block predictions fixed.
    rows=[{"version":version,"gauge_id":g,"model_id":mid,"fold_id":fold["fold_id"],"length":fold["length"],"primary":fold["primary"],"date":i[-7:],"sample_id":i,"prediction":float(v),"Qobs":labels[i],"status":"MASKED_ACCEPTED"} for i,v in zip(held,raw)]
    local.extend(rows);crossrecords.append({"gauge_id":g,"fold":fold,"actual_train_ids":train,"fit_seconds":sec,**m.record()})
  for mid in MODELS:
   cal=calibrate(g,mid,local,p3);cals[f"{g}|{mid}"]=cal
   m,x,sec=finalmodels[mid];path=P/"models"/version/f"ID_{g}"/mid.replace("+","_")
   manifest=save_model(path,m,x,cal,g,version,cutoff,sec,snapshot,digest({i:labels[i] for i in x.ids}));finals.append(manifest)
   loaded=load_model(path);met=weather(g);sampleids=s["V1_test_ids"] if version=="V1" else allids[-12:]
   # No test Q passed, only features (also registered external weather).
   if sampleids:
    expected=m.predict(xof(sampleids,snapshot));actual=np.array([loaded.predict_month(met,FM[i]["year"],FM[i]["month"])["q_hat_raw"] for i in sampleids])
    assert np.array_equal(actual,expected) or np.allclose(actual,expected,rtol=1e-14,atol=1e-12)
    shuffled=loaded.predict_month(list(reversed(met)),FM[sampleids[0]]["year"],FM[sampleids[0]]["month"])
    assert shuffled["q_hat_raw"]==actual[0]
    numeric_tests.append({"version":version,"gauge_id":g,"model_id":mid,"real_reload_max_abs_error":float(max(abs(actual-expected))),"reordered_weather_equal":True,"n":len(sampleids),"model_hash":loaded.hash})
  preds.extend(local)
  totalouter+=sum(e["level"]=="outer" for e in mathmodels.FIT_EVENTS);totalinner+=sum(e["level"]=="inner" for e in mathmodels.FIT_EVENTS)
  with (run/"fit_events.jsonl").open("a",encoding="utf-8") as f:
   for e in mathmodels.FIT_EVENTS:f.write(json.dumps(e)+"\n")
  print(json.dumps({"version":version,"gauge_id":g,"completed_final_models":len(finals),"outer_fits":totalouter,"inner_fits":totalinner}),flush=True)
 cw(run/"PSEUDOGAP_PREDICTIONS.csv",preds);jw(run/"crossfit_parameters.json",crossrecords);jw(run/"calibration.json",cals);jw(run/"reload_tests.json",numeric_tests)
 manifest={"version":version,"label":"PUBLIC_DATA_FINAL_P4","task":SPEC["task"],"run_id":run.name,"snapshot_id":snapshot,"spec_hash":SPEC["spec_hash"],"protocol_hash":sha(P/"P4_PROTOCOL.json"),"split_hash":sha(P/"P4_TEST_SPLIT_FROZEN.json"),"folds_hash":sha(P/"P4_PSEUDOGAP_FOLDS_FROZEN.json"),"train_cutoff":cutoff,"n_stations":len(SPLIT["splits"]),"final_fits":len(finals),"all_outer_fits_including_crossfit":totalouter,"inner_fits":totalinner,"models":finals,"test_Q_used":version=="V2","no_fresh_V2_independent_test":version=="V2","created_UTC":now()}
 jw(P/f"P4_{version}_MODEL_MANIFEST.json",manifest);jw(run/"manifest.json",manifest)
 if version=="V1":
  bundle=run/"prediction_bundle";bundle.mkdir()
  output=[]
  for mf in finals:
   s=next(t for t in SPLIT["splits"] if t["gauge_id"]==mf["gauge_id"]);loaded=load_model(mf["path"]);met=weather(mf["gauge_id"])
   for i in s["V1_test_ids"]:
    r=FM[i];pred=loaded.predict_month(met,r["year"],r["month"]);output.append({"label":"PUBLIC_DATA_FINAL_P4","task":SPEC["task"],"version":version,"sample_id":i,"macro":s["macro"],"region":s["region"],**pred})
  cw(bundle/"PREDICTIONS_WITHOUT_QOBS.csv",output)
  jw(bundle/"COMMITMENT.json",{"UTC":now(),"all_predictions_complete":True,"test_numeric_Q_loaded":False,"n_predictions":len(output),"models_manifest_hash":sha(P/"P4_V1_MODEL_MANIFEST.json"),"protocol_hash":sha(P/"P4_PROTOCOL.json"),"split_hash":sha(P/"P4_TEST_SPLIT_FROZEN.json"),"calibration_hash":sha(run/"calibration.json"),"prediction_hash":sha(bundle/"PREDICTIONS_WITHOUT_QOBS.csv")})
  seal(bundle);verify(bundle)
  cw(P/"P4_V1_PREDICTIONS.csv",output);jw(P/"P4_CALIBRATION.json",{"V1":cals,"basis":"V1 primary12 block-out residuals + frozen P3 scale ratio; no2015-17Q"})
  jw(P/"evidence/V1_PREDICTION_COMMIT.json",{"UTC":now(),"seal_hash":sha(bundle/"SHA256SUMS.txt"),"predictions":len(output),"test_Q_numeric_loaded":False,"reload_tests_pass":True})
 attempt(version+"_TRAIN_COMPLETED",outer_fits=totalouter,inner_fits=totalinner,final_models=len(finals))
if __name__=="__main__":
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument("stage",choices=["freeze","V1","V2"]);a=ap.parse_args()
 try:
  freeze_folds() if a.stage=="freeze" else run(a.stage)
 except Exception as e:
  attempt("FAILED",stage=a.stage,error=repr(e),traceback=traceback.format_exc());raise
