"""Freeze the authorized once-only R1 execution BEFORE any real fitting."""
from common import *

def main():
    if (HERE/'s1a_r1_execution_manifest.json').exists(): raise RuntimeError('Already frozen; do not restart the experiment')
    old=load(REPORTS/'vhs_next_s01_s1a_design_contract.json')
    v2=load(R0/'protocol_v2.json')
    tests=load(HERE/'executor_synthetic_tests.json')
    if not tests['pass']: raise RuntimeError('New executor synthetic tests failed')
    expectations=load(R0/'integrity_after.json')['hashes']
    expectations.update({k:v['sha256'] for k,v in load(R0/'delivery_manifest.json').items()})
    expectations[(R0/'delivery_manifest.json').relative_to(ROOT).as_posix()]=sha(R0/'delivery_manifest.json')
    mismatch=[k for k,v in expectations.items() if sha(ROOT/k)!=v]
    if mismatch: raise RuntimeError({'historical_hash_mismatch':mismatch})
    dump(HERE/'integrity_before.json',{'files':len(expectations),'hashes':expectations,'mismatch':[]},exclusive=True)
    substantive={
        'models':v2['primary']['models']=={k:old['models'][k] for k in ('S1A-0','S1A-1')},
        'folds':v2['folds']==old['folds'],
        'windows':v2['primary']['windows']==old['regimes']['REGIME_2_PAST_ONLY']['features'],
        'support':v2['primary']['common_support']==old['common_support'],
        'decisions':v2['primary']['decision_rules']==old['decision_rules'],
        'uncertainty':v2['primary']['uncertainty']==old['uncertainty'],
        'input':v2['input']==old['input'],
        'original_contract':sha(REPORTS/'vhs_next_s01_s1a_design_contract.json')==v2['original_contract']['sha256'],
        'r0_ready':load(R0/'r0_validation.json')['ready_for_execution_review']}
    if not all(substantive.values()): raise RuntimeError({'protocol_conflict':substantive})
    if old['input']['sha256']!='0aff15d0f6b355ee3516289b20e2daa137958b0fc926525792fbf8e54eb9920e': raise ValueError('Unauthorized input')
    if sha(ROOT/old['input']['path'])!=old['input']['sha256']: raise ValueError('Source drift')
    config={'phase':'VHS-NEXT-S1A-R1','real_execution_authorized':True,
            'authorization':'explicit user R1 request; one fixed retrospective development evaluation only',
            'EVIDENCE_LEVEL':'PRE_SPECIFIED_POST_EXPOSURE_DEVELOPMENT_ANALYSIS',
            'STRICT_ZERO_SHOT':False,'INDEPENDENT_FINAL_TEST':False,'CAUSAL_TRANSPORT_IDENTIFIED':False,
            'input':old['input'],'v2_contract_path':(R0/'protocol_v2.json').relative_to(ROOT).as_posix(),
            'v2_contract_sha256':sha(R0/'protocol_v2.json'),
            'same_day_secondary_enabled':True,'F2_enabled':True,'ownpast_executed':False,
            'placebo_k':v2['placebo']['k_days'],'source_anchor_months':True,
            'residual_R2_definition':'1-SSE/sum((observed-minus-training-calendar - mean(observed-minus-training-calendar))^2)',
            'F2_scope':'past-only fixed monthly upstream transform; no same-day F2 extra analysis',
            'bootstrap':{'replicates':10000,'seed':20261011,'block_days':[30,60],
                         'circular':[True,False],'scope':'each predeclared paired contrast; per-year and equal-year macro; conditional on fitted models'},
            'substantive_conflicts':[],'phase_metadata_resolution':'R0 execution bans and same-day not-run statements are stage-specific; R1 authorization enables only named methods',
            'frozen_R1_reference':'not re-evaluated: R1 restricts new numerical input to the one authorized CSV',
            'no_model_search':True,'GPU':False,'E5I1':False}
    dump(HERE/'execution_config.json',config,exclusive=True)
    dump(HERE/'environment.json',environment(),exclusive=True)
    files=[HERE/n for n in ('common.py','data_roles.py','same_day.py','fit_predict.py','score_results.py','preflight.py','test_executor.py')]
    files += [R0/'methods_v2.py',R0/'protocol_v2.json',REPORTS/'vhs_next_s01_mq_free_s1a_protocol.md',
              REPORTS/'vhs_next_s1a_r0_protocol_v2.md',REPORTS/'vhs_next_s01_s1a_design_contract.json',
              HERE/'environment.json',HERE/'executor_synthetic_tests.json']
    manifest={'phase':'VHS-NEXT-S1A-R1','frozen_at':now(),'protocol_checks':substantive,
              'frozen_hashes':{p.relative_to(ROOT).as_posix():sha(p) for p in files},
              'execution_config_sha256':sha(HERE/'execution_config.json'),
              'input_sha256':config['input']['sha256'],'fit_has_not_started':True,
              'evaluation_has_not_started':True,'substantive_conflicts':[]}
    dump(HERE/'s1a_r1_execution_manifest.json',manifest,exclusive=True)
    event('EXECUTOR_FROZEN',manifest_sha256=sha(HERE/'s1a_r1_execution_manifest.json'),
          substantive_conflicts=[],real_fit_started=False,environment_sha256=sha(HERE/'environment.json'))
    (REPORTS/'vhs_next_s1a_r1_protocol_preflight.md').write_text(
        '# R1执行前协议核对\n\n三份权威协议及原设计契约已核对，无实质性冲突。原模型、窗口、训练/评分支持、2%阈值、代价门槛及bootstrap规则逐字段一致。\n\n'
        'R0“不执行真实数据”和same-day“本轮不执行”是R0阶段元数据；用户R1明确授权相应固定实验。非环绕bootstrap从可选敏感性变为本轮必须执行，方法不改。'
        '新数值输入仅授权CSV，因此不读取旧R1参考预测；不执行Own-Past。\n\n'
        '真实拟合前已冻结执行器、配置、环境及权威协议hash；所有折预测及参数保存封存后才开启独立评分进程。'
        '共享CSV可信拆分层接触原行字符串，模型worker只读feature/train视图；此为过程隔离而非OS安全沙箱。\n','utf-8')
    print({'frozen':True,'historical_protected_files':len(expectations),'substantive_conflicts':[]})

if __name__=='__main__': main()
