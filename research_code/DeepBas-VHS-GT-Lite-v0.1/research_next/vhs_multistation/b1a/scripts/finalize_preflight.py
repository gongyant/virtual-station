"""Write only completed preflight deliverables, then stop for human approval."""
from pathlib import Path
import json,hashlib,ast
H=Path(__file__).resolve().parents[1];ROOT=H.parents[2];E=H/'evidence';R=H/'reports'
def read(n):return json.loads((E/n).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
facts=read('preflight_facts.json');record=read('official_record_metadata.json')['record'];head=read('network_probe.json')['archive_head']
assert str(record['id'])=='5153305' and record['metadata']['version']=='1.0'
matches=[f for f in record['files'] if f['key']==facts['filename']];assert len(matches)==1
official=matches[0];assert official['checksum']=='md5:'+facts['expected_md5']
assert int(head['headers']['content-length'])==official['size']
free=facts['disk']['free'];GiB=1024**3
# Conservative duplicate staging allowance: 2 compressed copies, 2x5GiB expanded, 2GiB overhead.
peak=2*official['size']+12*GiB;required=max(16*GiB,peak)
assert free>=required,'Insufficient free space; do not download'
protected=read('integrity_before.json')['hashes'];bad=[p for p,v in protected.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=v];assert not bad,bad
for p in (H/'scripts').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
summary=dict(stage='VHS-NEXT-B1A',status='PREFLIGHT_COMPLETE_AWAITING_DOWNLOAD_CONFIRMATION',pre_download_gate='PASS_WITH_LICENSE_QUALIFICATION',official_record_id=record['id'],version=record['metadata']['version'],filename=official['key'],official_bytes=official['size'],official_md5=official['checksum'],archive_sha256='NOT_AVAILABLE_BEFORE_DOWNLOAD',head_content_length_matches=True,free_bytes=free,conservative_peak_budget_bytes=peak,required_free_bytes=required,license_description='CC BY-SA 4.0',license_machine=record['metadata'].get('license'),license_review='CONDITIONAL_DISCREPANCY_AND_INFO_PENDING',protected_files=len(protected),historical_mismatches=bad,archive_get_requests=0,download_bytes=0,archive_member_scan='NOT_STARTED',actual_checksum_validation='NOT_STARTED',new_runoff_payloads_decoded=0,model_fits=0,gpu_runs=0,spatial_scores=0,confirmation_received=False,auto_download=False)
(E/'preflight_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
report=f'''# VHS-NEXT-B1A｜下载前预检查

审查日：2026-10-12（Asia/Singapore）。当前阶段：PRE-DOWNLOAD GATE。状态：PREFLIGHT_COMPLETE_AWAITING_DOWNLOAD_CONFIRMATION。

## 官方对象与访问证据

- 官方记录：[Zenodo 5153305](https://zenodo.org/records/5153305)，版本1.0；[数据论文](https://doi.org/10.5194/essd-13-4529-2021)。已重新读取用户指定的B0五份报告，未重跑旧模型/全部数据审计。
- 唯一拟获取文件：`{official['key']}`；API公布 **{official['size']:,}字节**，即{official['size']/10**9:.6f} GB / {official['size']/GiB:.6f} GiB。
- 官方MD5：`{facts['expected_md5']}`，与用户指定一致。实际文件尚未下载，因此不能称归档MD5已经通过；下载后须逐字节校验并另记SHA-256，不匹配立即停止、不解压。
- 本机通过现有代理对官方文件执行HEAD：HTTP200、Content-Length={official['size']}、Content-Disposition文件名一致，正文读取0字节。元数据API成功，原始JSON留存于 `../evidence/official_record_metadata.json`；HEAD结果见network_probe。HEAD成功不保证1.5GB持续传输成功，不保证断点续传；若Range不获206就不能追加已有partial。
- 当前urllib有效HTTP/HTTPS/ALL代理指向127.0.0.1:7897，未修改网络配置。代理证据仅记录scheme/host/port，未输出凭据。没有使用镜像；官方不可达时报告阻断，不擅自改源。

## E盘空间与保存位置

检查时E盘剩余 **{free:,}字节 = {free/10**9:.2f} GB = {free/GiB:.2f} GiB**。
官网说明日包解压约5GB；实际成员总大小在获取完整归档之前无法验证。[官方说明](https://zenodo.org/records/5153305)

保守预算按两份压缩包（完整+恢复/暂存）、两份各5GiB解压空间（隔离与分类暂存）、2GiB日志/开销计算，约 **{peak/GiB:.2f} GiB**；下载前要求至少 **{required/GiB:.2f} GiB** 空闲，高于附件12GB建议。当前空间通过；下载和成员扫描后必须按真实展开大小、成员数/配额重算，异常膨胀停止，不据“约5GB”无限解包。

完整包保存：`{facts['archive_destination']}`

下载partial/缓存限 `archive/`；临时文件限 `{facts['tmp_destination']}`。open_metadata、sealed_runoff、quarantine、evidence、scripts、reports均建在本B1A目录，全部位于E盘。新程序进程TEMP/TMP/TMPDIR指向E盘tmp；不改系统全局环境，不在C盘创建大型归档。当前复用项目Python标准库，未安装包或复制大型虚拟环境。

已有归档检查：按精确官方文件名检索本项目（排除.venv/.git/node_modules/__pycache__）、存在的E:/Downloads、E:/Datasets、E:/Data及E盘根层，未发现匹配文件；不是全磁盘不存在的证明。没有流量数值扫描。搜索范围和错误列表见 `existing_archive_search.json`。

## 安全解包与隔离准备

仅在用户确认并且完整归档MD5正确后，先生成完整成员manifest，再分类/提取；不调用无审查extractall。路径穿越、绝对/盘符路径、反斜杠穿越、符号/硬链接、特殊设备、大小写重复覆盖的9个合成案例已通过拒绝检查。实际归档尚未取得，成员安全状态 **NOT_TESTABLE**，不能当PASS。

实际解包还须拒绝Windows保留名/尾随点空格、ADS、无效名称、重复文件/目录冲突、越出目录的reparse目标及超配额/异常展开；成员manifest查明后才按独占创建写入，禁止覆盖旧文件。合成路径检查是准备性证据，不是已完成生产级安全提取器。

`sealed_runoff/`是同Windows账户下的目录与程序策略隔离，**没有OS级身份隔离或密码学封存**。目前该目录为空；没有日Q访问、计数、签名、相关性、绘图或拟合。受限coverage读取程序及非缺失Q数值替换不变性测试尚未实现，必须在接触真实Q前通过；失败则停在metadata-only。

## 许可差异与后续边界

官网正文描述 **CC BY-SA 4.0**，机器metadata.license.id为 **cc-by-4.0**；不抹平差异，也不自动按更宽松标识再授权。[页面](https://zenodo.org/records/5153305)、[API](https://zenodo.org/api/records/5153305)。Info供数方特殊限制尚未取得，LICENSE_REVIEW=CONDITIONAL。官方正文还列捷克运行性预警用途限制、来源署名要求及需另行联系获取的坝库/跨流域输水补充资料。不能将它们记为本地已有，也不实际发送邮件。

本阶段获取副本仅用于用户指定科研审查，不发布原始Q、合并再分发或宣称完成全部权利审查。归档取得后依据Info继续核查，冲突未解决时保留CONDITIONAL/REQUIRES_PROVIDER_SUPPLEMENT。

## 历史保护与停止点

复用B0的528文件保护清单，增量纳入B0交付及其manifest、旧论文遗漏保护项，共{len(protected)}文件；本轮前后SHA-256全部一致。没有重跑历史模型、重新读旧Q或修改旧资产。

当前没有获得官方完整归档，实际MD5/SHA-256、归档成员、真实连通对、覆盖站数、独立组、邻站匹配池均**尚未核查**，不生成空的station_metadata/connected_candidates等冒充完整交付。未运行GPU、真实训练或标签评分，未下载小时归档。B2规则仍未冻结；LEVEL_A/B/C及统一C0绝对误差/供数站气象基线增量的修订留待获批后按附件执行，不能预先认定B2_READY。

**下载/解压授权仍待确认。** 附件原文：“完成这一预检查后，必须向用户显示需要下载的实际文件、预计空间和保存位置，并请求一次明确确认。未获确认不得开始1.5GB下载。”

本轮仅交付已完成的预检查及证据，不生成后续完整结果。确认后才继续获取唯一日尺度包、校验、受限manifest/分类和标签盲审查；B2训练、B3评分、B4路由/GNN均不在授权范围内。
'''
out=R/'b1a_preflight.md';assert not out.exists();out.write_text(report,encoding='utf-8')
validation=f'''# VHS-NEXT-B1A｜预检查验证

日期：2026-10-12（Asia/Singapore）。验证范围限PRE-DOWNLOAD，不是完整B1A验收。

- 官方API record=5153305/version=1.0、唯一日尺度文件名、公布MD5通过一致性检查；HEAD字节数与API一致。
- E盘剩余{free/GiB:.2f}GiB，≥{required/GiB:.2f}GiB要求；缓存及临时目录落E盘。
- {len(protected)}个历史/B0/输入保护项SHA-256前后一致；未重跑历史科研审计。
- 9个合成归档路径案例通过；实际archive成员未扫描，生产安全提取、label-blind coverage程序未执行，不把NOT_TESTABLE改成PASS。
- 新增脚本AST语法通过；没有安装新依赖、修改系统代理或启用GPU。
- 官方元数据小JSON请求完成，archive GET=0、archive HEAD正文=0、归档下载=0、真实Q解码=0、拟合/评分=0。
- 许可正文与API标识差异已记录；包内Info尚未读取，完整许可审查未通过。
- 本轮停止等待下载确认；没有生成站点对/覆盖/分组的虚假完整CSV或完整B1A状态。

完整性证据见evidence/integrity_before.json和preflight_delivery_manifest.json。运行记录由脚本与请求类型保留，不宣称OS全局安全监测；同账户目录不构成密码学或OS封存。
'''
(R/'b1a_validation_report.md').write_text(validation,encoding='utf-8')
(R/'b1a_status.txt').write_text('stage=VHS-NEXT-B1A\nphase=PRE_DOWNLOAD_GATE\nstatus=PREFLIGHT_COMPLETE_AWAITING_DOWNLOAD_CONFIRMATION\narchive_acquisition=BLOCKED_AWAITING_EXPLICIT_CONFIRMATION\narchive_checksum=UNVERIFIED_NOT_ACQUIRED\nlabel_blind_scan=UNVERIFIED_NOT_STARTED\ntopology_candidates=UNVERIFIED_NOT_STARTED\npair_inventory=UNVERIFIED_NOT_STARTED\nindependent_groups=UNVERIFIED_NOT_STARTED\nmatching_pool=UNVERIFIED_NOT_STARTED\nlicense_review=CONDITIONAL\nready_for_B2_review=BLOCKED\narchive_GET_requests=0\nnew_target_Q_payloads_decoded=0\nmodel_fits=0\ngpu_runs=0\nauto_download=false\nauto_next_stage=false\n',encoding='utf-8')
manifest={str(p.relative_to(ROOT)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(H.rglob('*')) if p.is_file() and p.name!='preflight_delivery_manifest.json'}
(E/'preflight_delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
