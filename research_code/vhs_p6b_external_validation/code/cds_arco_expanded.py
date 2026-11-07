import sys,json,urllib.request,hashlib,time
from cds_split import req,base,D,save
if sys.argv[1]=='submit':
 assert not (D/'CDS_ARCO_EXACT_FOUR_GRID_JOB.json').exists();payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'date':['2015-01-01/2021-01-01'],'area':[46.701,10.199,46.599,10.301],'data_format':'netcdf'}};save(D/'ARCO_BOUNDARY_NUMERICAL_CORRECTION.json',{'reason':'Official coordinate arrays store46.7/10.2 with floating point noise. Zero-width exact slice returnedNoData; unpadded rectangle returned onlybottomrightcell. Pad .001degree solely to include the FOUR official grid coordinates. Final dimension2x2 and exact expected coordinates will be asserted. Not a change in basin weights or use of gauge point.','previous_failure_evidence':'CDS_ARCO_GRID4051_FAILED_RESULT.json','frozen_before_comparison':True,'all_scientific_tolerances_unchanged':True});res=req(base+'/processes/reanalysis-era5-land-timeseries/execution',payload);save(D/'CDS_ARCO_EXACT_FOUR_GRID_JOB.json',{'request':payload,'submission':res});print(json.dumps(res,indent=2))
else:
 j=json.loads((D/'CDS_ARCO_EXACT_FOUR_GRID_JOB.json').read_text());job=j['submission']['body']['jobID'];status=req(base+'/jobs/'+job);save(D/'CDS_ARCO_EXACT_FOUR_GRID_STATUS.json',status);print(json.dumps(status,indent=2))
 with (D/'CDS_ARCO_EXACT_FOUR_GRID_POLL_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status})+'\n')
 if isinstance(status['body'],dict) and status['body'].get('status')=='successful':
  res=req(base+'/jobs/'+job+'/results');save(D/'CDS_ARCO_EXACT_FOUR_GRID_RESULT.json',res);v=res['body']['asset']['value'];p=D/'ERA5L_ARCO_EXACT_FOUR_GRID_2015_2020.zip'
  if not p.exists():
   with urllib.request.urlopen(v['href'],timeout=60) as f:b=f.read(20_000_001)
   assert len(b)<20_000_000 and hashlib.md5(b).hexdigest()==v['file:checksum'];p.write_bytes(b)
  print('DOWNLOADED_EXACT_FOUR_CELLS',p.stat().st_size)
