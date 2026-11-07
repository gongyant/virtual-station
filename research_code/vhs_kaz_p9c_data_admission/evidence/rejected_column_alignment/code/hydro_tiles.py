from acquire import *
from download_resources import walk
if __name__=='__main__':
 for kind in ['dir','acc']:
  p=get(f'https://f000.backblazeb2.com/file/hydrosheds-v1-{kind}/{kind}_files.json',f'HYDROSHEDS_{kind}_FILES.json',max_bytes=3_000_000,timeout=25)
  if not p:continue
  tree=json.loads(p.read_text(encoding='utf-8'));matches=[]
  for x in walk(tree):
   if any('n40e070' in str(v).lower() for k,v in x.items() if not isinstance(v,(dict,list))):matches.append(x)
  js(ROOT/f'evidence/HYDROSHEDS_{kind}_PILOT_LINK.json',matches)
  for m in matches:print(kind,m)
 get('https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf','HYDROSHEDS_Technical_v1_4.pdf',max_bytes=10_000_000,timeout=30)
