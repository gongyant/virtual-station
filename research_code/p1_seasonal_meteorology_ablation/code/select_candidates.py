import csv,json,math,tarfile,hashlib
from pathlib import Path
R=Path(r"E:\VHS_Public_Baseline_Lab");P=R/"p1_seasonal_meteorology_ablation";M=P/"source/metadata"
def read(n):
 with (M/n).open(encoding="utf-8-sig") as f:return {int(r["ID"]):{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=";")}
g=read("D_gauges/1_attributes/Gauge_attributes.csv");a=read("A_basins_total_upstrm/1_attributes/Catchment_attributes.csv")
slots=[("Drava",100,1000,.35,1,400),("Inn above Salzach",10,100,.3,1,50),("Enns",100,1000,.15,.35,300),("Danube above Inn",1000,50000,0,.15,10000),("Raab",100,1000,0,.15,500),("Vltava",10,1000,0,.2,200)]
ranking=[]
for region,lo,hi,slo,shi,target in slots:
 ids=[i for i in a if i in g and g[i]["region"]==region and g[i]["country"] in ["AUT","DEU","CHE"] and g[i]["degimpact"]=="l" and int(g[i]["obsbeg_day"])<=1983 and lo<=float(a[i]["area_calc"])<hi and slo<=float(a[i]["frac_snow"])<shi]
 ids.sort(key=lambda i:(abs(math.log(float(a[i]["area_calc"])/target)),i))
 ranking.append({"region":region,"area_range_km2":[lo,hi],"snow_fraction_range":[slo,shi],"target_area":target,"candidate_ids_ranked":ids[:4],"candidates":[{"ID":i,"name":g[i]["name"],"river":g[i]["river"],"area":a[i]["area_calc"],"frac_snow":a[i]["frac_snow"]} for i in ids[:4]]})
assert all(x["candidate_ids_ranked"] for x in ranking)
rule={"created_before_new_model_scores":True,"selection_basis":"official metadata only, then unchanged completeness QC; no Q-derived hydro-indices used","slots":ranking,"candidate_tie_rule":"absolute log(area/target), numericID","per_slot":"first complete non-nested candidate in preordered top4, otherwise report slot unfilled, no score based replacements","quality":"same full-day ckhs=1 nonnegative finite Q and full-day P/T as original; qceq/qcol retained diagnostics","windows":{"CONSECUTIVE_10Y":list(range(1990,2000)),"SPARSE_10Y_PUBLIC_SUBSAMPLING":[1983,1987,1990,1994,1996,1999,2000,2001,2002,2004]},"allowed_countries":["AUT","DEU","CHE"],"old_gauges_excluded":[2,6,9],"dependency":"NEXTDOWNID ancestry and crossbasin transfer edges checked after completeness; distinct official regions remain climate-dependent and often share Danube macrobasin"}
(P/"source/NEW_BASIN_SELECTION_RULE.json").write_text(json.dumps(rule,indent=2),encoding="utf-8")
print(json.dumps(ranking,indent=2),flush=True)
wanted=set()
for r in ranking:
 for i in r["candidate_ids_ranked"]:
  wanted.update([f"A_basins_total_upstrm/2_timeseries/daily/ID_{i}.csv",f"D_gauges/2_timeseries/daily/ID_{i}.csv"])
got=[]
with tarfile.open(R/"source/archive/2_LamaH-CE_daily.tar.gz","r|gz") as t:
 for member in t:
  if member.name not in wanted:continue
  assert member.isfile() and ".." not in Path(member.name).parts
  dest=P/"source/daily"/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(t.extractfile(member).read());got.append(member.name)
assert set(got)==wanted
(P/"source/DAILY_EXTRACTION_HASHES.json").write_text(json.dumps({n:hashlib.sha256((P/"source/daily"/n).read_bytes()).hexdigest() for n in got},indent=2),encoding="utf-8")
print("EXTRACTED",len(got))

