"""R3 utilities; no import-time data access. Model worker receives no development labels."""
from pathlib import Path
from datetime import datetime,timezone
import csv,json,hashlib,sys,platform
import numpy as np
H=Path(__file__).resolve().parent;ROOT=H.parents[3];R1=H.parent/'s1a_r1';R2=H.parent/'s1a_r2';REPORTS=ROOT/'research_next/vhs_transfer/reports';P='vhs_next_s1a_r3_'
IDENTITY='RETROSPECTIVE_POST_EXPOSURE_EXPLORATORY_ANALYSIS'
FORCING=ROOT/'data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(n,obj): (H/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(n,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (H/n).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def event(name,**kw):
    with (H/'execution_events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(dict(event=name,time=datetime.now(timezone.utc).isoformat(),**kw),ensure_ascii=False)+'\n')
def check(a,b,rtol=1e-12,atol=1e-10):
    if not np.allclose(a,b,rtol=rtol,atol=atol):raise RuntimeError('Numerical mismatch')
def days(a,b):return np.arange(np.datetime64(a),np.datetime64(b)+np.timedelta64(1,'D'))
def months(d):return np.asarray(d,dtype='datetime64[M]').astype(int)%12
def windows(mapping,d,ws):
    return np.column_stack([np.array([np.mean([mapping[str(t-np.timedelta64(i,'D'))] for i in range(1,w+1)]) for t in d]) for w in ws])
def feature_sources():
    import xarray as xr
    with xr.open_dataset(FORCING) as ds:
        d=ds.time.values.astype('datetime64[D]');p=ds.precipitation_mm.values.reshape(-1).astype(float);t=ds.temperature_c.values.reshape(-1).astype(float)
    up={r['date']:float(r['Q_input_byblk']) for r in read(R1/'views/feature_view.csv')}
    return up,{str(k):v for k,v in zip(d,p)},{str(k):v for k,v in zip(d,t)}
def transform(up,p,t,train,dev,par):
    wm=windows(p,train,(7,));tm=windows(t,train,(7,));raw=np.column_stack([wm,tm]);cl=np.stack([raw[months(train)==i].mean(axis=0) for i in range(12)]);scale=(raw-cl[months(train)]).std(axis=0)
    if np.any(scale<=1e-12):raise RuntimeError('Meteorological zero scale')
    zmet_train=(raw-cl[months(train)])/scale
    zmet_dev=(np.column_stack([windows(p,dev,(7,)),windows(t,dev,(7,))])-cl[months(dev)])/scale
    qcl=np.array(par['upstream_monthly_climate']);qs=np.array(par['upstream_scale']);qw=windows(up,train,(1,7,30));check(qcl,np.stack([qw[months(train)==i].mean(axis=0) for i in range(12)]));check(qs,(qw-qcl[months(train)]).std(axis=0))
    zq_train=(qw-qcl[months(train)])/qs;zq_dev=(windows(up,dev,(1,7,30))-qcl[months(dev)])/qs
    return zmet_train,zmet_dev,zq_train,zq_dev,cl,scale
def verify_inputs():
    m=load(H/(P+'execution_manifest.json'))
    for p,v in m['frozen_hashes'].items():
        if sha(ROOT/p)!=v:raise RuntimeError('Frozen input/code drift: '+p)
    for p,v in load(H/'integrity_before.json')['hashes'].items():
        if sha(ROOT/p)!=v:raise RuntimeError('Historical hash drift: '+p)
    return m
def require_rank(x,k):
    s=np.linalg.svd(x,compute_uv=False)
    if len(s)!=k or s[-1]<=s[0]*1e-12:raise RuntimeError('Rank/conditioning stop; no repair')
    return s
