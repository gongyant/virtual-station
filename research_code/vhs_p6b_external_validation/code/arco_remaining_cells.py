"""Sequentially retrieve the other three original grid cells, never the gauge location."""
import sys,json,time,urllib.request,hashlib
from cds_split import req,base,D,save
sys.stdout.reconfigure(encoding='utf-8');weights=json.loads((D/'ID818_OFFICIAL_GRID_WEIGHTS.json').read_text())['weights'];jobs=[]
assert not (D/'CDS_ARCO_OTHER_CELLS.json').exists(),'CONTINUATION_ALREADY_EXISTS_INSPECT_BEFORE_RETRY'
for w in weights:
 lat=round(w['lat_centroid'],1);lon=round(w['lon_centroid'],1);grid=w['grid_attributes']['ID']
 if lat==46.6 and lon==10.3:continue
 payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'date':['2015-01-01/2021-01-01'],'area':[lat,lon,lat,lon],'data_format':'netcdf'}};res=req(base+'/processes/reanalysis-era5-land-timeseries/execution',payload);record={'official_grid_ID':grid,'latitude':lat,'longitude':lon,'request':payload,'submission':res,'status_history':[]};jobs.append(record);save(D/'CDS_ARCO_OTHER_CELLS.json',jobs);print('SUBMIT_GRID',grid,res['http'],flush=True)
 assert res['http']==201,res;job=res['body']['jobID']
 for poll in range(90):
  status=req(base+'/jobs/'+job);record['status_history'].append({'poll':poll,'utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**status});save(D/'CDS_ARCO_OTHER_CELLS.json',jobs);st=status['body'].get('status') if isinstance(status['body'],dict) else 'NETWORK_ERROR'
  if poll%3==0:print('GRID',grid,'STATUS',st,'poll',poll,flush=True)
  if st=='successful':
   result=req(base+'/jobs/'+job+'/results');record['result']=result;save(D/'CDS_ARCO_OTHER_CELLS.json',jobs);v=result['body']['asset']['value'];p=D/f'ARCO_CELL_{grid}.zip'
   with urllib.request.urlopen(v['href'],timeout=60) as f:b=f.read(10_000_001)
   assert len(b)<10_000_000 and hashlib.md5(b).hexdigest()==v['file:checksum'];p.write_bytes(b);record.update(download_file=p.name,sha256=hashlib.sha256(b).hexdigest(),bytes=len(b));save(D/'CDS_ARCO_OTHER_CELLS.json',jobs);print('GRID_DOWNLOADED',grid,len(b),flush=True);break
  if st in ['failed','rejected','dismissed']:raise RuntimeError('OFFICIAL_JOB_REFUSED_STOP:'+str(status))
  time.sleep(10)
 else:raise RuntimeError('OFFICIAL_JOB_NOT_FINISHED_KEEP_JOB_ID_NO_RESUBMISSION')
print('THREE_OTHER_CELLS_COMPLETE',flush=True)
