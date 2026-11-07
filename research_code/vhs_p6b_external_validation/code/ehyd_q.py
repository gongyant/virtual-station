import json,concurrent.futures
from acquire import dl,R,jw
ss=json.loads((R/'evidence/STATIONS_27.json').read_text());jobs=[]
for s in ss:
 if s['country']=='AUT':
  g=s['official_gauge_id'];jobs.append((f'https://ehyd.gv.at/services/MessstellenExtraData/owf?id={g}&file=5',f'EHYD_{g}_file5.txt'))
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rr=list(pool.map(lambda j:dl(*j),jobs))
jw(R/'external/EHYD_Q_DOWNLOAD_RECEIPTS.json',rr)
