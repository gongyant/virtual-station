"""Independent arithmetic/source verification; no model fit calls."""
import bootstrap,csv,json,hashlib,calendar,collections,sys
from pathlib import Path
from datetime import date,datetime,timezone
import numpy as np
P=Path(__file__).parents[1];R=P.parent
run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_EXPLORATORY_P1-"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def readsemi(p):
 with p.open(encoding="utf-8-sig") as f:return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=";")]
def seal(root):
 n=0
 for line in (root/"SHA256SUMS.txt").read_text().splitlines():
  h,name=line.split("  ",1);assert sha(root/name)==h,name;n+=1
 return n
def close(a,b):
 assert np.allclose(a,b,rtol=1e-10,atol=1e-10),(a,b)
def cw(p,rows):
 if p.exists():
  assert rr(p)==[{k: "" if v is None else str(v) for k,v in r.items()} for r in rows];return
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
result={"label":"PUBLIC_DATA_EXPLORATORY_P1","created_UTC":datetime.now(timezone.utc).isoformat(),"no_refits_in_verifier":True,"run_files_verified":seal(run),"old_delivery_files_verified":seal(R)}
man=jl(run/"manifest.json");proto=jl(run/"protocol.json");meta=jl(P/"source/MONTHLY_SNAPSHOT.json");selection=jl(P/"NEW_BASIN_SELECTION_FROZEN.json")
assert sha(P/"P1_PROTOCOL.json")==man["protocol_file_sha256"]
assert sha(P/"NEW_BASIN_SELECTION_FROZEN.json")==man["selection_sha256"]
for path,h in jl(run/"code_hashes.json").items():assert sha(Path(path))==h,path
for n,h in man["prefit_freeze"].items():assert sha(P/n)==h
for n,h in jl(P/"source/DAILY_EXTRACTION_HASHES.json").items():assert sha(P/"source/daily"/n)==h
for n,h in jl(P/"source/METADATA_HASHES.json").items():assert sha(P/"source/metadata"/n)==h
# Recompute real monthly means/totals from authorized public raw daily Q/P/T.
monthly=rr(P/"source/monthly_admitted.csv");source={r["sample_id"]:r for r in monthly}
years=set(proto["primary_years"]+proto["sparse_years"]);raw_checks=0
for g in meta["all_gauge_ids"]:
 d=R/"source/extracted" if g in proto["old_gauge_ids"] else P/"source/daily"
 q={};met={};seenq=set();seenm=set()
 for kind,path in [("Q",d/f"D_gauges/2_timeseries/daily/ID_{g}.csv"),("M",d/f"A_basins_total_upstrm/2_timeseries/daily/ID_{g}.csv")]:
  for r in readsemi(path):
   y=int(r["YYYY"])
   if y not in years:continue
   dt=date(y,int(r["MM"]),int(r["DD"]));bucket=q if kind=="Q" else met
   assert dt not in bucket,"DUPLICATE_DATE";bucket[dt]=r
 for y in years:
  for m in range(1,13):
   days=calendar.monthrange(y,m)[1];qs=[];ps=[];ts=[];eq=col=0
   for day in range(1,days+1):
    dt=date(y,m,day);qr=q[dt];mr=met[dt]
    v,p,t=float(qr["qobs"]),float(mr["prec"]),float(mr["2m_temp_mean"])
    assert np.isfinite([v,p,t]).all() and v>=0 and p>=0 and t!=-999 and qr["ckhs"]=="1"
    qs.append(v);ps.append(p);ts.append(t);eq+=qr["qceq"]=="1";col+=qr["qcol"]=="1"
   r=source[f"LAMAH_CE_PUBLIC_V1:{g}:{y:04d}-{m:02d}"]
   close([sum(qs)/days,sum(ps),sum(ts)/days],[float(r[k]) for k in ["Q_m3s","P_mm","T_C"]])
   assert int(r["qceq_flagged_days"])==eq and int(r["qcol_flagged_days"])==col
   assert all(int(r[k])==days for k in ["expected_days","Q_valid_days","P_valid_days","T_valid_days"])
   raw_checks+=1
pred=rr(run/"OOF_PREDICTIONS.csv");pars=jl(run/"model_parameters.json");folds=jl(run/"folds.json");events=jl(run/"fit_events.json")
fmap={(f["experiment"],int(f["gauge_id"]),f["fold_id"]):f for f in folds};pmap={(f["experiment"],int(f["gauge_id"]),f["fold_id"],f["record"]["model_id"]):f for f in pars}
seen=set();param_checks=0;beta_checks=0
from vhs_sci.contracts import ids_hash
for row in pred:
 key=(row["experiment"],int(row["gauge_id"]),row["sample_id"],row["model_id"]);assert key not in seen;seen.add(key)
 fold=fmap[row["experiment"],int(row["gauge_id"]),row["fold_id"]]
 assert row["sample_id"] in fold["test_ids"] and row["sample_id"] not in fold["train_ids"]
 assert int(row["year"]) in fold["test_years"] and int(row["year"]) not in fold["train_years"]
 rec=pmap[row["experiment"],int(row["gauge_id"]),row["fold_id"],row["model_id"]]["record"];pr=rec["parameters"];m=int(row["month"]);v=float(row["Qsim_raw_m3s"]);q=source[row["sample_id"]]
 close(float(row["Qobs_m3s"]),float(q["Q_m3s"]))
 assert rec["train_ids_hash"]==ids_hash(fold["train_ids"])
 train=[source[i] for i in fold["train_ids"]]
 clim=float(np.mean([float(r["Q_m3s"]) for r in train if int(r["month"])==m]))
 close(clim,float(row["training_C0_month_mean_m3s"]))
 mid=row["model_id"]
 if mid=="C0":expected=pr[str(m)]
 elif mid=="H0":expected=float(np.array([1,np.sin(2*np.pi*m/12),np.cos(2*np.pi*m/12)])@pr["coefficients"])
 else:
  stats=rec["meteorology_transform"]["monthly_stats"]
  z=[]
  for name,col in [("P","P_mm"),("T","T_C")]:
   st=stats[f"{name}/{m}"]
   vals=[float(r[col]) for r in train if int(r["month"])==m]
   close([st["mean"],st["sample_std"]],[np.mean(vals),np.std(vals,ddof=1)])
   z.append(0 if st["constant"] else (float(q[col])-st["mean"])/st["sample_std"])
  if mid=="C0+PT":
   close(pr["monthly_climatology"][str(m)],clim)
   expected=clim+float(np.array(z)@pr["beta_P_T"])
  else:expected=float(np.r_[1,np.sin(2*np.pi*m/12),np.cos(2*np.pi*m/12),z]@pr["coefficients"])
 close(expected,v);close(max(v,0),float(row["Qsim_nonnegative_m3s"]));param_checks+=1
for item in pars:
 ex,g,fid=item["experiment"],item["gauge_id"],item["fold_id"];f=fmap[ex,g,fid];rec=item["record"]
 if rec["model_id"] in ["E3n","C0+PT"]:
  assert rec["meteorology_transform"]["fit_ids_hash"]==ids_hash(f["train_ids"])
  assert sorted(rec["meteorology_transform"]["fit_years"])==sorted(f["train_years"])
  trace=rec["nested_CV"]
  assert len(trace)==5
  for a in trace:
   for inner in a["folds"]:
    held=inner["held_year"];ids=[i for i in f["train_ids"] if int(source[i]["year"])!=held]
    assert inner["train_ids_hash"]==inner["transform_fit_ids_hash"]==ids_hash(ids)
    assert set(inner["transform_fit_years"])==set(f["train_years"])-{held}
 # Compare H0 harmonic coefficients to E3n's unpenalized seasonal block.
 if rec["model_id"]=="H0":
  er=pmap[ex,g,fid,"E3n"]["record"]
  close(rec["parameters"]["coefficients"],er["parameters"]["coefficients"][:3]);beta_checks+=1
for e in events:
 f=fmap[e["experiment"],e["gauge_id"],f"LOYO-{e['outer_held_year']}"]
 if e["level"]=="outer":assert e["n_train"]==108 and e["train_ids_hash"]==ids_hash(f["train_ids"])
 else:
  possibilities=[ids_hash([i for i in f["train_ids"] if int(source[i]["year"])!=h]) for h in f["train_years"]]
  assert e["n_train"]==96 and e["train_ids_hash"] in possibilities
 assert e["status"]=="COMPLETED"
# Imported old references remain numerically exact; no replacement model runs.
old=Path(jl(run/"baseline_pins.json")["run"]);oldpred={(r["experiment"],r["gauge_id"],r["sample_id"],r["model_id"]):r for r in rr(old/"OOF_PREDICTIONS.csv")}
imported=0
for p in pred:
 if p["origin"]=="FROZEN_BASELINE_OOF_REFERENCE":
  r=oldpred[p["experiment"],p["gauge_id"],p["sample_id"],p["model_id"]]
  assert float(r["Qsim_raw_m3s"])==float(p["Qsim_raw_m3s"]);imported+=1
# Recompute primary reported scores arithmetically.
groups=collections.defaultdict(list)
for p in pred:groups[p["experiment"],p["gauge_id"],p["model_id"]].append(p)
overall=rr(run/"P1_OVERALL_METRICS.csv")
for r in overall:
 rows=groups[r["experiment"],r["gauge_id"],r["model_id"]];y=np.array([float(x["Qobs_m3s"]) for x in rows]);p=np.array([float(x["Qsim_raw_m3s"]) for x in rows])
 mse=float(np.mean((y-p)**2));nse=1-np.sum((y-p)**2)/np.sum((y-y.mean())**2)
 corr=np.corrcoef(y,p)[0,1];alpha=np.std(p)/np.std(y);beta=p.mean()/y.mean();kge=1-np.sqrt((corr-1)**2+(alpha-1)**2+(beta-1)**2)
 close([mse,nse,kge],[float(r[k]) for k in ["MSE","NSE","KGE"]])
# Establish concentration and bootstrap evidence without any extra model fitting.
details=jl(run/"comparison_details.json");concentration=[]
for k,d in details.items():
 ex,g,comp=k.split("|");delta=np.array(d["year_MSE_improvement"]);total=float(delta.sum());ix=int(np.argmax(delta));jack=d["jackknife"]["leave_one_year_out_estimates"]
 concentration.append({"cohort":d["cohort"],"experiment":ex,"gauge_id":int(g),"comparison":comp,"year_of_largest_improvement":d["years"][ix],"largest_positive_year_signed_share":float(delta[ix]/total) if total>0 else None,"jackknife_min":min(jack),"jackknife_max":max(jack),"bootstrap95_low":d["year_bootstrap"]["percentile_95_interval"][0],"bootstrap95_high":d["year_bootstrap"]["percentile_95_interval"][1],"bootstrap_resampling_unit":"YEAR","confirmatory":False})
cw(P/"P1_YEAR_CONCENTRATION.csv",concentration)
result.update(status="PASS",unique_real_months_reaggregated=raw_checks,OOF_parameter_predictions_recomputed=param_checks,harmonic_coefficient_equivalence_checks=beta_checks,outer_fold_count=len(folds),fold_model_records=len(pars),new_outer_fits=sum(e["level"]=="outer" for e in events),new_inner_fits=sum(e["level"]=="inner" for e in events),imported_old_OOF_exact=imported,new_OOF=len(pred)-imported,all_four_model_OOF=len(pred),train_test_intersections=0,inner_transform_leakage=0,teacher_Q_access=False,model_scores_used_for_new_selection=False,statistical_caveat="per-year bootstrap/sign-flip assumptions not established; no pooled independent-basin significance")
if (P/"SHA256SUMS.txt").exists():result["P1_delivery_files_verified"]=seal(P)
if "--write-evidence" in sys.argv:
 assert not (P/"SHA256SUMS.txt").exists(),"SEALED_DELIVERY_READ_ONLY"
 (P/"REAL_RUN_VERIFICATION.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))

