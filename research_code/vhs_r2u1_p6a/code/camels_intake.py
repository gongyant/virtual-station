import json,sys,urllib.request,hashlib,struct,zlib,time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');E=R/'external';rec=[]
def save(n,x):(E/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def get(url,name,limit=3000000,ran=None):
 p=E/name
 if p.exists():return p.read_bytes()
 hd={'User-Agent':'VHS-P6A-targeted-data-intake/1.0'}
 if ran:hd['Range']='bytes='+ran
 with urllib.request.urlopen(urllib.request.Request(url,headers=hd),timeout=40) as f:
  if ran:assert f.status==206
  raw=f.read(limit+1);assert len(raw)<=limit
  rec.append({'url':url,'range':ran,'status':f.status,'content_range':f.headers.get('Content-Range'),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'file':name});p.write_bytes(raw)
 save('CAMELS_TARGETED_RECEIPTS.json',rec);print('GOT',name,len(raw),flush=True);return raw
raw=get('https://zenodo.org/api/records/15025258','CAMELS_CH_RECORD.json');d=json.loads(raw)
print('RECORD',d['id'],d['metadata'].get('version'),d['metadata'].get('license'));print('FILES',[(f['key'],f['size']) for f in d['files']])
item=next(f for f in d['files'] if f['key']=='camels_ch.zip');url=item['links']['self'];size=item['size'];tail=get(url,'CAMELS_ZIP_TAIL.bin',131072,'-131072');e=tail.rfind(b'PK\x05\x06');h=struct.unpack_from('<4s4H2LH',tail,e);offset=h[6];n=h[4];base=size-len(tail)
central=tail[offset-base:]
if offset<base:central=get(url,'CAMELS_CENTRAL.bin',2000000,f'{offset}-{offset+h[5]-1}')
pos=0;directory=[]
for _ in range(n):
 h=struct.unpack_from('<4s6H3L5H2L',central,pos);assert h[0]==b'PK\x01\x02';name=central[pos+46:pos+46+h[10]].decode('utf-8');directory.append({'name':name,'compressed':h[8],'uncompressed':h[9],'offset':h[16],'method':h[4],'crc32':h[7]});pos+=46+h[10]+h[11]+h[12]
save('CAMELS_ZIP_DIRECTORY.json',directory)
chosen=[x for x in directory if (('2304' in x['name'] and '/timeseries/observation_based/' in x['name']) or ('static_attributes' in x['name'] and 'topographic_attributes' in x['name']) or x['name']=='camels_ch/readme.txt') and not x['name'].startswith('__MACOSX') and not x['name'].endswith('/')]
print('CHOSEN',chosen)
if not any('2304' in x['name'] for x in chosen):print('2304_MATCHES',[x for x in directory if '2304' in x['name']])
for x in chosen:
 assert x['compressed']<6000000
 short=Path(x['name']).name;cache='CAMELS_'+hashlib.sha256(x['name'].encode()).hexdigest()[:12];head=get(url,cache+'.head',4096,f'{x["offset"]}-{x["offset"]+4095}');h=struct.unpack_from('<4s5H3L2H',head);start=x['offset']+30+h[9]+h[10];raw=get(url,cache+'.deflate',6000000,f'{start}-{start+x["compressed"]-1}');out=zlib.decompress(raw,-15) if x['method']==8 else raw
 assert len(out)==x['uncompressed'] and zlib.crc32(out)==x['crc32'];(E/('CAMELS_'+short)).write_bytes(out);print('EXTRACTED',short,len(out),flush=True)
save('CAMELS_EXTRACTED_MEMBERS.json',chosen)
