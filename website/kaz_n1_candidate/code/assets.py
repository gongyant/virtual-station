from intake import *
import zipfile,pyogrio,geopandas as gpd,numpy as np
def main():
 log=readj(ROOT/'source/SOURCE_LOG.json')
 for name,url in [('official_map','http://ecodata.kz:3838/app_dg_map_en/'),('official_hydro_database','https://meteo.kazhydromet.kz/database_hydro/'),('GRDC_policy','https://grdc.bafg.de/data/data_portal/'),('naturalearth_terms','https://www.naturalearthdata.com/about/terms-of-use/'),('naturalearth_countries_page','https://www.naturalearthdata.com/downloads/10m-cultural-vectors/10m-admin-0-countries/')]:
  if not any(r['name']==name for r in log):log.append(fetch(name,url))
 put(ROOT/'source/SOURCE_LOG.json',log)
 links=readj(ROOT/'source/naturalearth_countries_page.links.json');url=next(x['href'] for x in links if 'ne_10m_admin_0_countries.zip' in x.get('href',''))
 malformed_page_link=url
 if '/http//' in url:url='https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_admin_0_countries.zip'
 p=ROOT/'source/ne_10m_admin_0_countries.zip'
 try:
  with urllib.request.urlopen(url,timeout=45) as r:body=r.read(8000001);assert len(body)<=8000000;headers=dict(r.headers)
  p.write_bytes(body);put(ROOT/'source/NATURALEARTH_DOWNLOAD.json',{'url':url,'malformed_page_link':malformed_page_link,'alternative':'canonical public Natural Earth S3 distribution; no credentials or certificate bypass','path':str(p),'sha256':sha(p),'bytes':len(body),'headers':headers,'license':'Natural Earth public domain','source_version':'5.1.1 as current download page','access_date':'2026-11-03'})
  dest=ROOT/'source/naturalearth'
  with zipfile.ZipFile(p) as z:
   assert all(not pathlib.PurePosixPath(n).is_absolute() and '..' not in pathlib.PurePosixPath(n).parts for n in z.namelist())
   assert sum(i.file_size for i in z.infolist())<40000000
   z.extractall(dest)
  boundary=gpd.read_file(dest/'ne_10m_admin_0_countries.shp',where="ADM0_A3 = 'KAZ'",engine='pyogrio');assert len(boundary)==1 and str(boundary.crs)=='EPSG:4326'
  boundary[['ADM0_A3','NAME','geometry']].to_file(ROOT/'source/KAZ_COUNTRY_BOUNDARY.geojson',driver='GeoJSON');print('KAZ boundary',boundary.total_bounds,flush=True)
 except Exception as e:put(ROOT/'source/NATURALEARTH_DOWNLOAD_FAILURE.json',{'url':url,'error':str(e)});raise
 infos=[];pins={}
 for stem in [REPO/'data/raw/hydrorivers/HydroRIVERS_v10_as',REPO/'data/raw/hydrobasins/hybas_as_lev12_v1c']:
  p=stem.with_suffix('.shp');info=pyogrio.read_info(p)
  infos.append({'path':str(p),'crs':str(info['crs']),'features':int(info['features']),'fields':list(info['fields']),'bounds':list(info['total_bounds']),'geometry_type':info['geometry_type'],'national_coverage':'PARTIAL_ASIA_TILE_NOT_FULL_KAZAKHSTAN','coverage_gap':'western Kazakhstan below57.6E outside this tile; other watershed tile gaps must also be checked'})
  for ext in ['.shp','.dbf','.shx','.prj']:
   q=stem.with_suffix(ext);pins[str(q)]=sha(q)
 put(ROOT/'evidence/EXISTING_GIS_ASSET_INSPECTION.json',infos);put(ROOT/'evidence/GIS_SOURCE_HASHES.json',pins)
 # Legacy user-supplied KMZ are inventoried without assuming present-day membership or redistribution rights.
 legacy=[]
 for q in (REPO/'data/raw/stations').glob('*.kmz'):
  with zipfile.ZipFile(q) as z:
   import xml.etree.ElementTree as ET
   data=z.read('doc.kml');tree=ET.fromstring(data);pts=tree.findall('.//{*}Point/{*}coordinates');coords=[]
   for pt in pts:
    try:lon,lat,*_=map(float,pt.text.strip().split(','));coords.append((lon,lat))
    except (ValueError,AttributeError):pass
  legacy.append({'path':str(q),'sha256':sha(q),'point_count':len(coords),'plausible_coordinate_count':sum(-180<=x<=180 and -90<=y<=90 for x,y in coords),'provenance':'USER_SUPPLIED_LEGACY_KMZ','official_current_network_identity':'UNVERIFIED','license':'NOT_DOCUMENTED_NOT_REPUBLISHED','used_as442_or394_catalog':False,'used_in_candidate_exclusion':False})
 put(ROOT/'evidence/LEGACY_STATION_METADATA_INSPECTION.json',legacy)
 # Protocol frozen before generating any candidate geometry or PUB model scores.
 protocol={'task':'KAZ_N1_NATIONAL_READINESS_AND_EUROPEAN_PUB_DEVELOPMENT','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'area_km2':2724900,'official_network_counts':{'all':442,'river':394},'GIS':{'source_rivers':'existing Asia HydroRIVERS_v10_as','source_basins':'existing Asia HydroBASINS L12','boundary':'Natural Earth 1:10m countries v5.1.1; generalized not cadastral/official border','min_reach_upstream_area_km2':1000,'network_spacing_km':25,'sampling':'fixed multiples25km of DIST_DN_KM; internal point interpolated along true upstream-downstream reach; no blanket endpoint conversion','junction_min_euclidean_separation_m':3000,'country_boundary_buffer_m':2000,'gauge_exclusion_buffer_m':5000,'max_gauge_snap_m':5000,'full_upstream_area_note':'UPLAND_SKM describes reach outlet, not a newly delineated interior-point watershed','admitted_candidate_requires':['current physical station catalog identity and exclusion complete','country/tile coverage known','valid drainage area and basin geometry','unambiguous eight-basin membership'],'geometry_pool_not_equivalent_to_admitted_candidate':True,'no_hydroRIVERS_DIS_AV_CMS_as_model_prediction':True},'PUB':{'classification':'EUROPEAN_PUB_DEVELOPMENT_EXPOSED_HISTORICAL_PERIOD_NOT_KAZAKHSTAN_ACCURACY','stations':[2,6,9,10,22,103,142,171,185,230,255,270,343,377,378,383,401,428,455,460,480,512,533,545],'train_max':'2013-12','score_period':['2014-01','2017-12'],'schemes':['LEAVE_ONE_GAUGE_OUT_REMOVE_NESTED_DONORS','LEAVE_MACRO_REGION_OUT'],'models':['DONOR_CLIMATOLOGY_BASELINE','GEOGRAPHIC_DONOR_TRANSFER','STATIC_CLIMATE_SIMILARITY_TRANSFER','REGIONAL_SHARED_RIDGE'],'fixed_alpha':100,'rho_search':None,'target_Q':'all dates removed from every fit, feature preprocessing, hyperparameter choice and seasonal Q template; separate process scorer after prediction seal','training_donor_Q_unit':'specific runoff mm/day = Q_m3s*86.4/area_km2','donor_transfer_features':['P_month_anomaly','T_month_anomaly','P_lag1_calendar_anomaly'],'static_similarity':['log_area','gauge_elevation','training_era_mean_P','training_era_mean_T'],'regional_features':'local training-era weather z(P,T,L1), standardized logarea and outlet elevation plus their sin/cos seasonal interactions;12 global donor-only month intercepts;ridge100','selection':'no model/hyperparameter selection by heldout score; all raw negative results retained','evaluation':['NSE','KGE and components','RMSE','MAE','PBIAS','MSE skill vs donor climate','DJF','MAY_JUNE'],'exposure':'2014-2017 labels were used in earlier European project phases; spatial masking changes estimand but does not restore blindness','Kaz_Q_downloaded_or_used':False},'website':'new copy of WEB-S1 on8795 if free, local research only; old permissions unchanged'}
 put(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json',protocol);put(ROOT/'evidence/PROTOCOL_FREEZE.json',{'sha256':sha(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json'),'frozen_before_candidate_geometry_and_PUB_scores':True})
 density=readj(ROOT/'KAZ_N1_OFFICIAL_BASELINE.json');d1=442/2724900;d2=394/2724900
 (ROOT/'KAZ_N1_GROUP_MEETING_SUMMARY.md').write_text(f'''# 组会可先使用的已核实事实\n截至2026-11-03官方网页快照，Kazhydromet网络442个观测点，其中河流394；并非394条已获得的训练序列。面积2,724,900 km²。\n全部监测点密度{d1:.12f}个/km²（{d1*10000:.9f}个/万km²）；河流监测点密度{d2:.12f}个/km²（{d2*10000:.9f}个/万km²）。\n当前未核实可训练的哈萨克斯坦Q序列与完整现行站点坐标。已核实亚洲河网实际可读，但该区域瓦片不覆盖全国西部，不能直接给出完整全国选址数量。全国预测NSE/KGE目前NOT_VALIDATED，欧洲P7已知站时序结果不等于全国无资料站精度。\n本轮继续执行真实GIS初筛和独立标记的欧洲站点遮蔽开发验证，最终数量与成绩将在实际产物完成后更新。\n''',encoding='utf-8')
 print('ASSET INTAKE AND PROTOCOL FROZEN',flush=True)
if __name__=='__main__':main()
