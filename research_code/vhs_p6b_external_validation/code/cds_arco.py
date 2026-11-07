import sys,json,time,urllib.request,hashlib
from cds_split import req,base,D,save
if sys.argv[1]=='submit':
 assert not (D/'CDS_ARCO_JOB.json').exists();save(D/'ARCO_GRID_EXTRACTION_FROZEN.json',{'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'method':'Official ERA5L ARCO optimized long time series for the FOUR original intersecting grid cells. Not gauge-point substitute. Apply original integer area weights and hourly rounding; ARCO tp already deaccumulated, shift interval end timestamps minus1h, never double deaccumulate.','period':['2015-01-01','2021-01-01'],'source_documentation':'https://confluence.ecmwf.int/pages/viewpage.action?pageId=699689224','equivalence_check':'compare ARCO against independently downloaded original January2015 hourly fields first, then all60 old-LamaH overlap months with UNCHANGED tolerances','test_Q2020_read':False})
 payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'date':['2015-01-01/2021-01-01'],'area':[46.7,10.2,46.6,10.3],'data_format':'netcdf'}};result=req(base+'/processes/reanalysis-era5-land-timeseries/execution',payload);save(D/'CDS_ARCO_JOB.json',{'request':payload,'submission':result});print(json.dumps(result,indent=2))
elif sys.argv[1]=='poll':
 j=json.loads((D/'CDS_ARCO_JOB.json').read_text());job=j['submission']['body']['jobID'];status=req(base+'/jobs/'+job);save(D/'CDS_ARCO_STATUS.json',status);print(json.dumps(status,indent=2))
 if status['body'].get('status')=='successful':
  result=req(base+'/jobs/'+job+'/results');save(D/'CDS_ARCO_RESULTS.json',result);v=result['body']['asset']['value'];p=D/'ERA5L_ARCO_FOUR_CELLS_2015_2020.nc'
  if not p.exists():
   with urllib.request.urlopen(v['href'],timeout=60) as f:b=f.read(30_000_001)
   assert len(b)<30_000_000;assert hashlib.md5(b).hexdigest()==v['file:checksum'];p.write_bytes(b)
  print('DOWNLOADED_ARCO',p.stat().st_size)
