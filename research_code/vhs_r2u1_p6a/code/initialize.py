import csv,hashlib,json,shutil,sys,time,urllib.request,zipfile
from pathlib import Path
LAB=Path(r'E:\VHS_Public_Baseline_Lab');ROOT=LAB/'vhs_r2u1_p6a';R2=LAB/'vhs_web_r2_host_integration';P4=LAB/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
assert not ROOT.exists(),'Independent target already exists; inspect before continuing'
for p in ['code','evidence','external','diagnostics','p6','runtime','screenshots']: (ROOT/p).mkdir(parents=True,exist_ok=True)
history={}
for folder,name in [(LAB,'SHA256SUMS.txt'),(LAB/'p1_seasonal_meteorology_ablation','SHA256SUMS.txt'),(LAB/'p2_antecedent_snow_features','SHA256SUMS.txt'),(LAB/'p3_forward_temporal_validation','SHA256SUMS.txt'),(P4,'SHA256SUMS.txt'),(LAB/'p5_robustness_and_external_validation','SHA256SUMS.txt'),(LAB/'vhs_web_r1_public_results_bridge','SHA256SUMS.txt'),(R2,'SHA256SUMS.txt')]:
    entries={};bad=[]
    for line in (folder/name).read_text(encoding='utf-8-sig').splitlines():
        h,n=line.split('  ',1);entries[n]=h
        if sha(folder/n)!=h:bad.append(n)
    assert not bad,(folder,bad)
    history[str(folder)]={'manifest':name,'manifest_sha256':sha(folder/name),'files':entries}
jw(ROOT/'evidence/HISTORY_BEFORE.json',history)
shutil.copytree(R2/'host',ROOT/'host',ignore=shutil.ignore_patterns('logs','tmp','var','__pycache__','.git'))
for p in ['logs','tmp','var']:(ROOT/'host'/p).mkdir(exist_ok=True)
for name in ['start_host.ps1','stop_host.ps1']:
    text=(R2/name).read_text(encoding='utf-8-sig').replace('8792','8793').replace('R2 original','R2U1 original')
    (ROOT/name).write_text(text,encoding='utf-8')
for name in ['server.py','run_vhs.ps1','stop_vhs.ps1']:
    p=ROOT/'host'/name;p.write_text(p.read_text(encoding='utf-8-sig').replace('8792','8793'),encoding='utf-8')
bundle=jl(LAB/'vhs_web_r1_public_results_bridge/data/bundle.json')
print('TARGET_STATIONS',json.dumps([s for s in bundle['stations'] if s['gauge_id'] in [818,611,688]],ensure_ascii=False))
s=(R2/'host/static/view_public_results.js').read_text(encoding='utf-8')
print('DUPLICATE_COUNTS',s.count('V1评价状态'),s.count('V1误差风险'))
i=s.index("title:'所选空间站点'");(ROOT/'evidence/BEFORE_SPATIAL_COMPONENT.txt').write_text(s[i:i+2300],encoding='utf-8')
print(s[i:i+2100])
snapshot=jl(P4/'source/SNAPSHOT.json');print('SNAPSHOT_KEYS',list(snapshot))
for g in [818,611,688]:
    paths=snapshot['source_paths'][str(g)]
    print('PATHS',g,paths)
    for role,path in paths.items():
        p=Path(path)
        if p.suffix.lower()!='.csv':continue
        with p.open(encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f,delimiter=';'))
        print('RANGE',g,role, len(rows),list(rows[0])[:25], {k:rows[-1].get(k) for k in ['YYYY','MM','DD','qobs','prec','2m_temp_mean']})
jw(ROOT/'evidence/P6_ORIGINAL_STATION_METADATA.json',[s for s in bundle['stations'] if s['gauge_id'] in [818,611,688]])
print('ROOT',str(ROOT),'HISTORY_FILES',sum(len(x['files']) for x in history.values()))
