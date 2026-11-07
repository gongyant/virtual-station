"""One score release after global prediction/interval commitment, no fitting."""
from common import *
bootstrap()
import public_runtime as rt
from vhs_sci.evaluate import metric_bundle
from data import read_labels
from collections import defaultdict
run=P/"runs/PUBLIC_DATA_FINAL_P4_V1";bundle=run/"prediction_bundle"
assert not (P/"P4_V1_EVALUATION.csv").exists(),"V1_ALREADY_SCORED"
assert jl(P/"evidence/REAL_MODEL_ACCEPTANCE.json")["all_pass"]
assert jl(P/"evidence/FRESH_PROCESS_V1_RECEIPT.json")["returncode"]==0
verify(bundle);commit=jl(bundle/"COMMITMENT.json");assert not commit["test_numeric_Q_loaded"] and commit["all_predictions_complete"]
labels,qstatus=read_labels("2017-12",bundle)
split=jl(P/"P4_TEST_SPLIT_FROZEN.json");groups={r["gauge_id"]:r for r in split["splits"]};pred=cr(bundle/"PREDICTIONS_WITHOUT_QOBS.csv")
assert len(pred)==commit["n_predictions"]
for r in pred:
 assert r["sample_id"] in labels,"METADATA_NUMERIC_TEST_Q_CONFLICT_NO_RESELECT"
 for k in ["q_hat_raw","q_hat_nonnegative","max_abs_z","leverage_ratio","lower80","upper80","lower90","upper90"]:r[k]=float(r[k]) if r[k]!="" else None
 r["gauge_id"]=int(r["gauge_id"]);r["Qobs"]=labels[r["sample_id"]];r["year"]=int(r["date"][:4]);r["month"]=int(r["date"][5:])
jw(P/"evidence/TEST_Q_RELEASE_RECEIPT.json",{"UTC":now(),"prediction_commit_sha256":sha(bundle/"SHA256SUMS.txt"),"first_test_numeric_Q_stage":"T2_SCORER","metadata_numeric_discrepancies":0,"unique_test_Q_months":len(set(r["sample_id"] for r in pred)),"read_after_real_model_acceptance":True})
def metrics(rows,mode="raw"):
 y=np.array([r["Qobs"] for r in rows]);p=np.array([r["q_hat_"+mode] for r in rows]);rt.permit_metric(y,p);m=metric_bundle(y,p,synthetic=False)
 return {**{k:v["value"] for k,v in m.items()},**{k+"_reason":v["reason_code"] for k,v in m.items()}}
overall=[];yearly=[];coverage=[];comparisons=[];diagnostics=[]
for g,s in groups.items():
 local=[r for r in pred if r["gauge_id"]==g]
 if not local:continue
 for mid in ["C0+PT","P2-L1"]:
  rr=[r for r in local if r["model_id"]==mid]
  for mode in ["raw","nonnegative"]:
   overall.append({"gauge_id":g,"macro":s["macro"],"model_id":mid,"prediction":mode,"n":len(rr),"primary_site":s["main_eligible"],**metrics(rr,mode)})
  for y in [2015,2016,2017]:
   yy=[r for r in rr if r["year"]==y]
   yearly.append({"gauge_id":g,"macro":s["macro"],"model_id":mid,"year":y,"n":len(yy),**metrics(yy)})
  for category,ss in [("ALL",rr)]+[(z,[r for r in rr if season(r["month"])==z]) for z in ["DJF","MAM","JJA","SON"]]+[("HIGH_EXTRAPOLATION",[r for r in rr if r["support_class"]=="HIGH_EXTRAPOLATION"])]:
   for level in [80,90]:
    valid=[r for r in ss if r[f"lower{level}"] is not None]
    coverage.append({"gauge_id":g,"macro":s["macro"],"model_id":mid,"subset":category,"nominal":level/100,"n":len(ss),"n_defined":len(valid),"coverage":sum(r[f"lower{level}"]<=r["Qobs"]<=r[f"upper{level}"] for r in valid)/len(valid) if valid else None,"mean_width":float(np.mean([r[f"upper{level}"]-r[f"lower{level}"] for r in valid])) if valid else None,"reason":"" if valid else "NO_DEFINED_INTERVALS"})
  losses=np.array([(r["q_hat_raw"]-r["Qobs"])**2 for r in rr]);j=int(np.argmax(losses));worst=rr[j]
  diagnostics.append({"gauge_id":g,"macro":s["macro"],"model_id":mid,"worst_month":worst["date"],"largest_month_SSE_fraction":float(losses[j]/sum(losses)) if sum(losses)>0 else None,"negative_predictions":sum(r["q_hat_raw"]<0 for r in rr),"high_extrapolation_months":sum(r["support_class"]=="HIGH_EXTRAPOLATION" for r in rr),"max_abs_z":max(r["max_abs_z"] for r in rr),"max_leverage_ratio":max(r["leverage_ratio"] for r in rr)})
 for subset in ["ALL",2015,2016,2017,"DJF","MAY_JUN"]:
  rr=[r for r in local if subset=="ALL" or r["year"]==subset or subset=="DJF" and r["month"] in [12,1,2] or subset=="MAY_JUN" and r["month"] in [5,6]]
  a={r["sample_id"]:r for r in rr if r["model_id"]=="C0+PT"};b={r["sample_id"]:r for r in rr if r["model_id"]=="P2-L1"};assert set(a)==set(b)
  mse0=float(np.mean([(a[i]["q_hat_raw"]-a[i]["Qobs"])**2 for i in a]));mse1=float(np.mean([(b[i]["q_hat_raw"]-b[i]["Qobs"])**2 for i in a]))
  comparisons.append({"gauge_id":g,"macro":s["macro"],"subset":subset,"n":len(a),"MSE_C0PT":mse0,"MSE_L1":mse1,"MSE_skill":1-mse1/mse0 if mse0>0 else None,"primary_site":s["main_eligible"]})
main=[r for r in comparisons if r["subset"]=="ALL" and r["primary_site"]];mean=float(np.mean([r["MSE_skill"] for r in main])) if main else None
summary=[]
for sub in ["ALL",2015,2016,2017,"DJF","MAY_JUN"]:
 for macro in ["ALL","Rhine","Elbe","Danube"]:
  vals=[r["MSE_skill"] for r in comparisons if r["subset"]==sub and r["primary_site"] and (macro=="ALL" or r["macro"]==macro)]
  summary.append({"subset":sub,"macro":macro,"n_stations":len(vals),"mean_station_skill":float(np.mean(vals)) if vals else None,"median_station_skill":float(np.median(vals)) if vals else None,"positive_stations":sum(v>0 for v in vals)})
yearwins=sum(r["mean_station_skill"]>0 for r in summary if r["macro"]=="ALL" and r["subset"] in [2015,2016,2017]);groupwins=sum(r["mean_station_skill"]>0 for r in summary if r["subset"]=="ALL" and r["macro"]!="ALL")
direction="NOT_SUPPORTED" if mean is None or mean<=0 else "DIRECTION_SUPPORTED" if yearwins>=2 and groupwins>=2 else "INCONCLUSIVE"
if split["support_tier"]=="INSUFFICIENT":direction="INSUFFICIENT_TEST_SUPPORT"
decision={"UTC":now(),"mean_station_MSE_skill":mean,"median_station_MSE_skill":float(np.median([r["MSE_skill"] for r in main])) if main else None,"n_sites":len(main),"positive_sites":sum(r["MSE_skill"]>0 for r in main),"positive_years":yearwins,"positive_macro_groups":groupwins,"direction":direction,"V2_global_default_model":"P2-L1" if direction=="DIRECTION_SUPPORTED" else "C0+PT","not_statistical_confirmation":True}
cw(P/"P4_V1_EVALUATION.csv",overall);cw(P/"P4_V1_YEARLY_EVALUATION.csv",yearly);cw(P/"P4_V1_MODEL_COMPARISON.csv",comparisons);cw(P/"P4_V1_REGION_YEAR_SUMMARY.csv",summary);cw(P/"P4_V1_COVERAGE.csv",coverage);cw(P/"P4_V1_FAILURE_DIAGNOSTICS.csv",diagnostics);jw(P/"evidence/V1_FROZEN_DECISION.json",decision)
# Q-free evaluation package copied, numeric labels remain scorer-only in memory/source.
cw(run/"EVALUATION.csv",overall);jw(run/"DECISION.json",decision);seal(run)
attempt("V1_SCORED_ONCE",**decision)
print(json.dumps(decision))
