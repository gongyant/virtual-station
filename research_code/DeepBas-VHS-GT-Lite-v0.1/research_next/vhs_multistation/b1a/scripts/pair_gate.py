"""Join eligibility counts and legal descriptors; no Q payload or predictive scoring."""
from pathlib import Path
import csv,json,math,calendar,collections
import pyogrio
from pyproj import Transformer
H=Path(__file__).resolve().parents[1];E=H/'evidence';O=H/'open_metadata'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    if not rows:return
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
stations=read(H/'station_metadata.csv');st={int(r['ID']):r for r in stations};pairs=read(H/'connected_candidates.csv')
cover=json.loads((E/'coverage_station_summary.json').read_text());masks=json.loads((E/'checked_date_masks.json').read_text())
snap={int(r['ID']):float(r['distance_m']) if r['distance_m'] else None for r in read(E/'station_reach_distances.csv')}
def snap_screen(i):return snap.get(i) is not None and snap[i]<=500
def joint(u,v):
    a,b=masks[str(u)],masks[str(v)];days=0;years=0
    for y in set(a)&set(b):
        n=(int(a[y],16)&int(b[y],16)).bit_count();days+=n
        if n/(366 if calendar.isleap(int(y)) else 365)>=.9:years+=1
    return years,days
nd={int(r['ID']):int(r['NEXTDOWNID']) for r in stations if r['in_A_B']=='True'}
def reachable(u,v):
    seen=set()
    while u in nd and u not in seen:
        if u==v:return True
        seen.add(u);u=nd[u]
    return False
ancestors=sum(sum(1 for v in nd if v!=u and reachable(u,v)) for u in nd)
for r in stations:
    r.update(cover[r['ID']]);r['coverage_rule']='>=10 calendar years with >=90% nonmissing ckhs=1; not model feature'
for p in pairs:
    u,v=int(p['donor_id']),int(p['target_id']);years,days=joint(u,v)
    p.update(dict(joint_years_ge90pct_checked=years,joint_checked_days=days,coverage_pass=years>=10,low_no_impact_endpoints=st[u]['degimpact'] in ('u','l') and st[v]['degimpact'] in ('u','l'),temporal_QC_coverage='RESTRICTED_DATE_QC_SCAN_COMPLETE',provisional_primary_eligible=p['topology_candidate_pass']=='True' and years>=10 and st[u]['degimpact'] in ('u','l') and st[v]['degimpact'] in ('u','l'),fully_admitted=False))
    p['coverage_lowimpact_pass']=p['provisional_primary_eligible']
    p['both_endpoint_snap_le500m']=snap_screen(u) and snap_screen(v)
    p['provisional_primary_eligible']=p['coverage_lowimpact_pass'] and p['both_endpoint_snap_le500m']
eligible=[p for p in pairs if p['provisional_primary_eligible']]
geo=pyogrio.read_dataframe(O/'A_basins_total_upstrm/3_shapefiles/Basins_A.shp',columns=['ID']);geom={int(r.ID):r.geometry for r in geo.itertuples(index=False)}
transformer=Transformer.from_crs('EPSG:3035','EPSG:4326',always_xy=True)
coordinates={i:transformer.transform(float(r['lon']),float(r['lat'])) for i,r in st.items()}
assert all(-180<=lon<=180 and -90<=lat<=90 for lon,lat in coordinates.values())
def distance(u,v):
    lon1,lat1=coordinates[u];lon2,lat2=coordinates[v];a1,a2=math.radians(lat1),math.radians(lat2);dl=math.radians(lon1-lon2);da=a1-a2
    return 6371*2*math.asin(min(1,math.sqrt(math.sin(da/2)**2+math.cos(a1)*math.cos(a2)*math.sin(dl/2)**2)))
pool=[i for i in nd if cover[str(i)]['coverage_10years_pass'] and st[i]['degimpact'] in ('u','l') and st[i]['operational_group'] and st[i]['arid_1'] not in ('','-999') and snap_screen(i)]
neighbors=[];counts=collections.Counter();paircounts=collections.Counter();raw_separate=0;overlap_reject=0;calipers=collections.Counter();metadata_support=[]
for p in eligible:
    donor,target=int(p['donor_id']),int(p['target_id']);matches=[]
    for n in pool:
        if n in (target,donor) or reachable(n,target) or reachable(target,n):continue
        if st[n]['operational_group']==st[target]['operational_group']:continue
        raw_separate+=1
        overlap=geom[n].intersection(geom[target]).area
        if overlap>1:overlap_reject+=1;continue
        ratio=float(st[n]['area_calc'])/float(st[donor]['area_calc']);d=distance(n,target)
        aridity_ratio=float(st[n]['arid_1'])/float(st[donor]['arid_1'])
        metadata_support.append((ratio,d,aridity_ratio))
        calipers['area_only_pass']+=.5<=ratio<=2
        calipers['aridity_only_pass']+=.5<=aridity_ratio<=2
        calipers['distance_only_pass']+=d<=500
        calipers['area_and_aridity_pass']+=.5<=ratio<=2 and .5<=aridity_ratio<=2
        calipers['all_descriptor_calipers_pass']+=.5<=ratio<=2 and .5<=aridity_ratio<=2 and d<=500
        if not (.5<=ratio<=2 and .5<=aridity_ratio<=2 and d<=500):continue
        jy,jd=joint(n,target)
        if jy<10:continue
        # This is a metadata-only ranking proposal; no fitted model, Q correlation or loss.
        score=2*abs(math.log(ratio))+2*abs(math.log(aridity_ratio))+abs(float(st[n]['elev_mean'])-float(st[donor]['elev_mean']))/1000+abs(float(st[n]['p_season'])-float(st[donor]['p_season']))+abs(d-distance(donor,target))/500
        matches.append((score,n,ratio,d,overlap,jy,jd))
    for rank,(score,n,ratio,d,overlap,jy,jd) in enumerate(sorted(matches)[:3],1):
        neighbors.append(dict(connected_donor_id=donor,target_id=target,nonnested_donor_id=n,rank=rank,donor_to_target_path=False,target_to_donor_path=False,basin_overlap_m2=overlap,different_transfer_group=True,donor_area_match_ratio=ratio,distance_km=d,descriptor_distance=score,joint_years_ge90pct_checked=jy,known_uncertainties='provisional transfer groups; omitted operations may connect groups; no explicit categorical climate-zone match; common-support/B2 rules not frozen',status='CONDITIONAL_METADATA_CANDIDATE_NOT_FINAL_MATCH'))
        counts[target]+=1;paircounts[(donor,target)]+=1
if neighbors:write(H/'nonnested_candidates.csv',neighbors)
else:
    # An honest machine-readable assessed empty pool with schema is not a fabricated complete sample.
    with (H/'nonnested_candidates.csv').open('w',encoding='utf-8',newline='') as f:csv.writer(f).writerow(['connected_donor_id','target_id','nonnested_donor_id','status'])
write(H/'connected_candidates.csv',pairs);write(H/'station_metadata.csv',stations)
attrition=[dict(step='gauges_with_runoff_files',count=len(st)),dict(step='A_B_delineated_gauges',count=len(nd)),dict(step='direct_gauge_edges',count=len(pairs)),dict(step='RiverATLAS_and_nested_geometry',count=sum(p['topology_candidate_pass']=='True' for p in pairs)),dict(step='plus_joint_10yr_checked_coverage',count=sum(p['topology_candidate_pass']=='True' and p['coverage_pass'] for p in pairs)),dict(step='plus_low_no_impact_endpoints',count=sum(p['coverage_lowimpact_pass'] for p in pairs)),dict(step='plus_both_endpoint_snap_le500m_provisional',count=len(eligible)),dict(step='fully_admitted_after_operations_license_latency',count=0)]
write(H/'attrition.csv',attrition)
summary=dict(directed_ancestor_pairs=ancestors,direct_pairs=len(pairs),topology_verified_pairs=sum(p['topology_candidate_pass']=='True' for p in pairs),joint_coverage_topology_pairs=sum(p['topology_candidate_pass']=='True' and p['coverage_pass'] for p in pairs),provisional_low_no_impact_pairs=len(eligible),provisional_unique_targets=len({p['target_id'] for p in eligible}),all_daily_stations_10_checked_years=sum(s['coverage_10years_pass'] for s in cover.values()),matching_pool_stations=len(pool),nonnested_proposed_rows=len(neighbors),targets_with_any_proposed_match=len(counts),connected_pairs_with_3_proposed_controls=sum(v>=3 for v in paircounts.values()),targets_with_at_least_one_3_control_pair=len({k[1] for k,v in paircounts.items() if v>=3}),different_transfer_group_candidates_before_descriptor_calipers=raw_separate,overlap_rejections=overlap_reject,fully_admitted_pairs=0,matching_status='CONDITIONAL_UNFROZEN_METADATA_SCREEN',no_Q_statistics=True)
summary['low_impact_before_snap_pairs']=sum(p['coverage_lowimpact_pass'] for p in pairs)
(E/'pair_gate_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
support=dict(candidate_comparisons=len(metadata_support),caliper_counts=dict(calipers),area_match_ratio_range=[min(x[0] for x in metadata_support),max(x[0] for x in metadata_support)] if metadata_support else [],target_neighbor_distance_km_range=[min(x[1] for x in metadata_support),max(x[1] for x in metadata_support)] if metadata_support else [],aridity_match_ratio_range=[min(x[2] for x in metadata_support),max(x[2] for x in metadata_support)] if metadata_support else [],no_Q_values_used=True)
(E/'matching_common_support.json').write_text(json.dumps(support,indent=2),encoding='utf-8');print(json.dumps(support))
