"""Actual partial-coverage river-distance GIS screening, never a prediction count."""
from intake import *
import geopandas as gpd,numpy as np,math
from shapely.geometry import Point,LineString,box,mapping
from shapely.ops import transform,unary_union
from pyproj import Transformer
def main():
 assert (ROOT/'KAZ_N1_FROZEN_PROTOCOL.json').exists()
 protocol=readj(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json');assert sha(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json')==readj(ROOT/'evidence/PROTOCOL_FREEZE.json')['sha256']
 country=gpd.read_file(ROOT/'source/KAZ_COUNTRY_BOUNDARY.geojson').geometry.iloc[0];bbox=tuple(country.bounds)
 riverpath=REPO/'data/raw/hydrorivers/HydroRIVERS_v10_as.shp';basinpath=REPO/'data/raw/hydrobasins/hybas_as_lev12_v1c.shp'
 rivers=gpd.read_file(riverpath,bbox=bbox,engine='pyogrio',columns=['HYRIV_ID','NEXT_DOWN','MAIN_RIV','LENGTH_KM','DIST_DN_KM','CATCH_SKM','UPLAND_SKM','HYBAS_L12','ENDORHEIC'])
 basins=gpd.read_file(basinpath,bbox=bbox,engine='pyogrio',columns=['HYBAS_ID','NEXT_DOWN','MAIN_BAS','UP_AREA','SUB_AREA','ENDO'])
 assert rivers.crs.to_epsg()==4326 and basins.crs.to_epsg()==4326
 rivers=rivers[rivers.geometry.intersects(country)].copy();basins=basins[basins.geometry.intersects(country)].copy()
 print('actual country-intersected rivers',len(rivers),'basins',len(basins),flush=True)
 crs='+proj=laea +lat_0=48 +lon_0=68 +datum=WGS84 +units=m +no_defs'
 fwd=Transformer.from_crs('EPSG:4326',crs,always_xy=True).transform;rev=Transformer.from_crs(crs,'EPSG:4326',always_xy=True).transform;cp=transform(fwd,country)
 rp=rivers.to_crs(crs);byid={int(r.HYRIV_ID):r for r in rp.itertuples()};eligible=rp[(rp.UPLAND_SKM-rp.CATCH_SKM)>=1000].sort_values(['MAIN_RIV','DIST_DN_KM','HYRIV_ID'])
 # HydroBASINS coverage is a real geometry union, not a bbox-based claim of country coverage.
 bgeo=unary_union([g.intersection(country) for g in basins.geometry]);covered=transform(fwd,bgeo).area/cp.area
 minx=float(rivers.total_bounds[0]);countrywest=country.intersection(box(-180,-90,minx,90));west_fraction=transform(fwd,countrywest).area/cp.area
 bid={int(r.HYBAS_ID):r for r in basins.itertuples()};pool=[];excluded=collections.Counter();accepted_xy=[]
 cross_mains=set(int(r.MAIN_RIV) for r in rp.itertuples() if not cp.covers(r.geometry))
 for r in eligible.itertuples():
  if not r.geometry.is_valid or r.geometry.is_empty:excluded['INVALID_GEOMETRY']+=1;continue
  length=float(r.LENGTH_KM);d=float(r.DIST_DN_KM);geom=r.geometry
  if length<=0 or abs(geom.length/1000-length)>max(.15,.05*length):excluded['LENGTH_INCONSISTENCY']+=1;continue
  downstream=byid.get(int(r.NEXT_DOWN))
  if downstream is None:excluded['FLOW_ORIENTATION_NOT_VERIFIED']+=1;continue
  a,b=Point(geom.coords[0]),Point(geom.coords[-1]);da=a.distance(downstream.geometry);db=b.distance(downstream.geometry)
  if min(da,db)>1000 or abs(da-db)<1:excluded['FLOW_ENDPOINT_AMBIGUOUS']+=1;continue
  end0_down=da<db
  first=int(math.ceil((d+1e-9)/25));last=int(math.floor((d+length-1e-9)/25))
  for k in range(first,last+1):
   target=k*25.;fraction=(target-d)/length
   if not 0<fraction<1:continue
   p=geom.interpolate(fraction*geom.length if end0_down else (1-fraction)*geom.length)
   if not cp.contains(p):excluded['OUTSIDE_COUNTRY']+=1;continue
   if p.distance(cp.boundary)<2000:excluded['GENERALIZED_BORDER_BUFFER']+=1;continue
   if any(p.distance(q)<3000 for q in accepted_xy):excluded['GEOMETRY_DUPLICATE_NEAR_JUNCTION']+=1;continue
   lon,lat=rev(p.x,p.y);sub=bid.get(int(r.HYBAS_L12));subvalid=sub is not None and sub.geometry.buffer(1e-6).covers(Point(lon,lat))
   # Point-specific upstream area has NOT been delineated; preserve defensible outlet/lower-bound values.
   props={'station_id':f'KAZ-GEOM-{int(r.HYRIV_ID)}-D{k*25}','status':'CANDIDATE_GEOMETRY','candidate_admitted':False,'research_admitted':False,'features_available':False,'virtual_prediction_available':False,'validation_status':'VALIDATION_NOT_AVAILABLE','water_management_basin':'UNASSIGNED_NO_OFFICIAL_8_BASIN_POLYGON','longitude':round(lon,8),'latitude':round(lat,8),'reach_id':int(r.HYRIV_ID),'next_down_reach_id':int(r.NEXT_DOWN),'main_river_id':int(r.MAIN_RIV),'hydrobasins_l12':int(r.HYBAS_L12),'drainage_polygon_present':bool(subvalid),'upstream_area_lower_bound_km2':float(r.UPLAND_SKM-r.CATCH_SKM),'upstream_area_at_reach_outlet_km2':float(r.UPLAND_SKM),'point_specific_upstream_area_km2':None,'network_distance_from_sink_km':target,'existing_gauge_exclusion':'UNVERIFIED_CURRENT394_COORDINATES_UNAVAILABLE','transboundary_status':'CROSS_BORDER_REACH_OBSERVED' if int(r.MAIN_RIV) in cross_mains else 'UNKNOWN_NOT_FULL_NETWORK','model_status':'NO_KAZ_REGIONAL_MODEL_OR_SAME_SUPPORT_MET','source_river_hash':readj(ROOT/'evidence/GIS_SOURCE_HASHES.json')[str(riverpath)],'source_basin_hash':readj(ROOT/'evidence/GIS_SOURCE_HASHES.json')[str(basinpath)],'scope':'PARTIAL_ASIA_TILE_PRELIMINARY_NOT_NATIONAL_ADMITTED_VIRTUAL_NETWORK'}
   pool.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':props});accepted_xy.append(p)
 assert len(pool)==len({f['properties']['station_id'] for f in pool})
 put(ROOT/'KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson',{'type':'FeatureCollection','name':'Real GIS screening pool, NOT admitted virtual gauges','features':pool})
 # River display geometry is simplified, never assigned Qsim.
 display=[]
 for r in rivers.itertuples():
  if float(r.UPLAND_SKM)<1000:continue
  g=r.geometry.intersection(country).simplify(.003,preserve_topology=True)
  if not g.is_empty:display.append({'type':'Feature','properties':{'reach_id':int(r.HYRIV_ID),'main_riv':int(r.MAIN_RIV),'qsim':None,'prediction_status':'REACH_PREDICTION_NOT_AVAILABLE'},'geometry':mapping(g)})
 put(ROOT/'data/KAZ_PARTIAL_RIVER_DISPLAY.geojson',{'type':'FeatureCollection','features':display})
 coverage={'national_boundary_source':'Natural Earth1:10m v5.1.1, generalized display/screening boundary only','country_polygon_area_km2':cp.area/1e6,'density_denominator_fixed_official_km2':2724900,'river_reaches_intersecting_country_in_local_AS_tile':len(rivers),'hydrobasins_L12_intersecting_country':len(basins),'L12_union_country_coverage_fraction':covered,'country_fraction_west_of_local_river_min_longitude':west_fraction,'preliminary_geometry_points':len(pool),'valid_subbasin_polygon_points':sum(f['properties']['drainage_polygon_present'] for f in pool),'admitted_candidate_count':0,'prediction_available_count':0,'research_admitted_count':0,'directly_validated_KAZ_gauges':0,'exclusions':dict(excluded),'blocking_reasons':['Current394 physical river-gauge coordinates not acquired; no complete overlap exclusion','localAS tiles do not cover all country','No authoritative8 water-management basin polygons','Interior-point full upstream catchments and same-support meteorology not constructed','No Kazakhstan PUB model or valid nationwide Q evaluation'],'fit_calls':0,'qsim_generated':0}
 put(ROOT/'KAZ_N1_GIS_EXECUTION.json',coverage)
 names=[('ARAL_SYRDARYA','阿拉尔—锡尔河'),('BALKHASH_ALAKOL','巴尔喀什—阿拉湖'),('IRTYSH','额尔齐斯河'),('YESIL','伊希姆河'),('ZHAYIK_CASPIAN','乌拉尔—里海'),('NURA_SARYSU','努拉—萨雷苏'),('TOBOL_TORGAI','托博尔—图尔盖'),('SHU_TALAS','楚河—塔拉斯')]
 csvout(ROOT/'KAZ_N1_GEOMETRY_ASSIGNMENT_BY_BASIN.csv',[{'basin_id':i,'basin_name_zh':n,'official_basin_exists':True,'verified_boundary_available':False,'admitted_candidate_count':0,'preliminary_geometry_count':None,'reason':'NO_OFFICIAL_POLYGON_CANNOT_ASSIGN_POINTS_BY_NEAREST_NAME'} for i,n in names]+[{'basin_id':'UNASSIGNED','basin_name_zh':'待取得官方流域边界后空间归属','official_basin_exists':False,'verified_boundary_available':False,'admitted_candidate_count':0,'preliminary_geometry_count':len(pool),'reason':'ACTUAL_GEOMETRY_POOL_NOT_ADMITTED_NETWORK'}])
 print(json.dumps(coverage,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
