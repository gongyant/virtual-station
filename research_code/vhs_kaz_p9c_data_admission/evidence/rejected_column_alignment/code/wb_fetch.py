from acquire import *
if __name__=='__main__':
 base='https://ddh-openapi.worldbank.org'
 for rid in ['DR0090971','DR0090965']:
  for kind in ['metadata','data']:
   suffix='?top=5' if kind=='data' and rid=='DR0090965' else ''
   p=get(f'{base}/resources/{rid}/{kind}{suffix}',f'WB_{rid}_{kind}.json',max_bytes=20_000_000)
   if p:print(rid,kind,p.read_text(encoding='utf-8')[:4500])
 # Repeat only previously failed public HTML requests, after its API page succeeded.
 get('https://datacatalog.worldbank.org/search/dataset/0064229/central-asia-flood-hazard-discharge-data','WB_DATASET.html',timeout=25)
