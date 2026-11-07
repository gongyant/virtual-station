"""Check deliverable completeness, evidence paths, numeric audit gates and hashes."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'research_next/vhs_transfer'
expected=['source_inventory','provenance_audit','leakage_audit','topology_audit','physics_baseline_inventory','research_protocol','validation_report']
reports=[BASE/'reports'/f'vhs_next_s0_{n}.md' for n in expected]
for p in reports:assert p.is_file() and len(p.read_text(encoding='utf-8'))>500,p
broken=[];anchors=0
for p in reports+[BASE/'physics/physics_baseline_specification.md']:
    text=p.read_text(encoding='utf-8');assert '\ufffd' not in text,p
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith('http'):continue
        m=re.fullmatch(r'(.+?):(\d+)',target);path=Path(m[1] if m else target)
        if not path.is_file():broken.append(target)
        elif m:
            anchors+=1;assert 1<=int(m[2])<=len(path.read_text(encoding='utf-8',errors='replace').splitlines()),target
assert not broken,broken
facts=json.loads((BASE/'data_audit/live_audit_facts.json').read_text(encoding='utf-8'))
assert all(v['max_abs_diff']==0 and v['missing_pairs']==0 and v['rows']==2191 for v in facts['daily_raw_to_processed'].values())
assert all(v==0 for v in facts['bd1m_mapping'].values())
assert all(v['sha_match'] and v['bytes_match'] for v in facts['e5a_manifest_check'])
assert facts['raw_hydrorivers_check']['matched_reaches']==68 and not facts['raw_hydrorivers_check']['bad_next_down']
assert facts['reach_topology']['sequential_edges_match']
assert all(v['max_abs_diff']<5.01e-9 and v['missing_mask_equal'] for v in facts['incremental_tminus1_checks'].values())
syn=json.loads((BASE/'tests/synthetic_results.json').read_text(encoding='utf-8'));assert syn['passed']==7 and syn['failed']==0
boundary=json.loads((BASE/'tests/synthetic_input_boundary.json').read_text(encoding='utf-8'));assert all(v['status']=='PASS' for v in boundary['results'])
integrity=json.loads((BASE/'data_audit/integrity_result.json').read_text(encoding='utf-8'));assert integrity['unchanged']
status=(BASE/'reports/vhs_next_s0_status.txt').read_text(encoding='utf-8');assert 'READY_FOR_VHS_NEXT_S1=false' in status
manifest={p.relative_to(ROOT).as_posix():{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in BASE.rglob('*') if p.is_file() and p.name not in ['delivery_manifest.json','delivery_validation.json','validate_delivery.log']}
(BASE/'data_audit/delivery_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
result={'delivery_complete':True,'report_count':len(reports),'broken_local_links':broken,'checked_source_line_anchors':anchors,'E5A_source_matches':len(facts['e5a_manifest_check']),'historical_files_unchanged':integrity['checked_files'],'synthetic_physics_passed':7,'synthetic_boundary_modes_passed':2,'real_data_models_trained':False,'ready_for_S1':False}
(BASE/'reports/delivery_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
