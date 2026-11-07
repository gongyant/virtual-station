from p5lib import *
from pyproj import Transformer
meta=P/"external_metadata/extracted/streamflow_gauges"
stations=cr(meta/"estreams_gauging_stations.csv");providers={r["provider_id"]:r for r in cr(meta/"estreams_streamflow_catalogue.csv")}
old={int(r["ID"]):r for r in cr(R/"p1_seasonal_meteorology_ablation/source/metadata/D_gauges/1_attributes/Gauge_attributes.csv",";")}
gids=jl(P/"P5_SHRINK_PROTOCOL.json")["all_stations"];tr=Transformer.from_crs(3035,4326,always_xy=True);out=[]
def normid(x):
 try:return str(int(float(x)))
 except ValueError:return x
for g in gids:
 r=old[g];country={"AUT":"AT","DEU":"DE","CHE":"CH"}[r["country"]];match=[x for x in stations if normid(x["gauge_id"])==normid(r["govnr"]) and x["gauge_country"]==country]
 if not match:
  out.append({"lamah_id":g,"provider_id":r["govnr"],"name":r["name"],"river":r["river"],"candidate_basins":"","identity":"NO_EXACT_PROVIDER_ID_MATCH","distance_km":None,"area_relative_difference":None,"catalogue_start":"","catalogue_end":"","provider":"","redistribution_license":"","license_url":"","met_compatibility":"E-OBS0.1deg differs from frozen LamaH ERA5-Land; no post2017 matching fields acquired","post2017_Q_acquired":False});continue
 lon,lat=tr.transform(float(r["lon"]),float(r["lat"]))
 for m in match:
  dlon=math.radians(float(m["lon"])-lon);dlat=math.radians(float(m["lat"])-lat);a=math.sin(dlat/2)**2+math.cos(math.radians(lat))*math.cos(math.radians(float(m["lat"])))*math.sin(dlon/2)**2;dist=6371*2*math.atan2(math.sqrt(a),math.sqrt(max(0,1-a)))
  area=abs(float(m["area_official"])-float(r["area_gov"]))/float(r["area_gov"]);prov=providers[m["gauge_provider"]]
  state="STRONG_METADATA_IDENTITY" if dist<=1 and area<=.05 else "PROVIDER_ID_MATCH_REQUIRES_GEOMETRY_REVIEW"
  out.append({"lamah_id":g,"provider_id":r["govnr"],"name":r["name"],"river":r["river"],"candidate_basins":m["basin_id"],"identity":state,"distance_km":dist,"area_relative_difference":area,"catalogue_start":m["start_date"],"catalogue_end":m["end_date"],"provider":m["gauge_provider"],"redistribution_license":prov["license_redistribution"],"license_url":prov["source_license"],"met_compatibility":"E-OBS0.1deg differs from frozen LamaH ERA5-Land; no matching post2017 fields acquired","post2017_Q_acquired":False})
cw(P/"P5_EXTERNAL_STATION_CROSSWALK.csv",out)
jw(P/"external_metadata/CROSSWALK_METHOD.json",{"exact_ID_country":True,"coordinate_CRS":"LamaH EPSG3035 transformed with pyproj to EStreams WGS84","strong_metadata_rule":"same officialID/country, distance<=1km, official area relative difference<=5%; metadata only, does not approve merging Q","streamflow_no_model_scores_used":True,"metadata_records":len(stations),"provider_records":len(providers),"matched_old_stations":len({r["lamah_id"] for r in out if r["candidate_basins"]}),"strong_stations":len({r["lamah_id"] for r in out if r["identity"]=="STRONG_METADATA_IDENTITY"}),"actual_external_Q_acquired":False,"matching_post2017_ERA5Land":False})
print(json.dumps({"rows":len(out),"strong_matches":sum(r["identity"]=="STRONG_METADATA_IDENTITY" for r in out),"max_distance_km":max(r["distance_km"] for r in out if r["distance_km"] is not None),"licenses":sorted(set(r["redistribution_license"] for r in out))}))
