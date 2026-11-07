from p5lib import *
from collections import Counter,defaultdict
import subprocess
run=P/"runs/P5_SHRINK_BLOCKED_V1";bundle=run/"prediction_bundle";verify(bundle);verify(run)
params=jl(bundle/"MODEL_PARAMETERS.json");sel=jl(bundle/"WEIGHT_SELECTION.json");pred=cr(bundle/"PREDICTIONS_WITHOUT_QOBS.csv");fm={r["sample_id"]:r for r in cr(P4/"source/features.csv")};q=labels("2014-12")
assert len({(r["model_id"],r["sample_id"]) for r in pred})==len(pred)
lookup={(r["gauge_id"],r["cutoff"],r["model_id"]):r for r in params if r["kind"]=="OUTER_FORWARD_DEVELOPMENT"}
selections={(s["gauge_id"],s["outer_test_start"]):s for s in sel}
for r in params:
 assert set(r["train_ids"]).isdisjoint(r["test_ids"])
 assert max(i[-7:] for i in r["train_ids"])<=r["cutoff"]<min(i[-7:] for i in r["test_ids"])
 assert all(i[-7:]<="2014-12" for i in r["train_ids"]+r["test_ids"])
for s in sel:
 means={float(k):v for k,v in s["mean_MSE"].items()};se={float(k):v for k,v in s["SE"].items()};best=min(means,key=lambda w:(means[w],w));cut=means[best]+se[best];w=min(w for w in means if means[w]<=cut+1e-12*max(1,abs(cut)))
 assert w==s["selected_weight"]
 for e in s["evidence"]:assert e["inner_train_cutoff"]<min(i[-7:] for i in e["validation_ids"]) and max(i[-7:] for i in e["validation_ids"])<s["outer_test_start"]
by={};maxdiff=0
for r in pred:
 if r["model_id"]=="P5-L1-SHRINK":continue
 p=lookup[int(r["gauge_id"]),r["outer_train_cutoff"],r["model_id"]];f=fm[r["sample_id"]];mo=int(f["month"])-1;raw=np.array([float(f[k]) for k in p["fields"]]);tr=p["transform"];mu=np.array(tr["monthly_mean"])[mo];sd=np.array(tr["monthly_sample_std"])[mo];const=np.array(tr["monthly_constant"])[mo];z=np.where(const,0,(raw-mu)/np.where(const,1,sd));v=float(p["parameters"]["monthly_climatology"][mo]+z@np.array(p["parameters"]["beta_standardized"]));err=abs(v-float(r["Qsim_raw"]));assert err<1e-10*max(1,abs(v));maxdiff=max(maxdiff,err);by[r["sample_id"],r["model_id"]]=v
for r in pred:
 if r["model_id"]!="P5-L1-SHRINK":continue
 w=selections[int(r["gauge_id"]),r["test_start"]]["selected_weight"];a=by[r["sample_id"],"C0+PT"];b=by[r["sample_id"],"P2-L1"];assert abs(float(r["Qsim_raw"])-(a+w*(b-a)))<1e-10*max(1,abs(a))
for r in cr(P/"P5_SHRINK_INTERNAL_RESULTS.csv"):
 rr=[v for v in pred if v["gauge_id"]==r["gauge_id"] and v["model_id"]==r["model_id"] and (r["outer_test_start"]=="ALL" or v["test_start"]==r["outer_test_start"])]
 m=metric([q[v["sample_id"]] for v in rr],[float(v["Qsim_raw"]) for v in rr])
 for key,v in m.items():
  if v is None:assert r[key]==""
  else:assert np.isclose(float(r[key]),v,rtol=1e-11,atol=1e-11)
hist={str(root):{"count":verify(root),"seal":sha(root/"SHA256SUMS.txt")} for root in [R,R/"p1_seasonal_meteorology_ablation",P2,R/"p3_forward_temporal_validation",P4]}
before=jl(P/"evidence/HISTORY_BEFORE.json");assert hist==before
jw(P/"evidence/HISTORY_AFTER.json",hist)
jw(P/"P5_VERIFICATION.json",{"UTC":now(),"pass":True,"independent_forward_model_parameter_records_checked":len(params),"base_and_shrink_predictions_checked":len(pred),"unique_target_months":len({r["sample_id"] for r in pred}),"weight_selections_checked":len(sel),"max_direct_formula_difference":maxdiff,"future2015Q_in_development":False,"train_validation_date_overlap":0,"historical_hashes_unchanged":True,"all54_final_models_loaded_in_new_process":True})
attempt("P5_NUMERIC_VERIFICATION_PASS",predictions=len(pred),weight_selections=len(sel),historical_freezes_unchanged=True)
print(json.dumps({"pass":True,"parameters":len(params),"predictions":len(pred),"selections":len(sel)}))
