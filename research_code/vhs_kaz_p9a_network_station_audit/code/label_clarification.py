from common import *
import shutil,ast,pyogrio
archive=ROOT/'evidence/PREDELIVERY_LABEL_CLARIFICATION';archive.mkdir()
targets=['SHA256SUMS.txt','evidence/BOUNDARY_TOPOLOGY_COUNTS.json','code/extra_audit.py','P9A_COMPLETE_REPORT_ZH.md','P9A_FINAL_STATUS.json']
old_manifest=sha(ROOT/'SHA256SUMS.txt')
for rel in targets:
    dest=archive/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,dest)
f=pyogrio.read_dataframe(GPKG,layer='basin_fragments',columns=['HYRIV_ID','basin_id'],read_geometry=False)
assigned=int((f[f.basin_id>0].groupby('HYRIV_ID').basin_id.nunique()>1).sum())
allids=int((f.groupby('HYRIV_ID').basin_id.nunique()>1).sum())
q=read(ROOT/'evidence/BOUNDARY_TOPOLOGY_COUNTS.json');assert q.pop('source_reaches_crossing_multiple_basins')==allids
q['source_reaches_crossing_two_or_more_assigned_basins']=assigned
q['source_reaches_crossing_two_or_more_assignment_ids_including_unassigned']=allids
q['UNASSIGNED_is_not_a_ninth_management_basin']=True
js(ROOT/'evidence/BOUNDARY_TOPOLOGY_COUNTS.json',q)
p=ROOT/'code/extra_audit.py';text=p.read_text(encoding='utf-8')
old="source_reaches_crossing_multiple_basins=int((f.groupby('HYRIV_ID').basin_id.nunique()>1).sum()),"
new="source_reaches_crossing_two_or_more_assigned_basins=int((f[f.basin_id>0].groupby('HYRIV_ID').basin_id.nunique()>1).sum()),source_reaches_crossing_two_or_more_assignment_ids_including_unassigned=int((f.groupby('HYRIV_ID').basin_id.nunique()>1).sum()),"
assert text.count(old)==1;text=text.replace(old,new);ast.parse(text);p.write_text(text,encoding='utf-8')
p=ROOT/'P9A_COMPLETE_REPORT_ZH.md';text=p.read_text(encoding='utf-8');text+=f'\n交付前标签澄清：跨两个及以上实际研究流域的来源河段为{assigned}条，与P8一致；跨两个及以上归属ID（含UNASSIGNED=0）为{allids}条。未归属区不是第九流域，两个字段分别保存；此修改不涉及原始几何、长度、站点筛选或旧成果。首次交付前清单及受影响文件已留存于evidence/PREDELIVERY_LABEL_CLARIFICATION，供追溯，不作为另一套独立实验。\n';p.write_text(text,encoding='utf-8')
js(ROOT/'evidence/PREDELIVERY_LABEL_AMENDMENT.json',dict(previous_manifest_sha256=old_manifest,assigned_basin_crossing_reaches=assigned,all_assignment_ID_crossing_reaches_including_unassigned=allids,geometry_changed=False,lengths_changed=False,selection_changed=False,scope='Clarify P9A new metadata label before user handoff; protected P0-P8 unchanged',archive='evidence/PREDELIVERY_LABEL_CLARIFICATION'))
state=read(ROOT/'P9A_FINAL_STATUS.json');state['metadata_scope_clarification']='492 assigned-basin crossings;1361 assignment-ID crossings including UNASSIGNED';state['previous_predelivery_manifest_sha256']=old_manifest;js(ROOT/'P9A_FINAL_STATUS.json',state)
event('predelivery_label_scope_clarified',assigned_basins=assigned,including_unassigned=allids,geometry_changed=False)
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and p!=ROOT/'SHA256SUMS.txt' and '__pycache__' not in p.parts)
(ROOT/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}\n' for p in files),encoding='utf-8')
print(json.dumps(dict(files=len(files),manifest_sha256=sha(ROOT/'SHA256SUMS.txt'),gpkg_sha256=sha(ROOT/'P9A_SEVEN_ORDER_NETWORK.gpkg'))),flush=True)
