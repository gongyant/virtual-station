"""Real public-gauge C0/E3n LOYO with unchanged S2 numerical implementations."""
import os
for key in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):os.environ[key]="1"
import csv,hashlib,json,sys,time,uuid,platform
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/"code/vendor_public"));sys.path.insert(0,str(R/"code"))
import public_runtime as source
from vhs_sci.contracts import SampleKey,FeatureBatch,TrainingBatch,GROUP_B,digest,ids_hash
from vhs_sci.models import baselines as models
from vhs_sci.folds import make_folds
from vhs_sci.invariants import enforce_fold
from vhs_sci.evaluate import metric_bundle,same_sample_skill,paired_year_comparison
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def writejson(path,obj):
 with path.open("x",encoding="utf-8") as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def writecsv(path,rows):
 with path.open("x",encoding="utf-8",newline="") as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def main():
 protocol=json.loads((R/"protocol.json").read_text(encoding="utf-8"))
 meta=json.loads((R/"source/MONTHLY_SNAPSHOT.json").read_text(encoding="utf-8"))
 assert sha(R/"source/monthly_admitted.csv")==meta["monthly_csv_sha256"]
 with (R/"source/monthly_admitted.csv").open(encoding="utf-8",newline="") as f:rows=list(csv.DictReader(f))
 for r in rows:
  for k in ("year","month","gauge_id","expected_days","Q_valid_days","P_valid_days","T_valid_days"):r[k]=int(r[k])
  for k in ("Q_m3s","P_mm","T_C"):r[k]=float(r[k])
  r["complete"]=r["complete"]=="True"
 source.register(rows,meta["snapshot_id"])
 codepins={p.relative_to(R).as_posix():sha(p) for p in sorted((R/"code").rglob("*.py"))}
 codehash=digest(codepins);protocolhash=digest(protocol)
 runid="PUBLIC_DATA_REAL_EXPERIMENT-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+digest({"snapshot":meta["snapshot_id"],"protocol":protocolhash,"code":codehash})[:12]
 stage=R/"runs"/(".staging-"+runid);stage.mkdir()
 attempt={"attempt_id":runid,"status":"STARTED","UTC":datetime.now(timezone.utc).isoformat(),"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","synthetic":False,"code_hash":codehash,"protocol_hash":protocolhash,"snapshot_id":meta["snapshot_id"]}
 with (R/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps(attempt)+"\n")
 fit_events=[];context={}
 def wrap_fit(original):
  def tracked(self,train):
   level="outer" if set(train.features.ids)==source._train_ids else "inner"
   event={"experiment":context["experiment"],"gauge_id":context["gauge_id"],"held_year":context["held_year"],"model_id":self.model_id,"level":level,"n_train":len(train.features.keys),"status":"STARTED"}
   fit_events.append(event)
   try:result=original(self,train)
   except Exception as e:event.update(status="FAILED",reason=str(e));raise
   event["status"]="COMPLETED";return result
  return tracked
 models.MonthlyClimatology.fit=wrap_fit(models.MonthlyClimatology.fit)
 models.MeteorologyRidge.fit=wrap_fit(models.MeteorologyRidge.fit)
 predictions=[];parameters=[];fold_records=[];overall=[];yearly=[];comparisons=[];comparison_detail={}
 start=time.monotonic()
 try:
  for experiment,yearfield in (("CONSECUTIVE_10Y","primary_years"),("SPARSE_10Y_PUBLIC_SUBSAMPLING","sparse_years")):
   years=protocol[yearfield]
   for gauge_id in meta["selected_gauge_ids"]:
    sub=sorted([r for r in rows if r["gauge_id"]==gauge_id and r["year"] in years],key=lambda r:(r["year"],r["month"]))
    assert len(sub)==120 and len(set(r["year"] for r in sub))==10
    keys=tuple(SampleKey(source.DATASET,meta["snapshot_id"],r["station_id"],r["year"],r["month"]) for r in sub)
    x=FeatureBatch(keys,{"P":np.asarray([r["P_mm"] for r in sub]),"T":np.asarray([r["T_C"] for r in sub]),"met_complete":np.ones(120,dtype=bool)},synthetic=False,authorization_status="PUBLIC_DATA_REAL_EXPERIMENT")
    ledger=[{"sample_id":r["sample_id"],"dataset_id":source.DATASET,"data_snapshot_id":meta["snapshot_id"],"station_id":r["station_id"],"year":r["year"],"month":r["month"],"down_public_complete_usable":True,"meteorology_valid":True} for r in sub]
    folds=make_folds(ledger,GROUP_B,scheme="public_complete",validation="LOYO")
    assert len(folds)==10
    result={m:{} for m in ("C0","E3n")}
    local_predictions=[]
    for fold in folds:
     context.update(experiment=experiment,gauge_id=gauge_id,held_year=fold.test_years[0])
     assert len(fold.train_ids)==108 and len(fold.test_ids)==12
     tx,vx=x.take(fold.train_ids),x.take(fold.test_ids);enforce_fold(tx,vx,fold);source.set_outer_train(fold.train_ids)
     train_y=np.asarray([source._registered[k.sample_id]["Q_m3s"] for k in tx.keys])
     fold_records.append({"experiment":experiment,"gauge_id":gauge_id,**fold.record()})
     for mid in ("C0","E3n"):
      model=models.model_factory(mid)
      train_x=tx.select([]) if mid=="C0" else tx
      test_x=vx.select([]) if mid=="C0" else vx
      model.fit(TrainingBatch(train_x,train_y))
      pred=model.predict(test_x)
      assert pred.synthetic is False and pred.train_ids_hash==ids_hash(fold.train_ids)
      record=model.record();assert record["synthetic"] is False
      parameters.append({"experiment":experiment,"gauge_id":gauge_id,"fold_id":fold.fold_id,"held_year":fold.test_years[0],"record":record})
      for k,raw,clipped in zip(pred.keys,pred.raw,pred.constrained):
       assert k.sample_id not in result[mid] and k.sample_id in fold.test_ids
       result[mid][k.sample_id]=float(raw)
       local_predictions.append({"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","synthetic":False,"experiment":experiment,"gauge_id":gauge_id,"sample_id":k.sample_id,"year":k.year,"month":k.month,"fold_id":fold.fold_id,"model_id":mid,"Qobs_m3s":None,"Qsim_raw_m3s":float(raw),"Qsim_nonnegative_m3s":float(clipped),"unit":"m3/s"})
     print(json.dumps({"stage":"FOLD_PREDICTED","experiment":experiment,"gauge_id":gauge_id,"held_year":fold.test_years[0],"elapsed_s":round(time.monotonic()-start,1)}),flush=True)
    # Freeze this catchment/scenario's entire OOF before connecting final test observations.
    commitment=digest([{k:v for k,v in p.items() if k!="Qobs_m3s"} for p in local_predictions])
    for p in local_predictions:p["Qobs_m3s"]=source._registered[p["sample_id"]]["Q_m3s"]
    predictions.extend(local_predictions)
    ids=sorted(r["sample_id"] for r in sub);yy=np.asarray([source._registered[s]["year"] for s in ids])
    raw={m:np.asarray([result[m][s] for s in ids]) for m in result}
    for mid,p in raw.items():
     y=source.permit_metric(ids,p);metrics=metric_bundle(y,p,synthetic=False)
     source.permit_metric(ids,np.maximum(p,0));secondary=metric_bundle(y,np.maximum(p,0),synthetic=False)
     source.permit_metric(ids,p);skill=same_sample_skill(y,p,raw["C0"],ids,ids,synthetic=False)
     losses=[]
     for year in years:
      idx=np.flatnonzero(yy==year);yearids=[ids[i] for i in idx];pyear=p[idx]
      yyear=source.permit_metric(yearids,pyear);ym=metric_bundle(yyear,pyear,synthetic=False);losses.append(ym["MSE"]["value"])
      yearly.append({"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","experiment":experiment,"gauge_id":gauge_id,"model_id":mid,"year":year,"n_months":len(idx),**{k:v["value"] for k,v in ym.items()},"NA_reasons":"|".join(k+":"+v["reason_code"] for k,v in ym.items() if v["status"]=="N/A")})
     overall.append({"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","experiment":experiment,"gauge_id":gauge_id,"model_id":mid,"n_years":10,"n_months":120,**{k:v["value"] for k,v in metrics.items()},"skill_vs_C0":skill["value"],"equal_year_MSE":float(np.mean(losses)),"negative_raw_predictions":int(np.sum(p<0)),"nonnegative_NSE":secondary["NSE"]["value"],"nonnegative_KGE":secondary["KGE"]["value"],"nonnegative_RMSE":secondary["RMSE"]["value"],"OOF_commitment":commitment,"NA_reasons":"|".join(k+":"+v["reason_code"] for k,v in metrics.items() if v["status"]=="N/A")})
    y=source.permit_metric(ids,raw["E3n"])
    detail=paired_year_comparison(y,raw["E3n"],raw["C0"],yy,20261025)
    detail.update(classification="DESCRIPTIVE_PUBLIC_CATCHMENT_EXPERIMENT",multiple_testing="No confirmatory multi-basin family pre-registered; do not use unadjusted p for confirmatory claims",same_train_and_test_support=True)
    key=f"{experiment}|ID_{gauge_id}";comparison_detail[key]=detail
    comparisons.append({"experiment":experiment,"gauge_id":gauge_id,"candidate":"E3n","benchmark":"C0","n_years":10,"mean_year_MSE_improvement":detail["mean_year_improvement"]["value"],"fraction_years_improved":detail["fraction_years_improved"],"unadjusted_descriptive_signflip_p":detail["exact_sign_flip"]["p"]["value"],"jackknife_all_deletions_positive":detail["jackknife"]["all_deletions_positive"],"classification":"DESCRIPTIVE_ONLY"})
  writecsv(stage/"OOF_PREDICTIONS.csv",predictions);writecsv(stage/"OVERALL_METRICS.csv",overall);writecsv(stage/"YEARLY_EVALUATION.csv",yearly);writecsv(stage/"MODEL_COMPARISON.csv",comparisons)
  writejson(stage/"folds.json",fold_records);writejson(stage/"model_parameters.json",parameters);writejson(stage/"model_comparison_details.json",comparison_detail);writejson(stage/"fit_events.json",fit_events)
  writejson(stage/"protocol.json",protocol);writejson(stage/"data_provenance.json",meta);writejson(stage/"code_hashes.json",codepins)
  counts={f"{model}_{level}":sum(e["model_id"]==model and e["level"]==level and e["status"]=="COMPLETED" for e in fit_events) for model in ("C0","E3n") for level in ("outer","inner")}
  assert all(e["status"]=="COMPLETED" for e in fit_events)
  manifest={"run_id":runid,"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","synthetic":False,"dataset_id":source.DATASET,"snapshot_id":meta["snapshot_id"],"dataset_doi":"10.5281/zenodo.5153305","license":"CC-BY-SA-4.0 (stricter page conditions; API CC-BY discrepancy documented)","code_hash":codehash,"protocol_hash":protocolhash,"folds_hash":digest(fold_records),"selected_gauge_ids":meta["selected_gauge_ids"],"models":["C0","E3n"],"scenarios":["CONSECUTIVE_10Y","SPARSE_10Y_PUBLIC_SUBSAMPLING"],"n_outer_folds":len(fold_records),"n_OOF_records":len(predictions),"fit_counts":counts,"actual_completed_fit_calls":len(fit_events),"environment":{"python":platform.python_version(),"numpy":np.__version__,"executable":sys.executable},"SyrDarya_real_trained_models":0,"teacher_Q_access":False,"historical_sealed_LamaH_access":False,"created_UTC":datetime.now(timezone.utc).isoformat()}
  manifest["artifact_hashes"]={p.name:sha(p) for p in sorted(stage.iterdir()) if p.is_file()}
  writejson(stage/"manifest.json",manifest)
  with (stage/"SHA256SUMS.txt").open("x",encoding="utf-8") as f:
   for p in sorted(stage.iterdir()):
    if p.name!="SHA256SUMS.txt":f.write(sha(p)+"  "+p.name+"\n")
  dest=R/"runs"/runid;stage.rename(dest)
  with (R/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({**attempt,"status":"COMPLETED","run_dir":str(dest),"fit_counts":counts,"n_OOF":len(predictions)})+"\n")
  print(json.dumps({"status":"COMPLETED","run_dir":str(dest),"fit_counts":counts,"actual_fit_calls":len(fit_events),"OOF_records":len(predictions),"public_real":True,"SyrDarya_real":False}),flush=True)
 except Exception as e:
  with (R/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({**attempt,"status":"FAILED","error":repr(e),"partial_fit_events":len(fit_events),"completed_predictions":len(predictions),"staging":str(stage)})+"\n")
  writejson(stage/"FAILURE.json",{"error":repr(e),"fit_events":fit_events});raise
if __name__=="__main__":main()

