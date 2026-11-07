"""Final R2U1/P6A release seal and explicit completed/blocked/not-run accounting."""
import json,hashlib,csv,sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_r2u1_p6a');P=R/'p6';LAB=R.parent;P4=LAB/'p4_final_reconstruction'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jl(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def jw(n,v):(R/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def write(n,t):(R/n).write_text(t,encoding='utf-8')
tests=jl(R/'R2U1_P6A_TEST_RESULTS.json');assert tests['failed']==0
frozen=jl(R/'evidence/HISTORY_BEFORE.json');n=0
for root,entry in frozen.items():
 for rel,h in entry['files'].items():assert sha(Path(root)/rel)==h,rel;n+=1
 assert sha(Path(root)/entry['manifest'])==entry['manifest_sha256']
old=jl(LAB/'vhs_web_r2_host_integration/evidence/HISTORY_BEFORE.json');orig=next((k,v) for k,v in old.items() if k.endswith('v0.6_four_layer_platform'));bad=[name for name,h in orig[1]['files'].items() if sha(Path(orig[0])/name)!=h];assert not bad
jw('HISTORICAL_INTEGRITY_REPORT.json',{'verified_current_run_files':n,'verified_current_run_root_manifests':8,'changed':[],'original_v06_reference_files':len(orig[1]['files']),'original_v06_changed':bad,'reference_source':'frozen R2 history manifest; current verification, not a fabricated new before state','teacher_Q_read':False,'P4_all108_models_unchanged':True})
reg=jl(LAB/'vhs_web_r1_public_results_bridge/PUBLIC_MODEL_REGISTRY.json');release=reg['models'][0]['model_release_id'];pred=P/'runs/P6A_V2_2018_2019';score=P/'runs/P6A_V2_2018_2019_SCORING'
jw('p6/P6_RUN_MANIFEST.json',{'run_id':'P6A_V2_2018_2019','classification':'PUBLIC_DATA_P6A_TEMPORAL_EXTERNAL_VALIDATION','quality_scope':'QUALIFIED_DESCRIPTIVE_PROVIDER_CURATED_NO_DAILY_FLAGS','gauges_scored':[818],'gauges_blocked':[611,688],'models':['C0+PT','P2-L1'],'model_release_id':release,'frozen_model_hashes':jl(P/'P6_PROTOCOL_FROZEN.json')['frozen_models'],'test_period':['2018-01','2019-12'],'actual_training_end':'2017-11','nominal_training_cutoff':'2017-12','protocol_sha256':sha(P/'P6_PROTOCOL_FROZEN.json'),'admission_sha256':sha(P/'P6_ADMISSION_FROZEN.json'),'prediction_seal_sha256':sha(pred/'SHA256SUMS.txt'),'scoring_seal_sha256':sha(score/'SHA256SUMS.txt'),'fit_calls':0,'new_predictions':48,'new_label_months':24,'scientific_inference':'one basin two years; no general efficacy confirmation','Qobs_exported':False,'SYRDARYA':'NOT_GRANTED_NOT_ACCESSED','ERA5_land_replaced_by_EOBS':False})
status={'completed':['R2U1_A1_unique_spatial_fields_and_scientific_statuses','R2U1_A2_selection_linked_source_summary','R2U1_A3_2446_frozen_predictions_exact_decomposition','R2U1_A4_108_alpha_standardization_readonly_audit','P6_818_fixed_V2_prediction_and_scoring_2018_2019_QUALIFIED_DESCRIPTIVE','Historical_V1_V2_mechanism_diagnostics'],'blocked':{'P6_611':'official daily checked Q unavailable; EStreams only2018-01,2020-02 within2018-2020, month/day QC unverifiable','P6_688':'official download not ready/Request Rejected; EStreams incomplete monthly support','P6_2020':'no same-processing ERA5-Land2020 in downloaded archive','production_display':'NOT_GRANTED'},'not_executed':['any_model_fit','hyperparameter_retuning','grid_expansion','P4_V1_or_V2_result_overwrite','teacher_Q_read_or_mount','P6_other24_stations','new_interval_calibration','business_certification','reach_prediction'],'predictions':48,'P6_scored_stations':1,'P6_scored_months':24,'fit_calls':0,'tests_passed':tests['passed'],'tests_total':tests['total'],'software_PASS_not_scientific_validation':True};jw('FINAL_STATUS.json',status)
write('COMPLETION_REPORT_ZH.md',f'''# VHS-R2U1-P6A交付

本轮日期：2026-11-02（Asia/Singapore）。**真实完成：原主站候选修复 + 冻结预测解释 + ID818的2018–2019带质量限制独立评分。没有重新训练。**

候选主站：http://127.0.0.1:8793/#/overview?dataset=LAMAH_CE_PUBLIC_V1

## 六个最终问题

1. **为什么不同年份预测高度相似？** 十二个月训练期Q均值固定逐年复用，年际变化只能经P/T/L1异常修正进入。ID2与模板相关0.9909，ID533为0.9971，气象修正RMS约为模板标准差的15.2%与9.8%。但失败站不一定模板主导，不能把所有负结果归因于季节模板。2446条旧预测复算误差0；详见FROZEN_PREDICTION_DECOMPOSITION_REPORT_ZH.md及diagnostics。
2. **重复风险字段修好了吗？** 是。原生成器重复插入导致两字段各出现5次；独立候选生成器整体替换卡片且可重复运行，不再累加。两字段各只出现1次，历史评价、NSE/KGE、输入支持、经验区间、新时期验证、业务认证分开显示，NOT_CERTIFIED保留。修复前后真实截图与字段对照已交付。
3. **哪些站有气象增量证据？** 旧V1中L1相对C0+PT改善15/25站；ID171/185三年均改善、留一年敏感性仍正，技能分别+23.93%/+29.85%，但185约80.54%年度差异集中于一个年份。ID9技能+17.49%；ID2只有+1.11%且年度不稳。ID533虽NSE高但L1技能−3.72%。这些是旧冻结测试的描述性证据，不是普遍或因果认证。
4. **P6取得了哪些真实新数据？** 三站同源ERA5-Land均有2018–2019完整24月；818取得官方CAMELS-CH实测日Q至2020，2018–2019共730日、2020另366日。EStreams818有2018–2020月索引36月；611/688各只有2018-01和2020-02两个非空月，目录标到2023不等于连续有效覆盖。后两站官方日均Q下载未成功，不放宽质量门槛。
5. **原P4-V2完成新时期独立评分了吗？** 仅818完成24月、两模型48条固定参数预测。C0+PT NSE/KGE=0.682576/0.695475；L1=0.691223/0.691412，MSE技能+2.724%。2018为−1.956%、2019为+5.082%、DJF为−52.187%（仅6月且绝对误差小）。L1 90%区间覆盖100%、均宽2.0302m³/s。来源无逐日QC标志，故为有质量限制的描述性独立验证；611/688以及27站整体尚未完成新时期评分。实际训练截止窗口2017-12，818最后训练标签为2017-11。预测先封存，评分后置且无Qobs批量导出。
6. **下一步最值得研究什么？** 先补齐官方新Q/QC与更多不同水系验证样本；模型上优先检验固定季节截距的时期漂移/基流适应不足和寒季储水记忆。不能直接认定融雪、水库或结冰为原因。保持C0+PT/L1并列参照，后续新模型预冻结公式，使用未看过的更晚时期检验；不刷旧2015–2019分数，不临时改SNOW阈值。

## 验收与边界

针对性修复/复算验收{tests['passed']}/{tests['total']}通过，包括来源选择联动、状态分离、真实浏览器页面、P6指标/Interval Score独立复核、预测先封存、输入不含Q及历史哈希。早期两项侧栏定位测试因检测器只在主视图查找侧栏文字失败，实际字段检查已通过；原失败证据保留，修正检测位置后通过。软件通过不等于科学验证通过。

P0–P5、R1、R2本轮{n}个封存文件与8份manifest未改变；原v0.6另108个历史参考文件一致，108个模型（V1/V2）保持原哈希。P4-V1原成绩、P4-V2参数、R2已验收候选都没有覆盖。原SYRDARYA权限和教师Q隔离保留，正式生产展示与动态执行仍403。

已完成、受阻、未执行逐项见FINAL_STATUS.json。运行与回滚见RUN_AND_ROLLBACK.md；精确源码差异见R2U1_CODE_DIFF.patch。停止8793即可回滚本轮候选，不需恢复R2文件。真实P6预测与评分分开封存在p6/runs，许可、来源和当前选择不写入锡尔河成绩表。

主要报告：FROZEN_PREDICTION_DECOMPOSITION_REPORT_ZH.md、ALPHA_108_MECHANISM_REPORT_ZH.md、P6_DATA_ADMISSION_REPORT_ZH.md、P6_INDEPENDENT_VALIDATION_REPORT_ZH.md、R2U1_FIELD_COMPARISON.md、NEXT_EXPERIMENT_DECISION.md。
''')
write('SOURCE_LICENSE_AND_CITATION.md','''# 来源、许可与展示边界

- 原LamaH-CE v1.0：https://zenodo.org/records/5153305 ，DOI10.5281/zenodo.5153305；沿用冻结CC BY-SA4.0与署名记录，气象为其ERA5-Land流域聚合。P4模型和训练来源未替换。
- CAMELS-CH v0.9：https://zenodo.org/records/15025258 ，DOI10.5281/zenodo.15025258；官方API声明CC BY4.0，引用Höge等CAMELS-CH数据集及FOEN/BAFU原观测机构。仅observation_based discharge_vol(m3/s)作为P6新Q，CAMELS气象和模拟Q不进入模型。
- EStreams v1.4：https://zenodo.org/records/17598150 ，DOI10.5281/zenodo.17598150；官方API声明CC BY-NC4.0，引用do Nascimento等数据集及对应提供机构。其E-OBS气象未下载未使用，月索引未进入主评分。局部ZIP读取仅验证成员CRC32与内容SHA256，不声称验证完整大归档MD5。
- FOEN2304主站：https://www.hydrodaten.admin.ch/de/seen-und-fluesse/stationen-und-daten/2304 ，用于官方站码、坐标和单位核查；当前冬季冰冻警告不是2018–2019错误原因的证据。
- 德国GKD/HND官方10035801和16602303站：站点身份可核验，日均Q下载未成功；不把EStreams目录日期当实测支持。没有绕过下载拒绝，没有发送邮件。

所有新结果仅作本轮非商业科研核查和隔离候选本地展示，不能继承为生产display许可或模型动态执行许可。来源明细、访问回执、字节范围与哈希在external，新的独立评分与旧V1/V2成绩分开保存。没有接触私有教师Q。
''')
write('code/verify_delivery.py','''import hashlib,json\nfrom pathlib import Path\nr=Path(__file__).resolve().parents[1];bad=[];n=0\nfor l in (r/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():\n h,s=l.split('  ',1);p=r/s;n+=1\n if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=h:bad.append(s)\nprint(json.dumps({'files':n,'mismatches':bad,'status':'PASS' if not bad else 'FAIL'}));raise SystemExit(bool(bad))\n''')
entries=[]
for p in sorted(R.rglob('*')):
 rel=p.relative_to(R)
 if not p.is_file() or p==R/'SHA256SUMS.txt' or any(x in {'runtime','logs','tmp','var','__pycache__'} for x in rel.parts):continue
 entries.append((sha(p),rel.as_posix()))
write('SHA256SUMS.txt',''.join(f'{h}  {p}\n' for h,p in entries));print(json.dumps({'sealed_files':len(entries),'tests':tests['passed'],'prediction_records':48,'P6_scored_stations':1,'fit_calls':0},ensure_ascii=False))
