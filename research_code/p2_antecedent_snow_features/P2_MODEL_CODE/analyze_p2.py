"""Post-fit aggregation: equal-basin skills, river-block uncertainty and fixed diagnostics."""
import csv,json,hashlib,collections,shutil
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];R=P.parent;run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_EXPLORATORY_P2-"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
comp=rr(run/"P2_MODEL_COMPARISON.csv");overall=rr(run/"P2_OVERALL_METRICS.csv");season=rr(run/"P2_SEASONAL_DIAGNOSTICS.csv");flow=rr(run/"P2_FLOW_DIAGNOSTICS.csv");pred=rr(run/"P2_OOF_PREDICTIONS.csv");pars=jl(run/"model_parameters.json")
groups=collections.defaultdict(list)
for r in comp:groups[r["cohort"],r["scenario"],r["candidate"]].append(r)
summary=[];regions=[];macrodetail={}
for (cohort,ex,mid),rows in groups.items():
 skills=np.array([float(r["MSE_skill"]) for r in rows]);macros=sorted(set(r["macro_group"] for r in rows))
 arrays=[np.array([float(r["MSE_skill"]) for r in rows if r["macro_group"]==mac]) for mac in macros]
 rng=np.random.default_rng(20261026);draws=[];drawsmacro=[]
 for _ in range(999):
  ix=rng.integers(0,len(macros),len(macros));draws.append(float(np.mean(np.concatenate([arrays[i] for i in ix]))));drawsmacro.append(float(np.mean([arrays[i].mean() for i in ix])))
 leave=[float(np.mean([float(r["MSE_skill"]) for r in rows if r["macro_group"]!=mac])) for mac in macros]
 q=np.quantile(draws,[.025,.975]);mq=np.quantile(drawsmacro,[.025,.975])
 summary.append({"cohort":cohort,"scenario":ex,"candidate":mid,"n_basins":len(rows),"equal_basin_mean_MSE_skill":float(skills.mean()),"equal_basin_median_MSE_skill":float(np.median(skills)),"positive_basin_count":int(np.sum(skills>0)),"positive_basin_fraction":float(np.mean(skills>0)),"mean_fraction_years_improved":float(np.mean([float(r["fraction_years_improved"]) for r in rows])),"jackknife_positive_all_year_deletions_count":sum(r["jackknife_all_deletions_positive"]=="True" for r in rows),"year_bootstrap95_entirely_positive_basins":sum(float(r["bootstrap95_low"])>0 for r in rows),"n_macro_clusters":len(macros),"river_block_bootstrap_basin_weighted95_low":float(q[0]),"river_block_bootstrap_basin_weighted95_high":float(q[1]),"macro_equal_mean_skill":float(np.mean([x.mean() for x in arrays])),"macro_equal_bootstrap95_low":float(mq[0]),"macro_equal_bootstrap95_high":float(mq[1]),"leave_one_macro_out_min_mean_skill":min(leave),"leave_one_macro_out_max_mean_skill":max(leave),"uncertainty_status":"DESCRIPTIVE_ONLY_THREE_UNBALANCED_DEPENDENT_CLUSTERS"})
 for category in ["macro_group","region"]:
  for group in sorted(set(r[category] for r in rows)):
   rs=[r for r in rows if r[category]==group];v=np.array([float(r["MSE_skill"]) for r in rs])
   regions.append({"cohort":cohort,"scenario":ex,"candidate":mid,"group_type":category,"group":group,"n_basins":len(rs),"mean_MSE_skill":float(v.mean()),"median_MSE_skill":float(np.median(v)),"positive_basins":int(np.sum(v>0)),"inference":"RELATED_SITES_NOT_INDEPENDENT_REPLICATION"})
 macrodetail["|".join([cohort,ex,mid])]={"macro_labels":macros,"macro_site_counts":[len(x) for x in arrays],"macro_means":[float(x.mean()) for x in arrays],"leave_one_macro_out_means":leave,"seed":20261026,"repetitions":999}
cw(P/"P2_COHORT_SUMMARY.csv",summary);cw(P/"P2_REGION_SUMMARY.csv",regions)
(P/"reports/P2_RIVER_BLOCK_UNCERTAINTY.json").write_text(json.dumps(macrodetail,indent=2),encoding="utf-8")
# Conditional same-row seasonal/flow skill. No change to fitted models.
diagnostic=[]
for kind,rs,field in [("season",season,"period"),("flow",flow,"flow_bin")]:
 index={(r["cohort"],r["scenario"],r["gauge_id"],r["model_id"],r[field]):r for r in rs}
 for r in rs:
  if r["model_id"]=="C0+PT":continue
  base=index[r["cohort"],r["scenario"],r["gauge_id"],"C0+PT",r[field]]
  assert r["n"]==base["n"]
  den=float(base["MSE"]) if base["MSE"] else 0
  diagnostic.append({"cohort":r["cohort"],"scenario":r["scenario"],"gauge_id":r["gauge_id"],"candidate":r["model_id"],"diagnostic_type":kind,"subset":r[field],"n_months":r["n"],"baseline_MSE":base["MSE"],"candidate_MSE":r["MSE"],"MSE_skill":1-float(r["MSE"])/den if den>1e-24 else None,"reason":"OK" if den>1e-24 else "ZERO_BASELINE_OR_EMPTY"})
cw(P/"P2_DIAGNOSTIC_COMPARISONS.csv",diagnostic)
diag_summary=[]
for co,ex,mid in groups:
 for typ,subset in [("season","MAY_JUN"),("season","DJF"),("flow","LOW_Q_LE_TRAIN_Q20"),("flow","HIGH_Q_GE_TRAIN_Q80")]:
  rr2=[r for r in diagnostic if (r["cohort"],r["scenario"],r["candidate"],r["diagnostic_type"],r["subset"])==(co,ex,mid,typ,subset) and r["MSE_skill"] is not None]
  v=[r["MSE_skill"] for r in rr2]
  diag_summary.append({"cohort":co,"scenario":ex,"candidate":mid,"subset":subset,"n_basins_with_defined_skill":len(v),"mean_skill":float(np.mean(v)) if v else None,"median_skill":float(np.median(v)) if v else None,"positive_basins":sum(x>0 for x in v)})
cw(P/"P2_DIAGNOSTIC_SUMMARY.csv",diag_summary)
# Inspect statistical proxy support/extrapolation; never trim, clip anomalies or refit.
source={r["sample_id"]:r for r in rr(P/"source/monthly_labels_features.csv")};pi={(x["cohort"],x["scenario"],x["gauge_id"],x["fold_id"],x["record"]["model_id"]):x["record"] for x in pars};fi={(x["cohort"],x["scenario"],x["gauge_id"],x["fold_id"]):x for x in jl(run/"folds.json")}
extra=[];extreme=[]
for p in pred:
 if p["model_id"]!="P2-SNOW":continue
 rec=pi[p["cohort"],p["scenario"],int(p["gauge_id"]),p["fold_id"],"P2-SNOW"];tr=rec["transform"];mo=int(p["month"])-1;row=source[p["sample_id"]];fold=fi[p["cohort"],p["scenario"],int(p["gauge_id"]),p["fold_id"]]
 for name in ["S","M"]:
  z=rec["fields"].index(name);mu=tr["monthly_mean"][mo][z];sd=tr["monthly_sample_std"][mo][z];const=tr["monthly_constant"][mo][z];raw=float(row[name])
  trainvals=[float(source[i][name]) for i in fold["train_ids"] if int(source[i]["month"])==int(p["month"])]
  anomaly=0 if const else (raw-mu)/sd
  extra.append({"cohort":p["cohort"],"scenario":p["scenario"],"gauge_id":p["gauge_id"],"sample_id":p["sample_id"],"held_year":p["year"],"month":p["month"],"feature":name,"raw_value":raw,"train_month_mean":mu,"train_month_sample_std":sd,"train_constant":const,"used_standardized_anomaly":anomaly,"train_month_min":min(trainvals),"train_month_max":max(trainvals),"outside_train_month_range":raw<min(trainvals) or raw>max(trainvals),"coefficient_m3s_per_train_SD":rec["parameters"]["beta_standardized"][z],"contribution_m3s":anomaly*rec["parameters"]["beta_standardized"][z]})
cw(P/"P2_PROXY_EXTRAPOLATION.csv",extra)
response=[]
for cohort,ex,g,mid in sorted(set((r["cohort"],r["scenario"],r["gauge_id"],r["model_id"]) for r in pred)):
 rows=[r for r in pred if (r["cohort"],r["scenario"],r["gauge_id"],r["model_id"])==(cohort,ex,g,mid)];v=np.array([float(r["current_T_plus1_conditional_response_m3s"]) for r in rows])
 response.append({"cohort":cohort,"scenario":ex,"gauge_id":g,"model_id":mid,"conditional_current_T_plus1_response_min_m3s":float(v.min()),"median_m3s":float(np.median(v)),"max_m3s":float(v.max()),"fraction_response_positive":float(np.mean(v>0)),"interpretation":"COORDINATE_RESPONSE_WITH_M_RECOMPUTED_AND_PAST_WEATHER_FIXED_NOT_CAUSAL"})
cw(P/"P2_RESPONSE_SUMMARY.csv",response)
# Expose requested exact files at delivery root, sealed run unchanged.
for f in run.glob("P2_*.csv"):shutil.copyfile(f,P/f.name)
for cohort in ["DEVELOPMENT_9","EXTERNAL_FROZEN_NEW"]:
 dest=P/"reports"/cohort;dest.mkdir(exist_ok=True)
 for name in ["P2_OVERALL_METRICS.csv","P2_YEARLY_METRICS.csv","P2_MODEL_COMPARISON.csv","P2_SEASONAL_DIAGNOSTICS.csv"]:
  cw(dest/name,[r for r in rr(run/name) if r["cohort"]==cohort])
print(json.dumps(summary,indent=2))
print("DIAGNOSTIC_SUMMARY",json.dumps(diag_summary,indent=2))

