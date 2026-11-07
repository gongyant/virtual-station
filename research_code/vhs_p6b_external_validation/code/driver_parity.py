import sys,json,calendar,hashlib,csv,math
from pathlib import Path
import numpy as np,xarray as xr
from admit import R,L,P4,jl,jw,cw,sha,readcsv
sys.stdout.reconfigure(encoding='utf-8');D=R/'driver'
assert not (D/'DRIVER_PARITY_RESULT.json').exists(),'PARITY_RESULT_ALREADY_FROZEN'
criteria=jl(D/'PARITY_CRITERIA_FROZEN.json');route=jl(D/'MONTHLY_EQUIVALENCE_ROUTE_FROZEN.json');weights=jl(D/'ID818_OFFICIAL_GRID_WEIGHTS.json');p=D/'ERA5L_MONTHLY_2015_2020.nc';ds=xr.open_dataset(p)
print(ds,flush=True);print('VARIABLE_ATTRIBUTES',{k:ds[k].attrs for k in ['t2m','tp']},flush=True)
def weighted(variable):
 parts=[]
 for w in weights['weights']:
  cell=ds[variable].sel(latitude=round(w['lat_centroid'],1),longitude=round(w['lon_centroid'],1),method='nearest');assert abs(float(cell.latitude)-round(w['lat_centroid'],1))<1e-5 and abs(float(cell.longitude)-round(w['lon_centroid'],1))<1e-5;parts.append(cell*w['weight'])
 return sum(parts)
t=weighted('t2m');prec=weighted('tp');met=[]
for i,dt in enumerate(ds.valid_time.values):
 date=str(dt)[:7];y,m=map(int,date.split('-'));days=calendar.monthrange(y,m)[1];tv=float(t.values[i])-273.15;pv=float(prec.values[i])*1000*days;assert math.isfinite(tv) and math.isfinite(pv) and pv>=0;met.append({'gauge_id':818,'date':date,'P':pv,'T':tv})
assert len(met)==72 and len({x['date'] for x in met})==72
snap=jl(P4/'source/SNAPSHOT.json');old=Path(snap['source_paths']['818']['MET']);assert sha(old)==snap['source_files'][str(old)];daily={}
for r in readcsv(old,';'):
 dt=f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}'
 if '2015-01'<=dt<='2019-12':daily.setdefault(dt,[]).append(r)
comparison=[]
for m in met:
 if m['date']>'2019-12':continue
 rr=daily[m['date']];nd=calendar.monthrange(int(m['date'][:4]),int(m['date'][5:]))[1];assert len(rr)==nd;op=sum(float(r['prec']) for r in rr);ot=sum(float(r['2m_temp_mean']) for r in rr)/nd;pe=m['P']-op;te=m['T']-ot;rel=abs(pe)/op if op>0 else None;ok=abs(pe)<=.18 and abs(te)<=.052 and (op<36 or rel<=.005)
 comparison.append({'date':m['date'],'P_original_mm':op,'P_new_mm':m['P'],'P_signed_error_mm':pe,'P_absolute_error_mm':abs(pe),'P_relative_error':rel,'T_original_C':ot,'T_new_C':m['T'],'T_signed_error_C':te,'T_absolute_error_C':abs(te),'pass':ok})
assert len(comparison)==60;cw(D/'P6B_ERA5_OVERLAP_MONTHLY_PARITY.csv',comparison);jw(D/'ID818_NEW_MONTHLY_MET_2015_2020.json',met)
# Independent within-source daily/monthly consistency for 2020 accumulated tp; 00UTC is prior day.
d20=xr.open_dataset(D/'ERA5L_2020_total_precipitation.nc');d21=xr.open_dataset(D/'ERA5L_2021.nc');daily_values={}
for source in [d20,d21]:
 v=sum(source.tp.sel(latitude=round(w['lat_centroid'],1),longitude=round(w['lon_centroid'],1),method='nearest')*w['weight'] for w in weights['weights'])
 for dt,val in zip(source.valid_time.values,v.values):
  date=str(np.datetime64(dt,'D')-np.timedelta64(1,'D'))
  if date.startswith('2020-'):daily_values[date]=float(val)*1000
assert len(daily_values)==366
internal=[]
for m in [x for x in met if x['date'].startswith('2020-')]:
 vv=[v for dt,v in daily_values.items() if dt.startswith(m['date'])];assert len(vv)==calendar.monthrange(2020,int(m['date'][5:]))[1];internal.append({'date':m['date'],'P_daily_UTC_sum':sum(vv),'P_monthly_product':m['P'],'absolute_error_mm':abs(sum(vv)-m['P'])})
cw(D/'P6B_2020_TP_INTERNAL_CHECK.csv',internal)
result={'criteria_hash':sha(D/'PARITY_CRITERIA_FROZEN.json'),'equivalence_route_hash':sha(D/'MONTHLY_EQUIVALENCE_ROUTE_FROZEN.json'),'new_dataset_hash':sha(p),'original_daily_hash':sha(old),'geometry_weights_hash':sha(D/'ID818_OFFICIAL_GRID_WEIGHTS.json'),'overlap_months':60,'months_passed':sum(r['pass'] for r in comparison),'max_P_absolute_error_mm':max(r['P_absolute_error_mm'] for r in comparison),'mean_P_signed_error_mm':float(np.mean([r['P_signed_error_mm'] for r in comparison])),'max_P_relative_error':max(r['P_relative_error'] for r in comparison if r['P_relative_error'] is not None),'max_T_absolute_error_C':max(r['T_absolute_error_C'] for r in comparison),'mean_T_signed_error_C':float(np.mean([r['T_signed_error_C'] for r in comparison])),'2020_full_met_months':12,'2020_daily_TP_days':366,'max_2020_P_daily_monthly_discrepancy_mm':max(r['absolute_error_mm'] for r in internal),'strict_same_processing_extension_admitted':all(r['pass'] for r in comparison),'processing_difference':'official monthly product then full basin area weighting vs published daily rounded LamaH values. No bias correction. ECMWF2020MIR change retained.','test_Q2020_read':False}
jw(D/'DRIVER_PARITY_RESULT.json',result);print(json.dumps(result,indent=2))
