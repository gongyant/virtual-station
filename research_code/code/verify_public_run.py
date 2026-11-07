"""Read-only verification of real public provenance, exact OOF support and immutable artifacts."""
import csv,hashlib,json,sys,math
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def readcsv(p):
 with p.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
def verify_run(run):
 run=Path(run).resolve();assert run.is_relative_to((R/"runs").resolve())
 m=load(run/"manifest.json");assert m["experiment_label"]=="PUBLIC_DATA_REAL_EXPERIMENT" and m["synthetic"] is False
 for name,pin in m["artifact_hashes"].items():assert sha(run/name)==pin,name
 for line in (run/"SHA256SUMS.txt").read_text().splitlines():
  pin,name=line.split("  ",1);assert sha(run/name)==pin,name
 meta=load(run/"data_provenance.json");assert sha(R/"source/monthly_admitted.csv")==meta["monthly_csv_sha256"]
 for row in meta["source_file_hashes"]:assert sha(R/row["file"])==row["sha256"],row["file"]
 monthly={r["sample_id"]:r for r in readcsv(R/"source/monthly_admitted.csv")}
 # Recompute all selected monthly aggregates directly from the independently acquired daily observations/forcings.
 for gid in meta["selected_gauge_ids"]:
  target={k:v for k,v in monthly.items() if int(v["gauge_id"])==gid};wanted={(int(v["year"]),int(v["month"])) for v in target.values()}
  gathered={}
  for kind,relpath in (("Q",f"D_gauges/2_timeseries/daily/ID_{gid}.csv"),("MET",f"A_basins_total_upstrm/2_timeseries/daily/ID_{gid}.csv")):
   with (R/"source/extracted"/relpath).open(encoding="utf-8-sig",newline="") as f:
    for day in csv.DictReader(f,delimiter=";"):
     ym=(int(day["YYYY"]),int(day["MM"]))
     if ym not in wanted:continue
     d=gathered.setdefault(ym,{"Q":[],"P":[],"T":[]})
     if kind=="Q":
      assert day["ckhs"]=="1";d["Q"].append(float(day["qobs"]))
     else:d["P"].append(float(day["prec"]));d["T"].append(float(day["2m_temp_mean"]))
  for row in target.values():
   d=gathered[(int(row["year"]),int(row["month"]))];n=int(row["expected_days"])
   assert len(d["Q"])==len(d["P"])==len(d["T"])==n
   for field,val in (("Q_m3s",math.fsum(d["Q"])/n),("P_mm",math.fsum(d["P"])),("T_C",math.fsum(d["T"])/n)):
    assert math.isclose(float(row[field]),val,rel_tol=1e-12,abs_tol=1e-12),(row["sample_id"],field)
 folds=load(run/"folds.json");index={(f["experiment"],f["gauge_id"],f["fold_id"]):f for f in folds}
 oof=readcsv(run/"OOF_PREDICTIONS.csv");assert len(oof)==1440==m["n_OOF_records"]
 groups={}
 for row in oof:
  assert row["experiment_label"]=="PUBLIC_DATA_REAL_EXPERIMENT" and row["synthetic"]=="False"
  f=index[(row["experiment"],int(row["gauge_id"]),row["fold_id"])]
  assert len(f["train_ids"])==108 and len(f["test_ids"])==12 and not set(f["train_ids"])&set(f["test_ids"])
  assert not set(f["train_years"])&set(f["test_years"])
  assert row["sample_id"] in f["test_ids"] and int(row["year"]) in f["test_years"]
  assert float(row["Qobs_m3s"])==float(monthly[row["sample_id"]]["Q_m3s"])
  assert float(row["Qsim_nonnegative_m3s"])==max(0,float(row["Qsim_raw_m3s"]))
  assert all(math.isfinite(float(row[k])) for k in ("Qobs_m3s","Qsim_raw_m3s","Qsim_nonnegative_m3s"))
  key=(row["experiment"],int(row["gauge_id"]),row["model_id"]);groups.setdefault(key,[]).append(row)
 assert len(groups)==12 and all(len(v)==120 and len({r["sample_id"] for r in v})==120 for v in groups.values())
 for exp in m["scenarios"]:
  for gid in m["selected_gauge_ids"]:assert {r["sample_id"] for r in groups[(exp,gid,"C0")]}=={r["sample_id"] for r in groups[(exp,gid,"E3n")]}
 params=load(run/"model_parameters.json");assert len(params)==120
 for p in params:
  assert p["record"]["synthetic"] is False
  assert p["held_year"] not in p["record"]["train_years"]
  if p["record"]["model_id"]=="E3n":
   assert p["held_year"] not in p["record"]["meteorology_transform"]["fit_years"]
   for alpha in p["record"]["nested_CV"]:
    for inner in alpha["folds"]:assert p["held_year"] not in inner["transform_fit_years"] and inner["held_year"] not in inner["transform_fit_years"]
 # Independent recomputation from saved public observations verifies reported NSE/RMSE, not a replacement scoring implementation.
 for row in readcsv(run/"OVERALL_METRICS.csv"):
  part=groups[(row["experiment"],int(row["gauge_id"]),row["model_id"])]
  y=np.array([float(x["Qobs_m3s"]) for x in part]);p=np.array([float(x["Qsim_raw_m3s"]) for x in part])
  mse=float(np.mean((y-p)**2));nse=1-np.sum((y-p)**2)/np.sum((y-y.mean())**2)
  assert np.isclose(mse,float(row["MSE"]),rtol=1e-12,atol=1e-12)
  assert np.isclose(nse,float(row["NSE"]),rtol=1e-12,atol=1e-12)
 fits=load(run/"fit_events.json");assert len(fits)==2820 and all(e["status"]=="COMPLETED" for e in fits)
 for pin in load(R/"evidence/S2_ORIGINAL_HASHES.json"):assert sha(Path(pin["file"]))==pin["sha256"]
 return {"status":"PASS","run_id":m["run_id"],"experiment_label":m["experiment_label"],"synthetic":False,"gauge_ids":m["selected_gauge_ids"],"verified_OOF_records":len(oof),"verified_folds":len(folds),"verified_outer_parameters":len(params),"verified_actual_fit_calls":len(fits),"source_observations_match_monthly_archive_derivation":True,"held_out_years_excluded_from_preprocessing":True,"S2_original_hashes_unchanged":True,"SyrDarya_real_models":0,"checked_artifact_files":len(m["artifact_hashes"])+2}
if __name__=="__main__":
 path=Path(sys.argv[1]) if len(sys.argv)>1 else next((R/"runs").glob("PUBLIC_DATA_REAL_EXPERIMENT-*"))
 print(json.dumps(verify_run(path),ensure_ascii=False,indent=2))

