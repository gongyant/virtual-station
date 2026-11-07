from common import *
import geopandas as gpd,shutil
def main():
 event('sovereign_country_boundary_amendment','STARTED');dest=ROOT/'runs/P8_INITIAL_ADMIN_BOUNDARY_V1';assert not dest.exists();dest.mkdir(parents=True)
 names=['P8_FROZEN_PROTOCOL.json','BASIN_SCOPE_CROSSWALK.csv','P8_NATIONAL_RIVER_REACHES.gpkg','P8_RIVER_LENGTH_BY_BASIN_ORDER.csv','P8_SIX_BASIN_SUMMARY.csv','P8_EIGHT_BASIN_SUMMARY.csv','P8_CLASSICAL_VS_STRAHLER.csv','P8_OFFICIAL_GAUGE_CROSSWALK.csv','P8_REAL_GAUGE_DENSITY.csv','P8_KAZ_N1_CANDIDATE_RECHECK.csv','P8_SPATIAL_QA.json','P8_NETWORK_EXCEPTIONS.csv','P8_SIX_SCOPE_CONFIG.json']
 for name in names:
  old=ROOT/name
  if old.is_file():assert old.resolve().is_relative_to(ROOT.resolve());shutil.move(str(old),str(dest/name))
 for name in ['BASIN_AREA_QA.json','BASIN_LINE_ALLOCATION.csv','GAUGE_AND_CANDIDATE_STATUS.json','INDEPENDENT_LENGTH_SAMPLE.csv','PROTOCOL_FREEZE.json','GLOBAL_RIVER_SOURCE_CHECK.json','HISTORY_FINAL_CHECK.json','BOUNDARY_LENGTH_SENSITIVITY.json','BOUNDARY_LENGTH_SENSITIVITY_FULL.json']:
  old=ROOT/'evidence'/name
  if old.is_file():shutil.copy2(old,dest/name)
 if (ROOT/'figures').is_dir():shutil.move(str(ROOT/'figures'),str(dest/'figures'))
 n1=pathlib.Path(read(ROOT/'evidence/DISCOVERY.json')['KAZ_N1']);shp=next((n1/'source/naturalearth').glob('*.shp'));d=gpd.read_file(shp);d=d[d.SOVEREIGNT=='Kazakhstan'].copy();assert set(d.ADM0_A3)=={'KAZ','KAB'} and d.is_valid.all()
 country=d.geometry.union_all();new=ROOT/'source/P8_KAZ_SOVEREIGN_BOUNDARY.geojson';gpd.GeoDataFrame([{'source':'Natural Earth1:10m v5.1.1 sovereign units KAZ+KAB','source_features':'Kazakhstan|Baykonur Cosmodrome','geometry':country}],crs=d.crs).to_file(new,driver='GeoJSON')
 p=read(dest/'P8_FROZEN_PROTOCOL.json');p.update(protocol_version='P8_GEOGRAPHIC_CORRECTION_V2',created_utc=now(),previous_protocol_sha256=sha(dest/'P8_FROZEN_PROTOCOL.json'),country_boundary=str(new),country_boundary_sha256=sha(new),country_boundary_limitation='Natural Earth generalized sovereign-country union; SOVEREIGNT=Kazakhstan includes main KAZ and separately mapped Baykonur KAB; not official surveying; explicit eight-basin residual retained',amendment_reason='visible hole revealed main ADMIN country omitted a sovereign subunit; geography correction only, no selection by model scores or gauge-density outcomes')
 put(ROOT/'P8_FROZEN_PROTOCOL.json',p);put(ROOT/'evidence/PROTOCOL_FREEZE.json',{'sha256':sha(ROOT/'P8_FROZEN_PROTOCOL.json'),'created_utc':now(),'before_corrected_river_length_and_gauge_computation':True})
 put(ROOT/'evidence/COUNTRY_BOUNDARY_AMENDMENT.json',{'source':str(shp),'source_hashes':{str(x):sha(x) for x in shp.parent.iterdir() if x.is_file()},'source_feature_attributes':d[['ADMIN','SOVEREIGNT','SOV_A3','ADM0_A3','NAME']].to_dict('records'),'union_sha256':sha(new),'previous_outputs_preserved':str(dest),'N1_not_modified':True,'no_training_or_prediction_score_selection':True})
 put(dest/'INITIAL_OUTPUTS_SHA256.json',{p.relative_to(dest).as_posix():sha(p) for p in dest.rglob('*') if p.is_file()})
 event('sovereign_country_boundary_amendment','FROZEN_BEFORE_RECOMPUTATION',protocol_sha256=sha(ROOT/'P8_FROZEN_PROTOCOL.json'),source_features=['KAZ','KAB'])
 event('operation_log_correction','CORRECTION',corrects='PRIMARY_OUTPUTS_COMPLETED_OPTIONAL_UNION_OVERLAY_INTERRUPTED',facts='original river statistics completed 02:04:48, gauge matching completed02:04:54 and QA completed02:05:04 before delayed progress-control command; no original calculation was interrupted; repeat gauge entry was correctly refused by existing-output guard. Original optional result placeholder was overwritten, retained archive is explicit about provenance; independent full-bbox alternative completes separately. No primary numbers changed by that operation.')
if __name__=='__main__':main()
