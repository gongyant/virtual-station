from common import *
import sqlite3,numpy as np,pyogrio,geopandas as gpd,requests,re
from urllib.parse import urlparse
DB=ROOT/'source/CA-discharge.gpkg';con=sqlite3.connect('file:'+DB.as_posix()+'?immutable=1',uri=True)
gauges=pyogrio.read_dataframe(DB,layer='gauges',IMMUTABLE='YES');country=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='country_boundary').geometry.union_all();management=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='basins_source');target=management[management.basin_id==2].geometry.union_all()
gauges['inside_Kazakhstan_boundary']=gauges.geometry.map(country.covers);gauges['inside_target_management_basin']=gauges.geometry.map(target.covers)
gauges['normalized_CODE']=gauges.CODE.astype(str).str.replace(r'[dm]$','',regex=True)
inventory=[];summary=[]
allcodes=pd.read_sql_query('SELECT CODE,res,COUNT(*) AS rows,MIN(date) AS start,MAX(date) AS end FROM discharge_time_series GROUP BY CODE,res',con)
csv(ROOT/'data/CA_ALL_SERIES_METADATA.csv',allcodes)
qflags=pd.read_sql_query('SELECT * FROM quality_flags',con)
for r in gauges.itertuples():
    ts=allcodes[allcodes.CODE.astype(str)==str(r.CODE)]
    rec=dict(source='CA-discharge v1.0',dataset_DOI='10.5281/zenodo.8147591',source_sha256=digest(DB),source_CODE=str(r.CODE),country_label=r.COUNTRY if pd.notna(r.COUNTRY) else 'MISSING',inside_Kazakhstan_boundary=bool(r.inside_Kazakhstan_boundary),inside_Balkhash_Alakol=bool(r.inside_target_management_basin),river=r.RIVER,name_eng=r.NAME_ENG,name_ru=r.NAME_RU,longitude=r.geometry.x,latitude=r.geometry.y,source_institution=r.SOURCE,has_actual_timeseries=not ts.empty,available_resolutions='|'.join(ts.res.astype(str)),source_start='|'.join(ts.start.astype(str)),source_end='|'.join(ts.end.astype(str)),record_count=int(ts.rows.sum()),Q_unit='m3/s according to source publication; q_m3s norm is not time series',license='CC-BY-4.0',quality='DATASET_LEVEL_FLAGS_NOT_DAILY_QC',within_current_basin_scope=bool(r.inside_target_management_basin),admission='OUTSIDE_TARGET_BASIN' if not r.inside_target_management_basin else 'IDENTITY_AND_ROW_QC_REVIEW_REQUIRED',norm_discharge_not_series=True)
    inventory.append(rec)
csv(ROOT/'P9B_AVAILABLE_Q_INVENTORY.csv',inventory)
kaz=gauges[(gauges.COUNTRY=='KAZ')|gauges.inside_Kazakhstan_boundary].copy()
monthly=[]
for code in kaz.CODE.astype(str).unique():
    d=pd.read_sql_query('SELECT CODE,res,date,value FROM discharge_time_series WHERE CODE=?',(con),params=[code]);d['date']=pd.to_datetime(d.date,errors='coerce');d['numeric_Q']=pd.to_numeric(d.value,errors='coerce')
    for res,sub in d.groupby('res'):
        valid=sub.date.notna() & np.isfinite(sub.numeric_Q) & (sub.numeric_Q>=0)
        q=qflags[qflags.CODE.astype(str)==code].drop(columns='CODE').to_dict('records')
        summary.append(dict(source_CODE=code,resolution=res,rows=len(sub),valid_nonnegative_finite=int(valid.sum()),missing_values=int(sub.numeric_Q.isna().sum()),negative_values=int((sub.numeric_Q<0).sum()),zero_values=int(sub.numeric_Q.eq(0).sum()),duplicate_dates=int(sub.date.duplicated().sum()),start=sub.date.min().strftime('%Y-%m-%d') if len(sub) else None,end=sub.date.max().strftime('%Y-%m-%d') if len(sub) else None,source_quality_flags=json.dumps(q,ensure_ascii=False),in_target_basin=bool(kaz.loc[kaz.CODE.astype(str)==code,'inside_target_management_basin'].any()),status='PUBLIC_SOURCE_ACQUIRED_OUTSIDE_FIRST_BASIN_NOT_P10_READY'))
        if res=='month':
            for rr in sub.itertuples():monthly.append(dict(source_CODE=code,year=rr.date.year,month=rr.date.month,source_date=rr.date.strftime('%Y-%m-%d'),Q_m3s=rr.numeric_Q,measurement_status='YEARBOOK_PROCESSED_POSSIBLE_GAP_FILL_ROW_FLAG_NOT_SUPPLIED',source='CA-dischargev1.0 CC-BY4.0',source_sha256=digest(DB)))
csv(ROOT/'data/KAZ_CA_SERIES_QC_SUMMARY.csv',summary)
if monthly:csv(ROOT/'data/CA_PUBLIC_KAZ_MONTHLY_Q_OUTSIDE_TARGET.csv',monthly)
bas=pyogrio.read_dataframe(DB,layer='basins',IMMUTABLE='YES');atts=pyogrio.read_dataframe(DB,layer='basin_attributes',IMMUTABLE='YES')
desc=pd.read_sql_query('SELECT * FROM basin_attribute_description',con);csv(ROOT/'data/CA_ATTRIBUTE_DESCRIPTION.csv',desc)
csv(ROOT/'data/CA_KAZ_GAUGE_METADATA.csv',kaz.drop(columns='geometry'))
csv(ROOT/'data/CA_KAZ_QUALITY_FLAGS.csv',qflags[qflags.CODE.astype(str).isin(kaz.CODE.astype(str))])
if len(kaz):bas[bas.CODE.astype(str).isin(kaz.normalized_CODE)].to_file(ROOT/'P9B_FIRST_BASIN_GIS.gpkg',layer='CA_KAZ_other_basin_outlines',driver='GPKG',engine='pyogrio')
old=pd.read_csv(P9A/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});old=old[old.primary_500m_geometric_match&(old.nearest_basin_id==2)].copy();out=[]
from pyproj import Geod
G=Geod(ellps='WGS84')
for r in old.to_dict('records'):
    exact=gauges[gauges.normalized_CODE==r['station_code']]
    distances=np.array([G.inv(r['longitude'],r['latitude'],p.x,p.y)[2] for p in gauges.geometry]);near=gauges.iloc[int(distances.argmin())]
    r.update(standard_station_code='UNVERIFIED',name_kazakh='NOT_PROVIDED',name_russian=r['station_name'],name_english='NOT_VERIFIED',commission_retirement_migration='NOT_AVAILABLE',CA_exact_code_count=len(exact),CA_exact_CODE='|'.join(exact.CODE.astype(str)),CA_exact_code_distance_m=float(min([G.inv(r['longitude'],r['latitude'],p.x,p.y)[2] for p in exact.geometry])) if len(exact) else None,nearest_CA_CODE=str(near.CODE),nearest_CA_distance_m=float(distances.min()),CA_source_match='NO_CORROBORATING_CA_GAUGE',official_identity_status='GEOMETRIC_PROVISIONAL',actual_historical_Q='NOT_ACQUIRED_FOR_THIS_STATION',history_start='N/A',history_end='N/A',Q_daily_QC='NOT_AVAILABLE',station_coordinate_bulk_reuse_license='NOT_ESTABLISHED',coordinate_precision='GeoJSON up to8 decimals; no certified positional accuracy',identity_reliability='P9A500mGEOMETRY_ONLY')
    if len(exact):r['CA_source_match']='SOURCE_CONFLICT_CODE_ONLY_MATCH_NOT_CERTIFIED' if r['CA_exact_code_distance_m']>500 else 'CROSS_SOURCE_CODE_AND_LOCATION_REVIEW_REQUIRED';r['official_identity_status']='SOURCE_CONFLICT' if r['CA_exact_code_distance_m']>500 else 'GEOMETRIC_PROVISIONAL'
    out.append(r)
csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',out)
con.close();assert digest(DB,'md5')=='e0ba6664aaec3e0b27138abdfd4ba263'
audit=[dict(source='CA-dischargev1.0',url='https://zenodo.org/records/8147591',download='GPKG24576000bytes MD5 verified',license='CC-BY4.0',actual_gauge_rows=len(gauges),unique_normalized_codes=gauges.normalized_CODE.nunique(),all_series_CODES=allcodes.CODE.nunique(),Kazakhstan_country_label=int(gauges.COUNTRY.eq('KAZ').sum()),target_basin_gauge_rows=int(gauges.inside_target_management_basin.sum()),target_basin_series=int(sum(r['record_count']>0 and r['inside_Balkhash_Alakol'] for r in inventory)),status='ACQUIRED_VALID_PUBLIC_SOURCE_NO_TARGET_BASIN_Q',limitations='Processed yearbook data; normQ distinct; row-level gap-fill/dailyQC not supplied; invalid glacier thinning fields not used'),dict(source='Kazhydromet official historicalQ',url='https://meteo.kazhydromet.kz/database_hydro/',download='READ_TIMEOUT',license='NOT_VERIFIED',actual_gauge_rows=None,status='ACCESS_BLOCKED_TIMEOUT_NO_BYPASS',limitations='No authenticated route or hidden API used'),dict(source='Kazhydromet official water bulletin',url='https://www.kazhydromet.kz/en/water-resources/',download='PAGE200; official2023PDF link discovered',license='PUBLIC_DISPLAY_NOT_A_BULK_TIME_SERIES_GRANT',status='BULLETIN_DATA_EXTRACTION_PENDING',limitations='Annual/basin summaries must not be relabeled continuous monthly station Q'),dict(source='QazSu archived49 target points',url='https://qazsu.gov.kz/',download='P9A readonly snapshot reused',license='BULK_REUSE_UNVERIFIED',actual_gauge_rows=49,status='GEOMETRIC_PROVISIONAL_CURRENT_MEAN_NOT_HISTORICAL_SERIES',limitations='No new continuous Q or station migration record')]
csv(ROOT/'P9B_HISTORICAL_Q_SOURCE_AUDIT.csv',audit)
js(ROOT/'evidence/CA_DATA_AUDIT.json',dict(source_gauge_rows=len(gauges),source_unique_normalized_codes=gauges.normalized_CODE.nunique(),source_basin_rows=len(bas),source_time_series_rows=int(allcodes.rows.sum()),series_ID_count=int(allcodes.CODE.nunique()),KAZ_country_gauge_rows=int(gauges.COUNTRY.eq('KAZ').sum()),KAZ_geometry_gauge_rows=int(gauges.inside_Kazakhstan_boundary.sum()),target_basin_gauges=int(gauges.inside_target_management_basin.sum()),KAZ_actual_series=len(summary),KAZ_monthly_rows=len(monthly),target_basin_Q_admitted=0,target49_CA_exact_code_matches=sum(x['CA_exact_code_count']>0 for x in out),source_Q_status='PROCESSED_OBSERVED_SOURCE_NOT_UNALTERED_DAILY_MEASUREMENT',invalid_glacier_fields_not_used=['gl_dmdt_km3a','gl_dmdtda_mma'],fit_calls=0))
print('CA_KAZ_SERIES_SUMMARY',json.dumps(summary,ensure_ascii=False),flush=True)
event('Q_source_and49identity_audit_complete',CA_gauges=len(gauges),Kazakhstan_gauges=int(gauges.COUNTRY.eq('KAZ').sum()),target_gauges=int(gauges.inside_target_management_basin.sum()),Kazakh_monthly_Q_rows=len(monthly),target49=len(out),fit_calls=0)
