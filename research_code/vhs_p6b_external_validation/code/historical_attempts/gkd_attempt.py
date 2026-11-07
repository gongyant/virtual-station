import sys,json,urllib.request,urllib.parse,time,hashlib,zipfile,io
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation');E=R/'external';records=[];mode=sys.argv[1] if len(sys.argv)>1 else 'individuell'
for code in ['10035801','16602303']:
 post={'zr':mode,'beginn':'01.01.2018' if mode=='individuell' else '','ende':'31.12.2020' if mode=='individuell' else '','email':'','geprueft':'1','wertart':'tmw','t':json.dumps({code:['fluesse.abfluss']},separators=(',',':')),'f':''};rec={'official_code':code,'request_form':post,'role':'OFFICIAL_CHECKED_DAILY_DISCHARGE','no_email_sent':True,'polls':[]}
 try:
  url='https://www.gkd.bayern.de/de/downloadcenter/enqueue_download';req=urllib.request.Request(url,data=urllib.parse.urlencode(post).encode(),headers={'Content-Type':'application/x-www-form-urlencoded','X-Requested-With':'XMLHttpRequest','User-Agent':'VHS-P6B-public-research/1.0'})
  with urllib.request.urlopen(req,timeout=30) as f:data=f.read(100000)
  (E/f'GKD_{code}_{mode}_REQUEST_RESPONSE.txt').write_bytes(data);response=json.loads(data);rec['response']=response;link=response.get('deeplink');assert link and response.get('result')=='success'
  for i in range(3):
   with urllib.request.urlopen(link,timeout=25) as f:b=f.read(4_000_001)
   assert len(b)<4_000_000;rec['polls'].append({'attempt':i,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'request_rejected':b'Request Rejected' in b})
   if b.startswith(b'PK\x03\x04'):
    p=E/f'GKD_{code}_2018_2020.zip';p.write_bytes(b)
    with zipfile.ZipFile(io.BytesIO(b)) as z:
     for info in z.infolist():
      if not info.is_dir():assert info.file_size<8_000_000;(E/f'GKD_{code}_{Path(info.filename).name}').write_bytes(z.read(info))
    rec['status']='DOWNLOADED';break
   (E/f'GKD_{code}_{mode}_POLL_{i}.html').write_bytes(b)
   if b'Request Rejected' in b:rec['status']='BLOCKED_REQUEST_REJECTED_NO_BYPASS';break
   time.sleep(3)
  else:rec['status']='NOT_READY_AFTER3_POLLS'
 except Exception as ex:rec['status']='FAILED';rec['error']=str(ex)
 records.append(rec);(E/f'GKD_NEW_ATTEMPTS_{mode}.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');print(code,rec['status'],rec.get('error'),flush=True)
