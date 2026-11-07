import csv,json,sys,struct,urllib.request,urllib.error
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');E=R/'external'
def jl(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def jw(n,x):(E/n).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['estreams_gauging_stations.csv','estreams_streamflow_catalogue.csv']:
 p=E/name
 with p.open(encoding='utf-8-sig') as f:
  sample=f.read(4000);f.seek(0);d=csv.Sniffer().sniff(sample,delimiters=',;');rows=list(csv.DictReader(f,delimiter=d.delimiter))
 print('COLUMNS',name,list(rows[0]))
 found=[r for r in rows if any(any(v in str(val) for v in ['10035801','16602303']) for val in r.values()) or any(str(val).strip()=='2304' for val in r.values())]
 if name.endswith('catalogue.csv'):
  found=[r for r in rows if any(v in str(r) for v in ['Switzerland','Bavaria','Bayern','FOEN','BAFU'])]
 print('MATCHES',name,json.dumps(found,ensure_ascii=False));jw('MATCH_'+name+'.json',found)
license=(E/'licenses.txt').read_text(encoding='utf-8-sig');print('LICENSE_PARTS','\n'.join(x for x in license.splitlines() if any(w in x.lower() for w in ['streamflow','switz','bavaria','bayern','noncomm','non-comm','creative','bafu','foen'])))
record=jl(E/'ESTREAMS_1_4_RECORD.json');entry=next(x for x in record['files'] if x['key']=='streamflow_indices.zip')
url=entry['links']['self'];print('ZIP_URL',url,'SIZE',entry['size'])
attempt=[]
for u in [url,'https://zenodo.org/records/17598150/files/streamflow_indices.zip?download=1']:
 req=urllib.request.Request(u,headers={'Range':'bytes=-131072','User-Agent':'VHS-P6A-targeted-intake/1.0'})
 try:
  with urllib.request.urlopen(req,timeout=45) as f:
   row={'url':u,'status':f.status,'headers':dict(f.headers)}
   if f.status==206:
    data=f.read(131073);assert len(data)<=131072
    (E/'INDEX_ZIP_TAIL.bin').write_bytes(data);row['tail_bytes']=len(data);attempt.append(row)
    print('RANGE_SUPPORTED',row)
    pos=data.rfind(b'PK\x05\x06');print('EOCD',pos,struct.unpack_from('<4s4H2LH',data,pos));break
   else:row['reason']='Range ignored; large body was not downloaded';attempt.append(row);print('RANGE_IGNORED',row)
 except Exception as e:attempt.append({'url':u,'error':str(e)});print('ERROR',e)
jw('TARGETED_RANGE_PROBE.json',attempt)
