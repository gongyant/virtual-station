import sys,json,csv,hashlib,math,calendar,time,ast,re
from pathlib import Path
from datetime import datetime
import numpy as np
L=Path(r'E:\VHS_Public_Baseline_Lab');R=L/'vhs_p6d_failure_diagnostics';P4=L/'p4_final_reconstruction';B=L/'vhs_p6b_external_validation';C=L/'vhs_p6c_2020_validation'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cr(p,sep=','):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline=''),delimiter=sep))
def cw(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def event(name,**kw):
 with (R/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'event':name,**kw})+'\n')
def seal(d):
 (d/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in sorted(d.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
def previous(dt):
 y,m=map(int,dt.split('-'));return f'{y if m>1 else y-1}-{m-1 if m>1 else 12:02d}'
def metric(y,p):
 y=np.array(y,float);p=np.array(p,float)
 if not len(y):return {'n':0,**{k:None for k in ['MSE','RMSE','MAE','NSE','KGE','KGE_r','KGE_alpha','KGE_beta','PBIAS','Qobs_mean','Qsim_mean','Qobs_std','Qsim_std','SST','bias','bias_MSE','centered_MSE']},'undefined_reason':'NO_ELIGIBLE_MONTHS'}
 e=p-y;sy=float(np.std(y));sp=float(np.std(p));ym=float(y.mean());pm=float(p.mean());mse=float(np.mean(e**2));r=float(np.corrcoef(y,p)[0,1]) if len(y)>1 and sy>0 and sp>0 else None;alpha=sp/sy if sy>0 else None;beta=pm/ym if ym!=0 else None
 return {'n':len(y),'MSE':mse,'RMSE':math.sqrt(mse),'MAE':float(np.mean(abs(e))),'NSE':1-mse/sy**2 if sy>0 else None,'KGE':1-math.sqrt((r-1)**2+(alpha-1)**2+(beta-1)**2) if all(x is not None for x in [r,alpha,beta]) else None,'KGE_r':r,'KGE_alpha':alpha,'KGE_beta':beta,'PBIAS':100*float(e.mean())/ym if ym else None,'Qobs_mean':ym,'Qsim_mean':pm,'Qobs_std':sy,'Qsim_std':sp,'SST':float(sum((y-ym)**2)),'bias':float(e.mean()),'bias_MSE':float(e.mean()**2),'centered_MSE':float(np.mean((e-e.mean())**2)),'undefined_reason':None if sy>0 and sp>0 and ym!=0 else 'UNDEFINED_VARIANCE_CORRELATION_OR_MEAN'}
def corr(x,y):return float(np.corrcoef(x,y)[0,1]) if len(x)>1 and np.std(x)>0 and np.std(y)>0 else None
def near(x,y):return (x is None and y in ['',None]) or (x is not None and y not in ['',None] and math.isclose(float(x),float(y),rel_tol=1e-10,abs_tol=1e-10))
