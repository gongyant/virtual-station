"""Independent no-fit numerical/provenance verification; no respecification/rescoring selection."""
from common import *
bootstrap()
from data import read_labels,features
from inference import load_model
from collections import Counter,defaultdict
commit=P/"runs/PUBLIC_DATA_FINAL_P4_V1/prediction_bundle";verify(commit)
labels,qs=read_labels("2017-12",commit);ff={r["sample_id"]:r for r in features()}
v1=jl(P/"P4_V1_MODEL_MANIFEST.json");v2=jl(P/"P4_V2_MODEL_MANIFEST.json")
assert v1["spec_hash"]==v2["spec_hash"] and v1["snapshot_id"]!=v2["snapshot_id"]
assert jl(P/"evidence/TEST_Q_RELEASE_RECEIPT.json")["UTC"]>jl(commit/"COMMITMENT.json")["UTC"]
assert jl(P/"evidence/T0_FREEZE.json")["UTC"]<jl(commit/"COMMITMENT.json")["UTC"]
loaded={}
for entry in v1["models"]+v2["models"]:
 m=load_model(entry["path"]);loaded[m.meta["release_version"],entry["gauge_id"],entry["model_id"]]=m
 ids=m.meta["train_ids"];assert len(set(ids))==len(ids) and all(i[-7:]<=m.meta["train_cutoff"] for i in ids)
 rows=[ff[i] for i in ids];y=np.array([labels[i] for i in ids]);mo=np.array([r["month"] for r in rows]);raw=np.array([[r[k] for k in m.fields] for r in rows]);a=m.arrays
 for month in range(1,13):
  ix=mo==month
  assert np.allclose(a["climate"][month-1],y[ix].mean(),atol=1e-12)
  assert np.allclose(a["mu"][month-1],raw[ix].mean(axis=0),atol=1e-12)
  assert np.allclose(a["sd"][month-1],raw[ix].std(axis=0,ddof=1),atol=1e-12)
 z=np.where(a["constant"][mo-1],0,(raw-a["mu"][mo-1])/np.where(a["constant"][mo-1],1,a["sd"][mo-1]));alpha=m.meta["parameters"]["selection"]["selected_alpha"]
 # Independent closed normal-equation solution verifies frozen SVD fit output.
 beta=np.linalg.solve(z.T@z+alpha*np.eye(len(m.fields)),z.T@(y-a["climate"][mo-1]))
 assert np.allclose(beta,a["beta"],atol=1e-10,rtol=1e-10)
 trace=m.meta["nested_CV"];best=min(trace,key=lambda t:(t["mean_year_MSE_raw"],t["alpha"]));cut=best["mean_year_MSE_raw"]+best["standard_error"];chosen=max(r["alpha"] for r in trace if r["mean_year_MSE_raw"]<=cut+1e-12*max(1,abs(cut)))
 assert chosen==alpha
 for row in trace:
  assert all(max(f["transform_fit_years"])<=int(m.meta["train_cutoff"][:4]) and f["held_year"] not in f["transform_fit_years"] for f in row["folds"])
pred=cr(P/"P4_V1_PREDICTIONS.csv");assert len({(r["sample_id"],r["model_id"]) for r in pred})==len(pred)
errors=defaultdict(list);maxdiff=0
for r in pred:
 g=int(r["gauge_id"]);mid=r["model_id"];m=loaded["V1",g,mid];feature=ff[r["sample_id"]];month=feature["month"];a=m.arrays;raw=np.array([feature[k] for k in m.fields]);z=np.where(a["constant"][month-1],0,(raw-a["mu"][month-1])/np.where(a["constant"][month-1],1,a["sd"][month-1]))
 expected=float(a["climate"][month-1]+z@a["beta"]);delta=abs(expected-float(r["q_hat_raw"]));assert delta<=1e-10*max(1,abs(expected));maxdiff=max(maxdiff,delta)
 assert r["sample_id"] not in m.meta["train_ids"]
 errors[g,mid].append((labels[r["sample_id"]],float(r["q_hat_raw"]),float(r["q_hat_nonnegative"])))
metric_checks=0
for r in cr(P/"P4_V1_EVALUATION.csv"):
 vals=errors[int(r["gauge_id"]),r["model_id"]];y=np.array([v[0] for v in vals]);p=np.array([v[1 if r["prediction"]=="raw" else 2] for v in vals]);mse=np.mean((y-p)**2)
 independent={"MSE":mse,"RMSE":np.sqrt(mse),"MAE":np.mean(abs(y-p)),"NSE":1-np.sum((y-p)**2)/np.sum((y-y.mean())**2),"PBIAS":100*np.sum(p-y)/np.sum(y)}
 corr=np.corrcoef(y,p)[0,1];al=np.std(p)/np.std(y);be=np.mean(p)/np.mean(y);independent.update(KGE=1-np.sqrt((corr-1)**2+(al-1)**2+(be-1)**2),KGE_r=corr,KGE_alpha=al,KGE_beta=be)
 for k,v in independent.items():assert np.isclose(float(r[k]),v,rtol=1e-11,atol=1e-11);metric_checks+=1
nfolds=0
for version in ["V1","V2"]:
 folds=jl(P/f"runs/PUBLIC_DATA_FINAL_P4_{version}/crossfit_parameters.json")
 for f in folds:
  assert set(f["actual_train_ids"]).isdisjoint(f["fold"]["test_ids"]);assert len(f["fold"]["test_ids"])==f["fold"]["length"]
  assert all(i[-7:]<=("2014-12" if version=="V1" else "2017-12") for i in f["actual_train_ids"]);nfolds+=1
 rows=cr(P/f"runs/PUBLIC_DATA_FINAL_P4_{version}/PSEUDOGAP_PREDICTIONS.csv");cal=jl(P/f"runs/PUBLIC_DATA_FINAL_P4_{version}/calibration.json")
 for key,sc in cal.items():
  g,mid=key.split("|")
  for ss,c in sc.items():
   residual=np.array([float(r["prediction"])-float(r["Qobs"]) for r in rows if r["gauge_id"]==g and r["model_id"]==mid and r["primary"]=="True" and season(int(r["date"][5:]))==ss])
   assert np.isclose(c["OOF_RMSE"],np.sqrt(np.mean(residual**2)),atol=1e-12)
   assert c["n_OOF_primary12"]==len(residual)
   if c["status"]=="CALIBRATED":
    for level in [80,90]:
     rank=math.ceil((len(residual)+1)*level/100);half=np.sort(abs(residual))[rank-1]*c["kappa"];assert np.isclose(c[f"halfwidth{level}"],half,rtol=1e-12)
meta=cr(P/"P4_OBSERVATION_STATUS_LEDGER.csv")
assert len({r["sample_id"] for r in meta})==len(meta)
assert all(not (r["observation_status"]=="MISSING_TRUE" and int(r["days_present"])>0) for r in meta)
for path,h in jl(P/"source/SNAPSHOT.json")["source_files"].items():assert sha(path)==h
historical={str(root):{"verified_files":verify(root),"seal_sha256":sha(root/"SHA256SUMS.txt")} for root in [R,R/"p1_seasonal_meteorology_ablation",P2,P3]}
before=jl(P/"evidence/HISTORICAL_FREEZE_BEFORE.json")
assert all(historical[k]["seal_sha256"]==before[k]["seal_sha256"] for k in before)
jw(P/"evidence/HISTORICAL_FREEZE_AFTER.json",historical)
result={"UTC":now(),"all_pass":True,"actual_models_independently_checked":len(loaded),"V1_predictions_recomputed":len(pred),"max_prediction_absolute_difference":maxdiff,"metric_cells_independently_recomputed":metric_checks,"masked_outer_folds_checked":nfolds,"train_test_overlap":0,"test_prediction_duplicates":0,"source_Qobs_prediction_columns":0,"historical_freezes_unchanged":True,"source_daily_files_verified":54,"not_new_scientific_evaluation":"verification of frozen numbers only; no fitting/model selection"}
jw(P/"P4_VERIFICATION.json",result);attempt("INDEPENDENT_VERIFICATION_PASS",**result);print(json.dumps(result))
