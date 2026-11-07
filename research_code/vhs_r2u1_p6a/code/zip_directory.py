import struct,json,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8');E=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a\external')
data=(E/'INDEX_ZIP_TAIL.bin').read_bytes();size=2324031564;base=size-len(data);pos=data.rfind(b'PK\x05\x06');_,_,_,_,n,csize,offset,_=struct.unpack_from('<4s4H2LH',data,pos)
p=offset-base;out=[]
for _ in range(n):
 h=struct.unpack_from('<4s6H3L5H2L',data,p);assert h[0]==b'PK\x01\x02'
 name=data[p+46:p+46+h[10]].decode('utf-8');out.append({'name':name,'compressed':h[8],'uncompressed':h[9],'offset':h[16],'method':h[4],'crc32':h[7]});p+=46+h[10]+h[11]+h[12]
(E/'STREAMFLOW_ZIP_DIRECTORY.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
print(json.dumps([x for x in out if 'monthly' in x['name'] and 'mean' in x['name']],indent=2))
