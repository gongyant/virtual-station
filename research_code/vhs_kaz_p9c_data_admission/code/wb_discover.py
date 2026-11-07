from acquire import *
from urllib.parse import urljoin
p=ROOT/'source/WB_DAILY_API_PAGE.html'
links=re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)',p.read_text(encoding='utf-8'),re.I)
for link in links:
 if '/_next/static/chunks/' not in link or 'turbopack' in link:continue
 name='WB_PUBLIC_JS_'+link.split('/')[-1]
 q=get(urljoin('https://datacatalog.worldbank.org',link),name,max_bytes=6_000_000,timeout=20)
 if q:
  s=q.read_text(encoding='utf-8')
  found=[]
  for word in ['resource_unique_id','resourceId','datacatalogapi','apiBase','API_BASE','api-service','apiservice','DR0090']:
   for m in list(re.finditer(re.escape(word),s))[:5]:found.append(s[max(0,m.start()-180):m.end()+240])
  if found:print(name,'MATCHES',found,flush=True)
