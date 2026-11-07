"""Topology/static/geometry audit only; no discharge or model-output files read."""
from pathlib import Path
import json,csv,collections,math
import pyogrio
H=Path(__file__).resolve().parents[1];O=H/'open_metadata';E=H/'evidence'
def read(n,cols=None):
    with (O/n).open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f,delimiter=';')
        if cols:assert set(cols)<=set(r.fieldnames),'Missing explicit metadata schema'
        return [{k:v for k,v in x.items() if cols is None or k in cols} for x in r]
def write(n,rows):
    assert rows,'No fake empty inventory'
    with (H/n).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
g=read('D_gauges/1_attributes/Gauge_attributes.csv',['ID','govnr','name','river','area_gov','elev','lon','lat','country','fedstate','region','obsbeg_day','obsend','area_ratio','nrs_euhyd','nrs_rivat','typimpact','diur_art','diur_glac','degimpact'])
gauges={int(r['ID']):r for r in g};assert len(gauges)==len(g)
hh=read('B_basins_intermediate_all/1_attributes/Gauge_hierarchy.csv');hier={int(r['ID']):r for r in hh};ids=set(hier)
a={int(r['ID']):r for r in read('A_basins_total_upstrm/1_attributes/Catchment_attributes.csv')}
b={int(r['ID']):r for r in read('B_basins_intermediate_all/1_attributes/Catchment_attributes.csv')}
assert ids==set(a)==set(b) and ids<=set(gauges)
nd={i:int(r['NEXTDOWNID']) for i,r in hier.items()};up={i:[] for i in ids};edges=[];outside=[]
for u,v in nd.items():
    if v in ids:up[v].append(u);edges.append((u,v))
    elif v not in (0,-999):outside.append((u,v))
state={};cycles=[]
def visit(u):
    if state.get(u)==1:cycles.append(u);return
    if state.get(u)==2:return
    state[u]=1
    if nd[u] in ids:visit(nd[u])
    state[u]=2
for i in ids:visit(i)
assert not cycles,'Directed gauge graph contains a cycle: STOP'
def ints(v):return [int(x.strip()) for x in str(v).split(',') if x.strip() and int(x.strip())>0]
reciprocal=[i for i in ids if sorted(ints(hier[i]['NEXTUPID']))!=sorted(up[i])]
river=pyogrio.read_dataframe(O/'E_stream_network/RiverATLAS.shp',columns=['HYRIV_ID','NEXT_DOWN','MAIN_RIV','LENGTH_KM','UPLAND_SKM'],read_geometry=False)
rv={int(r.HYRIV_ID):dict(next=int(r.NEXT_DOWN),root=int(r.MAIN_RIV),length=float(r.LENGTH_KM)) for r in river.itertuples(index=False)}
def rid(i):
    v=ints(gauges[i]['nrs_rivat']);return v[0] if len(v)==1 and v[0] in rv else None
def trace(u,v):
    start,end=rid(u),rid(v)
    if start is None or end is None:return 'NOT_TESTABLE',[]
    if start==end:return 'NOT_TESTABLE_SAME_REACH',[]
    p=[];seen=set();x=start
    while x in rv and x not in seen and x!=end:
        seen.add(x);p.append(x);x=rv[x]['next']
    return ('PASS' if x==end else 'NOT_TESTABLE_BOUNDARY' if x not in rv else 'FAIL'),p
geoa=pyogrio.read_dataframe(O/'A_basins_total_upstrm/3_shapefiles/Basins_A.shp',columns=['ID'])
assert str(geoa.crs)=='EPSG:3035'
geom={int(r.ID):r.geometry for r in geoa.itertuples(index=False)}
invalid=[i for i,p in geom.items() if not p.is_valid or p.is_empty];assert not invalid,'Invalid basin geometry: STOP'
groups={};component={}
for i in ids:
    seen=set();x=i
    while nd[x] in ids:
        if x in seen:raise RuntimeError('cycle')
        seen.add(x);x=nd[x]
    component[i]=x
    groups[i]=rv[rid(i)]['root'] if rid(i) else None
roots=sorted({x for x in groups.values() if x is not None});parent={x:x for x in roots}
def find(x):
    while parent[x]!=x:x=parent[x]
    return x
def union(x,y):
    x,y=find(x),find(y)
    if x!=y:parent[max(x,y)]=min(x,y)
transfers=read('B_basins_intermediate_all/1_attributes/Crossbasin_water_transfers.csv',['ID','To_ID','cross_region','estimated','model']);crossroot=[];unknowntransfer=[]
for t in transfers:
    sources=ints(t['ID']);targets=ints(t['To_ID'])
    for u in sources:
        for v in targets:
            ru,rd=groups.get(u),groups.get(v)
            if ru and rd:
                if ru!=rd:crossroot.append(dict(source=u,target=v,source_root=ru,target_root=rd))
                union(ru,rd)
            else:unknowntransfer.append(dict(source=u,target=v))
    if not targets:unknowntransfer.append(dict(source=t['ID'],target=t['To_ID']))
dist={int(r['ID']):r for r in read('B_basins_intermediate_all/1_attributes/Stream_dist.csv')}
pair=[];ab=[]
for i in sorted(ids):
    area=float(a[i]['area_calc']);inter=float(b[i]['area_calc']);summed=inter+sum(float(a[u]['area_calc']) for u in up[i]);err=(summed-area)/area
    ab.append(dict(ID=i,A_area=area,B_incremental_area=inter,sum_B_plus_direct_upstream_A=summed,relative_difference=err,status='PASS' if abs(err)<.01 and inter>0 else 'REVIEW'))
for u,v in sorted(edges):
    status,path=trace(u,v);au,av=float(a[u]['area_calc']),float(a[v]['area_calc']);govu,govv=float(gauges[u]['area_gov']),float(gauges[v]['area_gov'])
    containment=geom[u].intersection(geom[v]).area/geom[u].area
    pair.append(dict(donor_id=u,target_id=v,donor_govnr=gauges[u]['govnr'],target_govnr=gauges[v]['govnr'],directed_path=f'{u}>{v}',hops=1,donor_area_calc=au,target_area_calc=av,connected_area_ratio=au/av,donor_area_gov=govu,target_area_gov=govv,area_monotonic_calc=av>au,area_monotonic_gov=govv>govu,intermediate_area=b[v]['area_calc'],direct_upstream_count=len(up[v]),nested_geometry_fraction=containment,official_gauge_graph='PASS',RiverATLAS_path=status,river_reach_count=len(path),official_distance_km=dist.get(u,{}).get('dist_hdn',''),donor_impacts=gauges[u]['typimpact'],target_impacts=gauges[v]['typimpact'],donor_degimpact=gauges[u]['degimpact'],target_degimpact=gauges[v]['degimpact'],natural_root_donor=groups[u],natural_root_target=groups[v],operational_group=find(groups[u]) if groups[u] else '',temporal_QC_coverage='PENDING_RESTRICTED_SCAN',topology_candidate_pass=status=='PASS' and av>au and containment>=.98 and u not in reciprocal and v not in reciprocal,known_uncertainties='provider snapping not independently surveyed; operations metadata incomplete; license discrepancy; publication latency unknown',fully_admitted=False))
write('connected_candidates.csv',pair);write('evidence/area_reconstruction.csv',ab)
stations=[];membership=[]
for i in sorted(gauges):
    r=dict(gauges[i]);r.update(dict(in_A_B=i in ids,area_calc=a.get(i,{}).get('area_calc',''),HIERARCHY=hier.get(i,{}).get('HIERARCHY',''),NEXTUPID=hier.get(i,{}).get('NEXTUPID',''),NEXTDOWNID=hier.get(i,{}).get('NEXTDOWNID',''),natural_root=groups.get(i),operational_group=find(groups[i]) if groups.get(i) else '',impact_fields_use='ELIGIBILITY_ONLY_NOT_MODEL_INPUT'))
    # Explicitly whitelist static descriptors used for matching, not target-Q-derived statistics.
    r.update({k:a.get(i,{}).get(k,'') for k in ('elev_mean','slope_mean','arid_1','p_mean','p_season')});stations.append(r)
    membership.append(dict(ID=i,gauge_graph_component=component.get(i),natural_MAIN_RIV=groups.get(i),operational_transfer_group=find(groups[i]) if groups.get(i) else '',region=gauges[i]['region'],region_is_independence_unit=False,group_certification='CONDITIONAL_OPERATIONS_INCOMPLETE'))
write('station_metadata.csv',stations);write('group_membership.csv',membership)
summary=dict(gauges=len(g),A_B_basins=len(ids),directed_edges=len(edges),graph_cycles=cycles,downstream_outside_ids=outside,nextup_reciprocity_mismatches=reciprocal,graph_components=len(set(component.values())),RiverATLAS_records=len(rv),RiverATLAS_path_status=dict(collections.Counter(p['RiverATLAS_path'] for p in pair)),topology_candidates_pass=sum(p['topology_candidate_pass'] for p in pair),area_calc_monotonic=sum(p['area_monotonic_calc'] for p in pair),area_gov_monotonic=sum(p['area_monotonic_gov'] for p in pair),A_B_reconstruction_pass=sum(r['status']=='PASS' for r in ab),natural_roots=roots,natural_root_station_counts=dict(collections.Counter(groups.values())),operational_transfer_groups=len({find(x) for x in roots}),transfer_records=len(transfers),cross_root_transfers=crossroot,unknown_transfer_links=unknowntransfer,local_Asia_HydroRIVERS_comparison='NOT_TESTABLE_WRONG_GEOGRAPHIC_COVERAGE',fully_admitted_pairs=0,region_independence_assumed=False)
(E/'topology_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
