"""Sequential CDS acquisition of official hourly input. Never touches Q."""
import json,sys,time,urllib.request,hashlib
from cds_split import req,base,D,save
jobsfile=D/'CDS_LEGACY_HOURLY_JOBS.json'
if sys.argv[1]=='submit_first':
 assert not jobsfile.exists();contract={'source_code_files':['Timeseries_met_ERA5L.R','Transform_timeseries_hourly_to_daily.R'],'source_code_hashes':{n:hashlib.sha256((D/n).read_bytes()).hexdigest() for n in ['Timeseries_met_ERA5L.R','Transform_timeseries_hourly_to_daily.R']},'frozen_before_new_hourly_comparison':True,'original_implementation':'integer truncate intersection areas then normalize; deaccumulate tp except UTC01reset, shift tp timestamp minus1h; spatial weighted hourly temp Kelvin->C; round basin hourly tp to .01mm and T to .1C BEFORE daily sum/mean; round daily tp .01,T .1; sum monthly P / mean dailyT','reason_monthly_equivalence_failed':'rounding is nonlinear: sum(round(hourlyP,.01)) differs from round/sum of daily or monthly raw. Official original scripts now recovered from frozen archive. No Q used to choose pipeline.','thresholds':'UNCHANGED parity .18mm P and .052C T, all60months required','2019_boundary':'original script duplicates final hourly precipitation at2019-12-31 23 from22; reproduce exactly ONLY for overlap check, do not invent2020 data','2020':'use actual Jan1 2021 00 accumulation for Dec31 last hour; use original published2019-12 P for Jan2020 L1; no Q2020 read'};save(D/'ORIGINAL_LEGACY_IMPLEMENTATION_FROZEN.json',contract)
 payload={'inputs':{'variable':['2m_temperature','total_precipitation'],'year':['2015'],'month':['01','02'],'day':[f'{d:02d}' for d in range(1,32)],'time':[f'{h:02d}:00' for h in range(24)],'area':[46.7,10.2,46.6,10.3],'data_format':'netcdf','download_format':'unarchived'}};result=req(base+'/processes/reanalysis-era5-land/execution',payload);save(jobsfile,[{'key':'2015_01_02','request':payload,'submission':result}]);print(json.dumps(result,indent=2))
elif sys.argv[1]=='poll':
 jobs=json.loads(jobsfile.read_text());out=[]
 for j in jobs:
  if not isinstance(j['submission']['body'],dict) or 'jobID' not in j['submission']['body']:continue
  job=j['submission']['body']['jobID'];res=req(base+'/jobs/'+job);out.append({'key':j['key'],**res});print(json.dumps(res,indent=2))
  if isinstance(res['body'],dict) and res['body'].get('status')=='successful':
   result=req(base+'/jobs/'+job+'/results');save(D/f'CDS_LEGACY_RESULT_{j["key"]}.json',result);v=result['body']['asset']['value'];p=D/f'ERA5L_LEGACY_{j["key"]}.nc'
   if not p.exists():
    with urllib.request.urlopen(v['href'],timeout=60) as f:b=f.read(10_000_001)
    assert len(b)<10_000_000;assert hashlib.md5(b).hexdigest()==v['file:checksum'];p.write_bytes(b)
   print('DOWNLOADED',p.stat().st_size)
 save(D/'CDS_LEGACY_STATUS.json',out)
