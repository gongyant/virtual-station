import json,re,sys,importlib.util
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
L=Path(r'E:\VHS_Public_Baseline_Lab');R=L/'vhs_p6b_external_validation'
members=json.loads((L/'source/ARCHIVE_MEMBERS.json').read_text(encoding='utf-8-sig'))
print('GEOMETRY_MEMBERS',[(m['name'],m['bytes']) for m in members if any(x in m['name'].lower() for x in ['.shp','.prj','.dbf','.shx','grid','weight'])][:35])
print('MODELS',list((L/'p4_final_reconstruction/models/V2/ID_818/P2-L1').iterdir()))
from html.parser import HTMLParser
class Text(HTMLParser):
 def __init__(self):super().__init__();self.parts=[]
 def handle_data(self,data):self.parts.append(data)
soup=Text();soup.feed((L/'source/official/paper.html').read_text(encoding='utf-8'));txt=' '.join(soup.parts)
parts=[]
for term in ['4.2','ERA5-Land','area-weighted','accumulated','UTC','temperature','hourly']:
 p=0
 for j in range(8):
  i=txt.find(term,p)
  if i<0:break
  parts.append({'term':term,'excerpt':txt[max(0,i-250):i+900]});p=i+len(term)
(R/'driver/LAMAH_PROCESSING_EXCERPTS.json').write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding='utf-8')
print('PROCESSING',*[p for p in parts if p['term'] in ['area-weighted','accumulated','UTC']],sep='\n')
p=Path.home()/'.cdsapirc'
if p.exists():
 fields={}
 for line in p.read_text().splitlines():
  if ':' in line:k,v=line.split(':',1);fields[k.strip()]=v.strip()
 print('CDS_CONFIG_SAFE',{'url':fields.get('url'),'key_present':bool(fields.get('key')),'key_looks_placeholder':any(x in fields.get('key','').lower() for x in ['your','placeholder','example','<','>']),'config_fields':list(fields)})
 print('WINDOWS_TRUST_SUPPORT',bool(importlib.util.find_spec('truststore')))
