import calendar,collections,csv,json,math,hashlib
from datetime import date,datetime,timezone
from pathlib import Path
R=Path(r"E:\VHS_Public_Baseline_Lab");P=R/"p1_seasonal_meteorology_ablation"
def load(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def jw(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
def cw(p,rr):
 with p.open("w",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def read(p):
 with p.open(encoding="utf-8-sig") as f:return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=";")]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rule=load(P/"source/NEW_BASIN_SELECTION_RULE.json");years=set(sum(rule["windows"].values(),[]));D=P/"source/daily";M=P/"source/metadata"
gauges={int(r["ID"]):r for r in read(M/"D_gauges/1_attributes/Gauge_attributes.csv")}
attrs={int(r["ID"]):r for r in read(M/"A_basins_total_upstrm/1_attributes/Catchment_attributes.csv")}
hier={int(r["ID"]):r for r in read(M/"B_basins_intermediate_all/1_attributes/Gauge_hierarchy.csv")}
transfers=read(M/"B_basins_intermediate_all/1_attributes/Crossbasin_water_transfers.csv")
def downstream(i):
 seen=set()
 while i in hier:
  n=int(hier[i]["NEXTDOWNID"] or -1)
  if n<=0:break
  assert n not in seen,"CYCLE"
  seen.add(n);i=n
 return seen
def value(x):
 try:v=float(x)
 except ValueError:return None
 return v if math.isfinite(v) and v!=-999 else None
def daily(path):
 data={};dup=set()
 for r in read(path):
  y=int(r["YYYY"])
  if y not in years:continue
  dt=date(y,int(r["MM"]),int(r["DD"]))
  if "DOY" in r:assert int(r["DOY"])==dt.timetuple().tm_yday
  if dt in data:dup.add(dt)
  data[dt]=r
 return data,dup
selected=[];evidence=[];output=[]
for slot in rule["slots"]:
 chosen=None
 for i in slot["candidate_ids_ranked"]:
  q,qd=daily(D/f"D_gauges/2_timeseries/daily/ID_{i}.csv");met,md=daily(D/f"A_basins_total_upstrm/2_timeseries/daily/ID_{i}.csv")
  rr=[];bad=[]
  for y in sorted(years):
   for m in range(1,13):
    days=calendar.monthrange(y,m)[1];qs=[];ps=[];ts=[];eq=col=0
    for d in range(1,days+1):
     dt=date(y,m,d);qr=q.get(dt);mr=met.get(dt)
     if qr:
      v=value(qr["qobs"]);eq+=qr["qceq"]=="1";col+=qr["qcol"]=="1"
      if v is not None and v>=0 and qr["ckhs"]=="1" and dt not in qd:qs.append(v)
     if mr and dt not in md:
      p,t=value(mr["prec"]),value(mr["2m_temp_mean"])
      if p is not None and p>=0:ps.append(p)
      if t is not None:ts.append(t)
    counts={"expected_days":days,"Q_valid_days":len(qs),"P_valid_days":len(ps),"T_valid_days":len(ts)}
    if not len(qs)==len(ps)==len(ts)==days:bad.append({"year":y,"month":m,**counts});continue
    station=f"LAMAH_CE_PUBLIC_V1:{i}"
    rr.append({"sample_id":f"{station}:{y:04d}-{m:02d}","station_id":station,"gauge_id":i,"year":y,"month":m,"Q_m3s":sum(qs)/days,"P_mm":sum(ps),"T_C":sum(ts)/days,**counts,"qceq_flagged_days":eq,"qcol_flagged_days":col,"complete":True,"timezone":"UTC","source_kind":"PUBLIC_OBSERVED_GAUGE_Q_AND_ERA5LAND"})
  conflicts=[j for j in [2,6,9]+selected if i in downstream(j) or j in downstream(i)]
  status="ACCEPT" if not bad and not conflicts else "REJECT_INCOMPLETE" if bad else "REJECT_NESTED"
  evidence.append({"slot":slot["region"],"gauge_id":i,"status":status,"n_admitted_months":len(rr),"bad_months":bad,"nested_conflicts":conflicts,"scores_seen":False})
  print(i,status,len(rr),flush=True)
  if status=="ACCEPT":chosen=i;selected.append(i);output.extend(rr);break
 if chosen is None:print("UNFILLED",slot["region"])
assert len(selected)>=4
with (R/"source/monthly_admitted.csv").open(encoding="utf-8") as f:old=list(csv.DictReader(f))
for r in old:
 for n in ("gauge_id","year","month","expected_days","Q_valid_days","P_valid_days","T_valid_days","qceq_flagged_days","qcol_flagged_days"):r[n]=int(r[n])
 for n in ("Q_m3s","P_mm","T_C"):r[n]=float(r[n])
 r["complete"]=r["complete"]=="True"
output=old+output
cw(P/"source/monthly_admitted.csv",output)
membership={str(i):"EXPLORATORY_ORIGINAL_3" if i in [2,6,9] else "FROZEN_NEW_BASINS" for i in [2,6,9]+selected}
selected_info=[{"gauge_id":i,**gauges[i],"area_calc_km2":attrs[i]["area_calc"],"frac_snow":attrs[i]["frac_snow"],"p_season":attrs[i]["p_season"],"downstream_path":sorted(downstream(i)),"macro_dependency_cluster":"Elbe" if gauges[i]["region"]=="Vltava" else "Danube"} for i in selected]
all_ids=[2,6,9]+selected
pairs=[{"a":i,"b":j,"a_upstream_of_b":j in downstream(i),"b_upstream_of_a":i in downstream(j),"same_official_region":gauges[i]["region"]==gauges[j]["region"]} for z,i in enumerate(all_ids) for j in all_ids[z+1:]]
# Transfer paths can link non-nested watersheds; include any edge touching selected upstream closures.
up={i:{k for k in hier if i==k or i in downstream(k)} for i in all_ids}
related=[]
for t in transfers:
 a,b=int(t["ID"]),int(t["To_ID"])
 for i in all_ids:
  for j in all_ids:
   if i!=j and a in up[i] and b in up[j]:related.append({"from_gauge":i,"to_gauge":j,"official_edge":t})
selection={"label":"PUBLIC_DATA_EXPLORATORY_P1","frozen_UTC":datetime.now(timezone.utc).isoformat(),"selection_rule_sha256":sha(P/"source/NEW_BASIN_SELECTION_RULE.json"),"selected_new_ids":selected,"selected_metadata":selected_info,"candidate_quality_decisions":evidence,"pairwise_ancestry":pairs,"crossbasin_transfer_dependencies":related,"new_model_scores_seen_before_freeze":False,"dependency_limit":"Different official regions do not ensure independence. Five possible Danube groups share macrobasin/climate; Vltava is Elbe. No independent-basin p-value claim."}
jw(P/"NEW_BASIN_SELECTION_FROZEN.json",selection)
protocol=load(R/"protocol.json")
protocol.update(experiment_label="PUBLIC_DATA_EXPLORATORY_P1",models=["C0","H0","E3n","C0+PT"],old_gauge_ids=[2,6,9],new_gauge_ids=selected,cohort_membership=membership,old_reference="Frozen old C0/E3n OOF imported, not refitted; new basins fit all4 once",new_basin_selection_hash=sha(P/"NEW_BASIN_SELECTION_FROZEN.json"),new_basin_selection_rule_hash=sha(P/"source/NEW_BASIN_SELECTION_RULE.json"),model_definitions={"H0":"unpenalized OLS [1,sin(2pi*m/12),cos(2pi*m/12)]","C0+PT":"fixed train monthly Q means + ridge(P_anom,T_anom); train-only monthly means/sample sd; objective sum_squared_residual + alpha sum(beta^2); no intercept changes"},main_comparison="C0+PT vs C0",aux_comparison="E3n vs H0",structure_comparison="H0 vs C0",statistical_unit="year within basin; scenarios overlap and gauges share climate/networks; per-basin descriptive bootstrap999 and jackknife; no pooled independent-site inference",anomaly_definition="Qobs and each prediction minus SAME outer-training C0 month mean; zero anomaly benchmark; anomaly NSE equals skill_vs_C0; Pearson correlation N/A for constant prediction",exploratory_after_viewing_old_scores=True,primary_prediction="raw",secondary_prediction="max(raw,0)",P2_implemented=False,freeze_UTC=datetime.now(timezone.utc).isoformat())
jw(P/"P1_PROTOCOL.json",protocol)
meta={"snapshot_id":"lamah-public-monthly-"+sha(P/"source/monthly_admitted.csv")[:24],"monthly_csv_sha256":sha(P/"source/monthly_admitted.csv"),"n_unique_months":len(output),"all_gauge_ids":all_ids,"new_gauge_ids":selected,"source_archive_sha256":"b692afc817fc7d92c003b3203fa04def9bbc04c3db39fa58b94c37f8d5376dd0","original_monthly_snapshot":load(R/"source/MONTHLY_SNAPSHOT.json"),"extracted_source_hashes":load(P/"source/DAILY_EXTRACTION_HASHES.json"),"metadata_hashes":load(P/"source/METADATA_HASHES.json"),"protocol_sha256":sha(P/"P1_PROTOCOL.json"),"selection_sha256":sha(P/"NEW_BASIN_SELECTION_FROZEN.json"),"created_before_model_fit":True}
jw(P/"source/MONTHLY_SNAPSHOT.json",meta)
jw(P/"evidence/PREFIT_FREEZE.json",{n:sha(P/n) for n in ["P1_PROTOCOL.json","NEW_BASIN_SELECTION_FROZEN.json","source/NEW_BASIN_SELECTION_RULE.json","source/MONTHLY_SNAPSHOT.json","source/monthly_admitted.csv"]})
print(json.dumps({"selected":selected,"unique_months":len(output),"related_transfers":len(related)}))

