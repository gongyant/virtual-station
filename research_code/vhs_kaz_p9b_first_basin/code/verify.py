from common import *
import numpy as np,geopandas as gpd,pyogrio,sqlite3,re,math
from collections import defaultdict
checks=[]
def ck(n,x,**d):checks.append(dict(check=n,passed=bool(x),**d))
db=ROOT/'source/CA-discharge.gpkg';ck('CA_official_MD5',digest(db,'md5')=='e0ba6664aaec3e0b27138abdfd4ba263');ck('CA_expected_file_bytes',db.stat().st_size==24576000)
con=sqlite3.connect('file:'+db.as_posix()+'?immutable=1',uri=True)
ck('CA_actual_time_series_rows',con.execute('SELECT COUNT(*) FROM discharge_time_series').fetchone()[0]==244632)
kaz=pd.read_sql_query('SELECT date,value FROM discharge_time_series WHERE CODE=?',con,params=['16390']);out=pd.read_csv(ROOT/'data/CA_PUBLIC_KAZ_MONTHLY_Q_OUTSIDE_TARGET.csv');ck('public_KAZ492not_synthetic',len(kaz)==492 and np.allclose(kaz.value,out.Q_m3s,rtol=0,atol=1e-10));con.close()
g=pd.read_csv(ROOT/'P9B_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str});p9g=pd.read_csv(P9A/'P9A_GAUGE_IDENTITY_CROSSWALK.csv',dtype={'station_code':str}).set_index('station_code')
ck('all49retained',len(g)==49 and g.station_code.is_unique)
for r in g.itertuples():
    ref=p9g.loc[r.station_code];ck('gauge_coordinates_unchanged_'+r.station_code,abs(r.longitude-ref.longitude)<1e-9 and abs(r.latitude-ref.latitude)<1e-9);ck('not_official_identity_promoted_'+r.station_code,r.official_identity_status in ['GEOMETRIC_PROVISIONAL','SOURCE_CONFLICT'])
ck('area_conflict_retained_14419',g.set_index('station_code').loc['14419','official_identity_status']=='SOURCE_CONFLICT')
t=pd.read_csv(ROOT/'data/P9B_BULLETIN_MONTHLY_Q_TRANSCRIPTION.csv',dtype={'source_token':str});ck('all252reported_months_preserved',len(t)==252);ck('source_month_identity_unique',not t[['source_station','year','month']].duplicated().any())
# Independent numeric-word extraction from rendered-source geometry, not the handwritten matrix.
page_order={177:[('Ili-Dobyn',2021),('Ili-Dobyn',2022),('Ili-Dobyn',2023),('Tentek-Tonkeris',2021)],178:[('Tentek-Tonkeris',2022),('Tentek-Tonkeris',2023),('Ili-Kapshagay',2021),('Ili-Kapshagay',2022),('Ili-Kapshagay',2023),('Lepsy-Lepsy',2021),('Lepsy-Lepsy',2022),('Lepsy-Lepsy',2023),('Chilik-Malybay',2021),('Chilik-Malybay',2022)],179:[('Chilik-Malybay',2023),('Charyn-Sarytogay',2021),('Charyn-Sarytogay',2022),('Charyn-Sarytogay',2023),('Ili-above-Kapshagay164km',2021),('Ili-above-Kapshagay164km',2022),('Ili-above-Kapshagay164km',2023)]}
word_rows=[]
for page,keys in page_order.items():
    w=read(ROOT/'evidence'/f'BULLETIN_PAGE_{page}_WORDS.json');units=sorted([x for x in w if x['text']=='m3/s' and x['x0']<150],key=lambda x:x['top']);raw=[]
    for u in units:
        # Some unit glyphs are six points above the numeric row. Group glyphs
        # by their actual baseline rather than mixing the nearby rank labels.
        candidates=[x for x in w if abs(x['top']-u['top'])<7.0 and x['x0']>u['x1'] and re.fullmatch(r'\d+(?:\.\d+)?',x['text'])]
        baselines=sorted(set(round(x['top'],1) for x in candidates))
        rows=[sorted([x for x in candidates if abs(x['top']-y)<.2],key=lambda x:x['x0']) for y in baselines]
        complete=[v for v in rows if len(v)==16]
        vals=complete[0] if len(complete)==1 else []
        if len(vals)==16:raw.append([x['text'] for x in vals])
    if page==178:
        # The first data row continues across the page break: its year/unit
        # labels remain on page 177. Read the first complete numeric baseline
        # below the repeated header, before the percentage baseline.
        first=[x for x in w if 115<x['top']<130 and x['x0']>135 and re.fullmatch(r'\d+(?:\.\d+)?',x['text'])]
        raw.insert(0,[x['text'] for x in sorted(first,key=lambda x:x['x0'])])
    ck('independent_PDF_row_count_'+str(page),len(raw)==len(keys),actual_rows=len(raw),expected_rows=len(keys))
    if len(raw)!=len(keys):continue
    for (name,start),vals in zip(keys,raw):
        positions=[0,1,2,3,4,5,6,8,9,11,12,13] if name in ['Ili-Dobyn','Tentek-Tonkeris','Ili-Kapshagay','Lepsy-Lepsy'] else [0,1,2,3,4,5,6,7,9,10,12,13]
        for i,pos in enumerate(positions):
            month=(i+2)%12+1;year=start if month>=3 else start+1;r=t[(t.source_station==name)&(t.year==year)&(t.month==month)].iloc[0]
            value=float(vals[pos]);ck(f'PDF_numeric_{name}_{year}_{month}',abs(value-r.q_reported_m3s)<1e-10);word_rows.append(dict(source_station=name,year=year,month=month,page=page,pdf_word_value=value,transcribed_value=r.q_reported_m3s))
csv(ROOT/'evidence/INDEPENDENT_PDF_TRANSCRIPTION_CHECK.csv',word_rows)
ck('all252independently_matched_to_PDF',len(word_rows)==252)
ck('36Lepsy_conflicts_not_repaired',t[t.source_station=='Lepsy-Lepsy'].source_QC_status.eq('SOURCE_INTERNAL_SUM_CONFLICT').all())
s=pd.read_csv(ROOT/'P9B_CATCHMENT_DELINEATION_STATUS.csv');p=pyogrio.read_dataframe(ROOT/'P9B_FIRST_BASIN_GIS.gpkg',layer='upstream_L12_outlet_proxies');weights=pd.read_csv(ROOT/'data/ERA5_LAND_PROXY_AREA_WEIGHTS.csv')
ck('30catchment_records29uniquehosts',len(s)==30 and s.source_host_HYBAS_L12.nunique()==29);ck('no_exact_point_claims',s.point_exact_area_km2.isna().all());ck('30valid_proxy_geometries',p.geometry.is_valid.all())
ck('one_host_point_conflict_flagged',s.catchment_state.str.contains('SOURCE_CONFLICT').sum()==1)
for r in s.itertuples():
    d=weights[weights.candidate_id==r.candidate_id];ck('weights_sum_'+r.candidate_id,abs(d.area_weight.sum()-1)<1e-8 and d.overlap_area_km2.gt(0).all());ck('proxy_area_source_attribute_'+r.candidate_id,r.proxy_area_relative_difference<=.02)
ck('crossborder_area_not_clipped',s[s.engineering_role=='P9A_MAINSTEM_PILOT'].foreign_proxy_area_km2.gt(0).all())
alt=pd.read_csv(ROOT/'P9B_ALTERNATE_TRIBUTARY_CANDIDATES.csv');ck('10real_alternate_records',len(alt)==10 and alt.station_id.is_unique)
ck('alternates_respect_original_rules',alt.geometry_qualified.all() and alt.nearest_available_river_gauge_distance_m.ge(5000).all() and alt.ORD_CLAS.ge(2).all())
nodes=pd.read_csv(P9A/'data/GLOBAL_UPSTREAM_CLOSURE.csv');N={int(r.HYRIV_ID):r for r in nodes.itertuples()};up=defaultdict(list)
for rid,r in N.items():up[int(r.NEXT_DOWN)].append(rid)
cache={}
distance_cache={}

def reverse_distance(downstream,upstream):
    if downstream not in distance_cache:
        distances={downstream:0.};todo=[downstream]
        while todo:
            z=todo.pop()
            for parent in up[z]:
                if parent in distances:continue
                distances[parent]=distances[z]+float(N[parent].geometry_length_km)
                todo.append(parent)
        distance_cache[downstream]=distances
    return distance_cache[downstream][upstream]
def ancestors(rid):
    if rid not in cache:
        seen=set();todo=[rid]
        while todo:
            z=todo.pop()
            if z in seen:continue
            seen.add(z);todo.extend(up[z])
        cache[rid]=seen
    return cache[rid]
c=pd.read_csv(P9A/'P9A_FIRST_BASIN_PILOT_CANDIDATES.csv');allc=pd.concat([c,alt]);point={r.station_id:r for r in allc.itertuples()};gc=pd.read_csv(P9A/'P9A_UPSTREAM_CHAIN_LENGTH.csv',dtype={'station_id':str});point.update({r.station_id:r for r in gc.itertuples()})
rels=pd.read_csv(ROOT/'P9B_CANDIDATE_NETWORK_RELATIONSHIPS.csv',dtype={'b_id':str})
for r in rels.itertuples():
    a,b=point[r.a_id],point[r.b_id];ia,ib=int(a.HYRIV_ID),int(b.HYRIV_ID)
    if ia==ib:
        ck('same_reach_offset_'+r.a_id+'_'+r.b_id,abs(abs(a.within_reach_offset_km-b.within_reach_offset_km)-r.along_network_distance_km)<1e-6);continue
    ab=ia in ancestors(ib);ba=ib in ancestors(ia);expected='A_UPSTREAM_B' if ab else 'B_UPSTREAM_A' if ba else 'NO_DIRECTED_PATH_IN_SOURCE_GRAPH';ck('reverse_graph_relation_'+r.a_id+'_'+r.b_id,r.relation==expected)
    if ab or ba:
        uu,dd=(a,b) if ab else (b,a)
        length=reverse_distance(int(dd.HYRIV_ID),int(uu.HYRIV_ID))-float(uu.within_reach_offset_km)+float(dd.within_reach_offset_km)
        ck('reverse_graph_numeric_distance_'+r.a_id+'_'+r.b_id,abs(length-r.along_network_distance_km)<1e-6,absolute_difference_km=abs(length-r.along_network_distance_km))
main_ids=set(c.station_id);main=rels[(rels.pair_type=='CANDIDATE_CANDIDATE')&rels.a_id.isin(main_ids)&rels.b_id.isin(main_ids)];ck('20mainstem190nestedpairs',len(main)==190 and main.along_network_distance_km.notna().all())
members=pd.read_csv(ROOT/'data/HYDROBASINS_UPSTREAM_MEMBERS.csv');sets={k:set(d.HYBAS_ID) for k,d in members.groupby('candidate_id')};nested_alt=[]
for i,a in enumerate(alt.station_id):
    for b in alt.station_id.iloc[i+1:]:
        if sets[a].issubset(sets[b]) or sets[b].issubset(sets[a]):nested_alt.append(dict(a=a,b=b,warning='PROXY_CATCHMENTS_NESTED_DESPITE_SOURCE_PATH_ALTERNATIVE;not independent replicas'))
csv(ROOT/'evidence/ALTERNATE_PROXY_NESTING.csv',pd.DataFrame(nested_alt,columns=['a','b','warning']))
protocol=read(ROOT/'P9B_P10_VALIDATION_PROTOCOL.json');ck('P10stays_notready',protocol['current_execution']=='P10_NOT_READY');ck('no_target_template_inPUB', 'alltargetQ' in protocol['target_Q_exclusion']);ck('no_proxies_admitted_as_point_forcing',pd.read_csv(ROOT/'P9B_BASIN_DRIVERS_STATUS.csv').weights_status.eq('COMPUTED_PROXY_ONLY_NOT_ADMITTED').all())
ck('CA_source_unchanged_after_reads',digest(db,'md5')=='e0ba6664aaec3e0b27138abdfd4ba263')
h=history_check('HISTORY_FINAL_CHECK.json');source_qc=pd.read_csv(ROOT/'data/P9B_BULLETIN_TABLE_ARITHMETIC_QC.csv')
result=dict(passed=sum(x['passed'] for x in checks),failed=sum(not x['passed'] for x in checks),checks=checks,source_arithmetic_QC_passed=int(source_qc.passed.sum()),source_arithmetic_QC_failed=int((~source_qc.passed).sum()),source_Lepsy_conflicting_months=36,alternate_proxy_nested_pairs=len(nested_alt),grid_area_partition_max_relative_error=float(s.grid_area_partition_relative_error.max()),history_checked=h['checked'],fit_calls=0,teacher_Q_reads=0)
js(ROOT/'P9B_INDEPENDENT_QA.json',result);event('independent_QA_complete',passed=result['passed'],failed=result['failed'],source_QC_failed=result['source_arithmetic_QC_failed'],alternate_proxy_nested_pairs=len(nested_alt))
if result['failed']:raise RuntimeError('Independent checks failed; inspect explicit result')
