from common import *
import numpy as np,pyogrio,shapely
attrs=pyogrio.read_dataframe(GLOBAL,columns=['HYRIV_ID','ORD_CLAS','ORD_STRA','LENGTH_KM'],read_geometry=False)
rows=[]
for field in ['ORD_CLAS','ORD_STRA']:
    for val,d in attrs.groupby(field,dropna=False):rows.append(dict(order_scheme=field,order_value=int(val) if pd.notna(val) else None,source_reach_count=len(d),source_LENGTH_KM_sum=float(d.LENGTH_KM.sum()),length_basis='GLOBAL_SOURCE_ATTRIBUTE_NOT_P9A_DOMESTIC_GEOMETRY',missing_values=int(attrs[field].isna().sum())))
csv(ROOT/'P9A_GLOBAL_SOURCE_ORDER_AUDIT.csv',rows)
del attrs
n=pyogrio.read_dataframe(GPKG,layer='national_reaches')
ids=set(n.HYRIV_ID);n['parts_inside_country']=shapely.get_num_geometries(n.geometry.to_numpy());n['local_link_status']=['SOURCE_TERMINAL_ENDORHEIC' if r.NEXT_DOWN==0 and r.ENDORHEIC else 'SOURCE_TERMINAL_OTHER' if r.NEXT_DOWN==0 else 'LOCAL_ID_PRESENT' if r.NEXT_DOWN in ids else 'OUTSIDE_DOMESTIC_ID_SET_GLOBAL_REFERENCE_EXISTS' for r in n.itertuples()]
csv(ROOT/'P9A_TOPOLOGY_BOUNDARY_AUDIT.csv',n[['HYRIV_ID','NEXT_DOWN','MAIN_RIV','ENDORHEIC','ORD_CLAS','ORD_STRA','parts_inside_country','local_link_status']])
f=pyogrio.read_dataframe(GPKG,layer='basin_fragments',read_geometry=False)
js(ROOT/'evidence/BOUNDARY_TOPOLOGY_COUNTS.json',dict(local_link_status_counts=n.local_link_status.value_counts().astype(int).to_dict(),domestic_clipped_multipart_reaches=int((n.parts_inside_country>1).sum()),fragment_rows=len(f),fragment_unique_ids=bool(f.fragment_id.is_unique),fragment_repeated_source_ID_rows=int(f.HYRIV_ID.duplicated().sum()),source_reaches_crossing_two_or_more_assigned_basins=int((f[f.basin_id>0].groupby('HYRIV_ID').basin_id.nunique()>1).sum()),source_reaches_crossing_two_or_more_assignment_ids_including_unassigned=int((f.groupby('HYRIV_ID').basin_id.nunique()>1).sum()),ENDORHEIC_counts=n.ENDORHEIC.value_counts().astype(int).to_dict(),bifurcation_certification='NOT_AVAILABLE_SCALAR_SOURCE_NEXT_DOWN',country_basis='P8 sovereign-country union with Baykonur; no boundary recomputation'))
# Resolve within-reach direction using computed upstream offsets, not ID equality alone.
gauges=pd.read_csv(ROOT/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str})
c=pd.read_csv(ROOT/'data/CANDIDATE_CHAIN_METRICS.csv');conn=pd.read_csv(ROOT/'data/CANDIDATE_GAUGE_CONNECTIVITY.csv',keep_default_na=False)
conn['same_reach_gauge_present']=conn.same_reach_direction_not_resolved
conn['within_reach_direction_method']='NOT_NEEDED'
resolved=0
for ix,r in conn[conn.same_reach_direction_not_resolved].iterrows():
    target=c[c.station_id==r.station_id].iloc[0];same=gauges[gauges.HYRIV_ID==target.HYRIV_ID]
    up=set(filter(None,str(r.upstream_gauge_codes).split('|')));dn=set(filter(None,str(r.downstream_gauge_codes).split('|')));unresolved=False
    for g in same.itertuples():
        up.discard(g.station_id);dn.discard(g.station_id)
        if g.within_reach_offset_km<target.within_reach_offset_km-1e-6:up.add(g.station_id)
        elif g.within_reach_offset_km>target.within_reach_offset_km+1e-6:dn.add(g.station_id)
        else:unresolved=True
    conn.loc[ix,'upstream_gauge_codes']='|'.join(sorted(up));conn.loc[ix,'downstream_gauge_codes']='|'.join(sorted(dn));conn.loc[ix,'has_directed_gauge_connection']=bool(up or dn);conn.loc[ix,'same_reach_direction_not_resolved']=unresolved;conn.loc[ix,'within_reach_direction_method']='COMPARE_SOURCE_UPSTREAM_OFFSET_KM';resolved+=int(not unresolved)
csv(ROOT/'data/CANDIDATE_GAUGE_CONNECTIVITY.csv',conn)
js(ROOT/'evidence/WITHIN_REACH_DIRECTION_CHECK.json',dict(initial_same_reach_gauge_candidates=int(conn.same_reach_gauge_present.sum()),offset_direction_resolved=resolved,remaining_ambiguous=int(conn.same_reach_direction_not_resolved.sum()),same_reach_id_alone_not_direction=True))
event('extra_source_and_topology_audit',global_order_rows=len(rows),within_reach_directions_resolved=resolved)
