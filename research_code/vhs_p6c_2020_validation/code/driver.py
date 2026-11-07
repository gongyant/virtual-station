"""P6B frozen full-upstream hourly -> daily -> monthly method; never reads Q."""
from p6c_common import *
import zipfile,xarray as xr
sys.stdout.reconfigure(encoding='utf-8')
mode=sys.argv[1];protocol=jl(R/'P6C_FROZEN_PROTOCOL.json');weights=jl(R/'driver/ALL_BASIN_GRID_WEIGHTS_FROZEN.json');tiles=jl(R/'driver/DOWNLOAD_TILES_FROZEN.json');ids=[2] if mode=='station2' else protocol['representatives'] if mode=='representatives' else protocol['gauge_ids']
need={w['grid_id'] for g in ids for w in weights[str(g)]['weights']};data={};times=None;receipts=[]
for tile in tiles:
 if not need.intersection(c['grid_id'] for c in tile['required_cells']):continue
 t=tile['tile_id'];path=R/'driver'/f'{t}_ARCO_2015_2020.zip';receipt=R/'driver'/f'{t}_DOWNLOAD.json'
 if not receipt.exists() or not jl(receipt).get('completed'):print('WAITING_TILE',t);sys.exit(2)
 assert sha(path)==jl(receipt)['sha256'];parts=[]
 if zipfile.is_zipfile(path):
  with zipfile.ZipFile(path) as z:
   for i,n in enumerate(z.infolist()):
    if n.is_dir():continue
    assert n.file_size<1_000_000_000;dest=R/'driver'/f'{t}_VARIABLE_{i}.nc'
    if not dest.exists():dest.write_bytes(z.read(n))
    parts.append(xr.open_dataset(dest));receipts.append({'tile':t,'member':n.filename,'member_file':dest.name,'sha256':sha(dest),'bytes':n.file_size})
  ds=xr.merge(parts,join='exact')
 else:ds=xr.open_dataset(path);parts=[ds]
 key='time' if 'time' in ds.coords else 'valid_time';tt=ds[key].values.astype('datetime64[h]')
 if times is None:times=tt
 else:assert np.array_equal(times,tt),'TILE_TIME_MISMATCH'
 assert len(np.unique(tt))==len(tt) and np.all(np.diff(tt)==np.timedelta64(1,'h'))
 assert ds.t2m.attrs['units']=='K' and ds.tp.attrs['units']=='m'
 for c in tile['required_cells']:
  if c['grid_id'] not in need:continue
  x=ds.sel(latitude=c['lat'],longitude=c['lon'],method='nearest');assert abs(float(x.latitude)-c['lat'])<1e-5 and abs(float(x.longitude)-c['lon'])<1e-5
  data[c['grid_id']]=(x.t2m.values.copy(),x.tp.values.copy())
 for p in parts:p.close()
assert need==set(data);assert times[0]<=np.datetime64('2015-01-01T00') and times[-1]>=np.datetime64('2021-01-01T00')
Tday=times.astype('datetime64[D]');Pday=(times-np.timedelta64(1,'h')).astype('datetime64[D]');days=np.arange(np.datetime64('2015-01-01'),np.datetime64('2021-01-01'));ti=np.where((Tday>=days[0])&(Tday<=days[-1]))[0];pi=np.where((Pday>=days[0])&(Pday<=days[-1]))[0]
assert len(ti)==len(pi)==2192*24;assert np.array_equal(Tday[ti].reshape(-1,24)[:,0],days) and np.array_equal(Pday[pi].reshape(-1,24)[:,0],days)
snap=jl(P4/'source/SNAPSHOT.json');comparison=[];monthly=[];status=[]
for g in ids:
 ww=weights[str(g)]['weights'];tw=sum(data[w['grid_id']][0]*w['weight'] for w in ww).astype(float)-273.15;pw=sum(data[w['grid_id']][1]*w['weight'] for w in ww).astype(float)*1000
 assert np.isfinite(tw).all() and np.isfinite(pw).all();assert pw.min()>-.0001,'NEGATIVE_INCREMENT_NOT_ALLOWED'
 th=np.round(tw,1);ph=np.round(pw,2);tm=th[ti].reshape(-1,24);pm=ph[pi].reshape(-1,24).copy();pad=np.where(days==np.datetime64('2019-12-31'))[0][0];pm[pad,-1]=pm[pad,-2]
 td=np.round(np.mean(tm,axis=1),1);pd=np.round(np.sum(pm,axis=1),2);oldpath=Path(snap['source_paths'][str(g)]['MET']);assert sha(oldpath)==snap['source_files'][str(oldpath)]
 old={f'{int(r["YYYY"]):04d}-{int(r["MM"]):02d}-{int(r["DD"]):02d}':r for r in readcsv(oldpath,';')};sm=days.astype('datetime64[M]');local=[]
 for mo in np.unique(sm):
  dt=str(mo);mask=sm==mo;nd=calendar.monthrange(int(dt[:4]),int(dt[5:]))[1];assert mask.sum()==nd;pn=float(pd[mask].sum());tn=float(td[mask].mean());monthly.append({'gauge_id':g,'date':dt,'P':pn,'T':tn,'complete_days':nd})
  if dt>'2019-12':continue
  rr=[old[str(d)] for d in days[mask]];op=sum(float(r['prec']) for r in rr);ot=sum(float(r['2m_temp_mean']) for r in rr)/nd;pe=abs(pn-op);te=abs(tn-ot);rel=pe/op if op>0 else None;ok=pe<=.18 and te<=.052 and (op<36 or rel<=.005)
  local.append({'gauge_id':g,'date':dt,'P_original_mm':op,'P_reproduced_mm':pn,'P_absolute_error_mm':pe,'P_relative_error':rel,'T_original_C':ot,'T_reproduced_C':tn,'T_absolute_error_C':te,'pass':ok})
 assert len(local)==60;comparison+=local;status.append({'gauge_id':g,'months':60,'pass_months':sum(r['pass'] for r in local),'max_P_abs_mm':max(r['P_absolute_error_mm'] for r in local),'max_T_abs_C':max(r['T_absolute_error_C'] for r in local),'driver_admitted':all(r['pass'] for r in local),'source_met_hash':sha(oldpath),'cells':len(ww)})
 print('PARITY',status[-1],flush=True)
tag='SMOKE_ID2' if mode=='station2' else 'REPRESENTATIVES' if mode=='representatives' else 'ALL24';cw(R/'driver'/f'{tag}_HISTORICAL_PARITY.csv',comparison);jw(R/'driver'/f'{tag}_PARITY_RESULT.json',status);jw(R/'driver'/f'{tag}_MONTHLY_MET_2015_2020.json',monthly);jw(R/'driver'/f'{tag}_NETCDF_MEMBERS.json',receipts)
event('DRIVER_PARITY',cohort=tag,stations=len(ids),pass_stations=sum(r['driver_admitted'] for r in status),months=len(comparison),fit_calls=0,Q_read=False)
if not all(r['driver_admitted'] for r in status):sys.exit(3)

