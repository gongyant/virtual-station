import calendar,csv,json,hashlib,collections
from pathlib import Path
from datetime import date,datetime,timezone
from calendar_features import construct,previous_month
P=Path(__file__).parents[1];R=P.parent;P1=R/"p1_seasonal_meteorology_ablation"
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jw(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
def cw(p,rs):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def readsemi(p):
 with p.open(encoding="utf-8-sig") as f:return [{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=";")]
pro=jl(P/"P2_PROTOCOL.json");years=set(sum(pro["scenarios"].values(),[]));target={(y,m) for y in years for m in range(1,13)};need=target|{previous_month(y,m,k) for y,m in target for k in (1,2,3)}
m=P1/"source/metadata"
g={int(r["ID"]):r for r in readsemi(m/"D_gauges/1_attributes/Gauge_attributes.csv")};a={int(r["ID"]):r for r in readsemi(m/"A_basins_total_upstrm/1_attributes/Catchment_attributes.csv")};h={int(r["ID"]):r for r in readsemi(m/"B_basins_intermediate_all/1_attributes/Gauge_hierarchy.csv")}
def down(i):
 s=set()
 while i in h:
  i=int(h[i]["NEXTDOWNID"] or -1)
  if i<=0:break
  assert i not in s;s.add(i)
 return s
paths={i:down(i) for i in g}
def finite(v):
 try:x=float(v);return x if __import__("math").isfinite(x) and x!=-999 else None
 except (TypeError,ValueError):return None
cache={};used={}
def aggregate(i,old=False):
 if i in cache:return cache[i]
 d=(R/"source/extracted" if i in [2,6,9] else P1/"source/daily") if old else P/"source/daily"
 qp=d/f"D_gauges/2_timeseries/daily/ID_{i}.csv";mp=d/f"A_basins_total_upstrm/2_timeseries/daily/ID_{i}.csv"
 used[str(qp)]=sha(qp);used[str(mp)]=sha(mp)
 q={};qd=set();met={};md=set()
 # Discharge values outside target label months are never parsed or retained.
 for r in readsemi(qp):
  ym=int(r["YYYY"]),int(r["MM"])
  if ym not in target:continue
  dt=date(*ym,int(r["DD"]))
  if dt in q:qd.add(dt)
  q[dt]=r
 for r in readsemi(mp):
  ym=int(r["YYYY"]),int(r["MM"])
  if ym not in need:continue
  dt=date(*ym,int(r["DD"]));assert int(r["DOY"])==dt.timetuple().tm_yday
  if dt in met:md.add(dt)
  met[dt]=r
 weather={}
 for y,mo in sorted(need):
  days=calendar.monthrange(y,mo)[1];ps=[];ts=[]
  for day in range(1,days+1):
   dt=date(y,mo,day);r=met.get(dt)
   if r and dt not in md:
    p,t=finite(r["prec"]),finite(r["2m_temp_mean"])
    if p is not None and p>=0:ps.append(p)
    if t is not None:ts.append(t)
  complete=len(ps)==len(ts)==days
  weather[y,mo]={"gauge_id":i,"year":y,"month":mo,"P":sum(ps) if complete else None,"T":sum(ts)/days if complete else None,"expected_days":days,"P_valid_days":len(ps),"T_valid_days":len(ts),"met_complete":complete,"role":"MET_WITH_LABEL_MONTH" if (y,mo) in target else "EXOGENOUS_MET_ONLY_NO_Q"}
 out=[];support=[]
 for y,mo in sorted(target):
  days=calendar.monthrange(y,mo)[1];qs=[];eq=col=0
  for day in range(1,days+1):
   dt=date(y,mo,day);r=q.get(dt)
   if r:
    v=finite(r["qobs"]);eq+=r["qceq"]=="1";col+=r["qcol"]=="1"
    if v is not None and v>=0 and r["ckhs"]=="1" and dt not in qd:qs.append(v)
  f,diag=construct(y,mo,weather);ok=len(qs)==days and f is not None
  station=f"LAMAH_CE_PUBLIC_V1:{i}";sid=f"{station}:{y}-{mo:02d}"
  support.append({"gauge_id":i,"sample_id":sid,"year":y,"month":mo,"expected_days":days,"Q_valid_days":len(qs),"P_valid_days":weather[y,mo]["P_valid_days"],"T_valid_days":weather[y,mo]["T_valid_days"],"lag1_date":diag["antecedent_dates"][0],"lag2_date":diag["antecedent_dates"][1],"lag3_date":diag["antecedent_dates"][2],"weather_support_status":diag["status"],"missing_weather_dates":"|".join(diag.get("missing_dates",[])),"all_three_models_common_support":ok,"cold_prior_months":diag.get("cold_months"),"S_raw_zero":diag.get("S_zero"),"M_raw_zero":diag.get("M_zero"),"qceq_days":eq,"qcol_days":col})
  if ok:out.append({"sample_id":sid,"station_id":station,"gauge_id":i,"year":y,"month":mo,"Q_m3s":sum(qs)/days,**f,"complete":True})
 good={y for y in years if sum(r["year"]==y for r in out)==12}
 cache[i]=(out,support,list(weather.values()),good);return cache[i]
old=pro["development_gauges"];chosen=[];evidence=[]
for i in old:aggregate(i,True)
for slot in pro["new_selection"]["slots"]:
 accepted=None
 for i in slot["ranked_candidates"]:
  nested=[j for j in old+chosen if i in paths[j] or j in paths[i]]
  if nested:evidence.append({"slot":slot["slot"],"id":i,"status":"REJECT_NESTING","with_ids":nested});continue
  rows,support,w,good=aggregate(i)
  bad=[r for r in support if not r["all_three_models_common_support"]]
  status="ACCEPT" if len(good)==len(years) else "REJECT_INCOMPLETE_FIXED_WINDOWS_OR_PRIOR_MET"
  evidence.append({"slot":slot["slot"],"id":i,"status":status,"supported_years":sorted(good),"supported_months":len(rows),"bad_months":bad,"scores_seen":False})
  print(slot["slot"],i,status,flush=True)
  if status=="ACCEPT":accepted=i;chosen.append(i);break
 if accepted is None:evidence.append({"slot":slot["slot"],"status":"UNFILLED_NO_RULE_RELAXATION"})
allids=old+chosen
monthly=[];supports=[];weather=[];schemes=[]
for i in allids:
 rows,sup,w,good=cache[i];monthly.extend(rows);supports.extend(sup);weather.extend(w)
 for ex,ys in pro["scenarios"].items():
  goodys=sorted(set(ys)&good)
  schemes.append({"cohort":"DEVELOPMENT_9" if i in old else "EXTERNAL_FROZEN_NEW","gauge_id":i,"scenario":ex,"years":goodys,"n_months":12*len(goodys),"planned_years":ys,"excluded_years":sorted(set(ys)-good),"eligible":len(goodys)>=6})
macro=lambda i:"Rhine" if g[i]["region"]=="Rhine" else "Elbe" if g[i]["region"]=="Vltava" else "Danube"
pairs=[{"a":i,"b":j,"nested":j in paths[i] or i in paths[j],"same_macro":macro(i)==macro(j),"same_official_region":g[i]["region"]==g[j]["region"]} for z,i in enumerate(allids) for j in allids[z+1:]]
trans=readsemi(m/"B_basins_intermediate_all/1_attributes/Crossbasin_water_transfers.csv");up={i:{k for k in h if k==i or i in paths.get(k,set())} for i in allids};cross=[]
for t in trans:
 for i in allids:
  for j in allids:
   if i!=j and int(t["ID"]) in up[i] and int(t["To_ID"]) in up[j]:cross.append({"from_gauge":i,"to_gauge":j,"official_transfer":t})
selection={"label":pro["label"],"freeze_UTC":datetime.now(timezone.utc).isoformat(),"protocol_sha256":sha(P/"P2_PROTOCOL.json"),"new_basin_ids":chosen,"n_selected":len(chosen),"new_macro_regions":sorted(set(macro(i) for i in chosen)),"new_scores_seen":False,"P2_development_scores_seen":False,"new_metadata":[{"gauge_id":i,**g[i],"area_calc_km2":a[i]["area_calc"],"elev_mean_m":a[i]["elev_mean"],"frac_snow":a[i]["frac_snow"],"p_season":a[i]["p_season"],"macro_group":macro(i),"downstream_path":sorted(paths[i])} for i in chosen],"all_grouping":{str(i):{"macro":macro(i),"region":g[i]["region"],"cohort":"DEVELOPMENT_9" if i in old else "EXTERNAL_FROZEN_NEW"} for i in allids},"candidate_decisions":evidence,"pairwise_dependencies":pairs,"official_transfer_dependencies":cross,"schemes":schemes,"dependency_caveat":"No nesting of new sites with selected sites; macroclimate and shared Danube network remain dependent. Only three macro groups, Elbe few sites; group uncertainty descriptive."}
cw(P/"source/monthly_labels_features.csv",monthly);cw(P/"source/monthly_exogenous_weather.csv",weather);cw(P/"P2_FEATURE_SUPPORT.csv",supports)
selection["monthly_labels_features_sha256"]=sha(P/"source/monthly_labels_features.csv");selection["feature_support_sha256"]=sha(P/"P2_FEATURE_SUPPORT.csv")
jw(P/"P2_NEW_BASINS_FROZEN.json",selection)
jw(P/"source/SNAPSHOT.json",{"snapshot_id":"lamah-public-p2-"+sha(P/"source/monthly_labels_features.csv")[:24],"all_ids":allids,"n_unique_labeled_months":len(monthly),"n_exogenous_weather_months":len(weather),"n_antecedent_only_weather_months":sum(r["role"].startswith("EXOGENOUS") for r in weather),"source_files":used,"selection_sha256":sha(P/"P2_NEW_BASINS_FROZEN.json"),"original_official_metadata_hashes":jl(P1/"source/METADATA_HASHES.json"),"license_source":str(R/"source/ACQUISITION.json")})
jw(P/"evidence/PREFIT_FREEZE.json",{n:sha(P/n) for n in ["P2_PROTOCOL.json","P2_NEW_BASINS_FROZEN.json","P2_FEATURE_SUPPORT.csv","source/monthly_labels_features.csv","source/monthly_exogenous_weather.csv","source/SNAPSHOT.json"]})
print(json.dumps({"new_ids":chosen,"macros":selection["new_macro_regions"],"unique_label_months":len(monthly),"weather_months":len(weather),"supported_schemes":len(schemes),"all_full10yr":all(len(s["years"])==10 for s in schemes)},indent=2))
