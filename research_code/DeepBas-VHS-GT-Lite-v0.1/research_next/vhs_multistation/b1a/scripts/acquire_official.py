"""Authorized single official archive acquisition; no extraction or Q decoding."""
from pathlib import Path
import json,hashlib,urllib.request,shutil,os,time,datetime
H=Path(__file__).resolve().parents[1];ROOT=H.parents[2];E=H/'evidence';A=H/'archive'
NAME='2_LamaH-CE_daily.tar.gz';MD5='69fd2733e969513403f923ecc5eaa3dc';SIZE=1477248617
URL='https://zenodo.org/records/5153305/files/'+NAME+'?download=1'
for k in ('TEMP','TMP','TMPDIR'):os.environ[k]=str(H/'tmp')
def digest(p,alg):
    h=hashlib.new(alg)
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def save(n,d):(E/n).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
hist=json.loads((E/'integrity_before.json').read_text(encoding='utf-8'))['hashes']
bad=[p for p,v in hist.items() if not (ROOT/p).is_file() or digest(ROOT/p,'sha256')!=v]
assert not bad,'Historical mismatch'
assert shutil.disk_usage(H).free>=16*1024**3,'Disk gate failed'
with urllib.request.urlopen('https://zenodo.org/api/records/5153305',timeout=30) as r:record=json.load(r)
f=next(f for f in record['files'] if f['key']==NAME)
assert record['metadata']['version']=='1.0' and f['size']==SIZE and f['checksum']=='md5:'+MD5
save('acquisition_authorization.json',dict(date_singapore='2026-10-16',authorization='Explicit user approval in current chat, B1A only',filename=NAME,version='1.0',official_size=SIZE,official_md5=MD5,free_bytes=shutil.disk_usage(H).free,historical_files_checked=len(hist),historical_mismatches=bad,metadata_refreshed=True,mirrors_allowed=False))
save('official_record_acquisition.json',record)
dest=A/NAME;part=A/(NAME+'.part');events=[]
if not dest.exists():
    for attempt in range(1,4):
        offset=part.stat().st_size if part.exists() else 0
        assert offset<=SIZE
        if offset==SIZE:break
        headers={'User-Agent':'VHS-B1A-authorized-acquisition/1.0'}
        if offset:headers['Range']=f'bytes={offset}-'
        try:
            with urllib.request.urlopen(urllib.request.Request(URL,headers=headers),timeout=45) as r:
                assert urllib.parse.urlsplit(r.url).hostname=='zenodo.org','Unexpected redirect'
                if offset:
                    assert r.status==206 and r.headers.get('Content-Range','').startswith(f'bytes {offset}-'), 'Unsafe resume response'
                else:assert r.status==200
                mode='ab' if offset else 'xb'
                events.append(dict(attempt=attempt,offset=offset,http_status=r.status,content_range=r.headers.get('Content-Range')))
                with part.open(mode) as out:
                    count=offset;last=time.monotonic()
                    while True:
                        b=r.read(min(1024*1024,SIZE-count+1))
                        if not b:break
                        count+=len(b)
                        if count>SIZE:raise RuntimeError('Archive exceeds official size')
                        out.write(b)
                        if time.monotonic()-last>20:
                            print(json.dumps(dict(downloaded=count,total=SIZE,percent=round(count/SIZE*100,1))),flush=True);last=time.monotonic()
            if part.stat().st_size==SIZE:break
        except Exception as err:
            events.append(dict(attempt=attempt,error=type(err).__name__,message=str(err)));save('download_events.json',events)
            if 'Unsafe resume' in str(err) or 'exceeds' in str(err):raise
    assert part.stat().st_size==SIZE,'Incomplete official download; keep partial, do not extract'
    actual=digest(part,'md5');sha=digest(part,'sha256')
    save('archive_checksum.json',dict(filename=NAME,bytes=part.stat().st_size,expected_bytes=SIZE,official_md5=MD5,actual_md5=actual,sha256=sha,status='PASS' if actual==MD5 else 'FAIL',download_url=URL,completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    assert actual==MD5,'MD5 mismatch: STOP'
    assert not dest.exists();part.rename(dest)
else:
    actual=digest(dest,'md5');assert dest.stat().st_size==SIZE and actual==MD5,'Existing archive mismatch: STOP'
    save('archive_checksum.json',dict(filename=NAME,bytes=SIZE,official_md5=MD5,actual_md5=actual,sha256=digest(dest,'sha256'),status='PASS',reused=True))
save('download_events.json',events)
print('OFFICIAL_ARCHIVE_CHECKSUM_PASS',flush=True)
