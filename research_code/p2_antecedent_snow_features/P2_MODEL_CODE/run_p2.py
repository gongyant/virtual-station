"""Actual P2 public real LOYO, development first then frozen external; no P0/P1 refits."""
import os
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):os.environ[key]="1"
import bootstrap,csv,json,hashlib,time,platform,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import public_runtime as src
from models import Inputs,MonthlyWeatherRidge,FIT_CONTEXT,FIT_EVENTS,FIELDS
from vhs_sci.contracts import GROUP_B,digest,ids_hash
from vhs_sci.folds import make_folds
from vhs_sci.evaluate import metric_bundle,paired_year_comparison
P=Path(__file__).parents[1];R=P.parent;P1=R/"p1_seasonal_meteorology_ablation";LABEL="PUBLIC_DATA_EXPLORATORY_P2"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jw(p,x):
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def cw(p,rs):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def met(ids,p):
 y=src.permit_metric(ids,p);m=metric_bundle(y,p,synthetic=False)
 return y,{k:v["value"] for k,v in m.items()}|{"NA_reasons":"|".join(k+":"+v["reason_code"] for k,v in m.items() if v["status"]=="N/A")}
def stat(y,p):
 if len(y)==0:return {"n":0,"Qobs_mean":None,"Qsim_mean":None,"bias":None,"RMSE":None,"MSE":None,"reason":"EMPTY_DIAGNOSTIC_SUBSET"}
 return {"n":len(y),"Qobs_mean":float(np.mean(y)),"Qsim_mean":float(np.mean(p)),"bias":float(np.mean(p-y)),"RMSE":float(np.sqrt(np.mean((p-y)**2))),"MSE":float(np.mean((p-y)**2)),"reason":"OK"}
def history(root):
 result={}
 for line in (root/"SHA256SUMS.txt").read_text().splitlines():
  h,name=line.split("  ",1);assert sha(root/name)==h,name;result[name]=h
 return result
def main():
 assert jl(P/"P2_TEST_RESULTS.json")["success"]
 pro=jl(P/"P2_PROTOCOL.json");sel=jl(P/"P2_NEW_BASINS_FROZEN.json");meta=jl(P/"source/SNAPSHOT.json");freeze=jl(P/"evidence/PREFIT_FREEZE.json")
 for n,h in freeze.items():assert sha(P/n)==h,n
 hpin=history(P1)
 rows=rr(P/"source/monthly_labels_features.csv")
 for r in rows:
  for k in ("year","month","gauge_id"):r[k]=int(r[k])
  for k in ("Q_m3s","P","T","L1","S","M"):r[k]=float(r[k])
 src.register(rows,meta["snapshot_id"])
 code={str(p):sha(p) for root in [P/"P2_MODEL_CODE",R/"code/vendor_public"] for p in sorted(root.rglob("*.py"))}
 runid=LABEL+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+digest({"code":code,"freeze":freeze})[:12]
 stage=P/"runs"/(".staging-"+runid);stage.mkdir()
 attempt={"attempt_id":runid,"UTC":datetime.now(timezone.utc).isoformat(),"label":LABEL,"code_hash":digest(code),"protocol_hash":digest(pro),"snapshot_id":meta["snapshot_id"]}
 def log(status,**kw):
  with (P/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({**attempt,"status":status,**kw})+"\n")
 log("STARTED")
 predictions=[];overall=[];yearly=[];seasons=[];flow=[];comparisons=[];details={};parameters=[];foldrecs=[];responses=[];support=[];alphas=[];baseline_parity=[];skips=[]
 oldrun=P1/"runs/PUBLIC_DATA_EXPLORATORY_P1-20261026T015059Z-7f0aabd5cf43"
 oldpred={(r["experiment"],int(r["gauge_id"]),r["sample_id"]):float(r["Qsim_raw_m3s"]) for r in rr(oldrun/"OOF_PREDICTIONS.csv") if r["model_id"]=="C0+PT"}
 start=time.monotonic()
 try:
  for cohort in ("DEVELOPMENT_9","EXTERNAL_FROZEN_NEW"):
   for scheme in [s for s in sel["schemes"] if s["cohort"]==cohort]:
    g,ex,years=scheme["gauge_id"],scheme["scenario"],scheme["years"];group=sel["all_grouping"][str(g)]
    if not scheme["eligible"]:skips.append({"gauge_id":g,"scenario":ex,"reason":"LESS_THAN6_COMPLETE_SUPPORTED_YEARS","actual":len(years)});continue
    sub=sorted([r for r in rows if r["gauge_id"]==g and r["year"] in years],key=lambda r:(r["year"],r["month"]))
    assert len(sub)==12*len(years)
    x=Inputs(tuple(r["sample_id"] for r in sub),np.array([r["year"] for r in sub]),np.array([r["month"] for r in sub]),{k:np.array([r[k] for r in sub]) for k in ("P","T","L1","S","M")},meta["snapshot_id"])
    ledger=[{"sample_id":r["sample_id"],"dataset_id":src.DATASET,"data_snapshot_id":meta["snapshot_id"],"station_id":r["station_id"],"year":r["year"],"month":r["month"],"down_public_complete_usable":True,"meteorology_valid":True} for r in sub]
    folds=make_folds(ledger,GROUP_B,scheme="public_complete",validation="LOYO");assert len(folds)==len(years)
    loc=[];pdict={m:{} for m in pro["models"]}
    for f in folds:
     FIT_CONTEXT.update(cohort=cohort,scenario=ex,gauge_id=g,outer_held_year=f.test_years[0])
     tx,vx=x.take(f.train_ids),x.take(f.test_ids)
     assert not(set(tx.ids)&set(vx.ids)) and not(set(tx.years)&set(vx.years))
     src.set_outer_train(f.train_ids);ty=src.read_training(tx.ids);q20,q80=np.quantile(ty,[.2,.8])
     foldrecs.append({"cohort":cohort,"scenario":ex,"gauge_id":g,**f.record()})
     for mid in pro["models"]:
      model=MonthlyWeatherRidge(mid).fit(tx,ty);pp=model.predict(vx);depart=model.constant_departures(vx);tempresponse=model.response_current_T_plus1(vx)
      assert np.isfinite(pp).all() and not tx.synthetic
      record=model.record();parameters.append({"cohort":cohort,"scenario":ex,"gauge_id":g,"fold_id":f.fold_id,"held_year":f.test_years[0],"record":record})
      alphas.append({"cohort":cohort,"scenario":ex,"gauge_id":g,"model_id":mid,"held_year":f.test_years[0],**model.selection})
      for z,name in enumerate(model.fields):
       responses.append({"cohort":cohort,"scenario":ex,"gauge_id":g,"model_id":mid,"held_year":f.test_years[0],"feature":name,"beta_per_train_month_SD_m3s":float(model.beta[z]),"nonzero_train_rows":int(np.count_nonzero(tx.values[name])),"constant_calendar_months":int(model.constant[:,z].sum()),"conditional_not_causal":True})
      for z,k in enumerate(vx.ids):
       raw=float(pp[z]);assert k not in pdict[mid];pdict[mid][k]=raw
       loc.append({"experiment_label":LABEL,"cohort":cohort,"macro_group":group["macro"],"region":group["region"],"scenario":ex,"gauge_id":g,"sample_id":k,"year":int(vx.years[z]),"month":int(vx.months[z]),"fold_id":f.fold_id,"model_id":mid,"Qobs_m3s":None,"Qsim_raw_m3s":raw,"Qsim_nonnegative_m3s":max(raw,0),"train_Q_month_mean_m3s":float(model.climate[vx.months[z]-1]),"train_Q20":float(q20),"train_Q80":float(q80),"current_T_plus1_conditional_response_m3s":float(tempresponse[z]),"unseen_constant_feature_departures":"|".join(name for j,name in enumerate(model.fields) if depart[z,j]),"unit":"m3/s"})
      for name in model.fields:
       support.append({"cohort":cohort,"scenario":ex,"gauge_id":g,"model_id":mid,"held_year":f.test_years[0],"feature":name,"n_train":len(tx.ids),"nonzero_train_rows":int(np.count_nonzero(tx.values[name])),"train_min":float(np.min(tx.values[name])),"train_max":float(np.max(tx.values[name])),"constant_months":int(model.constant[:,model.fields.index(name)].sum()),"test_departure_from_constant_train_rows":int(depart[:,model.fields.index(name)].sum()),"support_status":"ZERO_INFORMATION_ALL_MONTHS" if model.constant[:,model.fields.index(name)].all() else "PARTIAL_CALENDAR_MONTH_SUPPORT" if model.constant[:,model.fields.index(name)].any() else "FULL_VARIATION"})
    assert len(loc)==len(sub)*3
    commitment=digest(loc)
    for row in loc:row["Qobs_m3s"]=src._registered[row["sample_id"]]["Q_m3s"]
    predictions.extend(loc)
    ids=sorted(x.ids);yy=np.array([src._registered[i]["year"] for i in ids]);mm=np.array([src._registered[i]["month"] for i in ids])
    raw={m:np.array([pdict[m][i] for i in ids]) for m in pro["models"]}
    baseline=raw["C0+PT"]
    for mid,pred in raw.items():
     y,m=met(ids,pred);_,clipped=met(ids,np.maximum(pred,0))
     bmse=float(np.mean((y-baseline)**2));skill=1-float(np.mean((y-pred)**2))/bmse if bmse>1e-24 else None
     base={i:r for i,r in ((r["sample_id"],r) for r in loc if r["model_id"]==mid)}
     peryear=[]
     for year in years:
      ix=np.flatnonzero(yy==year);_,ym=met([ids[i] for i in ix],pred[ix]);peryear.append(ym["MSE"])
      yearly.append({"cohort":cohort,"macro_group":group["macro"],"region":group["region"],"scenario":ex,"gauge_id":g,"model_id":mid,"year":year,"n_months":len(ix),**ym})
     overall.append({"label":LABEL,"cohort":cohort,"macro_group":group["macro"],"region":group["region"],"scenario":ex,"gauge_id":g,"model_id":mid,"n_years":len(years),"n_months":len(ids),**m,"MSE_skill_vs_C0PT":skill,"equal_year_MSE":float(np.mean(peryear)),"negative_raw_predictions":int(np.sum(pred<0)),"nonnegative_NSE":clipped["NSE"],"nonnegative_KGE":clipped["KGE"],"nonnegative_MSE":clipped["MSE"],"OOF_commitment":commitment})
     for period,months in [(f"M{mo:02d}",[mo]) for mo in range(1,13)]+list(pro["statistics"]["seasons"].items()):
      ix=np.isin(mm,months);seasons.append({"cohort":cohort,"macro_group":group["macro"],"region":group["region"],"scenario":ex,"gauge_id":g,"model_id":mid,"period":period,**stat(y[ix],pred[ix])})
     low=np.array([float(base[i]["train_Q20"]) for i in ids]);high=np.array([float(base[i]["train_Q80"]) for i in ids])
     for category,ix in [("LOW_Q_LE_TRAIN_Q20",y<=low),("HIGH_Q_GE_TRAIN_Q80",y>=high),("MIDDLE",(y>low)&(y<high))]:
      flow.append({"cohort":cohort,"macro_group":group["macro"],"scenario":ex,"gauge_id":g,"model_id":mid,"flow_bin":category,**stat(y[ix],pred[ix])})
    for mid in ("P2-L1","P2-SNOW"):
     d=paired_year_comparison(y,raw[mid],baseline,yy,pro["seed"]);details[f"{cohort}|{ex}|{g}|{mid}"]=d
     vals=np.array(d["year_MSE_improvement"]);total=float(vals.sum());largest=int(np.argmax(vals))
     comparisons.append({"cohort":cohort,"macro_group":group["macro"],"region":group["region"],"scenario":ex,"gauge_id":g,"candidate":mid,"benchmark":"C0+PT","n_years":len(years),"MSE_skill":1-float(np.mean((y-raw[mid])**2))/float(np.mean((y-baseline)**2)),"mean_year_MSE_improvement":d["mean_year_improvement"]["value"],"fraction_years_improved":d["fraction_years_improved"],"jackknife_all_deletions_positive":d["jackknife"]["all_deletions_positive"],"jackknife_min":min(d["jackknife"]["leave_one_year_out_estimates"]),"bootstrap95_low":d["year_bootstrap"]["percentile_95_interval"][0],"bootstrap95_high":d["year_bootstrap"]["percentile_95_interval"][1],"largest_improvement_year":d["years"][largest],"largest_year_signed_share":float(vals[largest]/total) if total>0 else None,"unadjusted_descriptive_signflip_p":d["exact_sign_flip"]["p"]["value"],"inference":"DESCRIPTIVE_DEPENDENT_YEARS_AND_BASINS"})
    if cohort=="DEVELOPMENT_9" and scheme["n_months"]==120:
     maxdiff=max(abs(baseline[z]-oldpred[ex,g,i]) for z,i in enumerate(ids));assert maxdiff<1e-9*max(1,float(np.max(abs(baseline))))
     baseline_parity.append({"scenario":ex,"gauge_id":g,"n_months":len(ids),"C0PT_refitted_here":True,"max_abs_prediction_difference_vs_P1":maxdiff,"reason":"same common support; independently refitted baseline, no imported scores"})
    print(json.dumps({"completed":f"{cohort}|{ex}|ID{g}","fits":len(FIT_EVENTS),"elapsed_s":round(time.monotonic()-start,1),"skills":{r["candidate"]:r["MSE_skill"] for r in comparisons[-2:]}}),flush=True)
   # Freeze cohort outcome before moving to next cohort; no protocol changes are allowed.
   jw(stage/("COHORT_"+cohort+"_PREDICTION_COMMITMENT.json"),{"cohort":cohort,"prediction_count":sum(r["cohort"]==cohort for r in predictions),"prediction_hash":digest([r for r in predictions if r["cohort"]==cohort]),"protocol_hash":digest(pro)})
  for name,data in [("P2_OOF_PREDICTIONS.csv",predictions),("P2_OVERALL_METRICS.csv",overall),("P2_YEARLY_METRICS.csv",yearly),("P2_MODEL_COMPARISON.csv",comparisons),("P2_SEASONAL_DIAGNOSTICS.csv",seasons),("P2_FLOW_DIAGNOSTICS.csv",flow),("P2_INPUT_RESPONSE.csv",responses),("P2_FOLD_FEATURE_SUPPORT.csv",support),("P2_ALPHA_SELECTION.csv",alphas),("P1_BASELINE_REFIT_PARITY.csv",baseline_parity)]:cw(stage/name,data)
  for name,data in [("protocol.json",pro),("frozen_basins.json",sel),("source_snapshot.json",meta),("folds.json",foldrecs),("model_parameters.json",parameters),("fit_events.json",FIT_EVENTS),("comparison_details.json",details),("code_hashes.json",code),("P1_HISTORY_PINS.json",hpin),("skipped_schemes.json",skips)]:jw(stage/name,data)
  counts={mid:{lev:sum(e["model_id"]==mid and e["level"]==lev and e["status"]=="COMPLETED" for e in FIT_EVENTS) for lev in ["outer","inner"]} for mid in pro["models"]}
  assert all(e["status"]=="COMPLETED" for e in FIT_EVENTS)
  manifest={"run_id":runid,"label":LABEL,"synthetic":False,"snapshot_id":meta["snapshot_id"],"source_DOI":pro["source_DOI"],"protocol_hash":digest(pro),"protocol_sha256":sha(P/"P2_PROTOCOL.json"),"code_hash":digest(code),"folds_hash":digest(foldrecs),"new_basins_sha256":sha(P/"P2_NEW_BASINS_FROZEN.json"),"frozen_inputs":freeze,"outer_folds":len(foldrecs),"fold_model_records":len(parameters),"actual_fit_counts":counts,"actual_fit_calls":len(FIT_EVENTS),"OOF_records":len(predictions),"unique_labeled_source_months":len(rows),"failed_fits":0,"skipped_schemes":len(skips),"cohorts":["DEVELOPMENT_9","EXTERNAL_FROZEN_NEW"],"new_basin_ids":sel["new_basin_ids"],"P1_refits":False,"P2_baseline_refitted":True,"teacher_Q_access":False,"SYRDARYA_REAL_EXPERIMENT":False,"environment":{"python":platform.python_version(),"numpy":np.__version__,"executable":sys.executable,"CPU_threads":1},"elapsed_s":time.monotonic()-start,"created_UTC":datetime.now(timezone.utc).isoformat()}
  jw(stage/"manifest.json",manifest)
  with (stage/"SHA256SUMS.txt").open("x",encoding="utf-8") as f:
   for p in sorted(stage.iterdir()):f.write(sha(p)+"  "+p.name+"\n") if p.is_file() and p.name!="SHA256SUMS.txt" else None
  dest=P/"runs"/runid;stage.rename(dest);log("COMPLETED",run_dir=str(dest),fit_counts=counts,OOF=len(predictions))
  print(json.dumps({"status":"COMPLETED","run_dir":str(dest),**manifest}),flush=True)
 except Exception as e:
  jw(stage/"FAILURE.json",{"error":repr(e),"fit_events":FIT_EVENTS});log("FAILED",error=repr(e),staging=str(stage),completed_fit_calls=sum(e["status"]=="COMPLETED" for e in FIT_EVENTS));raise
if __name__=="__main__":main()

