from pathlib import Path
import hashlib,json,datetime,sys,re,os
import requests
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(os.environ.get('VHS_P9C_OUTPUT','E:/VHS_Public_Baseline_Lab/vhs_kaz_p9c_data_admission'))
OLD=Path('E:/VHS_Public_Baseline_Lab/vhs_kaz_p9b_first_basin')
for d in ['code','source','data','evidence','sci']:(ROOT/d).mkdir(parents=True,exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def mutable():
 if (ROOT/'SHA256SUMS.txt').exists():raise RuntimeError('P9C delivery frozen; use VHS_P9C_OUTPUT in a new sibling directory')
def js(p,x):
 mutable();Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n',encoding='utf-8')
def event(**x):
 mutable()
 x={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**x}
 with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(x,ensure_ascii=False,default=str)+'\n')
 print(json.dumps(x,ensure_ascii=False,default=str),flush=True)
def get(url,name,max_bytes=20_000_000,timeout=35):
 mutable()
 p=ROOT/'source'/name
 if p.exists():event(stage='reuse_current_snapshot',path=str(p),sha256=sha(p));return p
 try:
  r=requests.get(url,timeout=(15,timeout),stream=True);meta=dict(stage='public_download',url=url,status=r.status_code,final_url=r.url,content_type=r.headers.get('Content-Type'))
  r.raise_for_status();buf=bytearray()
  for block in r.iter_content(1024*256):
   buf.extend(block)
   if len(buf)>max_bytes:raise RuntimeError('Declared small-download cap exceeded')
  p.write_bytes(buf);event(**meta,bytes=len(buf),path=str(p),sha256=sha(p));return p
 except Exception as e:event(stage='download_failed',url=url,error=repr(e));return None
if __name__=='__main__':
 if not (ROOT/'evidence/HISTORY_BASELINE.json').exists():
  h=json.loads((OLD/'evidence/HISTORY_BASELINE.json').read_text(encoding='utf-8'))
  for line in (OLD/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
   digest,rel=line.split('  ',1);h[str(OLD/rel)]=digest
  h[str(OLD/'SHA256SUMS.txt')]=sha(OLD/'SHA256SUMS.txt')
  bad=[p for p,d in h.items() if not Path(p).is_file() or sha(p)!=d]
  js(ROOT/'evidence/HISTORY_BASELINE.json',h);event(stage='initial_history_verify',checked=len(h),failed=len(bad),failures=bad)
  if bad:raise RuntimeError('Historical mismatch')
 urls={
 'WB_DATASET.html':'https://datacatalog.worldbank.org/search/dataset/0064229/central-asia-flood-hazard-discharge-data',
 'WB_DAILY_API_PAGE.html':'https://datacatalog.worldbank.org/search/api-services?resourceId=DR0090965',
 'NCDC_METADATA.html':'https://www.ncdc.ac.cn/portal/metadata/46593408-b951-42d8-b23f-1c79a7342f08',
 'ZENODO_17075252.json':'https://zenodo.org/api/records/17075252',
 'KAZ_OFFICIAL_NEWS.html':'https://www.kazhydromet.kz/en/post/2526',
 'KAZ_OFFICIAL_CADASTRE.html':'https://www.kazhydromet.kz/ru/gidrologiya/gosudarstvennyy-vodnyy-kadastr-poverhnostnye-vody',
 'KAZ_PUBLIC_DATABASE.html':'https://meteo.kazhydromet.kz/database_hydro/'}
 for name,url in urls.items():get(url,name,timeout=25)
 p=ROOT/'source/WB_DATASET.html'
 if p.exists():
  scripts=re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)',p.read_text(encoding='utf-8'),re.I)
  js(ROOT/'evidence/WB_PUBLIC_SCRIPT_LINKS.json',scripts)
  print('WB scripts',scripts)
 z=ROOT/'source/ZENODO_17075252.json'
 if z.exists():
  m=json.loads(z.read_text(encoding='utf-8'));print('ZENODO license',m['metadata'].get('license'))
  for f in m['files']:
   print('ZENODO file',f['key'],f['size'],f['checksum'])
   if f['size']<1_000_000:get(f['links']['self'],f['key'])
