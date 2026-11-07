"""P7A shared I/O; every output is new, source inputs remain read-only."""
import csv,json,hashlib,pathlib,datetime,math,os
import numpy as np
LAB=pathlib.Path(r'E:\VHS_Public_Baseline_Lab')
ROOT=pathlib.Path(os.environ.get('VHS_P7A_OUTPUT',str(LAB/'vhs_p7a_hydrological_models')))
WEB=pathlib.Path(os.environ.get('VHS_WEB_S1_OUTPUT',str(LAB/'vhs_web_s1_research_integration')))
P4=LAB/'p4_final_reconstruction'
GAUGES=[2,6,9,10,22,103,142,171,185,230,255,270,343,377,378,383,401,428,455,460,480,512,533,545]
MODELS=['C0','C0+PT','P2-L1','P7-SL','P7-MEM']
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def readj(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
 with open(p,encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(list,tuple)):return [clean(x) for x in v]
 if isinstance(v,np.ndarray):return clean(v.tolist())
 if isinstance(v,np.generic):return clean(v.item())
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def put(p,v):
 guard_write(p)
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(clean(v),ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def csvout(p,records,fields=None):
 guard_write(p)
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 if fields is None:fields=list(dict.fromkeys(k for r in records for k in r))
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fields);w.writeheader();w.writerows([{k:clean(v) for k,v in r.items()} for r in records])
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def guard_write(p):
 p=pathlib.Path(p).resolve()
 for root in [ROOT,WEB]:
  if (root/'SHA256SUMS.txt').exists() and p.is_relative_to(root.resolve()):
   rel=p.relative_to(root.resolve())
   if rel.parts[0] not in ['runtime','logs']:raise FileExistsError('FROZEN_DELIVERY_REFUSES_OVERWRITE: '+str(p))
def prev(d):
 y,m=map(int,d.split('-'));return f'{y-1:04d}-12' if m==1 else f'{y:04d}-{m-1:02d}'
def memory(weather,rho,warmup=24):
 out={};state=None;last=None;n=0
 for d,w in sorted(weather.items()):
  p=w.get('P')
  if p is None or not np.isfinite(p):state=None;last=d;n=0;continue
  if last!=prev(d):state=None;n=0
  if state is not None and n>=warmup:out[d]=state
  state=p if state is None else rho*state+(1-rho)*p
  n+=1;last=d
 return out
def verify_history(before):
 checks=[{'path':p,'expected':h,'actual':sha(p) if pathlib.Path(p).is_file() else None} for p,h in before.items()]
 return {'checked':len(checks),'passed':sum(x['actual']==x['expected'] for x in checks),'failed':[x for x in checks if x['actual']!=x['expected']]}
