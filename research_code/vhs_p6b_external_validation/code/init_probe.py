import csv,json,hashlib,sys,time,urllib.request,urllib.error,concurrent.futures,importlib.util,os
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
LAB=Path(r'E:\VHS_Public_Baseline_Lab');R=LAB/'vhs_p6b_external_validation';P4=LAB/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
assert not R.exists(),'NEW_DIRECTORY_REQUIRED'
for name in ['code','external','evidence','driver','runs']:(R/name).mkdir(parents=True,exist_ok=True)
history={}
for folder in [LAB,*[LAB/x for x in ['p1_seasonal_meteorology_ablation','p2_antecedent_snow_features','p3_forward_temporal_validation','p4_final_reconstruction','p5_robustness_and_external_validation','vhs_web_r1_public_results_bridge','vhs_web_r2_host_integration','vhs_r2u1_p6a']]]:
 manifest=folder/'SHA256SUMS.txt';entries={}
 for line in manifest.read_text(encoding='utf-8-sig').splitlines():
  h,n=line.split('  ',1);assert sha(folder/n)==h,(str(folder),n);entries[n]=h
 history[str(folder)]={'manifest_hash':sha(manifest),'files':entries}
jw(R/'evidence/HISTORY_BEFORE.json',history)
stations=jl(LAB/'vhs_web_r1_public_results_bridge/data/bundle.json')['stations'];assert len(stations)==27
attrs=list(csv.DictReader((LAB/'source/extracted/D_gauges/1_attributes/Gauge_attributes.csv').open(encoding='utf-8-sig'),delimiter=';'))
for s in stations:s['original_attributes']=next(a for a in attrs if int(a['ID'])==s['gauge_id'])
jw(R/'evidence/STATIONS_27.json',stations)
print('STATIONS',[(s['gauge_id'],s['country'],s['official_gauge_id'],s['name']) for s in stations],flush=True)
print('HISTORICAL_FILES',sum(len(v['files']) for v in history.values()))
print('ENV', {x:bool(importlib.util.find_spec(x)) for x in ['cdsapi','ecmwf.datastores','xarray','netCDF4','fiona','shapely','pyproj'] if '.' not in x})
print('CDS_CONFIG_PRESENT',Path.home().joinpath('.cdsapirc').exists(),'CDS_ENV_NAMES',[k for k in os.environ if k.startswith('CDS')])
jobs=[('https://ehyd.gv.at/','ehyd_home.html'),('https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048&file=1','ehyd_200048_1.txt'),('https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048','ehyd_200048_listing.txt'),('https://wasser.gv.at/hydjb/','hydjb.html'),('https://cds.climate.copernicus.eu/api/retrieve/v1/processes/reanalysis-era5-land','CDS_era5land_process.json')]
def get(job):
 url,name=job;t=time.time()
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VHS-P6B-public-hydrology-research/1.0'}),timeout=25) as f:b=f.read(8_000_001);headers=dict(f.headers);status=f.status
  assert len(b)<=8_000_000;(R/'external'/name).write_bytes(b)
  return {'url':url,'file':name,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'status':status,'seconds':time.time()-t,'headers':headers}
 except Exception as e:return {'url':url,'status':'FAILED','error':str(e),'seconds':time.time()-t}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:receipts=list(pool.map(get,jobs))
jw(R/'external/INITIAL_FETCH_RECEIPTS.json',receipts)
print(json.dumps(receipts,ensure_ascii=False,indent=2))
