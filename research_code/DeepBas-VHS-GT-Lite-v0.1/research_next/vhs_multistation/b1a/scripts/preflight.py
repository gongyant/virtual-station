"""B1A pre-download checks. No archive GET or extraction is performed."""
from pathlib import Path
import os,json,hashlib,shutil,urllib.request,urllib.parse,datetime,tarfile,io
ROOT=Path(__file__).resolve().parents[4];B=ROOT/'research_next/vhs_multistation';H=B/'b1a';E=H/'evidence'
NAME='2_LamaH-CE_daily.tar.gz';MD5='69fd2733e969513403f923ecc5eaa3dc';URL='https://zenodo.org/records/5153305/files/'+NAME+'?download=1'
for name in ('archive','open_metadata','sealed_runoff','quarantine','evidence','scripts','reports','tmp'):(H/name).mkdir(exist_ok=True)
assert H.resolve().drive.upper()=='E:'
os.environ['TEMP']=str(H/'tmp');os.environ['TMP']=str(H/'tmp');os.environ['TMPDIR']=str(H/'tmp')
def sha(p,alg='sha256'):
    h=hashlib.new(alg)
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def save(n,data):
    p=E/n
    if p.exists():raise RuntimeError('Evidence exists: '+n)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
# Reuse frozen lists, not old model/data audit execution.
old=json.loads((B/'evidence/integrity_before.json').read_text(encoding='utf-8'))['hashes']
for p,v in json.loads((B/'evidence/delivery_manifest.json').read_text(encoding='utf-8')).items():old[p]=v['sha256']
old[(B/'evidence/delivery_manifest.json').relative_to(ROOT).as_posix()]=sha(B/'evidence/delivery_manifest.json')
paper=json.loads((B/'evidence/paper_integrity_against_s0.json').read_text(encoding='utf-8'))['hashes']
for p,v in paper.items():old.setdefault(p,v['sha256'])
bad=[p for p,v in old.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v]
save('integrity_before.json',dict(reused_B0_files=528,protected_files=len(old),hashes=old,mismatches=bad))
if bad:raise RuntimeError('Historical digest mismatch; see evidence')
# Filenames only, with explicit scope. No runoff payload access.
search_roots=[ROOT,Path('E:/Downloads'),Path('E:/Datasets'),Path('E:/Data')]
existing=[];errors=[]
for base in search_roots:
    if not base.is_dir():continue
    def onerror(e):errors.append(dict(path=e.filename,error=type(e).__name__))
    for parent,dirs,files in os.walk(base,onerror=onerror,followlinks=False):
        dirs[:]=[d for d in dirs if d not in {'.git','.venv','node_modules','__pycache__'} and not Path(parent,d).is_symlink()]
        for n in files:
            if n==NAME:
                p=Path(parent,n);existing.append(dict(path=str(p.resolve()),bytes=p.stat().st_size,md5=sha(p,'md5'),sha256=sha(p),checksum_pass=sha(p,'md5')==MD5))
for p in Path('E:/').glob(NAME):
    if not any(x['path']==str(p.resolve()) for x in existing):existing.append(dict(path=str(p),bytes=p.stat().st_size,md5=sha(p,'md5'),sha256=sha(p),checksum_pass=sha(p,'md5')==MD5))
save('existing_archive_search.json',dict(roots=[str(p) for p in search_roots],root_level='E:/ exact filename',excluded_directories=['.git','.venv','node_modules','__pycache__'],scope='bounded filename-only search; not proof of absence on all drives',errors=errors,matches=existing))
def clean_proxy(v):
    p=urllib.parse.urlsplit(v if '://' in v else '//'+v)
    return dict(scheme=p.scheme,host=p.hostname,port=p.port,credentials_present=p.username is not None)
proxy={k:clean_proxy(v) for k,v in urllib.request.getproxies().items() if k!='no'}
proxy['no_proxy_configured']=bool(urllib.request.getproxies().get('no'))
save('proxy_configuration.json',dict(urllib_effective_proxy=proxy,proxy_env_names_present=[k for k in os.environ if k.lower() in ('http_proxy','https_proxy','all_proxy','no_proxy')],credentials_redacted=True,configuration_changes=False))
# Small official metadata only; HEAD for large file, never GET/range requests.
record_result={}
for endpoint in ('https://zenodo.org/api/records/5153305','https://zenodo.org/records/5153305/export/json'):
    try:
        req=urllib.request.Request(endpoint,headers={'User-Agent':'VHS-B1A-official-metadata-preflight/1.0','Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=25) as response:
            body=response.read(1024*1024+1)
            if len(body)>1024*1024:raise RuntimeError('Metadata size cap exceeded')
            record=json.loads(body)
        save('official_record_metadata.json',dict(request_url=endpoint,final_url=response.url,record=record))
        record_result=dict(status='PASS',endpoint=endpoint)
        break
    except Exception as err:record_result.setdefault('errors',[]).append(dict(endpoint=endpoint,error=type(err).__name__,message=str(err)))
try:
    with urllib.request.urlopen(urllib.request.Request(URL,method='HEAD',headers={'User-Agent':'VHS-B1A-official-metadata-preflight/1.0'}),timeout=25) as response:
        head=dict(status='PASS',method='HEAD',final_url=response.url,http_status=response.status,headers={k:v for k,v in response.headers.items() if k.lower() in ('content-length','content-type','accept-ranges','etag','last-modified','content-disposition')},body_bytes_read=0)
except Exception as err:head=dict(status='UNVERIFIED',method='HEAD',error=type(err).__name__,message=str(err),body_bytes_read=0)
save('network_probe.json',dict(metadata=record_result,archive_head=head,archive_get_requests=0,mirrors_used=False))
# Synthetic path safety validation. Actual archive members are unavailable before approval.
def safe_member(m,seen):
    n=m.name.replace('\\','/');parts=n.split('/')
    if not n or n.startswith('/') or any(x=='..' or ':' in x for x in parts):return False
    if m.issym() or m.islnk() or not (m.isfile() or m.isdir()):return False
    key=n.rstrip('/').casefold()
    if key in seen:return False
    seen.add(key)
    target=(H/'quarantine'/n).resolve()
    return target.is_relative_to((H/'quarantine').resolve())
cases=[]
for name,typ in [('A/file.csv',tarfile.REGTYPE),('../escape',tarfile.REGTYPE),('/absolute',tarfile.REGTYPE),('C:/escape',tarfile.REGTYPE),('A/../../escape',tarfile.REGTYPE),('A/link',tarfile.SYMTYPE),('A/hardlink',tarfile.LNKTYPE),('A/device',tarfile.CHRTYPE)]:
    m=tarfile.TarInfo(name);m.type=typ;actual=safe_member(m,set());expected=name=='A/file.csv';cases.append(dict(name=name,accepted=actual,expected=expected,passed=actual==expected))
seen=set();a=tarfile.TarInfo('A/file.csv');b=tarfile.TarInfo('a/FILE.csv');first=safe_member(a,seen);second=safe_member(b,seen)
cases.append(dict(name='case-insensitive duplicate',accepted=second,expected=False,passed=first and not second))
assert all(c['passed'] for c in cases)
save('synthetic_archive_safety.json',dict(status='PASS',synthetic_only=True,cases=cases,actual_archive_members_scanned=False,extractall_used=False))
disk=shutil.disk_usage(H)
result=dict(stage='VHS-NEXT-B1A',phase='PRE_DOWNLOAD_GATE',checked_date_singapore='2026-10-12',checked_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),official_record='https://zenodo.org/records/5153305',version='1.0',filename=NAME,expected_md5=MD5,archive_url=URL,archive_destination=str(H/'archive'/NAME),tmp_destination=str(H/'tmp'),download_bytes=0,archive_acquired=any(x['checksum_pass'] for x in existing),disk=dict(total=disk.total,free=disk.free,used=disk.used),metadata_status=record_result.get('status','UNVERIFIED'),network_head_status=head['status'],protected_files=len(old),historical_mismatches=bad,isolation_level='Same-account directory and program-policy separation only; no OS security boundary, cryptographic sealing or separate account',download_confirmation='REQUIRED_NOT_YET_RECEIVED',actual_archive_member_safety='NOT_TESTABLE_BEFORE_ACQUISITION')
save('preflight_facts.json',result)
print(json.dumps(result,ensure_ascii=False))
