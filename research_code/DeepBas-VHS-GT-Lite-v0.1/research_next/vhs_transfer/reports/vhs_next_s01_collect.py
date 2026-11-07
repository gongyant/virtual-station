"""Targeted S0.1 metadata/evidence capture; never fits/predicts a model.

Candidate label files are hashed as opaque byte streams, never parsed. Only the
two already-exposed workbooks' names/properties and known 2005 headers are read.
No S0-wide scan, raw Q statistics, graph rerun, GPU or historical file write.
"""
import hashlib,json,sys,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import xlrd
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research_next/vhs_transfer'
OUT=BASE/'reports'
sys.stdout.reconfigure(encoding='utf-8')
S0=json.loads((BASE/'data_audit/historical_after.json').read_text(encoding='utf-8'))
S0MAN=json.loads((BASE/'data_audit/source_manifest.json').read_text(encoding='utf-8'))
paths=[
 'research_next/vhs_transfer/data_audit/historical_after.json',
 'research_next/vhs_transfer/data_audit/integrity_result.json',
 'research_next/vhs_transfer/data_audit/source_manifest.json',
 'research_next/vhs_transfer/data_audit/live_audit_facts.json',
 'research_next/vhs_transfer/data_audit/code_evidence.txt',
 'research_next/vhs_transfer/reports/vhs_next_s0_source_inventory.md',
 'research_next/vhs_transfer/reports/vhs_next_s0_provenance_audit.md',
 'research_next/vhs_transfer/reports/vhs_next_s0_leakage_audit.md',
 'research_next/vhs_transfer/reports/vhs_next_s0_research_protocol.md',
 'research_next/vhs_transfer/reports/vhs_next_s0_validation_report.md',
 'research_next/vhs_transfer/reports/vhs_next_s0_status.txt',
 'data/raw/runoff/BYBLK-DSK日数据.xlsx','data/raw/runoff/Q-新疆.xls','data/raw/runoff/Q-dsk-byblk.xlsx',
 'data/teacher_raw/Doc1.docx',
 'configs/real_data.yaml','configs/multisite2005_snapshot_gnn.yaml','configs/holdout_dsk_graph1.yaml','configs/mainline_formal_graph.yaml',
 'src/vhs/io.py','src/vhs/data.py','src/vhs/train.py',
 'scripts/prepare_timeseries.py','scripts/extract_multisite_runoff_2005.py','scripts/prepare_multisite_gnn_bundle_2005.py',
 'scripts/build_bd1m_model_dataset_audit.py','scripts/bd1m_e4a2_optimizer.py','scripts/run_bd1m_e4c_fixed_1983_holdout.py',
 'outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md',
 'outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/source_audit_report_zh.md',
 'outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/daily_time_definition_audit.md',
 'outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/station_mapping_audit.csv',
 'outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/raw_workbook_structure_audit.json',
 'outputs/diagnosis_2005_snapshot/stage_d5_round3/additional_station_input_audit.csv',
 'outputs/diagnosis_2005_snapshot/stage_d5_round3/candidate_additional_inputs_registry.csv',
 'outputs/diagnosis_2005_snapshot/stage_d5_round4/candidate_selection_report_zh.md',
 'outputs/diagnosis_2005_snapshot/stage_d5_round4/m2c_development_report_zh.md',
 'outputs/vhs_bd1m/experiments/e4a2_train_daily_q_lineage.md',
 'outputs/vhs_bd1m/experiments/e4a2_r1_train_fit.csv',
 'outputs/vhs_bd1m/experiments/e4b1_incremental_residual_predictions.csv',
 'outputs/vhs_bd1m/experiments/e4c_1983_daily_predictions.csv',
 'data/processed/virtual_station_external/external_runoff_metadata.json',
 'data/processed/virtual_station_multisite/multisite_metadata_2005.json',
 'data/processed/virtual_station_multisite/multisite_bundle_metadata_2005.json',
 'outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/frozen_prediction_metadata.json',
 'outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json',
 'outputs/vhs_bd1m/experiments/e4b3_method_freeze.json',
]
frozen=json.loads((ROOT/'outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json').read_text(encoding='utf-8'))
paths += [v['path'].replace('\\','/') for v in frozen['source_files'].values()]
# Small protected manuscript/registry artifacts only; reuse S0 for large figures/models.
paths += [p.relative_to(ROOT).as_posix() for p in (ROOT/'outputs/vhs_bd1m/paper').iterdir() if p.is_file() and p.suffix in ['.md','.txt','.json','.csv']]
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return {'bytes':p.stat().st_size,'sha256':h.hexdigest()}
before_path=OUT/'vhs_next_s01_integrity_before.json'
if before_path.exists():raise SystemExit('Refusing to replace S0.1 before snapshot')
baseline={}
for rel in sorted(set(paths)):
    p=ROOT/rel
    if p.is_file():
        row=digest(p); row['absolute_path']=str(p)
        row['matches_S0_snapshot']=({k:row[k] for k in ['bytes','sha256']}==S0[rel]) if rel in S0 else None
        row['matches_S0_source_manifest']=(row['sha256']==S0MAN[rel]['sha256']) if rel in S0MAN else None
        baseline[rel]=row
    else:raise FileNotFoundError(p)
before_path.write_text(json.dumps(baseline,ensure_ascii=False,indent=2),encoding='utf-8')
facts={'phase':'VHS-NEXT-S0.1','candidate_labels_parsed':False,'target_statistics_computed':False,'scope':'known S0 MQ/obs evidence; local runoff/teacher metadata; existing processed metadata and historical usage evidence only','known_S0_files_hash_checked':len(baseline)}
facts['local_source_file_inventory']=[]
for folder in ['data/raw/runoff','data/teacher_raw']:
    for p in sorted((ROOT/folder).rglob('*')):
        if p.is_file():facts['local_source_file_inventory'].append({'path':p.relative_to(ROOT).as_posix(),**digest(p),'filesystem_mtime_ns':p.stat().st_mtime_ns,'mtime_is_not_observation_date':True})
def package_metadata(p):
    with zipfile.ZipFile(p) as z:
        result={'core':{},'sheet_names':[]}
        if 'docProps/core.xml' in z.namelist():
            tree=ET.fromstring(z.read('docProps/core.xml'))
            result['core']={n.tag.split('}')[-1]:n.text for n in tree}
        if 'xl/workbook.xml' in z.namelist():
            tree=ET.fromstring(z.read('xl/workbook.xml'))
            result['sheet_names']=[n.attrib['name'] for n in tree.iter() if n.tag.endswith('}sheet')]
        return result
facts['daily_package_metadata']=package_metadata(ROOT/'data/raw/runoff/BYBLK-DSK日数据.xlsx')
facts['monthly_package_metadata']=package_metadata(ROOT/'data/raw/runoff/Q-dsk-byblk.xlsx')
facts['doc1_package_metadata']=package_metadata(ROOT/'data/teacher_raw/Doc1.docx')
book=xlrd.open_workbook(str(ROOT/'data/raw/runoff/Q-新疆.xls'),on_demand=True)
facts['MQ_book']={'sheet_names':book.sheet_names(),'workbook_user_name':str(getattr(book,'user_name','')),'sheet_cell_reads_limited_to':[9,11], 'independence_of_other_sheets':'UNVERIFIED'}
for i in [9,11]:
    sh=book.sheet_by_index(i)
    # Known already-exposed headers only; no row-1..end Q values accessed.
    facts['MQ_book'][f'known_header_sheet_{i}']={'name':sh.name,'row0':sh.row_values(0)}
book.release_resources()
# Capture daily header and OQ text row only. No daily Q values parsed.
with zipfile.ZipFile(ROOT/'data/raw/runoff/BYBLK-DSK日数据.xlsx') as z:
    sst=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        sst=[''.join(n.itertext()) for n in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    known_headers=[]
    with z.open('xl/worksheets/sheet1.xml') as fh:
        for event,row in ET.iterparse(fh,events=['end']):
            if not row.tag.endswith('}row'):continue
            rid=int(row.attrib['r'])
            if rid>2:break
            cells=[]
            for cell in row:
                if not cell.tag.endswith('}c'):continue
                vv=next((n.text for n in cell if n.tag.endswith('}v')),None)
                if cell.attrib.get('t')=='s' and vv is not None:vv=sst[int(vv)]
                elif cell.attrib.get('t')=='inlineStr':vv=''.join(cell.itertext())
                cells.append({'address':cell.attrib.get('r'),'text':vv})
            known_headers.append({'row':rid,'cells':cells})
    facts['daily_headers_only']=known_headers
# Whitelist metadata fields; do not report min/max/mean/metrics or values arrays.
def safe_metadata(obj):
    allowed={'status','source_workbook','workbook','source','source_file','source_sheet','source_header','path','input','inputs','output','output_dir','protocol','station','stations','station_id','station_ids','station_code','station_name','target_station','upstream_station','date_start','date_end','start_date','end_date','dates','time_start','time_end','date_range','date_ranges','coverage','unit','units','source_ranges','sha256','input_hashes','target_labels_loaded','target_labels_used_for_training','target_labels_used_for_model_selection','evaluation_window','held_out_target','edge_attribute_policy'}
    if not isinstance(obj,dict):return obj
    out={}
    for k,v in obj.items():
        if k not in allowed:continue
        out[k]=safe_metadata(v) if isinstance(v,dict) else v
    return out
facts['existing_metadata']={}
for rel in ['data/processed/virtual_station_external/external_runoff_metadata.json','data/processed/virtual_station_multisite/multisite_metadata_2005.json','data/processed/virtual_station_multisite/multisite_bundle_metadata_2005.json','outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/frozen_prediction_metadata.json']:
    facts['existing_metadata'][rel]=safe_metadata(json.loads((ROOT/rel).read_text(encoding='utf-8')))
facts['historical_scoring_artifacts_exist']={}
for rel in ['outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/blind_scoring/external_validation_summary.json','outputs/diagnosis_2005_snapshot/stage_d5/stage_d5_round1_report_zh.md','outputs/diagnosis_2005_snapshot/stage_d/stage_d_report_zh.md','outputs/diagnosis_2005_snapshot/stage_d5_round2/stage_d5_round2_report_zh.md','outputs/diagnosis_2005_snapshot/stage_d5_round4/candidate_selection_report_zh.md']:
    p=ROOT/rel;facts['historical_scoring_artifacts_exist'][rel]={'exists':p.is_file(),**(digest(p) if p.is_file() else {})}
# Prediction source headers only, not predictions or target columns.
facts['frozen_prediction_columns']={}
for rel in ['outputs/vhs_bd1m/experiments/e4b1_incremental_residual_predictions.csv','outputs/vhs_bd1m/experiments/e4c_1983_daily_predictions.csv']:
    with (ROOT/rel).open(encoding='utf-8-sig') as f:facts['frozen_prediction_columns'][rel]=f.readline().strip().split(',')
# Candidate availability and known processed entries, without opening their values.
facts['processed_candidate_file_names']={}
for folder in ['data/processed/virtual_station_external','data/processed/virtual_station_multisite']:
    facts['processed_candidate_file_names'][folder]=[p.name for p in sorted((ROOT/folder).iterdir()) if p.is_file()]
(OUT/'vhs_next_s01_targeted_evidence.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'hash_checked_files':len(baseline),'matches_prior_S0':sum(v['matches_S0_snapshot'] is True for v in baseline.values()),'mismatch_S0':[p for p,v in baseline.items() if v['matches_S0_snapshot'] is False], 'daily_metadata':facts['daily_package_metadata'],'MQ_sheet_names':facts['MQ_book']['sheet_names'],'daily_headers_only':facts['daily_headers_only'],'prediction_columns':facts['frozen_prediction_columns'],'new_candidate_target_values_accessed':False},ensure_ascii=False,indent=2))
