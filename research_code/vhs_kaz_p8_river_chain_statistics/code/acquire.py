from common import *
import requests,shutil,zipfile,concurrent.futures,re,platform,importlib.metadata
def fetch(name,url,big=False):
 dest=ROOT/'source'/name;log={'name':name,'url':url,'started_utc':now()};t=time.monotonic()
 if dest.exists():
  log.update(status='EXISTING_REUSED',bytes=dest.stat().st_size,sha256=sha(dest));return log
 try:
  with requests.get(url,timeout=(15,45),stream=True,headers={'User-Agent':'VHS-P8-public-research/1.0'}) as r:
   log.update(http_status=r.status_code,final_url=r.url,headers=dict(r.headers));r.raise_for_status();size=0;printed=0
   part=dest.with_suffix(dest.suffix+'.partial')
   with part.open('wb') as f:
    for chunk in r.iter_content(1024*1024):
     size+=len(chunk);assert size<(900*1024*1024 if big else 30*1024*1024),'DOWNLOAD_QUOTA';assert time.monotonic()-t<900,'DOWNLOAD_TIME_LIMIT';f.write(chunk)
     if big and size-printed>=50*1024*1024:printed=size;print(name,round(size/1024/1024),'MiB',flush=True)
   os.replace(part,dest);log.update(status='DOWNLOADED',bytes=size,sha256=sha(dest))
 except Exception as e:log.update(status='FAILED',error=repr(e))
 log.update(ended_utc=now(),elapsed_s=time.monotonic()-t);put(ROOT/'source'/('FETCH_'+name+'.json'),log);print(name,log['status'],log.get('error',''),flush=True);return log
def extract(z,d):
 with zipfile.ZipFile(z) as f:
  ms=f.infolist();assert sum(x.file_size for x in ms)<6*1024**3
  for x in ms:
   p=pathlib.PurePosixPath(x.filename);assert not p.is_absolute() and '..' not in p.parts and not (x.external_attr>>16)&0o170000==0o120000
  assert f.testzip() is None
  f.extractall(d)
 put(ROOT/'evidence'/('ZIP_'+z.stem+'.json'),{'archive_sha256':sha(z),'members':[{'name':x.filename,'size':x.file_size,'CRC':x.CRC} for x in ms],'CRC_all_pass':True})
def main():
 ROOT.mkdir(exist_ok=True);(ROOT/'source').mkdir(exist_ok=True);(ROOT/'evidence').mkdir(exist_ok=True)
 event('acquisition','STARTED')
 n1s=[p for p in LAB.glob('vhs_kaz*') if (p/'KAZ_N1_COUNTS.json').is_file()];assert len(n1s)==1;n1=n1s[0]
 put(ROOT/'evidence/DISCOVERY.json',{'KAZ_N1':str(n1),'P8':str(ROOT),'network_probe':'official HTTPS requests below','disk':dict(zip(['total','used','free'],shutil.disk_usage('E:/'))),'environment':{'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ['geopandas','shapely','pyproj','pyogrio','numpy','matplotlib']}}})
 hist=read(n1/'evidence/HISTORY_BEFORE.json')
 for line in (n1/'SHA256SUMS.txt').read_text().splitlines():
  h,rel=line.split('  ',1);hist[str(n1/rel)]=h
 hist[str(n1/'SHA256SUMS.txt')]=sha(n1/'SHA256SUMS.txt');bad=[p for p,h in hist.items() if not pathlib.Path(p).is_file() or sha(p)!=h];put(ROOT/'evidence/HISTORY_BEFORE.json',hist);put(ROOT/'evidence/HISTORY_INITIAL_CHECK.json',{'checked':len(hist),'failed':len(bad),'failures':bad});assert not bad
 urls=[('zenodo_17077776.json','https://zenodo.org/api/records/17077776'),('zenodo_17077776.html','https://zenodo.org/records/17077776'),('hydrorivers.html','https://www.hydrosheds.org/products/hydrorivers'),('HydroRIVERS_TechDoc_v10.pdf','https://data.hydrosheds.org/file/technical-documentation/HydroRIVERS_TechDoc_v10.pdf'),('HydroSHEDS_TechDoc_v1_4.pdf','https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf'),('official_network.html','https://www.kazhydromet.kz/en/hydrological-monitoring/interaktivnaya-karta-gidrologicheskogo-monitoringa'),('qazsu.html','https://qazsu.gov.kz/'),('official_meteo_db.html','https://www.kazhydromet.kz/en/meteo_db'),('hydro_database.html','https://meteo.kazhydromet.kz/database_hydro/')]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:logs=list(ex.map(lambda u:fetch(*u),urls))
 put(ROOT/'source/ACCESS_LOG.json',logs)
 if (ROOT/'source/zenodo_17077776.json').is_file():
  j=read(ROOT/'source/zenodo_17077776.json');print('ZENODO LICENSE',j['metadata'].get('license'),flush=True);put(ROOT/'source/ZENODO_METADATA_SUMMARY.json',{'doi':j.get('doi'),'version':j['metadata'].get('version'),'license':j['metadata'].get('license'),'files':j.get('files'),'creators':j['metadata'].get('creators')})
  assert j['metadata'].get('license',{}).get('id') in ['cc-by-4.0','cc-by-sa-4.0','cc0-1.0']
  rec=next(x for x in j['files'] if x['key']=='ver.2.zip');l=fetch('ver.2.zip',rec['links']['self']);logs.append(l)
  if l['status']!='FAILED':
   assert hashlib.md5((ROOT/'source/ver.2.zip').read_bytes()).hexdigest()==rec['checksum'].split(':')[-1];extract(ROOT/'source/ver.2.zip',ROOT/'source/basins_v2')
 # Official global release avoids uncertain regional-tile completeness.
 assert 'HydroRIVERS_v10_shp.zip' in (ROOT/'source/hydrorivers.html').read_text(encoding='utf-8')
 l=fetch('HydroRIVERS_v10_shp.zip','https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_shp.zip',True);logs.append(l)
 if l['status']!='FAILED':extract(ROOT/'source/HydroRIVERS_v10_shp.zip',ROOT/'source/hydrorivers_global')
 put(ROOT/'source/ACCESS_LOG.json',logs);event('acquisition','FINISHED',download_status=[{'file':l['name'],'status':l['status']} for l in logs]);print('ACQUIRE FINISHED',flush=True)
if __name__=='__main__':main()
