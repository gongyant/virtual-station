"""B0 structure/topology audit only. No observed discharge arrays or cells are loaded."""
from pathlib import Path
import json,csv,hashlib,zipfile,xml.etree.ElementTree as ET
import numpy as np
ROOT=Path(__file__).resolve().parents[3];H=ROOT/'research_next/vhs_multistation';OUT=H/'evidence';OUT.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def read(p,cols=None):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:
        r=csv.DictReader(f)
        if cols is not None:assert set(cols)<=set(r.fieldnames)
        return [{k:v for k,v in row.items() if cols is None or k in cols} for row in r]
def dump(n,obj):(OUT/n).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def main():
    if (OUT/'local_complete.json').exists():raise RuntimeError('Already audited; preserve evidence')
    r3=ROOT/'research_next/vhs_transfer/experiments/s1a_r3'
    hist=load(r3/'integrity_before.json')['hashes']
    for p,v in load(r3/'delivery_manifest.json').items():hist[p]=v['sha256']
    p=r3/'delivery_manifest.json';hist[p.relative_to(ROOT).as_posix()]=sha(p)
    for p,v in hist.items():assert sha(ROOT/p)==v,p
    # Scoped protection of the entire frozen transfer branch; no project-wide discovery scan.
    for p in (ROOT/'research_next/vhs_transfer').rglob('*'):
        if p.is_file():hist.setdefault(p.relative_to(ROOT).as_posix(),sha(p))
    inputs=['data/processed/nodes.csv','data/processed/edges.csv','data/processed/station_river_matches.csv','data/raw/hydrorivers/HydroRIVERS_v10_as.shp','data/raw/hydrorivers/HydroRIVERS_v10_as.dbf','data/raw/hydrorivers/HydroRIVERS_v10_as.shx','data/raw/stations/新疆基本水文站.kmz','data/raw/stations/前苏联水文站点.kmz','data/raw/runoff/Q-新疆.xls','data/raw/runoff/BYBLK-DSK日数据.xlsx','data/raw/runoff/Q-dsk-byblk.xlsx']
    for p in inputs:hist.setdefault(p,sha(ROOT/p))
    baseline=OUT/'integrity_before.json'
    if baseline.exists():
        for p,v in load(baseline)['hashes'].items():assert sha(ROOT/p)==v,p
    else:dump('integrity_before.json',dict(files=len(hist),hashes=hist))
    nodes=read(ROOT/'data/processed/nodes.csv');edges=read(ROOT/'data/processed/edges.csv');node={r['station_id']:r for r in nodes}
    stations=[]
    for fname in ('新疆基本水文站.kmz','前苏联水文站点.kmz'):
        with zipfile.ZipFile(ROOT/'data/raw/stations'/fname) as z:
            kmls=[n for n in z.namelist() if n.lower().endswith('.kml')]
            count=0
            for n in kmls:
                tree=ET.fromstring(z.read(n))
                for placemark in tree.findall('.//{*}Placemark'):
                    fields={x.attrib.get('name'):x.findtext('{*}value') for x in placemark.findall('.//{*}Data')}
                    fields.update({x.attrib.get('name'):x.text for x in placemark.findall('.//{*}SimpleData')})
                    name=placemark.findtext('{*}name');coord=placemark.findtext('.//{*}Point/{*}coordinates')
                    stations.append(dict(source=fname,name=name,coordinates=coord,metadata={k:v for k,v in fields.items() if k in ('CZID','CZNM','RIVNM','RIVID','BEGIN','END','BASIN','AREA','CATCHAREA','NAME','RIVER','FILE_NAME')}));count+=1
            dump(fname+'.inventory.json',dict(source='data/raw/stations/'+fname,sha256=sha(ROOT/'data/raw/stations'/fname),placemark_count=count,kml_entries=kmls))
    dump('station_catalogs.json',stations)
    books=[]
    for p in (ROOT/'data/raw/runoff').iterdir():
        if p.suffix.lower()=='.xlsx':
            with zipfile.ZipFile(p) as z:
                root=ET.fromstring(z.read('xl/workbook.xml'));sheets=[dict(name=x.attrib['name'],sheet_id=x.attrib['sheetId']) for x in root.findall('.//{*}sheet')]
                # Dimension attributes only; stop before any row/cell content.
                dims={}
                for entry in z.namelist():
                    if entry.startswith('xl/worksheets/sheet') and entry.endswith('.xml'):
                        with z.open(entry) as f:
                            for _,element in ET.iterparse(f,events=('start',)):
                                tag=element.tag.rsplit('}',1)[-1]
                                if tag=='dimension':dims[entry]=element.attrib.get('ref')
                                if tag=='sheetData':break
                books.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),format='xlsx',sheets=sheets,dimensions=dims,discharge_cells_loaded=False))
        elif p.suffix.lower()=='.xls':
            import xlrd
            b=xlrd.open_workbook(p,on_demand=True);books.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),format='xls',sheets=b.sheet_names(),sheet_cells_loaded=False));b.release_resources()
    dump('workbook_structures.json',books)
    bundles=[]
    for p in [ROOT/'data/processed/real_bundle.npz',ROOT/'data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz']:
        arrays={}
        with zipfile.ZipFile(p) as z:
            for entry in z.namelist():
                if not entry.endswith('.npy'):continue
                with z.open(entry) as f:
                    version=np.lib.format.read_magic(f)
                    if version==(1,0):shape,fortran,dtype=np.lib.format.read_array_header_1_0(f)
                    elif version==(2,0):shape,fortran,dtype=np.lib.format.read_array_header_2_0(f)
                    else:raise RuntimeError(f'Unsupported NPY header version: {version}')
                arrays[entry]=dict(shape=list(shape),dtype=str(dtype),payload_loaded=False)
        bundles.append(dict(path=p.relative_to(ROOT).as_posix(),arrays=arrays,flow_payload_loaded=False))
    dump('bundle_headers.json',bundles)
    multi=ROOT/'data/processed/virtual_station_multisite'
    coverage=read(multi/'multisite_coverage_2005.csv',('station_id','station_code','component','first_date','last_date','calendar_days','rows','observed_days','observed_missing_days'))
    dump('coverage_metadata.json',coverage)
    # Read bounded regional river geometry and attributes, never discharge; derive paths from official NEXT_DOWN.
    import pyogrio
    river=pyogrio.read_dataframe(ROOT/'data/raw/hydrorivers/HydroRIVERS_v10_as.shp',bbox=(70,30,96,50),columns=['HYRIV_ID','NEXT_DOWN','MAIN_RIV','LENGTH_KM','UPLAND_SKM'],read_geometry=False)
    graph={int(r.HYRIV_ID):dict(next=int(r.NEXT_DOWN),root=int(r.MAIN_RIV),length=float(r.LENGTH_KM),area=float(r.UPLAND_SKM)) for r in river.itertuples(index=False)}
    pairs=[];paths={}
    for e in edges:
        u=node[e['source']];v=node[e['target']];start=int(u['river_id']);end=int(v['river_id']);x=start;path=[];seen=set()
        while x!=end and x in graph and x not in seen and x!=0:
            seen.add(x);path.append(x);x=graph[x]['next']
        reached=x==end;distance=sum(graph[k]['length'] for k in path) if reached else None
        if reached:assert abs(distance-float(e['river_distance_km']))<1e-6
        area_u=float(u['UP_AREA']);area_v=float(v['UP_AREA']);snap_u=float(u['snap_distance_m']);snap_v=float(v['snap_distance_m']);full_status='TOPOLOGY_UNVERIFIED'
        pairs.append(dict(pair_id=e['source']+'__'+e['target'],source_dataset='local_34_station_project_graph',upstream_id=e['source'],upstream_name=u['station_name'],downstream_id=e['target'],downstream_name=v['station_name'],upstream_river_id=start,downstream_river_id=end,main_river_id=graph[start]['root'] if start in graph else '',directed_path_verified=reached,path_reach_count=len(path),river_distance_km=distance,river_distance_definition='sum entire upstream through pre-target reaches; no endpoint offset correction',upstream_area_km2=area_u,downstream_area_km2=area_v,area_ratio=area_u/area_v,area_monotonic=area_v>area_u,upstream_snap_m=snap_u,downstream_snap_m=snap_v,snap_source='existing project nearest-reach mapping; no competing-candidate review',reservoir_path_status='UNVERIFIED',diversion_return_flow_status='UNVERIFIED',other_gauged_tributaries_status='UNVERIFIED',formal_identity_status='PROJECT_CATALOG_ONLY',observed_overlap_metadata='1978-1983 2191 days' if (e['source'],e['target'])==('00705600','00705700') else 'NO_LOCAL_OBSERVED_Q_COVERAGE_PROVEN',unit_day_boundary_status='UNVERIFIED',license_status='UNVERIFIED',topology_status=full_status,B0_admitted=False))
        paths[e['source']+'__'+e['target']]=dict(reached=reached,reach_ids=path,target_boundary_reach=end)
    for e in read(multi/'multisite_edges_2005.csv'):
        if e['source']=='00705600':continue
        pairs.append(dict(pair_id=e['source']+'__'+e['target'],source_dataset='local_five_station_2005',upstream_id=e['source'],downstream_id=e['target'],upstream_name=e['source'].replace('TARIM_',''),downstream_name=e['target'].replace('TARIM_',''),directed_path_verified=False,observed_overlap_metadata='2005-01-02..2005-10-28,300days; inherited coverage only',formal_identity_status='PROJECT_ALIAS_ONLY',topology_status='TOPOLOGY_UNVERIFIED',topology_basis=e['basis'],river_distance_km='',main_river_id='',reservoir_path_status='UNVERIFIED',diversion_return_flow_status='UNVERIFIED',other_gauged_tributaries_status='intermediate Yingbaza/Usman named in project collapsed-edge record; observations absent',unit_day_boundary_status='UNVERIFIED',license_status='UNVERIFIED',B0_admitted=False))
    out=H/'reports';out.mkdir(exist_ok=True)
    keys=list(dict.fromkeys(k for r in pairs for k in r))
    with (out/'b0_candidate_station_pairs.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(pairs)
    dump('directed_paths.json',paths)
    roots=sorted({int(graph[int(n['river_id'])]['root']) for n in nodes if int(n['river_id']) in graph});pairroots=sorted({r['main_river_id'] for r in pairs if r.get('directed_path_verified')})
    result=dict(status='LOCAL_METADATA_AUDIT_COMPLETE',project_nodes=len(nodes),project_edges=len(edges),regional_river_records=len(graph),raw_catalog_placemarks=len(stations),candidate_pairs=len(pairs),raw_graph_verified_pairs=sum(r['directed_path_verified'] for r in pairs),fully_admitted_pairs=0,graph_main_river_ids_all_nodes=roots,graph_main_river_ids_candidate_pairs=pairroots,admitted_independent_systems=0,known_independent_complete_systems=0,independent_systems_note='MAIN_RIV groups are topology candidates only, not proven operational independence; five-station project components not counted as independent rivers',new_target_observation_payload_reads=0,training_runs=0,gpu_runs=0,access_exception='Interactive inspection of existing five-station coverage table also displayed pre-existing historical aggregate Q columns. These were already historical exposed metadata, not raw new target series; excluded from all B0 selection, reports and artifacts. Subsequent reads enforce coverage-column whitelist.')
    dump('local_complete.json',result)
    for p,v in hist.items():assert sha(ROOT/p)==v,p
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
