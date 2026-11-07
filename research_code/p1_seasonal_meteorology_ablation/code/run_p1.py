"""Execute P1 once; preserve old reference OOF; score only committed outer predictions."""
import os
for k in ("OMP_NUM_THREADS","OPENBLAS_NUM_THREADS","MKL_NUM_THREADS"):os.environ[k]="1"
import bootstrap,csv,json,hashlib,platform,time,sys
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import public_runtime as src
from vhs_sci.contracts import SampleKey,FeatureBatch,TrainingBatch,GROUP_B,digest,ids_hash
from vhs_sci.models import baselines as bm
from vhs_sci.folds import make_folds
from vhs_sci.invariants import enforce_fold
from vhs_sci.evaluate import metric_bundle,paired_year_comparison
from p1_models import HarmonicSeasonal,ClimatologyPT
P=Path(__file__).parents[1];R=P.parent;OLD=R/"runs/PUBLIC_DATA_REAL_EXPERIMENT-20261026T010504Z-f4d13a326504";LABEL="PUBLIC_DATA_EXPLORATORY_P1"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def jw(p,x):
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def readcsv(p):
 with p.open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def metrics(ids,p):
 y=src.permit_metric(ids,p)
 return y,{k:v["value"] for k,v in metric_bundle(y,p,synthetic=False).items()}
def stat(y,p):
 return {"n":len(y),"Qobs_mean":float(np.mean(y)),"Qsim_mean":float(np.mean(p)),"bias":float(np.mean(p-y)),"RMSE":float(np.sqrt(np.mean((p-y)**2))),"MSE":float(np.mean((p-y)**2))}
def main():
 assert jl(P/"evidence/UNIT_LEAKAGE_TESTS.json")["success"]
 freeze=jl(P/"evidence/PREFIT_FREEZE.json")
 for n,h in freeze.items():assert sha(P/n)==h,n
 proto=jl(P/"P1_PROTOCOL.json");meta=jl(P/"source/MONTHLY_SNAPSHOT.json");pin=jl(P/"evidence/FROZEN_BASELINE_PINS.json")
 for n,h in pin["files"].items():assert sha(OLD/n)==h,n
 rows=readcsv(P/"source/monthly_admitted.csv")
 for r in rows:
  for k in ("gauge_id","year","month"):r[k]=int(r[k])
  for k in ("Q_m3s","P_mm","T_C"):r[k]=float(r[k])
  r["complete"]=r["complete"]=="True"
 src.register(rows,meta["snapshot_id"])
 codes={str(p):sha(p) for root in [P/"code",R/"code/vendor_public"] for p in sorted(root.rglob("*.py"))}
 runid=LABEL+"-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+digest({"code":codes,"protocol":proto,"snapshot":meta["snapshot_id"]})[:12]
 stage=P/"runs"/(".staging-"+runid);stage.mkdir()
 attempt={"attempt_id":runid,"label":LABEL,"status":"STARTED","UTC":datetime.now(timezone.utc).isoformat(),"protocol_hash":digest(proto),"code_hash":digest(codes),"snapshot_id":meta["snapshot_id"]}
 def log(status,**kw):
  with (P/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({**attempt,"status":status,**kw})+"\n")
 log("STARTED")
 context={};fits=[]
 def wrap(fun):
  def call(self,train):
   event={**context,"model_id":self.model_id,"level":"outer" if set(train.features.ids)==src._train_ids else "inner","train_ids_hash":ids_hash(train.features.ids),"n_train":len(train.labels),"status":"STARTED"};fits.append(event)
   try:out=fun(self,train)
   except Exception as e:event.update(status="FAILED",reason=repr(e));raise
   event["status"]="COMPLETED";return out
  return call
 for cls in [bm.MonthlyClimatology,bm.MeteorologyRidge,HarmonicSeasonal,ClimatologyPT]:cls.fit=wrap(cls.fit)
 oldpred={(r["experiment"],int(r["gauge_id"]),r["sample_id"],r["model_id"]):r for r in readcsv(OLD/"OOF_PREDICTIONS.csv")}
 oldpars={(r["experiment"],int(r["gauge_id"]),r["fold_id"],r["record"]["model_id"]):r for r in jl(OLD/"model_parameters.json")}
 oldfolds={(r["experiment"],int(r["gauge_id"]),r["fold_id"]):r for r in jl(OLD/"folds.json")}
 predictions=[];pars=[];foldrecs=[];overall=[];yearly=[];seasons=[];comparisons=[];details={};decomp=[];boundary=[]
 start=time.monotonic()
 try:
  for ex,yearfield in [("CONSECUTIVE_10Y","primary_years"),("SPARSE_10Y_PUBLIC_SUBSAMPLING","sparse_years")]:
   years=proto[yearfield]
   for g in meta["all_gauge_ids"]:
    cohort=proto["cohort_membership"][str(g)];sub=sorted([r for r in rows if r["gauge_id"]==g and r["year"] in years],key=lambda r:(r["year"],r["month"]))
    assert len(sub)==120
    keys=tuple(SampleKey(src.DATASET,meta["snapshot_id"],r["station_id"],r["year"],r["month"]) for r in sub)
    x=FeatureBatch(keys,{"P":np.array([r["P_mm"] for r in sub]),"T":np.array([r["T_C"] for r in sub]),"met_complete":np.ones(120,bool)},False,LABEL)
    ledger=[{"sample_id":r["sample_id"],"dataset_id":src.DATASET,"data_snapshot_id":meta["snapshot_id"],"station_id":r["station_id"],"year":r["year"],"month":r["month"],"down_public_complete_usable":True,"meteorology_valid":True} for r in sub]
    folds=make_folds(ledger,GROUP_B,scheme="public_complete",validation="LOYO")
    loc=[];train_climate={}
    for fold in folds:
     assert len(fold.train_ids)==108 and len(fold.test_ids)==12
     context.update(experiment=ex,gauge_id=g,outer_held_year=fold.test_years[0],cohort=cohort)
     tx,vx=x.take(fold.train_ids),x.take(fold.test_ids);enforce_fold(tx,vx,fold);src.set_outer_train(fold.train_ids)
     ty=np.array([src._registered[i]["Q_m3s"] for i in tx.ids])
     climate={m:float(ty[tx.months==m].mean()) for m in range(1,13)}
     train_climate.update({k.sample_id:climate[k.month] for k in vx.keys})
     frec={"experiment":ex,"gauge_id":g,"cohort":cohort,**fold.record()};foldrecs.append(frec)
     if g in proto["old_gauge_ids"]:
      old=oldfolds[ex,g,fold.fold_id]
      assert old["train_ids_hash"]==frec["train_ids_hash"] and old["test_ids_hash"]==frec["test_ids_hash"]
     for mid in proto["models"]:
      if g in proto["old_gauge_ids"] and mid in ["C0","E3n"]:
       values=[float(oldpred[ex,g,k.sample_id,mid]["Qsim_raw_m3s"]) for k in vx.keys]
       record=oldpars[ex,g,fold.fold_id,mid]["record"]
       origin="FROZEN_BASELINE_OOF_REFERENCE"
       for k in vx.keys:assert float(oldpred[ex,g,k.sample_id,mid]["Qobs_m3s"])==src._registered[k.sample_id]["Q_m3s"]
      else:
       model={"C0":lambda:bm.MonthlyClimatology(),"H0":HarmonicSeasonal,"E3n":lambda:bm.MeteorologyRidge(False),"C0+PT":ClimatologyPT}[mid]()
       xx=tx.select([]) if mid in ["C0","H0"] else tx;vv=vx.select([]) if mid in ["C0","H0"] else vx
       model.fit(TrainingBatch(xx,ty));pp=model.predict(vv);values=pp.raw.tolist()
       assert pp.train_ids_hash==ids_hash(fold.train_ids)
       record=model.record();record["authorization_status"]=LABEL;origin="P1_NEW_REAL_FIT"
      pars.append({"experiment":ex,"gauge_id":g,"cohort":cohort,"fold_id":fold.fold_id,"held_year":fold.test_years[0],"origin":origin,"record":record})
      if mid in ["E3n","C0+PT"]:
       selection=record["parameters"]["selection"]
       boundary.append({"experiment":ex,"gauge_id":g,"cohort":cohort,"model_id":mid,"held_year":fold.test_years[0],"origin":origin,"selected_alpha":selection["selected_alpha"],"best_alpha":selection.get("best_alpha"),"at_grid_upper_boundary":selection["selected_alpha"]==100})
      for k,v in zip(vx.keys,values):
       if mid=="C0":assert abs(v-climate[k.month])<=1e-10*max(1,abs(v))
       loc.append({"experiment_label":LABEL,"cohort":cohort,"experiment":ex,"gauge_id":g,"sample_id":k.sample_id,"year":k.year,"month":k.month,"fold_id":fold.fold_id,"model_id":mid,"Qobs_m3s":None,"Qsim_raw_m3s":v,"Qsim_nonnegative_m3s":max(v,0),"training_C0_month_mean_m3s":climate[k.month],"origin":origin,"unit":"m3/s"})
    assert len(loc)==480 and len(set((r["sample_id"],r["model_id"]) for r in loc))==480
    commit=digest([{k:v for k,v in r.items() if k!="Qobs_m3s"} for r in loc])
    for r in loc:r["Qobs_m3s"]=src._registered[r["sample_id"]]["Q_m3s"]
    predictions.extend(loc)
    ids=sorted(r["sample_id"] for r in sub);yy=np.array([src._registered[i]["year"] for i in ids]);mm=np.array([src._registered[i]["month"] for i in ids])
    base=np.array([train_climate[i] for i in ids]);raw={}
    for mid in proto["models"]:
     lr={r["sample_id"]:r for r in loc if r["model_id"]==mid};p=np.array([lr[i]["Qsim_raw_m3s"] for i in ids]);raw[mid]=p
     y,met=metrics(ids,p);_,clipped=metrics(ids,np.maximum(p,0))
     obs_an=y-base;pred_an=p-base
     cor=float(np.corrcoef(obs_an,pred_an)[0,1]) if np.std(pred_an)>1e-12*max(1,float(np.max(abs(pred_an)))) and np.std(obs_an)>0 else None
     overall.append({"experiment_label":LABEL,"cohort":cohort,"experiment":ex,"gauge_id":g,"model_id":mid,"n_months":120,"n_years":10,**met,"skill_vs_C0":float(1-np.sum((y-p)**2)/np.sum((y-base)**2)),"anomaly_correlation":cor,"anomaly_correlation_reason":"CONSTANT_PREDICTED_ANOMALY" if cor is None else "OK","anomaly_NSE_vs_zero":float(1-np.sum((obs_an-pred_an)**2)/np.sum(obs_an**2)),"anomaly_obs_mean":float(obs_an.mean()),"anomaly_prediction_mean":float(pred_an.mean()),"equal_year_MSE":met["MSE"],"negative_raw_predictions":int(np.sum(p<0)),"nonnegative_NSE":clipped["NSE"],"nonnegative_KGE":clipped["KGE"],"nonnegative_MSE":clipped["MSE"],"OOF_commitment":commit})
     for year in years:
      ix=np.flatnonzero(yy==year);_,ym=metrics([ids[i] for i in ix],p[ix]);yearly.append({"cohort":cohort,"experiment":ex,"gauge_id":g,"model_id":mid,"year":year,"n_months":12,**ym})
     for period,months in [(f"M{m:02d}",[m]) for m in range(1,13)]+[("MAM",[3,4,5]),("JJA",[6,7,8]),("SON",[9,10,11]),("DJF",[12,1,2]),("MAY_JUN",[5,6])]:
      ix=np.isin(mm,months);seasons.append({"cohort":cohort,"experiment":ex,"gauge_id":g,"model_id":mid,"period":period,**stat(y[ix],p[ix])})
    for candidate,benchmark,kind in [("C0+PT","C0","MAIN_MET_INCREMENT"),("E3n","H0","HARMONIC_MET_INCREMENT"),("H0","C0","SEASONAL_STRUCTURE")]:
     det=paired_year_comparison(y,raw[candidate],raw[benchmark],yy,proto["seed"])
     details[f"{ex}|{g}|{candidate}_vs_{benchmark}"]={"cohort":cohort,**det}
     bmse=float(np.mean((y-raw[benchmark])**2));cmse=float(np.mean((y-raw[candidate])**2))
     comparisons.append({"cohort":cohort,"experiment":ex,"gauge_id":g,"comparison":kind,"candidate":candidate,"benchmark":benchmark,"benchmark_MSE":bmse,"candidate_MSE":cmse,"MSE_skill":1-cmse/bmse,"mean_year_MSE_improvement":det["mean_year_improvement"]["value"],"fraction_years_improved":det["fraction_years_improved"],"jackknife_all_deletions_positive":det["jackknife"]["all_deletions_positive"],"unadjusted_descriptive_signflip_p":det["exact_sign_flip"]["p"]["value"],"classification":"EXPLORATORY_NOT_INDEPENDENT_CONFIRMATION"})
    mse={m:float(np.mean((y-v)**2)) for m,v in raw.items()}
    gap=mse["E3n"]-mse["C0"];structure=mse["H0"]-mse["C0"];weather=mse["E3n"]-mse["H0"]
    assert abs(gap-structure-weather)<1e-9*max(1,abs(gap))
    decomp.append({"cohort":cohort,"experiment":ex,"gauge_id":g,"E3n_minus_C0_MSE":gap,"H0_minus_C0_structure_MSE":structure,"E3n_minus_H0_weather_MSE":weather,"structure_signed_fraction_of_gap":structure/gap if abs(gap)>1e-12 else None,"C0PT_minus_C0_MSE":mse["C0+PT"]-mse["C0"]})
    print(json.dumps({"done":f"{ex}|ID{g}","new_completed_fits":len(fits),"elapsed_s":round(time.monotonic()-start,1),"MSE":mse}),flush=True)
  for name,rr in [("OOF_PREDICTIONS.csv",predictions),("P1_OVERALL_METRICS.csv",overall),("P1_YEARLY_METRICS.csv",yearly),("P1_SEASONAL_BIAS.csv",seasons),("P1_MODEL_COMPARISON.csv",comparisons),("P1_MSE_DECOMPOSITION.csv",decomp),("P1_ALPHA_SELECTION.csv",boundary)]:cw(stage/name,rr)
  for name,data in [("model_parameters.json",pars),("folds.json",foldrecs),("fit_events.json",fits),("comparison_details.json",details),("protocol.json",proto),("source_snapshot.json",meta),("code_hashes.json",codes),("frozen_selection.json",jl(P/"NEW_BASIN_SELECTION_FROZEN.json")),("baseline_pins.json",pin)]:jw(stage/name,data)
  counts={mid:{level:sum(e["model_id"]==mid and e["level"]==level and e["status"]=="COMPLETED" for e in fits) for level in ["outer","inner"]} for mid in proto["models"]}
  assert all(e["status"]=="COMPLETED" for e in fits)
  nnew=sum(r["origin"]=="P1_NEW_REAL_FIT" for r in predictions)
  manifest={"run_id":runid,"experiment_label":LABEL,"synthetic":False,"dataset_id":src.DATASET,"snapshot_id":meta["snapshot_id"],"protocol_hash":digest(proto),"protocol_file_sha256":sha(P/"P1_PROTOCOL.json"),"code_hash":digest(codes),"folds_hash":digest(foldrecs),"selection_sha256":sha(P/"NEW_BASIN_SELECTION_FROZEN.json"),"outer_folds":len(foldrecs),"fold_model_records":len(pars),"real_new_fit_counts":counts,"n_new_real_OOF":nnew,"n_imported_frozen_OOF":len(predictions)-nnew,"n_four_model_OOF":len(predictions),"n_unique_source_months":len(rows),"elapsed_seconds":time.monotonic()-start,"environment":{"python":platform.python_version(),"numpy":np.__version__,"executable":sys.executable},"new_cohort_seen_before_freeze":False,"failed_fits":0,"teacher_Q_access":False,"SYRDARYA_REAL_EXPERIMENT":False,"source_DOI":"10.5281/zenodo.5153305","license":"CC BY-SA 4.0 stricter page conditions; original attribution and discrepancy retained","created_UTC":datetime.now(timezone.utc).isoformat(),"prefit_freeze":freeze}
  jw(stage/"manifest.json",manifest)
  with (stage/"SHA256SUMS.txt").open("x",encoding="utf-8") as f:
   for p in sorted(stage.iterdir()):
    if p.is_file() and p.name!="SHA256SUMS.txt":f.write(sha(p)+"  "+p.name+"\n")
  target=P/"runs"/runid;stage.rename(target);log("COMPLETED",run_dir=str(target),n_new_real_OOF=nnew,fit_counts=counts)
  print(json.dumps({"status":"COMPLETED","run_dir":str(target),**manifest}),flush=True)
 except Exception as e:
  jw(stage/"FAILURE.json",{"error":repr(e),"fits":fits});log("FAILED",reason=repr(e),staging=str(stage));raise
if __name__=="__main__":main()

