from acquire import *
if __name__=='__main__':
 p=get('https://www.hydrosheds.org/hydrosheds-core-downloads','HYDROSHEDS_CORE_DOWNLOADS.html',max_bytes=3_000_000,timeout=30)
 if p:
  s=p.read_text(encoding='utf-8')
  links=re.findall(r'(?:src|href)=["\x27]([^"\x27]+)',s)
  js(ROOT/'evidence/HYDROSHEDS_PUBLIC_LINKS.json',links)
  selected=[x for x in links if any(t in x for t in ['dir_15s','aca_15s','Technical','technical','tree','.js','.json'])]
  print(json.dumps(selected,indent=2))
  for m in re.finditer(r'n40e070|n40e080|treeData|\.json',s,re.I):print(s[max(0,m.start()-150):m.end()+250])
