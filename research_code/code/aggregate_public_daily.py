"""Native UTC daily Q/P/T -> complete monthly observations. Selection has no model access."""
import calendar,collections,csv,hashlib,json,math
from datetime import date,datetime,timezone
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/"source/extracted"
load=lambda p:json.loads(p.read_text(encoding="utf-8"))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
protocol=load(R/"protocol.json")
# Complete variable/time definitions verified in Info and the associated paper, before any model scores.
(R/"evidence/PROTOCOL_BEFORE_SOURCE_DEFINITIONS.json").write_text(json.dumps(protocol,indent=2),encoding="utf-8")
protocol.update(source_timezone="UTC, no summer time",native_daily_window="00:00 through 23:59 UTC for AUT/DEU/CHE, per ESSD section4.1; selected stations recorded in metadata",source_columns={"Q":"qobs m3/s","P":"prec daily sum mm","T":"2m_temp_mean degC"} ,source_Q_processing="observational hydrographic-service Q; LamaH provider may have linearly filled <=6h gaps before daily aggregation; no additional filling performed here",qceq_qcol_policy="retain finite nonnegative ckhs=1 values; qceq/qcol are diagnostics, not proof of invalidity; record all flagged days; rare extremes/repeats are not automatically deleted")
(R/"protocol.json").write_text(json.dumps(protocol,indent=2,ensure_ascii=False),encoding="utf-8")
wanted_years=sorted(set(protocol["primary_years"]+protocol["sparse_years"]))
months=[(y,m) for y in wanted_years for m in range(1,13)]
with (D/"D_gauges/1_attributes/Gauge_attributes.csv").open(encoding="utf-8-sig",newline="") as f:attrs={int(x["ID"]):x for x in csv.DictReader(f,delimiter=";")}
def finite(x):
 try:v=float(x)
 except (ValueError,TypeError):return None
 return v if math.isfinite(v) and v!=-999 else None
def parse_daily(path,kind):
 data={};duplicates=set()
 with path.open(encoding="utf-8-sig",newline="") as f:
  rows=csv.DictReader(f,delimiter=";")
  required={"YYYY","MM","DD","qobs","ckhs","qceq","qcol"} if kind=="Q" else {"YYYY","MM","DD","prec","2m_temp_mean","DOY"}
  if not required<=set(rows.fieldnames):raise ValueError("UNEXPECTED_PUBLIC_DAILY_SCHEMA")
  for row in rows:
   y,m,d=int(row["YYYY"]),int(row["MM"]),int(row["DD"])
   if y not in wanted_years:continue
   dt=date(y,m,d)
   if kind=="MET" and int(row["DOY"])!=dt.timetuple().tm_yday:raise ValueError("PUBLIC_MET_DOY_MISMATCH")
   if dt in data:duplicates.add(dt)
   data[dt]=row
 return data,duplicates
selected=[];evidence=[];out=[];used=[]
for ident in range(1,51):
 qpath=D/f"D_gauges/2_timeseries/daily/ID_{ident}.csv";mpath=D/f"A_basins_total_upstrm/2_timeseries/daily/ID_{ident}.csv"
 if not qpath.is_file() or not mpath.is_file():
  evidence.append({"gauge_id":ident,"status":"REJECT_MISSING_FILE"});continue
 q,qd=parse_daily(qpath,"Q");met,md=parse_daily(mpath,"MET")
 monthly=[];bad=[];qc=collections.Counter()
 for y,m in months:
  days=calendar.monthrange(y,m)[1];qvals=[];ps=[];ts=[];eq=col=0
  for d in range(1,days+1):
   dt=date(y,m,d);qr=q.get(dt);mr=met.get(dt)
   if qr:
    v=finite(qr["qobs"]);eq+=qr["qceq"]=="1";col+=qr["qcol"]=="1"
    if v is not None and v>=0 and qr["ckhs"]=="1" and dt not in qd:qvals.append(v)
   if mr and dt not in md:
    p=finite(mr["prec"]);t=finite(mr["2m_temp_mean"])
    if p is not None and p>=0:ps.append(p)
    if t is not None:ts.append(t)
  complete=len(qvals)==len(ps)==len(ts)==days
  qc.update(qceq_flagged_days=eq,qcol_flagged_days=col)
  if not complete:bad.append({"year":y,"month":m,"expected_days":days,"Q_valid_days":len(qvals),"P_valid_days":len(ps),"T_valid_days":len(ts)})
  else:
   station=f"LAMAH_CE_PUBLIC_V1:{ident}"
   monthly.append({"sample_id":f"{station}:{y:04d}-{m:02d}","station_id":station,"gauge_id":ident,"year":y,"month":m,"Q_m3s":sum(qvals)/days,"P_mm":sum(ps),"T_C":sum(ts)/days,"expected_days":days,"Q_valid_days":len(qvals),"P_valid_days":len(ps),"T_valid_days":len(ts),"qceq_flagged_days":eq,"qcol_flagged_days":col,"complete":True,"timezone":"UTC","source_kind":"PUBLIC_OBSERVED_GAUGE_Q_AND_ERA5LAND"})
 evidence.append({"gauge_id":ident,"name":attrs.get(ident,{}).get("name"),"status":"ACCEPT" if not bad else "REJECT_INCOMPLETE_FIXED_WINDOWS","admissible_months":len(monthly),"required_months":len(months),"bad_months":bad,"qc_diagnostics":dict(qc),"selection_used_model_metrics":False})
 if not bad:
  selected.append(ident);out.extend(monthly)
  used.extend({"file":str(p.relative_to(R)),"sha256":sha(p)} for p in (qpath,mpath))
  print(json.dumps({"accepted_gauge_id":ident,"name":attrs[ident]["name"],"months":len(monthly),"qceq_qcol_diagnostics":dict(qc)}),flush=True)
 if len(selected)==3:break
if len(selected)!=3:raise ValueError("NOT_THREE_COMPLETE_PUBLIC_BASINS_IN_FIXED_CANDIDATE_SET")
assert len(out)==3*len(months) and len({r["sample_id"] for r in out})==len(out)
csvpath=R/"source/monthly_admitted.csv"
with csvpath.open("x",encoding="utf-8",newline="") as f:
 w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
snapshot="lamah-public-monthly-"+hashlib.sha256(canonical(out).encode()).hexdigest()[:24]
meta={"experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","synthetic":False,"snapshot_id":snapshot,"source_acquisition":load(R/"source/ACQUISITION.json"),"selected_gauge_ids":selected,"selected_gauge_attributes":{str(i):attrs[i] for i in selected},"selection_evidence":evidence,"monthly_rows":len(out),"monthly_csv_sha256":sha(csvpath),"source_file_hashes":used,"protocol_sha256":sha(R/"protocol.json"),"Q_source":"hydrographic-service observed streamflow in D_gauges; NOT F_hydrol_model output","P_T_source":"ERA5-Land basin A area-weighted forcings; these are reanalysis, not local meteorological observations","unit_definitions":{"Q":"m3/s","P":"mm/month from daily totals","T":"degC from daily means"},"time_alignment":"native UTC daily dates; complete native calendar months; no month shifts","additional_interpolation":False,"source_may_include_provider_short_gap_interpolation":True,"raw_Qobs_export_under_public_license":True}
(R/"source/MONTHLY_SNAPSHOT.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
(R/"evidence/BASIN_SELECTION.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps({"status":"READY_FOR_REAL_TRAINING","selected":selected,"monthly_rows":len(out),"snapshot_id":snapshot,"units":"m3/s; mm/month; degC"}),flush=True)

