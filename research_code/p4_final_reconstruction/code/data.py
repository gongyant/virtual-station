"""Only this module can convert source Q to float; T2 token is prediction seal."""
from common import *
from collections import defaultdict
SOURCE=jl(P/"source/SNAPSHOT.json")
def read_labels(cutoff,commit=None):
 if cutoff>"2014-12":
  assert commit is not None and (Path(commit)/"COMMITMENT.json").is_file()
  verify(Path(commit));c=jl(Path(commit)/"COMMITMENT.json")
  assert c["test_numeric_Q_loaded"] is False and c["all_predictions_complete"]
 out={};status=[];parsed_test=0
 for g,p in SOURCE["source_paths"].items():
  g=int(g);groups=defaultdict(list)
  for r in cr(p["Q"],";"):
   dt=f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}'
   if "1981-01"<=dt<=cutoff:groups[dt].append(r)
  for dt,rr in groups.items():
   y,m=map(int,dt.split("-"));n=calendar.monthrange(y,m)[1];vals=[];anyraw=0;invalid=0
   for r in rr:
    v=finite(r["qobs"])
    if dt>="2015-01":parsed_test+=1
    if v is not None:anyraw+=1
    if v is not None and v<0:invalid+=1
    if v is not None and v>=0 and r["ckhs"]=="1":vals.append(v)
   ok=len(rr)==n and len({r["DD"] for r in rr})==n and len(vals)==n
   if ok:out[sid(g,dt)]=sum(vals)/n
   status.append({"sample_id":sid(g,dt),"numeric_accepted":ok,"invalid_negative_days":invalid,"valid_checked_days":len(vals),"finite_present_days":anyraw})
 attempt("NUMERIC_Q_READ",cutoff=cutoff,n_accepted=len(out),post2014_day_conversions=parsed_test,prediction_commit_sha256=sha(Path(commit)/"SHA256SUMS.txt") if commit else None)
 return out,{r["sample_id"]:r for r in status}
def features():
 rr=cr(P/"source/features.csv")
 return [{k:(int(v) if k in ["gauge_id","year","month"] else float(v) if k in ["P","T","L1"] else v) for k,v in r.items()} for r in rr]
def weather(g):
 return [{"date":r["date"],"gauge_id":int(g),"P":float(r["P"]) if r["P"]!="" else None,"T":float(r["T"]) if r["T"]!="" else None} for r in cr(P/"source/weather.csv") if int(r["gauge_id"])==int(g)]
