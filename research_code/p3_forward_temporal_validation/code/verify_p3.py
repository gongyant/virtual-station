"""Independent P3 verification, no refit; score-only labels allowed after sealed run exists."""
import bootstrap,csv,json,hashlib,calendar,sys,collections
from pathlib import Path
from datetime import date,datetime,timezone
import numpy as np
from vhs_sci.contracts import ids_hash,digest
P=Path(__file__).parents[1];R=P.parent;run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_TEMPORAL_P3-"));B=run/"prediction_bundle"
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def rr(p,delimiter=","):
 with p.open(encoding="utf-8-sig") as f:return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=delimiter)]
def seal(root):
 n=0
 for line in (root/"SHA256SUMS.txt").read_text().splitlines():
  h,name=line.split("  ",1);assert sha(root/name)==h,name;n+=1
 return n
def close(a,b,rtol=1e-9,atol=1e-9):assert np.allclose(a,b,rtol=rtol,atol=atol),(a,b)
man=jl(run/"P3_RUN_MANIFEST.json");pro=jl(P/"P3_PROTOCOL.json");split=jl(P/"P3_SPLIT_FROZEN.json");snap=jl(P/"source/SNAPSHOT.json")
result={"label":pro["label"],"created_UTC":datetime.now(timezone.utc).isoformat(),"no_refits":True,"run_files_verified":seal(run),"prediction_bundle_files_verified":seal(B)}
for n,h in man["frozen_inputs"].items():assert sha(P/n)==h,n
for n,h in jl(run/"code_hashes.json").items():assert sha(Path(n))==h,n
history=jl(P/"evidence/HISTORY_PINS.json");history_counts={}
for root,pins in history.items():
 for n,h in pins.items():assert sha(Path(root)/n)==h,n
 history_counts[root]=len(pins)
result["history_files_verified"]=history_counts
for n,h in snap["source_files"].items():assert sha(Path(n))==h
features=rr(P/"source/features.csv");fi={r["sample_id"]:r for r in features};train=rr(P/"source/train_labels.csv");test=rr(P/"source/test_labels_SCORE_ONLY.csv")
tr={r["sample_id"]:r for r in train};te={r["sample_id"]:r for r in test}
assert set(tr).isdisjoint(te);assert max((int(r["year"]),int(r["month"])) for r in train)<(2005,1);assert min((int(r["year"]),int(r["month"])) for r in test)>=(2005,1)
weather={(int(r["gauge_id"]),int(r["year"]),int(r["month"])):r for r in rr(P/"source/weather_monthly.csv")}
for r in features:
 y,m=int(r["year"]),int(r["month"]);pm=(y,m-1) if m>1 else (y-1,12);g=int(r["gauge_id"])
 close([float(r["P"]),float(r["T"]),float(r["L1"])],[float(weather[g,y,m]["P"]),float(weather[g,y,m]["T"]),float(weather[g,*pm]["P"])])
# Independently assess all audit months, including rejected raw months and true zeros.
audit=rr(P/"P3_TEMPORAL_SUPPORT_AUDIT.csv");auditidx={(int(r["gauge_id"]),int(r["year"]),int(r["month"])):r for r in audit}
Qchecks=METchecks=0
for g in split["all_gauges"]:
 qp=next(Path(p) for p in snap["source_files"] if p.replace(chr(92),"/").endswith(f"D_gauges/2_timeseries/daily/ID_{g}.csv"));mp=next(Path(p) for p in snap["source_files"] if p.replace(chr(92),"/").endswith(f"A_basins_total_upstrm/2_timeseries/daily/ID_{g}.csv"))
 q={};met={};qd=set();md=set()
 for r in rr(qp,";"):
  y,m=int(r["YYYY"]),int(r["MM"])
  if not 1981<=y<=2014:continue
  d=date(y,m,int(r["DD"]))
  if d in q:qd.add(d)
  q[d]=r
 for r in rr(mp,";"):
  y,m=int(r["YYYY"]),int(r["MM"])
  if not (1981<=y<=2014 or (y,m)==(1980,12)):continue
  d=date(y,m,int(r["DD"]))
  if d in met:md.add(d)
  met[d]=r
 for y,m in [(1980,12)]+[(yy,mm) for yy in range(1981,2015) for mm in range(1,13)]:
  days=calendar.monthrange(y,m)[1];pp=[];tt=[];qq=[];eq=col=0
  for day in range(1,days+1):
   d=date(y,m,day);wr=met.get(d);qr=q.get(d)
   if wr and d not in md:
    p,t=float(wr["prec"]),float(wr["2m_temp_mean"])
    if np.isfinite(p) and p>=0:pp.append(p)
    if np.isfinite(t) and t!=-999:tt.append(t)
   if qr:
    v=float(qr["qobs"]);eq+=qr["qceq"]=="1";col+=qr["qcol"]=="1"
    if np.isfinite(v) and v>=0 and qr["ckhs"]=="1" and d not in qd:qq.append(v)
  w=weather[g,y,m];assert int(w["P_valid_days"])==len(pp) and int(w["T_valid_days"])==len(tt)
  if len(pp)==days:close(float(w["P"]),sum(pp))
  else:assert w["P"]==""
  if len(tt)==days:close(float(w["T"]),sum(tt)/days)
  else:assert w["T"]==""
  METchecks+=1
  if y==1980:continue
  a=auditidx[g,y,m];assert int(a["Q_valid_days"])==len(qq) and int(a["qceq_flagged_days"])==eq and int(a["qcol_flagged_days"])==col
  pm=(y,m-1) if m>1 else (y-1,12);lag=weather[g,*pm];ok=len(qq)==days and len(pp)==days and len(tt)==days and lag["P"]!=""
  assert (a["common_admissible"]=="True")==ok
  sid=f"LAMAH_CE_PUBLIC_V1:{g}:{y}-{m:02d}"
  if ok:close(float((tr if y<=2004 else te)[sid]["Q_m3s"]),sum(qq)/days)
  else:assert sid not in fi
  Qchecks+=1
folds=jl(B/"folds.json");fmap={f["gauge_id"]:f for f in folds};pars=jl(B/"model_parameters.json");pmaps={}
inner_checks=0
for p in pars:
 rec=p["record"];f=fmap[p["gauge_id"]];pa=rec["parameters"];T=rec["transform"];fields=rec["fields"]
 assert rec["model_id"] in ["C0+PT","P2-L1"]
 assert rec["train_ids_hash"]==T["fit_ids_hash"]==ids_hash(f["train_ids"])
 assert set(f["train_ids"])<=set(tr) and set(f["test_ids"])<=set(te)
 assert max(int(fi[i]["year"]) for i in f["train_ids"])<=2004 and min(int(fi[i]["year"]) for i in f["test_ids"])>=2005
 assert set(f["train_ids"]).isdisjoint(f["test_ids"])
 vals=np.array([[float(fi[i][k]) for k in fields] for i in f["train_ids"]]);months=np.array([int(fi[i]["month"]) for i in f["train_ids"]]);y=np.array([float(tr[i]["Q_m3s"]) for i in f["train_ids"]])
 mu=np.array(T["monthly_mean"]);sd=np.array(T["monthly_sample_std"]);const=np.array(T["monthly_constant"]);climate=np.array(pa["monthly_climatology"]);beta=np.array(pa["beta_standardized"]);alpha=pa["selection"]["selected_alpha"]
 for mo in range(1,13):
  v=vals[months==mo];close(mu[mo-1],v.mean(axis=0));close(sd[mo-1],v.std(axis=0,ddof=1));close(climate[mo-1],y[months==mo].mean())
 Z=np.where(const[months-1],0,(vals-mu[months-1])/np.where(const[months-1],1,sd[months-1]))
 grad=Z.T@(Z@beta-(y-climate[months-1]))+alpha*beta
 assert np.linalg.norm(grad)<=1e-8*max(1,np.linalg.norm(Z.T@(y-climate[months-1])))
 assert [x["alpha"] for x in rec["nested_CV"]]==pro["alpha"]
 for cv in rec["nested_CV"]:
  close(cv["mean_year_MSE_raw"],np.mean(cv["year_losses"]));close(cv["standard_error"],np.std(cv["year_losses"],ddof=1)/np.sqrt(len(cv["year_losses"])))
  for v in cv["folds"]:
   held=v["held_year"];ids=[i for i in f["train_ids"] if int(fi[i]["year"])!=held]
   assert held<=2004 and v["train_ids_hash"]==v["transform_fit_ids_hash"]==ids_hash(ids)
   assert set(v["transform_fit_years"])==set(f["train_years"])-{held};inner_checks+=1
 best=min(rec["nested_CV"],key=lambda z:(z["mean_year_MSE_raw"],z["alpha"]));cut=best["mean_year_MSE_raw"]+best["standard_error"];tol=1e-12*max(1,abs(cut));assert alpha==max(z["alpha"] for z in rec["nested_CV"] if z["mean_year_MSE_raw"]<=cut+tol)
 pmaps[p["gauge_id"],p["model_id"]]=rec
qfree=rr(B/"TEST_PREDICTIONS_WITHOUT_QOBS.csv");pred=rr(run/"P3_TEST_PREDICTIONS.csv");seen=set();allgroups=collections.defaultdict(list)
assert len(qfree)==len(pred)==man["test_predictions"] and not any("qobs" in k.lower() for k in qfree[0])
for a,b in zip(qfree,pred):
 assert all(a[k]==b[k] for k in a)
 g=int(b["gauge_id"]);mid=b["model_id"];sid=b["sample_id"];key=(g,mid,sid);assert key not in seen;seen.add(key)
 f=fmap[g];rec=pmaps[g,mid];m=int(b["month"])-1;T=rec["transform"];pa=rec["parameters"]
 assert sid in f["test_ids"] and sid not in f["train_ids"]
 v=np.array([float(fi[sid][k]) for k in rec["fields"]]);mu=np.array(T["monthly_mean"][m]);sd=np.array(T["monthly_sample_std"][m]);con=np.array(T["monthly_constant"][m]);z=np.where(con,0,(v-mu)/np.where(con,1,sd))
 expected=pa["monthly_climatology"][m]+z@pa["beta_standardized"];close(expected,float(b["Qsim_raw_m3s"]));close(max(expected,0),float(b["Qsim_nonnegative_m3s"]));close(float(b["Qobs_m3s"]),float(te[sid]["Q_m3s"]))
 allgroups[g,mid].append(b)
for g,f in fmap.items():
 for mid in pro["models"]:assert {r["sample_id"] for r in allgroups[g,mid]}==set(f["test_ids"])
# Independent exact score recomputation, including yearly unavailable entries.
metric_checks=0
for filename,yearly in [("P3_OVERALL_METRICS.csv",False),("P3_YEARLY_METRICS.csv",True)]:
 for r in rr(run/filename):
  g=int(r["gauge_id"]);rs=allgroups[g,r["model_id"]]
  if yearly:rs=[x for x in rs if x["year"]==r["year"]]
  if not rs:
   assert r["MSE"]=="" and "NO_ADMISSIBLE" in r["NA_reasons"];continue
  y=np.array([float(x["Qobs_m3s"]) for x in rs]);p=np.array([float(x["Qsim_raw_m3s"]) for x in rs]);e=p-y;mse=np.mean(e**2)
  close([mse,np.sqrt(mse),np.mean(abs(e)),100*sum(e)/sum(y)],[float(r[k]) for k in ["MSE","RMSE","MAE","PBIAS"]])
  if np.var(y)>0:close(1-sum(e**2)/sum((y-y.mean())**2),float(r["NSE"]))
  if np.std(y)>0 and np.std(p)>0 and y.mean()!=0:
   rho=np.corrcoef(y,p)[0,1];a=p.std()/y.std();b=p.mean()/y.mean();close(1-np.sqrt((rho-1)**2+(a-1)**2+(b-1)**2),float(r["KGE"]))
  metric_checks+=1

# Secondary, seasonal and flow scores must also recompute from the exact committed rows.
secondary_checks=0
for r in rr(run/"P3_OVERALL_METRICS.csv"):
 rs=allgroups[int(r["gauge_id"]),r["model_id"]];y=np.array([float(x["Qobs_m3s"]) for x in rs]);p=np.maximum(0,np.array([float(x["Qsim_raw_m3s"]) for x in rs]))
 mse=np.mean((p-y)**2);nse=1-np.sum((p-y)**2)/np.sum((y-y.mean())**2);rho=np.corrcoef(y,p)[0,1];a=p.std()/y.std();b=p.mean()/y.mean();kge=1-np.sqrt((rho-1)**2+(a-1)**2+(b-1)**2)
 close([mse,nse,kge],[float(r[k]) for k in ["nonnegative_MSE","nonnegative_NSE","nonnegative_KGE"]]);secondary_checks+=1
subset_checks=0
for filename,kind in [("P3_SEASONAL_METRICS.csv","season"),("P3_FLOW_METRICS.csv","flow")]:
 for r in rr(run/filename):
  rs=allgroups[int(r["gauge_id"]),r["model_id"]]
  if kind=="season":
   period=r["period"];allowed=[int(period[1:])] if period.startswith("M") and period[1:].isdigit() else pro["diagnostics"]["seasons"][period]
   rs=[x for x in rs if int(x["month"]) in allowed]
  else:
   category=r["flow_bin"]
   rs=[x for x in rs if (float(x["Qobs_m3s"])<=float(x["train_Q20"]) if category=="LOW_LE_TRAIN_Q20" else float(x["Qobs_m3s"])>=float(x["train_Q80"]) if category=="HIGH_GE_TRAIN_Q80" else float(x["train_Q20"])<float(x["Qobs_m3s"])<float(x["train_Q80"]))]
  assert len(rs)==int(r["n_months"])
  if not rs:assert r["MSE"]=="";continue
  y=np.array([float(x["Qobs_m3s"]) for x in rs]);p=np.array([float(x["Qsim_raw_m3s"]) for x in rs]);e=p-y
  close([np.mean(e**2),np.mean(abs(e)),np.sqrt(np.mean(e**2)),e.mean()],[float(r[k]) for k in ["MSE","MAE","RMSE","bias"]]);subset_checks+=1

events=jl(B/"fit_events.json")
for e in events:
 f=fmap[e["gauge_id"]]
 if e["level"]=="outer":ids=f["train_ids"];assert e["train_ids_hash"]==ids_hash(ids) and e["n_train"]==len(ids)
 else:
  candidates=[[i for i in f["train_ids"] if int(fi[i]["year"])!=held] for held in f["train_years"]]
  assert any(e["train_ids_hash"]==ids_hash(ids) and e["n_train"]==len(ids) for ids in candidates)
 assert e["status"]=="COMPLETED" and e["model_id"] in pro["models"]
commit=jl(B/"COMMITMENT.json");receipt=jl(run/"TEST_Q_RELEASE_RECEIPT.json");access=jl(run/"data_access_log.json")
assert commit["all_predictions_complete"] and commit["test_Q_loaded"] is False
assert commit["created_UTC"]<=receipt["UTC"] and receipt["prediction_bundle_seal_sha256"]==sha(B/"SHA256SUMS.txt")
assert access[0]["test_labels_loaded"] is False and access[-1]["event"]=="TEST_LABELS_RELEASED_AFTER_ALL_PREDICTIONS_SEALED"
attempts=[json.loads(line) for line in (P/"RUN_ATTEMPTS.jsonl").read_text().splitlines()]
phases=[a["status"] for a in attempts if a["attempt_id"]==man["run_id"]]
assert phases==["STARTED","ALL_PREDICTIONS_SEALED_NO_TEST_Q","TEST_LABELS_RELEASED_FOR_FINAL_SCORING","COMPLETED"]
result.update(status="PASS",all_train_Q_before2005=True,test_Q_loaded_after_global_prediction_commit=True,test_labels_not_registered_for_modeling=True,Q_month_audits_independently_recomputed=Qchecks,MET_months_independently_reaggregated=METchecks,calendar_feature_rows_verified=len(features),test_predictions_recomputed=len(pred),outer_Ridge_optimality_checks=len(pars),inner_training_folds_checked=inner_checks,actual_fit_events_checked=len(events),score_bundles_checked=metric_checks,secondary_score_bundles_checked=secondary_checks,seasonal_flow_score_bundles_checked=subset_checks,full_test_stations=len(split["full120_gauges"]),partial_test_stations=split["partial_test_gauges"],unique_test_months=len(test),duplicate_prediction_ids=0,teacher_Q_access=False)
if (P/"SHA256SUMS.txt").exists():result["delivery_files_verified"]=seal(P)
if "--write-evidence" in sys.argv:
 assert not (P/"SHA256SUMS.txt").exists()
 (P/"P3_VERIFICATION.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

