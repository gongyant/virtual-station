from acquire import *
import pandas as pd,numpy as np,pyogrio,geopandas as gpd,csv,calendar
from pyproj import Geod
def out(name,d):d.to_csv(ROOT/name,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
def longest(values):
 best=run=0
 for a in values:run=run+1 if a else 0;best=max(best,run)
 return best
js(ROOT/'P9C_Q_RULES_FROZEN.json',dict(version='P9C_Q_v2_SOURCE_TIME_HEADER_CORRECTION_BEFORE_VALID_SCORES',models_fit=0,
 source='World Bank0064229 version2 public daily resource; observation-source report separate from TOPKAPI output',
 dates='strictdd/mmyy;36..99=>1936..1999;00..20=>2000..2020;reject all other footer/invalid rows',
 complete_month='every actual Gregorian date unique, all days finite nonnegative, no missing daily fill;truezero retained',
 sentinels=[-9999],negative='othernegativequarantine',repeats='atleast3identicalmonthlymeansflagonly',
 peak='10xpositivecalendar-monthmedianflagonly;not model-based selection',
 identity='metadata spatial target membership not certified; nearest49 within500m/area agreement is provisional corroboration;no name-only or score selection',
 primary_gate='P9B frozen8gauges3groups8completeyears plus provenance/identity/QC/rights/pointcatchment/drivers;not relaxed'))
meta=pd.read_csv(ROOT/'source/stations_daily_discharge.csv',sep=';',dtype={'Station':str})
artifact='System.IO.MemoryStream'
meta['source_Name_raw']=meta.Name
meta['Name']=meta.Name.str.removesuffix(artifact).str.rstrip()
meta['source_footer_artifact_removed_from_derived_name']=meta.source_Name_raw.ne(meta.Name)
with (ROOT/'source/data_daily_discharge.csv').open(encoding='utf-8-sig',newline='') as f:header=next(csv.reader(f))
assert header[0]=='date' and header[-1]=='' and all(x.isdigit() for x in header[1:-1])
logical_header=['date','source_midnight_time']+header[1:-1]
raw=pd.read_csv(ROOT/'source/data_daily_discharge.csv',skiprows=1,names=logical_header,dtype={'date':str,'source_midnight_time':str})
date_token=raw.date.str.fullmatch(r'\d{2}/\d{2}/\d{2}',na=False)
bad=raw[~date_token].copy();out('evidence/WB_NON_DATE_SOURCE_ROWS.csv',bad)
valid=raw[date_token].copy();assert valid.source_midnight_time.eq('00.00').all()
js(ROOT/'evidence/WB_CSV_COLUMN_ALIGNMENT_CONTRACT.json',dict(raw_header=header,logical_header=logical_header,
 normalization='sourceCSVomitsmidnightTIMEcolumnnameandhastrailingemptyheader;data78fields=date,time,76Qcolumns;noQvalueschanged',
 evidence='all31047date rows secondtokenliterally00.00;lastnumericcolumncontainsvalidobservationsnotextraneous;source station order preserved',
 source_rows_with_midnight=int(valid.source_midnight_time.eq('00.00').sum()),formal_publisher_schema_confirmation='NOT_PROVIDED',
 rejected_attempt='exploratory_temporal_REJECTED_COLUMN_ALIGNMENT;initialQcountsandscoreswithdrawn',raw_file_sha256=sha(ROOT/'source/data_daily_discharge.csv')))
parts=valid.date.str.split('/',expand=True).astype(int)
yy=parts[2];year=np.where(yy<=20,2000+yy,1900+yy)
dates=pd.to_datetime(dict(year=year,month=parts[1],day=parts[0]),errors='raise')
assert dates.min()==pd.Timestamp('1936-01-01') and dates.max()==pd.Timestamp('2020-12-31')
assert dates.is_unique and dates.is_monotonic_increasing
valid.index=pd.DatetimeIndex(dates);valid=valid.drop(columns=['date','source_midnight_time'])
P9A=ROOT.parent/'vhs_kaz_p9a_network_station_audit'
country=pyogrio.read_dataframe(P9A/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='country_boundary').geometry.union_all()
basin=pyogrio.read_dataframe(OLD/'P9B_FIRST_BASIN_GIS.gpkg',layer='management_basin').geometry.union_all()
geo=gpd.GeoDataFrame(meta,geometry=gpd.points_from_xy(meta.lon,meta.lat),crs=4326)
geo['inside_country_geometry']=geo.geometry.map(country.covers);geo['inside_first_basin_geometry']=geo.geometry.map(basin.covers)
out('data/WB_STATION_METADATA_CLEANED.csv',geo.drop(columns='geometry'))
previous=pd.read_csv(OLD/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str})
G=Geod(ellps='WGS84');relations=[];summaries=[];monthly=[];years=[]
target_ids=set(geo.loc[geo.inside_first_basin_geometry,'Station'])
for code in valid.columns:
 series=pd.to_numeric(valid[code],errors='coerce');finite=np.isfinite(series);sentinel=series.eq(-9999);othernegative=series.lt(0)&~sentinel;good=finite&series.ge(0)
 source_row=geo[geo.Station==code]
 row=source_row.iloc[0] if len(source_row)==1 else None
 mon=pd.DataFrame({'Q_daily':series.where(good),'valid':good.astype(int),'source_negative':othernegative.astype(int),'source_sentinel':sentinel.astype(int)})
 mm=mon.resample('MS').agg(Q_mean=('Q_daily','mean'),valid_days=('valid','sum'),negative_days=('source_negative','sum'),sentinel_days=('source_sentinel','sum'))
 mm['required_days']=mm.index.days_in_month;mm['complete']=mm.valid_days.eq(mm.required_days)
 mm['Q_monthly']=mm.Q_mean.where(mm.complete)
 yy=mm.groupby(mm.index.year).agg(complete_months=('complete','sum'));cy=yy.index[yy.complete_months==12].tolist()
 gg=series[good]
 summary=dict(source='WB0064229v2_DAILY_OBSERVED_SOURCE',source_station_id=code,name=row.Name if row is not None else 'MISSING_STATION_METADATA',
  longitude=row.lon if row is not None else None,latitude=row.lat if row is not None else None,source_area_km2=row.area if row is not None else None,
  inside_Kazakhstan=bool(row.inside_country_geometry) if row is not None else None,inside_first_basin=bool(row.inside_first_basin_geometry) if row is not None else None,
  date_start=str(gg.index.min().date()) if len(gg) else None,date_end=str(gg.index.max().date()) if len(gg) else None,
  valid_daily_values=int(good.sum()),zero_days=int(series.eq(0).sum()),missing_sentinel_days=int(sentinel.sum()),other_negative_days=int(othernegative.sum()),
  complete_months=int(mm.complete.sum()),complete_calendar_years=len(cy),complete_year_list='|'.join(map(str,cy)),longest_contiguous_complete_months=longest(mm.complete),
  longest_constant_zero_days=longest(series.eq(0)),source_unit='m3/s',license='WB_DATASET_CC_BY4.0;station-original-terms-chain_not_individually_provided',
  observation_grade='OBSERVED_SOURCE_TECHNICAL_REPORT_P24;no dailyQC or original agency by station',
  monthly_numeric_QC='COMPLETE_GREGORIAN_DAYS_FINITE_NONNEGATIVE;ZERO_AND_REPEAT_NOT_DELETED',Q_admission='DATA_QC_ONLY',
  E2='NOT_READY_NO_ADMITTED_DRIVERS',P10='NOT_READY_IDENTITY_QC_CATCHMENT_DRIVERS_HOLDOUT')
 summaries.append(summary)
 if code in target_ids:
  for dt,r in mm.iterrows():
   monthly.append(dict(source_station_id=code,year=dt.year,month=dt.month,Q_m3s=r.Q_monthly,source_partial_mean_not_admitted=r.Q_mean,
    valid_days=r.valid_days,required_days=r.required_days,sentinel_days=r.sentinel_days,negative_days=r.negative_days,complete_month=bool(r.complete),
    daily_QC='NOT_PROVIDED',imputation='NONE_IN_THIS_PROCESS;SOURCE_FILL_STATUS_NOT_PROVIDED',observation_class='PUBLIC_OBSERVED_SOURCE_PROCESSED;NOT_TOPKAPI_SIMULATION',
    unit='m3/s',P10_admitted=False))
  for y,r in yy.iterrows():years.append(dict(source_station_id=code,year=y,complete_months=int(r.complete_months),complete_year=bool(r.complete_months==12)))
 if row is not None and row.inside_first_basin_geometry:
  ds=G.inv(np.repeat(row.lon,len(previous)),np.repeat(row.lat,len(previous)),previous.longitude.values,previous.latitude.values)[2]
  ix=int(np.argmin(ds));near=previous.iloc[ix];distance=float(ds[ix]);area_rel=abs(row.area-near.source_upstream_area_km2)/near.source_upstream_area_km2 if row.area>0 and near.source_upstream_area_km2>0 else None
  state='GEOMETRIC_PROVISIONAL_WITH_AREA_SUPPORT' if distance<=500 and area_rel is not None and area_rel<=.05 else 'SOURCE_CONFLICT_OR_HISTORICAL_LOCATION_UNRESOLVED'
  relations.append(dict(source='WB0064229v2',source_station_id=code,source_name=row.Name,source_longitude=row.lon,source_latitude=row.lat,source_area_km2=row.area,
   nearest_P9B_station_code=near.station_code,P9B_station_name=near.station_name,P9B_longitude=near.longitude,P9B_latitude=near.latitude,P9B_area_km2=near.source_upstream_area_km2,
   geodesic_distance_m=distance,relative_area_difference=area_rel,identity_status=state,official_code_certification=False,
   name_only_not_confirmation=True,commission_retirement_migration='NOT_PROVIDED',complete_years=len(cy),QC='SOURCE_DAILY_FLAG_NOT_PROVIDED'))
out('P9C_GAUGE_Q_ADMISSION.csv',pd.DataFrame(summaries));out('P9C_HISTORICAL_STATION_CROSSWALK.csv',pd.DataFrame(relations))
monthly=pd.DataFrame(monthly)
for code,indices in monthly.groupby('source_station_id').groups.items():
 d=monthly.loc[indices];q=d.Q_m3s
 # flag repeats, preserve every source-valid mean; no automatic placeholders.
 same=q.notna()&q.eq(q.shift(1));run=same.groupby((~same).cumsum()).transform('sum')+1
 monthly.loc[indices,'repeat3_suspect_only']=((run>=3)&q.notna()).values
 med=d.groupby('month').Q_m3s.transform('median')
 monthly.loc[indices,'peak10x_calendar_median_suspect_only']=((med>0)&(q>10*med)).values
out('P9C_MONTHLY_Q_QC.csv',monthly);out('data/WB_TARGET_STATION_YEAR_COMPLETENESS.csv',pd.DataFrame(years))
source_summary=dict(raw_daily_rows=len(raw),valid_date_rows=len(valid),quarantined_nondate_rows=len(bad),daily_duplicate_dates=int(dates.duplicated().sum()),
 source_numeric_columns=len(valid.columns),station_metadata_rows=len(meta),metadata_missing_source_columns=[x for x in valid.columns if x not in set(meta.Station)],corrected_midnight_time_field=True,
 target_station_metadata_count=len(target_ids),target_ids=sorted(target_ids),target_complete_months=int(monthly.complete_month.sum()),
 target_complete_year_station_pairs=int(sum(x['complete_calendar_years'] for x in summaries if x['source_station_id'] in target_ids)),
 target_stations_atleast8years=[x['source_station_id'] for x in summaries if x['source_station_id'] in target_ids and x['complete_calendar_years']>=8],
 source_footer='System.IO.MemoryStream22bytes appended by source distribution to both CSVs; original bytes retained; nondate footer excluded with explicit record; metadata name suffix removed only in derived table',
 fit_calls=0,model_score_calls=0)
js(ROOT/'evidence/WB_Q_COMPUTATION_SUMMARY.json',source_summary)
print(json.dumps(source_summary,ensure_ascii=False,indent=2))
print(pd.DataFrame(summaries).query('inside_first_basin==True')[['source_station_id','name','date_start','date_end','complete_months','complete_calendar_years']].to_string(index=False))
event(stage='WB_real_Q_aggregation_complete',**source_summary)
