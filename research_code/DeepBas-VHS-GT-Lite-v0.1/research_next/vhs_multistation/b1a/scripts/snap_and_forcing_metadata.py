"""Geometry distances and meteorological file structure; no Q statistics."""
from pathlib import Path
import json,csv,collections,math
import pyogrio
from pyproj import Transformer
from shapely.geometry import Point
H=Path(__file__).resolve().parents[1];O=H/'open_metadata';E=H/'evidence'
with (H/'station_metadata.csv').open(encoding='utf-8',newline='') as f:st=list(csv.DictReader(f))
river=pyogrio.read_dataframe(O/'E_stream_network/RiverATLAS.shp',columns=['HYRIV_ID'])
geo={str(int(r.HYRIV_ID)):r.geometry for r in river.itertuples(index=False)}
gauge_geometry=pyogrio.read_dataframe(O/'D_gauges/3_shapefiles/Gauges.shp',columns=['ID'])
assert str(gauge_geometry.crs)=='EPSG:3035'
gg={str(int(r.ID)):r.geometry for r in gauge_geometry.itertuples(index=False)}
rows=[]
for r in st:
    rid=r['nrs_rivat'];g=geo.get(rid)
    point=Point(float(r['lon']),float(r['lat']))
    assert point.distance(gg[r['ID']])<.01,'CSV lon/lat do not match official EPSG:3035 geometry'
    d=point.distance(g) if g is not None else None
    if d is not None:assert math.isfinite(d),'Nonfinite geometric distance'
    rows.append(dict(ID=r['ID'],nrs_rivat=rid,distance_m=d,status='GEOMETRIC_DISTANCE_ONLY' if d is not None else 'NOT_TESTABLE',competing_candidates_reviewed=False))
with (E/'station_reach_distances.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(rows[0]));w.writeheader();w.writerows(rows)
ds=[r['distance_m'] for r in rows if r['distance_m'] is not None]
forcing={}
for scope in ('A_basins_total_upstrm','B_basins_intermediate_all','C_basins_intermediate_lowimp'):
    files=list((O/scope/'2_timeseries/daily').glob('ID_*.csv'));headers=collections.Counter()
    for p in files:
        with p.open(encoding='utf-8-sig') as f:head=f.readline().strip()
        headers[head]+=1
    forcing[scope]=dict(files=len(files),headers=dict(headers),numeric_meteorological_payloads_scanned=False,dates_full_scan=False)
result=dict(station_coordinate_crs='EPSG:3035; fields named lon/lat are projected meters, verified against Gauges.shp',station_reach_distance_rows=len(rows),mapped=len(ds),distance_min_m=min(ds),distance_max_m=max(ds),distance_above_500m=sum(d>500 for d in ds),snap_certification='CONDITIONAL_NEAREST_ALTERNATIVE_AND_OFFICIAL_LOCATION_HISTORY_NOT_REVIEWED',forcing=forcing)
(E/'snap_forcing_summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
