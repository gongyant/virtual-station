"""VHS-NEXT-S0 read-only artifact checks. Does not fit or run real-data models."""
import hashlib, json, re, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import xlrd
import xarray as xr
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research_next/vhs_transfer/data_audit'
sys.stdout.reconfigure(encoding='utf-8')
facts={}
used={}
def use(rel):
    p=ROOT/rel
    if not p.is_file(): raise FileNotFoundError(p)
    used[rel]={'absolute_path':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    return p
def summary(df,date,station,values):
    result=[]
    for sid,g in df.groupby(station):
        dates=pd.to_datetime(g[date]).sort_values()
        result.append({'station':str(sid),'rows':len(g),'start':str(dates.min().date()),'end':str(dates.max().date()),'duplicate_dates':int(dates.duplicated().sum()),'missing_calendar_days':len(pd.date_range(dates.min(),dates.max()).difference(dates)), 'missing':{v:int(g[v].isna().sum()) for v in values}})
    return result
raw=pd.read_excel(use('data/raw/runoff/BYBLK-DSK日数据.xlsx'),sheet_name=0)
facts['daily_raw_columns']=list(raw.columns)
raw['date']=pd.to_datetime(raw['Q'])
facts['daily_raw_nondata_rows']=raw.loc[raw.date.isna()].astype(str).to_dict('records')
raw=raw.loc[raw.date.notna()].copy()
ts=pd.read_csv(use('data/processed/timeseries.csv'),dtype={'station_id':str},parse_dates=['date'])
facts['daily_processed_coverage']=summary(ts,'date','station_id',['obs_q'])
facts['daily_raw_to_processed']={}
for code,sid in [('BYBLK','00705600'),('DSK','00705700')]:
    cmp=raw[['date',code]].merge(ts[ts.station_id.eq(sid)][['date','obs_q']],on='date',how='outer',validate='one_to_one')
    facts['daily_raw_to_processed'][code]={'rows':len(cmp),'max_abs_diff':float((cmp[code]-cmp.obs_q).abs().max()),'missing_pairs':int(cmp[[code,'obs_q']].isna().any(axis=1).sum())}
ds=pd.read_csv(use('outputs/vhs_bd1m/bd1m_model_dataset_audit.csv'),parse_dates=['date'])
facts['bd1m_dataset']={'rows':len(ds),'split_counts':ds.split_candidate.value_counts().to_dict(),'missing':ds.isna().sum().to_dict(),'duplicate_dates':int(ds.date.duplicated().sum())}
facts['bd1m_mapping']={}
for code,field in [('BYBLK','Q_input_byblk'),('DSK','Q_target_dsk')]:
    c=raw[['date',code]].merge(ds[['date',field]],on='date',validate='one_to_one')
    facts['bd1m_mapping'][field]=float((c[code]-c[field]).abs().max())
z=np.load(use('data/processed/real_bundle.npz'),allow_pickle=False)
names=list(z['feature_names'].astype(str)); stations=list(z['station_ids'].astype(str)); oi=names.index('obs_q')
facts['base_bundle']={'stations':stations,'features':names,'x_shape':list(z['x'].shape),'edge_index':z['edge_index'].tolist()}
for code,sid in [('BYBLK','00705600'),('DSK','00705700')]:
    j=stations.index(sid); ref=raw.set_index('date')[code].reindex(pd.to_datetime(z['dates'])).to_numpy(np.float32)
    facts['base_bundle'][code]={'x_exact_float32':bool(np.array_equal(ref,z['x'][:,j,oi],equal_nan=True)), 'y_exact_float32':bool(np.array_equal(ref,z['y'][:,j],equal_nan=True))}
multi=pd.read_csv(use('data/processed/virtual_station_multisite/multisite_discharge_2005.csv'),dtype={'station_id':str},parse_dates=['date'])
facts['multi_coverage']=summary(multi,'date','station_code',['observed_q_m3s','physical_reference_q_m3s'])
book=xlrd.open_workbook(str(use('data/raw/runoff/Q-新疆.xls')))
facts['mq_import_checks']=[]
for code,sheetidx,refcol,obscol in [('BYBLK',9,3,4),('DSK',9,1,2),('ALAR',11,1,4),('XQM',11,2,5),('AQK',11,3,6)]:
    sh=book.sheet_by_index(sheetidx); g=multi[multi.station_code.eq(code)]
    diffs={'observed_q_m3s':[],'physical_reference_q_m3s':[]}
    dates_ok=True
    for _,r in g.iterrows():
        row=int(r.source_row)-1
        dates_ok &= pd.Timestamp(*xlrd.xldate_as_tuple(sh.cell_value(row,0),book.datemode)[:6]).normalize()==r.date
        for field,col in [('observed_q_m3s',obscol),('physical_reference_q_m3s',refcol)]:
            a=sh.cell_value(row,col); a=float(a) if isinstance(a,(int,float)) else np.nan
            b=float(r[field]); diffs[field].append(0.0 if np.isnan(a) and np.isnan(b) else abs(a-b))
    facts['mq_import_checks'].append({'station':code,'sheet':sh.name,'headers':sh.row_values(0),'date_match':bool(dates_ok),'max_abs_diffs':{k:float(np.nanmax(v)) for k,v in diffs.items()}})
mz=np.load(use('data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz'),allow_pickle=False)
facts['multi_bundle']={'stations':mz['station_ids'].astype(str).tolist(),'features':mz['feature_names'].astype(str).tolist(),'edge_index':mz['edge_index'].tolist(),'edge_attr':mz['edge_attr'].tolist(),'x_shape':list(mz['x'].shape)}
facts['mq_tensor_checks']=[]
for j,sid in enumerate(mz['station_ids'].astype(str)):
    g=multi[multi.station_id.eq(sid)].set_index('date').reindex(pd.to_datetime(mz['dates']))
    facts['mq_tensor_checks'].append({'station':sid,'reference_exact_float32':bool(np.array_equal(g.physical_reference_q_m3s.to_numpy(np.float32),mz['x'][:,j,1],equal_nan=True)),'label_exact_float32':bool(np.array_equal(g.observed_q_m3s.to_numpy(np.float32),mz['y'][:,j],equal_nan=True))})
def topology(rel,source,target,node_rel,node_id):
    e=pd.read_csv(use(rel),dtype=str); n=pd.read_csv(use(node_rel),dtype=str)
    ids=set(n[node_id]); adjacency={v:set() for v in ids}
    for a,b in zip(e[source],e[target]): adjacency[a].add(b); adjacency[b].add(a)
    seen=set(); components=[]
    for v in sorted(ids):
        if v in seen: continue
        stack=[v]; comp=[]
        while stack:
            a=stack.pop()
            if a in seen: continue
            seen.add(a); comp.append(a); stack+=list(adjacency[a]-seen)
        components.append(comp)
    return {'nodes':len(n),'edges':len(e),'weak_components':components,'edge_records':e.to_dict('records'),'node_columns':n.columns.tolist()}
facts['multi_topology']=topology('data/processed/virtual_station_multisite/multisite_edges_2005.csv','source','target','data/processed/virtual_station_multisite/multisite_stations_2005.csv','station_id')
facts['reach_topology']=topology('outputs/vhs_bd1m/bd1m_reach_graph_edges.csv','source_reach_id','target_reach_id','outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv','reach_id')
n=pd.read_csv(ROOT/'outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv',dtype={'reach_id':str})
e=pd.read_csv(ROOT/'outputs/vhs_bd1m/bd1m_reach_graph_edges.csv',dtype={'source_reach_id':str,'target_reach_id':str})
order=n.sort_values('reach_order'); ee=e.sort_values('source_order')
facts['reach_topology']['sequential_edges_match']=bool(ee.source_reach_id.tolist()==order.reach_id.tolist()[:-1] and ee.target_reach_id.tolist()==order.reach_id.tolist()[1:])
facts['reach_topology']['length_km_sum']=float(n.length_km.sum())
facts['reach_topology']['endpoints']=order.iloc[[0,-1]].to_dict('records')
# Check actual HydroRIVERS DBF downstream pointers, rather than a stored PASS flag.
try:
    import shapefile
    dbf=use('data/raw/hydrorivers/HydroRIVERS_v10_as.dbf')
    reader=shapefile.Reader(dbf=str(dbf)); fields=[f[0] for f in reader.fields[1:]]
    wanted=set(map(int,n.reach_id)); matches={}
    for rec in reader.iterRecords():
        d=dict(zip(fields,rec)); rid=int(d['HYRIV_ID'])
        if rid in wanted: matches[rid]=d
    bad=[]
    for a,b in zip(order.reach_id.tolist()[:-1],order.reach_id.tolist()[1:]):
        if int(matches[int(a)]['NEXT_DOWN'])!=int(b): bad.append([a,b,matches[int(a)]['NEXT_DOWN']])
    facts['raw_hydrorivers_check']={'matched_reaches':len(matches),'bad_next_down':bad,'raw_length_km':sum(float(matches[k]['LENGTH_KM']) for k in wanted)}
except ImportError:
    # Minimal read-only dBASE III numeric-field parser; avoids installing packages.
    import struct
    dbf=use('data/raw/hydrorivers/HydroRIVERS_v10_as.dbf')
    data=dbf.read_bytes(); count=struct.unpack_from('<I',data,4)[0]; start=struct.unpack_from('<H',data,8)[0]; size=struct.unpack_from('<H',data,10)[0]
    fields={};offset=1
    for pos in range(32,start-1,32):
        if data[pos]==13:break
        name=data[pos:pos+11].split(b'\x00')[0].decode('ascii'); width=data[pos+16]
        fields[name]=(offset,width);offset+=width
    wanted=set(map(int,n.reach_id));matches={}
    for i in range(count):
        base=start+i*size
        off,width=fields['HYRIV_ID'];rid=int(data[base+off:base+off+width])
        if rid in wanted:
            row={}
            for name in ['HYRIV_ID','NEXT_DOWN','LENGTH_KM']:
                off,width=fields[name];row[name]=float(data[base+off:base+off+width])
            matches[rid]=row
    bad=[]
    for a,b in zip(order.reach_id.tolist()[:-1],order.reach_id.tolist()[1:]):
        if int(matches[int(a)]['NEXT_DOWN'])!=int(b):bad.append([a,b,matches[int(a)]['NEXT_DOWN']])
    facts['raw_hydrorivers_check']={'reader':'stdlib dBASE numeric fields','matched_reaches':len(matches),'bad_next_down':bad,'raw_length_km':sum(matches[k]['LENGTH_KM'] for k in wanted),'last_included_next_down':int(matches[int(order.reach_id.iloc[-1])]['NEXT_DOWN'])}
facts['netcdf_metadata']={}
for rel in ['data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc','data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc']:
    with xr.open_dataset(use(rel)) as nc:
        facts['netcdf_metadata'][rel]={'attrs':dict(nc.attrs),'sizes':dict(nc.sizes),'time_start':str(nc.time.values[0]),'time_end':str(nc.time.values[-1]),'variables':{v:{'attrs':dict(nc[v].attrs),'nonfinite':int((~np.isfinite(nc[v].values)).sum())} for v in nc.data_vars if np.issubdtype(nc[v].dtype,np.number)}}
# Reproduce only deterministic t-1 rolling features, never any fitted predictions.
inc=pd.read_csv(use('outputs/vhs_bd1m/experiments/e4b0_incremental_forcing_features.csv'),parse_dates=['date'])
facts['incremental_feature_columns']=inc.columns.tolist()
with xr.open_dataset(ROOT/'data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc') as nc:
    p=pd.Series(nc.precipitation_mm.values.reshape(-1),index=pd.to_datetime(nc.time.values)).shift(1)
    t=pd.Series(nc.temperature_c.values.reshape(-1),index=pd.to_datetime(nc.time.values)).shift(1)
    checks={}
    for name,w,kind in [('P_inc_3d',3,'p'),('P_inc_7d',7,'p'),('P_inc_30d',30,'p'),('T_inc_7d',7,'t'),('T_inc_30d',30,'t')]:
        ref=(p.rolling(w,min_periods=w).sum() if kind=='p' else t.rolling(w,min_periods=w).mean()).reindex(inc.date).to_numpy()
        actual=inc[name].to_numpy(float)
        checks[name]={'max_abs_diff':float(np.nanmax(abs(ref-actual))),'missing_mask_equal':bool(np.array_equal(np.isnan(ref),np.isnan(actual)))}
    facts['incremental_tminus1_checks']=checks
external=use('data/raw/runoff/Q-dsk-byblk.xlsx')
with zipfile.ZipFile(external) as zz: facts['external_core_xml']=zz.read('docProps/core.xml').decode('utf-8')
facts['external_workbook']={'sheet_names':pd.ExcelFile(external).sheet_names,'DSK_head':pd.read_excel(external,sheet_name='DSK',header=None).head(4).astype(str).values.tolist()}
manifest=json.loads(use('outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json').read_text(encoding='utf-8'))
facts['e5a_manifest_check']=[]
for key,value in manifest['source_files'].items():
    rel=value['path'].replace('\\','/'); use(rel)
    facts['e5a_manifest_check'].append({'key':key,'path':rel,'sha_match':used[rel]['sha256'].lower()==value['sha256'].lower(),'bytes_match':used[rel]['bytes']==value['bytes']})
# Store exact code-line evidence for all relevant source/config/report artifacts.
selected=[]
for base in ['scripts','src/vhs','configs','outputs/vhs_bd1m','outputs/diagnosis_2005_snapshot']:
    for p in (ROOT/base).rglob('*'):
        if not p.is_file() or p.suffix not in ['.py','.md','.yaml','.json','.txt','.csv']: continue
        if '__pycache__' in p.parts or 'node_modules' in p.parts: continue
        if base=='scripts' and not re.search(r'bd1m|e4a2|multisite|stage_[bcd]|prepare_(timeseries|graph|virtual|residual)|era5|donor|calibrated|physics_safety|shared',p.name): continue
        if base=='configs' and not re.search(r'holdout|mainline|multisite|real_data',p.name): continue
        selected.append(p)
lines=[]
pattern=re.compile(r'physical_reference|MQ-DSK|obs_q|Q_target|train|validation|test|fit\(|shift\(|interpol|bfill|ffill|state|storage|provenance|source|来源|单位|leak|NEXT_DOWN|slope|width|Muskingum',re.I)
for p in selected:
    rel=p.relative_to(ROOT).as_posix(); use(rel)
    content=p.read_text(encoding='utf-8',errors='replace').splitlines()
    hits=[f'{i}: {line}' for i,line in enumerate(content,1) if pattern.search(line)]
    if hits: lines += [f'\n## {rel}\n']+hits
(OUT/'code_evidence.txt').write_text('\n'.join(lines),encoding='utf-8')
(OUT/'source_manifest.json').write_text(json.dumps(used,ensure_ascii=False,indent=2),encoding='utf-8')
def strict_json_value(value):
    if isinstance(value,dict):return {k:strict_json_value(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [strict_json_value(v) for v in value]
    if isinstance(value,(float,np.floating)) and not np.isfinite(value):return None
    return value
(OUT/'live_audit_facts.json').write_text(json.dumps(strict_json_value(facts),ensure_ascii=False,indent=2,default=str,allow_nan=False),encoding='utf-8')
print(json.dumps({'audited_files':len(used),'daily':facts['daily_processed_coverage'],'mq':facts['mq_import_checks'],'topology':{k:facts[k] for k in ['raw_hydrorivers_check']},'manifest':facts['e5a_manifest_check']},ensure_ascii=False))
