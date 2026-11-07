import sys,json,csv,hashlib,calendar,math,time,ast,re
from pathlib import Path
import numpy as np
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6c_2020_validation');L=R.parent;B=L/'vhs_p6b_external_validation';P4=L/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def readcsv(p,sep=','):return list(csv.DictReader(Path(p).open(encoding='utf-8-sig',newline=''),delimiter=sep))
def cw(p,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with Path(p).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def event(name,**kw):
 with (R/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'event':name,**kw})+'\n')
def seal(d):
 (d/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(d).as_posix()}\n' for p in sorted(d.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt'),encoding='utf-8')
def verify(d):
 for line in (d/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():h,n=line.split('  ',1);assert sha(d/n)==h,n
def original_function(filename,name,space):
 tree=ast.parse((B/'code'/filename).read_text(encoding='utf-8'));defs=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name];assert len(defs)==1;exec(compile(ast.Module(body=defs,type_ignores=[]),filename,'exec'),space);return space[name]
from datetime import datetime
ehyd=original_function('admit.py','ehyd',globals())
metrics=original_function('run_fixed.py','metrics',globals())
