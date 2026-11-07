from acquire import *
import zipfile,numpy as np,pandas as pd,xarray as xr,calendar
DR=ROOT/'driver'
def out(name,d):d.to_csv(DR/name,index=False,encoding='utf-8-sig',na_rep='N/A',float_format='%.12g')
def aggregate(kind):
 source=DR/f'ERA5L_{kind}.bin';parts=[];members=[]
 if zipfile.is_zipfile(source):
  with zipfile.ZipFile(source) as z:
   for i,item in enumerate(z.infolist()):
    if item.is_dir():continue
    assert item.file_size<100_000_000
    dest=DR/f'{kind}_SOURCE_VAR_{i}.nc'
    if not dest.exists():dest.write_bytes(z.read(item))
    parts.append(xr.open_dataset(dest));members.append(dict(file=dest.name,member=item.filename,sha256=sha(dest)))
  ds=xr.merge(parts,join='exact')
 else:ds=xr.open_dataset(source)
 key='valid_time' if 'valid_time' in ds.coords else 'time';times=pd.DatetimeIndex(ds[key].values)
 assert times.is_unique and times.is_monotonic_increasing
 assert (times[1:]-times[:-1]==pd.Timedelta(hours=1)).all()
 assert ds.t2m.attrs['units']=='K' and ds.tp.attrs['units']=='m'
 weights=pd.read_csv(ROOT/'data/TAUTURGEN_ERA5_LAND_AREA_WEIGHTS.csv')
 assert abs(weights.area_weight.sum()-1)<1e-8
 T=np.zeros(len(times));P=np.zeros(len(times));rawP=np.zeros(len(times));selection=[];PT=[];negative=[];min_raw=0.
 js(DR/'PRECIP_NUMERIC_QC_AMENDMENT_v2.json',dict(rule='Per-cell NetCDF tiny negative precipitation in [-0.001,0)mm/h is clamped to0 in derived physical-P only; less than-0.001blocks. Raw files and raw monthly sums retained.',
  primary_source='https://forum.ecmwf.int/t/negative-values-in-era5-precipitation-data/1636',
  additional_source='https://confluence.ecmwf.int/spaces/UDOC/pages/208501579/',
  threshold_is_design_choice_not_instrument_uncertainty=True,scope='samefixedruleforpilotandlaterperiod;beforeanymodelscore',
  previous_failure='strict_nonnegative_check_detected_tinyrawNetCDFnegatives;notmissingvalues;notQ;noarbitrarygapfill'))
 for w in weights.itertuples():
  ix=int(np.argmin(abs(ds.longitude.values-w.grid_lon)));iy=int(np.argmin(abs(ds.latitude.values-w.grid_lat)))
  assert abs(float(ds.longitude.values[ix])-w.grid_lon)<1e-4 and abs(float(ds.latitude.values[iy])-w.grid_lat)<1e-4
  t=ds.t2m.isel(longitude=ix,latitude=iy).values.astype(float)-273.15;p=ds.tp.isel(longitude=ix,latitude=iy).values.astype(float)*1000
  assert t.shape==(len(times),) and p.shape==(len(times),) and np.isfinite(t).all() and np.isfinite(p).all()
  min_raw=min(min_raw,float(p.min()))
  assert p.min()>=-.001,'Negative precipitation exceeds frozen small-numeric-artifact bound'
  for i in np.where(p<0)[0]:negative.append(dict(time=str(times[i]),grid_lon=w.grid_lon,grid_lat=w.grid_lat,raw_precipitation_mm=float(p[i]),derived_physical_P_mm=0.,area_weight=w.area_weight))
  rawP+=p*w.area_weight;p=np.maximum(p,0.)
  T+=t*w.area_weight;P+=p*w.area_weight;PT.append((t,p,w.area_weight))
  selection.append(dict(requested_lon=w.grid_lon,requested_lat=w.grid_lat,actual_lon=float(ds.longitude.values[ix]),actual_lat=float(ds.latitude.values[iy]),weight=w.area_weight))
 assert P.min()>=0
 out(f'{kind}_NEGATIVE_PRECIPITATION_QC.csv',pd.DataFrame(negative,columns=['time','grid_lon','grid_lat','raw_precipitation_mm','derived_physical_P_mm','area_weight']))
 js(DR/f'{kind}_NETCDF_INSPECTION.json',dict(source_sha256=sha(source),members=members,selected_cells=selection,
  dimensions=dict(ds.sizes),time_start=str(times.min()),time_end=str(times.max()),
  variable_units={v:dict(ds[v].attrs) for v in ['t2m','tp']},minimum_weighted_hourly_P_mm=float(P.min()),
  transformed_T_C_range=[float(T.min()),float(T.max())],precip_deaccumulation_applied=False,raw_negative_cell_hours=len(negative),min_raw_cell_P_mm=min_raw,
  numeric_negative_correction='explicitv2physicalderivedP;rawpreserved;missingvaluesneverzero'))
 start,end=('1965-01-01','1965-12-31') if kind=='PILOT1965' else ('1964-01-01','1978-12-31')
 th=pd.Series(T,index=times);ph=pd.Series(P,index=times-pd.Timedelta(hours=1))
 td=th.resample('D').agg(['mean','count']);pdaily=ph.resample('D').agg(['sum','count']);daily=pd.DataFrame(index=pd.date_range(start,end))
 daily['T_C']=td['mean'];daily['T_hours']=td['count'];daily['P_mm']=pdaily['sum'];daily['P_hours']=pdaily['count']
 assert daily[['P_mm','T_C']].notna().all().all() and daily[['P_hours','T_hours']].eq(24).all().all()
 daily['date']=daily.index.strftime('%Y-%m-%d');monthly=daily.resample('MS').agg(P_mm=('P_mm','sum'),T_C=('T_C','mean'),valid_days=('P_mm','count'))
 monthly['required_days']=monthly.index.days_in_month;assert monthly.valid_days.eq(monthly.required_days).all()
 monthly['P_raw_signed_mm']=pd.Series(rawP,index=times-pd.Timedelta(hours=1)).resample('MS').sum().reindex(monthly.index)
 monthly['P_numeric_negative_correction_mm']=monthly.P_mm-monthly.P_raw_signed_mm
 directP=ph.resample('MS').sum();directT=th.resample('MS').mean();errP=abs(monthly.P_mm-directP.reindex(monthly.index));errT=abs(monthly.T_C-directT.reindex(monthly.index))
 assert errP.max()<1e-8 and errT.max()<1e-8
 # Independent ordering: temporal aggregation at each cell first, then area weighting.
 altP=np.zeros(len(monthly));altT=np.zeros(len(monthly))
 for t,p,w in PT:
  altP+=pd.Series(p,index=times-pd.Timedelta(hours=1)).resample('MS').sum().reindex(monthly.index).values*w
  altT+=pd.Series(t,index=times).resample('MS').mean().reindex(monthly.index).values*w
 gridErrP=float(abs(altP-monthly.P_mm).max());gridErrT=float(abs(altT-monthly.T_C).max());assert gridErrP<1e-8 and gridErrT<1e-8
 monthly['year']=monthly.index.year;monthly['month']=monthly.index.month;monthly['source_station_id']='10195';monthly['driver_class']='ERA5_LAND_REANALYSIS_CATCHMENT_WEIGHTED';monthly['input_support']='COMPLETE_24H_DAYS_VALIDATED'
 out(f'P9C_TAUTURGEN_{kind}_DAILY.csv',daily.reset_index(drop=True));out(f'P9C_TAUTURGEN_{kind}_MONTHLY.csv',monthly.reset_index(drop=True))
 result=dict(passed=True,kind=kind,hours_in_source=len(times),cells_weighted=len(weights),days_complete=len(daily),months_complete=len(monthly),
   leap_days=int(((daily.index.month==2)&(daily.index.day==29)).sum()),maximum_direct_hour_vs_daily_month_P_difference_mm=float(errP.max()),
   maximum_direct_hour_vs_daily_month_T_difference_C=float(errT.max()),maximum_grid_first_vs_time_first_P_difference_mm=gridErrP,maximum_grid_first_vs_time_first_T_difference_C=gridErrT,
   source_Q_read=False,fit_calls=0,new_actual_P_T=True,raw_negative_cell_hours=len(negative),min_raw_cell_P_mm=min_raw,
   maximum_monthly_P_numeric_correction_mm=float(monthly.P_numeric_negative_correction_mm.max()))
 js(DR/f'{kind}_NUMERIC_VALIDATION.json',result);print(json.dumps(result,indent=2));event(stage='actual_ERA5_monthly_aggregation_complete',**result)
if __name__=='__main__':aggregate(sys.argv[1])
