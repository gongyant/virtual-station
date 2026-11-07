from intake import *
import shutil,socket,numpy as np,geopandas as gpd
from shapely.geometry import shape,mapping
from shapely.ops import transform
from pyproj import Transformer
def rs(p):
 with open(p,encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def numeric(r):
 out={}
 for k,v in r.items():
  if v=='':out[k]=None
  elif v in ['True','False']:out[k]=v=='True'
  elif re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',v):out[k]=float(v)
  else:out[k]=v
 return out
def main():
 w=ROOT/'web_candidate';assert not (w/'host/server.py').exists(),'Candidate already exists'
 s=socket.socket();s.settimeout(1);port_status=s.connect_ex(('127.0.0.1',8795));s.close();assert port_status!=0,'8795 already occupied; nothing stopped'
 put(ROOT/'evidence/PORT_8795_BEFORE.json',{'connect_ex':port_status,'connected':False,'no_existing_process_stopped':True})
 old=LAB/'vhs_web_s1_research_integration'
 for line in (old/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  h,rel=line.split('  ',1)
  if not (rel.startswith('host/') or rel.startswith('diagnostics/') or rel.startswith('p6/') or rel.startswith('research/') or rel=='WEB_S1_DATA_CONTRACT.json'):continue
  p=old/rel;assert sha(p)==h;dest=w/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
 for name in ['start_host.ps1','stop_host.ps1']:
  text=(old/name).read_text(encoding='utf-8-sig').replace('8794','8795').replace('WEB-S1','KAZ-N1');(w/name).write_text(text,encoding='utf-8-sig')
 contract=readj(w/'WEB_S1_DATA_CONTRACT.json');oldpin=str(old/'research/P7A_SUMMARY.json');contract['source_pins'][str(w/'research/P7A_SUMMARY.json')]=contract['source_pins'].pop(oldpin);put(w/'WEB_S1_DATA_CONTRACT.json',contract)
 rp=w/'host/r2_public.py';text=rp.read_text(encoding='utf-8')
 text=text.replace('R1ROOT=R2ROOT.parent/"vhs_web_r1_public_results_bridge"','R1ROOT=Path(r"E:\\VHS_Public_Baseline_Lab\\vhs_web_r1_public_results_bridge")')
 text=text.replace('from s1_research import ResearchEvidence','from s1_research import ResearchEvidence\nfrom kaz_national import KazNationalEvidence')
 text=text.replace('self.s1=ResearchEvidence()','self.s1=ResearchEvidence()\n  self.kaz=KazNationalEvidence()')
 text=text.replace('def handle(self,path,qs):','def handle(self,path,qs):\n  if path.startswith("/api/v6/public-kaz/"):return 403,{"status":"PRODUCTION_DISPLAY_NOT_GRANTED"}\n  if path.startswith("/api/v6/candidate-kaz/"):\n   if not self.candidate_local:return 403,{"status":"CANDIDATE_DISPLAY_DISABLED"}\n   if any(len(v)!=1 for v in qs.values()):return 400,{"status":"DUPLICATE_PARAM"}\n   return self.kaz.handle(path,{k:v[0] for k,v in qs.items()})')
 rp.write_text(text,encoding='utf-8')
 server=w/'host/server.py';text=server.read_text(encoding='utf-8').replace('default=8794','default=8795').replace('8775,8791,8792,8793)','8775,8791,8792,8793,8794)')
 text=text.replace('elif p.startswith("/api/v6/candidate-public/") or p.startswith("/api/v6/public/"):','elif p.startswith(("/api/v6/candidate-public/","/api/v6/public/","/api/v6/candidate-kaz/","/api/v6/public-kaz/")):')
 text=text.replace('h["datasets"]["LAMAH_CE_PUBLIC_V1"] = "FROZEN_PUBLIC_RESULTS"','h["datasets"]["LAMAH_CE_PUBLIC_V1"] = "FROZEN_PUBLIC_RESULTS"\n            h["datasets"]["KAZAKHSTAN_PUBLIC_NETWORK"] = "OFFICIAL_BASELINE_PARTIAL_GEOMETRY_NO_KAZ_PREDICTIONS"')
 server.write_text(text,encoding='utf-8')
 idx=w/'host/static/index.html';text=idx.read_text(encoding='utf-8').replace('</div>\n    <div class="topstatus"','<button type="button" data-ds="KAZAKHSTAN_PUBLIC_NETWORK" role="tab">哈萨克斯坦全国覆盖</button>\n    </div>\n    <div class="topstatus"',1)
 text=text.replace('WEB-S1科研证据集成候选','KAZ-N1全国覆盖与PUB评估候选').replace('</body>','<script src="/static/view_kaz_national.js"></script>\n</body>');idx.write_text(text,encoding='utf-8')
 inputs=['KAZ_N1_OFFICIAL_BASELINE.json','KAZ_N1_COUNTS.json','KAZ_N1_BASELINE_DENSITY.csv','KAZ_N1_DATA_READINESS.csv','KAZ_N1_GIS_EXECUTION.json','KAZ_N1_GEOMETRY_ASSIGNMENT_BY_BASIN.csv','KAZ_N1_NATIONAL_DENSITY_SCENARIOS.csv','KAZ_N1_FROZEN_PROTOCOL.json','KAZ_N1_UG_VALIDATION_METRICS.csv','pub/EU_PUB_SUMMARY.csv','pub/EU_PUB_FINAL_STATUS.json','data/SUPERVISOR_FOUR_ANSWERS.json','data/P7_KNOWN_GAUGE_CONTEXT.json','source/KAZ_COUNTRY_BOUNDARY.geojson','KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson','data/KAZ_PARTIAL_RIVER_DISPLAY.geojson']
 pins={str(ROOT/p):sha(ROOT/p) for p in inputs};sid='kaz-n1-'+hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest()[:24]
 bundle={'dataset_id':'KAZAKHSTAN_PUBLIC_NETWORK','source_snapshot_id':sid,'model_release_id':None,'counts':readj(ROOT/'KAZ_N1_COUNTS.json'),'official':readj(ROOT/'KAZ_N1_OFFICIAL_BASELINE.json'),'baseline_density':[numeric(r) for r in rs(ROOT/'KAZ_N1_BASELINE_DENSITY.csv')],'readiness':rs(ROOT/'KAZ_N1_DATA_READINESS.csv'),'GIS':readj(ROOT/'KAZ_N1_GIS_EXECUTION.json'),'basins':rs(ROOT/'KAZ_N1_GEOMETRY_ASSIGNMENT_BY_BASIN.csv'),'density':[numeric(r) for r in rs(ROOT/'KAZ_N1_NATIONAL_DENSITY_SCENARIOS.csv')],'four_answers':readj(ROOT/'data/SUPERVISOR_FOUR_ANSWERS.json'),'European_PUB_benchmark':{'dataset_id':'LAMAH_CE_PUBLIC_V1','classification':'EUROPEAN_PUB_DEVELOPMENT','summary':[numeric(r) for r in rs(ROOT/'pub/EU_PUB_SUMMARY.csv')],'metrics':[dict(numeric(r),station_uid='LAMAH_CE_PUBLIC_V1:'+r['gauge_id']) for r in rs(ROOT/'KAZ_N1_UG_VALIDATION_METRICS.csv')],'not_Kazakhstan_accuracy':True},'P7_known_gauge_context':readj(ROOT/'data/P7_KNOWN_GAUGE_CONTEXT.json'),'source_pins':pins,'public_display':'LOCAL_CANDIDATE_ONLY','production_display_permission':'NOT_GRANTED','execution_permission':'NOT_AUTHORIZED','Kazakhstan_NSE':None,'Kazakhstan_KGE':None,'teacher_Q_used':False}
 put(ROOT/'data/NATIONAL_WEB_BUNDLE.json',bundle)
 fwd=Transformer.from_crs(4326,'+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs',always_xy=True).transform
 boundary=gpd.read_file(ROOT/'source/KAZ_COUNTRY_BOUNDARY.geojson').geometry.iloc[0];boundary=transform(fwd,boundary).simplify(350)
 geo=readj(ROOT/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson');pts=[]
 for r in geo['features']:
  lon,lat=r['geometry']['coordinates'];x,y=fwd(lon,lat);pts.append({'station_id':r['properties']['station_id'],'x':x,'y':y,'reach_id':r['properties']['reach_id'],'status':'CANDIDATE_GEOMETRY','admitted':False,'qsim':None,'NSE':None,'KGE':None})
 rr=readj(ROOT/'data/KAZ_PARTIAL_RIVER_DISPLAY.geojson');rivers=[mapping(transform(fwd,shape(r['geometry'])).simplify(500)) for r in rr['features']]
 mapdata={'source_snapshot_id':sid,'crs':'LAEA48N68E_WGS84_METRES','boundary':mapping(boundary),'bounds':list(boundary.bounds),'rivers_partial':rivers,'layers':{'PHYSICAL_GAUGE':{'features':[],'official_count':394,'mapped_count':0,'status':'CURRENT_OFFICIAL_COORDINATES_NOT_AVAILABLE'},'CANDIDATE_GEOMETRY':{'features':pts,'preliminary_count':len(pts),'admitted_count':0,'status':'PARTIAL_PRELIMINARY_NOT_ADMITTED'},'VIRTUAL_PREDICTION_AVAILABLE':{'features':[],'count':0,'status':'NO_KAZ_PREDICTIONS_AVAILABLE'}}}
 put(ROOT/'data/KAZ_NATIONAL_MAP.json',mapdata);put(ROOT/'WEB_KAZ_SOURCE_PINS.json',{str(ROOT/'data/NATIONAL_WEB_BUNDLE.json'):sha(ROOT/'data/NATIONAL_WEB_BUNDLE.json'),str(ROOT/'data/KAZ_NATIONAL_MAP.json'):sha(ROOT/'data/KAZ_NATIONAL_MAP.json'),**pins})
 print('new host copied; KAZ snapshot',sid,'preliminary geometry',len(pts),flush=True)
if __name__=='__main__':main()
