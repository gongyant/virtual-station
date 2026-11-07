"""Freeze P2 formulas and metadata-only candidate ranking before any P2 fitting."""
import csv,json,math,hashlib,tarfile
from pathlib import Path
from datetime import datetime,timezone
R=Path(r"E:\VHS_Public_Baseline_Lab");P1=R/"p1_seasonal_meteorology_ablation";P=R/"p2_antecedent_snow_features"
for n in ["P2_MODEL_CODE","source/daily","evidence","runs","reports"]: (P/n).mkdir(parents=True,exist_ok=True)
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def jw(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):
 with (P1/"source/metadata"/n).open(encoding="utf-8-sig") as f:return {int(r["ID"]):{k.strip():v.strip() for k,v in r.items()} for r in csv.DictReader(f,delimiter=";")}
g=read("D_gauges/1_attributes/Gauge_attributes.csv");a=read("A_basins_total_upstrm/1_attributes/Catchment_attributes.csv");h=read("B_basins_intermediate_all/1_attributes/Gauge_hierarchy.csv")
old=[2,6,9,533,818,255,611,460,378]
def down(i):
 seen=set()
 while i in h:
  i=int(h[i]["NEXTDOWNID"] or -1)
  if i<=0:break
  assert i not in seen
  seen.add(i)
 return seen
paths={i:down(i) for i in g}
specs=[("Rhine",50,1000,.25,1,200),("Rhine",5,100,0,.25,30),("Vltava",10,1000,0,1,100),("Inn above Salzach",50,1000,.3,1,150),("Salzach",50,1000,.25,1,150),("Enns",50,1000,.15,1,150),("Traun",50,1000,0,1,150),("Drava",20,1000,.3,1,100),("Mur",30,1000,.25,1,100),("Mur",50,1000,0,.2,200),("Leitha",30,1000,0,1,150),("Morava",30,1000,0,1,150),("Rabnitz",30,1000,0,1,150),("Raab",50,1000,0,1,200),("Inn under Salzach",50,1000,0,1,150),("Danube between Enns and Morava",50,1000,0,1,300),("Danube between Inn and Traun",50,1000,0,1,150),("Danube above Inn",500,50000,0,.15,1000)]
slots=[]
for k,(reg,lo,hi,sl,sh,target) in enumerate(specs):
 ids=[i for i in a if i in g and g[i]["region"]==reg and g[i]["country"] in ["AUT","DEU","CHE"] and g[i]["degimpact"]=="l" and int(g[i]["obsbeg_day"])<=1983 and lo<=float(a[i]["area_calc"])<hi and sl<=float(a[i]["frac_snow"])<sh and i not in old and not any(i in paths[j] or j in paths[i] for j in old)]
 ids.sort(key=lambda i:(abs(math.log(float(a[i]["area_calc"])/target)),i))
 slots.append({"slot":k+1,"region":reg,"area_km2_range":[lo,hi],"snow_fraction_range":[sl,sh],"target_area_km2":target,"ranked_candidates":ids[:4]})
protocol={"label":"PUBLIC_DATA_EXPLORATORY_P2","created_UTC":datetime.now(timezone.utc).isoformat(),"source_DOI":"10.5281/zenodo.5153305","source_archive_sha256":jl(R/"source/ACQUISITION.json")["sha256"],"development_gauges":old,"models":["C0+PT","P2-L1","P2-SNOW"],"formulas":{"C0+PT":"train Q month mean + beta_P*P_z + beta_T*T_z","P2-L1":"train Q month mean + beta_P*P_z + beta_T*T_z + beta_L1*P_calendar_previous_month_z","P2-SNOW":"train Q month mean + beta_P*P_z + beta_T*T_z + beta_S*S_z + beta_M*M_z","S":"sum(P_(t-k)*I(T_(t-k)<=0degC), k=1,2,3)","M":"S*max(T_t,0degC)"},"snow_window_months":3,"threshold_degC":0.0,"proxy_units":{"S":"mm proxy; NOT SWE","M":"mm degC proxy; NOT melt runoff"},"coefficient_estimation":"Jointly refit all P/T and additional meteorological coefficients under one shared alpha; fixed unpenalized twelve-month Q climate; no old frozen prediction as a training feature","alpha":[.01,.1,1,10,100],"selection":"inner LOYO; choose largest alpha within one standard error of minimum mean yearly MSE; tie smallest alpha; tolerance1e-12*max(1,abs(cutoff))","transform":"each feature calendar-month mean and sample std estimated on training target rows only; inner refit; prior raw weather can be outside labeled years; no held-out Q; raw covariate overlap is exogenous and explicitly allowed","constant_rule":"monthly sample std<=1e-12*max(1,maxabs) -> zero anomaly with reason; no imputation of missing values; record unseen test departures from constant train support","support":"intersection of valid current Q/P/T, calendar t-1 P/T and t-2/t-3 P/T for all models; use only full12-month supported years per scenario; no model-specific row deletions; slots unfilled if insufficient support","quality":{"Q":"same as P1 finite nonnegative qobs not-999 ckhs=1 full native daily coverage; qceq/qcol retained diagnostics","P":"finite nonnegative daily prec, -999 missing, full calendar month sum mm","T":"finite daily2m_temp_mean not-999, full calendar month mean degC","no_new_Q_years":"Q values parsed only for fixed label years; antecedent-only months read MET only"},"scenarios":{"CONSECUTIVE_10Y":list(range(1990,2000)),"SPARSE_10Y_PUBLIC_SUBSAMPLING":[1983,1987,1990,1994,1996,1999,2000,2001,2002,2004]},"validation":"LOYO10 if full support, otherwise record actual whole supported years; >=6years for planned fitting, >=3years/month in inner training","prediction_primary":"raw","prediction_secondary":"max(raw,0)","main_comparisons":["P2-L1 vs C0+PT","P2-SNOW vs C0+PT"],"statistics":{"unit":"year within basin; basins equal-weighted within each scenario, do not treat overlapping scenarios as independent","metrics":["NSE","KGE","KGE_r","KGE_alpha","KGE_beta","MAE","RMSE","MSE","PBIAS"],"uncertainty":"year bootstrap999/jackknife fixed OOF losses; macro-river cluster bootstrap999 across Rhine/Danube/Elbe; few clusters => descriptive only; no confirmatory pooled p-value","low_high_flow":"outer train Q 20th/80th quantiles for final-score diagnostics only","seasons":{"MAM":[3,4,5],"JJA":[6,7,8],"SON":[9,10,11],"DJF":[12,1,2],"MAY_JUN":[5,6]},"input_response":"save standardized feature beta and conditional +1degC current-temperature response recomputing M; not a physical causal effect"},"new_selection":{"target":18,"slots":slots,"rank":"absolute log(area/target), then ID; at most top4 per slot","eligibility":"low documented impact, AUT/DEU/CHE, obs_start<=1983; exclude existing9 and nesting with old/new; full original windows plus antecedent weather; no scores used","macro_regions":"Rhine / Elbe(Vltava) / Danube(all others); official regions also reported","no_replacement_by_score":True},"P1_unchanged":True,"SYRDARYA_access":False,"P0_P1_refitting":False,"seed":20261026,"exploratory":True,"P3_implemented":False}
jw(P/"P2_PROTOCOL.json",protocol)
jw(P/"evidence/P2_INITIAL_FREEZE.json",{"protocol_sha256":sha(P/"P2_PROTOCOL.json"),"created_before_P2_scores":True,"P1_seal_sha256":sha(P1/"SHA256SUMS.txt"),"P1_run_id":"PUBLIC_DATA_EXPLORATORY_P1-20261026T015059Z-7f0aabd5cf43"})
wanted=set()
for slot in slots:
 print(slot["slot"],slot["region"],slot["ranked_candidates"],flush=True)
 for i in slot["ranked_candidates"]:
  wanted.update([f"A_basins_total_upstrm/2_timeseries/daily/ID_{i}.csv",f"D_gauges/2_timeseries/daily/ID_{i}.csv"])
got=[]
with tarfile.open(R/"source/archive/2_LamaH-CE_daily.tar.gz","r|gz") as t:
 for member in t:
  if member.name not in wanted:continue
  assert member.isfile() and ".." not in Path(member.name).parts
  dest=P/"source/daily"/member.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(t.extractfile(member).read());got.append(member.name)
assert set(got)==wanted
jw(P/"source/EXTRACTED_HASHES.json",{n:sha(P/"source/daily"/n) for n in got})
print("EXTRACTED_PUBLIC_DAILY_FILES",len(got))

