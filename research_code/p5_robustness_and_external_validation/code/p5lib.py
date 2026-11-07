import csv,json,hashlib,sys,math,calendar
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
P=Path(__file__).resolve().parents[1];R=P.parent;P4=R/"p4_final_reconstruction";P2=R/"p2_antecedent_snow_features";PKG=P4/"release/P4_PUBLIC_V2"
def now():return datetime.now(timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding="utf-8-sig"))
def jw(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x",encoding="utf-8") as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def cr(p,delimiter=","):
 with Path(p).open(encoding="utf-8-sig",newline="") as f:return [{k.strip():v.strip() if v is not None else "" for k,v in r.items()} for r in csv.DictReader(f,delimiter=delimiter)]
def cw(p,rows,fields=None):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def verify(root):
 n=0
 for ln in (root/"SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
  h,name=ln.split("  ",1);assert sha(root/name)==h,name;n+=1
 return n
def seal(root):
 items=[(sha(p),p.relative_to(root).as_posix()) for p in sorted(root.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt"]
 (root/"SHA256SUMS.txt").write_text("".join(f"{h}  {n}\n" for h,n in items),encoding="utf-8");return sha(root/"SHA256SUMS.txt")
def attempt(event,**kw):
 with (P/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"UTC":now(),"event":event,**kw})+"\n")
def season(m):return "DJF" if m in [12,1,2] else "MAM" if m in [3,4,5] else "JJA" if m in [6,7,8] else "SON"
def labels(cutoff):
 assert cutoff<="2017-12";out={}
 for g,paths in jl(P4/"source/SNAPSHOT.json")["source_paths"].items():
  grouped={}
  for r in cr(paths["Q"],";"):
   dt=f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}'
   if "1981-01"<=dt<=cutoff:grouped.setdefault(dt,[]).append(r)
  for dt,rr in grouped.items():
   y,m=map(int,dt.split("-"));n=calendar.monthrange(y,m)[1];vals=[]
   for r in rr:
    try:v=float(r["qobs"])
    except ValueError:continue
    if math.isfinite(v) and v>=0 and r["ckhs"]=="1":vals.append(v)
   if len(rr)==n and len({r["DD"] for r in rr})==n and len(vals)==n:out[f"LAMAH_CE_PUBLIC_V1:{g}:{dt}"]=sum(vals)/n
 attempt("PUBLIC_LABEL_READ",cutoff=cutoff,n=len(out));return out
def metric(y,p):
 y,p=np.array(y,float),np.array(p,float);e=p-y;sy=np.std(y);sp=np.std(p);mu=np.mean(y);mse=np.mean(e*e)
 rr=float(np.corrcoef(y,p)[0,1]) if sy>0 and sp>0 else None;a=float(sp/sy) if sy>0 else None;b=float(np.mean(p)/mu) if abs(mu)>1e-12 else None
 return {"n":len(y),"MSE":float(mse),"RMSE":float(np.sqrt(mse)),"MAE":float(np.mean(abs(e))),"NSE":float(1-mse/np.mean((y-mu)**2)) if sy>0 else None,"KGE":float(1-np.sqrt((rr-1)**2+(a-1)**2+(b-1)**2)) if None not in [rr,a,b] else None,"PBIAS":float(100*sum(e)/sum(y)) if abs(sum(y))>1e-12 else None}
