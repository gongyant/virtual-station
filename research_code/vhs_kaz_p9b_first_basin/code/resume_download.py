from common import *
import requests,sqlite3,pyogrio,re
from urllib.parse import urljoin
m=read(ROOT/'source/zenodo_8147591.json');f=next(f for f in m['files'] if f['key']=='CA-discharge.gpkg');dst=ROOT/'source/CA-discharge.gpkg'
size=dst.stat().st_size;expected=f['size'];url='https://zenodo.org/records/8147591/files/CA-discharge.gpkg?download=1'
rec=dict(url=url,existing_partial_bytes=size,expected_bytes=expected,reason='Previous public transfer truncated; bounded single Range recovery',started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
try:
    if size!=expected or 'md5:'+digest(dst,'md5')!=f['checksum']:
        with requests.get(url,headers={'Range':f'bytes={size}-{expected-1}'},stream=True,timeout=(10,45)) as r:
            rec.update(status=r.status_code,content_range=r.headers.get('Content-Range'),content_length=r.headers.get('Content-Length'))
            if r.status_code==206:
                assert r.headers.get('Content-Range','').startswith(f'bytes {size}-');mode='ab';temp=dst
            elif r.status_code==200:mode='wb';temp=ROOT/'source/CA-discharge-recovery.gpkg'
            else:r.raise_for_status();raise RuntimeError('Range status not allowed')
            start=time.monotonic()
            with temp.open(mode) as out:
                for b in r.iter_content(128*1024):
                    if time.monotonic()-start>180:raise TimeoutError('bounded recovery deadline')
                    out.write(b)
        if temp!=dst:
            if temp.stat().st_size!=expected or 'md5:'+digest(temp,'md5')!=f['checksum']:raise RuntimeError('Recovery full download checksum mismatch')
            dst.rename(ROOT/'source/CA-discharge-INCOMPLETE_FIRST_TRANSFER.bin');temp.rename(dst)
    assert dst.stat().st_size==expected and 'md5:'+digest(dst,'md5')==f['checksum']
    rec.update(final_bytes=dst.stat().st_size,md5=digest(dst,'md5'),sha256=digest(dst),verified=True)
except Exception as e:rec.update(error=f'{type(e).__name__}: {e}',verified=False);raise
finally:js(ROOT/'source/DOWNLOAD_RECOVERY.json',rec);event('small_download_recovery',**rec)
con=sqlite3.connect(f'file:{dst.as_posix()}?mode=ro',uri=True);tables=con.execute("SELECT name,type FROM sqlite_master WHERE type IN ('table','view')").fetchall();schemas={t:con.execute(f'PRAGMA table_info("{t}")').fetchall() for t,k in tables if not t.startswith(('gpkg_','rtree_','sqlite_'))};js(ROOT/'evidence/CA_GPKG_SCHEMA.json',dict(layers=pyogrio.list_layers(dst).tolist(),tables=tables,schemas=schemas));con.close()
for layer,_ in pyogrio.list_layers(dst):
    info=pyogrio.read_info(dst,layer=layer);print('CA_SCHEMA',layer,info['features'],info['fields'].tolist()[:35],flush=True)
download=[];links=[]
for label,url in [('official_water_resources.html','https://www.kazhydromet.kz/en/water-resources/'),('official_hydro_database.html','https://meteo.kazhydromet.kz/database_hydro/'),('CA_paper.pdf','https://www.nature.com/articles/s41597-023-02474-8.pdf')]:
    a=dict(url=url,label=label,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        r=requests.get(url,timeout=(10,25));a.update(status=r.status_code,final_url=r.url,bytes=len(r.content));p=ROOT/'source'/label;p.write_bytes(r.content);a['sha256']=digest(p)
        if label.endswith('.html') and r.ok:
            for href,title in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',r.text,re.S|re.I):links.append(dict(source=url,title=re.sub('<[^>]+>',' ',title).strip(),url=urljoin(r.url,href)))
    except Exception as e:a['error']=f'{type(e).__name__}: {e}'
    download.append(a);event('official_source_attempt',**a)
js(ROOT/'source/ADDITIONAL_DOWNLOAD_LOG.json',download);csv(ROOT/'source/OFFICIAL_WATER_LINKS.csv',links)
