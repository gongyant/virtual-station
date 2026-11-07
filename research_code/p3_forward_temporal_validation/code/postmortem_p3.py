import csv,json,collections,numpy as np
from pathlib import Path
P=Path(__file__).parents[1];r=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_"))
def rr(path):
 with path.open() as f:return list(csv.DictReader(f))
pred=rr(r/"P3_TEST_PREDICTIONS.csv");split=json.loads((P/"P3_SPLIT_FROZEN.json").read_text());full=set(split["full120_gauges"]);idx={(int(x["gauge_id"]),x["model_id"],x["sample_id"]):x for x in pred};out=[]
for g in sorted(full):
 rows=[x for x in pred if int(x["gauge_id"])==g and x["model_id"]=="P2-L1" and x["year"]=="2012"];den=sum((float(idx[g,"C0+PT",x["sample_id"]]["Qsim_raw_m3s"])-float(x["Qobs_m3s"]))**2 for x in rows)
 for x in rows:
  b=idx[g,"C0+PT",x["sample_id"]];y=float(x["Qobs_m3s"]);bp=float(b["Qsim_raw_m3s"]);lp=float(x["Qsim_raw_m3s"]);out.append({"gauge_id":g,"month":int(x["month"]),"normalized_annual_skill_contribution":((bp-y)**2-(lp-y)**2)/den,"baseline_error_m3s":bp-y,"L1_error_m3s":lp-y})
def cw(path,rows):
 with path.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
cw(P/"P3_2012_MONTH_CONTRIBUTIONS.csv",out)
print("2012_CONTRIBUTIONS",[(m,np.mean([x["normalized_annual_skill_contribution"] for x in out if x["month"]==m])) for m in range(1,13)])
yearly=rr(r/"P3_YEARLY_METRICS.csv");bad=[x for x in yearly if x["model_id"]=="P2-L1" and x["MSE_skill_vs_C0PT"] and float(x["MSE_skill_vs_C0PT"])<0];cw(P/"P3_NEGATIVE_YEAR_CASES.csv",bad)
print("negative_year_cases",len(bad),"full",sum(int(x["gauge_id"]) in full for x in bad))
print("params_alpha",collections.Counter((x["model_id"],x["record"]["parameters"]["selection"]["selected_alpha"]) for x in json.loads((r/"prediction_bundle/model_parameters.json").read_text())))
x=rr(P/"P3_EXTRAPOLATION_SUMMARY.csv");temps=[float(z["mean_standardized_test_anomaly"]) for z in x if z["model_id"]=="P2-L1" and z["feature"]=="T"]
print("temp_mean_z",np.mean(temps),"positive_count",sum(x>0 for x in temps))
print("constant_months",collections.Counter(z["constant_months"] for z in rr(r/"prediction_bundle/MODEL_SUPPORT.csv")))
print("min_calendar_train_years",min(min(z["training_year_support_per_month"].values()) for z in split["splits"]))

