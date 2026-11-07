import json,concurrent.futures,urllib.request,hashlib
from cds_split import req,base,D,save
jobs=json.loads((D/'CDS_T_MONTHLY_JOBS.json').read_text());out=[]
def one(j):
 if not isinstance(j['submission']['body'],dict) or 'jobID' not in j['submission']['body']:return j
 job=j['submission']['body']['jobID'];result=req(base+'/jobs/'+job);status=result['body'].get('status') if isinstance(result['body'],dict) else 'NETWORK_ERROR';rec={'key':j['key'],'jobID':job,**result}
 print(j['key'],status,flush=True)
 if status=='successful':
  res=req(base+'/jobs/'+job+'/results');save(D/f'CDS_RESULT_{j["key"]}.json',res)
  if isinstance(res['body'],dict) and 'asset' in res['body']:
   asset=res['body']['asset']['value'];p=D/f'ERA5L_{j["key"]}.nc'
   if not p.exists():
    with urllib.request.urlopen(asset['href'],timeout=45) as f:b=f.read(20_000_001)
    assert len(b)<20_000_000;assert hashlib.md5(b).hexdigest()==asset['file:checksum'];p.write_bytes(b)
 return rec
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(one,jobs):out.append(result)
save(D/'CDS_T_MONTHLY_FINAL_STATUS.json',out)
