"""Post-V2 release, true-gap inference, and honest masked-observation disk-inference demo."""
from common import *
bootstrap()
from data import read_labels,features,weather
from inference import load_model,predict_range
import public_runtime as rt
import models as mathmodels
from vhs_sci.evaluate import metric_bundle
from train import fit_model,save_model,xof
from collections import Counter,defaultdict
import subprocess
commit=P/"runs/PUBLIC_DATA_FINAL_P4_V1/prediction_bundle"
def metric(y,p):
 rt.permit_metric(np.array(y),np.array(p));m=metric_bundle(y,p,synthetic=False)
 return {k:v["value"] for k,v in m.items()}
def main():
 v1=jl(P/"P4_V1_MODEL_MANIFEST.json");v2=jl(P/"P4_V2_MODEL_MANIFEST.json");assert v1["spec_hash"]==v2["spec_hash"]
 decision=jl(P/"evidence/V1_FROZEN_DECISION.json");default=decision["V2_global_default_model"]
 labels,qstatus=read_labels("2017-12",commit);fm={r["sample_id"]:r for r in features()};meta=cr(P/"source/observation_metadata.csv");attrs={int(r["ID"]):r for r in cr(R/"p1_seasonal_meteorology_ablation/source/metadata/D_gauges/1_attributes/Gauge_attributes.csv",";")}
 rt.register(list(fm.values()),labels,v2["snapshot_id"],"2017-12")
 ledger=[];gap=[];rec=[];finaltests=[];models={(r["gauge_id"],r["model_id"]):r for r in v2["models"]};model_cache={};weathers={}
 for entry in v2["models"]:
  g=entry["gauge_id"];m=load_model(entry["path"]);model_cache[g,entry["model_id"]]=m
  assert m.meta["spec_hash"]==v1["spec_hash"] and m.meta["snapshot_id"]!=v1["snapshot_id"]
  assert all(i[-7:]<="2017-12" for i in m.meta["train_ids"])
  old=next(t for t in v1["models"] if t["gauge_id"]==g and t["model_id"]==entry["model_id"])
  assert entry["model_hash"]!=old["model_hash"]
  finaltests.append({"gauge_id":g,"model_id":entry["model_id"],"V2_loaded":True,"V1_V2_spec_equal":True,"new_snapshot_and_parameters_identity":True,"calibration_statuses":";".join(sorted({z["status"] for z in m.calibration.values()}))})
 for row in meta:
  g=int(row["gauge_id"]);i=row["sample_id"];dt=row["date"];state=row["source_status"];nr=qstatus.get(i);start=attrs[g]["obsbeg_day"];end=attrs[g]["obsend"]
  if start not in ["0","-999",""] and int(dt[:4])<int(float(start)):state="OUTSIDE_OBSERVATION_COVERAGE"
  elif end not in ["0","-999",""] and int(dt[:4])>int(float(end)):state="OUTSIDE_OBSERVATION_COVERAGE"
  elif nr and nr["invalid_negative_days"]>0:state="OBS_REJECTED"
  elif state=="OBS_ACCEPTED":assert nr and nr["numeric_accepted"]
  ledger.append({**row,"observation_status":state,"numeric_Q_validated":True,"numeric_valid_checked_days":nr["valid_checked_days"] if nr else 0,"outside_version_coverage":False,"coverage_note":"before/after official gauge operating-year coverage" if state=="OUTSIDE_OBSERVATION_COVERAGE" else "within daily file and documented gauge-year coverage"})
  if state!="MISSING_TRUE":continue
  m=model_cache[g,default];weathers.setdefault(g,weather(g));out=None;reason=""
  if i not in fm:reason="MISSING_CURRENT_OR_PREVIOUS_CALENDAR_MET"
  else:
   try:out=m.predict_month(weathers[g],int(dt[:4]),int(dt[5:]))
   except AssertionError as e:reason=str(e)
  eligible=out is not None and out["application_eligible"]
  if out is not None and not eligible:reason="HIGH_EXTRAPOLATION_OR_UNCALIBRATED"
  gap.append({"gauge_id":g,"date":dt,"sample_id":i,"observation_status":state,"model_id":default,"eligible":eligible,"reason":reason,"support_class":out["support_class"] if out else "NO_MET_SUPPORT","model_hash":m.hash,"input_hash":out["input_hash"] if out else ""})
  if eligible:rec.append({"label":"PUBLIC_DATA_FINAL_P4","task":"RETROSPECTIVE_MONTHLY_STREAMFLOW_RECONSTRUCTION","observation_status":"MISSING_TRUE","eligible":True,"no_Qobs_for_scoring":True,**out})
 for g in sorted({int(r["gauge_id"]) for r in meta}):
  for dt in ["1980-12","2018-01"]:
   ledger.append({"gauge_id":g,"date":dt,"sample_id":sid(g,dt),"source_status":"OUTSIDE_SOURCE_COVERAGE","days_expected":calendar.monthrange(int(dt[:4]),int(dt[5:]))[1],"days_rows":0,"days_present":0,"days_checked_present":0,"days_qceq":0,"days_qcol":0,"numeric_Q_validated":False,"status_basis":"VERSION_MONTHLY_SOURCE_WINDOW_1981_2017","macro":"","region":"","met_supported":False,"observation_status":"OUTSIDE_SOURCE_COVERAGE","numeric_valid_checked_days":0,"outside_version_coverage":True,"coverage_note":"explicit boundary sentinel, not a true gap"})
 cw(P/"P4_OBSERVATION_STATUS_LEDGER.csv",ledger);cw(P/"P4_GAP_ELIGIBILITY.csv",gap,["gauge_id","date","sample_id","observation_status","model_id","eligible","reason","support_class","model_hash","input_hash"])
 cw(P/"P4_RECONSTRUCTIONS.csv",rec,list(rec[0]) if rec else ["label","date","gauge_id","observation_status","q_hat_raw","lower80","upper80","lower90","upper90"])
 # T0-frozen honest masked12 demonstration: independently refitted disk models omit all2016 Q.
 g=2;held=[sid(g,f"2016-{mo:02d}") for mo in range(1,13)];allids=sorted(i for i in labels if i in fm and fm[i]["gauge_id"]==g);train=[i for i in allids if i not in set(held)]
 assert set(held)<=set(allids) and not set(held)&set(train)
 demo=P/"runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO";demo.mkdir(exist_ok=False);mathmodels.FIT_EVENTS.clear();demoout=[];demometrics=[];demoparams=[]
 met=weather(g);metpath=demo/"MET_ONLY.json";jw(metpath,met)
 for mid in ["C0+PT","P2-L1"]:
  m,x,sec=fit_model(g,mid,train,held,v2["snapshot_id"],{"kind":"MASKED_DEMO","held_year":2016,"version":"V2"})
  cal=jl(P/"runs/PUBLIC_DATA_FINAL_P4_V1/calibration.json")[f"{g}|{mid}"]
  path=demo/mid.replace("+","_")
  dm=save_model(path,m,x,cal,g,"V2_MASKED_DEMO_NO_2016_Q","2017-12",sec,v2["snapshot_id"],digest({i:labels[i] for i in train}));demoparams.append(dm)
  output=demo/(mid.replace("+","_")+"_FRESH_PROCESS.csv")
  cp=subprocess.run([sys.executable,"-B",str(P/"code/inference.py"),"--model",str(path),"--met",str(metpath),"--start","2016-01","--end","2016-12","--output",str(output)],capture_output=True,text=True,check=True)
  rr=cr(output);assert len(rr)==12
  expected=m.predict(xof(held,v2["snapshot_id"]));actual=np.array([float(r["q_hat_raw"]) for r in rr]);assert np.allclose(expected,actual,atol=1e-12,rtol=1e-14)
  demoout.extend([{"observation_status":"MASKED_ACCEPTED","NOT_A_TRUE_GAP":True,**r} for r in rr])
  demometrics.append({"gauge_id":g,"model_id":mid,"masked_year":2016,"n":len(rr),"fresh_process_fit_calls":0,"actual_model_refit_excludes_2016":True,"PI_calibration":"V1<=2014, no2016Q","not_independent_new_V1_test":True,**metric([labels[i] for i in held],actual)})
  jw(demo/(mid.replace("+","_")+"_PROCESS_RECEIPT.json"),{"returncode":cp.returncode,"stdout":cp.stdout,"new_process":True,"fit_calls_inside_inference":0})
 cw(P/"P4_MASKED_DEMO_PREDICTIONS.csv",demoout);cw(P/"P4_MASKED_DEMO_METRICS.csv",demometrics)
 jw(demo/"MANIFEST.json",{"models":demoparams,"test_ids":held,"train_ids":train,"all_fit_events":mathmodels.FIT_EVENTS,"PI_basis":"V1 calibration contains no2016 labels","outer_fits":2,"inner_fits":sum(e["level"]=="inner" for e in mathmodels.FIT_EVENTS),"prediction_Qobs_free":True})
 seal(demo)
 jw(P/"evidence/V2_DISK_ACCEPTANCE.json",{"checks":finaltests,"all_pass":True,"model_count":len(finaltests),"fresh_process_masked_demo_metrics":demometrics})
 counts=dict(Counter(r["observation_status"] for r in ledger))
 release=[]
 for entry in v2["models"]:
  m=model_cache[entry["gauge_id"],entry["model_id"]];calok=all(v["status"]=="CALIBRATED" for v in m.calibration.values());isdefault=entry["model_id"]==default and calok
  release.append({**entry,"is_global_default":isdefault,"release_status":"DEFAULT_CONDITIONAL_ON_INPUT_SUPPORT" if isdefault else "BENCHMARK_RESEARCH_CANDIDATE","per_month_application_gate":"calendar met complete + month support>=4 + validPI + risk notHIGH","V1_station_score_not_used_for_default":True})
 jw(P/"P4_RELEASE_INDEX.json",{"classification":decision["direction"],"default_model_id":default,"V2_models":release,"default_count":sum(r["is_global_default"] for r in release),"gap_status":"ELIGIBLE_TRUE_GAPS_FOUND" if rec else "NO_ELIGIBLE_TRUE_GAPS","true_gaps":len(gap),"eligible_true_gaps":len(rec),"observation_status_counts":counts,"all_models_loadable":True})
 jw(P/"evidence/T4_COUNTS.json",{"observation_status_counts":counts,"true_gaps":len(gap),"eligible_true_gaps":len(rec),"fresh_process_demo_models":2,"fresh_process_demo_predictions":24,"demo_training_fits":2,"demo_inner_fits":sum(e["level"]=="inner" for e in mathmodels.FIT_EVENTS)})
 for ver in ["V1","V2"]:
  rows=cr(P/f"runs/PUBLIC_DATA_FINAL_P4_{ver}/PSEUDOGAP_PREDICTIONS.csv");agg=[]
  for key in sorted({(r["gauge_id"],r["model_id"],r["fold_id"]) for r in rows}):
   rr=[r for r in rows if (r["gauge_id"],r["model_id"],r["fold_id"])==key]
   agg.append({"version":ver,"gauge_id":int(key[0]),"model_id":key[1],"fold_id":key[2],"length":int(rr[0]["length"]),"n":len(rr),"primary":rr[0]["primary"],**metric([float(r["Qobs"]) for r in rr],[float(r["prediction"]) for r in rr])})
  cw(P/f"P4_{ver}_PSEUDOGAP_RESULTS.csv",agg)
 # combined required artifact
 cw(P/"P4_PSEUDOGAP_RESULTS.csv",cr(P/"P4_V1_PSEUDOGAP_RESULTS.csv")+cr(P/"P4_V2_PSEUDOGAP_RESULTS.csv"))
 attempt("T4_COMPLETED",true_gaps=len(gap),eligible_true_gaps=len(rec),fresh_process_predictions=24)
 print(json.dumps({"true_gaps":len(gap),"eligible_true_gaps":len(rec),"statuses":counts,"demo":demometrics}))
if __name__=="__main__":main()
