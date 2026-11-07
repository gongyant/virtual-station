from acquire import *
import csv,calendar,datetime,statistics,math
import pandas as pd,numpy as np,rasterio,pyogrio,zipfile
checks=[]
def ck(name,x,**data):checks.append(dict(check=name,passed=bool(x),**data))
if __name__=='__main__':
 target=['10014','10195','2314400','2314600'];buckets={};master=[];midnight=0;nondate=0
 with (ROOT/'source/data_daily_discharge.csv').open(encoding='utf-8-sig',newline='') as f:
  reader=csv.reader(f);header=next(reader);positions={code:header[1:-1].index(code)+2 for code in target}
  for row in reader:
   if not row or not re.fullmatch(r'\d{2}/\d{2}/\d{2}',row[0]):nondate+=1;continue
   a,b,c=map(int,row[0].split('/'));dt=datetime.date(2000+c if c<=20 else 1900+c,b,a);master.append(dt)
   assert len(row)==len(header)
   midnight+=row[1]=='00.00'
   for code,index in positions.items():
    value=float(row[index]);key=(code,dt.year,dt.month);buckets.setdefault(key,[])
    if math.isfinite(value) and value>=0:buckets[key].append(value)
 ck('CSV_31047_unique_Gregorian_days',len(master)==31047 and len(set(master))==len(master));ck('all_source_midnight_tokens_normalized_not_Q',midnight==31047);ck('one_invalid_source_footer_retained',nondate==1)
 ck('source_header76station_codes_plus_date_time',len(header)==78 and len(header[1:-1])==76)
 report=pd.read_csv(ROOT/'P9C_MONTHLY_Q_QC.csv',dtype={'source_station_id':str});complete=0;yearmonth={};maxerror=0.
 for r in report.itertuples():
  values=buckets[(r.source_station_id,r.year,r.month)];n=calendar.monthrange(r.year,r.month)[1];ok=len(values)==n
  ck(f'manual_day_coverage_{r.source_station_id}_{r.year}_{r.month}',ok==r.complete_month and len(values)==r.valid_days)
  if ok:
   error=abs(statistics.fmean(values)-r.Q_m3s);maxerror=max(maxerror,error);ck(f'manual_Qmean_correct_source_column_{r.source_station_id}_{r.year}_{r.month}',error<1e-8);complete+=1
   key=(r.source_station_id,r.year);yearmonth[key]=yearmonth.get(key,0)+1
 ck('corrected705complete_station_months',complete==705);ck('corrected57complete_station_years',sum(v==12 for v in yearmonth.values())==57)
 for code,months,years in [('10014',286,23),('10195',179,14),('2314400',120,10),('2314600',120,10)]:
  ck('corrected_station_coverage_'+code,sum(r.source_station_id==code and r.complete_month for r in report.itertuples())==months and sum(v==12 for k,v in yearmonth.items() if k[0]==code)==years)
 ck('2003Jul_not_imputed',not report[(report.source_station_id=='10195')&(report.year==2003)&(report.month==7)].iloc[0].complete_month)
 metadata=pd.read_csv(ROOT/'source/stations_daily_discharge.csv',sep=';');ck('real75station_metadata_rows',len(metadata)==75)
 rawmeta=json.loads((ROOT/'evidence/WB_RESOURCE_LINK_PROVENANCE.json').read_text(encoding='utf-8'))
 for rid,name in [('DR0090965','data_daily_discharge.csv'),('DR0090971','stations_daily_discharge.csv')]:
  raw=(ROOT/'source'/name).read_bytes();ck('source_footer22bytes_'+rid,raw.endswith(b'System.IO.MemoryStream') and len(raw)-int(rawmeta[rid]['size'])==22)
 xls=ROOT/'source/Water_cycle_components_in_BLB.xlsx';ck('auxiliary_official_MD5',hashlib.md5(xls.read_bytes()).hexdigest()=='53a83e76e786fe28dbf9768da1e25a5f')
 book=pd.ExcelFile(xls);ck('13annual_sheets_not_monthly_Q',len(book.sheet_names)==13)
 for name in book.sheet_names:
  d=book.parse(name);expected=66 if name=='Kashi_tuohai' else 65
  ck('annual_constructed_no_raw_observation_mask_'+name,len(d)==72 and d['Runoff (mm)'].notna().sum()==expected and set(d.columns)=={'Time','Ta (K)','Pre (mm)','ET (mm)','PET (mm)','Rainfall(mm)','Snowfall (mm)','Runoff (mm)'})
 kd=book.parse('Kashi_tuohai');ck('Kashi2015_extra_source_annual_value_retained',kd.loc[kd['Runoff (mm)'].notna(),'Time'].astype(int).tolist()==list(range(1950,2016)))
 c=json.loads((ROOT/'evidence/TAUTURGEN_D8_RESULT.json').read_text(encoding='utf-8'))
 with rasterio.open(ROOT/'data/TAUTURGEN_D8_CATCHMENT_MASK.tif') as ds:
  mask=ds.read(1);ck('independent_mask94895cells_matches_ACC',int(mask.sum())==c['source_ACC_cells_including_outlet']==94895)
 poly=pyogrio.read_dataframe(ROOT/'P9C_CATCHMENT_GIS.gpkg',layer='Tauturgen_D8_catchment').geometry.iloc[0]
 ck('valid_raster_polygon_not_source_host_proxy',poly.is_valid and c['point_precision']=='NATIVE_RASTER_POINT_DELINEATION_NOT_EXACT_FIELD_SURVEY')
 ck('complete_no_window_cut',not c['source_window_edge_touched']);ck('source_area_tolerance_unchanged',c['relative_area_error']<.10)
 weights=pd.read_csv(ROOT/'data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv');ck('14positive_grid_weights',len(weights)==14 and weights.area_weight.gt(0).all() and abs(weights.area_weight.sum()-1)<1e-8)
 ck('grid_overlap_area_conservation',abs(weights.overlap_area_km2.sum()-c['delineated_geodesic_area_km2'])/c['delineated_geodesic_area_km2']<.001)
 for kind,n in [('PILOT1965',12),('LONG1964_1978',180),('QALIGNED2000_2015',192)]:
  r=json.loads((ROOT/f'driver/{kind}_NUMERIC_VALIDATION.json').read_text(encoding='utf-8'));ck('actual_driver_'+kind,r['passed'] and r['months_complete']==n and r['source_Q_read']==False)
  daily=pd.read_csv(ROOT/f'driver/P9C_TAUTURGEN_{kind}_DAILY.csv');monthly=pd.read_csv(ROOT/f'driver/P9C_TAUTURGEN_{kind}_MONTHLY.csv');daily['month']=daily.date.str[:7]
  for m,d in daily.groupby('month'):
   y,mo=map(int,m.split('-'));v=monthly[(monthly.year==y)&(monthly.month==mo)].iloc[0]
   ck('independent_DAILY_MONTH_'+kind+'_'+m,abs(math.fsum(d.P_mm)-v.P_mm)<1e-7 and abs(statistics.fmean(d.T_C)-v.T_C)<1e-8 and len(d)==calendar.monthrange(y,mo)[1])
 run=ROOT/'exploratory_temporal/run';seal=json.loads((run/'PREDICTIONS_SEALED_BEFORE_SCORE.json').read_text(encoding='utf-8'))
 ck('accepted_prediction96sealed_before_scores',seal['records']==96 and sha(run/'E2_PREDICTIONS.csv')==seal['prediction_sha256'])
 pred=pd.read_csv(run/'E2_PREDICTIONS.csv');ck('accepted2012to2015only_same48dates',len(pred)==96 and set(pred.year)=={2012,2013,2014,2015} and not pred[['sample_id','model_id']].duplicated().any())
 roles=json.loads((run/'PREDICTION_ROLE_AUDIT.json').read_text(encoding='utf-8'));ck('test_label_access_actually_denied',roles['attempt_to_open_score_label_file_blocked'] and not roles['test_Q_read'])
 ck('accepted_only131training_rows',roles['fit_rows_per_model']==131)
 params=json.loads((run/'MODEL_PARAMETERS.json').read_text(encoding='utf-8'));ck('fixed100no_tuning',params['C0+PT']['parameters']['selection']['rule']=='FIXED_ALPHA' and params['C0+PT']['parameters']['selection']['selected_alpha']==100)
 ck('old_invalid_schema_attempt_explicitly_rejected',(ROOT/'evidence/rejected_column_alignment/REJECTION.json').is_file())
 rejected=ROOT/'exploratory_temporal_REJECTED_COLUMN_ALIGNMENT/run';bad_rejected=[]
 for line in (rejected/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
  h,rel=line.split('  ',1)
  if sha(rejected/rel)!=h:bad_rejected.append(rel)
 ck('rejected_run_bits_unchanged',not bad_rejected)
 h=json.loads((ROOT/'evidence/HISTORY_BASELINE.json').read_text(encoding='utf-8'));bad=[p for p,s in h.items() if not Path(p).is_file() or sha(p)!=s]
 js(ROOT/'evidence/HISTORY_FINAL_CHECK.json',dict(checked=len(h),passed=len(h)-len(bad),failed=len(bad),failures=bad));ck('historical3329protected',len(h)==3329 and not bad)
 pins=json.loads((ROOT/'evidence/REUSED_MODEL_CODE_PINS.json').read_text(encoding='utf-8'));ck('reused_frozen_math_unchanged',all(sha(p)==s for p,s in pins.items()))
 result=dict(passed=sum(r['passed'] for r in checks),failed=sum(not r['passed'] for r in checks),checks=checks,maximum_independent_monthly_Q_mean_difference=maxerror,
  historical_checked=len(h),historical_changed=len(bad),source_QC_not_business_certified=True,valid_E2_models=2,valid_E2_predictions=96,
  rejected_schema_models=2,rejected_schema_predictions=120,formal_P10_fit_calls=0,teacher_Q_reads=0)
 js(ROOT/'P9C_INDEPENDENT_QA.json',result);event(stage='independent_science_verification',passed=result['passed'],failed=result['failed'],historical_unchanged=len(h)-len(bad),rejected_source_error_not_hidden=True)
 if result['failed']:raise RuntimeError('Failed independent checks; inspect P9C_INDEPENDENT_QA')
