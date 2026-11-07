from common import *
import numpy as np,geopandas as gpd,pyogrio,shapely,math,ast
from collections import deque
from pyproj import Geod
G=Geod(ellps='WGS84');checks=[]
def ck(name,value,**kw):checks.append(dict(check=name,passed=bool(value),**kw))
# Independent ellipsoidal inverse from frozen P8, copied as source without running its module.
source=(P8/'code/verify.py').read_text(encoding='utf-8');tree=ast.parse(source)
node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='vincenty')
text='\n'.join(source.splitlines()[node.lineno-1:node.end_lineno])+'\n'
(ROOT/'code/vincenty_inverse.py').write_text('import math\n'+text,encoding='utf-8')
exec(compile(text,'frozen_P8_vincenty_inverse','exec'))
ck('independent_inverse_known_equatorial_degree',abs(vincenty((0,0),(1,0))-111.31949079327357)<1e-7)
n=pyogrio.read_dataframe(GPKG,layer='national_reaches');f=pyogrio.read_dataframe(GPKG,layer='basin_fragments')
new=ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg'
ck('national_unique_original_ID',n.HYRIV_ID.is_unique)
ck('fragment_unique_fragment_ID',f.fragment_id.is_unique)
ck('domestic_partition_conserves_length',abs(n.length_km.sum()-f.length_km.sum())<1e-4,difference_km=float(n.length_km.sum()-f.length_km.sum()))
ck('national_count_preserved',len(n)==132620)
for layer in ['national_reaches','basin_fragments','basins_source','country_boundary']:
    a=pyogrio.read_dataframe(GPKG,layer=layer);b=pyogrio.read_dataframe(new,layer=layer)
    ck('GPKG_original_layer_exact_attributes_'+layer,a.drop(columns='geometry').equals(b.drop(columns='geometry')))
    ck('GPKG_original_layer_exact_geometry_'+layer,all(shapely.to_wkb(a.geometry)==shapely.to_wkb(b.geometry)))
for r in pd.read_csv(ROOT/'P9A_ORDER_1_TO_7.csv').itertuples():
    z=n[n[r.order_scheme]==r.order_value]
    ck(f'national_grade_{r.order_scheme}_{r.order_value}',abs(z.length_km.sum()-r.length_km)<1e-5 and z.HYRIV_ID.nunique()==r.source_reaches)
for name in ['P9A_EIGHT_BASIN_ORDER_SUMMARY.csv','P9A_SIX_BASIN_ORDER_SUMMARY.csv','P9A_UNASSIGNED_ORDER_SUMMARY.csv']:
    for r in pd.read_csv(ROOT/name).itertuples():
        z=f[(f.basin_id==r.basin_id)&(f[r.order_scheme]==r.order_value)]
        ck(f'basin_grade_{name}_{r.basin_id}_{r.order_scheme}_{r.order_value}',abs(z.length_km.sum()-r.length_km)<1e-5 and len(z)==r.fragment_count)
for scheme in ['ORD_CLAS','ORD_STRA']:
    tot=0;km=0.
    for label in list(map(str,range(1,8)))+['gt7']:
        d=pyogrio.read_dataframe(new,layer=scheme.lower()+'_'+label,read_geometry=False)
        ck('GIS_view_filter_'+scheme+'_'+label,(d[scheme].gt(7) if label=='gt7' else d[scheme].eq(int(label))).all());tot+=len(d);km+=d.length_km.sum()
    ck('GIS_view_complete_partition_'+scheme,tot==len(n) and abs(km-n.length_km.sum())<1e-7)
rng=np.random.default_rng(90901);sample=np.unique(np.r_[rng.choice(len(f),256,replace=False),f.groupby(['basin_id','ORD_CLAS']).head(1).index])
lengthchecks=[]
for idx in sample:
    r=f.iloc[idx];v=0.
    for line in shapely.get_parts(r.geometry):
        if line.geom_type=='LineString':v+=sum(vincenty(tuple(a),tuple(b)) for a,b in zip(list(line.coords)[:-1],list(line.coords)[1:]))
    err=abs(v-r.length_km);ck('independent_Vincenty_'+str(r.fragment_id),err<1e-6,error_km=float(err));lengthchecks.append(dict(fragment_id=r.fragment_id,saved_km=r.length_km,independent_km=v,error_km=err))
csv(ROOT/'evidence/INDEPENDENT_LENGTH_CHECKS.csv',lengthchecks)
gauges=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str})
laea='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
ng=f.to_crs(laea);pts=gpd.GeoDataFrame(gauges,geometry=gpd.points_from_xy(gauges.longitude,gauges.latitude),crs=4326).to_crs(laea)
# P8 snap distances used basin fragments, not the unsplit source-line chord projection.
# Projecting a split line can differ by millimetres; preserve the original failed national-line comparison.
tree=shapely.STRtree(ng.geometry.to_numpy())
for i,r in gauges.iterrows():
    idx=int(tree.nearest(pts.geometry.iloc[i]));distance=pts.geometry.iloc[i].distance(ng.geometry.iloc[idx])
    ck('independent_snap_distance_'+str(r.station_code),abs(distance-r.nearest_distance_m_LAEA)<1e-4,error_m=float(abs(distance-r.nearest_distance_m_LAEA)))
    ck('original_snapshot_identity_'+str(r.station_code),r.coordinate_axis_verified and r.source_name_exact_match and r.source_code_exact_match)
ck('no_station_identity_promoted',gauges.official_certification.eq('NOT_CONFIRMED').all())
ck('no_historical_Q_claims',gauges.historical_Q_state.eq('NOT_ACQUIRED').all())
chain=pd.read_csv(ROOT/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str})
nodes=pd.read_csv(ROOT/'data/GLOBAL_UPSTREAM_CLOSURE.csv');nodeidx={int(v):i for i,v in enumerate(nodes.HYRIV_ID)}
up={}
for i,r in nodes.iterrows():up.setdefault(int(r.NEXT_DOWN),[]).append(i)
sample_ids=np.unique(np.r_[np.linspace(0,len(chain)-1,24,dtype=int),chain.all_upstream_connected_length_km.idxmax(),chain.source_to_station_mainstem_km.idxmax()])
for ix in sample_ids:
    r=chain.iloc[ix];start=nodeidx[int(r.HYRIV_ID)];q=[start];seen=set()
    while q:
        i=q.pop()
        if i in seen:continue
        seen.add(i);q.extend(up.get(int(nodes.HYRIV_ID.iloc[i]),[]))
    direct=math.fsum(nodes.geometry_length_km.iloc[list(seen)].tolist())-nodes.geometry_length_km.iloc[start]+r.within_reach_offset_km
    ck('independent_reverse_BFS_sum_'+r.station_id,abs(direct-r.all_upstream_connected_length_km)<2e-5,error_km=float(abs(direct-r.all_upstream_connected_length_km)))
    value=0.;i=start;visited=set()
    while True:
        if i in visited:raise RuntimeError('Independent mainstem cycle')
        visited.add(i);value+=float(nodes.geometry_length_km.iloc[i])
        kids=[j for j in up.get(int(nodes.HYRIV_ID.iloc[i]),[]) if nodes.ORD_CLAS.iloc[j]==nodes.ORD_CLAS.iloc[i]]
        if len(kids)==0:break
        if len(kids)>1:raise RuntimeError('Unexpected mainstem ambiguity')
        i=kids[0]
    value=value-nodes.geometry_length_km.iloc[start]+r.within_reach_offset_km
    ck('independent_mainstem_walk_'+r.station_id,abs(value-r.source_to_station_mainstem_km)<1e-5,error_km=float(abs(value-r.source_to_station_mainstem_km)))
for r in chain.itertuples():
    ck('partial_offset_bounded_'+r.station_id,0<=r.within_reach_offset_km<=r.within_reach_full_length_km+1e-7 and r.offset_full_roundtrip_error_km<1e-7)
    ck('three_length_relationships_'+r.station_id,r.source_to_station_mainstem_km<=r.all_upstream_connected_length_km+1e-6 and r.longest_headwater_to_station_km<=r.all_upstream_connected_length_km+1e-6)
c=pd.read_csv(ROOT/'P9A_VHS_CANDIDATE_SCREENING.csv');pilot=c[c.pilot_selected]
ck('all_1230_candidates_retained',len(c)==1230 and c.station_id.is_unique)
ck('pilot_only_one_basin',pilot.basin_id.nunique()==1)
ck('pilot_20_real_points',len(pilot)==20 and pilot.geometry_qualified.all())
ck('no_false_virtual_prediction_available',c.prediction_status.eq('VIRTUAL_PREDICTION_NOT_AVAILABLE').all())
ck('no_false_research_admission',c.research_admission.eq('NOT_ADMITTED').all())
pg=gpd.GeoDataFrame(pilot,geometry=gpd.points_from_xy(pilot.longitude,pilot.latitude),crs=4326).to_crs(laea)
for i in range(len(pg)):
    for j in range(i):ck(f'pilot_3km_spacing_{i}_{j}',pg.geometry.iloc[i].distance(pg.geometry.iloc[j])>=3000)
ck('pilot_available_gauge_5km_separation',pilot.nearest_available_river_gauge_distance_m.ge(5000).all())
ck('source_graph_DAG_and_connected',read(ROOT/'evidence/TOPOLOGY_AUDIT.json')['closure_cycles_unprocessed']==0 and read(ROOT/'evidence/TOPOLOGY_AUDIT.json')['closure_endpoint_edges_over_100m']==0)
history_check(ROOT/'evidence/HISTORY_FINAL_CHECK.json')
ck('history_hash_protection',read(ROOT/'evidence/HISTORY_FINAL_CHECK.json')['failed']==0)
js(ROOT/'P9A_INDEPENDENT_QA.json',dict(passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks,independent_length_sample_n=len(lengthchecks),max_length_error_km=max(x['error_km'] for x in lengthchecks),fit_calls=0,Q_scoring_calls=0,not_scientific_certification=True))
event('independent_QA_complete',passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks))
if any(not x['passed'] for x in checks):raise RuntimeError('Independent QA failed; inspect explicit failures')
