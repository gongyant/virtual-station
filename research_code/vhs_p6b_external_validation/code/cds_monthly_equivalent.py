import sys,json,time
from cds_split import req,base,D,save
if sys.argv[1]=='submit':
 assert not (D/'CDS_MONTHLY_EQUIVALENT_JOB.json').exists()
 schema=req(base+'/processes/reanalysis-era5-land-monthly-means');save(D/'CDS_MONTHLY_PRODUCT_METADATA.json',schema)
 amendment={'frozen_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'reason':'Hourly full-year queries exceed CDS per-request size; queued tasks were rejected. Official monthly averaged daily means mathematically permit same monthly T and P without entire hourly download. Representation route fixed BEFORE any new overlap meteorological comparison or 2020Q scoring.','product':'reanalysis-era5-land-monthly-means','product_type':'monthly_averaged_reanalysis','P_transform':'ERA5L monthly mean daily total in metres/day *1000*calendar days','T_transform':'monthly mean K -273.15','spatial_weights':'same four intersections, official basin A and official Grid_ERA5L EPSG3035','acceptance':'all60overlapmonths2015..2019 must pass the pre-frozen .18mm monthlyP and .052C temperature tolerances; P relative <=.005 for P>=36mm','not_authorized_to_bias_correct':True,'original_hourly_attempts_retained':True,'2020_MIR_change':'ECMWF documents atmospheric forcing interpolation package MIR introduced2020-01-01; retain caveat even if overlap passes'}
 save(D/'MONTHLY_EQUIVALENCE_ROUTE_FROZEN.json',amendment)
 original=json.loads((D/'CDS_YEAR_JOBS.json').read_text())[0]['request']['inputs'];payload={'inputs':{'product_type':['monthly_averaged_reanalysis'],'variable':['2m_temperature','total_precipitation'],'year':[str(y) for y in range(2015,2021)],'month':[f'{m:02d}' for m in range(1,13)],'time':['00:00'],'area':original['area'],'data_format':'netcdf','download_format':'unarchived'}}
 result=req(base+'/processes/reanalysis-era5-land-monthly-means/execution',payload);save(D/'CDS_MONTHLY_EQUIVALENT_JOB.json',{'request':payload,'submission':result});print(json.dumps(result,indent=2))
elif sys.argv[1]=='poll':
 import urllib.request,hashlib
 j=json.loads((D/'CDS_MONTHLY_EQUIVALENT_JOB.json').read_text());job=j['submission']['body']['jobID'];status=req(base+'/jobs/'+job);save(D/'CDS_MONTHLY_EQUIVALENT_STATUS.json',status);print(json.dumps(status,indent=2))
 if status['body'].get('status')=='successful':
  res=req(base+'/jobs/'+job+'/results');save(D/'CDS_MONTHLY_EQUIVALENT_RESULT.json',res);asset=res['body']['asset']['value'];p=D/'ERA5L_MONTHLY_2015_2020.nc'
  if not p.exists():
   with urllib.request.urlopen(asset['href'],timeout=60) as f:b=f.read(2_000_001)
   assert len(b)<2_000_000;assert hashlib.md5(b).hexdigest()==asset['file:checksum'];p.write_bytes(b)
  print('DOWNLOADED',p.stat().st_size)
