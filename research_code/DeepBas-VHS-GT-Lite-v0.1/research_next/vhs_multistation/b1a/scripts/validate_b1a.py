"""Final B1A integrity and metadata gates. Hashes bytes, never decodes Q values."""
from pathlib import Path
import json,csv,hashlib,ast,collections,datetime,shutil
from blind_coverage import synthetic_test
H=Path(__file__).resolve().parents[1];ROOT=H.parents[2];E=H/'evidence';R=H/'reports'
def load(n):return json.loads((E/n).read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def read(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
required_reports=['preflight','provenance','archive_manifest','field_dictionary','topology_audit','pair_eligibility','independent_groups','neighbor_matching','label_blindness_validation','license_audit','go_no_go','validation_report','status']
for n in required_reports:assert (R/('b1a_'+n+('.txt' if n=='status' else '.md'))).is_file(),n
for n in ('station_metadata.csv','connected_candidates.csv','nonnested_candidates.csv','coverage_by_year.csv','group_membership.csv','attrition.csv','provenance.json'):assert (H/n).is_file(),n
protected=load('integrity_before.json')['hashes'];bad=[k for k,v in protected.items() if not (ROOT/k).is_file() or sha(ROOT/k)!=v];assert not bad,bad
archive=load('archive_checksum.json');archivepath=H/'archive'/archive['filename'];assert archivepath.stat().st_size==1477248617 and sha(archivepath)==archive['sha256']
assert archive['actual_md5']==archive['official_md5']=='69fd2733e969513403f923ecc5eaa3dc'
members=read(E/'extraction_manifest.csv');extracted_bad=[]
for n,r in enumerate(members,1):
    p=H/r['path']
    if not p.is_file() or p.stat().st_size!=int(r['bytes']) or sha(p)!=r['sha256']:extracted_bad.append(r['path'])
    if n%1500==0:print('Verified extracted source hashes',n,flush=True)
assert not extracted_bad,extracted_bad
assert len(members)==4312
assert sum(r['category']=='SEALED_Q_DATA' for r in members)==1112
assert sum(r['category']=='MODEL_OUTPUT' for r in members)==887
assert sum(r['category']=='FORCING' for r in members)==2172
st=read(H/'station_metadata.csv');pairs=read(H/'connected_candidates.csv');neg=read(H/'nonnested_candidates.csv');coverage=read(H/'coverage_by_year.csv')
assert len(st)==882 and len({r['ID'] for r in st})==882
assert len({(r['country'],r['govnr']) for r in st})==882
assert len(pairs)==834 and len({(r['donor_id'],r['target_id']) for r in pairs})==834
assert all(r['area_monotonic_calc']=='True' and r['area_monotonic_gov']=='True' for r in pairs)
assert sum(r['provisional_primary_eligible']=='True' for r in pairs)==141
assert len({r['target_id'] for r in pairs if r['provisional_primary_eligible']=='True'})==92
assert len(coverage)==29775
assert len(neg)==116 and len({r['target_id'] for r in neg})==70
assert {r['nonnested_donor_id'] for r in neg}=={'377','378'}
assert all(r['donor_to_target_path']=='False' and r['target_to_donor_path']=='False' and float(r['basin_overlap_m2'])<=1 and r['different_transfer_group']=='True' for r in neg)
assert all(r['fully_admitted']=='False' for r in pairs)
for n in ('blind_coverage_synthetic.json','actual_schema_synthetic.json','archive_manifest_summary.json','coverage_scan_summary.json'):assert load(n)['status']=='PASS',n
assert synthetic_test()['status']=='PASS'
# Re-run ONLY synthetic functions via AST selection; importing the driver would rerun a real scan.
source=(H/'scripts/scan_coverage.py').read_text(encoding='utf-8');tree=ast.parse(source)
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('restricted','tests')]
assert len(nodes)==2
import io,calendar
from blind_coverage import MISSING
ns=dict(csv=csv,io=io,datetime=datetime,MISSING=MISSING,synthetic_test=synthetic_test)
exec(compile(ast.Module(body=nodes,type_ignores=[]),'<synthetic-only-functions>','exec'),ns)
assert ns['tests']()['status']=='PASS'
for p in (H/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
for p in E.glob('*.json'):json.loads(p.read_text(encoding='utf-8'),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Invalid nonfinite JSON: '+str(p))))
# Predictive Q payload fields must never be present in open derived metadata tables.
for name in ('station_metadata.csv','connected_candidates.csv','nonnested_candidates.csv','coverage_by_year.csv','group_membership.csv'):
    rows=read(H/name)
    assert not ({'qobs','Q','q_mean','runoff_ratio','slope_fdc','NSE','KGE'}&set(rows[0])),name
decision=load('b1a_decision.json');assert decision['status']=='COMPLETED_AND_STOPPED' and not decision['auto_next_stage'] and not decision['training_authorized']
assert decision['counts']['provisional_target_transfer_groups']==1 and decision['counts']['targets_with_three_controls']==0
result=dict(status='PASS_WITH_DOCUMENTED_POLICY_LIMITS',date_singapore='2026-10-16',completed_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),protected_files=len(protected),historical_hash_mismatches=bad,extracted_files_rehashed=len(members),extracted_hash_mismatches=extracted_bad,archive_sha256=archive['sha256'],required_reports=13,station_count=882,connected_direct_pairs=834,provisional_pairs=141,provisional_targets=92,targets_with_controls=70,targets_with_three_controls=0,Q_numeric_statistics=0,real_model_fits=0,spatial_scores=0,gpu_runs=0,synthetic_only_retest=True,isolation='Same-account directory/program policy; no OS or cryptographic boundary',corrections='EPSG:3035 coordinate assumption corrected and matching recomputed; one R source reclassified UNKNOWN. See correction_log.json.')
(E/'final_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# VHS-NEXT-B1A｜最终验证报告

日期：2026-10-16（Asia/Singapore）；完成UTC：{result['completed_at_utc']}。
交付与执行边界验证：**PASS_WITH_DOCUMENTED_POLICY_LIMITS**；数据准入仍依独立Go/No-Go报告，不能混称全部PASS。

- 官方唯一日包1,477,248,617字节；MD5与公布值一致；SHA-256再次逐字节一致。未下载小时包、镜像或其他大型数据集。
- 596个历史/B0/新疆原始输入/论文保护项全部SHA-256一致，没有重跑旧模型/审计。原始归档和4312个已提取成员全部重新哈希，分类移动仅改变一个新B1A R源码位置，字节未变。
- 安全成员清单4356项，44目录、4312普通文件；无链接/特殊类型/路径穿越，大小和展开配额通过；独占写入不覆盖旧资产。实际展开5,169,337,364字节，当前磁盘余量仍大于2GiB。
- 13份要求报告及所有要求机读资产齐备，另有field_dictionary.csv与补充证据。站点882唯一ID与country/govnr无重复；834直接对无重复，面积方向均通过；141暂定对涉及92目标；负对照116关联、70目标、2 unique供数站；0目标达3控制。
- 882日文件受限扫描输出29775站年计数。合成Q替换不变性在真实扫描前通过，最终仅AST选取纯合成函数重测通过，**没有导入并重跑真实扫描driver**。未计算Q数值统计/相关/性能，没有图、拟合或GPU。
- 派生开放CSV无qobs/Q均值/FDC/径流比/NSE/KGE列；A5/A10只读取表头、模型输出不解码，UNKNOWN不作输入。检查的是输出字段边界，不宣称OS级监控证明。
- 新脚本AST语法通过，所有证据JSON拒绝NaN/Infinity且解析通过。使用-B，未生成旧源码pycache。仅应用当前项目已有标准库、pyogrio/geospatial运行时，无安装或环境重配。
- 许可冲突、未知/域外输水、43站>500m指定河段偏差及独立组不足保留；没有把NOT_TESTABLE记PASS，也没有用同region作为独立系统。

## 工具修复与局限

CSV名为lon/lat的列最初被错误当作度数，导致初版距离及零匹配不可信。官方Gauges.shp明确EPSG:3035米坐标且逐点一致后，修正转换、重算全部距离/匹配；最终为70目标而非初版0目标。43站指定河段距离>500m作为额外待复核筛选，最终141对/92目标。错误初算没有使用Q数据，也没有改变历史资产；更正保留于correction_log.json。

一个附录R源码曾因路径启发式被初分FORCING，已改UNKNOWN并移入quarantine，未执行；初始提取manifest保留，当前manifest反映实际位置与字节哈希。

受限程序会读取Q字段字符串以识别缺测，不能称没有接触标签文件；其保证是输出不依赖非缺失数值。目录同账户隔离非OS/密码学封存，未来训练前仍需冻结访问角色与日志。气象只做文件/字段检查，未核验逐日全部有效性与实际发布时间；插补前缺口230文件保留，本轮未将插补标记完整并入日级资格。

独立性为3自然root、已知输水合并2候选组，而暂定连通目标只有1组，0认证独立目标组；没有假装充足功效。许可正文/机器/包内文本差异不自动解决。B1A_READY_FOR_B2_REVIEW=BLOCKED，B2/B3/B4均未启动。

最终status=COMPLETED_AND_STOPPED；整体NO_GO_CURRENT_MULTISYSTEM_BENCHMARK。所有资产的字节、SHA-256、用途边界见根下integrity_manifest.json（排除其自身以避免循环哈希）。
'''
(R/'b1a_validation_report.md').write_text(report,encoding='utf-8')
# Correct the report's inline initial category counts to the final source manifest.
p=R/'b1a_archive_manifest.md';s=p.read_text(encoding='utf-8').replace('"FORCING": 2173','"FORCING": 2172').replace('"UNKNOWN": 55','"UNKNOWN": 56');p.write_text(s,encoding='utf-8')
assert shutil.disk_usage(H).free>2*1024**3
manifest={}
for p in sorted(H.rglob('*')):
    if p.is_file() and p.name!='integrity_manifest.json':manifest[p.relative_to(H).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p),boundary='SEALED_Q_DATA' if p.is_relative_to(H/'sealed_runoff') else 'QUARANTINE' if p.is_relative_to(H/'quarantine') else 'ARCHIVE_CONTAINS_SEALED_Q' if p.is_relative_to(H/'archive') else 'METADATA_CODE_OR_REPORT')
(H/'integrity_manifest.json').write_text(json.dumps(dict(stage='VHS-NEXT-B1A',files=len(manifest),hashes=manifest),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
