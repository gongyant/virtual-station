from pathlib import Path
import hashlib,json,datetime,sys,time,os
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
LAB=Path('E:/VHS_Public_Baseline_Lab')
P8=LAB/'vhs_kaz_p8_river_chain_statistics'
ROOT=Path(os.environ.get('VHS_P9A_OUTPUT',str(LAB/'vhs_kaz_p9a_network_station_audit')))
GPKG=P8/'P8_NATIONAL_RIVER_REACHES.gpkg'
GLOBAL=P8/'source/hydrorivers_global/HydroRIVERS_v10_shp/HydroRIVERS_v10.shp'
N1=LAB/'vhs_kaz_n1_national_virtual_stations'
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def js(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n',encoding='utf-8')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def csv(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    (obj if isinstance(obj,pd.DataFrame) else pd.DataFrame(obj)).to_csv(p,index=False,encoding='utf-8-sig',float_format='%.12g',na_rep='N/A')
def event(stage,**kw):
    o=dict(time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage=stage,**kw)
    with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(o,ensure_ascii=False,default=str)+'\n')
    print(json.dumps(o,ensure_ascii=False,default=str),flush=True)
def history_check(dest):
    hist=read(ROOT/'evidence/HISTORY_BASELINE.json'); bad=[]
    for p,h in hist.items():
        if not Path(p).is_file():bad.append(dict(path=p,reason='MISSING'))
        elif sha(p)!=h:bad.append(dict(path=p,reason='HASH_CHANGED'))
    result=dict(checked=len(hist),passed=len(hist)-len(bad),failed=len(bad),failures=bad)
    js(dest,result);event('history_check',**{k:result[k] for k in ['checked','passed','failed']})
    if bad:raise RuntimeError('Protected history hash changed')
