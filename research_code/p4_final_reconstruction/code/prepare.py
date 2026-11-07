"""T0: numerical-test-Q-blind source metadata freeze. Q tokens are reduced to missing/present flags without float conversion."""
from common import *
from collections import Counter,defaultdict
for d in ["code","source","evidence","runs","models"]:(P/d).mkdir(parents=True,exist_ok=True)
assert not (P/"P4_TEST_SPLIT_FROZEN.json").exists(),"DO_NOT_REFREEZE"
attempt("T0_STARTED")
hist={str(root):{"files_verified":verify(root),"seal_sha256":sha(root/"SHA256SUMS.txt")} for root in [R,R/"p1_seasonal_meteorology_ablation",P2,P3]}
jw(P/"evidence/HISTORICAL_FREEZE_BEFORE.json",hist)
snap=jl(P3/"source/SNAPSHOT.json");sp=jl(P3/"P3_SPLIT_FROZEN.json");groups={int(r["gauge_id"]):r for r in sp["splits"]};ids=sp["all_gauges"]
src={}
for g in ids:
 paths=[Path(k) for k in snap["source_files"] if k.endswith(f"ID_{g}.csv")]
 src[g]={"Q":next(p for p in paths if "D_gauges" in p.parts),"MET":next(p for p in paths if "A_basins_total_upstrm" in p.parts)}
 for p in paths:assert sha(p)==snap["source_files"][str(p)]
metadata=[];weather=[];features=[];byid={};qmeta={}
missing_codes={"","-999","-999.0","nan","NaN","NA","null"}
for g in ids:
 q=defaultdict(list)
 # Numeric Q is not parsed here, including historical Q. Raw token is discarded immediately.
 for r in cr(src[g]["Q"],";"):
  dt=f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}'
  token=r.pop("qobs");present=token not in missing_codes;del token
  q[dt].append({"day":int(r["DD"]),"present":present,"checked":r["ckhs"]=="1","eq":r["qceq"]=="1","outlier":r["qcol"]=="1"})
 source_min,source_max=min(q),max(q)
 for dt in months("1981-01","2017-12"):
  y,m=map(int,dt.split("-"));n=calendar.monthrange(y,m)[1];rr=q.get(dt,[]);present=sum(z["present"] for z in rr);checked=sum(z["present"] and z["checked"] for z in rr)
  complete=len(rr)==n and len({z["day"] for z in rr})==n
  status=("OUTSIDE_SOURCE_COVERAGE" if dt<source_min or dt>source_max else "MISSING_TRUE" if complete and present==0 else "OBS_ACCEPTED" if complete and checked==n else "OBS_UNCHECKED")
  row={"gauge_id":g,"date":dt,"sample_id":sid(g,dt),"source_status":status,"days_expected":n,"days_rows":len(rr),"days_present":present,"days_checked_present":checked,"days_qceq":sum(z["eq"] for z in rr),"days_qcol":sum(z["outlier"] for z in rr),"numeric_Q_validated":False,"status_basis":"SOURCE_DATE_COVERAGE_MISSING_SENTINEL_CKHS_ONLY","macro":groups[g]["macro"],"region":groups[g]["region"]}
  metadata.append(row);qmeta[g,dt]=row
 met=defaultdict(list)
 for r in cr(src[g]["MET"],";"):
  dt=f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}'
  if "1980-12"<=dt<="2017-12":met[dt].append(r)
 wm={}
 for dt in months("1980-12","2017-12"):
  y,m=map(int,dt.split("-"));n=calendar.monthrange(y,m)[1];rr=met.get(dt,[]);ps=[finite(r["prec"]) for r in rr];ts=[finite(r["2m_temp_mean"]) for r in rr]
  unique=len({r["DD"] for r in rr})==n;pv=len(ps)==n and unique and all(v is not None and v>=0 for v in ps);tv=len(ts)==n and unique and all(v is not None for v in ts)
  w={"gauge_id":g,"date":dt,"P":sum(ps) if pv else None,"T":sum(ts)/n if tv else None,"expected_days":n,"P_valid_days":sum(v is not None and v>=0 for v in ps),"T_valid_days":sum(v is not None for v in ts)}
  wm[dt]=w;weather.append(w)
 for dt in months("1981-01","2017-12"):
  w=wm[dt];prev=wm[previous(dt)];valid=w["P"] is not None and w["T"] is not None and prev["P"] is not None
  qmeta[g,dt]["met_supported"]=valid
  if valid:
   byid[sid(g,dt)]={"gauge_id":g,"sample_id":sid(g,dt),"date":dt,"year":int(dt[:4]),"month":int(dt[5:]),"P":w["P"],"T":w["T"],"L1":prev["P"],"L1_date":previous(dt)}
   features.append(byid[sid(g,dt)])
cw(P/"source/weather.csv",weather);cw(P/"source/features.csv",features);cw(P/"source/observation_metadata.csv",metadata)
tests=[r for r in metadata if "2015-01"<=r["date"]<="2017-12"];cw(P/"P4_TEST_SUPPORT_METADATA.csv",tests)
spec={"models":["C0+PT","P2-L1"],"math_source":str(P2/"P2_MODEL_CODE/models.py"),"math_sha256":sha(P2/"P2_MODEL_CODE/models.py"),"formula":"train twelve independent Q month means + jointly Ridge P/T [and actual calendar L1] anomalies","alpha":[.01,.1,1,10,100],"inner":"training-only year LOYO; one-SE largest alpha; unchanged P2 code","units":{"P":"mm/month","T":"degC","Q":"m3/s"},"missing":"reject missing/no zero imputation; monthly ddof1 std, P2 constant rule","raw_primary":True}
protocol={"label":"PUBLIC_DATA_FINAL_P4","task":"RETROSPECTIVE_MONTHLY_STREAMFLOW_RECONSTRUCTION","created_UTC":now(),"dataset":"LamaH-CE v1.0","DOI":"10.5281/zenodo.5153305","license":"CC BY-SA 4.0 stricter recorded attribution terms; ERA5-Land catchment P/T; measured qobs only","spec":spec,"spec_hash":digest(spec),"V1_cutoff":"2014-12","test":["2015-01","2017-12"],"V2_cutoff":"2017-12","prior_experiments":{"P0":["C0","E3n"],"P1":["C0","H0","E3n","C0+PT"],"P2":["C0+PT","P2-L1","P2-SNOW"],"P3":["C0+PT","P2-L1"],"selection":"initial3 ID order; P1 added6 metadata; P2 added18 quality/area/snow/network metadata; P3 same27 no score exclusions","QC_changes":"none; finite nonnegative full-month ckhs1, qceq/qcol diagnostics retained"},"test_metadata_admissibility":"No numeric Q parse in T0; present sentinel + full distinct dates + ckhs1 = provisional source-admissible. Postcommit numerical audit must confirm finite/nonnegative; any mismatch recorded and scoring aborted, no reselection.","support_tiers":{"relative_support":">=20 stations each>=24months","descriptive":"10-19","insufficient":"<10: no main comparison"},"direction":{"positive_mean_and_years_groups":">0 mean station skill AND >=2/3 years AND >=2/3 represented macro groups positive => DIRECTION_SUPPORTED","positive_other":"positive but conditions fail => INCONCLUSIVE","zero_or_negative":"<=0 => NOT_SUPPORTED (zero boundary explicitly assigned here)","default":"SUPPORTED=>L1; INCONCLUSIVE=>C0+PT default/L1 candidate; NOT_SUPPORTED=>C0+PT default/L1 research candidate; all require valid calibration and no constant departure"},"pseudo":{"lengths":[3,6,12,24],"primary":12,"primary_blocks":"four nonoverlapping full-calendar-year accepted blocks at 20/40/60/80 percentiles of available whole years, rounded to nearest index; unique; metadata/calendar selection only","other_lengths":"one first valid contiguous block at >=1989-01 per length, not required disjoint with primary; only primary12 residuals used calibration","refit":"each block excludes all held Q, refits alpha and all transforms","season_min_n":8},"interval":{"type":"symmetric empirical primary12 block-out absolute residual, basin-season","scale":"season OOF RMSE; normalized absolute residual finite order statistic ceil((n+1)*coverage); if rank>n => UNDEFINED_QUANTILE","levels":[.8,.9],"kappa":"max(1, P3 forward season RMSE / current block-out season RMSE) perbasin/model/season; no finite P3 n>=8 => NO_TRANSFER_SUPPORT (no interval), zero scale => ZERO_RESIDUAL_SCALE","no_unconditional_coverage_guarantee":True,"P3_selection_reuse":True,"V2":"regenerate blocks and transforms with <=2017; retain same kappa rule using old P3 residuals, no fresh independent V2 test"},"risk":{"IN_SUPPORT":"maxabsz<=3 AND leverage_ratio<=1 AND no constant departure","EXTRAPOLATION_CAUTION":"maxabsz<=5 AND leverage_ratio<=2 AND no constant departure","HIGH_EXTRAPOLATION":"otherwise; research inference only, not default application eligible","leverage":"z'(Z'Z+alphaI)^-1 z divided by train 99th percentile; train Z only"},"application":"true gaps only inside source coverage all daily Q missing sentinel; partial or ckhs0 never true gap; no simulations as labels","demo":{"station":2,"masked_year":2016,"model":"separate V2 crossfit excluding all2016 Q; V1 calibration only (no2016 labels in interval calibration)","state":"MASKED_ACCEPTED","not_true_gap":True},"test_prediction_commit":"all predictions/intervals and model hashes sealed before first numeric testQ read","claim":"retrospective with observed current meteorology, not advance forecast or zero-target transfer","SYRDARYA":"NOT_GRANTED_NO_ACCESS","Claude_review":"No separately named Claude P4 review found in public workspace; supplied P4-FINAL corrections treated as governing review constraints"}
jw(P/"P4_PROTOCOL.json",protocol)
splits=[]
for g in ids:
 train=[r["sample_id"] for r in metadata if r["gauge_id"]==g and r["date"]<="2014-12" and r["source_status"]=="OBS_ACCEPTED" and r["met_supported"]]
 test=[r["sample_id"] for r in tests if r["gauge_id"]==g and r["source_status"]=="OBS_ACCEPTED" and r["met_supported"]]
 splits.append({"gauge_id":g,"macro":groups[g]["macro"],"region":groups[g]["region"],"V1_train_ids":train,"V1_test_ids":test,"test_months":len(test),"main_eligible":len(test)>=24})
n=sum(r["main_eligible"] for r in splits)
split={"freeze_UTC":now(),"protocol_hash":sha(P/"P4_PROTOCOL.json"),"test_Q_numeric_accesses":0,"test_scores_seen":False,"support_tier":"RELATIVELY_SUPPORTED" if n>=20 else "DESCRIPTIVE" if n>=10 else "INSUFFICIENT","n_sites_ge24":n,"splits":splits}
jw(P/"P4_TEST_SPLIT_FROZEN.json",split)
jw(P/"P4_TEST_ACCESS_AUDIT.json",{"T0_UTC":now(),"test_Q_float_conversions":0,"only_Q_token_operation":"membership in fixed missing-sentinel set; discard immediately","numeric_quality_confirmation":"postcommit, failclosed on discrepancy","source_file_hashes":snap["source_files"],"protocol_hash":sha(P/"P4_PROTOCOL.json"),"split_hash":sha(P/"P4_TEST_SPLIT_FROZEN.json"),"prior_P3_use":"<=2014 numeric labels only; 2015-17 never modeled/scored in P0-P3"})
jw(P/"source/SNAPSHOT.json",{"snapshot_base":"lamah-public-p4-"+digest(snap["source_files"])[:24],"source_files":snap["source_files"],"source_paths":{str(g):{k:str(v) for k,v in src[g].items()} for g in ids},"feature_hash":sha(P/"source/features.csv"),"metadata_hash":sha(P/"source/observation_metadata.csv")})
jw(P/"evidence/T0_FREEZE.json",{"UTC":now(),"protocol":sha(P/"P4_PROTOCOL.json"),"split":sha(P/"P4_TEST_SPLIT_FROZEN.json"),"test_metadata":sha(P/"P4_TEST_SUPPORT_METADATA.csv"),"no_test_numeric_Q":True})
attempt("T0_FROZEN",n_sites_ge24=n,test_months=sum(r["test_months"] for r in splits),status_counts=dict(Counter(r["source_status"] for r in tests)))
print(json.dumps({"n_sites_ge24":n,"test_months":sum(r["test_months"] for r in splits),"status_counts":dict(Counter(r["source_status"] for r in tests))}))
