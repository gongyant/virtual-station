"""Generate S0.1 P0 decisions and fixed S1A design. No model implementation/fit."""
import hashlib,json,re,sys
from datetime import date,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];BASE=ROOT/'research_next/vhs_transfer';OUT=BASE/'reports'
sys.stdout.reconfigure(encoding='utf-8')
E=json.loads((OUT/'vhs_next_s01_targeted_evidence.json').read_text(encoding='utf-8'))
BPATH=OUT/'vhs_next_s01_integrity_before.json';B=json.loads(BPATH.read_text(encoding='utf-8'))
S0=json.loads((BASE/'data_audit/historical_after.json').read_text(encoding='utf-8'))
DELIVERY0=json.loads((BASE/'data_audit/delivery_manifest.json').read_text(encoding='utf-8'))
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return {'bytes':p.stat().st_size,'sha256':h.hexdigest()}
# Supplement files already recorded as opaque hashes by the metadata-only probe.
# Keep original first-observation hashes, never replace a previously saved entry.
for rel,row in E['historical_scoring_artifacts_exist'].items():
    if not row['exists'] or rel in B:continue
    h={k:row[k] for k in ['bytes','sha256']}
    B[rel]={**h,'absolute_path':str(ROOT/rel),'matches_S0_snapshot':h==S0[rel] if rel in S0 else None,'matches_S0_source_manifest':None,'first_observed':'opaque hash captured by S0.1 metadata probe'}
BPATH.write_text(json.dumps(B,ensure_ascii=False,indent=2),encoding='utf-8')
changed=[];s0_mismatch=[];s0_artifact_mismatch=[]
for rel,v in B.items():
    current=digest(ROOT/rel)
    if current!={k:v[k] for k in ['bytes','sha256']}:changed.append(rel)
    if rel in S0 and current!=S0[rel]:s0_mismatch.append(rel)
    if rel in DELIVERY0 and current!=DELIVERY0[rel]:s0_artifact_mismatch.append(rel)
assert not changed and not s0_mismatch and not s0_artifact_mismatch,(changed,s0_mismatch,s0_artifact_mismatch)
integrity={'scope':'targeted historical inputs/metadata/freeze/manuscript + consulted S0 artifacts; not a repeat of full S0 audit','files_checked':len(B),'matched_S0_historical_snapshot':sum(rel in S0 for rel in B),'matched_S0_delivery_manifest':sum(rel in DELIVERY0 for rel in B),'changed_this_phase':changed,'different_from_S0_snapshot':s0_mismatch,'changed_S0_artifacts':s0_artifact_mismatch,'full_S0_baseline_reused_files':2398,'full_S0_baseline_rehashed_this_phase':False,'E5A_registered_sources_checked':17,'large_figures_models_not_rehashed':'S0 integrity reused; no file mutations in those paths','git_prior_worktree_state':'UNVERIFIED; no Git repair attempted'}
(OUT/'vhs_next_s01_integrity_result.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding='utf-8')
def link(rel,label=None):return f'[{label or rel}]({(ROOT/rel).as_posix()})'
def ev(rel,pattern):
    for i,line in enumerate((ROOT/rel).read_text(encoding='utf-8',errors='replace').splitlines(),1):
        if re.search(pattern,line):return f'[{rel}:{i}]({(ROOT/rel).as_posix()}:{i})'
    raise ValueError((rel,pattern))
header='''
阶段：VHS-NEXT-S0.1 — P0 Resolution and Scientific Experiment Readiness。
日期：2026-10-11，Asia/Singapore。项目根目录：`E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
本轮仅针对S0已定位证据核查、元数据/历史使用可行性和协议设计。未进行真实模型训练、调参、真实预测重跑、GPU任务、S1A实验或E5I1。
`CONFIRMED`仅确认指定事实；来源复制确认不等于物理独立性确认。所有未证实事项保持未证实。
'''
def write(slug,title,existing,new,unresolved,impact):
    text=f'# VHS-NEXT-S0.1｜{title}\n\n{header}\n## 已有证据（继承S0，不算本轮发现）\n\n{existing.strip()}\n\n## 本轮新增核查或设计\n\n{new.strip()}\n\n## 仍未解决\n\n{unresolved.strip()}\n\n## 对后续实验的影响\n\n{impact.strip()}\n'
    (OUT/f'vhs_next_s01_{slug}.md').write_text(text,encoding='utf-8')
mq_questions=[
 {'id':'MQ1','question':'physical_reference_q原始工作簿来源','status':'CONFIRMED','finding':'本地Q-新疆.xls/2005-支流/MQ-DSK-2005-SB，DSK B列；此为导入源，非最初生成来源'},
 {'id':'MQ2','question':'MQ是否按工作簿值直接复制导入','status':'CONFIRMED','finding':'extract_multisite_runoff_2005读取reference后赋给physical_reference_q_m3s，再改名为tensor physical_reference_q；没有在此计算物理MQ'},
 {'id':'MQ3','question':'原始MQ生成脚本是否找到','status':'UNVERIFIED','finding':'在S0指向的导入/血缘/使用链中未找到；不把局部未发现扩张成全盘不存在证明'},
 {'id':'MQ4','question':'能否证明MQ未用目标站Q校准','status':'UNVERIFIED','finding':'缺生成输入、校准站/年/参数记录；既不能证明独立，也不能断言确有目标校准'},
 {'id':'MQ5','question':'MQ是否含目标站历史插补、平滑或模拟结果','status':'UNVERIFIED','finding':'复制链不修改值；工作簿之前的处理及MQ含义无证据，SB/RS字样不能替代模型说明'},
 {'id':'MQ6','question':'是否有可验证供数者、观测时期与单位说明','status':'UNVERIFIED','finding':'已知2005表头及文件user_name=MECHREVO只能证文件内标记，不能认证提供者/水文日/单位；未见正式供数说明'},
 {'id':'MQ7','question':'把本仓库导入器称为MQ独立物理生成模型','status':'CONTRADICTED','finding':'源码在该位置直接复制现成列；这只否定导入器现场生成MQ，不否定未知外部存在物理模型'},
 {'id':'MQ8','question':'S1A主输入是否需要MQ','status':'NOT_APPLICABLE','finding':'新主比较排除MQ及其派生量，生成链不是S1A主比较的数值输入依赖'}]
(OUT/'vhs_next_s01_mq_decision.json').write_text(json.dumps(mq_questions,ensure_ascii=False,indent=2),encoding='utf-8')
mq_lines='\n\n'.join(f"**{q['id']} {q['question']}：`{q['status']}`。** {q['finding']}。" for q in mq_questions)
write('mq_provenance_decision','MQ来源逐问题决策',
 f'''S0确认工作簿→CSV→NPZ的复制链一致，原始生成/校准链未确认。既有D5血缘记录同样阻断：{link('outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md')}。本轮不重做逐值比对。''',
 f'''{mq_lines}

本轮只核对已知2005支流/干流表头和导入赋值，不读取其他sheet的目标流量。源码证据：{ev('scripts/extract_multisite_runoff_2005.py','raw_reference =')}; {ev('scripts/extract_multisite_runoff_2005.py','physical_reference_q_m3s')}; {ev('scripts/prepare_multisite_gnn_bundle_2005.py','physical_reference_q_m3s.*physical_reference_q')}。
文件SHA-256：`9bd677ae904e3520fd89f759589ec3194fbaff8f10b6f9ccca5a63f8c78efe46`，与S0/既有元数据一致。worksheet表头的2005是本地时期标记，不是正式数据采集证明。''',
 '''没有MQ公式/可执行生成脚本、原始输入清单、校准站点及年份、目标标签是否参与的记录、参数/版本、提供者和原始变量单位。需要原提供者提供这些最小记录；不得通过Q相关性或数值范围反推。''',
 '''`MQ_PROVENANCE_VERIFIED=false`；`MQ_FREE_PRIMARY_PROTOCOL=true`。MQ及MQ派生残差锚点、physics loss、station_reference归一化全部排除出S1A主比较。不能把“MQ-free”改称strict zero-shot，因为S1A仍使用DSK训练标签。MQ分支及S1C继续阻断。''')
metadata_rows=[
 {'item':'Q单位m³/s','primary':'UNVERIFIED','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'原始头为Q/BYBLK/DSK、OQ；原单位检查无打印单位。m³/s来自项目契约/评价及导入列名，不是原始计量证明'},
 {'item':'日平均还是某时刻瞬时值','primary':'UNVERIFIED','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'日数据文件名和逐日索引支持daily cadence；daily mean流量是现有routing解释，不等于已证实daily mean'},
 {'item':'水文日界/时区/时间戳意义','primary':'UNVERIFIED','project':'UNVERIFIED','code':'ASSUMED_BY_EXISTING_CODE','evidence':'read_flow_source只pd.to_datetime；build_bundle normalize到日期，无水文日/时区换算'},
 {'item':'两站共享同一日期键','primary':'VERIFIED_FROM_PRIMARY_SOURCE','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'原工作簿同一Q日期列、BYBLK/DSK两列；此项只确认文件布局'},
 {'item':'两站真实日统计窗口相同','primary':'UNVERIFIED','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'同表对齐不能证明原始汇编前两站用了相同起止时刻'},
 {'item':'站名/站号项目内映射','primary':'UNVERIFIED','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'配置/KMZ衍生映射：00705600巴音布鲁克，00705700大山口；未见正式编号名录/站址沿革认证'},
 {'item':'物理模型单位与原Q真实单位一致','primary':'UNVERIFIED','project':'SUPPORTED_BY_PROJECT_METADATA','code':'ASSUMED_BY_EXISTING_CODE','evidence':'现有代码按Q=m³/s、tau=day、S=Q·day计算，代码内部量纲可一致，但原Q单位/日均身份未证实'}]
(OUT/'vhs_next_s01_observation_metadata_decision.json').write_text(json.dumps(metadata_rows,ensure_ascii=False,indent=2),encoding='utf-8')
metadata_table='| 项目 | 原始证据级别 | 项目支持级别 | 代码级别 |\n|---|---|---|---|\n'+'\n'.join(f"| {r['item']} | {r['primary']} | {r['project']} | {r['code']} |" for r in metadata_rows)
write('observation_metadata','观测单位、日界与站点证据等级',
 f'''4382站日加工一致、无项目层目标插补是S0既有结论。本轮仅读取原始表的前两行文字与docProps，不再次统计Q。历史单位与时间口径记录：{link('outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/daily_time_definition_audit.md')}、{link('outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/raw_workbook_structure_audit.json')}。''',
 f'''{metadata_table}

逐项解释：
'''+ '\n\n'.join(f"- **{r['item']}**：{r['evidence']}。" for r in metadata_rows)+f'''

本轮直接核得原日工作簿 `creator=MECHREVO`、`lastModifiedBy=Tie`、创建 `2026-07-20T06:45:48Z`、修改 `2026-07-20T06:46:45Z`。这些是文件属性；不能当官方供数者、1978–1983采集时间或科学真实性证明，也不能因新文件日期推断数据伪造。
原两行：A1=Q、B1=BYBLK、C1=DSK；B2/C2=OQ，无单位/日界文字。已知旧结构审计没有单位单元格，本轮没有全面重新扫描工作表。
导入证据：{ev('src/vhs/io.py',r'out\["date"\].*to_datetime')}; 项目映射：{link('outputs/diagnosis_2005_snapshot/stage_d5_round2/source_audit/station_mapping_audit.csv')}。
关键区分：历史报告“同来源/同整编口径”可支持项目对齐，不能升级为两站真实水文日界相同的原始证明；不修改其历史文字。''',
 '''最少索取四类资料：①带机构/提供者身份的原始数据说明与版本；②Q单位、是否日平均/瞬时、统计方法及缺测/质控/人工订正说明；③两站各自日统计起止时刻、时区、时间戳标记起日/止日和历年变更；④正式站号—站名—站址沿革/测站位置对应。可为一份覆盖以上字段的正式说明，不要求虚构多个文件。MQ和外部月序列另需各自生成/来源说明。''',
 '''`DAILY_Q_METADATA_VERIFIED=false`。S1A可按已有日期键与数值Q约定做受限开发，RMSE/MAE/Bias标“项目Q数值单位，m³/s尚未由原始来源证实”；NSE/相对RMSE/PBIAS仍只解释为同源数值比较，不能认证物理量纲。日水量只报告数值日和/相对偏差，不转m³；峰时只解释为日期索引误差。不能声称实时可用、亚日物理时滞或真实水量闭合。''')
matrix='''| 信息/用途 | Protocol A 历史重建 | Protocol B 时间留出重建 | Protocol C strict ungauged/zero-shot |
|---|---|---|---|
| 目标站训练期Q | 允许监督及已声明校准 | 允许，仅早于开发/测试 | 禁止所有时期目标Q参与拟合/归一化/选模 |
| 目标站开发验证Q | 允许评分/开发选择，之后失去最终测试身份 | 允许在最终测试前开发选模 | 禁止目标站Q用于模型选择；仅source站验证 |
| 目标站测试Q | 只在冻结后评分 | 只在模型/代码冻结后一次评分 | 只在全部source训练/选择冻结后评价 |
| 测试期更早日期目标Q回填 | 禁止（不属于本轮缺测重建） | 禁止 | 禁止 |
| 目标站历史参数校准 | 允许但必须标明 | 允许仅训练期，不能用未来dev/test隐式校准 | 禁止目标专用Q校准参数/查表及其派生量 |
| 来源站训练数据 | 允许并记录使用范围 | 允许，按预先规定的时间边界 | 允许，source与target严格隔离 |
| 物理参考流量 | 生成链可核查，若含目标监督须计入A | 不能含测试信息，历史校准限train | 只能独立来源/合法source参数；未知MQ不可接受 |
| 上游观测 | 依声明制度及时间戳可用 | 同上；不能借目标未来修正 | 同上；上游不等于目标标签 |
| 气象信息 | 依时间可用性；后验再分析需标明 | 不含目标未来；forecast与reanalysis分层 | 合法独立气象可用，不能代入含目标Q的派生量 |
| 静态流域属性 | 允许，说明来源和历史代表性 | 同上，禁止用测试Q反推“静态参数” | 允许独立静态属性，禁止目标Q导出的目标专用参数 |
| 统计拟合/标准化范围 | 明确train，不使用最终评分标签 | 每个时间train折，完整feature selection也必须先于test | source训练范围；不能使用target Q统计量 |
'''
identity='''| 历史实验 | 实际身份（独立新表，不改旧名称） | 不可作出的主张 |
|---|---|---|
| E4 R1/R2 | A目标监督校准；E4A2只拟合1978–1981 | 不能C；旧tau不能当所有新外层折均未见目标 |
| Fourier6/月残差 | A目标残差监督，1982开发；E4C为冻结方法B式1983评价 | 不能C；不能再把已揭示1983给新方法当盲测 |
| 2005五站snapshot GNN/no-graph | 整站留出C设计意图，当前可见OQ路径遮蔽，但保留目标MQ | C未认证；不能把MQ复制源当独立物理源 |
| 早期1978–1983 base-bundle STGNN | 34站输入、目标遮蔽设计；wg_dis外部率定独立性未核实 | 不能自动认证C，也不能等同68河段图 |
| E1 persistence/E2 DSK_history | 目标观测辅助诊断，测试内过去Q作预测输入 | 不符合此表A/B/C缺测重建；不是无目标观测基线 |
| E1目标监督LR/RF、E2 BYBLK历史、E3 | A，源码按时间分区的历史开发 | 不是C；历史test揭示不能撤销 |
| Stage C P1/D5 M1/M2/M2R/M2C | A目标监督；D5为回顾性LOYO，部分折有未来训练年 | 不是时序B，不是C；M2C全六年筛选不能当独立外层选择 |
| 新S1A-0/1 | A下的按时序折开发，RETROSPECTIVE_DEVELOPMENT_ANALYSIS | MQ-free不是C；不称INDEPENDENT_FINAL_TEST |
'''
write('protocol_identity_matrix','协议信息边界与历史模型身份独立对照表',
 '''S0已经确认R1/R2/Fourier6使用目标站训练标签、2005目标MQ不独立、E1/E2目标历史输入及D5筛选限制。本轮不重新评价旧性能。''',
 f'''{matrix}

{identity}

A是历史重建的信息约束；B进一步要求严格时序和未揭示最终测试，不是“目标站不能有训练标签”。C是目标站标签/目标Q校准完全隔离，不能通过参数、参考锚点或scaler间接绕过。
现有GNN源码训练target mask证据：{ev('src/vhs/data.py',r'train_x\[:, target_mask, flow_idx\] = np.nan')}；早停用非目标节点：{ev('src/vhs/train.py','target_only=False')}；目标MQ训练约束：{ev('src/vhs/train.py','physics_mask =')}。源码路径检查继承S0，不证明历史checkpoint版本绑定或MQ独立。''',
 '''MQ与wg_dis内部校准来源、正式目标站编号和真正新最终测试仍未解决。当前源码的正确遮蔽不能替代对整个信息生成链的证明。''',
 '''S1A不需要先把所有历史分支变成C；应使用清晰A/开发身份执行受限主比较。B最终测试与C认证分别设门槛；不改历史模型名称，不把三个分支强制一起通过。''')
candidate_rows=[
 {'candidate':'1978–1983 BYBLK/DSK日数据','source':'data/raw/runoff/BYBLK-DSK日数据.xlsx','time_metadata':'1978-01-01..1983-12-31 inherited S0','station':'BYBLK, DSK','usage':'E1–E4及D5全六年开发/评价','blind_status':'CONTRADICTED_AS_NEW_BLIND','values_accessed_this_phase':False},
 {'candidate':'2000–2001支流OQ','source':'data/raw/runoff/Q-新疆.xls / 2000-支流','time_metadata':'2000-01-01..2001-12-01 per existing frozen metadata, not full two calendar years','station':'BYBLK, DSK','usage':'existing blind_scoring artifact present; S0 already records revealed','blind_status':'CONTRADICTED_AS_NEW_BLIND','values_accessed_this_phase':False},
 {'candidate':'2005五站OQ/MQ','source':'data/raw/runoff/Q-新疆.xls / 2005-支流,2005-干流','time_metadata':'merged 2005-01-02..10-31 per existing metadata; per-station ranges inherited S0','station':'BYBLK, DSK, ALAR, XQM, AQK','usage':'GNN train/dev/evaluation and Stage B/C diagnostics','blind_status':'CONTRADICTED_AS_NEW_BLIND','values_accessed_this_phase':False},
 {'candidate':'2011 Doc1/水位测流资料','source':'data/teacher_raw/Doc1.docx','time_metadata':'2011 identity inherited historical D5/S0; no document table parsed this phase','station':'known BYBLK/DSK material, station-specific metadata not newly revalidated','usage':'historical Stage D–D12 and D5 documented revealed material','blind_status':'CONTRADICTED_AS_NEW_BLIND','values_accessed_this_phase':False},
 {'candidate':'外部月序列其余区间','source':'data/raw/runoff/Q-dsk-byblk.xlsx','time_metadata':'1983 evaluation already revealed; other ranges not certified by this bounded check','station':'sheets BYBLK, DSK, Sheet3','usage':'E4D source audit/overlap; provenance/units and access history incomplete','blind_status':'UNVERIFIED_NOT_CERTIFIED','values_accessed_this_phase':False},
 {'candidate':'Q-新疆其他sheet别名/副本','source':'data/raw/runoff/Q-新疆.xls','time_metadata':'sheet names only DSK2000/BYBLK2000 and 2005 SB/RS variants; no new named year identified','station':'DSK/BYBLK named variants','usage':'alias or unseen range cannot be inferred without access history; no cell values opened','blind_status':'UNVERIFIED_NOT_CERTIFIED','values_accessed_this_phase':False},
 {'candidate':'新增站/流域观测','source':'bounded local runoff/teacher source inventory + prior additional-station registry','time_metadata':'no certified unused range identified','station':'Yanqi/intermediate1978–1983 not found per existing registry; no new source discovered','usage':'2005 ALAR/XQM/AQK already used, cannot relabel them unseen','blind_status':'NOT_FOUND_WITHIN_CHECKED_SCOPE','values_accessed_this_phase':False}]
(OUT/'vhs_next_s01_blind_candidates.json').write_text(json.dumps(candidate_rows,ensure_ascii=False,indent=2),encoding='utf-8')
candidates='\n\n'.join(f"- **{r['candidate']}**：`{r['blind_status']}`；来源 `{r['source']}`；时间元数据：{r['time_metadata']}。历史使用：{r['usage']}。" for r in candidate_rows)
write('blind_test_feasibility','新盲测可行性与封存方案',
 '''S0已指出1978–1983/2005及2000、2001、2011都存在揭示历史，新最终测试尚缺。此结论不因目录名sealed/blind或曾经predictions_frozen而改变。''',
 f'''本轮只列举 `data/raw/runoff/` 三个工作簿、`data/teacher_raw/Doc1.docx`，读取工作簿sheet名/docProps、既有source metadata、D5可用性注册及历史评分产物存在性。没有打开候选label CSV或新的目标数值，没有计算目标统计量或绘图；哈希是文件字节摘要，不是解析标签。

{candidates}

本轮新增的直接元数据证据：Q-新疆12个sheet名称仅出现2000/2005及其SB/RS副本名；不能用副本后缀断言新观测或独立性。旧2000–2001冻结记录仍写target_labels_loaded=false，但它只描述当时生成预测的步骤；`outputs/virtual_station_mainline/external_2000_2001/frozen_predictions/blind_scoring/external_validation_summary.json`已经存在。本轮只检查其存在与哈希，未读取指标。这不是当前“仍封存”的证明。该区间元数据截至2001-12-01，不能按文件名误写完整2000–2001年。

## 后续真正新测试的封存协议（未执行）

1. 数据保管者给候选target站/流域、日期范围、单位、日界、来源记录和文件哈希；候选若与历史文件同值副本则不能算新。agent仅看元数据，目标文件存于模型进程不可访问的独立权限边界。
2. 保管者核对既有脚本、访问/解封记录、成果、模型选择历史，签注“未进入任何开发”；只有文件mtime新、未命名test或代码声明sealed均不够。缺记录则UNVERIFIED。
3. 预注册A/B/C身份、训练/开发数据、两输入制度、所有特征与超参、主要比较/指标、缺测/日期support、失败和停止规则。现有候选label不能参与选择。
4. 冻结最终模型权重、代码、配置、环境/输入白名单及哈希，由保管者独立保留；先用合法上游/静态输入生成并哈希预测，模型进程无target labels可读路径。
5. 一次性解封，由评价器与预测按date join评分，不把标签提供给训练/预测程序。保留访问日志、输出哈希与全部预注册指标，失败也报告。
6. 若解封后修改特征/参数或重算选择，该测试立即成为开发资料，最终独立主张需要另一批未揭示数据；不得“重新封存”恢复盲测身份。
''',
 '''本地未找到能够认证的新且未揭示最终测试。检查范围是S0指向的流量来源和元数据，不是全盘所有可能资源的穷举；不证明世界上不存在新数据。其他月范围/别名sheet无访问历史、单位或独立性证明，保持未认证，不打开数值去挑性能好的年份。''',
 '''`NEW_BLIND_TEST_AVAILABLE=false`、`S1B_FINAL_HOLDOUT_READINESS=BLOCKED`。继续MQ-free历史开发设计，不因最终测试缺失终止准备。需要未来新供数及访问历史证明；本轮未下载、移动、复制封存标签或申请外部发送。''')

# The future input itself is hashed only, without reading Q cells or fitting.
input_rel='outputs/vhs_bd1m/bd1m_model_dataset_audit.csv'
if input_rel not in B:
    h=digest(ROOT/input_rel)
    B[input_rel]={**h,'absolute_path':str(ROOT/input_rel),'matches_S0_snapshot':h==S0[input_rel],'matches_S0_source_manifest':None,'first_observed':'S0.1 contract preparation, hash only'}
    BPATH.write_text(json.dumps(B,ensure_ascii=False,indent=2),encoding='utf-8')
assert B[input_rel]['matches_S0_snapshot'] is True
folds=[]
for end_year,dev_year in [(1980,1981),(1981,1982),(1982,1983)]:
    start=date(1978,1,31);end=date(end_year,12,31);devstart=date(dev_year,1,1);devend=date(dev_year,12,31)
    folds.append({'fold':f'F{dev_year}','fit_start':start.isoformat(),'fit_end':end.isoformat(),'development_start':devstart.isoformat(),'development_end':devend.isoformat(),'date_count_train_before_missing_Q_check':(end-start).days+1,'date_count_development_before_missing_Q_check':(devend-devstart).days+1,'R1_reference_role':'EXCLUDE_TARGET_CALIBRATION_OVERLAP' if dev_year==1981 else 'FROZEN_HISTORICAL_REFERENCE_NOT_NEW_BLIND'})
contract={
 'phase':'VHS-NEXT-S0.1','evaluation_identity':'RETROSPECTIVE_DEVELOPMENT_ANALYSIS','protocol_identity':'A with time-ordered development folds; not C or INDEPENDENT_FINAL_TEST',
 'execution_allowed_this_phase':False,'real_data_models_trained':False,'MQ_FREE_PRIMARY_PROTOCOL':True,
 'input':{'path':input_rel,'sha256':B[input_rel]['sha256'],'parse_allowlist':['date','Q_input_byblk','Q_target_dsk'],'station_mapping':{'Q_input_byblk':'00705600 / BYBLK','Q_target_dsk':'00705700 / DSK'},'feature_view':['date','Q_input_byblk'],'fit_label_view':'Q_target_dsk restricted to fit dates','development_label_role':'evaluation only, never passed to fit/feature/scaler construction','Q_units':'project numeric Q units; m3/s primary provenance UNVERIFIED','sampling':'daily date index; daily mean and physical day boundary UNVERIFIED'},
 'forbidden_inputs':['physical_reference_q','physical_reference_q_m3s','MQ','wg_dis','Q_target_lag','target_observation_as_input','P_or_T','snowmelt','Fourier6_prediction','any_residual_reference_or_target_Q_derived_feature'],
 'folds':folds,
 'common_support':{'initial_boundary_start':'1978-01-01','max_lookback_days':30,'fit_start_after_warmup':'1978-01-31','same_for_regimes_and_primary_models':True,'impute_Q':False,'future_fill':False,'primary_score_dates':'predeclared full development calendar, shared feature support; missing support => stop, no posthoc intersection selection'},
 'models':{
   'S1A-0':{'calendar':'12 target-train monthly means on common training support','harmonics':None,'fit_target_train':True,'hyperparameter_search':False},
   'S1A-1':{'calendar':'exact same frozen within-fold S1A-0 climate','upstream_center':'each feature monthly train mean','upstream_scale':'per-feature train std after monthly centering, ddof=0','model':'3-coefficient OLS on target residuals with no additional intercept','solver':'SVD pseudoinverse rcond=1e-12; require rank=3','model_search':False,'lags_selected_from_target':False,'prediction_rule':'max(C_target_month + beta dot standardized_upstream_anomalies,0)'},
   'S1A-2':{'model':'frozen original R1 only','tau_global_days':0.7071228027343739,'substeps_per_day':3,'parameter_refit':False,'prediction_rerun':False,'reference_sources':[{'path':'outputs/vhs_bd1m/experiments/e4b1_incremental_residual_predictions.csv','usecols':['date','Q_R1_route'],'eligible_development_years':[1982]},{'path':'outputs/vhs_bd1m/experiments/e4c_1983_daily_predictions.csv','usecols':['date','Q_R1_route'],'eligible_development_years':[1983]}],'target_calibration_years':[1978,1979,1980,1981],'primary_contrast_member':False,'regime1_role':'annotated contextual reference only','regime2_role':'NOT_COMPARABLE_INPUT_REGIME; do not shift predictions or reroute'}
 },
 'regimes':{'REGIME_1_SAME_DAY':{'availability':'post-event date-index reconstruction, not certified real-time','features':[{'name':'up_current','lags':[0]},{'name':'up_mean7','lags':list(range(0,7))},{'name':'up_mean30','lags':list(range(0,30))}]},'REGIME_2_PAST_ONLY':{'availability':'date t-1 and earlier only','features':[{'name':'up_lag1','lags':[1]},{'name':'up_past_mean7','lags':list(range(1,8))},{'name':'up_past_mean30','lags':list(range(1,31))}]}},
 'primary_contrast':'S1A-1 minus S1A-0 separately in each regime; never rank regimes together',
 'uncertainty':{'development_years':3,'random_model_seed_needed':False,'bootstrap':'paired circular moving block within development year; equal year weights; conditional on fitted model','replicates':10000,'seed':20261011,'primary_block_days':30,'prespecified_sensitivity_block_days':60,'confidence_level':0.95,'two_regimes_not_pooled_for_significance':True,'population_significance_claim_allowed':False},
 'decision_rules':{'consistent_development_gain':'positive RMSE gain in all 3 dev years, macro relative gain >=2%, conditional paired-bootstrap lower bound >0 at both prespecified block lengths','mixed_or_uncertain':'otherwise; failure to find stable gain does not prove no upstream information','robust_usefulness_guard':'any year absolute PBIAS worsens by >2 percentage points or low-flow RMSE worsens >5% => mark tradeoff/NOT_ROBUST even if aggregate improves','peak_timing':'signed and absolute annual-max-date error, ties earliest; diagnostic, no method selection','residual_error':'remove the same target-training climate from obs and prediction; algebraically same error, not a second independent endpoint'},
 'stops':['no user authorization for executing S1A','input hashes or station mapping mismatch','unsupported or duplicate/missing dates; negative/nonfinite Q; missing feature windows beyond prescribed warmup','monthly train climate undefined; feature std <=1e-12; rank !=3','access to development/unknown candidate target labels from fit/scaler/feature process','attempt to tune lag/window/harmonics or refit R1/R2/Fourier6/D5','attempt to promote exposed development results to independent final or strict zero-shot'],
 'readiness':{'S1A':'CONDITIONAL','S1B':'BLOCKED','S1C':'BLOCKED'},
 'report_units':{'RMSE_MAE_Bias':'project Q numeric units; provisional m3/s only if labeled assumption','annual_water_balance':'PBIAS and numerical daily sum difference; no conversion to physical m3 until units/day-mean primary proof','peak_timing':'date-index days, unknown real hydrologic day offset disclosed'}
}
(OUT/'vhs_next_s01_s1a_design_contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
fold_table='| 折 | 实际fit日期（共同预热后） | 开发年份 | 日期计划n（fit/dev） | 原R1身份 |\n|---|---|---|---|\n'+'\n'.join(f"| {f['fold']} | {f['fit_start']}..{f['fit_end']} | {f['development_start']}..{f['development_end']} | {f['date_count_train_before_missing_Q_check']}/{f['date_count_development_before_missing_Q_check']} | {f['R1_reference_role']} |" for f in folds)
write('mq_free_s1a_protocol','MQ-free S1A最小实验正式设计（不执行）',
 '''日Q加工一致、E0列映射及S0泄漏审计可复用，不重做4382站日对比或7项物理测试。R1已有目标监督校准和已保存预测，禁止重拟合或重跑；所有旧年份已揭示。主问题为去除共同季节性后，上游Q是否仍增加未参与该折拟合的开发时段预测信息。''',
 f'''## 1. 身份与授权边界

固定为 **RETROSPECTIVE_DEVELOPMENT_ANALYSIS**；新S1A-0/1属于Protocol A的时间有序开发，**不是INDEPENDENT_FINAL_TEST、不是strict zero-shot**。开发年虽然不参与对应新模型fit，但已被历史研究揭示，因此不能恢复独立测试身份。S0.1只设计和自检契约，不执行真实实验；机器契约 `vhs_next_s01_s1a_design_contract.json` 明确 execution_allowed_this_phase=false。

## 2. 数据输入与目标标签契约

固定源 `{input_rel}`，SHA-256 `{B[input_rel]['sha256']}`；只读取date、Q_input_byblk、Q_target_dsk三列，不把整表气象/标志/旧预测自动作为输入。date是索引，BYBLK/00705600是上游输入，DSK/00705700是监督/评价标签。
实现时先拆role：feature view仅date和上游Q；fit-label view只含该折train日期的DSK；evaluation view单独含开发DSK，只在预测冻结后join。禁止特征工程、scaler、窗口/超参选择函数接收开发Q。训练DSK仅用于固定季节均值及回归目标，不进入上游特征。
排除MQ、wg_dis、目标Q窗口、物理参考锚点、温度/降水/融雪、Fourier6预测及其派生量。无气象不等于其物理上不重要，只是这次隔离上游增量信息。不能从“future_information_leakage=False”常量标志推定安全。

## 3. 固定时间折及共同有效日

{fold_table}

三折均仅用过去训练，先从1978-01-01合法上游历史构窗，统一删除初始30个日期，从1978-01-31开始fit；表中n只按日历计算，不是本轮实际拟合或Q统计结果。开发日期计划为每年完整日历365日。
所有S1A-0/1、两制度共享同一预热与训练日期support。若未来发现缺Q、重复/错日、非有限/负Q或未预注册窗口缺失，停止并记录，不能为某模型事后挑交集、补目标值、前后填补或缩小评分期。原S0显示Q完整，但执行时仍应按契约验证哈希和完整日期；本轮未再次读取这些Q数值。

## 4. 两种输入制度（分开报告）

**Regime 1 Same-day available**：W0(t)=Q_up(t)，W7(t)=mean Q_up(t−6..t)，W30(t)=mean Q_up(t−29..t)。这是事后日期索引重建，日界和发布时刻未证实，不能声称当天开头可实时预报。
**Regime 2 Past-only**：W1(t)=Q_up(t−1)，W7(t)=mean Q_up(t−7..t−1)，W30(t)=mean Q_up(t−30..t−1)。全部最大日期≤t−1。
窗口1/7/30固定为本次低容量设计选择，不来自目标未来相关性，也不声称它们最优；不搜索lag/窗口。每制度3个上游特征，日期支持相同；两个制度的差别是输入可用性，禁止放同一排行榜后归因于模型结构。

## 5. S1A-0 / S1A-1定义

**S1A-0 Seasonal Climatology Only**：每折对共同train日期，C_y(m)=mean(Q_DSK(train dates in month m))。12个月均值；开发仅按month(date)查表。闰日沿用2月均值，不搜索DOY平滑或Fourier harmonics。输出max(C_y,0)，无上游Q拟合参数。季节表必须与S1A-1逐值相同。

**S1A-1 Seasonal + Upstream**：每个上游窗口W_j只用共同train日期拟合月均C_wj(m)，A_j(t)=W_j(t)−C_wj(month(t))，s_j=std_train(A_j,ddof=0)，Z_j=A_j/s_j。这样先去除上游窗口中共同月季节性，而不是把明显季节相关误作增量信息。
在train上定义r_y(t)=Q_DSK(t)−C_y(month(t))，拟合固定三系数：beta=argmin Σ_train(r_y−Σ_j beta_j Z_j)²；无额外截距、无隐藏层、无调参、无lag选择。采用SVD伪逆rcond=1e−12，要求3列满秩、s_j>1e−12及12月季节表都有train支持；不满足则停止，不能看开发结果选ridge/删特征。数值阈值是预先固定实现规则，不是水文发现。
开发预测Qhat_1(t)=max(C_y(month(t))+beta·Z(t),0)。与S1A-0用相同非负规则；报告裁剪次数及裁剪改变量，未裁剪结果仅作预注册诊断，不按其好坏替换主结果。OLS确定性，无随机模型种子；不能把重复同解当独立重复。
此处控制的是固定的**月季节气候态**，不证明去尽所有季节/长期状态。改善只能支持超过这个预定义季节基线的预测信息，不能证明上游因果贡献或全部物理机制；未改善也不能证明任何非线性方法都无信息。

## 6. S1A-2 Frozen R1 Reference的公平边界

只读既有预测的date和Q_R1_route：1982取 `e4b1_incremental_residual_predictions.csv`，1983取 `e4c_1983_daily_predictions.csv`。本轮已检查两文件表头，未读取预测数值。禁止复制Q_Fourier6_final、Q_E4B1或目标列作为R1预测，禁止重新路由、重新fit或改tau。
原R1在1978–1981 DSK上校准，因此F1981的1981与校准期重叠，**不列入未参与fit的参考比较**。F1982/F1983只作已校准、已揭示历史参考，不具备与当前全部expanding folds相同train制度，不能和新模型作三折统一排名。
R1原输入契约接受当日上游forcing；其在past-only预测起点的精确可用性未单独认证。本轮不通过移动预测一天或推测链内延迟改变其身份。Regime1只另列上下文参考，Regime2的S1A-2标 **NOT_COMPARABLE_INPUT_REGIME**。不为凑三项完整排行榜而造一个新R1。
所以真正公平的主要因果无关比较是**各制度内S1A-1相对S1A-0的成对差**；R1满足冻结参考要求，但不是该成对增量检验的可交换对照。R1参数与状态规则见原 `e4b3_method_freeze.json`，保留A监督身份。

## 7. 可证伪假设、指标和误差分析

H0：在固定月季节基线/预定义窗口与开发设计下，合法上游Q不提供稳定样本外增量信息。H1：在相同边界下提供稳定增量信息。结论限定当前线性最小方法，不推广到所有GNN/物理方法。
每年每制度报告RMSE、MAE、NSE、Bias、PBIAS；定义正增益g_y=(RMSE0_y−RMSE1_y)/RMSE0_y、DeltaNSE=NSE1−NSE0。主汇总为3年等权宏平均，pooled逐日只作辅助。NSE分母用开发观测均值仅用于评价，不进入模型；RMSE0=0、常量目标或零和Q时返回NA并说明，不凭NA选模型。
去季节残差使用同一个train C_y：r_obs=Q_DSK−C_y，r_pred=Qhat−C_y。二者差与原Q预测误差**代数相同**，残差RMSE不是第二个独立支持证据；另报残差SSE/R²及残差图（未来获准执行后），均不得再做窗口筛选。
年水量报告PBIAS=100Σ(Qhat−Qobs)/ΣQobs及数值日和差；真实单位/日均身份未确认前不转m³。低流量阈值为该折train DSK的20%分位，开发只评价此固定阈值对应日期，不能用开发分位重新挑低流期。KGE仅作为可选描述，若实现须固定定义，不作选择门槛。
洪峰时间采用全年最大流量日期，平峰取最早日；报告预测峰日减观测峰日及绝对日数、峰值幅度误差。只解释为日期索引诊断，不声称亚日传播速度。还报告逐月有符号偏差、训练/开发缺测计数、裁剪率和最差年份，不能隐去退化年。

## 8. 不确定性与判断规则（提前固定，未计算）

三折只有**3个相邻开发年份**，训练窗重叠，不能将1095个自相关日或三个重叠模型当1095次独立实验。按年并列展示是主要证据；不能认证跨站/流域或总体显著性。
未来评分用**同日期配对**误差的年内circular moving-block bootstrap：10000次，seed20261011，主block30日，固定60日敏感性；每年独立抽取块直至该年长度，截断尾块，在同一重采样索引上分别重算两模型RMSE/NSE，按年等权汇总。该CI条件于已fit模型和三个已见年份，不覆盖训练估计/历史方法探索/跨年依赖；仅作描述，不报总体显著性p值或把block数当独立样本量。
每制度分别判断，不能挑表现更好的制度宣称唯一“显著”结果：
- **CONSISTENT_DEVELOPMENT_GAIN**：3年RMSE全部降低、宏平均相对降低≥2%，且30/60日预设block下宏平均增益CI下界均>0。2%是本协议预先选择的实践阈值，不是由数据估计或通行水文标准证明。
- 条件未全满足：记MIXED_OR_UNCERTAIN或NO_STABLE_GAIN，完整报告方向/CI，不证明上游完全无信息或H0普遍为真。若CI因资料不足无法解释则证据不足。
- 若任一年绝对PBIAS较季节基线恶化>2个百分点，或low-flow RMSE恶化>5%，即使平均改善也记**TRADEOFF / NOT_ROBUST_USEFULNESS**；不把水量/低流代价藏在平均RMSE之后。这些同样是预设实践门槛。峰时只描述，不反过来调参。
两个制度均为预注册描述性开发检验，没有总体显著性结论；不得基于某个CI结果重新挑block/年/窗口。

## 9. 实施检查和停止条件

将来获准后只新增独立S1A脚本、配置、预测与报告，绝不编辑历史。固定三列白名单与源hash；检查fit/dev日期严格分离、train-only气候态/scaler、Regime2所有lag≥1、共同评分日及R1校准重叠排除；先在合成占位数据上验证边界，再允许真实开发fit（这些都不是S0.1现在执行的任务）。
发现hash漂移/站号问题、缺日期/缺Q、非法值/窗口、零方差/秩不足、越界目标访问立即停止，不自动修复数据或改变模型；记录阻断。停止于预注册主比较报告，禁止继续lag/harmonic/D5搜索、转GNN/GPU、解封新label或升格最终测试。需要改变协议时先出新版本并获批准，当前设计不具备执行授权。
''',
 '''原始日均身份、单位/日界/提供者仍无正式证明；只有一个上下游案例和3个开发年；已揭示数据不能消除历史探索偏差，月气候态未控制全部季节性/未观测过程。R1在一折有校准重叠、在past-only无认证，故不作三项统一排行榜。''',
 '''`MQ_FREE_PROTOCOL_DESIGNED=true`；`S1A_EXPLORATORY_READINESS=CONDITIONAL`。允许边界是用户另行批准后，以项目数值Q/日期约定开展上述固定、低容量、MQ-free回顾性开发，明确接受元数据及已揭示风险；不必等待MQ独立性解决。若要声明物理m³水量、实时预报、新独立泛化或C，仍必须解决相应P0，不能靠此次设计自动准入。''')

write('p0_resolution','P0处置与分支准入总决策',
 '''S0审计完成但READY_FOR_VHS_NEXT_S1=false；MQ原始生成链、观测原始单位/日界和新独立测试未解决。历史数值一致性、7/7合成测试和E4/E5保护结论不被本轮重复标为新发现。''',
 f'''本轮把P0从单一全局开关拆为分支：

| 门槛 | 本轮证据/处置 | S1A受限开发 | S1B最终独立测试 | S1C strict zero-shot |
|---|---|---|---|---|
| MQ独立性 | 复制确认；生成/校准仍UNVERIFIED；主协议移除所有MQ路径 | 主比较可绕开，不宣称来源已解决 | 如未来模型用MQ仍阻断 | 阻断未知MQ/目标校准参数 |
| 观测单位/日界/正式站号 | 原始头与文件属性不提供正式证明；项目映射/数值约定保留 | 仅数值/日期级开发，披露风险 | 官方物理或跨来源评价仍需补证 | 真实目标独立身份/资料契约仍需补证 |
| 新未揭示测试 | 在限定本地源及历史记录中没有认证候选 | 不需要盲测身份；仅历史开发 | BLOCKED | 独立评价和标签隔离方案仍缺 |
| 目标Q监督 | S1A-0/1明确用train DSK；R1原校准身份保留 | A合法，dev不进入fit/选择 | B允许train，但最终test隔离 | 当前S1A及原R1不能C |
| R1公平性 | 原78–81校准与1981开发重叠；past-only契约未认证 | 只上下文参考，核心1vs0成对 | 不能靠改旧tau解决 | 不能拿已目标校准R1冒充C |
| 开发年数/历史筛选 | 新协议固定3个expanding开发年及预设窗口 | CONDITIONAL、证据弱需披露 | 不能重复封存旧年 | 不能外推多站/多流域 |

本轮**解决的是实验设计上的绕开和身份边界，不是外部来源事实已经补齐**。没有新官方证明，没有新流量统计或性能数字，没有重开D5搜索。

分支状态：`S1A_EXPLORATORY_READINESS=CONDITIONAL`，`S1B_FINAL_HOLDOUT_READINESS=BLOCKED`，`S1C_STRICT_ZERO_SHOT_READINESS=BLOCKED`。保留S0原状态文件不改。
''',
 '''P0-来源：MQ公式/校准独立性；日Q供数机构、单位、日均与日界/站址；月序列原始身份。P0-验证：新时间/站/流域的未揭示证明与封存权限；C目标全标签及目标专用参数隔离。P0-解释：历史开发不能包装独立测试，R1有校准期重叠和制度限制。
资料请求清单见observation_metadata/mq_provenance_decision；缺证仍为UNVERIFIED。''',
 '''最值得先做的单个实验是**Past-only制度下、固定月气候态与固定1/7/30日上游去季节窗口的三折成对增量检验**。它针对核心Q1，用低容量对照隔离季节性；same-day作为同一预注册实验的独立信息制度次要分层，不挑优者。仅在用户批准执行上述受限S1A协议后开展，本轮已停止。''')

# Final targeted after-check: all historic inputs, consulted S0 reports and frozen
# small records only. No models/figures rehashed or reread in a global scan.
after={rel:digest(ROOT/rel) for rel in B}
assert all(after[r]=={k:B[r][k] for k in ['bytes','sha256']} for r in B)
integrity.update({'files_checked':len(B),'matched_S0_historical_snapshot':sum(r in S0 for r in B),'matched_S0_delivery_manifest':sum(r in DELIVERY0 for r in B),'changed_this_phase':[]})
(OUT/'vhs_next_s01_integrity_after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'vhs_next_s01_integrity_result.json').write_text(json.dumps(integrity,ensure_ascii=False,indent=2),encoding='utf-8')
write('validation_report','中文最终报告与完成核验',
 '''继承S0已确认事实，未重做全量审计、4382站日加工核验、物理测试或历史模型实验。S0历史2398文件完整性和E5A冻结记录作为基线。本轮仅进行必要元数据/赋值链核对与新增协议设计。''',
 f'''1. **MQ是否真正查清？没有。** 可确认工作簿复制源和赋值链，不能确认原物理生成/校准链、目标信息独立性、提供者/原始单位。逐问题状态见mq_provenance_decision；MQ_PROVENANCE_VERIFIED=false。
2. **日Q单位与日界是否证明？没有。** 本轮确认原表头/OQ标记和文件作者/创建属性，仅支持项目内日期键。原始m³/s、daily mean、两站真实相同日界与正式编号认证仍未核实。DAILY_Q_METADATA_VERIFIED=false。
3. **哪些历史模型使用目标监督？** R1/R2、Fourier6及目标残差、E1目标监督模型、Stage C P1与D5同站跨年模型。E1/E2目标历史窗还使用测试内过去目标Q；早期GNN遮蔽OQ不代表MQ独立，不能认证C。独立协议对照表已新增，未改历史名称。
4. **有真正新且未揭示测试吗？未认证到。** 2000–2001旧冻结步骤之后已有评分产物；其元数据截止2001-12-01。Q-新疆sheet名只有2000/2005及变体；月序列其他区间/副本无独立性证明。NEW_BLIND_TEST_AVAILABLE=false；本轮未打开候选目标Q或计算其统计量。
5. **MQ-free探索能否准备？可以，受限。** 排除MQ及所有派生锚点、wg_dis/气象/目标滞后，白名单仅date/上游Q/role隔离的train或评价DSK标签。身份为RETROSPECTIVE_DEVELOPMENT_ANALYSIS，仍是目标监督A，不是C。
6. **三个对照是否公平？** S1A-0/1用同一train季节表、日期support、非负规则，只有固定上游异常窗口不同；same-day/past-only分开。原R1校准见过1981，past-only也未认证，因此只作1982/1983的注明身份参考，不参加统一三折排行榜或主增量检验，不shift或重算旧预测。
7. **P0剩余什么？** 原始单位/日界/供数站号，MQ生成/校准清单，新未揭示测试及访问记录，C的source训练/目标全标签隔离。S1A绕开MQ不等于这些来源事实解决。
8. **S1A准入？CONDITIONAL。** 已固定三折（train78–80→dev81、train78–81→dev82、train78–82→dev83）、12个月气候态、1/7/30上游窗口、3系数OLS、共同30日预热、成对block描述性不确定性及停止规则。只有3个开发年，不能把自相关日数当独立重复。需要用户批准受限执行；S1B/S1C均BLOCKED。
9. **历史是否完整？** 本轮涉及 **{len(B)}个文件** 前后哈希不变，其中{integrity['matched_S0_historical_snapshot']}个与S0历史快照一致、{integrity['matched_S0_delivery_manifest']}个S0交付资产与其交付manifest一致；E5A17源文件和现有论文小文件纳入检查。S0完整2398文件记录复用，未重复处理大数据/模型/图件；对此不声称本轮重新校验了2398个文件。原始工作簿不变，无历史修复/模型拟合/论文组装，S0报告保持不变。
10. **下一步最值得做的单个实验？** 用户批准后，按固定协议做**Past-only月季节控制后的上游增量信息成对检验**；same-day另列预注册信息制度，R1仅上下文参考。不做lag/harmonic搜索、不训练GNN、不重新打开D5。

## 交付和本轮实际验证

已生成7份专题/最终Markdown报告及状态txt，另有逐问题决策JSON、输入/评价机器契约、元数据证据、局部before/after哈希。契约验证只检查日期/特征边界、文件链接、身份/状态和哈希，不读取候选目标值，不调用fit/predict或GPU。
核心新发现与新设计：原日工作簿作者和文件创建属性的证据等级；旧external封存元数据不能证明今天仍封存；R1对新1981开发折有校准重叠，且不能默认加入past-only榜；固定可执行准备的MQ-free月季节控制设计。S0已有事实不重新计作本轮发现。
''',
 '''来源元数据/新独立测试/C目标独立性未获得新外部证明。文件哈希证明本轮未改动，不认证观测真实性。没有全盘穷举未发现数据；局部搜索未找到生成脚本不证明任何外部代码不存在。Git原未提交状态沿用UNVERIFIED，未尝试修复。''',
 '''VHS_NEXT_S01_COMPLETE=true只表示本轮P0判断与协议交付完成；不表示所有来源通过。REAL_DATA_MODELS_TRAINED=false、NEW_GPU_TASKS_RUN=false、FROZEN_RESULTS_CHANGED=false、EXISTING_MANUSCRIPT_CHANGED=false。S0.1工作到此停止，等待用户批准，不执行S1A/S1B/S1C。''')
status='''VHS_NEXT_S01_COMPLETE=true
MQ_PROVENANCE_VERIFIED=false
DAILY_Q_METADATA_VERIFIED=false
NEW_BLIND_TEST_AVAILABLE=false
MQ_FREE_PROTOCOL_DESIGNED=true
MQ_FREE_PRIMARY_PROTOCOL=true
S1A_EXPLORATORY_READINESS=CONDITIONAL
S1B_FINAL_HOLDOUT_READINESS=BLOCKED
S1C_STRICT_ZERO_SHOT_READINESS=BLOCKED
REAL_DATA_MODELS_TRAINED=false
NEW_GPU_TASKS_RUN=false
FROZEN_RESULTS_CHANGED=false
EXISTING_MANUSCRIPT_CHANGED=false
S1A_EVALUATION_IDENTITY=RETROSPECTIVE_DEVELOPMENT_ANALYSIS
S1A_REAL_EXPERIMENT_EXECUTED=false
S1A_STRICT_ZERO_SHOT=false
NEW_CANDIDATE_TARGET_VALUES_ACCESSED=false
E5I1_EXECUTED=false
STOPPED_AFTER_VHS_NEXT_S01=true
'''
(OUT/'vhs_next_s01_status.txt').write_text(status,encoding='utf-8')
print(json.dumps({'phase':'S0.1','reports':7,'targeted_hash_checked_files':len(B),'matches_S0_historical':integrity['matched_S0_historical_snapshot'],'matches_S0_delivery':integrity['matched_S0_delivery_manifest'],'real_models_trained':False,'readiness':contract['readiness']},ensure_ascii=False,indent=2))
