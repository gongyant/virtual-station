"""Disk-only inference. No target-Q argument, no model fit/import at inference."""
from common import *
UNITS={"P":"mm/month","T":"degC"}
class LoadedModel:
 def __init__(self,path):
  self.path=Path(path)
  verify(self.path);self.meta=jl(self.path/"model.json");self.hash=sha(self.path/"SHA256SUMS.txt")
  assert self.meta["dataset"]=="LAMAH_CE_PUBLIC_V1"
  assert self.meta["math_sha256"]==sha(P2/"P2_MODEL_CODE/models.py"),"MATH_VERSION_CHANGED"
  assert self.meta["protocol_hash"]==sha(P/"P4_PROTOCOL.json")
  with np.load(self.path/"arrays.npz",allow_pickle=False) as a:self.arrays={k:a[k].copy() for k in a.files}
  self.calibration=self.meta["calibration"];self.fields=self.meta["fields"]
 def predict_rows(self,rows,units):
  assert units==UNITS,"UNIT_MISMATCH"
  mapping={}
  for r in rows:
   assert not any(k.lower() in {"q","qobs","qobs_m3s","target","y"} for k in r),"TARGET_Q_IN_INFERENCE"
   assert set(r)<={"date","P","T","gauge_id"},"UNEXPECTED_FIELD"
   assert int(r.get("gauge_id",self.meta["gauge_id"]))==self.meta["gauge_id"],"WRONG_GAUGE"
   assert r["date"] not in mapping,"DUPLICATE_DATE"
   mapping[r["date"]]=r
  return mapping
 def predict_month(self,met_inputs,year,month,units=UNITS):
  data=self.predict_rows(met_inputs,units);dt=f"{year}-{month:02d}";prev=previous(dt)
  assert dt in data,"MISSING_CURRENT_MONTH"
  r=data[dt];vals=[]
  for k in self.fields:
   rr=data.get(prev) if k=="L1" else r;assert rr is not None,"MISSING_PREVIOUS_CALENDAR_P"
   v=rr.get("P" if k=="L1" else k)
   assert v is not None and math.isfinite(float(v)),"MISSING_NONFINITE_MET"
   if k in ["P","L1"]:assert float(v)>=0,"NEGATIVE_PRECIPITATION"
   vals.append(float(v))
  raw=np.array(vals);a=self.arrays;ix=month-1;constant=a["constant"][ix];sd=np.where(constant,1.,a["sd"][ix]);z=np.where(constant,0.,(raw-a["mu"][ix])/sd)
  pred=float(a["climate"][ix]+z@a["beta"]);assert math.isfinite(pred)
  departures=bool(np.any(constant&(abs(raw-a["mu"][ix])>1e-12*np.maximum(1,abs(a["mu"][ix])))))
  maxz=float(max(abs(z)));lev=float(z@a["precision"]@z)/max(float(a["leverage_q99"]),1e-20)
  support="HIGH_EXTRAPOLATION" if departures or maxz>5 or lev>2 else "EXTRAPOLATION_CAUTION" if maxz>3 or lev>1 else "IN_SUPPORT"
  cal=self.calibration[season(month)];out={"date":dt,"gauge_id":self.meta["gauge_id"],"model_id":self.meta["model_id"],"q_hat_raw":pred,"q_hat_nonnegative":max(0,pred),"support_class":support,"max_abs_z":maxz,"leverage_ratio":lev,"constant_departure":departures,"calibration_status":cal["status"],"model_hash":self.hash,"input_hash":digest({"gauge_id":self.meta["gauge_id"],"date":dt,"fields":self.fields,"values":vals,"units":units}),"unit":"m3/s"}
  for level in [80,90]:
   h=cal.get(f"halfwidth{level}")
   out[f"lower{level}"]=pred-h if h is not None else None;out[f"upper{level}"]=pred+h if h is not None else None
  out["application_eligible"]=support!="HIGH_EXTRAPOLATION" and cal["status"]=="CALIBRATED" and int(a["month_counts"][ix])>=4
  return out
def load_model(model_dir):return LoadedModel(model_dir)
def predict_month(model,met_inputs,year,month,units=UNITS):return model.predict_month(met_inputs,year,month,units)
def predict_range(model,met_series,start_month,end_month,units=UNITS):
 return [model.predict_month(met_series,int(d[:4]),int(d[5:]),units) for d in months(start_month,end_month)]
if __name__=="__main__":
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument("--model",required=True);ap.add_argument("--met",required=True);ap.add_argument("--start",required=True);ap.add_argument("--end",required=True);ap.add_argument("--output",required=True);args=ap.parse_args()
 records=jl(args.met);m=load_model(args.model);out=predict_range(m,records,args.start,args.end);cw(Path(args.output),out)
 print(json.dumps({"new_process":True,"model_hash":m.hash,"predictions":len(out),"fit_calls":0}))
