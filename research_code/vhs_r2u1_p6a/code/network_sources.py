import hashlib,json,struct,sys,time,urllib.request,zlib,zipfile
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');E=R/'external';receipts=[]
def sha(data):return hashlib.sha256(data).hexdigest()
def jw(n,v):(E/n).write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def get(url,name,limit=3000000,byte_range=None):
 p=E/name
 if p.exists():return p.read_bytes()
 headers={'User-Agent':'VHS-P6A-targeted-research/1.0'}
 if byte_range:headers['Range']='bytes='+byte_range
 req=urllib.request.Request(url,headers=headers)
 with urllib.request.urlopen(req,timeout=120) as f:
  if byte_range:assert f.status==206,('RANGE_IGNORED_ABORT',f.status)
  if f.headers.get('Content-Length'):assert int(f.headers['Content-Length'])<=limit
  data=f.read(limit+1);assert len(data)<=limit
  p.write_bytes(data);receipts.append({'url':url,'byte_range':byte_range,'status':f.status,'content_range':f.headers.get('Content-Range'),'bytes':len(data),'sha256':sha(data),'file':name,'UTC':time.strftime('%Y-%m-%dT%H:%M:%S%z')});jw('TARGETED_DOWNLOAD_RECEIPTS.json',receipts)
 print('GOT',name,len(data),flush=True);return data
def extract_member(url,item,name):
 offset=item['offset'];head=get(url,name+'.local_header.bin',100000, f'{offset}-{offset+4095}')
 h=struct.unpack_from('<4s5H3L2H',head,0);assert h[0]==b'PK\x03\x04';start=offset+30+h[9]+h[10];n=item['compressed']
 assert n<65000000
 data=get(url,name+'.deflate',65000000,f'{start}-{start+n-1}')
 assert len(data)==n
 raw=zlib.decompress(data,-15) if item['method']==8 else data
 assert len(raw)==item['uncompressed'] and zlib.crc32(raw)==item['crc32']
 (E/name).write_bytes(raw);print('EXTRACTED',name,len(raw),flush=True)
 jw(name+'.provenance.json',{'url':url,'zip_member':item,'sha256_uncompressed':sha(raw),'CRC32_pass':True,'whole_archive_MD5_not_verified':'partial member extraction only'})
directory=json.loads((E/'STREAMFLOW_ZIP_DIRECTORY.json').read_text())
item=next(i for i in directory if i['name']=='streamflow_indices/monthly/monthly_streamflow_mean.csv')
extract_member('https://zenodo.org/api/records/17598150/files/streamflow_indices.zip/content',item,'monthly_streamflow_mean.csv')
for url,name in [('https://zenodo.org/api/records/7784632','CAMELS_CH_RECORD.json'),('https://www.gkd.bayern.de/de/fluesse/abfluss/bayern/dillingen-10035801/download','GKD_DILLINGEN_DOWNLOAD.html'),('https://www.gkd.bayern.de/de/fluesse/abfluss/bayern/stegen-16602303/stammdaten','GKD_STEGEN_STATION.html'),('https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen-und-daten/2304','FOEN_2304_STATION.html')]:
 try:
  raw=get(url,name)
  if name.endswith('.json'):
   d=json.loads(raw);print('CAMELS_VERSION',d['id'],d['metadata'].get('version'),d['metadata'].get('license'));print('CAMELS_FILES',[(f['key'],f['size'],f['links']['self']) for f in d['files']])
 except Exception as e:print('SOURCE_FAIL',name,str(e));receipts.append({'url':url,'file':name,'status':'FAILED','error':str(e)})
jw('TARGETED_DOWNLOAD_RECEIPTS.json',receipts)
