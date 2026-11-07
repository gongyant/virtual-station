"""Validate S0.1 documents/design/hashes only. Never parses any flow data."""
import hashlib,json,re,sys
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'research_next/vhs_transfer';OUT=BASE/'reports'
sys.stdout.reconfigure(encoding='utf-8')
required=['p0_resolution','mq_provenance_decision','observation_metadata','protocol_identity_matrix','blind_test_feasibility','mq_free_s1a_protocol','validation_report']
headings=['## 已有证据','## 本轮新增核查或设计','## 仍未解决','## 对后续实验的影响']
broken=[];anchors=0
for name in required:
    path=OUT/f'vhs_next_s01_{name}.md';text=path.read_text(encoding='utf-8')
    assert all(h in text for h in headings),name
    assert '\ufffd' not in text and len(text)>500,name
    for target in re.findall(r'\]\(([^)]+)\)',text):
        if target.startswith('http'):continue
        m=re.fullmatch(r'(.+?):(\d+)',target);p=Path(m[1] if m else target)
        if not p.is_file():broken.append(target)
        if m and p.is_file():
            anchors+=1;assert 0<int(m[2])<=len(p.read_text(encoding='utf-8',errors='replace').splitlines()),target
assert not broken,broken
C=json.loads((OUT/'vhs_next_s01_s1a_design_contract.json').read_text(encoding='utf-8'))
assert C['execution_allowed_this_phase'] is False and C['real_data_models_trained'] is False
assert C['evaluation_identity']=='RETROSPECTIVE_DEVELOPMENT_ANALYSIS'
assert C['input']['feature_view']==['date','Q_input_byblk']
assert set(C['models'])=={'S1A-0','S1A-1','S1A-2'}
assert C['models']['S1A-0']['hyperparameter_search'] is False
assert C['models']['S1A-1']['model_search'] is False
assert C['models']['S1A-2']['parameter_refit'] is False and C['models']['S1A-2']['prediction_rerun'] is False
assert C['models']['S1A-2']['primary_contrast_member'] is False
assert 'NOT_COMPARABLE_INPUT_REGIME' in C['models']['S1A-2']['regime2_role']
assert C['folds'][0]['R1_reference_role']=='EXCLUDE_TARGET_CALIBRATION_OVERLAP'
for f in C['folds']:
    a,b,c,d=[date.fromisoformat(f[k]) for k in ['fit_start','fit_end','development_start','development_end']]
    assert a<=b<c<=d
    assert f['date_count_train_before_missing_Q_check']==(b-a).days+1
    assert f['date_count_development_before_missing_Q_check']==(d-c).days+1
    assert f['fit_start']=='1978-01-31'
for key,minlag in [('REGIME_1_SAME_DAY',0),('REGIME_2_PAST_ONLY',1)]:
    features=C['regimes'][key]['features'];assert len(features)==3
    assert all(min(f['lags'])>=minlag and max(f['lags'])<=30 for f in features)
assert 30==max(k for f in C['regimes']['REGIME_2_PAST_ONLY']['features'] for k in f['lags'])
assert len(C['folds'])==C['uncertainty']['development_years']==3
assert C['uncertainty']['population_significance_claim_allowed'] is False
assert C['readiness']=={'S1A':'CONDITIONAL','S1B':'BLOCKED','S1C':'BLOCKED'}
assert all(not r['values_accessed_this_phase'] for r in json.loads((OUT/'vhs_next_s01_blind_candidates.json').read_text(encoding='utf-8')))
assert json.loads((OUT/'vhs_next_s01_targeted_evidence.json').read_text(encoding='utf-8'))['candidate_labels_parsed'] is False
before=json.loads((OUT/'vhs_next_s01_integrity_before.json').read_text(encoding='utf-8'))
S0=json.loads((BASE/'data_audit/historical_after.json').read_text(encoding='utf-8'))
S0DEL=json.loads((BASE/'data_audit/delivery_manifest.json').read_text(encoding='utf-8'))
def digest(p):return {'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for rel,row in before.items():
    actual=digest(ROOT/rel)
    assert actual=={k:row[k] for k in ['bytes','sha256']},rel
    if rel in S0:assert actual==S0[rel],rel
    if rel in S0DEL:assert actual==S0DEL[rel],rel
frozen=json.loads((ROOT/'outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json').read_text(encoding='utf-8'))
for row in frozen['source_files'].values():
    rel=row['path'].replace('\\','/');assert digest(ROOT/rel)=={k:row[k] for k in ['bytes','sha256']},rel
status=dict(line.split('=',1) for line in (OUT/'vhs_next_s01_status.txt').read_text(encoding='utf-8').splitlines() if '=' in line)
for k in ['REAL_DATA_MODELS_TRAINED','NEW_GPU_TASKS_RUN','FROZEN_RESULTS_CHANGED','EXISTING_MANUSCRIPT_CHANGED','NEW_CANDIDATE_TARGET_VALUES_ACCESSED','E5I1_EXECUTED']:assert status[k]=='false',k
assert status['VHS_NEXT_S01_COMPLETE']=='true' and status['MQ_PROVENANCE_VERIFIED']=='false' and status['NEW_BLIND_TEST_AVAILABLE']=='false'
result={'validation':'PASS_WITH_UNRESOLVED_PROVENANCE_AND_BRANCH_GATES','markdown_reports':7,'status_file_present':True,'all_reports_distinguish_existing_new_unresolved_impact':True,'broken_links':broken,'checked_source_line_anchors':anchors,'design_only':True,'fixed_time_folds_checked':3,'regime_feature_boundaries_checked':True,'R1_comparison_limits_checked':True,'targeted_historical_and_S0_files_unchanged':len(before),'E5A_registered_source_hashes_match':len(frozen['source_files']),'no_full_S0_rerun':True,'candidate_target_values_parsed':False,'real_models_trained':False,'GPU_tasks_run':False,'readiness':C['readiness'],'scope':'Document/design/hash checks; not model-performance or physical-validation PASS'}
(OUT/'vhs_next_s01_delivery_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={p.relative_to(ROOT).as_posix():digest(p) for p in OUT.glob('vhs_next_s01_*') if p.is_file() and p.name not in ['vhs_next_s01_delivery_manifest.json','vhs_next_s01_validation.log']}
(OUT/'vhs_next_s01_delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
