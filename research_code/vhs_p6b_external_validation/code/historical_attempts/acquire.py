import json,csv,sys,subprocess,concurrent.futures,hashlib,tarfile,importlib.util,re,urllib.request,urllib.error,time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');L=Path(r'E:\VHS_Public_Baseline_Lab');R=L/'vhs_p6b_external_validation';STAGE=Path(__file__).parent
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def dl(url,name):
 p=R/'external'/name
 if p.exists() and p.stat().st_size:return {'url':url,'file':str(p),'status':'CACHED','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 q=subprocess.run(['pwsh','-NoProfile','-File',str(STAGE/'download.ps1'),'-Uri',url,'-OutputFile',str(p)],capture_output=True,text=True,encoding='utf-8')
 try:r=json.loads(q.stdout)
 except Exception:r={'url':url,'status':'FAILED','error':q.stderr[-500:]}
 print(name,r['status'],r.get('bytes',''),flush=True);return r
mode=sys.argv[1]
if mode=='ehyd':
 stations=json.loads((R/'evidence/STATIONS_27.json').read_text(encoding='utf-8'));jobs=[]
 for s in stations:
  if s['country']=='AUT':
   code=s['official_gauge_id'];jobs += [(f'https://ehyd.gv.at/services/MessstellenExtraData/owf?id={code}&file={k}',f'EHYD_{code}_file{k}.txt') for k in [1,3]]
 jobs += [('https://ehyd.gv.at/main-UFXEVZGM.js','ehyd_main.js')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rr=list(pool.map(lambda j:dl(*j),jobs))
 jw(R/'external/EHYD_DOWNLOAD_RECEIPTS.json',rr)
elif mode=='geometry':
 print('PYSHAPEFILE_PRESENT',bool(importlib.util.find_spec('shapefile')),flush=True)
 archive=L/'source/archive/2_LamaH-CE_daily.tar.gz';wanted=['A_basins_total_upstrm/3_shapefiles/Basins_A.','G_appendix/3_shapefiles/Grid_ERA5L.'];out=[]
 with tarfile.open(archive,'r|gz') as t:
  for m in t:
   if m.isfile() and any(m.name.startswith(w) for w in wanted):
    b=t.extractfile(m).read();p=R/'driver'/Path(m.name).name;p.write_bytes(b);out.append({'archive_member':m.name,'file':str(p),'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b)})
 jw(R/'driver/GEOMETRY_EXTRACT_RECEIPTS.json',out);print(out,flush=True)
elif mode=='cds':
 # Frozen before retrieving or comparing any new driving series.
 protocol={'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'station':818,'overlap_months':['2015-01','2019-12'],'strict_tolerance':{'P_absolute_mm_month':.02,'P_relative_when_gt1mm':.0001,'T_absolute_degC':.002},'tolerance_basis':'LamaH daily P published to .0001mm and T .001degC; daily rounding accumulation <.0016mm and monthly temp <=.0005degC. Extra tolerance covers numerical float/geometric precision, not source shifts. All checks must pass; no Q-conditioned processing choices.','aggregation':'official full-upstream basin polygon intersect official ERA5L cell polygons; original planar projection area weights; hourly tp daily accumulation at next-day 00UTC converted m->mm; instantaneous T mean 00..23 UTC Kelvin->C; sum daily P and average daily T; calendar full-month only','status':'PARITY_NOT_YET_TESTED','no_point_substitute':True}
 p=R/'driver/PARITY_CRITERIA_FROZEN.json';assert not p.exists();jw(p,protocol)
 fields={}
 for line in (Path.home()/'.cdsapirc').read_text().splitlines():
  if ':' in line:k,v=line.split(':',1);fields[k.strip()]=v.strip()
 # Small real official retrieval request: one day over the basin box. No secret logged.
 payload={'inputs':{'product_type':['reanalysis'],'variable':['2m_temperature','total_precipitation'],'year':['2020'],'month':['01'],'day':['01'],'time':[f'{h:02d}:00' for h in range(24)],'area':[46.8,10.0,46.5,10.5],'data_format':'netcdf','download_format':'unarchived'}}
 jw(R/'driver/CDS_ACCESS_TEST_REQUEST.json',payload)
 url=fields['url'].rstrip('/')+'/retrieve/v1/processes/reanalysis-era5-land/execution'
 req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','PRIVATE-TOKEN':fields['key'],'User-Agent':'VHS-P6B-research/1.0'})
 receipt={'url':url,'request_file':'CDS_ACCESS_TEST_REQUEST.json','purpose':'authenticated minimal 2020 basin-area data acquisition, not station point','credential_value_logged':False}
 try:
  with urllib.request.urlopen(req,timeout=45) as f:b=f.read(200000);receipt.update(status=f.status,response=json.loads(b),headers=dict(f.headers))
 except urllib.error.HTTPError as e:
  b=e.read(100000).decode('utf-8','replace').replace(fields['key'],'[REDACTED]');receipt.update(status=e.code,response=b)
 except Exception as e:receipt.update(status='FAILED',error=str(e).replace(fields['key'],'[REDACTED]'))
 jw(R/'driver/CDS_REAL_ACCESS_RESULT.json',receipt);print(json.dumps(receipt,ensure_ascii=False,indent=2))
