"""Checksum-gated full TAR member scan. No member payload is decoded/extracted."""
from pathlib import Path,PurePosixPath
import json,csv,tarfile,hashlib,shutil,collections,re,time
H=Path(__file__).resolve().parents[1];A=H/'archive/2_LamaH-CE_daily.tar.gz';E=H/'evidence'
def digest(p,alg):
    h=hashlib.new(alg)
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
assert digest(A,'md5')=='69fd2733e969513403f923ecc5eaa3dc'
reserved={'CON','PRN','AUX','NUL'}|{f'{x}{i}' for x in ('COM','LPT') for i in range(1,10)}
def check_name(n):
    if '\\' in n or n.startswith('/') or ':' in n or any(ord(c)<32 for c in n):return False
    parts=n.rstrip('/').split('/')
    return bool(parts) and all(p not in ('','..','.') and p==p.rstrip(' .') and p.split('.')[0].upper() not in reserved and not any(c in p for c in '<>"|?*') for p in parts)
def classify(n,isdir):
    if isdir:return 'DIRECTORY'
    l=n.lower()
    if any(x in l for x in ('cosero','hydrol_model','hydrological_model','model_output','modelled')):return 'MODEL_OUTPUT'
    if 'gauges' in l and ('timeseries' in l or 'time_series' in l):return 'SEALED_Q_DATA'
    if any(x in l for x in ('hydro_indices','hydrol_indices','hydrological_indices','water_balance','waterbalance')):return 'LABEL_DERIVED'
    if '/info/' in '/'+l or l.startswith('info/'):return 'DOCUMENTATION'
    if any(x in l for x in ('stream_network','streamnetwork','topology')):return 'TOPOLOGY'
    if ('basin' in l and ('timeseries' in l or 'time_series' in l)):return 'FORCING'
    if 'gauge' in l and 'attribute' in l:return 'ELIGIBILITY_ONLY'
    if 'attribute' in l:return 'UNKNOWN_ATTRIBUTE_PENDING_SOURCE_TABLE'
    return 'UNKNOWN'
rows=[];seen={};total=0;bad=[];largest=0;started=time.monotonic()
with tarfile.open(A,'r|gz') as tar:
    for m in tar:
        n=m.name
        # TAR often contains a harmless ./ prefix; remove it explicitly, reject interior traversal.
        while n.startswith('./'):n=n[2:]
        if n in ('','.') and m.isdir():continue
        norm=n.rstrip('/').casefold();reason=[]
        if not check_name(n):reason.append('UNSAFE_WINDOWS_PATH')
        if m.issym() or m.islnk() or not (m.isfile() or m.isdir()):reason.append('UNSUPPORTED_LINK_OR_SPECIAL_TYPE')
        if norm in seen:reason.append('CASE_INSENSITIVE_DUPLICATE')
        if len(n)>210:reason.append('PATH_LENGTH_REQUIRES_REVIEW')
        if m.size<0 or m.size>256*1024**2:reason.append('MEMBER_SIZE_QUOTA')
        for parent in PurePosixPath(n).parents:
            if str(parent)!='.' and seen.get(str(parent).casefold())=='FILE':reason.append('FILE_PARENT_COLLISION')
        seen[norm]='DIRECTORY' if m.isdir() else 'FILE'
        total+=m.size;largest=max(largest,m.size)
        if total>12*1024**3 or len(rows)>100000:reason.append('TOTAL_SIZE_OR_MEMBER_COUNT_QUOTA')
        row=dict(member=m.name,normalized_path=n,type='DIRECTORY' if m.isdir() else 'REGULAR_FILE' if m.isfile() else 'REJECTED',bytes=m.size,category=classify(n,m.isdir()),safety='PASS' if not reason else 'FAIL',reason='|'.join(reason))
        rows.append(row)
        if reason:bad.append(dict(member=m.name,reason=reason))
        if len(rows)%3000==0:print('Manifest members',len(rows),flush=True)
with (E/'archive_members.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
free=shutil.disk_usage(H).free
result=dict(status='PASS' if not bad and free>total+2*1024**3 else 'FAIL',members=len(rows),regular_files=sum(r['type']=='REGULAR_FILE' for r in rows),expanded_bytes=total,largest_member_bytes=largest,free_bytes=free,required_for_one_extraction_bytes=total+2*1024**3,categories=dict(collections.Counter(r['category'] for r in rows)),unsafe_members=bad,member_payloads_decoded=0,extraction_started=False,elapsed_seconds=round(time.monotonic()-started,2))
(E/'archive_manifest_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result),flush=True)
assert result['status']=='PASS','Archive safety/space failure: STOP before extraction'
