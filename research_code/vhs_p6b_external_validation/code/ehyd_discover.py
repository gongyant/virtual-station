import sys,json,concurrent.futures
from acquire import dl,R,jw
jobs=[(f'https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048&file={k}',f'EHYD_200048_file{k}.txt') for k in range(6,13)]
jobs += [('https://ehyd.gv.at/services/Messstellen/info?id=200048','EHYD_INFO_200048_RETRY.json'),('https://ehyd.gv.at/services/Messstellen/json','EHYD_ALL_STATIONS_RETRY.json'),('https://ehyd.gv.at/assets/eHYD/pdf/eHYD_Allgemein.pdf','EHYD_USE_TERMS_RETRY.pdf')]
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(lambda j:dl(*j),jobs))
jw(R/'external/EHYD_FILE_DISCOVERY_RECEIPTS.json',rows)
for k in range(2,13):
 p=R/'external'/f'EHYD_200048_file{k}.txt'
 if p.exists():
  s=p.read_text(encoding='latin1');header=s.split('Werte:')[0];print('FILE',k,'size',p.stat().st_size,header[-550:].replace('\n',' | '),flush=True)
