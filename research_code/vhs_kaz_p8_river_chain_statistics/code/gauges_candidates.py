from common import *
import geopandas as gpd,numpy as np,pandas as pd,shapely,re
from shapely.geometry import shape,Point
from scipy.spatial import cKDTree
LAEA='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
def typ(n):
 n=n.lower().strip()
 if re.search(r'канал|кан\.',n):return 'CANAL_OR_CHANNEL_MENTION_REVIEW'
 if re.search(r'море',n):return 'MARINE'
 if re.search(r'оз\.|озеро|водохранилищ|вдхр',n):return 'LAKE_OR_RESERVOIR'
 if re.match(r'р[.\s]|река\s|руч[.\s]',n):return 'RIVER_OR_STREAM_FROM_NAME'
 return 'TYPE_UNKNOWN'
def main():
 assert not (ROOT/'P8_OFFICIAL_GAUGE_CROSSWALK.csv').exists(),'EXISTING_CROSSWALK_NO_OVERWRITE'
 event('gauge_matching_and_candidate_recheck','STARTED');p=read(ROOT/'P8_FROZEN_PROTOCOL.json');gpk=ROOT/'P8_NATIONAL_RIVER_REACHES.gpkg'
 nat=gpd.read_file(gpk,layer='national_reaches');frag=gpd.read_file(gpk,layer='basin_fragments');b=gpd.read_file(gpk,layer='basins_source');country=gpd.read_file(gpk,layer='country_boundary').geometry.iloc[0]
 fp=frag.to_crs(LAEA);np_=nat.to_crs(LAEA);tree=shapely.STRtree(fp.geometry.array)
 j=read(ROOT/'source/qazsu_hydroposts_response.json');assert len(j['features'])==j['numberReturned']==j['numberMatched']==334
 pts=gpd.GeoDataFrame([{'code':f['properties']['code'],'geometry':shape(f['geometry'])} for f in j['features']],crs=4326);ptsproj=pts.to_crs(LAEA);dup=pts.code.duplicated(keep=False);dupxy=pts.geometry.to_wkb().duplicated(keep=False)
 out=[]
 for i,f in enumerate(j['features']):
  a=f['properties'];pt=pts.geometry.iloc[i];pp=ptsproj.geometry.iloc[i];xy=pt.coords[0];cat=typ(a['name']);idx=int(tree.nearest(pp));d=float(pp.distance(fp.geometry.iloc[idx]));r=frag.iloc[idx]
  possible=tree.query(pp.buffer(d+10));near=[(int(k),float(pp.distance(fp.geometry.iloc[k]))) for k in possible];amb=[k for k,dd in near if dd<=d+10 and (int(frag.iloc[k].ORD_CLAS)!=int(r.ORD_CLAS) or int(frag.iloc[k].basin_id)!=int(r.basin_id))]
  inside=bool(country.covers(pt));valid=pt.geom_type=='Point' and 40<=xy[0]<=90 and 35<=xy[1]<=60
  eligible=valid and inside and not dup.iloc[i] and cat=='RIVER_OR_STREAM_FROM_NAME' and d<=p['gauge_snap_primary_m'] and not amb and int(r.basin_id)>0
  flags=[]
  if not inside:flags.append('OUTSIDE_GENERALIZED_COUNTRY')
  if dup.iloc[i]:flags.append('DUPLICATE_STATION_CODE')
  if dupxy.iloc[i]:flags.append('DUPLICATE_COORDINATES_REVIEW')
  if cat!='RIVER_OR_STREAM_FROM_NAME':flags.append(cat)
  if d>500:flags.append('SNAP_DISTANCE_GT500M')
  if amb:flags.append('ORDER_OR_BASIN_AMBIGUITY_WITHIN10M')
  if int(r.basin_id)==0:flags.append('BASIN_UNASSIGNED')
  flags+=['HYDRORIVERS_HAS_NO_RIVER_NAME_CROSSCHECK','CURRENT394_MEMBERSHIP_UNVERIFIED','COMMISSION_RETIREMENT_DATES_NOT_PROVIDED','BULK_REUSE_LICENSE_NOT_EXPLICIT']
  out.append({'institution_catalog':'QazSu public hydropost map; operator identity not asserted per station','source_snapshot_sha256':sha(ROOT/'source/qazsu_hydroposts_response.json'),'station_code':a['code'],'source_object_id':a['id'],'source_feature_id':f['id'],'station_name':a['name'],'river_name_parsed':re.split(r'\s+[–-]\s+',a['name'],maxsplit=1)[0],'station_type_inferred':cat,'longitude':xy[0],'latitude':xy[1],'source_CRS':'EPSG:4326 GeoJSON longitude-latitude','attribute_x_is_lat_y_is_lon':bool(abs(float(a['x'])-xy[1])<0.001 and abs(float(a['y'])-xy[0])<0.001),'source_basin_id':a['bassein_id'],'source_basin_name':a['bassein'],'coordinate_basin_ids':'|'.join(str(int(z.id)) for _,z in b.iterrows() if z.geometry.covers(pt)),'source_upstream_area_km2':a['fkm2'],'commission_date':None,'retirement_date':None,'last_public_observation_date':a['date'],'nearest_HYRIV_ID':int(r.HYRIV_ID),'nearest_ORD_CLAS':int(r.ORD_CLAS),'nearest_ORD_STRA':int(r.ORD_STRA),'nearest_basin_id':int(r.basin_id),'nearest_basin_name':r.basin_name,'nearest_distance_m_LAEA':d,'primary_500m_geometric_match':eligible,'sensitivity_1000m_geometry_only':valid and inside and cat=='RIVER_OR_STREAM_FROM_NAME' and d<=1000,'sensitivity_5000m_geometry_only':valid and inside and cat=='RIVER_OR_STREAM_FROM_NAME' and d<=5000,'match_status':'MATCHED_GEOMETRY_PROVISIONAL' if eligible else 'NOT_ADMITTED_TO_GEOMETRIC_SUBSET','official394_identity_confirmed':False,'reason_codes':'|'.join(flags)})
 csvout(ROOT/'P8_OFFICIAL_GAUGE_CROSSWALK.csv',out);gg=pd.DataFrame(out);primary=gg[gg.primary_500m_geometric_match]
 lens=pd.read_csv(ROOT/'P8_RIVER_LENGTH_BY_BASIN_ORDER.csv');dens=[]
 for _,r in lens[lens.order_system=='ORD_CLAS'].iterrows():
  scope=r.scope;bid=str(r.basin_id)
  if scope=='EIGHT_BASIN':subset=primary[primary.nearest_basin_id.astype(str)==bid]
  elif scope=='UNASSIGNED':subset=primary[primary.nearest_basin_id==0]
  elif scope=='SIX_SUBSET_TOTAL':subset=primary[primary.nearest_basin_name.isin(p['six_scope'])]
  elif scope=='EIGHT_ASSIGNED_TOTAL':subset=primary[primary.nearest_basin_id>0]
  else:subset=primary
  k=str(r.order_group)
  if k in ['1','2','3']:subset=subset[subset.nearest_ORD_CLAS==int(k)]
  elif k=='4_PLUS':subset=subset[subset.nearest_ORD_CLAS>=4]
  elif k=='UNCLASSIFIED':subset=subset[~subset.nearest_ORD_CLAS.between(1,100)]
  count=len(subset);l=float(r.river_length_km)
  dens.append({'scope':scope,'basin_id':r.basin_id,'basin_name':r.basin_name,'ORD_CLAS_group':k,'river_length_km':l,'matched_QazSu_geometric_subset_count':count,'matched_subset_density_per_km':count/l if l else None,'matched_subset_density_per_1000km':1000*count/l if l else None,'admitted_virtual_gauges':0,'combined_subset_density_per_1000km':1000*count/l if l else None,'complete_official394_matched_count':None,'complete_official_density_per_km':None,'complete_official_density_per_1000km':None,'density_status':'PROVISIONAL_CATALOG_SUBSET_NOT_RECONCILED394','unallocated_official394_ratio_per_1000km':394*1000/l if scope=='NATIONAL' and k=='ALL' else None})
 csvout(ROOT/'P8_REAL_GAUGE_DENSITY.csv',dens)
 n1=pathlib.Path(read(ROOT/'evidence/DISCOVERY.json')['KAZ_N1']);old=read(n1/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson');c=gpd.GeoDataFrame.from_features(old['features'],crs=4326);cp=c.to_crs(LAEA);cptree=cKDTree(np.array([[g.x,g.y] for g in cp.geometry]));closepairs=cptree.query_pairs(1);dupc={i for pair in closepairs for i in pair};phys=ptsproj.loc[gg.station_type_inferred=='RIVER_OR_STREAM_FROM_NAME'];phys_tree=cKDTree(np.array([[x.x,x.y] for x in phys.geometry]));rr=[]
 for i,row in c.iterrows():
  pt=row.geometry;pr=cp.geometry.iloc[i];ix=int(tree.nearest(pr));fr=frag.iloc[ix];dist=float(pr.distance(fp.geometry.iloc[ix]));bid=[int(q.id) for _,q in b.iterrows() if q.geometry.covers(pt)];gdist,gi=phys_tree.query([pr.x,pr.y]);flags=['FULL_CURRENT394_GAUGE_EXCLUSION_UNVERIFIED','POINT_UPSTREAM_CATCHMENT_NOT_DELINEATED','HOMOGENEOUS_P_T_DRIVERS_NOT_AVAILABLE']
  if gdist<5000:flags.append('CONFLICT_WITH_AVAILABLE_QAZSU_RIVER_COORDINATE_WITHIN5KM')
  if i in dupc:flags.append('DUPLICATE_POINT_WITHIN1M')
  if not country.covers(pt):flags.append('OUTSIDE_COUNTRY')
  if dist>5:flags.append('SOURCE_REACH_ALIGNMENT_GT5M')
  if len(bid)!=1:flags.append('MANAGEMENT_BASIN_AMBIGUOUS_OR_MISSING')
  on_old=int(row.reach_id)==int(fr.HYRIV_ID) or any(int(frag.iloc[k].HYRIV_ID)==int(row.reach_id) and pr.distance(fp.geometry.iloc[k])<=5 for k in tree.query(pr.buffer(5)))
  rr.append({'station_id':row.station_id,'longitude':pt.x,'latitude':pt.y,'historical_reach_id':int(row.reach_id),'source_global_reach_match':on_old,'nearest_reach_id':int(fr.HYRIV_ID),'nearest_distance_m':dist,'inside_country':bool(country.covers(pt)),'management_basin_ids':'|'.join(map(str,bid)),'ORD_CLAS':int(fr.ORD_CLAS),'ORD_STRA':int(fr.ORD_STRA),'nearest_available_river_gauge_distance_m':float(gdist),'source_upstream_area_outlet_proxy_km2':row.get('upstream_area_at_reach_outlet_km2',None),'source_upstream_area_lower_bound_km2':row.get('upstream_area_lower_bound_km2',None),'exact_point_upstream_area_verified':False,'meteorology_verified':False,'geometry_state':'GEOMETRY_SCREENED','admitted_virtual_gauge':False,'validation_status':'VALIDATION_NOT_AVAILABLE','reason_codes':'|'.join(flags),'historical_pool_sha256':sha(n1/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson')})
 csvout(ROOT/'P8_KAZ_N1_CANDIDATE_RECHECK.csv',rr)
 stat={'official_current_river_count':394,'QazSu_public_catalog_records':len(gg),'QazSu_valid_coordinate_records':int(sum(pts.geometry.notna())),'QazSu_duplicate_codes':int(dup.sum()),'QazSu_duplicate_coordinates':int(dupxy.sum()),'type_counts':gg.station_type_inferred.value_counts().to_dict(),'geometric_500m_provisional_matches':len(primary),'official394_membership_reconciled':False,'official394_unmatched_identity_count':None,'geometry_subset_not_qualifies_as_394_complete_density':True,'candidate_recheck_records':len(rr),'candidate_basin_assigned_once':sum(bool(x['management_basin_ids']) and '|' not in x['management_basin_ids'] for x in rr),'candidate_available_gauge_conflicts5km':sum(x['nearest_available_river_gauge_distance_m']<5000 for x in rr),'candidate_admitted':0,'source_raw_Q_not_exported_in_crosswalk':True}
 put(ROOT/'evidence/GAUGE_AND_CANDIDATE_STATUS.json',stat);event('gauge_matching_and_candidate_recheck','FINISHED',**stat);print(json.dumps(stat,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
