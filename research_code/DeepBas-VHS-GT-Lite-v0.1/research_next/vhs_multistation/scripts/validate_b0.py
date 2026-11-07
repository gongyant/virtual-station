"""Metadata-only final delivery/integrity checks. Does not import model code."""
from pathlib import Path
import json,csv,hashlib,ast,sys,datetime
H=Path(__file__).resolve().parents[1];ROOT=H.parents[1];E=H/'evidence';R=H/'reports'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
required=['b0_dataset_inventory.md','b0_candidate_station_pairs.csv','b0_topology_verification.md','b0_metadata_and_license_audit.md','b0_independent_network_count.md','b0_strict_ungauged_protocol.md','b0_connected_vs_unconnected_control.md','b0_literature_gap_matrix.md','b0_go_no_go_decision.md','b0_validation_report.md','b0_status.txt']
assert not (E/'validation.json').exists(),'Preserve completed validation'
for n in required:
    if n!='b0_validation_report.md':assert (R/n).is_file() and (R/n).stat().st_size>0,n
hist=load(E/'integrity_before.json')['hashes']
bad=[k for k,v in hist.items() if not (ROOT/k).is_file() or sha(ROOT/k)!=v]
assert not bad,bad
paper=load(E/'paper_integrity_against_s0.json');assert paper['paper_entries']==81 and not paper['mismatches']
for k,v in paper['hashes'].items():assert sha(ROOT/k)==v['sha256'],k
with (R/'b0_candidate_station_pairs.csv').open(encoding='utf-8',newline='') as f:pairs=list(csv.DictReader(f))
assert len(pairs)==len({r['pair_id'] for r in pairs})==21
assert sum(r['directed_path_verified']=='True' for r in pairs)==19
assert all(r['B0_admitted']=='False' and r['topology_status']=='TOPOLOGY_UNVERIFIED' for r in pairs)
paths=load(E/'directed_paths.json')
assert len(paths)==19 and all(v['reached'] for v in paths.values())
for p in pairs:
    if p['directed_path_verified']=='True':
        assert int(p['path_reach_count'])==len(paths[p['pair_id']]['reach_ids'])
        assert p['area_monotonic']=='True'
for bundle in load(E/'bundle_headers.json'):
    assert bundle['flow_payload_loaded'] is False
    assert all(v['payload_loaded'] is False for v in bundle['arrays'].values())
assert len(load(E/'station_catalogs.json'))==1512
coverage=load(E/'coverage_metadata.json')
allowed={'station_id','station_code','component','first_date','last_date','calendar_days','rows','observed_days','observed_missing_days'}
assert len(coverage)==5 and all(set(r)<=allowed for r in coverage)
assert all(r['status']=='VERIFIED_CROSSREF' for r in load(E/'crossref_records.json'))
for p in (H/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
decision=load(E/'decision.json')
assert decision['overall']=='NO_GO_MODELING' and not decision['auto_next_stage']
assert decision['gates']=={'A':'BLOCKED','B':'BLOCKED','C':'BLOCKED','D':'CONDITIONAL','E':'UNVERIFIED','F':'CONDITIONAL','G':'CONDITIONAL'}
result=dict(status='PASS_WITH_DISCLOSED_ACCESS_EXCEPTION',completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),python=sys.version,protected_historical_files=len(hist),historical_hash_mismatches=bad,paper_files_unchanged_against_S0=81,required_reports=11,candidate_pairs=21,raw_directed_paths_verified=19,fully_admitted_pairs=0,admitted_independent_systems=0,station_catalog_entries=1512,crossref_records_verified=9,model_fits=0,spatial_scores=0,gpu_runs=0,new_target_Q_payloads_decoded=0,large_dataset_downloads=0,checks=['required-delivery-presence','frozen-hashes','all-S0-paper-hashes','candidate-uniqueness-and-gates','path-chain-count-consistency','header-only-NPZ-flags','coverage-column-whitelist','bibliographic-DOI-verification','new-script-AST-parse','stop-status-consistency'],scope='Scoped metadata audit and hash comparison; no OS-wide access tracing or data provider certification.')
report=f'''# VHS-NEXT-B0｜验证报告

检查时间（UTC）：{result['completed_at']}。结果：PASS_WITH_DISCLOSED_ACCESS_EXCEPTION；这是交付/边界检查通过，不是数据准入通过。

## 已执行检查

- 项目现有 `.venv/Scripts/python.exe -B` 执行 `audit_local.py`、`fetch_bibliographic_metadata.py`、`write_reports.py`、`validate_b0.py`；无模型模块导入，无训练命令、GPU命令或空间评分。
- {len(hist)} 个受保护历史/输入文件逐个SHA-256一致，覆盖R3继承清单、R3交付、完整vhs_transfer分支与本地输入。独立用S0冻结前清单核对现有论文81文件，全部一致。完整性证明限于列出的文件清单，不声称对全磁盘作法证审计。
- 11个要求报告齐备；CSV21唯一候选，19原始河网路径证据，所有候选均未准入且TOPOLOGY_UNVERIFIED；路径计数、面积方向与对应证据一致。计数是当前证据门槛下的结果，不虚构站点。
- 新疆130+前苏联1382=1512目录条目；它们不当作观测序列。工作簿只读取目录/维度，NPZ只读NPY头。日期/QC计数字段白名单检查通过；没有解码新目标Q的数组或单元格。
- 9条DOI由Crossref返回正式元数据；另2条由PMLR/HESS出版页核验。文献11项，小范围定位，不是穷尽综述。失败的出版页/PDF抓取在文献报告明确标注；没把失败当成功。
- 新增Python脚本AST语法检查通过；没有写入旧路径，使用-B避免生成旧源码pycache。没有为低影响文档修改启动真实模型测试。
- 决策JSON与status一致：A/B/C BLOCKED，D/F/G CONDITIONAL，E UNVERIFIED；NO_GO_MODELING；auto_next_stage=false。

## 访问例外与工具修复记录

交互查看已有五站历史覆盖表时，显示过该表中预先存在的Q汇总及历史误差列，超出严格白名单。本轮没有打开新的原始目标Q序列、没有利用这些汇总筛站、设计模型或评价；后续立即改为站号/日期/计数白名单，B0证据及报告不复制这些数值。不能将本轮描述成“从未看到任何历史Q派生汇总”。这一例外保留披露，不假称读取边界毫无瑕疵。

首次NPY头读取遇NumPy私有API不存在，在读取数组payload之前失败；仅修改新B0脚本，改用公开header API后完整成功。最初完整性快照保留，没有借重跑覆盖历史或改变基线。

SHA-256读取的是文件字节；工作簿容器解析只取得目录/维度，未解码sheet Q单元格；这些与“模型开发者读取目标Q序列”分开记录。零训练/零GPU等计数依据本轮执行操作和脚本设计，不冒充OS全局监测结果。

## 未完成的数据资格核验

没有认证本地Q供数权、正式身份/迁站、单位日界和全路径调节；没有取得公开库逐站拓扑/覆盖表，未实际下载/解压测试归档；没有独立系统或C2邻站的完整准入枚举；没有实现真实标签库访问控制或synthetic-only泄漏单元测试。本轮交付协议和门槛，不把方案写完当作隔离已经实现。

仅metadata/B0设计完成并停止。后续元数据获取、技术隔离、训练和真实评分都不自动运行。新资产清单与SHA-256见 `../evidence/delivery_manifest.json`；该清单排除自身以避免循环哈希。
'''
(R/'b0_validation_report.md').write_text(report,encoding='utf-8')
assert all((R/n).is_file() and (R/n).stat().st_size>0 for n in required)
(E/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
manifest={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json'}
(E/'delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False))
