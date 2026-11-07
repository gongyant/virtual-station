"""P3 descriptive aggregation and P2 comparison, no fits or sample changes."""
import csv,json,collections,shutil
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];R=P.parent;run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_TEMPORAL_P3-"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
met=rr(run/"P3_OVERALL_METRICS.csv");l1=[r for r in met if r["model_id"]=="P2-L1"];base={int(r["gauge_id"]):r for r in met if r["model_id"]=="C0+PT"}
failure={int(r["gauge_id"]):r for r in rr(run/"P3_FAILURE_ANALYSIS.csv")}
scopes={"ALL_SUPPORTED_27":l1,"PRIMARY_COMPLETE_10Y_24":[r for r in l1 if r["support_status"]=="COMPLETE_120_TEST_MONTHS"],"PARTIAL_SUPPORT_ONLY":[r for r in l1 if r["support_status"]!="COMPLETE_120_TEST_MONTHS"],"P2_DEVELOPMENT_9":[r for r in l1 if r["cohort"]=="DEVELOPMENT_9"],"P2_EXTERNAL_18_SAME_SITES":[r for r in l1 if r["cohort"]=="EXTERNAL_FROZEN_NEW"],"P2_EXTERNAL_COMPLETE_16":[r for r in l1 if r["cohort"]=="EXTERNAL_FROZEN_NEW" and r["support_status"]=="COMPLETE_120_TEST_MONTHS"]}
summary=[];regions=[];uncertainty={}
for scope,rows in scopes.items():
 v=np.array([float(r["MSE_skill_vs_C0PT"]) for r in rows]);gs=[int(r["gauge_id"]) for r in rows];macros=sorted(set(r["macro_group"] for r in rows));blocks=[np.array([float(r["MSE_skill_vs_C0PT"]) for r in rows if r["macro_group"]==g]) for g in macros]
 draws=[]
 if len(blocks)>1:
  rng=np.random.default_rng(20261026)
  for _ in range(999):
   ix=rng.integers(0,len(blocks),len(blocks));draws.append(float(np.mean(np.concatenate([blocks[i] for i in ix]))))
  interval=np.quantile(draws,[.025,.975]).tolist();leave=[float(np.mean([float(r["MSE_skill_vs_C0PT"]) for r in rows if r["macro_group"]!=g])) for g in macros]
 else:interval=[None,None];leave=[None]
 clipped=[1-float(r["nonnegative_MSE"])/float(base[int(r["gauge_id"])]["nonnegative_MSE"]) for r in rows]
 summary.append({"scope":scope,"n_stations":len(rows),"n_unique_test_months":sum(int(r["n_test_months"]) for r in rows),"positive_skill_stations":int(np.sum(v>0)),"mean_station_MSE_skill":float(v.mean()),"median_station_MSE_skill":float(np.median(v)),"min_station_skill":float(v.min()),"max_station_skill":float(v.max()),"C0PT_mean_NSE":float(np.mean([float(base[g]["NSE"]) for g in gs])),"L1_mean_NSE":float(np.mean([float(r["NSE"]) for r in rows])),"C0PT_mean_KGE":float(np.mean([float(base[g]["KGE"]) for g in gs])),"L1_mean_KGE":float(np.mean([float(r["KGE"]) for r in rows])),"mean_improved_year_fraction":float(np.mean([float(failure[g]["fraction_years_improved"]) for g in gs])),"all_year_jackknife_positive_stations":sum(failure[g]["jackknife_all_year_deletions_positive"]=="True" for g in gs),"year_bootstrap95_positive_stations":sum(float(failure[g]["year_bootstrap95_low"])>0 for g in gs),"n_macro_clusters":len(macros),"macro_block_bootstrap95_low":interval[0],"macro_block_bootstrap95_high":interval[1],"leave_one_macro_out_min":min(leave) if leave[0] is not None else None,"leave_one_macro_out_max":max(leave) if leave[0] is not None else None,"nonnegative_mean_station_skill":float(np.mean(clipped)),"nonnegative_positive_stations":sum(x>0 for x in clipped),"uncertainty":"DESCRIPTIVE_ONLY_FEW_UNBALANCED_MACRO_CLUSTERS" if len(blocks)>1 else "N/A_ONLY_ONE_MACRO_CLUSTER"})
 uncertainty[scope]={"macro_labels":macros,"macro_site_counts":[len(b) for b in blocks],"macro_skill_means":[float(b.mean()) for b in blocks],"cluster_bootstrap_repetitions":999 if draws else 0,"resampling_unit":"MACRO_RIVER_KEEP_RELATED_SITES_TOGETHER","point_estimand":"basin equally weighted normalized skill, no pooling raw squared errors","interval":interval,"leave_macro_out":leave}
 for typ in ["macro_group","region"]:
  for group in sorted(set(r[typ] for r in rows)):
   subset=[r for r in rows if r[typ]==group];ids=[int(r["gauge_id"]) for r in subset];vv=np.array([float(r["MSE_skill_vs_C0PT"]) for r in subset])
   regions.append({"scope":scope,"group_type":typ,"group":group,"n_stations":len(subset),"station_ids":"|".join(str(g) for g in ids),"positive_skill_stations":int(np.sum(vv>0)),"mean_station_MSE_skill":float(vv.mean()),"median_station_MSE_skill":float(np.median(vv)),"C0PT_mean_NSE":float(np.mean([float(base[g]["NSE"]) for g in ids])),"L1_mean_NSE":float(np.mean([float(r["NSE"]) for r in subset])),"related_stations_not_independent":True})
cw(P/"P3_COHORT_SUMMARY.csv",summary);cw(P/"P3_REGION_SUMMARY.csv",regions)
(P/"reports/P3_MACRO_BLOCK_UNCERTAINTY.json").write_text(json.dumps(uncertainty,indent=2),encoding="utf-8")
yearly=rr(run/"P3_YEARLY_METRICS.csv");seasons=rr(run/"P3_SEASONAL_METRICS.csv");flows=rr(run/"P3_FLOW_METRICS.csv")
diags=[];yearsumm=[]
for scope,rs in scopes.items():
 ids={r["gauge_id"] for r in rs}
 for year in range(2005,2015):
  rows=[r for r in yearly if r["gauge_id"] in ids and r["model_id"]=="P2-L1" and int(r["year"])==year and r["MSE_skill_vs_C0PT"]!=""]
  values=[float(r["MSE_skill_vs_C0PT"]) for r in rows]
  yearsumm.append({"scope":scope,"year":year,"n_stations_with_defined_skill":len(rows),"n_test_months":sum(int(r["n_months"]) for r in rows),"positive_station_count":sum(v>0 for v in values),"mean_station_year_MSE_skill":float(np.mean(values)) if values else None,"median_station_year_MSE_skill":float(np.median(values)) if values else None})
 for kind,arr,field in [("season",seasons,"period"),("flow",flows,"flow_bin")]:
  for subset in sorted(set(r[field] for r in arr)):
   rows=[r for r in arr if r["gauge_id"] in ids and r["model_id"]=="P2-L1" and r[field]==subset and r["MSE_skill_vs_C0PT"]!=""]
   v=[float(r["MSE_skill_vs_C0PT"]) for r in rows]
   diags.append({"scope":scope,"diagnostic_type":kind,"subset":subset,"n_stations":len(rows),"positive_station_count":sum(z>0 for z in v),"mean_station_skill":float(np.mean(v)) if v else None,"median_station_skill":float(np.median(v)) if v else None})
cw(P/"P3_YEAR_SKILL_SUMMARY.csv",yearsumm);cw(P/"P3_SEASON_FLOW_SUMMARY.csv",diags)
# Compare same station sets with historical P2 references, no P2 refit; expanded training differs.
old=rr(R/"p2_antecedent_snow_features/P2_MODEL_COMPARISON.csv");lookup={(int(r["gauge_id"]),r["scenario"]):r for r in old if r["candidate"]=="P2-L1"}
comparison=[]
for row in l1:
 g=int(row["gauge_id"])
 for scenario in ["CONSECUTIVE_10Y","SPARSE_10Y_PUBLIC_SUBSAMPLING"]:
  o=lookup[g,scenario];oldskill=float(o["MSE_skill"]);newskill=float(row["MSE_skill_vs_C0PT"])
  comparison.append({"gauge_id":g,"cohort":row["cohort"],"macro_group":row["macro_group"],"P3_support_status":row["support_status"],"P2_scenario":scenario,"P2_MSE_skill":oldskill,"P3_MSE_skill":newskill,"P3_minus_P2_skill":newskill-oldskill,"P3_train_months":row["n_train_months"],"P3_test_months":row["n_test_months"],"comparison_limit":"DIFFERENT_TARGET_PERIOD_AND_MORE_TRAINING_DATA_NOT_ISOLATED_TIME_EFFECT"})
cw(P/"P3_VS_P2_COMPARISON.csv",comparison)
compsummary=[]
for scope,rows in scopes.items():
 ids={r["gauge_id"] for r in rows}
 for scenario in ["CONSECUTIVE_10Y","SPARSE_10Y_PUBLIC_SUBSAMPLING"]:
  rs=[r for r in comparison if str(r["gauge_id"]) in ids and r["P2_scenario"]==scenario]
  compsummary.append({"scope":scope,"P2_scenario":scenario,"n_same_stations":len(rs),"P2_mean_station_skill":float(np.mean([r["P2_MSE_skill"] for r in rs])),"P3_mean_station_skill":float(np.mean([r["P3_MSE_skill"] for r in rs])),"mean_skill_change":float(np.mean([r["P3_minus_P2_skill"] for r in rs])),"n_stations_P3_skill_greater":sum(r["P3_minus_P2_skill"]>0 for r in rs)})
cw(P/"P3_VS_P2_SUMMARY.csv",compsummary)
# Summarize covariate extrapolation without changing any feature or prediction.
ext=rr(run/"prediction_bundle/FEATURE_EXTRAPOLATION.csv");xgroups=collections.defaultdict(list)
for r in ext:xgroups[int(r["gauge_id"]),r["model_id"],r["feature"]].append(r)
xsum=[]
for (g,mid,feature),rs in xgroups.items():
 z=np.array([float(r["standardized_test_anomaly"]) for r in rs]);worst=rs[int(np.argmax(abs(z)))]
 xsum.append({"gauge_id":g,"model_id":mid,"feature":feature,"n_test_months":len(rs),"mean_standardized_test_anomaly":float(z.mean()),"max_abs_standardized_test_anomaly":float(max(abs(z))),"max_abs_anomaly_month":worst["sample_id"][-7:],"outside_training_month_range_count":sum(r["outside_train_month_range"]=="True" for r in rs),"train_constant_test_rows":sum(r["train_constant"]=="True" for r in rs),"test_raw_min":min(float(r["raw_test_value"]) for r in rs),"test_raw_max":max(float(r["raw_test_value"]) for r in rs),"beta_standardized":rs[0]["coefficient_m3s_per_train_SD"]})
cw(P/"P3_EXTRAPOLATION_SUMMARY.csv",xsum)
audit=rr(P/"P3_TEMPORAL_SUPPORT_AUDIT.csv");cw(P/"P3_EXCLUDED_TEST_MONTHS.csv",[r for r in audit if r["period"]=="TEST" and r["common_admissible"]=="False"])
for name in ["P3_TEST_PREDICTIONS.csv","P3_OVERALL_METRICS.csv","P3_YEARLY_METRICS.csv","P3_FAILURE_ANALYSIS.csv","P3_SEASONAL_METRICS.csv","P3_FLOW_METRICS.csv","P3_ERROR_CONCENTRATION.csv","P3_MONTHLY_Q_DRIFT.csv","P3_RUN_MANIFEST.json"]:shutil.copyfile(run/name,P/name)
for scope in ["PRIMARY_COMPLETE_10Y_24","PARTIAL_SUPPORT_ONLY"]:
 dest=P/"reports"/scope;dest.mkdir(exist_ok=True);ids={r["gauge_id"] for r in scopes[scope]}
 for name in ["P3_OVERALL_METRICS.csv","P3_YEARLY_METRICS.csv","P3_FAILURE_ANALYSIS.csv"]:cw(dest/name,[r for r in rr(run/name) if r["gauge_id"] in ids])
print(json.dumps(summary,indent=2))
print("P2_COMPARISON",json.dumps(compsummary,indent=2))
print("PRIMARY_YEAR_RESULTS",json.dumps([r for r in yearsumm if r["scope"]=="PRIMARY_COMPLETE_10Y_24"],indent=2))
print("PRIMARY_SEASON_FLOW",json.dumps([r for r in diags if r["scope"]=="PRIMARY_COMPLETE_10Y_24" and r["subset"] in ["DJF","MAY_JUN","LOW_LE_TRAIN_Q20","HIGH_GE_TRAIN_Q80"]],indent=2))

