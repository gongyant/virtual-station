from common import *
import requests,shutil,sqlite3,pyogrio,re,platform
for d in ['source','data','evidence','code','figures','logs','sci']:(ROOT/d).mkdir(parents=True,exist_ok=True)
if (ROOT/'evidence/HISTORY_BASELINE.json').exists():event('RESUME_ACQUISITION',reason='source timestamp collided with event utc field; fixed logger only; no historical data changed')
h=read(P9A/'evidence/HISTORY_BASELINE.json')
for line in (P9A/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
    d,r=line.split('  ',1);h[str(P9A/r)]=d
h[str(P9A/'SHA256SUMS.txt')]=digest(P9A/'SHA256SUMS.txt');js(ROOT/'evidence/HISTORY_BASELINE.json',h);history_check('HISTORY_INITIAL_CHECK.json')
event('START',argv=sys.argv,fit_calls=0,teacher_Q_reads=0)
local=[]
for base in [LAB/'source',REPO/'data/raw/hydrobasins',REPO/'data/raw/hydrorivers',REPO/'data/raw/dem']:
    if not base.exists():continue
    for p in base.rglob('*'):
        if p.is_file() and (p.suffix.lower() in ['.gpkg','.shp','.tif','.nc','.json'] or 'discharge' in p.name.lower()):local.append(dict(path=str(p),bytes=p.stat().st_size))
csv(ROOT/'evidence/LOCAL_PUBLIC_ASSET_INVENTORY.csv',local)
js(ROOT/'evidence/ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),disk_free_bytes=shutil.disk_usage(ROOT).free))
s=requests.Session();s.headers['User-Agent']='DeepBas-VHS P9B public hydrology research'
log=read(ROOT/'source/DOWNLOAD_LOG.json') if (ROOT/'source/DOWNLOAD_LOG.json').exists() else []
def fetch(label,url,cap=2_000_000):
    rec=dict(label=label,url=url,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        r=s.get(url,timeout=(10,25));rec.update(status=r.status_code,final_url=r.url,content_type=r.headers.get('Content-Type'),bytes=len(r.content))
        if len(r.content)>cap:raise RuntimeError('response exceeds planned metadata size')
        p=ROOT/'source'/label;p.write_bytes(r.content);rec.update(path=str(p),sha256=digest(p));r.raise_for_status();return r
    except Exception as e:rec['error']=f'{type(e).__name__}: {e}';return None
    finally:log.append(rec);js(ROOT/'source/DOWNLOAD_LOG.json',log);event('download_attempt',**rec)
r=fetch('zenodo_8147591.json','https://zenodo.org/api/records/8147591')
if r is None:raise RuntimeError('Zenodo metadata unavailable; do not guess file details')
m=r.json();js(ROOT/'source/CA_DISCHARGE_METADATA_SUMMARY.json',dict(doi=m.get('doi'),version=m['metadata'].get('version'),license=m['metadata'].get('license'),creators=m['metadata'].get('creators'),publication_date=m['metadata'].get('publication_date'),files=[{k:f.get(k) for k in ['key','size','checksum','links']} for f in m['files']]))
f=next(f for f in m['files'] if f['key']=='CA-discharge.gpkg');assert f['size']<30_000_000
dst=ROOT/'source/CA-discharge.gpkg';url=f['links']['self'];rec=dict(label='CA-discharge.gpkg',url=url,expected_bytes=f['size'],expected_md5=f['checksum'],utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
try:
    existing=next((Path(x['path']) for x in local if Path(x['path']).name=='CA-discharge.gpkg' and Path(x['path']).stat().st_size==f['size'] and 'md5:'+digest(x['path'],'md5')==f['checksum']),None)
    if existing:shutil.copyfile(existing,dst);rec['reused_local_source']=str(existing)
    else:
        with s.get(url,stream=True,timeout=(10,40)) as resp:
            rec.update(status=resp.status_code,content_type=resp.headers.get('Content-Type'));resp.raise_for_status();start=time.monotonic();size=0
            with dst.open('wb') as out:
                for b in resp.iter_content(1024*1024):
                    size+=len(b)
                    if size>30_000_000 or time.monotonic()-start>180:raise RuntimeError('Bounded small-file download exceeded limit')
                    out.write(b)
    rec.update(bytes=dst.stat().st_size,md5=digest(dst,'md5'),sha256=digest(dst));rec['md5_passed']='md5:'+rec['md5']==f['checksum'];assert rec['md5_passed'] and rec['bytes']==f['size']
finally:log.append(rec);js(ROOT/'source/DOWNLOAD_LOG.json',log);event('CA_small_GPKG_download',**rec)
con=sqlite3.connect(f'file:{dst.as_posix()}?mode=ro',uri=True)
tables=con.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view')").fetchall();schemas={t:con.execute(f'PRAGMA table_info("{t}")').fetchall() for t,k in tables if not t.startswith(('gpkg_','rtree_','sqlite_'))};js(ROOT/'evidence/CA_GPKG_SCHEMA.json',dict(layers=pyogrio.list_layers(dst).tolist(),tables=tables,schemas=schemas));con.close()
print('CA_LAYERS',pyogrio.list_layers(dst).tolist(),flush=True)
for layer,_ in pyogrio.list_layers(dst):
    info=pyogrio.read_info(dst,layer=layer);print('CA_SCHEMA',layer,info['features'],info['fields'].tolist(),flush=True)
fetch('official_water_resources.html','https://www.kazhydromet.kz/en/water-resources/')
fetch('official_hydro_database.html','https://meteo.kazhydromet.kz/database_hydro/')
fetch('CA_paper_github_readme.md','https://raw.githubusercontent.com/hydrosolutions/CA-data-paper/main/README.md')
event('initial_acquisition_complete',large_archive_downloaded=False)
