from pathlib import Path
import os,sys,json,hashlib,datetime,time
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')
LAB=Path('E:/VHS_Public_Baseline_Lab');P9A=LAB/'vhs_kaz_p9a_network_station_audit';P8=LAB/'vhs_kaz_p8_river_chain_statistics'
ROOT=Path(os.environ.get('VHS_P9B_OUTPUT',str(LAB/'vhs_kaz_p9b_first_basin')))
REPO=Path('E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1')
def digest(p,alg='sha256'):
    h=hashlib.new(alg)
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def js(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
def csv(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);(x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)).to_csv(p,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
def event(stage,**kw):
    e=dict(event_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage=stage,**kw)
    with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(e,ensure_ascii=False,default=str)+'\n')
    print(json.dumps(e,ensure_ascii=False,default=str),flush=True)
def md(name,text):(ROOT/name).write_text(text.strip()+'\n',encoding='utf-8')
def history_check(name):
    h=read(ROOT/'evidence/HISTORY_BASELINE.json');bad=[p for p,d in h.items() if not Path(p).is_file() or digest(p)!=d];q=dict(checked=len(h),passed=len(h)-len(bad),failed=len(bad),failures=bad);js(ROOT/'evidence'/name,q);event('history_check',checked=len(h),failed=len(bad));assert not bad;return q
