"""Small bibliographic JSON requests only; never retrieve hydrologic archives."""
import json,urllib.request,urllib.parse,concurrent.futures
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]/'evidence'
DOIS=['10.1623/hysj.48.6.857.51421','10.1002/wat2.1487','10.5194/hess-27-139-2023','10.1029/2021WR030394','10.1111/ecog.02881','10.1002/hyp.9740','10.5194/essd-13-4529-2021','10.5194/hess-21-5293-2017','10.5194/essd-16-2741-2024']
def fetch(doi):
    url='https://api.crossref.org/works/'+urllib.parse.quote(doi,safe='')
    try:
        with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VHS-B0-metadata-audit/1.0'}),timeout=25) as r:
            raw=r.read(2000001)
            if len(raw)>2000000:raise ValueError('metadata limit')
        m=json.loads(raw)['message']
        return dict(doi=doi,metadata_source=url,status='VERIFIED_CROSSREF',title=m.get('title'),author=m.get('author'),container=m.get('container-title'),published=m.get('published'),URL=m.get('URL'),type=m.get('type'))
    except Exception as e:return dict(doi=doi,metadata_source=url,status='UNVERIFIED',error=str(e))
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:records=list(ex.map(fetch,DOIS))
(OUT/'crossref_records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
for r in records:print(r['doi'],r['status'],r.get('title',''))
