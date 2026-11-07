from common import *
import numpy as np,pyogrio
checks=[]
def ck(n,v,**detail):checks.append(dict(check=n,passed=bool(v),**detail))
glob=pd.read_csv(ROOT/'P9A_GLOBAL_SOURCE_ORDER_AUDIT.csv')
for scheme in ['ORD_CLAS','ORD_STRA']:
    d=glob[glob.order_scheme==scheme];ck('global_full_source_count_'+scheme,int(d.source_reach_count.sum())==8477883);ck('global_source_no_missing_'+scheme,d.missing_values.eq(0).all())
g=pd.read_csv(ROOT/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});p=pd.read_csv(ROOT/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str})
cad=pd.read_csv(ROOT/'data/CANDIDATE_CHAIN_METRICS.csv');conn=pd.read_csv(ROOT/'data/CANDIDATE_GAUGE_CONNECTIVITY.csv',keep_default_na=False)
nodes=pd.read_csv(ROOT/'data/GLOBAL_UPSTREAM_CLOSURE.csv',usecols=['HYRIV_ID','NEXT_DOWN']);down=dict(zip(nodes.HYRIV_ID.astype(int),nodes.NEXT_DOWN.astype(int)))
gauge={r.station_id:r for r in p.itertuples()};candidate={r.station_id:r for r in cad.itertuples()};cache={}
def path(rid):
    rid=int(rid)
    if rid not in cache:
        s=set();i=rid
        while i in down and i not in s:s.add(i);i=down[i]
        cache[rid]=s
    return cache[rid]
for r in conn.itertuples():
    t=candidate[r.station_id]
    for direction,codefield in [('upstream',r.upstream_gauge_codes),('downstream',r.downstream_gauge_codes)]:
        for code in filter(None,str(codefield).split('|')):
            q=gauge[code]
            if q.HYRIV_ID==t.HYRIV_ID:
                valid=(q.within_reach_offset_km<t.within_reach_offset_km) if direction=='upstream' else (q.within_reach_offset_km>t.within_reach_offset_km)
            else:valid=(t.HYRIV_ID in path(q.HYRIV_ID)) if direction=='upstream' else (q.HYRIV_ID in path(t.HYRIV_ID))
            ck(f'directed_witness_{r.station_id}_{direction}_{code}',valid)
ck('all14_same_reach_offsets_resolved',int(conn.same_reach_gauge_present.sum())==14 and not conn.same_reach_direction_not_resolved.any())
ck('334_coordinate_axis_at_declared_precision',g.coordinate_axis_verified.all() and g.attribute_x_lat_verified.all() and g.attribute_y_lon_verified.all())
ck('two_basin_id_namespaces_kept',set(['source_basin_id','nearest_basin_id','QazSu_source_basin_research_id']).issubset(g.columns))
ck('seven_basin_mismatches_not_certified',g[g.source_basin_vs_geometric_basin_agreement!='AGREES_AFTER_NAMESPACE_CROSSWALK'].official_certification.eq('NOT_CONFIRMED').all())
for field in ['q','q_mean','Qobs','qobs','qu_mean','qd_mean']:ck('no_Q_label_column_exported_'+field,field not in g.columns)
cross=pyogrio.read_dataframe(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg',layer='qazsu_identity_audit',read_geometry=False)
ck('GIS334_station_records',len(cross)==334)
ck('GIS_identity_namespace_fields_synced','QazSu_source_basin_research_id' in cross.columns)
ck('no_missing_paper_evidence_index',pd.read_csv(ROOT/'P9A_SCI_EVIDENCE_INDEX.csv').exists.all())
qa=read(ROOT/'P9A_INDEPENDENT_QA.json');extra=dict(passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks)
js(ROOT/'evidence/ADDITIONAL_INDEPENDENT_QA.json',extra)
js(ROOT/'evidence/COMBINED_INDEPENDENT_QA.json',dict(base_passed=qa['passed'],base_failed=qa['failed'],additional_passed=extra['passed'],additional_failed=extra['failed'],passed=qa['passed']+extra['passed'],failed=qa['failed']+extra['failed'],scope='baseGIS,length,sourceanddirectedconnectivity; not business or hydrologic validation'))
event('additional_independent_QA_complete',passed=extra['passed'],failed=extra['failed'])
if extra['failed']:raise RuntimeError('Additional independent checks failed')
