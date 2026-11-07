import pathlib,json,hashlib,csv,datetime,re,urllib.request,urllib.error,html,collections,importlib.util
from html.parser import HTMLParser
LAB=pathlib.Path(r'E:\VHS_Public_Baseline_Lab');ROOT=LAB/'vhs_kaz_n1_national_virtual_stations';REPO=pathlib.Path(r'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1')
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def put(p,v):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def readj(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def csvout(p,rs,fields=None):
 p=pathlib.Path(p);p.parent.mkdir(parents=True,exist_ok=True);fields=fields or list(dict.fromkeys(k for r in rs for k in r))
 with p.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rs)
class Text(HTMLParser):
 def __init__(self):super().__init__();self.txt=[];self.links=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag in ['script','style']:self.skip+=1
  if tag in ['a','script','iframe','link']:self.links.append({'tag':tag,**a})
 def handle_endtag(self,tag):
  if tag in ['script','style']:self.skip=max(0,self.skip-1)
 def handle_data(self,data):
  if not self.skip and data.strip():self.txt.append(data.strip())
def fetch(name,url,max_bytes=5000000):
 now=datetime.datetime.now(datetime.timezone.utc).isoformat();entry={'name':name,'url':url,'accessed_utc':now,'access_date_client_timezone':'2026-11-03 Asia/Singapore'}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'VHS-KAZ-N1 research source verification'})
  with urllib.request.urlopen(req,timeout=35) as r:
   body=r.read(max_bytes+1);assert len(body)<=max_bytes,'SOURCE_EXCEEDS_BOUNDED_DOWNLOAD';entry.update(http_status=r.status,final_url=r.url,response_headers=dict(r.headers))
  p=ROOT/'source'/f'{name}.html';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(body);entry.update(path=str(p),sha256=sha(p),bytes=len(body))
  parser=Text();parser.feed(body.decode('utf-8',errors='replace'));text='\n'.join(parser.txt);(p.with_suffix('.txt')).write_text(text,encoding='utf-8');put(p.with_suffix('.links.json'),parser.links);entry['text_path']=str(p.with_suffix('.txt'));print(name,len(body),entry['http_status'],flush=True)
 except Exception as e:entry.update(status='DOWNLOAD_BLOCKED_OR_FAILED',error=str(e));print(name,str(e)[:120],flush=True)
 return entry
def main():
 assert not (ROOT/'KAZ_N1_OFFICIAL_BASELINE.json').exists(),'Do not overwrite intake'
 ROOT.mkdir(parents=True,exist_ok=True)
 d=LAB/'vhs_p6d_failure_diagnostics';hist=readj(d/'evidence/HISTORY_BEFORE.json')
 for folder in [d,LAB/'vhs_p7a_hydrological_models',LAB/'vhs_web_s1_research_integration']:
  for line in (folder/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
   h,rel=line.split('  ',1);hist[str(folder/rel)]=h
  hist[str(folder/'SHA256SUMS.txt')]=sha(folder/'SHA256SUMS.txt')
 bad=[p for p,h in hist.items() if not pathlib.Path(p).exists() or sha(p)!=h];assert not bad,bad[:3]
 put(ROOT/'evidence/HISTORY_BEFORE.json',hist);put(ROOT/'evidence/HISTORY_INITIAL_CHECK.json',{'checked':len(hist),'passed':len(hist),'failed':0})
 urls=[('kazhydromet_network','https://www.kazhydromet.kz/en/hydrological-monitoring/interaktivnaya-karta-gidrologicheskogo-monitoringa'),('gov_area','https://www.gov.kz/article/19305?lang=en'),('gov_eight_basins','https://www.gov.kz/memleket/entities/water/press/news/details/878044?lang=ru'),('hydrorivers_product','https://www.hydrosheds.org/products/hydrorivers'),('hydrobasins_product','https://www.hydrosheds.org/products/hydrobasins')]
 sources=[fetch(n,u) for n,u in urls];put(ROOT/'source/SOURCE_LOG.json',sources)
 nt=(ROOT/'source/kazhydromet_network.txt').read_text(encoding='utf-8');at=(ROOT/'source/gov_area.txt').read_text(encoding='utf-8')
 assert re.search(r'442\s+observation posts',nt) and all(str(n) in nt for n in [381,61,394,38])
 assert re.search(r'2\s*724\s*900',at)
 facts={'dataset':'KAZ_N1_OFFICIAL_NETWORK_BASELINE','access_date':'2026-11-03','network_reference_year':'NOT_STATED_ON_CURRENT_PAGE','N_real_all':442,'N_real_river':394,'lake_posts':38,'marine_posts':7,'marine_hydrometeorological_stations':3,'marine_combined':10,'permanent':381,'seasonal':61,'area_km2':2724900,'network_scope':'Kazhydromet network displayed on current official page; not asserted all operators or all historical gauges','river_scope':'394 posts observing228 rivers,1stream,3channels; not394 rivers or394 usable Q series','comparability':'2024 count377 is historical and not used as the current numerator','sources':sources[:2],'verification':{'442_equals_394_plus_38_plus_7_plus_3':442==394+38+7+3,'442_equals_381_plus_61':442==381+61},'model_accuracy_Kazakhstan':None,'Kazakhstan_accuracy_status':'NOT_VALIDATED'}
 put(ROOT/'KAZ_N1_OFFICIAL_BASELINE.json',facts)
 densities=[{'scope':scope,'N':n,'area_km2':2724900,'stations_per_km2':n/2724900,'stations_per_10000_km2':n/2724900*10000,'km2_per_station':2724900/n,'status':'OFFICIAL_COUNT_DERIVED_DENSITY','access_date':'2026-11-03'} for scope,n in [('national_all_Kazhydromet',442),('national_river_Kazhydromet',394)]]
 csvout(ROOT/'KAZ_N1_BASELINE_DENSITY.csv',densities)
 links=readj(ROOT/'source/kazhydromet_network.links.json');maps=[x for x in links if 'ecodata' in x.get('href','') or x['tag']=='iframe'];put(ROOT/'source/OFFICIAL_MAP_LINKS.json',maps);print('MAP LINKS',maps,flush=True)
 (ROOT/'KAZ_N1_SUPERVISOR_ANSWER_ZH.md').write_text('''# 导师问题：第一批已核实基线\n访问日期2026-11-03。官方现页列示442个Kazhydromet监测点，其中河流394、湖泊38、海洋7测点+3水文气象站，常年381、季节61。未把2024年377站作为同一时期。固定面积2,724,900 km²。\n全类型密度0.000162207787441741个/km²，即1.62207787441741个/万km²；河流密度0.0001445924621个/km²，即1.445924621个/万km²（精确计算见CSV）。\n全国候选、可预测、研究准入数量及PUB精度正在依据实际文件核验，尚不以欧洲已知站时间外结果替代。最终答案将在本轮真实GIS/PUB支持检查后更新。\n''',encoding='utf-8')
 print('BASELINE READY',densities,flush=True)
if __name__=='__main__':main()
