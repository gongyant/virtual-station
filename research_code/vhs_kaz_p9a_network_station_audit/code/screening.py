from common import *
import geopandas as gpd,numpy as np,pyogrio
from pyproj import CRS
p=read(ROOT/'P9A_FROZEN_PROTOCOL.json')['pilot_selection']
c=pd.read_csv(P8/'P8_KAZ_N1_CANDIDATE_RECHECK.csv')
chain=pd.read_csv(ROOT/'data/CANDIDATE_CHAIN_METRICS.csv')
conn=pd.read_csv(ROOT/'data/CANDIDATE_GAUGE_CONNECTIVITY.csv',keep_default_na=False)
d=c.merge(chain.drop(columns=['longitude','latitude','ORD_CLAS','ORD_STRA']),on='station_id',validate='one_to_one').merge(conn,on='station_id',validate='one_to_one')
d['basin_id']=pd.to_numeric(d.management_basin_ids,errors='coerce').fillna(0).astype(int)
b=pyogrio.read_dataframe(GPKG,layer='basins_source',read_geometry=False)
names=dict(zip(b.basin_id,b.basin_name));d['basin_name']=d.basin_id.map(names).fillna('UNASSIGNED')
d['real_gauge_conflict']=d.nearest_available_river_gauge_distance_m<p['minimum_available_gauge_distance_m']
d['geometry_qualified']=d.inside_country & d.source_global_reach_match & (d.basin_id>0) & d.ORD_CLAS.isin(p['river_orders']) & (d.source_upstream_area_lower_bound_km2>=p['minimum_upstream_area_lower_bound_km2']) & (~d.real_gauge_conflict) & d.has_directed_gauge_connection & d.topology_complete_within_source_product & d.all_upstream_connected_length_km.notna() & d.source_to_station_mainstem_km.notna()
d['features_status']='NOT_AVAILABLE_POINT_CATCHMENT_AND_HOMOGENEOUS_MET_UNVERIFIED'
d['prediction_status']='VIRTUAL_PREDICTION_NOT_AVAILABLE'
d['research_admission']='NOT_ADMITTED'
d['validation_status']='VALIDATION_NOT_AVAILABLE'
d['candidate_status']=np.where(d.geometry_qualified,'TOPOLOGY_AND_GEOMETRY_SCREENED','CANDIDATE_GEOMETRY_WITH_BLOCKERS')
d['pilot_selected']=False;d['pilot_rank']=pd.Series([pd.NA]*len(d),dtype='Int64')
g=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv');g=g[g.primary_500m_geometric_match]
basinrows=[]
for r in b.itertuples():
    q=d[d.basin_id==r.basin_id];s=g[g.nearest_basin_id==r.basin_id]
    basinrows.append(dict(basin_id=r.basin_id,basin_name=r.basin_name,provisional_geometric_gauges=len(s),official_identity_certified=0,continuous_Q_series_acquired=0,continuous_Q_period='N/A_NOT_ACQUIRED',daily_QC='NOT_PROVIDED',Q_reuse_license='NOT_ESTABLISHED',homogeneous_P_T_basins=0,driver_state='NOT_ACQUIRED_AND_NOT_BOUND_TO_POINT_CATCHMENTS',historical_candidates=len(q),topology_geometry_qualified=int(q.geometry_qualified.sum()),boundary_state='RESEARCH_POLYGONS_WITH_P8_UNASSIGNED_RESIDUAL',attributes_state='HydroRIVERS reach-outlet upstream area proxy; exact point catchment unverified',future_validation='Label-blind station/network-group holdout plus reserved time block once Q and drivers admitted',model_execution='BLOCKED_Q_AND_DRIVERS',geometry_pilot=False))
rank=pd.DataFrame(basinrows).sort_values(['provisional_geometric_gauges','topology_geometry_qualified','basin_id'],ascending=[False,False,True])
chosen=int(rank.basin_id.iloc[0]);rank.loc[rank.basin_id==chosen,'geometry_pilot']=True
pool=d[(d.basin_id==chosen)&d.geometry_qualified].sort_values(['ORD_CLAS','source_upstream_area_lower_bound_km2','station_id'],ascending=[True,False,True])
laea=CRS.from_proj4('+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs')
pg=gpd.GeoDataFrame(pool.copy(),geometry=gpd.points_from_xy(pool.longitude,pool.latitude),crs=4326).to_crs(laea)
selected=[]
for idx,r in pg.iterrows():
    if all(r.geometry.distance(pg.loc[j].geometry)>=p['minimum_candidate_euclidean_spacing_m'] for j in selected):selected.append(idx)
    if len(selected)>=p['target_count']:break
for j,idx in enumerate(selected,1):d.loc[idx,'pilot_selected']=True;d.loc[idx,'pilot_rank']=j
def reasons(r):
    z=[]
    if r.real_gauge_conflict:z.append('WITHIN_5KM_AVAILABLE_QAZSU_RIVER_COORDINATE')
    if r.basin_id==0:z.append('BASIN_UNASSIGNED')
    if r.ORD_CLAS not in p['river_orders']:z.append('OUTSIDE_PILOT_ORDER_1_TO_7')
    if not r.has_directed_gauge_connection:z.append('NO_VERIFIED_DIRECTED_LINK_TO_PROVISIONAL_GAUGE')
    if not r.topology_complete_within_source_product:z.append('UPSTREAM_SOURCE_GRAPH_INCOMPLETE')
    z.extend(['OFFICIAL_FULL_GAUGE_EXCLUSION_UNVERIFIED','POINT_CATCHMENT_NOT_DELINEATED','HOMOGENEOUS_P_T_NOT_ACQUIRED','Q_TRAINING_AND_VALIDATION_NOT_ACQUIRED'])
    return '|'.join(z)
d['screening_reason_codes']=[reasons(r) for r in d.itertuples()]
csv(ROOT/'P9A_VHS_CANDIDATE_SCREENING.csv',d)
csv(ROOT/'P9A_FIRST_BASIN_PILOT_CANDIDATES.csv',d[d.pilot_selected])
csv(ROOT/'P9A_FIRST_BASIN_COMPARISON.csv',rank.sort_values('basin_id'))
out=ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg'
gpd.GeoDataFrame(d,geometry=gpd.points_from_xy(d.longitude,d.latitude),crs=4326).to_file(out,layer='candidate_screening',driver='GPKG',engine='pyogrio')
pilot=d[d.pilot_selected]
gpd.GeoDataFrame(pilot,geometry=gpd.points_from_xy(pilot.longitude,pilot.latitude),crs=4326).to_file(out,layer='first_basin_pilot',driver='GPKG',engine='pyogrio')
allg=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv')
gpd.GeoDataFrame(allg,geometry=gpd.points_from_xy(allg.longitude,allg.latitude),crs=4326).to_file(out,layer='qazsu_identity_audit',driver='GPKG',engine='pyogrio')
summary=dict(historical_geometry_pool=len(d),directed_gauge_connected=int(d.has_directed_gauge_connection.sum()),available_gauge_conflicts_5km=int(d.real_gauge_conflict.sum()),topology_geometry_qualified=int(d.geometry_qualified.sum()),pilot_basin_id=chosen,pilot_basin_name=names[chosen],pilot_geometry_count=len(selected),features_available=0,prediction_available=0,research_admitted=0,officially_validated_virtual_stations=0)
js(ROOT/'evidence/CANDIDATE_SCREENING_SUMMARY.json',summary);event('screening_complete',**summary)
