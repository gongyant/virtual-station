import json,sys
from cds_split import req,base,D,save
initial=json.loads((D/'CDS_REAL_ACCESS_RESULT.json').read_text())['response']['jobID'];annual=json.loads((D/'CDS_SPLIT_JOBS.json').read_text())[1]['submission']['body']['jobID'];monthly=json.loads((D/'CDS_T_MONTHLY_JOBS.json').read_text())[0]['submission']['body']['jobID']
out=[]
for name,job in [('initial',initial),('annual',annual),('monthly',monthly)]:
 for endpoint in ['', '/results']:
  result=req(base+'/jobs/'+job+endpoint);out.append({'role':name,'jobID':job,'endpoint':endpoint,**result});print(name,endpoint,json.dumps(result)[:1800],flush=True)
save(D/'CDS_ERROR_DETAILS.json',out)
