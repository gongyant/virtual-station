from common import *
import requests,re
d=pd.read_csv(ROOT/'source/OFFICIAL_WATER_LINKS.csv');pdf=d[d.url.str.contains(r'\.pdf(?:\?|$)',case=False,regex=True)]
records=[]
for r in pdf.drop_duplicates('url').itertuples():
    a=dict(url=r.url,link_title=r.title,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),maximum_bytes=20_000_000)
    dest=ROOT/'source/OFFICIAL_HYDROLOGICAL_BULLETIN_2023.pdf'
    try:
        with requests.get(r.url,stream=True,timeout=(10,35)) as response:
            a.update(status=response.status_code,content_length=response.headers.get('Content-Length'));response.raise_for_status()
            if int(response.headers.get('Content-Length',0))>20_000_000:raise RuntimeError('Official small bulletin exceeds cap')
            start=time.monotonic();size=0
            with dest.open('wb') as out:
                for b in response.iter_content(128*1024):
                    size+=len(b)
                    if size>20_000_000 or time.monotonic()-start>150:raise RuntimeError('Bulletin bounded download exceeded')
                    out.write(b)
        a.update(bytes=dest.stat().st_size,sha256=digest(dest),path=str(dest),download_complete=True)
    except Exception as e:a.update(error=f'{type(e).__name__}: {e}',download_complete=False)
    records.append(a);event('official_bulletin_download',**a)
    break
for name,url in [('ERA5_LAND_CATALOG.html','https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview'),('HYDROBASINS_SOURCE_TERMS.html','https://www.hydrosheds.org/products/hydrobasins')]:
    a=dict(url=url,label=name,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        r=requests.get(url,timeout=(10,20));p=ROOT/'source'/name;p.write_bytes(r.content);a.update(status=r.status_code,bytes=len(r.content),sha256=digest(p))
    except Exception as e:a['error']=str(e)
    records.append(a);event('driver_static_metadata_source',**a)
js(ROOT/'source/BULLETIN_AND_DRIVER_DOWNLOAD_LOG.json',records)
# DOI metadata supports citations, without substituting abstracts for the read sources.
refs=[]
for doi in ['10.1038/s41597-023-02474-8','10.1002/hyp.9740','10.5194/essd-13-4349-2021','10.5194/hess-22-2225-2018','10.5194/hess-23-4323-2019']:
    a=dict(doi=doi,url='https://api.crossref.org/works/'+doi)
    try:
        r=requests.get(a['url'],timeout=(10,15));r.raise_for_status();m=r.json()['message'];js(ROOT/'source'/('CITATION_'+doi.split('/')[-1]+'.json'),m);a.update(verified=True,title=m.get('title'),authors=m.get('author'),year=m.get('published',{}),container=m.get('container-title'),volume=m.get('volume'),page=m.get('page'),licenses=m.get('license'))
    except Exception as e:a.update(verified=False,error=str(e))
    refs.append(a)
js(ROOT/'sci/VERIFIED_REFERENCE_METADATA.json',refs);event('citation_metadata_verified',passed=sum(x['verified'] for x in refs),failed=sum(not x['verified'] for x in refs))
