from catchment import *
if __name__=='__main__':
 archive=ROOT/'evidence/initial_grid_geometrycollection';archive.mkdir(exist_ok=False)
 for name in ['data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv','evidence/TAUTURGEN_DRIVER_GRID.json']:
  p=ROOT/name;p.rename(archive/p.name)
 poly=pyogrio.read_dataframe(ROOT/'P9C_CATCHMENT_GIS.gpkg',layer='Tauturgen_D8_catchment').geometry.iloc[0]
 weights=[]
 for ix in range(math.floor((poly.bounds[0]-.05)*10),math.ceil((poly.bounds[2]+.05)*10)+1):
  for iy in range(math.floor((poly.bounds[1]-.05)*10),math.ceil((poly.bounds[3]+.05)*10)+1):
   lo,la=ix/10,iy/10;inter=polygonal(poly.intersection(box(lo-.05,la-.05,lo+.05,la+.05)))
   if inter.is_empty:continue
   a=area(inter)
   if a>1e-9:weights.append(dict(source_station_id='10195',grid_lon=lo,grid_lat=la,overlap_area_km2=a))
 denom=sum(x['overlap_area_km2'] for x in weights);relative=abs(denom-area(poly))/area(poly);assert relative<.001
 for x in weights:x['area_weight']=x['overlap_area_km2']/denom;x['catchment_status']='RASTER_DELINEATION_NUMERICALLY_VALIDATED_EXPLORATORY'
 csvout('data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv',weights)
 old=json.loads((archive/'TAUTURGEN_DRIVER_GRID.json').read_text(encoding='utf-8'))
 old.update(grid_centres=len(weights),partition_relative_difference=relative,grid_latitudes=sorted(set(x['grid_lat'] for x in weights)),grid_longitudes=sorted(set(x['grid_lon'] for x in weights)),weights_admitted_exploratory=True,
  repair='Retain polygon components inside GeometryCollection; first11cell weights missing11.035% area archived; no catchment geometry or Q changes')
 js(ROOT/'evidence/TAUTURGEN_DRIVER_GRID.json',old)
 event(stage='grid_polygon_components_corrected',grid_cells=len(weights),partition_relative_difference=relative,previous_failed_weights_preserved=True)
