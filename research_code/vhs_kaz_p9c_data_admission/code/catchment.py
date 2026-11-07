from acquire import *
import numpy as np,pandas as pd,geopandas as gpd,pyogrio,rasterio,zipfile,math
from rasterio.windows import from_bounds
from rasterio.features import shapes
from shapely.geometry import Point,box,shape
import shapely
from pyproj import Geod
G=Geod(ellps='WGS84');P9A=ROOT.parent/'vhs_kaz_p9a_network_station_audit';REPO=Path('E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1')
def csvout(name,d):pd.DataFrame(d).to_csv(ROOT/name,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
def area(g):return abs(G.geometry_area_perimeter(shapely.orient_polygons(g,exterior_cw=False))[0])/1e6
def polygonal(g):
 if g.geom_type in ['Polygon','MultiPolygon']:return g
 if hasattr(g,'geoms'):return shapely.union_all([polygonal(x) for x in g.geoms if not x.is_empty])
 return shapely.GeometryCollection()
def rasterpath(name):
 p=ROOT/'source'/name
 with zipfile.ZipFile(p) as z:members=[m.filename for m in z.infolist() if m.filename.lower().endswith('.tif')]
 assert len(members)==1
 return '/vsizip/'+p.as_posix()+'/'+members[0]
if __name__=='__main__':
 protocol=dict(version='P9C_D8_PILOT_v2_SOURCE_ACC_SEMANTICS_CORRECTION',pilot_WB='10195',P9B_code='14187',
  selection='only WB first-basin site with <500m coordinate and <=5% metadata area agreement; no Q scores used',
  outlet='maximum native ACC within150m of frozen P9A HydroRIVERS snappedpoint; reject if >500m from WB coordinate; never choose by matching area',
  area_check_relative_tolerance=.10,grid='officialHydroSHEDSv1.1 D8/ACC3arcsec; no claim literal field-exact boundary',
  completeness='reverseD8 counts==ACC and no connected source cells at window edge; officialTechDocv1.4p18 starts source count at1',window=[76.5,42.0,78.6,44.1],
  revision='Initial plus1 assumption was incorrect; source documentation independently checked before any model or score. Initial failed outputs archived, all spatial rules unchanged.',
  precision='raster-point delineation with ~90m pixel/snap/source-identity limitations, not operational certification')
 js(ROOT/'P9C_CATCHMENT_PROTOCOL.json',protocol)
 chain=pd.read_csv(P9A/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str});g=chain[chain.station_id=='14187'].iloc[0]
 lon,lat=float(g.snapped_longitude),float(g.snapped_latitude)
 with rasterio.open(rasterpath('n40e070_dir.zip')) as ds:
  w=from_bounds(*protocol['window'],transform=ds.transform).round_offsets().round_lengths();flow=ds.read(1,window=w);tr=ds.window_transform(w);profile=ds.profile.copy();sourceinfo=dict(crs=str(ds.crs),transform=list(ds.transform),shape=[ds.height,ds.width],nodata=ds.nodata)
 with rasterio.open(rasterpath('N40E070_acc.zip')) as ds:
  # Source y origins differ by 7e-15 degrees in binary GeoTIFF metadata.
  # Require sub-1e-10 degree agreement, same native pixel shape/CRS; no warp.
  delta=max(abs(a-b) for a,b in zip(ds.transform,sourceinfo['transform']))
  assert delta<1e-10 and [ds.height,ds.width]==sourceinfo['shape'] and str(ds.crs)==sourceinfo['crs']
  sourceinfo['ACC_transform_max_difference_degree']=delta
  acc=ds.read(1,window=w);acc_nodata=ds.nodata
 rr,cc=rasterio.transform.rowcol(tr,lon,lat);candidates=[]
 for y in range(rr-4,rr+5):
  for x in range(cc-4,cc+5):
   xx,yy=rasterio.transform.xy(tr,y,x);distance=G.inv(lon,lat,xx,yy)[2]
   if distance<=150 and acc[y,x]>=0 and acc[y,x]!=acc_nodata:candidates.append((float(acc[y,x]),-distance,y,x,xx,yy))
 assert candidates
 value,_,r,c,ol,oa=max(candidates);distance_WB=G.inv(77.616,43.337,ol,oa)[2];assert distance_WB<=500
 codes={(0,1):1,(1,1):2,(1,0):4,(1,-1):8,(0,-1):16,(-1,-1):32,(-1,0):64,(-1,1):128}
 mask=np.zeros(flow.shape,dtype=np.uint8);mask[r,c]=1;todo=[(r,c)];edge=False;count=0
 while todo:
  y,x=todo.pop();count+=1
  if y==0 or x==0 or y==flow.shape[0]-1 or x==flow.shape[1]-1:edge=True
  for (dy,dx),code in codes.items():
   ny,nx=y-dy,x-dx
   if 0<=ny<flow.shape[0] and 0<=nx<flow.shape[1] and not mask[ny,nx] and flow[ny,nx]==code:
    mask[ny,nx]=1;todo.append((ny,nx))
 polys=[shape(geom) for geom,v in shapes(mask,mask=mask.astype(bool),transform=tr) if v==1]
 poly=shapely.make_valid(shapely.union_all(polys));a=area(poly)
 sums=0.
 for y in np.where(mask.sum(axis=1)>0)[0]:
  top=tr.f+y*tr.e;cell=box(tr.c,top+tr.e,tr.c+tr.a,top);sums+=area(cell)*int(mask[y].sum())
 country=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='country_boundary').geometry.union_all()
 result=dict(source_station_id='10195',P9B_station_code='14187',source_grid='HYDROSHEDS_D8_3s_v1.1',point_official_area_km2=614.,delineated_geodesic_area_km2=a,
  relative_area_error=abs(a-614)/614,WB_longitude=77.616,WB_latitude=43.337,P9A_snapped_longitude=lon,P9A_snapped_latitude=lat,
  raster_outlet_longitude=ol,raster_outlet_latitude=oa,outlet_to_WB_distance_m=distance_WB,outlet_to_source_snap_m=G.inv(lon,lat,ol,oa)[2],
  connected_cells=count,source_ACC_cells_including_outlet=int(value),matches_source_ACC=count==int(value),source_window_edge_touched=edge,
  independent_cell_area_sum_km2=sums,cell_vs_polygon_relative_difference=abs(a-sums)/a,foreign_upstream_area_km2=area(poly.difference(country)),
  valid_polygon=bool(poly.is_valid),native_resolution_arcseconds=3,identity_status='GEOMETRIC_PROVISIONAL_WITH_AREA_SUPPORT',
  daily_QC='NOT_PROVIDED',hydrological_certification='NOT_CERTIFIED',physical_diversion_lake_bifurcation='NOT_VERIFIED',
  point_precision='NATIVE_RASTER_POINT_DELINEATION_NOT_EXACT_FIELD_SURVEY')
 ok=result['matches_source_ACC'] and not edge and result['relative_area_error']<=.10 and result['valid_polygon'] and result['cell_vs_polygon_relative_difference']<1e-4
 result['delineation_status']='RASTER_DELINEATION_NUMERICALLY_VALIDATED_EXPLORATORY' if ok else 'RASTER_DELINEATION_NOT_ADMITTED_FAILED_CHECK'
 js(ROOT/'evidence/TAUTURGEN_D8_RESULT.json',result);print(json.dumps(result,indent=2),flush=True)
 outfile=ROOT/'P9C_CATCHMENT_GIS.gpkg'
 if outfile.exists():raise RuntimeError('Refuse overwrite of current catchment GIS')
 gpd.GeoDataFrame([result],geometry=[poly],crs=4326).to_file(outfile,layer='Tauturgen_D8_catchment',driver='GPKG',engine='pyogrio')
 gpd.GeoDataFrame([dict(source_station_id='10195',point_kind='D8_RASTER_OUTLET')],geometry=[Point(ol,oa)],crs=4326).to_file(outfile,layer='raster_outlet',driver='GPKG',engine='pyogrio')
 rows,cols=np.where(mask);y0,y1=rows.min(),rows.max()+1;x0,x1=cols.min(),cols.max()+1
 m=mask[y0:y1,x0:x1];mt=tr*rasterio.Affine.translation(x0,y0)
 with rasterio.open(ROOT/'data/TAUTURGEN_D8_CATCHMENT_MASK.tif','w',driver='GTiff',height=m.shape[0],width=m.shape[1],count=1,dtype='uint8',crs=4326,transform=mt,nodata=0,compress='deflate') as ds:ds.write(m,1)
 weights=[]
 for ix in range(math.floor((poly.bounds[0]-.05)*10),math.ceil((poly.bounds[2]+.05)*10)+1):
  for iy in range(math.floor((poly.bounds[1]-.05)*10),math.ceil((poly.bounds[3]+.05)*10)+1):
   lo,la=ix/10,iy/10;inter=polygonal(poly.intersection(box(lo-.05,la-.05,lo+.05,la+.05)))
   if inter.is_empty:continue
   v=area(inter)
   if v>1e-9:weights.append(dict(source_station_id='10195',grid_lon=lo,grid_lat=la,overlap_area_km2=v))
 denom=sum(x['overlap_area_km2'] for x in weights)
 for x in weights:x['area_weight']=x['overlap_area_km2']/denom;x['catchment_status']=result['delineation_status']
 csvout('data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv',weights)
 assert abs(denom-a)/a<.001,'Grid partition must preserve polygon area'
 js(ROOT/'evidence/TAUTURGEN_DRIVER_GRID.json',dict(grid_centres=len(weights),partition_relative_difference=abs(denom-a)/a,grid_latitudes=sorted(set(x['grid_lat'] for x in weights)),grid_longitudes=sorted(set(x['grid_lon'] for x in weights)),source_rasters=sourceinfo,weights_admitted_exploratory=ok))
 event(stage='point_D8_delineation_complete',status=result['delineation_status'],cells=count,area_km2=a,area_relative_difference=result['relative_area_error'],weights=len(weights),fit_calls=0)
