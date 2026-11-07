"""Fixed source-code-derived transform of four official grid time series; no Q."""
import sys,json,calendar,math,zipfile
from pathlib import Path
import numpy as np,xarray as xr
from admit import R,L,P4,jl,jw,cw,sha,readcsv
sys.stdout.reconfigure(encoding='utf-8');D=R/'driver';path=D/'ERA5L_ARCO_EXACT_FOUR_GRID_2015_2020.zip'
if zipfile.is_zipfile(path):
 members=[];points=[];containers=[path]
 for zindex,container in enumerate(containers):
  parts=[]
  with zipfile.ZipFile(container) as z:
   for i,item in enumerate(z.infolist()):
    if item.is_dir():continue
    assert item.file_size<20_000_000;dest=D/f'ARCO_SOURCE_{zindex}_VARIABLE_{i}.nc';dest.write_bytes(z.read(item));members.append({'container':container.name,'member':item.filename,'bytes':item.file_size,'file':dest.name,'sha256':sha(dest)});parts.append(xr.open_dataset(dest))
  point=xr.merge(parts,join='exact');assert point.sizes['latitude']==point.sizes['longitude']==2;assert set(np.round(point.latitude.values,1))=={46.6,46.7} and set(np.round(point.longitude.values,1))=={10.2,10.3};points.append(point.assign_coords(latitude=np.round(point.latitude.values,1),longitude=np.round(point.longitude.values,1)))
 jw(D/'ARCO_NETCDF_CONTAINER_RECEIPT.json',members);ds=points[0];assert ds.sizes['latitude']==ds.sizes['longitude']==2
else:ds=xr.open_dataset(path)
print(ds,flush=True)
timekey='time' if 'time' in ds.coords else 'valid_time';times=ds[timekey].values;dates=np.array([str(x)[:10] for x in times]);assert str(times[0])[:10]<='2015-01-01' and str(times[-1])[:10]>='2021-01-01';assert len(np.unique(times))==len(times)
weights=jl(D/'ID818_OFFICIAL_GRID_WEIGHTS.json')['weights'];area=np.array([int(w['intersection_area_m2']) for w in weights],float);area/=sum(area)
def weighted(data,var):
 parts=[]
 for w,aw in zip(weights,area):
  cell=data[var].sel(latitude=round(w['lat_centroid'],1),longitude=round(w['lon_centroid'],1),method='nearest');assert abs(float(cell.latitude)-round(w['lat_centroid'],1))<1e-5 and abs(float(cell.longitude)-round(w['lon_centroid'],1))<1e-5;parts.append(cell*aw)
 return sum(parts)
assert ds.t2m.attrs['units']=='K' and ds.tp.attrs['units']=='m';T=weighted(ds,'t2m').values.astype(float)-273.15;Pinc=weighted(ds,'tp').values.astype(float)*1000;assert np.isfinite(T).all() and np.isfinite(Pinc).all()
# Before old-LamaH parity, independently validate official ARCO deaccumulation against original hourly product.
orig=xr.open_dataset(D/'ERA5L_LEGACY_2015_01_02.nc');otimes=orig.valid_time.values;op=weighted(orig,'tp').values.astype(float);ot=weighted(orig,'t2m').values.astype(float)-273.15;hour=np.array([int(str(x)[11:13]) for x in otimes]);od=op-np.r_[np.nan,op[:-1]];od[hour==1]=op[hour==1];od*=1000;lookup={str(t):i for i,t in enumerate(times)};td=[];pd=[]
for i,t in enumerate(otimes):
 if str(t) not in lookup or not np.isfinite(od[i]):continue
 j=lookup[str(t)];td.append(abs(T[j]-ot[i]));pd.append(abs(Pinc[j]-od[i]))
raw_check={'matched_hours':len(td),'max_hourly_T_difference_C':float(max(td)),'max_hourly_deaccum_P_difference_mm':float(max(pd)),'tolerance_T_C':.0001,'tolerance_P_mm':.0001};raw_check['pass']=bool(max(td)<=.0001 and max(pd)<=.0001);jw(D/'ARCO_ORIGINAL_HOURLY_EQUIVALENCE.json',raw_check);assert raw_check['pass'],'ARCO_RAW_HOURLY_NOT_EQUIVALENT'
Th=np.round(T,1);Ph=np.round(Pinc,2);pdates=np.array([str(np.datetime64(t,'h')-np.timedelta64(1,'h'))[:10] for t in times]);daily=[]
for date in sorted(set(dates)|set(pdates)):
 if not '2015-01-01'<=date<='2020-12-31':continue
 tv=Th[dates==date];pv=Ph[pdates==date]
 if len(tv)!=24 or len(pv)!=24:raise ValueError('INCOMPLETE_OR_DUPLICATE_HOURS:'+date)
 # Reproduce only the documented 2019 terminal padding in the original published overlap.
 if date=='2019-12-31':pv=pv.copy();pv[-1]=pv[-2]
 daily.append({'date':date,'gauge_id':818,'P':float(np.round(sum(pv),2)),'T':float(np.round(np.mean(tv),1))})
assert len(daily)==2192
oldpath=Path(jl(P4/'source/SNAPSHOT.json')['source_paths']['818']['MET']);old={f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}-{int(r["DD"]):02d}':r for r in readcsv(oldpath,';')};comparison=[];monthly=[]
for month in sorted({r['date'][:7] for r in daily}):
 rr=[r for r in daily if r['date'].startswith(month)];nd=calendar.monthrange(int(month[:4]),int(month[5:]))[1];assert len(rr)==nd;np_=sum(r['P'] for r in rr);nt=sum(r['T'] for r in rr)/nd;monthly.append({'gauge_id':818,'date':month,'P':np_,'T':nt})
 if month>'2019-12':continue
 op=sum(float(old[r['date']]['prec']) for r in rr);ot=sum(float(old[r['date']]['2m_temp_mean']) for r in rr)/nd;pe=np_-op;te=nt-ot;relative=abs(pe)/op if op>0 else None;ok=abs(pe)<=.18 and abs(te)<=.052 and (op<36 or relative<=.005);comparison.append({'date':month,'P_original_mm':op,'P_legacy_mm':np_,'P_signed_error_mm':pe,'P_absolute_error_mm':abs(pe),'P_relative_error':relative,'T_original_C':ot,'T_legacy_C':nt,'T_absolute_error_C':abs(te),'pass':ok})
assert len(comparison)==60;cw(D/'ARCO_LEGACY_60_MONTH_PARITY.csv',comparison);jw(D/'ARCO_LEGACY_MONTHLY_MET_2015_2020.json',monthly)
result={'months_compared':60,'months_passed':sum(r['pass'] for r in comparison),'max_monthly_P_error_mm':max(r['P_absolute_error_mm'] for r in comparison),'max_monthly_T_error_C':max(r['T_absolute_error_C'] for r in comparison),'mean_P_signed_error_mm':float(np.mean([r['P_signed_error_mm'] for r in comparison])),'original_hourly_equivalence':raw_check,'same_processing_2020_admitted':all(r['pass'] for r in comparison),'original_weight_integer_truncation':True,'original_hourly_rounding_then_daily_rounding':True,'original_2019_terminal_padding_reproduced':True,'2020_no_synthetic_boundary':True,'CDS_ARCO_file_hash':sha(path),'legacy_contract_hash':sha(D/'ORIGINAL_LEGACY_IMPLEMENTATION_FROZEN.json'),'ARCO_route_hash':sha(D/'ARCO_GRID_EXTRACTION_FROZEN.json'),'original_lamah_daily_hash':sha(oldpath),'Q2020_read':False,'note':'full-upstream4cells; ARCO raw equivalent then original code transform; no bias correction or threshold relaxation'};jw(D/'ARCO_LEGACY_PARITY_RESULT.json',result);print(json.dumps(result,indent=2))
