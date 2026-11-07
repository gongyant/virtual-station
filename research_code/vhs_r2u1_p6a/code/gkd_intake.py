"""Retrieve official daily discharge through the public GKD download form, no email."""
import hashlib,json,sys,time,urllib.request,urllib.parse,zipfile,io
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');E=R/'external';receipts=[]
def save(): (E/'GKD_DOWNLOAD_RECEIPTS.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
def small(url,name):
 p=E/name
 if p.exists():return p.read_bytes()
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'VHS-P6A-public-research/1.0'}),timeout=30) as f:raw=f.read(2000000)
 p.write_bytes(raw);receipts.append({'url':url,'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)});save();return raw
for code,slug,basin in [('10035801','dillingen','donau_bis_kelheim'),('16602303','stegen','isar')]:
 try:
  small(f'https://www.hnd.bayern.de/pegel/{basin}/{slug}-{code}/stammdaten',f'GKD_PRIMARY_{code}_STATION.html')
  small(f'https://www.gkd.bayern.de/de/fluesse/abfluss/{basin}/{slug}-{code}/download',f'GKD_PRIMARY_{code}_DOWNLOAD.html')
  if (E/f'GKD_{code}_daily.zip').exists():continue
  post={'zr':'gesamt','beginn':'','ende':'','email':'','geprueft':'1','wertart':'tmw','t':json.dumps({code:['fluesse.abfluss']},separators=(',',':')),'f':''}
  url='https://www.gkd.bayern.de/de/downloadcenter/enqueue_download';data=urllib.parse.urlencode(post).encode();req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest','User-Agent':'VHS-P6A-public-research/1.0'})
  with urllib.request.urlopen(req,timeout=40) as f:response=json.load(f)
  (E/f'GKD_{code}_REQUEST.json').write_text(json.dumps({'url':url,'form':post,'response':response},ensure_ascii=False,indent=2),encoding='utf-8');print('GKD_RESPONSE',code,response,flush=True)
  link=response.get('deeplink');assert response.get('result')=='success' and link
  if link.startswith('/'):link=urllib.parse.urljoin('https://www.gkd.bayern.de',link)
  for attempt in range(12):
   try:
    req=urllib.request.Request(link,headers={'User-Agent':'VHS-P6A-public-research/1.0'})
    with urllib.request.urlopen(req,timeout=20) as f:
     final=f.geturl();raw=f.read(6000001);assert len(raw)<=6000000
    if raw.startswith(b'PK\x03\x04'):
     (E/f'GKD_{code}_daily.zip').write_bytes(raw);receipts.append({'gauge_id':code,'request_url':url,'download_url':final,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'quality_filter':'geprueft=1','source_role':'official_measured_discharge_daily'});save()
     with zipfile.ZipFile(io.BytesIO(raw)) as z:
      for info in z.infolist():
       if info.is_dir():continue
       assert info.file_size<15000000;dest=E/(f'GKD_{code}_'+Path(info.filename).name);dest.write_bytes(z.read(info));print('GKD_EXTRACTED',dest.name,info.file_size,flush=True)
     break
    print('GKD_PENDING',code,attempt,len(raw),final,flush=True)
   except Exception as e:print('GKD_POLL',code,attempt,str(e),flush=True)
   time.sleep(3)
  else:raise RuntimeError('Download not ready within12 polls')
 except Exception as e:receipts.append({'gauge_id':code,'status':'FAILED','error':str(e)});save();print('GKD_FAILED',code,str(e),flush=True)
