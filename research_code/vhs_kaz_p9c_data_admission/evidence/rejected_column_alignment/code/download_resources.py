from acquire import *
def page_props(p):
 s=p.read_text(encoding='utf-8');return json.loads(re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',s).group(1))['props']['pageProps']
def walk(x):
 if isinstance(x,dict):
  yield x
  for z in x.values():yield from walk(z)
 elif isinstance(x,list):
  for z in x:yield from walk(z)
if __name__=='__main__':
 props=page_props(ROOT/'source/WB_DATASET.html');js(ROOT/'source/WB_DATASET_EMBEDDED_METADATA.json',props)
 resources={}
 for x in walk(props):
  if x.get('resource_unique_id') in ['DR0090965','DR0090971']:
   url=x.get('url') or x.get('distribution',{}).get('url')
   if url:resources[x['resource_unique_id']]=dict(name=x.get('name'),url=url,size=x.get('distribution_size') or x.get('distribution',{}).get('distribution_size'),description=x.get('description') or x.get('identification',{}).get('description'))
 js(ROOT/'evidence/WB_RESOURCE_LINK_PROVENANCE.json',resources)
 for rid,x in resources.items():
  get(x['url'],Path(x['url']).name,max_bytes=20_000_000,timeout=45)
  print('RESOURCE',rid,x)
 p=get('https://datacatalog.worldbank.org/search/dataset/0064084/central-asia-flood-hazard','WB_FLOOD_HAZARD.html',timeout=25)
 if p:
  props=page_props(p);js(ROOT/'source/WB_FLOOD_HAZARD_METADATA.json',props)
  for x in walk(props):
   name=x.get('name','')
   if name=='Central Asia flood hazard technical report - English version':
    url=x.get('url') or x.get('distribution',{}).get('url')
    if url:
     get(url,'WB_FLOOD_TECHNICAL_REPORT_EN.pdf',max_bytes=15_000_000,timeout=40);break
