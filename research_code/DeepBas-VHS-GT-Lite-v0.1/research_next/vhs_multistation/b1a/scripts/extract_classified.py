"""Manifest-gated exclusive extraction. Copy bytes only, never decode runoff/model payloads."""
from pathlib import Path
import csv,json,tarfile,hashlib,shutil,os
H=Path(__file__).resolve().parents[1];E=H/'evidence'
for k in ('TMP','TEMP','TMPDIR'):os.environ[k]=str(H/'tmp')
assert json.loads((E/'archive_checksum.json').read_text())['status']=='PASS'
assert json.loads((E/'archive_manifest_summary.json').read_text())['status']=='PASS'
assert json.loads((E/'blind_coverage_synthetic.json').read_text())['status']=='PASS'
with (E/'archive_members.csv').open(encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
lookup={r['member']:r for r in rows};logs=[];total=0
def category(n,initial):
    l=n.lower()
    if n.startswith('G_appendix/2_codes/'):return 'UNKNOWN'
    if n.startswith(('Info_english/','Info_deutsch/')):return 'DOCUMENTATION'
    if 'Gauge_hierarchy.csv' in n or n.endswith('Stream_dist.csv') or n.startswith('E_stream_network/'):return 'TOPOLOGY'
    if n.endswith('Crossbasin_water_transfers.csv') or n.startswith('G_appendix/3_shapefiles/Impacts.'):return 'ELIGIBILITY_ONLY'
    if n.endswith('Catchment_attributes.csv'):return 'STATIC_ADMISSIBLE_PENDING_FIELD_REVIEW'
    if '/3_shapefiles/Basins_' in n or '/3_shapefiles/Gauges.' in n or n.startswith('G_appendix/3_shapefiles/River_regions.'):return 'GEOMETRY_PENDING_FIELD_REVIEW'
    if n=='G_appendix/1_attributes/EU-Hydro_network_start_end_ID.csv':return 'TOPOLOGY'
    return initial if initial in ('SEALED_Q_DATA','FORCING','LABEL_DERIVED','MODEL_OUTPUT','ELIGIBILITY_ONLY') else 'UNKNOWN'
with tarfile.open(H/'archive/2_LamaH-CE_daily.tar.gz','r|gz') as tar:
    for m in tar:
        if m.name not in lookup:continue
        r=lookup[m.name];assert r['safety']=='PASS'
        if r['type']=='DIRECTORY':continue
        n=r['normalized_path'];cat=category(n,r['category'])
        base=H/('sealed_runoff' if cat=='SEALED_Q_DATA' else 'quarantine' if cat in ('MODEL_OUTPUT','LABEL_DERIVED','UNKNOWN') else 'open_metadata')
        target=base/n;assert target.resolve().is_relative_to(base.resolve())
        assert target.resolve().drive.upper()=='E:' and not target.exists()
        target.parent.mkdir(parents=True,exist_ok=True)
        assert target.parent.resolve().is_relative_to(base.resolve())
        with tar.extractfile(m) as src,target.open('xb') as dst:
            copied=0;h=hashlib.sha256()
            while b:=src.read(1024*1024):
                copied+=len(b);assert copied<=m.size
                h.update(b);dst.write(b)
        assert copied==m.size
        logs.append(dict(member=m.name,category=cat,path=str(target.relative_to(H)).replace('\\','/'),bytes=copied,sha256=h.hexdigest(),payload_decoded=False));total+=copied
        if len(logs)%1000==0:print('Copied members',len(logs),flush=True)
        if len(logs)%200==0:assert shutil.disk_usage(H).free>2*1024**3,'Unexpected disk exhaustion: STOP'
with (E/'extraction_manifest.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(logs[0]));w.writeheader();w.writerows(logs)
from collections import Counter
out=dict(status='PASS',files=len(logs),bytes=total,categories=dict(Counter(r['category'] for r in logs)),exclusive_create=True,runoff_or_model_payload_decoded=False,same_account_policy_isolation_only=True,free_bytes=shutil.disk_usage(H).free)
(E/'extraction_summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
