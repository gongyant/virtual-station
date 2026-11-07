import sys,json,time
from cds_split import req,base,D,save
assert not (D/'CDS_T_MONTHLY_JOBS.json').exists()
source=json.loads((D/'CDS_YEAR_JOBS.json').read_text())[0]['request'];jobs=[]
for year in range(2015,2021):
 for month in range(1,13):
  payload=json.loads(json.dumps(source));payload['inputs'].update(year=[str(year)],month=[f'{month:02d}'],variable=['2m_temperature'])
  result=req(base+'/processes/reanalysis-era5-land/execution',payload);jobs.append({'key':f'{year}_{month:02d}_2m_temperature','request':payload,'submission':result});save(D/'CDS_T_MONTHLY_JOBS.json',jobs)
  print('T_MONTH',year,month,result['http'],result['body'].get('jobID') if isinstance(result['body'],dict) else result['body'][:100],flush=True)
  if len(jobs)==1 and result['http']!=201:raise SystemExit('FIRST_MONTH_FAILED_STOP_NO_BULK_SUBMISSION')
