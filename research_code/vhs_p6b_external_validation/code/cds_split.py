import json,sys,time,urllib.request,urllib.error
from pathlib import Path
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation');D=R/'driver';sys.stdout.reconfigure(encoding='utf-8')
fields={}
for l in (Path.home()/'.cdsapirc').read_text().splitlines():
 if ':' in l:k,v=l.split(':',1);fields[k.strip()]=v.strip()
base=fields['url'].rstrip('/')+'/retrieve/v1';headers={'PRIVATE-TOKEN':fields['key'],'Content-Type':'application/json'}
def req(url,payload=None):
 try:
  with urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(payload).encode() if payload else None,headers=headers),timeout=40) as f:return {'http':f.status,'body':json.load(f)}
 except urllib.error.HTTPError as e:return {'http':e.code,'body':e.read().decode().replace(fields['key'],'[REDACTED]')}
 except Exception as e:return {'http':'FAILED','body':str(e).replace(fields['key'],'[REDACTED]')}
def save(p,x):p.write_text(json.dumps(x,indent=2),encoding='utf-8')
if __name__=='__main__' and sys.argv[1]=='submit':
 assert not (D/'CDS_SPLIT_JOBS.json').exists();original=json.loads((D/'CDS_YEAR_JOBS.json').read_text());jobs=[]
 for y in range(2015,2021):
  for var in ['2m_temperature','total_precipitation']:
   payload=json.loads(json.dumps(original[0]['request']));payload['inputs'].update(year=[str(y)],variable=[var]);payload['inputs']['time']=['00:00'] if var=='total_precipitation' else [f'{h:02d}:00' for h in range(24)]
   result=req(base+'/processes/reanalysis-era5-land/execution',payload);jobs.append({'key':f'{y}_{var}','request':payload,'submission':result});save(D/'CDS_SPLIT_JOBS.json',jobs);print('CDS_SPLIT',y,var,result['http'],result['body'].get('jobID') if isinstance(result['body'],dict) else result['body'][:150],flush=True)
elif __name__=='__main__' and sys.argv[1]=='poll':
 jobs=json.loads((D/'CDS_SPLIT_JOBS.json').read_text());statuses=[]
 for j in jobs:
  if not isinstance(j['submission']['body'],dict) or 'jobID' not in j['submission']['body']:continue
  jobid=j['submission']['body']['jobID'];key=j['key'];path=D/f'ERA5L_{key}.nc'
  if path.exists():statuses.append({'key':key,'status':'DOWNLOADED','bytes':path.stat().st_size});continue
  res=req(base+'/jobs/'+jobid);status=res['body'].get('status') if isinstance(res['body'],dict) else res['body'];statuses.append({'key':key,**res});print('STATUS',key,status,flush=True)
  if status=='successful':
   results=req(base+'/jobs/'+jobid+'/results');save(D/f'CDS_RESULT_{key}.json',results)
   print('RESULT_KEYS',key,list(results['body']),flush=True)
   val=results['body'].get('asset',{}).get('value',{})
   if not val and 'asset' in results['body']:val=results['body']['asset']
   url=val.get('href')
   if url:
    with urllib.request.urlopen(url,timeout=60) as f:b=f.read(100_000_001)
    assert len(b)<100_000_000;path.write_bytes(b);print('DOWNLOADED',key,len(b),flush=True)
 save(D/'CDS_SPLIT_STATUS.json',statuses)
