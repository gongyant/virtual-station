import csv,hashlib,json,sys,urllib.request,urllib.error,zipfile,time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');LAB=R.parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
receipts=[]
def fetch(url,name,limit):
 p=R/'external'/name
 if p.exists():return p
 req=urllib.request.Request(url,headers={'User-Agent':'VHS-P6A-research-data-intake/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=45) as f:
   if f.headers.get('Content-Length') and int(f.headers['Content-Length'])>limit:raise ValueError('EXCEEDS_TARGETED_DOWNLOAD_LIMIT')
   content=f.read(limit+1)
   if len(content)>limit:raise ValueError('EXCEEDS_TARGETED_DOWNLOAD_LIMIT')
   p.write_bytes(content)
   receipts.append({'url':url,'path':str(p),'bytes':len(content),'sha256':sha(p),'headers':dict(f.headers),'status':'DOWNLOADED','UTC':time.strftime('%Y-%m-%dT%H:%M:%S%z')})
   print('DOWNLOADED',name,len(content),flush=True)
 except Exception as e:
  receipts.append({'url':url,'status':'FAILED','reason':str(e)});print('FAILED',name,str(e),flush=True)
 return p if p.exists() else None
api=fetch('https://zenodo.org/api/records/17598150','ESTREAMS_1_4_RECORD.json',3_000_000)
for name,limit in [('README.md',20000),('streamflow_gauges.zip',4_000_000),('appendix.zip',100000)]:
 fetch('https://zenodo.org/records/17598150/files/'+name+'?download=1',name,limit)
if api:
 d=jl(api);print('LICENSE',d['metadata'].get('license'));print('FILES',[(f['key'],f['size']) for f in d['files']])
for name in ['streamflow_gauges.zip','appendix.zip']:
 p=R/'external'/name
 if p.exists():
  with zipfile.ZipFile(p) as z:
   print('MEMBERS',name,[(i.filename,i.file_size) for i in z.infolist() if not i.is_dir()])
   for item in z.infolist():
    if item.is_dir():continue
    assert item.file_size<30_000_000
    dest=R/'external'/Path(item.filename).name
    dest.write_bytes(z.read(item))
snapshot=jl(LAB/'p4_final_reconstruction/source/SNAPSHOT.json');bundle=jl(LAB/'vhs_web_r1_public_results_bridge/data/bundle.json')
jw(R/'evidence/P6_ORIGINAL_STATION_METADATA.json',[s for s in bundle['stations'] if s['gauge_id'] in [818,611,688]])
local=[]
for g in [818,611,688]:
 for role,path in snapshot['source_paths'][str(g)].items():
  p=Path(path)
  if p.suffix.lower()!='.csv':continue
  with p.open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f,delimiter=';'))
  dates=[f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}-{int(r["DD"]):02d}' for r in rows]
  post=[r for r,d in zip(rows,dates) if '2018-01-01'<=d<='2020-12-31']
  info={'gauge_id':g,'role':role,'path':path,'sha256':sha(p),'rows':len(rows),'first':min(dates),'last':max(dates),'post2017_rows':len(post),'columns':list(rows[0]),'last_example':rows[-1]}
  local.append(info);print('LOCAL',json.dumps(info,ensure_ascii=False),flush=True)
jw(R/'p6/EXISTING_OFFICIAL_FILE_COVERAGE.json',local)
jw(R/'external/DOWNLOAD_RECEIPTS.json',receipts)
