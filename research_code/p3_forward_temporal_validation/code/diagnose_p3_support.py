import csv,json,math,collections
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_"))
def rr(path,sep=","):
 with path.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f,delimiter=sep))
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
snap=json.loads((P/"source/SNAPSHOT.json").read_text());excluded=rr(P/"P3_EXCLUDED_TEST_MONTHS.csv");out=[]
for g in sorted(set(int(r["gauge_id"]) for r in excluded)):
 path=next(Path(s) for s in snap["source_files"] if s.replace(chr(92),"/").endswith(f"D_gauges/2_timeseries/daily/ID_{g}.csv"));q=rr(path,";")
 for e in [r for r in excluded if int(r["gauge_id"])==g]:
  y,m=int(e["year"]),int(e["month"]);rs=[r for r in q if int(r["YYYY"])==y and int(r["MM"])==m]
  missing=sum(float(r["qobs"])==-999 or not math.isfinite(float(r["qobs"])) for r in rs);unchecked=sum(r["ckhs"]!="1" for r in rs)
  out.append({"gauge_id":g,"year":y,"month":m,"source_daily_rows":len(rs),"missing_or_nonfinite_Q_days":missing,"unchecked_ckhs_days":unchecked,"admitted_Q_days":int(e["Q_valid_days"]),"exclusion_class":"RAW_Q_PRESENT_BUT_NOT_SOURCE_CHECKED" if missing==0 and unchecked>0 else "MISSING_OR_INVALID_Q_DAYS","not_automatically_a_true_archive_gap":missing==0,"scores_not_computed_for_excluded_month":True})
cw(P/"P3_EXCLUDED_TEST_Q_REASONS.csv",out)
s=json.loads((P/"P3_SPLIT_FROZEN.json").read_text());full={str(g) for g in s["full120_gauges"]};years=rr(run/"P3_YEARLY_METRICS.csv");season=rr(run/"P3_SEASONAL_METRICS.csv");macro={str(x["gauge_id"]):x["macro"] for x in s["splits"]};groupout=[]
for category,rows,key in [("year",years,"year"),("season",season,"period")]:
 for group in ["Rhine","Elbe","Danube"]:
  values=sorted(set(r[key] for r in rows))
  for label in values:
   rs=[r for r in rows if r["gauge_id"] in full and macro[r["gauge_id"]]==group and r["model_id"]=="P2-L1" and r[key]==label and r["MSE_skill_vs_C0PT"]!=""]
   vals=[float(r["MSE_skill_vs_C0PT"]) for r in rs]
   groupout.append({"scope":"PRIMARY_COMPLETE_10Y_24","group":group,"diagnostic_type":category,"period":label,"n_stations":len(vals),"positive_stations":sum(v>0 for v in vals),"mean_station_skill":float(np.mean(vals)) if vals else None,"median_station_skill":float(np.median(vals)) if vals else None})
cw(P/"P3_GROUP_DIAGNOSTICS.csv",groupout)
print("QC_EXCLUSIONS",collections.Counter(r["exclusion_class"] for r in out))
print("GROUP_FAILURES",[r for r in groupout if r["period"] in ["2012","DJF","MAY_JUN"]])

