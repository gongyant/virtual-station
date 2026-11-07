"""Second official network path check; no ID-system interchange or flow data."""
from pathlib import Path
import csv,json,collections
import pyogrio
H=Path(__file__).resolve().parents[1];E=H/'evidence';O=H/'open_metadata'
with (H/'station_metadata.csv').open(encoding='utf-8') as f:st={r['ID']:r for r in csv.DictReader(f)}
with (H/'connected_candidates.csv').open(encoding='utf-8') as f:pairs=list(csv.DictReader(f))
d=pyogrio.read_dataframe(O/'E_stream_network/EU-Hydro_network.shp',columns=['OBJECT_ID','NEXTDOWNID','STRAHLER'],read_geometry=False)
graph={str(r.OBJECT_ID):str(r.NEXTDOWNID) for r in d.itertuples(index=False)};artificial={str(r.OBJECT_ID) for r in d.itertuples(index=False) if int(r.STRAHLER)==-1}
results=[]
for p in pairs:
    u,v=p['donor_id'],p['target_id'];x,end=st[u]['nrs_euhyd'],st[v]['nrs_euhyd'];seen=set();n=0;art=0
    if x not in graph or end not in graph:status='NOT_TESTABLE_ID_MISSING'
    elif x==end:status='NOT_TESTABLE_SAME_REACH'
    else:
        while x in graph and x not in seen and x!=end:
            seen.add(x);n+=1;art+=x in artificial;x=graph[x]
        status='PASS' if x==end else 'NOT_TESTABLE_BOUNDARY' if x not in graph else 'FAIL_CYCLE'
    results.append(dict(donor_id=u,target_id=v,status=status,river_reach_count=n,artificial_reaches_in_pre_target_path=art,artificial_path_review_required=art>0))
with (E/'eu_hydro_path_checks.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(results[0]));w.writeheader();w.writerows(results)
out=dict(river_records=len(graph),edges=len(results),status_counts=dict(collections.Counter(r['status'] for r in results)),paths_with_artificial_segments=sum(r['artificial_path_review_required'] for r in results),independent_ID_namespace=True)
(E/'eu_hydro_summary.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out))
