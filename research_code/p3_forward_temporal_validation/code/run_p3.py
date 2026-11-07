"""P3 fixed-model temporal experiment: seal ALL Q-free predictions before opening test Q."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):os.environ[k]="1"
import bootstrap,csv,json,hashlib,platform,time,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import public_runtime as src
from models import Inputs,MonthlyWeatherRidge,FIT_CONTEXT,FIT_EVENTS,ALPHAS
from vhs_sci.contracts import digest,ids_hash
from vhs_sci.evaluate import metric_bundle,paired_year_comparison
P=Path(__file__).parents[1];R=P.parent;P2=R/"p2_antecedent_snow_features"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jw(p,x):
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def seal(root):
 with (root/"SHA256SUMS.txt").open("x",encoding="utf-8") as f:
  for p in sorted(root.rglob("*")):
   if p.is_file() and p!=root/"SHA256SUMS.txt":f.write(sha(p)+"  "+p.relative_to(root).as_posix()+"\n")
def metrics(ids,p):
 y=src.permit_metric(ids,p);m=metric_bundle(y,p,synthetic=False)
 return y,{k:v["value"] for k,v in m.items()}|{"NA_reasons":"|".join(k+":"+v["reason_code"] for k,v in m.items() if v["status"]=="N/A")}
def diagnostic(y,p):
 if len(y)==0:return {"n_months":0,"Qobs_mean":None,"Qsim_mean":None,"bias":None,"MAE":None,"RMSE":None,"MSE":None,"NA_reasons":"NO_ADMISSIBLE_TEST_MONTHS"}
 return {"n_months":len(y),"Qobs_mean":float(np.mean(y)),"Qsim_mean":float(np.mean(p)),"bias":float(np.mean(p-y)),"MAE":float(np.mean(abs(p-y))),"RMSE":float(np.sqrt(np.mean((p-y)**2))),"MSE":float(np.mean((p-y)**2)),"NA_reasons":""}
def load_feature(r):
 for k in ("year","month","gauge_id"):r[k]=int(r[k])
 for k in ("P","T","L1"):r[k]=float(r[k])
 return r
def main():
 assert jl(P/"evidence/P3_BOUNDARY_TESTS.json")["success"]
 pro=jl(P/"P3_PROTOCOL.json");split=jl(P/"P3_SPLIT_FROZEN.json");snap=jl(P/"source/SNAPSHOT.json");freeze=jl(P/"evidence/PREFIT_FREEZE.json")
 assert list(ALPHAS)==pro["alpha"] and pro["models"]==["C0+PT","P2-L1"]
 for n,h in freeze.items():
  if n!="source/test_labels_SCORE_ONLY.csv":assert sha(P/n)==h,n
 assert sha(Path(pro["frozen_model_file"]))==pro["frozen_model_sha256"]
 rows=[load_feature(r) for r in rr(P/"source/features.csv")]
 labels=rr(P/"source/train_labels.csv")
 for r in labels:
  for k in ("year","month","gauge_id"):r[k]=int(r[k])
  r["Q_m3s"]=float(r["Q_m3s"])
 src.register(rows,labels,snap["snapshot_id"]);assert not src._scoring_released and not src._score_labels
 model_path=P2/"P2_MODEL_CODE/models.py"
 codes={str(p):sha(p) for p in sorted((P/"code").glob("*.py"))}|{str(model_path):sha(model_path)}|{str(p):sha(p) for p in sorted((R/"code/vendor_public/vhs_sci").rglob("*.py"))}
 runid=pro["label"]+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+digest({"code":codes,"freeze":freeze})[:12]
 stage=P/"runs"/(".staging-"+runid);stage.mkdir();bundle=stage/"prediction_bundle";bundle.mkdir()
 attempt={"attempt_id":runid,"label":pro["label"],"task":pro["task"],"UTC":datetime.now(timezone.utc).isoformat(),"protocol_hash":digest(pro),"code_hash":digest(codes),"snapshot_id":snap["snapshot_id"]}
 def log(status,**kw):
  with (P/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({**attempt,"status":status,**kw})+"\n")
 log("STARTED")
 allpred=[];params=[];folds=[];extras=[];model_support=[];start=time.monotonic()
 try:
  for s in split["splits"]:
   if not s["eligible"]:continue
   g=s["gauge_id"];sub=sorted([r for r in rows if r["gauge_id"]==g],key=lambda r:(r["year"],r["month"]))
   xx=Inputs(tuple(r["sample_id"] for r in sub),np.array([r["year"] for r in sub]),np.array([r["month"] for r in sub]),{k:np.array([r[k] for r in sub]) for k in ("P","T","L1")},snap["snapshot_id"])
   tx,vx=xx.take(s["train_ids"]),xx.take(s["test_ids"]);assert max(tx.years)<min(vx.years) and not(set(tx.ids)&set(vx.ids))
   src.set_outer_train(tx.ids);ty=src.read_training(tx.ids);q20,q80=np.quantile(ty,[.2,.8])
   fold={"fold_id":f"FORWARD_ID{g}_2005_2014","gauge_id":g,"dataset_id":src.DATASET,"snapshot_id":snap["snapshot_id"],"train_ids":list(tx.ids),"test_ids":list(vx.ids),"train_ids_hash":ids_hash(tx.ids),"test_ids_hash":ids_hash(vx.ids),"train_years":sorted(set(tx.years.tolist())),"test_years":sorted(set(vx.years.tolist())),"n_train":len(tx.ids),"n_test":len(vx.ids),"train_max_date":max(tx.ids)[-7:],"test_min_date":min(vx.ids)[-7:],"status":s["status"]};folds.append(fold)
   FIT_CONTEXT.update(gauge_id=g,outer_split=fold["fold_id"],task=pro["task"])
   for mid in pro["models"]:
    model=MonthlyWeatherRidge(mid).fit(tx,ty);pred=model.predict(vx);assert np.isfinite(pred).all()
    params.append({"gauge_id":g,"model_id":mid,"fold_id":fold["fold_id"],"n_train":len(tx.ids),"n_test":len(vx.ids),"record":model.record()})
    ztest=model.transform(vx);depart=model.constant_departures(vx)
    for z,name in enumerate(model.fields):
     model_support.append({"gauge_id":g,"model_id":mid,"feature":name,"beta_per_monthly_train_SD":float(model.beta[z]),"constant_months":int(model.constant[:,z].sum()),"test_constant_departures":int(depart[:,z].sum()),"max_abs_test_standardized_anomaly":float(np.max(abs(ztest[:,z])))})
    for j,i in enumerate(vx.ids):
     yy,mo=int(vx.years[j]),int(vx.months[j])
     allpred.append({"label":pro["label"],"task":pro["task"],"gauge_id":g,"cohort":s["cohort"],"macro_group":s["macro"],"region":s["region"],"support_status":s["status"],"sample_id":i,"year":yy,"month":mo,"fold_id":fold["fold_id"],"model_id":mid,"Qsim_raw_m3s":float(pred[j]),"Qsim_nonnegative_m3s":float(max(pred[j],0)),"train_Q_month_mean_m3s":float(model.climate[mo-1]),"train_Q20":float(q20),"train_Q80":float(q80),"unseen_constant_departures":"|".join(name for z,name in enumerate(model.fields) if depart[j,z]),"unit":"m3/s"})
     for z,name in enumerate(model.fields):
      vals=tx.values[name][tx.months==mo];raw=float(vx.values[name][j])
      extras.append({"gauge_id":g,"sample_id":i,"year":yy,"month":mo,"model_id":mid,"feature":name,"raw_test_value":raw,"train_month_mean":float(model.mu[mo-1,z]),"train_month_sample_std":float(model.sd[mo-1,z]),"train_month_min":float(min(vals)),"train_month_max":float(max(vals)),"train_constant":bool(model.constant[mo-1,z]),"standardized_test_anomaly":float(ztest[j,z]),"outside_train_month_range":raw<min(vals) or raw>max(vals),"coefficient_m3s_per_train_SD":float(model.beta[z]),"contribution_m3s":float(ztest[j,z]*model.beta[z])})
   assert not src._score_labels and not src._scoring_released
   print(json.dumps({"stage":"PREDICTED_NO_TEST_Q","gauge_id":g,"n_train":len(tx.ids),"n_test":len(vx.ids),"fit_calls":len(FIT_EVENTS),"elapsed_s":round(time.monotonic()-start,1)}),flush=True)
  expected=2*sum(s["test_months"] for s in split["splits"] if s["eligible"]);assert len(allpred)==expected
  assert len(set((r["sample_id"],r["model_id"]) for r in allpred))==len(allpred)
  cw(bundle/"TEST_PREDICTIONS_WITHOUT_QOBS.csv",allpred);jw(bundle/"model_parameters.json",params);jw(bundle/"folds.json",folds);jw(bundle/"fit_events.json",FIT_EVENTS);cw(bundle/"FEATURE_EXTRAPOLATION.csv",extras);cw(bundle/"MODEL_SUPPORT.csv",model_support)
  jw(bundle/"COMMITMENT.json",{"run_id":runid,"all_predictions_complete":True,"n_predictions":len(allpred),"n_outer_fits":len(params),"test_Q_loaded":False,"prediction_values_hash":digest(allpred),"protocol_sha256":sha(P/"P3_PROTOCOL.json"),"code_hash":digest(codes),"snapshot_id":snap["snapshot_id"],"created_UTC":datetime.now(timezone.utc).isoformat()})
  seal(bundle);log("ALL_PREDICTIONS_SEALED_NO_TEST_Q",n_predictions=len(allpred),bundle_seal_sha256=sha(bundle/"SHA256SUMS.txt"))
  # FIRST numerical test-label load in this process occurs here, after global commit.
  receipt=src.release_scoring(bundle);jw(stage/"TEST_Q_RELEASE_RECEIPT.json",receipt);log("TEST_LABELS_RELEASED_FOR_FINAL_SCORING",**receipt)
  predictions=[{**r,"Qobs_m3s":src._score_labels[r["sample_id"]]} for r in allpred]
  overall=[];yearly=[];seasonal=[];flow=[];failure=[];details={};concentration=[];drift=[]
  for s in split["splits"]:
   if not s["eligible"]:continue
   g=s["gauge_id"];ps=[r for r in predictions if r["gauge_id"]==g];index={m:{r["sample_id"]:r for r in ps if r["model_id"]==m} for m in pro["models"]}
   ids=sorted(s["test_ids"]);years=np.array([index["C0+PT"][i]["year"] for i in ids]);months=np.array([index["C0+PT"][i]["month"] for i in ids]);raw={m:np.array([index[m][i]["Qsim_raw_m3s"] for i in ids]) for m in pro["models"]}
   trainq=np.array([src._training_labels[i] for i in s["train_ids"]]);n_test_years=len(set(years.tolist()))
   station_metrics={}
   for mid,pred in raw.items():
    y,m=metrics(ids,pred);_,clipped=metrics(ids,np.maximum(pred,0));station_metrics[mid]=m
    annual=[]
    for year in range(2005,2015):
     ix=np.flatnonzero(years==year)
     if len(ix):
      _,ym=metrics([ids[j] for j in ix],pred[ix]);annual.append(ym["MSE"])
     else:ym={k:None for k in ["MAE","RMSE","MSE","NSE","PBIAS","KGE_r","KGE_alpha","KGE_beta","KGE"]}|{"NA_reasons":"NO_ADMISSIBLE_TEST_MONTHS"}
     yearly.append({"gauge_id":g,"cohort":s["cohort"],"macro_group":s["macro"],"support_status":s["status"],"model_id":mid,"year":year,"n_months":len(ix),**ym})
    denom=float(np.mean((y-raw["C0+PT"])**2));skill=1-float(np.mean((y-pred)**2))/denom if denom>1e-24 else None
    overall.append({"label":pro["label"],"task":pro["task"],"gauge_id":g,"cohort":s["cohort"],"macro_group":s["macro"],"region":s["region"],"support_status":s["status"],"model_id":mid,"n_train_months":len(s["train_ids"]),"n_test_months":len(ids),"n_test_years":n_test_years,**m,"MSE_skill_vs_C0PT":skill,"skill_NA_reason":"" if skill is not None else "PERFECT_OR_ZERO_LOSS_BENCHMARK","equal_year_MSE":float(np.mean(annual)),"negative_raw_predictions":int(np.sum(pred<0)),"nonnegative_NSE":clipped["NSE"],"nonnegative_KGE":clipped["KGE"],"nonnegative_MSE":clipped["MSE"],"prediction_bundle_sha256":sha(bundle/"SHA256SUMS.txt")})
    for period,ms in [(f"M{mo:02d}",[mo]) for mo in range(1,13)]+list(pro["diagnostics"]["seasons"].items()):
     ix=np.isin(months,ms);seasonal.append({"gauge_id":g,"model_id":mid,"period":period,**diagnostic(y[ix],pred[ix])})
    q20=np.array([index[mid][i]["train_Q20"] for i in ids]);q80=np.array([index[mid][i]["train_Q80"] for i in ids])
    for category,ix in [("LOW_LE_TRAIN_Q20",y<=q20),("HIGH_GE_TRAIN_Q80",y>=q80),("MID",(y>q20)&(y<q80))]:flow.append({"gauge_id":g,"model_id":mid,"flow_bin":category,**diagnostic(y[ix],pred[ix])})
    errors=(y-pred)**2;worst=int(np.argmax(errors));yearSSE={int(year):float(np.sum(errors[years==year])) for year in sorted(set(years.tolist()))};worstyear=max(yearSSE,key=yearSSE.get)
    concentration.append({"gauge_id":g,"model_id":mid,"worst_month":ids[worst][-7:],"worst_month_Qobs_m3s":float(y[worst]),"worst_month_Qsim_m3s":float(pred[worst]),"worst_month_squared_error":float(errors[worst]),"worst_month_share_of_total_SSE":float(errors[worst]/errors.sum()) if errors.sum()>0 else None,"largest_SSE_year":worstyear,"largest_year_share_of_total_SSE":yearSSE[worstyear]/sum(yearSSE.values()) if sum(yearSSE.values())>0 else None})
   y=src.permit_metric(ids,raw["P2-L1"]);d=paired_year_comparison(y,raw["P2-L1"],raw["C0+PT"],years,pro["seed"]);details[str(g)]=d
   for year in range(2005,2015):
    a=next(r for r in yearly if r["gauge_id"]==g and r["model_id"]=="C0+PT" and r["year"]==year);b=next(r for r in yearly if r["gauge_id"]==g and r["model_id"]=="P2-L1" and r["year"]==year)
    for row in [a,b]:
     denom=a["MSE"];row["MSE_skill_vs_C0PT"]=1-row["MSE"]/denom if row["MSE"] is not None and denom is not None and denom>1e-24 else None;row["skill_NA_reason"]="" if row["MSE_skill_vs_C0PT"] is not None else "NO_TEST_MONTHS_OR_ZERO_BASELINE"
   for period,ms in pro["diagnostics"]["seasons"].items():
    a=next(r for r in seasonal if r["gauge_id"]==g and r["model_id"]=="C0+PT" and r["period"]==period);b=next(r for r in seasonal if r["gauge_id"]==g and r["model_id"]=="P2-L1" and r["period"]==period)
    for row in [a,b]:row["MSE_skill_vs_C0PT"]=1-row["MSE"]/a["MSE"] if row["MSE"] is not None and a["MSE"] is not None and a["MSE"]>1e-24 else None
   for mo in range(1,13):
    ix=months==mo;trainids=[i for i in s["train_ids"] if int(i[-2:])==mo];trainvals=np.array([src._training_labels[i] for i in trainids]);testvals=y[ix]
    drift.append({"gauge_id":g,"month":mo,"n_train":len(trainvals),"n_test":len(testvals),"train_Qmean":float(trainvals.mean()),"test_Qmean":float(testvals.mean()) if len(testvals) else None,"Qmean_change":float(testvals.mean()-trainvals.mean()) if len(testvals) else None,"test_mean_minus_train_in_train_Qsd":float((testvals.mean()-trainvals.mean())/trainvals.std(ddof=1)) if len(testvals) and trainvals.std(ddof=1)>0 else None,"scoring_only_not_a_feature":True})
   skill=1-station_metrics["P2-L1"]["MSE"]/station_metrics["C0+PT"]["MSE"];delta=(raw["C0+PT"]-y)**2-(raw["P2-L1"]-y)**2;worstdiff=int(np.argmin(delta));worstyear=min(d["years"],key=lambda year:d["year_MSE_improvement"][d["years"].index(year)])
   worstrec=next(r for r in concentration if r["gauge_id"]==g and r["model_id"]=="P2-L1")
   failure.append({"gauge_id":g,"cohort":s["cohort"],"macro_group":s["macro"],"region":s["region"],"support_status":s["status"],"n_test_months":len(ids),"MSE_skill_L1":skill,"station_negative_skill":skill<0,"fraction_years_improved":d["fraction_years_improved"],"jackknife_all_year_deletions_positive":d["jackknife"]["all_deletions_positive"],"year_bootstrap95_low":d["year_bootstrap"]["percentile_95_interval"][0],"year_bootstrap95_high":d["year_bootstrap"]["percentile_95_interval"][1],"worst_increment_year":worstyear,"worst_increment_year_MSE_change":-min(d["year_MSE_improvement"]),"most_harmful_L1_month":ids[worstdiff][-7:],"most_harmful_L1_month_extra_SSE":-float(delta[worstdiff]),"worst_L1_error_month":worstrec["worst_month"],"worst_L1_error_Qobs":worstrec["worst_month_Qobs_m3s"],"worst_L1_error_Qsim":worstrec["worst_month_Qsim_m3s"],"worst_L1_error_month_share_SSE":worstrec["worst_month_share_of_total_SSE"],"reason":"NEGATIVE_TEMPORAL_INCREMENT_RETAINED" if skill<0 else "POSITIVE_MEAN_DOES_NOT_IMPLY_ALL_YEARS_OR_SEASONS"})
  # Add monthly/seasonal and flow skills consistently for every row, including empty subsets.
  for arr,key in [(seasonal,"period"),(flow,"flow_bin")]:
   look={(r["gauge_id"],r["model_id"],r[key]):r for r in arr}
   for r in arr:
    den=look[r["gauge_id"],"C0+PT",r[key]]["MSE"];r["MSE_skill_vs_C0PT"]=1-r["MSE"]/den if r["MSE"] is not None and den is not None and den>1e-24 else None
    r["skill_NA_reason"]="" if r["MSE_skill_vs_C0PT"] is not None else "EMPTY_OR_ZERO_BASELINE"
  for name,data in [("P3_TEST_PREDICTIONS.csv",predictions),("P3_OVERALL_METRICS.csv",overall),("P3_YEARLY_METRICS.csv",yearly),("P3_SEASONAL_METRICS.csv",seasonal),("P3_FLOW_METRICS.csv",flow),("P3_FAILURE_ANALYSIS.csv",failure),("P3_ERROR_CONCENTRATION.csv",concentration),("P3_MONTHLY_Q_DRIFT.csv",drift)]:cw(stage/name,data)
  for name,data in [("P3_PROTOCOL.json",pro),("P3_SPLIT_FROZEN.json",split),("source_snapshot.json",snap),("code_hashes.json",codes),("data_access_log.json",src.ACCESS_LOG),("year_comparison_details.json",details)]:jw(stage/name,data)
  counts={m:{lev:sum(e["model_id"]==m and e["level"]==lev and e["status"]=="COMPLETED" for e in FIT_EVENTS) for lev in ["outer","inner"]} for m in pro["models"]}
  assert all(e["status"]=="COMPLETED" and e["model_id"] in pro["models"] for e in FIT_EVENTS)
  manifest={**attempt,"run_id":runid,"synthetic":False,"status":"COMPLETED","source_DOI":pro["DOI"],"train_window":["1981-01","2004-12"],"test_window":["2005-01","2014-12"],"eligible_stations":len(split["eligible_gauges"]),"complete120_stations":len(split["full120_gauges"]),"partial_stations":split["partial_test_gauges"],"train_months":sum(s["train_months"] for s in split["splits"] if s["eligible"]),"test_months":sum(s["test_months"] for s in split["splits"] if s["eligible"]),"test_predictions":len(allpred),"fit_counts":counts,"actual_fit_calls":len(FIT_EVENTS),"test_predictions_sealed_before_test_Q":True,"prediction_bundle_sha256":sha(bundle/"SHA256SUMS.txt"),"frozen_inputs":freeze,"split_hash":sha(P/"P3_SPLIT_FROZEN.json"),"P2_model_sha256":sha(Path(pro["frozen_model_file"])),"test_label_release_receipt":receipt,"environment":{"python":platform.python_version(),"numpy":np.__version__,"executable":sys.executable,"CPU_threads":1},"failed_fits":0,"SYRDARYA_access":False,"P4_executed":False,"elapsed_s":time.monotonic()-start,"created_UTC":datetime.now(timezone.utc).isoformat()}
  jw(stage/"P3_RUN_MANIFEST.json",manifest);seal(stage)
  dest=P/"runs"/runid;stage.rename(dest);log("COMPLETED",run_dir=str(dest),fit_counts=counts,n_predictions=len(allpred))
  print(json.dumps({"run_dir":str(dest),**manifest}),flush=True)
 except Exception as e:
  jw(stage/"FAILURE.json",{"error":repr(e),"fit_events":FIT_EVENTS});log("FAILED",error=repr(e),staging=str(stage),fits_completed=sum(e["status"]=="COMPLETED" for e in FIT_EVENTS));raise
if __name__=="__main__":main()

