"""P3 coverage-only audit and time split freeze, before any model score."""
import calendar,csv,json,hashlib,math
from pathlib import Path
from datetime import date,datetime,timezone
R=Path(r"E:\VHS_Public_Baseline_Lab");P2=R/"p2_antecedent_snow_features";P=R/"p3_forward_temporal_validation"
for name in ["code","source","evidence","runs","reports"]:(P/name).mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def jw(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False),encoding="utf-8")
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def seal(root):
 pins={}
 for line in (root/"SHA256SUMS.txt").read_text().splitlines():
  h,name=line.split("  ",1);assert sha(root/name)==h,name;pins[name]=h
 return pins
history={str(root):seal(root) for root in [R,R/"p1_seasonal_meteorology_ablation",P2]}
pro={"label":"PUBLIC_DATA_TEMPORAL_P3","task":"RECONSTRUCTION_WITH_OBSERVED_MET","created_UTC":datetime.now(timezone.utc).isoformat(),"dataset":"LamaH-CE v1.0","DOI":"10.5281/zenodo.5153305","models":["C0+PT","P2-L1"],"frozen_model_file":str(P2/"P2_MODEL_CODE/models.py"),"frozen_model_sha256":sha(P2/"P2_MODEL_CODE/models.py"),"train_candidate_window":["1981-01","2004-12"],"test_candidate_window":["2005-01","2014-12"],"training_rule":"all common admissible months before2005, including incomplete calendar years; at least6 distinct years and at least4 distinct training years per calendar month, so inner LOYO retains>=3 references; no score-based station exclusion","test_rule":"retain every common admissible month in fixed2005-2014; station with>=1valid month and eligible training participates; full120months primary complete-window cohort, partial stations retained separately and in all-supported descriptive summary; no score-based year/site deletion","quality":{"Q":"finite nonnegative qobs not-999, ckhs=1, unique full native calendar daily coverage; qceq/qcol diagnostics retained","P":"finite nonnegative dailyprec not-999, complete calendar month sum mm","T":"finite daily2m_temp_mean not-999, complete calendar month mean degC","L1":"actual preceding calendar month P; may be unlabeled exogenous month; missing never zero"},"formula":"same P2 fixed train twelve monthly Qmeans + jointly Ridge-penalized P/T [and L1] standardized anomalies; no Snow, no feature/window changes","alpha":[.01,.1,1,10,100],"inner_validation":"training-period only LOYO, mean of per-year MSE, one-SE largest alpha; partial inner held years allowed, observed month counts recorded","transform":"training target rows only monthly means and sample std; inner refit; no test-period Q in fit/transform/tuning","constant_rule":"unchanged P2: sd<=1e-12*max(1,maxabs)->zero standardized anomaly and support reason; raw zero retained, missing never zero","prediction_commit":"all stations and both models predicted first, write separate immutable prediction bundle WITHOUT Qobs and seal SHA256; only then load test labels in scoring function","scoring":"same exact months/labels for bothmodels; raw primary, max(raw,0) secondary; NSE KGE/components RMSE MAE MSE PBIAS; NA and reason for undefined; annual MSE skill and equally weighted annual MSE","diagnostics":{"seasons":{"DJF":[12,1,2],"MAY_JUN":[5,6],"MAM":[3,4,5],"JJA":[6,7,8],"SON":[9,10,11]},"flows":"low<=outer train Q20 and high>=outer train Q80, diagnostics only","uncertainty":"year-paired fixed-loss bootstrap999 and jackknife perstation; macro river cluster bootstrap999 descriptive with only3unequal groups; do not pool raw m3/s squared losses across basins","extrapolation":"test monthly anomalies vs frozen train month ranges/std, constant departures; target month mean drift scored postcommit only"},"seed":20261026,"claims":"independent later-period validation of already developed methods on same27basins; not new basin test, not advance-month forecasting, not physical loss attribution; once used for P4 selection not a fresh final P4 test","SYRDARYA_access":False,"no_P2_refitting":True,"P4_executed":False}
jw(P/"P3_PROTOCOL.json",pro);jw(P/"evidence/INITIAL_PROTOCOL_FREEZE.json",{"protocol_sha256":sha(P/"P3_PROTOCOL.json"),"before_any_P3_score":True})
meta=jl(P2/"source/SNAPSHOT.json");sel=jl(P2/"P2_NEW_BASINS_FROZEN.json");ids=meta["all_ids"];used={};audit=[];features=[];trainlabels=[];testlabels=[];splits=[];weather_output=[]
need={(y,m) for y in range(1981,2015) for m in range(1,13)}|{(1980,12)}
def rows(path):
 with path.open(encoding="utf-8-sig") as f:
  for r in csv.DictReader(f,delimiter=";"):yield {k.strip():v.strip() for k,v in r.items()}
def finite(s):
 try:x=float(s)
 except (TypeError,ValueError):return None
 return x if math.isfinite(x) and x!=-999 else None
for g in ids:
 d=(R/"source/extracted" if g in [2,6,9] else R/"p1_seasonal_meteorology_ablation/source/daily") if g in [2,6,9,533,818,255,611,460,378] else P2/"source/daily"
 qp=d/f"D_gauges/2_timeseries/daily/ID_{g}.csv";mp=d/f"A_basins_total_upstrm/2_timeseries/daily/ID_{g}.csv";used[str(qp)]=sha(qp);used[str(mp)]=sha(mp)
 q={};met={};qd=set();md=set()
 for r in rows(qp):
  y,m=int(r["YYYY"]),int(r["MM"])
  if not 1981<=y<=2014:continue
  dt=date(y,m,int(r["DD"]))
  if dt in q:qd.add(dt)
  q[dt]=r
 for r in rows(mp):
  y,m=int(r["YYYY"]),int(r["MM"])
  if (y,m) not in need:continue
  dt=date(y,m,int(r["DD"]));assert int(r["DOY"])==dt.timetuple().tm_yday
  if dt in met:md.add(dt)
  met[dt]=r
 weather={}
 for y,m in sorted(need):
  days=calendar.monthrange(y,m)[1];ps=[];ts=[]
  for z in range(1,days+1):
   dt=date(y,m,z);r=met.get(dt)
   if r and dt not in md:
    p,t=finite(r["prec"]),finite(r["2m_temp_mean"])
    if p is not None and p>=0:ps.append(p)
    if t is not None:ts.append(t)
  weather[y,m]={"gauge_id":g,"year":y,"month":m,"P":sum(ps) if len(ps)==days else None,"T":sum(ts)/days if len(ts)==days else None,"P_valid_days":len(ps),"T_valid_days":len(ts),"expected_days":days}
  weather_output.append(weather[y,m])
 local=[];loc_train=[];loc_test=[]
 for y in range(1981,2015):
  for m in range(1,13):
   period="TRAIN" if y<=2004 else "TEST";days=calendar.monthrange(y,m)[1];qs=[];eq=col=0
   for z in range(1,days+1):
    dt=date(y,m,z);r=q.get(dt)
    if r:
     v=finite(r["qobs"]);eq+=r["qceq"]=="1";col+=r["qcol"]=="1"
     if v is not None and v>=0 and r["ckhs"]=="1" and dt not in qd:qs.append(v)
   previous=(y,m-1) if m>1 else (y-1,12);cur=weather[y,m];lag=weather[previous]
   validQ=len(qs)==days;validmet=cur["P"] is not None and cur["T"] is not None;validlag=lag["P"] is not None
   ok=validQ and validmet and validlag
   station=f"LAMAH_CE_PUBLIC_V1:{g}";sid=f"{station}:{y}-{m:02d}"
   reasons=[]
   if not validQ:reasons.append("INCOMPLETE_OR_INVALID_Q_DAYS")
   if not validmet:reasons.append("INCOMPLETE_CURRENT_MET_DAYS")
   if not validlag:reasons.append("INCOMPLETE_PREVIOUS_CALENDAR_P")
   audit.append({"gauge_id":g,"sample_id":sid,"year":y,"month":m,"period":period,"expected_days":days,"Q_valid_days":len(qs),"P_valid_days":cur["P_valid_days"],"T_valid_days":cur["T_valid_days"],"lag1_date":f"{previous[0]}-{previous[1]:02d}","lag1_P_valid_days":lag["P_valid_days"],"lag1_expected_days":lag["expected_days"],"qceq_flagged_days":eq,"qcol_flagged_days":col,"common_admissible":ok,"reason_codes":"|".join(reasons) if reasons else "OK"})
   if ok:
    f={"sample_id":sid,"station_id":station,"gauge_id":g,"year":y,"month":m,"period":period,"P":cur["P"],"T":cur["T"],"L1":lag["P"]};features.append(f);local.append(f)
    label={"sample_id":sid,"gauge_id":g,"year":y,"month":m,"Q_m3s":sum(qs)/days}
    if period=="TRAIN":trainlabels.append(label);loc_train.append(f)
    else:testlabels.append(label);loc_test.append(f)
 support_counts={str(m):len({r["year"] for r in loc_train if r["month"]==m}) for m in range(1,13)}
 eligible=len({r["year"] for r in loc_train})>=6 and min(support_counts.values())>=4 and len(loc_test)>0
 groups=sel["all_grouping"][str(g)]
 split={"gauge_id":g,**groups,"eligible":eligible,"status":"COMPLETE_120_TEST_MONTHS" if eligible and len(loc_test)==120 else "PARTIAL_TEST_SUPPORT_RETAINED" if eligible else "BLOCKED_INSUFFICIENT_TRAIN_OR_TEST_SUPPORT","train_ids":[r["sample_id"] for r in loc_train],"test_ids":[r["sample_id"] for r in loc_test],"train_years":sorted({r["year"] for r in loc_train}),"test_years":sorted({r["year"] for r in loc_test}),"train_months":len(loc_train),"test_months":len(loc_test),"training_year_support_per_month":support_counts,"train_partial_years":{str(y):sum(r["year"]==y for r in loc_train) for y in sorted({r["year"] for r in loc_train}) if sum(r["year"]==y for r in loc_train)<12},"test_months_per_year":{str(y):sum(r["year"]==y for r in loc_test) for y in range(2005,2015)},"excluded_test_months":[r["sample_id"] for r in audit if r["gauge_id"]==g and r["period"]=="TEST" and not r["common_admissible"]]}
 splits.append(split);print(g,split["status"],"train",len(loc_train),"test",len(loc_test),flush=True)
cw(P/"P3_TEMPORAL_SUPPORT_AUDIT.csv",audit);cw(P/"source/features.csv",features);cw(P/"source/train_labels.csv",trainlabels);cw(P/"source/test_labels_SCORE_ONLY.csv",testlabels);cw(P/"source/weather_monthly.csv",weather_output)
frozen={"label":pro["label"],"task":pro["task"],"freeze_UTC":datetime.now(timezone.utc).isoformat(),"protocol_sha256":sha(P/"P3_PROTOCOL.json"),"candidate_and_selected_test_window":["2005-01","2014-12"],"alternate_window_used":False,"model_scores_seen":False,"all_gauges":ids,"splits":splits,"eligible_gauges":[s["gauge_id"] for s in splits if s["eligible"]],"full120_gauges":[s["gauge_id"] for s in splits if s["eligible"] and s["test_months"]==120],"partial_test_gauges":[s["gauge_id"] for s in splits if s["eligible"] and s["test_months"]<120],"data_hashes":{n:sha(P/n) for n in ["P3_TEMPORAL_SUPPORT_AUDIT.csv","source/features.csv","source/train_labels.csv","source/test_labels_SCORE_ONLY.csv","source/weather_monthly.csv"]},"source_daily_hashes":used,"quality_only_audit":"test Q audited for source validity/coverage only; no scores; modeling process loads only train-label file until all predictions sealed"}
jw(P/"P3_SPLIT_FROZEN.json",frozen);jw(P/"source/SNAPSHOT.json",{"snapshot_id":"lamah-public-p3-"+sha(P/"source/features.csv")[:24],"split_sha256":sha(P/"P3_SPLIT_FROZEN.json"),"DOI":pro["DOI"],"source_files":used,"features_sha256":sha(P/"source/features.csv"),"train_labels_sha256":sha(P/"source/train_labels.csv"),"test_score_labels_sha256":sha(P/"source/test_labels_SCORE_ONLY.csv")})
jw(P/"evidence/HISTORY_PINS.json",history);jw(P/"evidence/PREFIT_FREEZE.json",{n:sha(P/n) for n in ["P3_PROTOCOL.json","P3_SPLIT_FROZEN.json","source/SNAPSHOT.json",*frozen["data_hashes"].keys()]})
print(json.dumps({"eligible":len(frozen["eligible_gauges"]),"full120":len(frozen["full120_gauges"]),"partial":frozen["partial_test_gauges"],"train_months":sum(s["train_months"] for s in splits if s["eligible"]),"test_months":sum(s["test_months"] for s in splits if s["eligible"]),"history_counts":{k:len(v) for k,v in history.items()}},indent=2))

