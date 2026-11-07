"""Read-only independent P2 source, calendar, fold, parameter and score verification."""
import bootstrap,csv,json,hashlib,calendar,sys,collections
from pathlib import Path
from datetime import date,datetime,timezone
import numpy as np
from vhs_sci.contracts import ids_hash,digest
P=Path(__file__).parents[1];R=P.parent;P1=R/"p1_seasonal_meteorology_ablation"
run=next(p for p in (P/"runs").iterdir() if p.name.startswith("PUBLIC_DATA_EXPLORATORY_P2-"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def rr(p,delimiter=","):
 with p.open(encoding="utf-8-sig") as f:return [{k.strip():v for k,v in r.items()} for r in csv.DictReader(f,delimiter=delimiter)]
def seal(root):
 n=0
 for line in (root/"SHA256SUMS.txt").read_text().splitlines():
  h,name=line.split("  ",1);assert sha(root/name)==h,name;n+=1
 return n
def close(a,b,rtol=1e-9,atol=1e-9):assert np.allclose(a,b,rtol=rtol,atol=atol),(a,b)
man=jl(run/"manifest.json");meta=jl(P/"source/SNAPSHOT.json");sel=jl(P/"P2_NEW_BASINS_FROZEN.json");pro=jl(P/"P2_PROTOCOL.json")
result={"label":pro["label"],"created_UTC":datetime.now(timezone.utc).isoformat(),"P2_run_files_verified":seal(run),"P1_files_unchanged":seal(P1),"refitting_in_verifier":False}
for n,h in man["frozen_inputs"].items():assert sha(P/n)==h
for n,h in jl(run/"code_hashes.json").items():assert sha(Path(n))==h
for n,h in meta["source_files"].items():assert sha(Path(n))==h
rows=rr(P/"source/monthly_labels_features.csv");index={r["sample_id"]:r for r in rows};weather=rr(P/"source/monthly_exogenous_weather.csv");wi={(int(r["gauge_id"]),int(r["year"]),int(r["month"])):r for r in weather}
# Recompute date mapping independently of calendar_features.previous_month.
def previous(y,m,k):
 for _ in range(k):
  m-=1
  if m==0:y-=1;m=12
 return y,m
for r in rows:
 g,y,m=int(r["gauge_id"]),int(r["year"]),int(r["month"]);past=[wi[(g,*previous(y,m,k))] for k in (1,2,3)]
 ss=sum(float(v["P"]) for v in past if float(v["T"])<=0)
 close([float(r["L1"]),float(r["S"]),float(r["M"])],[float(past[0]["P"]),ss,ss*max(float(r["T"]),0)])
 assert all(v["met_complete"]=="True" for v in past)
# Reaggregate all actual source MET dates and target Q labels.
qchecks=mchecks=0
for g in meta["all_ids"]:
 old=g in pro["development_gauges"];d=(R/"source/extracted" if g in [2,6,9] else P1/"source/daily") if old else P/"source/daily"
 need={(y,m) for gg,y,m in wi if gg==g};target={(int(r["year"]),int(r["month"])) for r in rows if int(r["gauge_id"])==g}
 met={};q={}
 for r in rr(d/f"A_basins_total_upstrm/2_timeseries/daily/ID_{g}.csv",";"):
  y,m=int(r["YYYY"]),int(r["MM"])
  if (y,m) not in need:continue
  dt=date(y,m,int(r["DD"]));assert dt not in met;met[dt]=r
 for r in rr(d/f"D_gauges/2_timeseries/daily/ID_{g}.csv",";"):
  y,m=int(r["YYYY"]),int(r["MM"])
  if (y,m) not in target:continue
  dt=date(y,m,int(r["DD"]));assert dt not in q;q[dt]=r
 for y,m in need:
  days=calendar.monthrange(y,m)[1];rs=[met[date(y,m,z)] for z in range(1,days+1)]
  pp=[float(r["prec"]) for r in rs];tt=[float(r["2m_temp_mean"]) for r in rs]
  assert np.isfinite(pp+tt).all() and min(pp)>=0 and -999 not in tt
  close([sum(pp),sum(tt)/days],[float(wi[g,y,m]["P"]),float(wi[g,y,m]["T"])]);mchecks+=1
  if (y,m) in target:
   qs=[q[date(y,m,z)] for z in range(1,days+1)];vals=[float(r["qobs"]) for r in qs]
   assert all(r["ckhs"]=="1" for r in qs) and min(vals)>=0 and np.isfinite(vals).all()
   close(sum(vals)/days,float(index[f"LAMAH_CE_PUBLIC_V1:{g}:{y}-{m:02d}"]["Q_m3s"]));qchecks+=1
folds=jl(run/"folds.json");pars=jl(run/"model_parameters.json");events=jl(run/"fit_events.json")
fmap={(f["cohort"],f["scenario"],f["gauge_id"],f["fold_id"]):f for f in folds}
pmap={};inner_count=0;gradient_checks=0
for item in pars:
 f=fmap[item["cohort"],item["scenario"],item["gauge_id"],item["fold_id"]];rec=item["record"];tr=rec["transform"];pa=rec["parameters"];fields=rec["fields"]
 assert rec["train_ids_hash"]==tr["fit_ids_hash"]==ids_hash(f["train_ids"])
 assert set(f["train_ids"]).isdisjoint(f["test_ids"]) and set(f["train_years"]).isdisjoint(f["test_years"])
 train=[index[i] for i in f["train_ids"]];months=np.array([int(r["month"]) for r in train]);raw=np.array([[float(r[k]) for k in fields] for r in train]);y=np.array([float(r["Q_m3s"]) for r in train])
 mu=np.array(tr["monthly_mean"]);sd=np.array(tr["monthly_sample_std"]);const=np.array(tr["monthly_constant"]);climate=np.array(pa["monthly_climatology"]);beta=np.array(pa["beta_standardized"]);alpha=pa["selection"]["selected_alpha"]
 for mo in range(1,13):
  vals=raw[months==mo];close(mu[mo-1],vals.mean(axis=0));close(sd[mo-1],vals.std(axis=0,ddof=1));close(climate[mo-1],y[months==mo].mean())
  expected=vals.std(axis=0,ddof=1)<=1e-12*np.maximum(1,np.max(abs(vals),axis=0));assert np.array_equal(expected,const[mo-1])
 Z=np.where(const[months-1],0,(raw-mu[months-1])/np.where(const[months-1],1,sd[months-1]))
 residual=y-climate[months-1];gradient=Z.T@(Z@beta-residual)+alpha*beta
 assert np.linalg.norm(gradient)<=1e-8*max(1,np.linalg.norm(Z.T@residual));gradient_checks+=1
 assert [cv["alpha"] for cv in rec["nested_CV"]]==pro["alpha"],"UNFROZEN_ALPHA_GRID"
 for cv in rec["nested_CV"]:
  close(cv["mean_year_MSE_raw"],np.mean(cv["year_losses"]));close(cv["standard_error"],np.std(cv["year_losses"],ddof=1)/np.sqrt(len(cv["year_losses"])))
  for inf in cv["folds"]:
   held=inf["held_year"];trainids=[i for i in f["train_ids"] if int(index[i]["year"])!=held]
   assert inf["train_ids_hash"]==inf["transform_fit_ids_hash"]==ids_hash(trainids)
   assert set(inf["transform_fit_years"])==set(f["train_years"])-{held};inner_count+=1
 best=min(rec["nested_CV"],key=lambda z:(z["mean_year_MSE_raw"],z["alpha"]));cut=best["mean_year_MSE_raw"]+best["standard_error"];tol=1e-12*max(1,abs(cut))
 assert alpha==max(z["alpha"] for z in rec["nested_CV"] if z["mean_year_MSE_raw"]<=cut+tol)
 pmap[item["cohort"],item["scenario"],item["gauge_id"],item["fold_id"],rec["model_id"]]=(rec,f)
pred=rr(run/"P2_OOF_PREDICTIONS.csv");seen=set();groups=collections.defaultdict(list)
for r in pred:
 g=int(r["gauge_id"]);m=int(r["month"]);sid=r["sample_id"];key=(r["cohort"],r["scenario"],g,sid,r["model_id"]);assert key not in seen;seen.add(key)
 rec,f=pmap[r["cohort"],r["scenario"],g,r["fold_id"],r["model_id"]];assert sid in f["test_ids"] and sid not in f["train_ids"]
 fields=rec["fields"];tr=rec["transform"];pa=rec["parameters"];mu=np.array(tr["monthly_mean"][m-1]);sd=np.array(tr["monthly_sample_std"][m-1]);con=np.array(tr["monthly_constant"][m-1]);raw=np.array([float(index[sid][n]) for n in fields])
 z=np.where(con,0,(raw-mu)/np.where(con,1,sd));clim=pa["monthly_climatology"][m-1];beta=np.array(pa["beta_standardized"])
 close(clim+z@beta,float(r["Qsim_raw_m3s"]));close(clim,float(r["train_Q_month_mean_m3s"]));close(max(float(r["Qsim_raw_m3s"]),0),float(r["Qsim_nonnegative_m3s"]));close(float(index[sid]["Q_m3s"]),float(r["Qobs_m3s"]))
 trainq=[float(index[i]["Q_m3s"]) for i in f["train_ids"]];close(np.quantile(trainq,[.2,.8]),[float(r["train_Q20"]),float(r["train_Q80"])])
 response=0;j=fields.index("T")
 if not con[j]:response=beta[j]/sd[j]
 if "M" in fields:
  j=fields.index("M")
  if not con[j]:response+=beta[j]*float(index[sid]["S"])*(max(float(index[sid]["T"])+1,0)-max(float(index[sid]["T"]),0))/sd[j]
 close(response,float(r["current_T_plus1_conditional_response_m3s"]))
 groups[r["cohort"],r["scenario"],r["gauge_id"],r["model_id"]].append(r)
for r in rr(run/"P2_OVERALL_METRICS.csv"):
 rs=groups[r["cohort"],r["scenario"],r["gauge_id"],r["model_id"]];y=np.array([float(x["Qobs_m3s"]) for x in rs]);p=np.array([float(x["Qsim_raw_m3s"]) for x in rs]);err=p-y
 mse=np.mean(err**2);nse=1-sum(err**2)/sum((y-y.mean())**2);rho=np.corrcoef(y,p)[0,1];alpha=p.std()/y.std();beta=p.mean()/y.mean();kge=1-np.sqrt((rho-1)**2+(alpha-1)**2+(beta-1)**2)
 close([mse,nse,kge,np.mean(abs(err)),np.sqrt(mse),100*sum(err)/sum(y)],[float(r[k]) for k in ["MSE","NSE","KGE","MAE","RMSE","PBIAS"]])
 assert len(rs)==int(r["n_months"])
# Every actual fit matches allowed train hashes, including all alpha/inner calls.
allowed={}
for key,f in fmap.items():
 allowed[key]={"outer":{ids_hash(f["train_ids"])},"inner":{ids_hash([i for i in f["train_ids"] if int(index[i]["year"])!=held]) for held in f["train_years"]}}
for e in events:
 key=e["cohort"],e["scenario"],e["gauge_id"],f"LOYO-{e['outer_held_year']}"
 assert e["train_ids_hash"] in allowed[key][e["level"]] and e["status"]=="COMPLETED"
 assert e["n_train"]==(108 if e["level"]=="outer" else 96)
parity=rr(run/"P1_BASELINE_REFIT_PARITY.csv");assert len(parity)==18 and max(float(x["max_abs_prediction_difference_vs_P1"]) for x in parity)<1e-9
result.update(status="PASS",monthly_Q_reaggregated=qchecks,monthly_MET_reaggregated=mchecks,calendar_features_independently_recomputed=len(rows),parameter_predictions_verified=len(pred),outer_ridge_stationarity_checks=gradient_checks,outer_folds=len(folds),fold_model_records=len(pars),inner_transform_fold_records_verified=inner_count,actual_fit_events_verified=len(events),P1_baseline_refit_parity_cases=len(parity),max_baseline_refit_difference=max(float(x["max_abs_prediction_difference_vs_P1"]) for x in parity),new_basins_selected_before_scores=not sel["new_scores_seen"],no_test_Q_in_features=True,teacher_Q_access=False)
if (P/"SHA256SUMS.txt").exists():result["P2_delivery_files_verified"]=seal(P)
if "--write-evidence" in sys.argv:
 assert not (P/"SHA256SUMS.txt").exists(),"SEALED_READ_ONLY"
 (P/"P2_REAL_RUN_VERIFICATION.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

