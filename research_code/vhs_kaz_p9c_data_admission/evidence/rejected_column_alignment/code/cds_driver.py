from acquire import *
from urllib.parse import urlsplit
import hashlib
DR=ROOT/'driver';DR.mkdir(exist_ok=True)
def config():
 fields={}
 for line in (Path.home()/'.cdsapirc').read_text(encoding='utf-8').splitlines():
  if ':' in line:
   k,v=line.split(':',1);fields[k.strip()]=v.strip().strip('"\x27')
 return fields['url'].rstrip('/')+'/retrieve/v1',fields['key']
def request(url,payload=None):
 base,key=config()
 try:
  r=requests.post(url,json=payload,headers={'PRIVATE-TOKEN':key},timeout=(15,45)) if payload else requests.get(url,headers={'PRIVATE-TOKEN':key},timeout=(15,45))
  try:b=r.json()
  except ValueError:b=r.text[:6000]
  cleaned=json.loads(json.dumps(b).replace(key,'[REDACTED]'))
  return dict(http=r.status_code,body=cleaned)
 except Exception as e:return dict(http='REQUEST_FAILED',body=str(e).replace(key,'[REDACTED]'))
def submit(kind):
 path=DR/f'CDS_{kind}_JOB.json'
 if path.exists():print('EXISTING_JOB_NOT_RESUBMITTED',path);return
 grid=json.loads((ROOT/'evidence/TAUTURGEN_DRIVER_GRID.json').read_text(encoding='utf-8'));assert grid['weights_admitted_exploratory'] and grid['partition_relative_difference']<.001
 dates='1965-01-01/1966-01-01' if kind=='PILOT1965' else '1964-01-01/1979-01-01'
 assert kind=='PILOT1965' or (DR/'PILOT1965_NUMERIC_VALIDATION.json').is_file()
 if kind!='PILOT1965':assert json.loads((DR/'PILOT1965_NUMERIC_VALIDATION.json').read_text(encoding='utf-8'))['passed']
 payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'date':[dates],
  'area':[max(grid['grid_latitudes'])+.001,min(grid['grid_longitudes'])-.001,min(grid['grid_latitudes'])-.001,max(grid['grid_longitudes'])+.001],
  'data_format':'netcdf'}}
 contract=dict(dataset='reanalysis-era5-land-timeseries',task='RECONSTRUCTION_WITH_OBSERVED_MET',pilot='WB10195/QazSu14187',period=dates,
  variables={'t2m':'K=>degreeC;instantaneous UTC;24h dailymean=>calendar monthlymean','tp':'m=>mm;ARCOalreadydeaccumulated;interval-endminus1h forUTC accumulated precipitation;no repeated differencing'},
  aggregation='native full precision geodesic catchment area weights BEFORE daily/monthly aggregation; no European integer weight/rounding copied',
  quality='unique complete24h days; Gregorian leapday; complete calendar months; no padding/gapfill; all14 positive-weight cells required',
  source_catchment_sha256=sha(ROOT/'P9C_CATCHMENT_GIS.gpkg'),weights_sha256=sha(ROOT/'data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv'),
  model_fit_calls=0,test_Q_used=False,additional_values_in_bbox='retained raw;only14 actual catchment cells weighted')
 js(DR/f'{kind}_DRIVER_CONTRACT.json',contract)
 base,key=config();response=request(base+'/processes/reanalysis-era5-land-timeseries/execution',payload)
 js(path,dict(payload=payload,submission=response));event(stage='CDS_submit',kind=kind,http=response['http'],jobID=response['body'].get('jobID') if isinstance(response['body'],dict) else None)
 print(json.dumps(response,ensure_ascii=False)[:4000])
def poll(kind):
 j=json.loads((DR/f'CDS_{kind}_JOB.json').read_text(encoding='utf-8'));body=j['submission']['body'];job=body.get('jobID') if isinstance(body,dict) else None
 if not job:print('NO_VALID_JOB');return
 base,key=config();status=request(base+'/jobs/'+job);js(DR/f'CDS_{kind}_STATUS.json',status)
 event(stage='CDS_poll',kind=kind,http=status['http'],status=status['body'].get('status') if isinstance(status['body'],dict) else status['body'])
 if isinstance(status['body'],dict) and status['body'].get('status')=='successful':
  result=request(base+'/jobs/'+job+'/results');js(DR/f'CDS_{kind}_RESULT.json',result)
  value=result['body']['asset']['value'];dest=DR/f'ERA5L_{kind}.bin'
  if dest.exists():print('REUSE',dest);return
  r=requests.get(value['href'],timeout=(15,60));r.raise_for_status();assert len(r.content)<100_000_000
  expected=value.get('file:checksum');actual=hashlib.md5(r.content).hexdigest()
  if expected:assert actual==expected.removeprefix('md5:')
  dest.write_bytes(r.content);event(stage='CDS_download',kind=kind,bytes=len(r.content),sha256=sha(dest),official_MD5=expected,download_host=urlsplit(value['href']).hostname)
 elif status['http']==200 and isinstance(status['body'],dict) and status['body'].get('status')=='failed':
  result=request(base+'/jobs/'+job+'/results');js(DR/f'CDS_{kind}_FAILED_RESULT.json',result);print(json.dumps(result,ensure_ascii=False)[:3500])
if __name__=='__main__':
 kind=sys.argv[2] if len(sys.argv)>2 else 'PILOT1965'
 if sys.argv[1]=='submit':submit(kind)
 else:poll(kind)
