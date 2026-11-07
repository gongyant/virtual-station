from common import *
import numpy as np,geopandas as gpd,pyogrio,shapely,rasterio
from shapely.geometry import Point,box
from pyproj import Geod,CRS
from collections import defaultdict,deque
G=Geod(ellps='WGS84');LAEA='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
HB=REPO/'data/raw/hydrobasins/hybas_as_lev12_v1c.shp';OUT=ROOT/'P9B_FIRST_BASIN_GIS.gpkg'
if OUT.exists():raise RuntimeError('Refuse overwriting new GIS; use separate revision output')
js(ROOT/'P9B_GIS_PROTOCOL.json',dict(before_Q_model_scores=True,models_trained=0,river_snap_m=500,available_gauge_exclusion_m=5000,candidate_spacing_m=3000,min_upstream_area_lower_bound_km2=1000,alternate_limit=10,alternate_rule='different tributary/source path, no upstream-downstream nesting between selected alternatives; ORD_CLAS>=2; same frozen P9A screening; order asc area desc id asc',catchment='HydroBASINS L12 entire source-host outlet upstream union; not exact interior-point delineation; no claimed strict point lower bound',grid='ERA5-Land0.1degree nominal grid; geodesic polygon overlap weights for PROXY_ONLY catchments; not admitted point forcings',area_attribute_check_relative_tolerance=.02))
c=pd.read_csv(P9A/'P9A_FIRST_BASIN_PILOT_CANDIDATES.csv');allc=pd.read_csv(P9A/'P9A_VHS_CANDIDATE_SCREENING.csv');n=pd.read_csv(P9A/'data/GLOBAL_UPSTREAM_CLOSURE.csv');N={int(r.HYRIV_ID):r for r in n.itertuples()}
def path(a):
    out=[];seen=set();i=int(a)
    while i in N and i not in seen:out.append(i);seen.add(i);i=int(N[i].NEXT_DOWN)
    return out
pathcache={int(a):path(a) for a in allc[allc.basin_id==2].historical_reach_id}
selected=[];selectedpoints=[]
pool=allc[(allc.basin_id==2)&allc.geometry_qualified&(allc.ORD_CLAS>=2)].sort_values(['ORD_CLAS','source_upstream_area_lower_bound_km2','station_id'],ascending=[True,False,True])
pilotxy=gpd.GeoSeries(gpd.points_from_xy(c.longitude,c.latitude),crs=4326).to_crs(LAEA)
for ix,r in pool.iterrows():
    rid=int(r.HYRIV_ID);ps=set(pathcache[rid]);pt=gpd.GeoSeries([Point(r.longitude,r.latitude)],crs=4326).to_crs(LAEA).iloc[0]
    if any(rid in pathcache[int(s.HYRIV_ID)] or int(s.HYRIV_ID) in ps for s in selected):continue
    if any(pt.distance(g)<3000 for g in [*pilotxy,*selectedpoints]):continue
    selected.append(r);selectedpoints.append(pt)
    if len(selected)>=10:break
alt=pd.DataFrame(selected).reset_index(drop=True);alt['engineering_role']='ALTERNATE_TRIBUTARY_GEOMETRY_NOT_VHS';csv(ROOT/'P9B_ALTERNATE_TRIBUTARY_CANDIDATES.csv',alt)
targets=pd.concat([c.assign(engineering_role='P9A_MAINSTEM_PILOT'),alt],ignore_index=True)
gauge=pd.read_csv(P9A/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});gauge=gauge[gauge.primary_500m_geometric_match&(gauge.nearest_basin_id==2)]
chain=pd.read_csv(P9A/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str});gc=chain[chain.station_id.isin(gauge.station_code)].copy()
def relation(a,b):
    ia=int(a.HYRIV_ID);ib=int(b.HYRIV_ID);oa=float(a.within_reach_offset_km);ob=float(b.within_reach_offset_km)
    if ia==ib:return ('A_UPSTREAM_B' if oa<ob else 'B_UPSTREAM_A' if ob<oa else 'SAME_POSITION'),abs(oa-ob),[ia]
    pa=pathcache.get(ia) or path(ia);pb=pathcache.get(ib) or path(ib)
    if ib in pa:
        segment=pa[:pa.index(ib)];return 'A_UPSTREAM_B',sum(N[x].geometry_length_km for x in segment)-oa+ob,segment+[ib]
    if ia in pb:
        segment=pb[:pb.index(ia)];return 'B_UPSTREAM_A',sum(N[x].geometry_length_km for x in segment)-ob+oa,segment+[ia]
    return 'NO_DIRECTED_PATH_IN_SOURCE_GRAPH',None,[]
rel=[]
for i,a in enumerate(targets.itertuples()):
    for b in list(targets.itertuples())[i+1:]:
        direction,distance,ids=relation(a,b);rel.append(dict(pair_type='CANDIDATE_CANDIDATE',a_id=a.station_id,b_id=b.station_id,relation=direction,along_network_distance_km=distance,source_path_reaches=len(ids),path_ID_sha256=hashlib.sha256('|'.join(map(str,ids)).encode()).hexdigest(),same_HYRIV_ID=a.HYRIV_ID==b.HYRIV_ID,independent_catchments=False if distance is not None else 'NOT_CERTIFIED',source='P9A global upstream closure + interior offsets'))
    for b in gc.itertuples():
        direction,distance,ids=relation(a,b);rel.append(dict(pair_type='CANDIDATE_PROVISIONAL_GAUGE',a_id=a.station_id,b_id=b.station_id,relation=direction,along_network_distance_km=distance,source_path_reaches=len(ids),path_ID_sha256=hashlib.sha256('|'.join(map(str,ids)).encode()).hexdigest(),same_HYRIV_ID=a.HYRIV_ID==b.HYRIV_ID,independent_catchments='NOT_CERTIFIED',source='P9A geometric station identity; not official certification'))
csv(ROOT/'P9B_CANDIDATE_NETWORK_RELATIONSHIPS.csv',rel)
hb=pyogrio.read_dataframe(HB,read_geometry=False,fid_as_index=True);hb['source_fid']=hb.index;hb=hb.set_index('HYBAS_ID');up=defaultdict(list)
for r in hb.itertuples():up[int(r.NEXT_DOWN)].append(int(r.Index))
nat=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='national_reaches',columns=['HYRIV_ID','HYBAS_L12','UPLAND_SKM'],read_geometry=False).set_index('HYRIV_ID')
closures={};hosts={};required=set()
for r in targets.itertuples():
    host=int(nat.loc[r.HYRIV_ID,'HYBAS_L12']);hosts[r.station_id]=host;seen=set();todo=[host]
    while todo:
        z=todo.pop()
        if z in seen:continue
        seen.add(z);todo.extend(up.get(z,[]))
    if not seen.issubset(hb.index):raise RuntimeError('HydroBASINS upstream reference missing')
    closures[r.station_id]=seen;required.update(seen)
geoms=pyogrio.read_dataframe(HB,fids=hb.loc[sorted(required),'source_fid'].tolist(),columns=['HYBAS_ID','UP_AREA','SUB_AREA']).set_index('HYBAS_ID')
country=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='country_boundary').geometry.union_all()
def area(g):return abs(G.geometry_area_perimeter(shapely.orient_polygons(g,exterior_cw=False))[0])/1e6
status=[];polys=[];members=[];weights=[]
for r in targets.itertuples():
    host=hosts[r.station_id];idx=closures[r.station_id];poly=shapely.union_all(geoms.loc[sorted(idx)].geometry.to_numpy());poly=shapely.make_valid(poly) if not poly.is_valid else poly
    a=area(poly);sourcearea=float(hb.loc[host,'UP_AREA']);hostgeom=geoms.loc[host].geometry;inside=hostgeom.covers(Point(r.longitude,r.latitude));foreign=area(poly.difference(country))
    st=dict(candidate_id=r.station_id,engineering_role=r.engineering_role,HYRIV_ID=int(r.HYRIV_ID),ORD_CLAS=int(r.ORD_CLAS),source_host_HYBAS_L12=host,source_host_contains_candidate_point=bool(inside),catchment_state='SOURCE_HOST_OUTLET_PROXY_NOT_EXACT_POINT',point_exact_area_km2=None,proxy_geodesic_area_km2=a,proxy_host_attribute_UP_AREA_km2=sourcearea,proxy_area_relative_difference=abs(a-sourcearea)/sourcearea,unresolved_host_unit_area_km2=area(hostgeom),unresolved_host_fraction=area(hostgeom)/a,foreign_proxy_area_km2=foreign,foreign_fraction=foreign/a,upstream_L12_units=len(idx),point_accuracy='15arcsec-derived L12 unit geometry; source-host outlet includes unresolved within-cell tributaries; not raster delineation',hydrological_DEM_flowdir_status='FULL_CATCHMENT_MATCHED_D8_NOT_AVAILABLE',formal_VHS=False,driver_weight_admission='PROXY_ONLY_NOT_P10_POINT_FORCING',limitations='ENDORHEIC_NETWORK|BIFURCATIONS_LAKES_RESERVOIRS_DIVERSIONS_UNCERTIFIED|SOURCE_GEOMETRY_NOT_FIELD_CERTIFIED')
    if not inside:st['catchment_state']='SOURCE_CONFLICT_HOST_DOES_NOT_CONTAIN_POINT_PROXY_ONLY'
    status.append(st);polys.append(poly)
    members.extend(dict(candidate_id=r.station_id,HYBAS_ID=x,is_host=x==host) for x in sorted(idx))
    minx,miny,maxx,maxy=poly.bounds;ws=[]
    for ix in range(int(np.floor((minx-.05)*10)),int(np.ceil((maxx+.05)*10))+1):
        lon=ix/10
        for iy in range(int(np.floor((miny-.05)*10)),int(np.ceil((maxy+.05)*10))+1):
            lat=iy/10;cell=box(lon-.05,lat-.05,lon+.05,lat+.05)
            if not poly.intersects(cell):continue
            inter=poly.intersection(cell);ar=area(inter) if inter.geom_type in ['Polygon','MultiPolygon'] else 0.
            if ar>1e-10:ws.append(dict(candidate_id=r.station_id,grid_lon=lon,grid_lat=lat,overlap_area_km2=ar,grid_definition='nominalERA5Land0.1degreecellcentre',catchment_status=st['catchment_state']))
    denom=sum(x['overlap_area_km2'] for x in ws)
    for x in ws:x['area_weight']=x['overlap_area_km2']/denom
    st['grid_cells']=len(ws);st['grid_area_partition_relative_error']=abs(denom-a)/a;weights.extend(ws)
    event('proxy_catchment_and_grid',candidate=r.station_id,L12_units=len(idx),area_km2=a,foreign_km2=foreign,weights=len(ws),host_contains_point=bool(inside))
csv(ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv',status);csv(ROOT/'data/HYDROBASINS_UPSTREAM_MEMBERS.csv',members);csv(ROOT/'data/ERA5_LAND_PROXY_AREA_WEIGHTS.csv',weights)
gpd.GeoDataFrame(status,geometry=polys,crs=4326).to_file(OUT,layer='upstream_L12_outlet_proxies',driver='GPKG',engine='pyogrio')
gpd.GeoDataFrame(targets,geometry=gpd.points_from_xy(targets.longitude,targets.latitude),crs=4326).to_file(OUT,layer='engineering_candidates',driver='GPKG',engine='pyogrio')
gpd.GeoDataFrame(gauge,geometry=gpd.points_from_xy(gauge.longitude,gauge.latitude),crs=4326).to_file(OUT,layer='provisional_gauges49',driver='GPKG',engine='pyogrio')
basin=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='basins_source');basin[basin.basin_id==2].to_file(OUT,layer='management_basin',driver='GPKG',engine='pyogrio')
for i,a in enumerate(targets.itertuples()):
    for b in list(targets.itertuples())[i+1:]:
        if a.station_id in set(c.station_id) and b.station_id in set(c.station_id):
            relidx=next(z for z in rel if z['a_id']==a.station_id and z['b_id']==b.station_id);relidx['proxy_basin_members_nested']=closures[a.station_id].issubset(closures[b.station_id]) or closures[b.station_id].issubset(closures[a.station_id]);relidx['identical_host_proxy']=hosts[a.station_id]==hosts[b.station_id]
csv(ROOT/'P9B_CANDIDATE_NETWORK_RELATIONSHIPS.csv',rel)
rasters=[]
for p in (REPO/'data/raw/dem').rglob('*.tif'):
    with rasterio.open(p) as ds:rasters.append(dict(path=str(p),bytes=p.stat().st_size,crs=str(ds.crs),bounds=list(ds.bounds),resolution=list(ds.res),width=ds.width,height=ds.height,nodata=ds.nodata,hydrologically_conditioned='NOT_VERIFIED',flow_direction='NOT_PROVIDED',license='SOURCE_SPECIFIC_VERIFY_BEFORE_DERIVATION',use='HEADER_INSPECTION_ONLY_NO_DELINEATION'))
csv(ROOT/'evidence/DEM_HEADER_INVENTORY.csv',rasters)
for p in [HB.with_suffix(ext) for ext in ['.shp','.dbf','.shx','.prj']]:event('static_source_pin',path=str(p),sha256=digest(p),bytes=p.stat().st_size)
js(ROOT/'evidence/GIS_SUMMARY.json',dict(original_candidates=len(c),alternate_tributary_candidates=len(alt),total_proxy_catchments=len(status),exact_point_catchments=0,proxy_weight_rows=len(weights),unique_ERA5_grid_centres=len(set((x['grid_lon'],x['grid_lat']) for x in weights)),foreign_upstream_preserved=True,fit_calls=0,driver_values_downloaded=0,DEM_rasters_headers_inspected=len(rasters)))
event('GIS_complete',original20=len(c),alternates=len(alt),proxy_catchments=len(status),weight_rows=len(weights),exact_point_catchments=0)
