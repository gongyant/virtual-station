from common import *
import geopandas as gpd,pyogrio,numpy as np,pandas as pd,shapely
from shapely.geometry import MultiLineString,LineString
from pyproj import Geod
GEOD=Geod(ellps='WGS84')
LAEA='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
def linear(g):
 if g.is_empty:return MultiLineString([])
 if g.geom_type=='LineString':return MultiLineString([g])
 if g.geom_type=='MultiLineString':return g
 return MultiLineString([p for p in shapely.get_parts(g) if p.geom_type=='LineString' and not p.is_empty])
def length(g):return abs(GEOD.geometry_length(g))/1000 if not g.is_empty else 0.
def groups(d,col):
 vals=pd.to_numeric(d[col],errors='coerce');return np.select([vals==1,vals==2,vals==3,vals>=4],['1','2','3','4_PLUS'],default='UNCLASSIFIED')
def stats(d,scope,name,order):
 rows=[];gr=groups(d,order)
 for k in ['1','2','3','4_PLUS','UNCLASSIFIED','ALL']:
  x=d if k=='ALL' else d.loc[gr==k]
  rows.append({'scope':scope,'basin_id':name[0],'basin_name':name[1],'order_system':order,'order_group':k,'source_unique_reaches':int(x.HYRIV_ID.nunique()),'fragment_count':len(x),'river_length_km':float(x.length_km.sum()),'length_definition':'WGS84_GEODESIC_CLIPPED_GEOMETRY','network_threshold':'upstream area>=10km2 OR modeled meanQ>=0.1m3/s','official_administrative_order':False})
 return rows
def summary(rows):
 out=[]
 for scope,bid,name in sorted({(r['scope'],str(r['basin_id']),r['basin_name']) for r in rows}):
  rs=[r for r in rows if r['scope']==scope and str(r['basin_id'])==bid and r['order_system']=='ORD_CLAS'];v={r['order_group']:r['river_length_km'] for r in rs}
  out.append({'scope':scope,'basin_id':bid,'basin_name':name,'class1_km':v['1'],'class2_km':v['2'],'class3_km':v['3'],'class4plus_km':v['4_PLUS'],'unclassified_km':v['UNCLASSIFIED'],'all_orders_km':v['ALL'],'class1_3_km':v['1']+v['2']+v['3']})
 return out
def main():
 assert not (ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg').exists(),'EXISTING_RESULT_NO_OVERWRITE'
 event('river_statistics','STARTED');p=read(ROOT/'P8_FROZEN_PROTOCOL.json');assert sha(ROOT/'P8_FROZEN_PROTOCOL.json')==read(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']
 shp=next((ROOT/'source/hydrorivers_global').rglob('HydroRIVERS_v10.shp'));info=pyogrio.read_info(shp);assert info['features']==8477883 and info['crs']=='EPSG:4326'
 print('global identity and order attribute scan',flush=True)
 cache=ROOT/'evidence/GLOBAL_RIVER_SOURCE_CHECK.json'
 if cache.exists():
  srcmeta=read(cache);assert sha(shp)==srcmeta['source_hashes'][str(shp)];print('reuse independently checked global attribute inventory',flush=True)
 else:
  raw=pyogrio.read_dataframe(shp,columns=['HYRIV_ID','ORD_CLAS','ORD_STRA','ORD_FLOW','ENDORHEIC'],read_geometry=False)
  srcmeta={'path':str(shp),'features':len(raw),'unique_HYRIV_ID':int(raw.HYRIV_ID.nunique()),'duplicate_HYRIV_ID':int(raw.HYRIV_ID.duplicated().sum()),'CRS':str(info['crs']),'global_attribute_missing_rate':{c:float(raw[c].isna().mean()) for c in raw},'global_order_ranges':{c:[int(raw[c].min()),int(raw[c].max())] for c in ['ORD_CLAS','ORD_STRA','ORD_FLOW']}}
  assert srcmeta['duplicate_HYRIV_ID']==0;del raw
 country=gpd.read_file(p['country_boundary']).geometry.union_all();bbox=tuple(country.bounds)
 print('read actual country bounding box',bbox,flush=True);r=pyogrio.read_dataframe(shp,bbox=bbox)
 print('bbox reaches',len(r),flush=True);c=shapely.intersection(r.geometry.array,country);ls=[linear(x) for x in c];keep=np.array([not x.is_empty for x in ls]);national=r.loc[keep].copy();national.geometry=[g for g,k in zip(ls,keep) if k];national.rename(columns={'LENGTH_KM':'SOURCE_REACH_LENGTH_KM'},inplace=True);national['length_km']=[length(g) for g in national.geometry];national=national[national.length_km>0].copy();national.reset_index(drop=True,inplace=True)
 srcmeta.update(bbox_features=len(r),national_source_reaches=len(national),regional_ID_prefix_counts={str(int(k)):int(v) for k,v in (national.HYRIV_ID//10000000).value_counts().items()},national_attribute_missing_rate={c:float(national['SOURCE_REACH_LENGTH_KM' if c=='LENGTH_KM' else c].isna().mean()) for c in r.columns if c!='geometry'},zero_length_or_point_intersections_removed=int(len(r)-len(national)),source_hashes={str(x):sha(x) for x in shp.parent.iterdir() if x.is_file()})
 put(ROOT/'evidence/GLOBAL_RIVER_SOURCE_CHECK.json',srcmeta);print('country clipped',len(national),'length',national.length_km.sum(),flush=True)
 b=gpd.read_file(p['basins']).sort_values('id');assert len(b)==8 and b.crs.to_epsg()==4326 and b.is_valid.all()
 b['basin_id']=b['id'].astype(int);b['basin_name']=b['name'];b['six_subset']=b['name'].isin(p['six_scope']);bp=b.to_crs(LAEA);cp=gpd.GeoSeries([country],crs=4326).to_crs(LAEA).iloc[0];bu=bp.geometry.union_all()
 aq={'source_basin_count':len(b),'source_geometries_valid':bool(b.is_valid.all()),'source_area_attribute_sum_km2':float(b.area_km2.sum()),'basin_equal_area_sum_km2':float(bp.area.sum()/1e6),'basin_union_area_km2':bu.area/1e6,'basin_overlap_area_km2':(bp.area.sum()-bu.area)/1e6,'country_generalized_area_km2':cp.area/1e6,'country_uncovered_area_km2':cp.difference(bu).area/1e6,'basin_outside_country_area_km2':bu.difference(cp).area/1e6,'country_covered_fraction':cp.intersection(bu).area/cp.area,'fixed_official_area_for_density':2724900,'national_boundary_is_generalized':True}
 remaining=np.array(national.geometry.array,dtype=object);pieces=[];raw_overlap=[];cross=[];records=national.drop(columns='geometry').to_dict('records')
 for _,row in b.iterrows():
  poly=row.geometry.intersection(country);ix=np.flatnonzero(shapely.intersects(remaining,poly));taken=shapely.intersection(remaining[ix],poly)
  # Sequential line subtraction assigns any shared positive-length boundary exactly once.
  rawix=np.flatnonzero(shapely.intersects(national.geometry.array,poly));rawinter=shapely.intersection(national.geometry.array[rawix],poly);rawlen=sum(length(linear(g)) for g in rawinter)
  rows=[]
  for i,g in zip(ix,taken):
   g=linear(g)
   for seq,part in enumerate(g.geoms):
    l=length(part)
    if l<=0:continue
    rec=dict(records[i]);rec.update(basin_id=int(row.id),basin_name=row['name'],six_subset=bool(row['six_subset']),fragment_id=f'{int(rec["HYRIV_ID"])}|B{int(row.id)}|{seq}',length_km=l,geometry=part);rows.append(rec)
  pieces.extend(rows);remaining[ix]=shapely.difference(remaining[ix],poly)
  allocated=sum(x['length_km'] for x in rows);raw_overlap.append({'basin_id':int(row.id),'raw_intersection_length_km':rawlen,'allocated_once_length_km':allocated,'shared_boundary_or_overlap_removed_km':rawlen-allocated})
  cross.append({'official_eight_basin_id':int(row.id),'name':row['name'],'aliases':{'Ertis':'Irtysh|Ertys','Yesil':'Ishim|Esil','Tobyl-Torgai':'Tobol-Turgay','Zhaiyk-Caspian':'Ural-Caspian','Balkhash-Alakol':'Ili-Balkhash-Alakol','Aral-Syr Darya':'Syrdarya-Aral','Shu-Talas':'Chu-Talas','Nura-Sarysu':'Nura-Sarysuu'}[row['name']],'six_basin_candidate_subset':bool(row['six_subset']),'boundary_source_DOI':'10.5281/zenodo.17077776 v2','source_CRS':str(b.crs),'geometry_valid':True,'within_country_area_km2':float(poly and gpd.GeoSeries([poly],crs=4326).to_crs(LAEA).area.iloc[0]/1e6),'review':'RESEARCH_BOUNDARY_VALID_WITH_BORDER_RESIDUAL_NOT_LEGAL_SURVEY','overlap_or_gaps':'see BASIN_AREA_QA and UNASSIGNED'});print('basin',row['name'],'km',allocated,'pieces',len(rows),flush=True)
 for i,g in enumerate(remaining):
  for seq,part in enumerate(linear(g).geoms):
   l=length(part)
   if l<=0:continue
   rec=dict(records[i]);rec.update(basin_id=0,basin_name='UNASSIGNED_BORDER_OR_BOUNDARY_GAP',six_subset=False,fragment_id=f'{int(rec["HYRIV_ID"])}|B0|{seq}',length_km=l,geometry=part);pieces.append(rec)
 f=gpd.GeoDataFrame(pieces,crs=4326);assert not f.fragment_id.duplicated().any();f['ORD_CLAS_GROUP']=groups(f,'ORD_CLAS');f['ORD_STRA_GROUP']=groups(f,'ORD_STRA')
 path=ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg';national.to_file(path,layer='national_reaches',driver='GPKG',engine='pyogrio');f.to_file(path,layer='basin_fragments',driver='GPKG',engine='pyogrio');b.to_file(path,layer='basins_source',driver='GPKG',engine='pyogrio');gpd.GeoDataFrame([{'source':'NaturalEarth1:10m v5.1.1','geometry':country}],crs=4326).to_file(path,layer='country_boundary',driver='GPKG',engine='pyogrio')
 rs=[]
 for bid,name in sorted(set(zip(f.basin_id,f.basin_name))):
  d=f[f.basin_id==bid]
  for order in ['ORD_CLAS','ORD_STRA']:rs+=stats(d,'EIGHT_BASIN' if bid else 'UNASSIGNED',(int(bid),name),order)
 for scope,d,name in [('NATIONAL',national,('NATIONAL','Kazakhstan country clip')),('EIGHT_ASSIGNED_TOTAL',f[f.basin_id>0],('EIGHT_TOTAL','Eight assigned basins only')),('SIX_SUBSET_TOTAL',f[f.six_subset],('SIX_TOTAL','2025-10-03 platform six subset'))]:
  for order in ['ORD_CLAS','ORD_STRA']:rs+=stats(d,scope,name,order)
 csvout(ROOT/'P8_RIVER_LENGTH_BY_BASIN_ORDER.csv',rs);csvout(ROOT/'P8_CLASSICAL_VS_STRAHLER.csv',rs);csvout(ROOT/'BASIN_SCOPE_CROSSWALK.csv',cross);csvout(ROOT/'P8_EIGHT_BASIN_SUMMARY.csv',summary([x for x in rs if x['scope'] in ['EIGHT_BASIN','EIGHT_ASSIGNED_TOTAL','NATIONAL','UNASSIGNED']]))
 six_ids=set(b.loc[b.six_subset,'basin_id']);csvout(ROOT/'P8_SIX_BASIN_SUMMARY.csv',summary([x for x in rs if x['scope']=='SIX_SUBSET_TOTAL' or x['scope']=='EIGHT_BASIN' and x['basin_id'] in six_ids]));csvout(ROOT/'evidence/BASIN_LINE_ALLOCATION.csv',raw_overlap)
 aq.update(national_length_km=float(national.length_km.sum()),assigned_eight_length_km=float(f.loc[f.basin_id>0,'length_km'].sum()),unassigned_length_km=float(f.loc[f.basin_id==0,'length_km'].sum()),partition_length_difference_km=float(f.length_km.sum()-national.length_km.sum()),source_reaches_crossing_multiple_basins=int((f[f.basin_id>0].groupby('HYRIV_ID').basin_id.nunique()>1).sum()),national_fragments=len(f))
 put(ROOT/'evidence/BASIN_AREA_QA.json',aq)
 # Boundary sensitivity uses the same full global bbox and no alternative score selection.
 put(ROOT/'evidence/BOUNDARY_LENGTH_SENSITIVITY.json',{'status':'SEPARATE_ENTRY_SCOPE_AND_BOUNDARY_PY','primary_country_clip_km':float(national.length_km.sum()),'note':'optional whole-union overlay was interrupted after primary outputs persisted; separate full-basin-bbox sequential algorithm avoids expensive monolithic overlay and bbox omission'})
 csvout(ROOT/'P8_NETWORK_EXCEPTIONS.csv',[{'category':'ENDORHEIC','source_value':int(k),'reach_count':int(len(d)),'length_km':float(d.length_km.sum()),'status':'source flag, not proof of perennial flow'} for k,d in national.groupby('ENDORHEIC')]+[{'category':'SEASONALITY','source_value':'NOT_AVAILABLE','reach_count':None,'length_km':None,'status':'no observed seasonality/perennial flag; no inference from modeled discharge'}, {'category':'UNCLASSIFIED_ORD_CLAS','source_value':'invalid or missing','reach_count':int(sum(groups(national,'ORD_CLAS')=='UNCLASSIFIED')),'length_km':float(national.loc[groups(national,'ORD_CLAS')=='UNCLASSIFIED','length_km'].sum()),'status':'kept in national total'}])
 event('river_statistics','FINISHED',national_reaches=len(national),national_length_km=float(national.length_km.sum()),fragments=len(f),unassigned_km=aq['unassigned_length_km']);print(json.dumps(aq),flush=True)
if __name__=='__main__':main()
