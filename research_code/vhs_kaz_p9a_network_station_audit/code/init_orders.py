from common import *
import pyogrio,geopandas as gpd,numpy as np,sqlite3,shutil,platform
for d in ['code','evidence','data','figures','logs','source']:(ROOT/d).mkdir(parents=True,exist_ok=True)
event('START',argv=sys.argv,fit_calls=0,Q_scoring_calls=0)
hist=read(P8/'evidence/HISTORY_BEFORE.json')
for line in (P8/'SHA256SUMS.txt').read_text(encoding='utf-8-sig').splitlines():
    h,rel=line.split('  ',1);hist[str(P8/rel)]=h
hist[str(P8/'SHA256SUMS.txt')]=sha(P8/'SHA256SUMS.txt')
js(ROOT/'evidence/HISTORY_BASELINE.json',hist)
history_check(ROOT/'evidence/HISTORY_INITIAL_CHECK.json')
inventory=[]
for p in [GPKG,GLOBAL,GLOBAL.with_suffix('.dbf'),GLOBAL.with_suffix('.shx'),P8/'source/qazsu_hydroposts_response.json',P8/'P8_OFFICIAL_GAUGE_CROSSWALK.csv',P8/'P8_KAZ_N1_CANDIDATE_RECHECK.csv',N1/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson']:
    inventory.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)))
js(ROOT/'evidence/INPUT_INVENTORY.json',inventory)
js(ROOT/'evidence/ENVIRONMENT.json',dict(python=sys.executable,version=sys.version,platform=platform.platform(),geopandas=gpd.__version__,numpy=np.__version__,pyogrio=pyogrio.__version__,disk_free_bytes=shutil.disk_usage(ROOT).free))
prot=dict(task='KAZ_P9A',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),fit_calls=0,Q_scoring_calls=0,
 primary_order='ORD_CLAS',parallel_order='ORD_STRA',all_observed_orders_retained=True,source_order_not_recomputed=True,projected_CRS='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs',revision='P9A_COORDINATE_IMPLEMENTATION_V2',
 length='WGS84 ellipsoidal vertex-to-vertex geodesic km; preserve P8 sovereign-country union including Baykonur and basin allocation',
 gauge_snap_m=500,gauge_ambiguity_m=10,identity='inherit P8 provisional geometry subset; no official identity certification inferred',
 topology='unique source HYRIV_ID->NEXT_DOWN directed graph; use original global upstream closure; clipped fragments never treated as independent source reaches',
 endpoint_connection_tolerance_m=100,mainstem='unique same-ORD_CLAS upstream continuation; ambiguous continuations return N/A; separate longest-headwater-path field',
 offsets='orient source reach by NEXT_DOWN endpoint; project station onto its source line; measure upstream partial line by WGS84 geodesic, not fractional source length',
 completeness='complete only within thresholded HydroRIVERS global product; physical headwater/channel completeness not certified',
 pilot_selection=dict(basin_rule='max count P8 primary provisional gauges, then max topology-qualified candidates, then basin_id; no Q scores',target_count=20,maximum_count=30,minimum_upstream_area_lower_bound_km2=1000,minimum_available_gauge_distance_m=5000,minimum_candidate_euclidean_spacing_m=3000,river_orders=[1,2,3,4,5,6,7],requires_topological_gauge_connection=True,priority='ORD_CLAS asc; lower-bound upstream area desc; stable candidate ID',admission='ENGINEERING_GEOMETRY_ONLY; missing point catchment and homogeneous forcing block scientific VHS admission'),
 missing_Q='No teacher Q; public current snapshot fields are not continuous historical training labels',
 six_subset=read(P8/'P8_FROZEN_PROTOCOL.json')['six_scope'],six_scope_supervisor_confirmed=False,
 audit_tolerances=dict(partition_km=1e-4,offset_km=1e-7,independent_geodesic_km=1e-6),
 stop='P9A only; no training, prediction, websites, P9B or P10')
js(ROOT/'P9A_FROZEN_PROTOCOL.json',prot)
event('protocol_frozen',sha256=sha(ROOT/'P9A_FROZEN_PROTOCOL.json'))
n=pyogrio.read_dataframe(GPKG,layer='national_reaches',read_geometry=False)
b=pyogrio.read_dataframe(GPKG,layer='basin_fragments',read_geometry=False)
bas=pyogrio.read_dataframe(GPKG,layer='basins_source',read_geometry=False)
print('BASIN_COLUMNS',bas.columns.tolist(),flush=True)
rows=[]; br=[]
for field in ['ORD_CLAS','ORD_STRA']:
    orders=sorted(set(range(1,8))|set(n[field].dropna().astype(int)))
    for order in orders:
        s=n[n[field]==order];rows.append(dict(order_scheme=field,order_value=order,order_scope='1_TO_7' if order<=7 else 'ABOVE_7',source_reaches=s.HYRIV_ID.nunique(),length_km=s.length_km.sum(),missing_order_records=int(n[field].isna().sum())))
    for (bid,bname),sub in b.groupby(['basin_id','basin_name'],dropna=False):
        for order in orders:
            s=sub[sub[field]==order];br.append(dict(basin_id=int(bid),basin_name=bname,six_subset=bool(sub.six_subset.iloc[0]),order_scheme=field,order_value=order,order_scope='1_TO_7' if order<=7 else 'ABOVE_7',fragment_count=len(s),unique_source_reaches=s.HYRIV_ID.nunique(),length_km=s.length_km.sum()))
csv(ROOT/'P9A_ORDER_1_TO_7.csv',rows)
df=pd.DataFrame(br);csv(ROOT/'P9A_EIGHT_BASIN_ORDER_SUMMARY.csv',df[df.basin_id>0]);csv(ROOT/'P9A_SIX_BASIN_ORDER_SUMMARY.csv',df[(df.basin_id>0)&df.six_subset]);csv(ROOT/'P9A_UNASSIGNED_ORDER_SUMMARY.csv',df[df.basin_id==0])
js(ROOT/'evidence/ORDER_FIELD_AUDIT.json',{field:dict(values=sorted(n[field].dropna().astype(int).unique().tolist()),nulls=int(n[field].isna().sum()),source_dtype=str(n[field].dtype)) for field in ['ORD_CLAS','ORD_STRA']})
out=ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg'
if out.exists():raise RuntimeError('Refuse overwriting existing new GPKG')
shutil.copyfile(GPKG,out)
con=sqlite3.connect(out)
geom=con.execute("SELECT column_name,geometry_type_name,srs_id,z,m FROM gpkg_geometry_columns WHERE table_name='national_reaches'").fetchone()
contents=con.execute("SELECT min_x,min_y,max_x,max_y,srs_id FROM gpkg_contents WHERE table_name='national_reaches'").fetchone()
for field in ['ORD_CLAS','ORD_STRA']:
    for label,condition in [(str(k),f'{field}={k}') for k in range(1,8)]+[('gt7',f'{field}>7')]:
        name=f'{field.lower()}_{label}'
        con.execute(f'CREATE VIEW "{name}" AS SELECT * FROM national_reaches WHERE {condition}')
        con.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,description,min_x,min_y,max_x,max_y,srs_id) VALUES(?,?,?,?,?,?,?,?,?)',(name,'features',name,f'P9A inherited global {field}; P8 clipped geometry',*contents))
        con.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?,?,?)',(name,*geom))
con.commit();con.close()
checks=[]
for field in ['ORD_CLAS','ORD_STRA']:
    views=[pyogrio.read_dataframe(out,layer=f'{field.lower()}_{label}',read_geometry=False) for label in list(map(str,range(1,8)))+['gt7']]
    checks.append(dict(check=f'{field}_registered_views_sum',passed=sum(len(v) for v in views)==len(n),records=sum(len(v) for v in views)))
    checks.append(dict(check=f'{field}_length_partition',passed=bool(abs(sum(v.length_km.sum() for v in views)-n.length_km.sum())<1e-7)))
js(ROOT/'evidence/ORDER_VIEW_CHECKS.json',checks)
event('orders_complete',source_reaches=len(n),basin_fragments=len(b),national_km=float(n.length_km.sum()),registered_view_checks=checks)
