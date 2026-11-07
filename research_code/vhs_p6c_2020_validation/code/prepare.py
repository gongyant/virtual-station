import sys,json,csv,hashlib,struct,ast,time,collections,shutil
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon
from shapely.strtree import STRtree
from pyproj import Transformer
sys.stdout.reconfigure(encoding='utf-8');L=Path(r'E:\VHS_Public_Baseline_Lab');B=L/'vhs_p6b_external_validation';R=L/'vhs_p6c_2020_validation';P4=L/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def cw(p,rr):
 with Path(p).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
assert not R.exists(),'EXISTING_P6C_DIRECTORY_INSPECT_FIRST'
for d in ['code','evidence','driver','external','runs']:(R/d).mkdir(parents=True,exist_ok=True)
history={}
for folder in [L,*[L/x for x in ['p1_seasonal_meteorology_ablation','p2_antecedent_snow_features','p3_forward_temporal_validation','p4_final_reconstruction','p5_robustness_and_external_validation','vhs_web_r1_public_results_bridge','vhs_web_r2_host_integration','vhs_r2u1_p6a','vhs_p6b_external_validation']]]:
 lines=(folder/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines();entries={}
 for line in lines:
  h,n=line.split('  ',1);assert sha(folder/n)==h,(str(folder),n);entries[n]=h
 history[str(folder)]={'manifest_hash':sha(folder/'SHA256SUMS.txt'),'files':entries}
jw(R/'evidence/HISTORY_BEFORE.json',history)
cross=list(csv.DictReader((B/'P6B_STATION_CROSSWALK_FINAL.csv').open(encoding='utf-8-sig')));stations=[r for r in cross if r['country']=='AUT'];assert len(stations)==24
src=(B/'code/geometry_cds.py').read_text(encoding='utf-8');defs=[n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name in ['dbf','shapes']];space={'struct':struct,'np':np,'Polygon':Polygon};exec(compile(ast.Module(body=defs,type_ignores=[]),'P6B_geometry_readers','exec'),space);dbf=space['dbf'];shapes=space['shapes']
attrs=dbf(B/'driver/Basins_A.dbf');grid=dbf(B/'driver/Grid_ERA5L.dbf');basins=shapes(B/'driver/Basins_A.shp');cells=shapes(B/'driver/Grid_ERA5L.shp');tree=STRtree(cells);transform=Transformer.from_crs(3035,4326,always_xy=True);weights={};allcells={};rows=[]
for s in stations:
 g=int(s['gauge_id']);idx=next(i for i,a in enumerate(attrs) if int(a['ID'])==g);basin=basins[idx];ww=[]
 for i in tree.query(basin,predicate='intersects'):
  ar=basin.intersection(cells[i]).area
  if ar<=0:continue
  ia=int(ar)
  if ia<=0:continue
  lon,lat=transform.transform(cells[i].centroid.x,cells[i].centroid.y);gid=grid[i]['ID'];record={'grid_id':gid,'lon':round(lon,1),'lat':round(lat,1),'intersection_area_m2':ar,'integer_area_m2':ia};ww.append(record);allcells[gid]={'grid_id':gid,'lon':round(lon,1),'lat':round(lat,1)}
 ww.sort(key=lambda x:int(x['grid_id']));total=sum(w['integer_area_m2'] for w in ww)
 for w in ww:w['weight']=w['integer_area_m2']/total
 assert abs(sum(w['weight'] for w in ww)-1)<1e-12;weights[str(g)]={'gauge_id':g,'basin_area_m2':basin.area,'integer_intersection_sum':total,'weights':ww};rows.append({'gauge_id':g,'official_id':s['official_id'],'country':'AUT','region':s['region'],'basin_A_area_km2':basin.area/1e6,'n_intersecting_cells':len(ww),'Q_source':str(B/'external'/f'EHYD_{s["official_id"]}_file5.txt'),'metadata_source':str(B/'external'/f'EHYD_{s["official_id"]}_file1.txt'),'coordinate_difference_m':s['coordinate_difference_m'],'Q_unit':'m3/s','P_unit':'mm/month','T_unit':'degC','UTC_day_status':'PROVIDER_DAY_NOT_YET_CERTIFIED','prior_2020_Q_parser_exposure':True})
cw(R/'P6C_STATION_CROSSWALK_INITIAL.csv',rows);jw(R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json',weights);jw(R/'driver/UNIQUE_REQUIRED_GRID_CELLS.json',list(allcells.values()))
# Fixed compact download tiling, two-degree lon x one-degree lat, only tiles with required grid cells.
tiles=collections.defaultdict(list)
for c in allcells.values():tiles[(int(np.floor(c['lon']/2))*2,int(np.floor(c['lat'])))].append(c)
download=[]
for i,(key,cc) in enumerate(sorted(tiles.items())):
 lo=min(c['lon'] for c in cc);hi=max(c['lon'] for c in cc);so=min(c['lat'] for c in cc);no=max(c['lat'] for c in cc);expected=(round((hi-lo)*10)+1)*(round((no-so)*10)+1);download.append({'tile_id':f'T{i:02d}','required_cells':cc,'area':[no+.001,lo-.001,so-.001,hi+.001],'expected_rectangle_cells':expected,'need_cells':len(cc)})
jw(R/'driver/DOWNLOAD_TILES_FROZEN.json',download)
print('COUNTS',[(r['gauge_id'],r['n_intersecting_cells'],round(r['basin_A_area_km2'],1)) for r in rows]);print('UNIQUE_CELLS',len(allcells),'TILES',[(x['tile_id'],x['need_cells'],x['expected_rectangle_cells']) for x in download],'TOTAL_RECTANGLE',sum(x['expected_rectangle_cells'] for x in download));print('HISTORY_FILES',sum(len(v['files']) for v in history.values()))
