"""Literal original hourly rounding/deaccumulation on downloaded bounded overlap."""
import numpy as np,xarray as xr,calendar,json
from admit import R,L,P4,jl,jw,cw,sha,readcsv
D=R/'driver';ds=xr.open_dataset(D/'ERA5L_LEGACY_2015_01_02.nc');weights=jl(D/'ID818_OFFICIAL_GRID_WEIGHTS.json')['weights'];area=np.array([int(w['intersection_area_m2']) for w in weights],float);area/=sum(area)
def weighted(var):return sum(ds[var].sel(latitude=round(w['lat_centroid'],1),longitude=round(w['lon_centroid'],1),method='nearest')*v for w,v in zip(weights,area))
T=weighted('t2m').values.astype(float)-273.15;tp=weighted('tp').values.astype(float);times=ds.valid_time.values;hour=np.array([int(str(t)[11:13]) for t in times]);inc=tp-np.r_[np.nan,tp[:-1]];inc[hour==1]=tp[hour==1];P=np.round(inc*1000,2);Th=np.round(T,1);daily={}
for i,t in enumerate(times):
 dt=str(t)[:10];daily.setdefault(dt,{'T':[],'P':[]});daily[dt]['T'].append(float(Th[i]));pd=str(np.datetime64(t,'h')-np.timedelta64(1,'h'))[:10];daily.setdefault(pd,{'T':[],'P':[]})['P'].append(float(P[i]))
oldpath=jl(P4/'source/SNAPSHOT.json')['source_paths']['818']['MET'];old={f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}-{int(r["DD"]):02d}':r for r in readcsv(oldpath,';')};comparison=[];eligible=[]
for dt,v in sorted(daily.items()):
 if len(v['T'])!=24 or len(v['P'])!=24 or not np.isfinite(v['P']).all() or not dt.startswith('2015-'):continue
 p=float(np.round(sum(v['P']),2));t=float(np.round(np.mean(v['T']),1));eligible.append({'gauge_id':818,'date':dt,'P':p,'T':t});comparison.append({'date':dt,'P_error_mm':p-float(old[dt]['prec']),'T_error_C':t-float(old[dt]['2m_temp_mean'])})
cw(D/'ORIGINAL_HOURLY_DAILY_PARITY.csv',comparison);months=[]
for month in sorted({r['date'][:7] for r in eligible}):
 rr=[r for r in eligible if r['date'].startswith(month)];nd=calendar.monthrange(int(month[:4]),int(month[5:]))[1]
 if len(rr)!=nd:continue
 op=sum(float(old[r['date']]['prec']) for r in rr);ot=sum(float(old[r['date']]['2m_temp_mean']) for r in rr)/nd;np_=sum(r['P'] for r in rr);nt=sum(r['T'] for r in rr)/nd;months.append({'date':month,'P_original':op,'P_new_legacy':np_,'P_absolute_error_mm':abs(np_-op),'T_original':ot,'T_new_legacy':nt,'T_absolute_error_C':abs(nt-ot),'pass':abs(np_-op)<=.18 and abs(nt-ot)<=.052})
cw(D/'ORIGINAL_HOURLY_MONTHLY_PARITY.csv',months);jw(D/'ORIGINAL_HOURLY_PARITY_RESULT.json',{'full_overlap_months_compared':len(months),'passed':sum(r['pass'] for r in months),'days_compared':len(comparison),'max_daily_P_error_mm':max(abs(r['P_error_mm']) for r in comparison),'max_daily_T_error_C':max(abs(r['T_error_C']) for r in comparison),'method_hash':sha(D/'ORIGINAL_LEGACY_IMPLEMENTATION_FROZEN.json'),'code_hash':sha(__file__),'no_Q2020_read':True,'all60overlap_verified':len(months)==60,'2020_scoring_allowed':False});print(months)
