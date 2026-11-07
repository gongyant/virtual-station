from common import *
import geopandas as gpd,pyogrio,pandas as pd,shapely,numpy as np
from pyproj import Geod
def main():
 event('scope_identifier_and_boundary_checks','STARTED');p=read(ROOT/'P8_FROZEN_PROTOCOL.json');rows=list(csv.DictReader((ROOT/'BASIN_SCOPE_CROSSWALK.csv').open(encoding='utf-8-sig')))
 pairs=sorted({(r['properties']['bassein_id'],r['properties']['bassein']) for r in read(ROOT/'source/qazsu_hydroposts_response.json')['features']});mapped={}
 for i,name in pairs:
  s=name.lower();v='Ertis' if 'иртыш' in s else 'Yesil' if 'есил' in s else 'Tobyl-Torgai' if 'тобол' in s else 'Balkhash-Alakol' if 'балхаш' in s else 'Nura-Sarysu' if 'нура' in s else 'Shu-Talas' if 'шу-талас' in s else 'Zhaiyk-Caspian' if 'урало-касп' in s else 'Aral-Syr Darya' if 'арало-сыр' in s else None
  assert v is not None;(mapped.update({v:{'qazsu_basin_id':i,'qazsu_basin_name':name}}))
 assert len(mapped)==8
 for row in rows:
  row['research_source_basin_id']=row.pop('official_eight_basin_id');row.update(mapped[row['name']]);row['national_standard_official_basin_code']=None;row['identifier_status']='Zenodo paper ID and official QazSu system ID are different namespaces; no universal national standard code verified'
 csvout(ROOT/'BASIN_SCOPE_CROSSWALK.csv',rows)
 put(ROOT/'P8_SIX_SCOPE_CONFIG.json',{'scope_id':'PLATFORM_REPORTED_SIX_2025_10_03','basin_names':p['six_scope'],'source':p['six_scope_source'],'supervisor_definition_confirmed':False,'recompute_entry':'derive_six_scope.py --config <new JSON> --output <new CSV>; preserves eight-basin GPKG and original tables'})
 # Exact alternative footprint: bbox contains all eight source basins, not just the NE country bbox.
 shp=next((ROOT/'source/hydrorivers_global').rglob('HydroRIVERS_v10.shp'));b=gpd.read_file(p['basins']);r=pyogrio.read_dataframe(shp,bbox=tuple(b.total_bounds));geod=Geod(ellps='WGS84');rem=np.array(r.geometry.array,dtype=object);total=0
 for _,a in b.sort_values('id').iterrows():
  ix=np.flatnonzero(shapely.intersects(rem,a.geometry));taken=shapely.intersection(rem[ix],a.geometry)
  total+=sum(geod.geometry_length(x)/1000 for x in taken if x.geom_type in ['LineString','MultiLineString']);rem[ix]=shapely.difference(rem[ix],a.geometry)
 put(ROOT/'evidence/BOUNDARY_LENGTH_SENSITIVITY_FULL.json',{'source_eight_basin_union_length_km':total,'source_basin_bbox':list(b.total_bounds),'source_bbox_features':len(r),'primary_country_clip_length_km':read(ROOT/'evidence/BASIN_AREA_QA.json')['national_length_km'],'difference_km':total-read(ROOT/'evidence/BASIN_AREA_QA.json')['national_length_km'],'method':'sequential8source basin geometry union; shared positive-length lines counted once; no clipping to NaturalEarth; full basin bbox','not_replacement_for_primary':True});event('scope_identifier_and_boundary_checks','FINISHED',alternative_boundary_length_km=total)
if __name__=='__main__':main()
