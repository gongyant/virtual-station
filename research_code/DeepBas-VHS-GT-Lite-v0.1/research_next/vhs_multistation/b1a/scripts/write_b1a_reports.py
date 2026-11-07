"""Evidence-based B1A deliverables. No model evaluation or Q numeric analysis."""
from pathlib import Path
import json,csv,collections,hashlib,shutil
from pyproj import Transformer
H=Path(__file__).resolve().parents[1];E=H/'evidence';R=H/'reports'
def load(n):return json.loads((E/n).read_text(encoding='utf-8'))
def csvread(n):
    with (H/n).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write(n,s):(R/n).write_text(s.strip()+'\n',encoding='utf-8')
top=load('topology_summary.json');p=load('pair_gate_summary.json');cov=load('coverage_scan_summary.json');arc=load('archive_checksum.json');man=load('archive_manifest_summary.json');snap=load('snap_forcing_summary.json');eu=load('eu_hydro_summary.json');ext=load('extraction_summary.json')
stations=csvread('station_metadata.csv');pairs=csvread('connected_candidates.csv');neighbors=csvread('nonnested_candidates.csv')
tf=Transformer.from_crs('EPSG:3035','EPSG:4326',always_xy=True)
for r in stations:
    r['coordinate_crs']='EPSG:3035';lon,lat=tf.transform(float(r['lon']),float(r['lat']));r['longitude_wgs84']=lon;r['latitude_wgs84']=lat
with (H/'station_metadata.csv').open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,list(stations[0]));w.writeheader();w.writerows(stations)
eligible=[x for x in pairs if x['provisional_primary_eligible']=='True']
target_groups=sorted({r['operational_group'] for r in eligible});target_roots=sorted({r['natural_root_target'] for r in eligible})
prefix='# VHS-NEXT-B1A｜';scope='日期：2026-10-16（Asia/Singapore）。本阶段仅官方数据清点、元数据/拓扑和受限日期-QC扫描；没有真实训练、性能评分或GPU任务。\n\n'
source='https://zenodo.org/records/5153305';paper='https://essd.copernicus.org/articles/13/4529/2021/'
write('b1a_provenance.md',prefix+'来源链\n\n'+scope+f'''
用户于本轮明确批准唯一官方日尺度归档。记录5153305、版本1.0、文件`{arc['filename']}`，下载源[官方Zenodo]({source})；API在下载前重新核实，快照`official_record_acquisition.json`。没有镜像、小时级包或其他大型数据集。

文件大小{arc['bytes']:,}字节，官方/实际MD5均`{arc['actual_md5']}`；SHA-256为`{arc['sha256']}`。完整包保留在archive/；没有修改归档。下载请求/恢复事件、校验及原始成员清单分别在evidence中。

对4312个普通文件按归档成员安全清单独占创建，保持相对目录；其SHA-256及分类见extraction_manifest.csv。Q、模型输出、Q派生表和未知内容分区保存；所有原始资产不经过数值加工。程序读取日期/QC时仍须解析Q字段的缺失token，不能声称没有接触Q文件字节；不会把非缺失Q转换为数值。

官方Info确认m³/s、UTC、缺测−999、原始插补前缺口另存；Info_english/3_References列供数来源与引用要求。该副本是编整/统一格式后的观测产品，不是原始水位仪器记录。正式ID采用LamaH ID加country/govnr，不将项目自造别名混入。

新目标系列不向交互工具输出；原始标签不进入研究报告、图表或特征。hash是字节一致性证据，不证明原供数真值或OS安全隔离。
''')
write('b1a_archive_manifest.md',prefix+'归档与安全分类\n\n'+scope+f'''
实际完整成员4356项，其中4312普通文件、44目录，总展开{man['expanded_bytes']:,}字节（约5.17GB）。最大成员{man['largest_member_bytes']:,}字节；各成员≤256MiB，总大小≤12GiB，数量≤100000，实际解包前余量充足。路径/特殊类型/链接/大小写重复/父子冲突检查无拒绝项；仅去除显式开头`./`，不放行内部`..`。

拒绝路径穿越、绝对盘符、ADS、控制字符、Windows保留名和尾随点空格、软/硬链接及特殊类型；resolve必须留在分类根下，所有输出用xb独占创建，未调用extractall、未覆盖旧资产。实际展开和磁盘配额检查通过；所有缓存/临时文件在E盘。清单见evidence/archive_members.csv，提取SHA-256见extraction_manifest.csv。

分类后的实际文件数：{json.dumps(ext['categories'],ensure_ascii=False)}。

其中SEALED_Q_DATA的1112文件包括882份日径流和230份插补前缺口日期文件；不等于1112站。FORCING目录有2172份A/B/C日气象CSV；额外1个按路径初分的说明/辅助文件不算气象站点。MODEL_OUTPUT的887文件是整个F_hydrol_model隔离资产，包含输入、率定结果和输出，不称887条观测。

RiverATLAS是含丰富属性的混合容器，只读取HYRIV_ID/NEXT_DOWN/MAIN_RIV/LENGTH_KM/UPLAND_SKM以及选择性的几何；其余字段默认UNKNOWN，不把整张表当输入。A5、A10整表隔离，字典仅查看表头。UNKNOWN文件只复制/哈希，不执行其代码或用作输入。外部R/Python源码仅读指定QC说明；没有执行原作者处理/率定程序。

目录隔离仅同账户程序策略；sealed_runoff并非密码学封存。完整archive也含Q字节，未来开发者不得任意绕过受限程序读取它。
''')
write('b1a_field_dictionary.md',prefix+'实际字段与白黑名单\n\n'+scope+'''
机器字典field_dictionary.csv含584个来源字段条目，不只按字段名猜测。来源按论文及实际目录记录：A1站点/层级，A2气象，A3地形，A4气候，A6地类，A7植被，A8土壤，A9地质。公开静态属性仍须在B2冻结适用时间与单位，不因这份白名单自动进入训练。

- 实际层级字段：ID、HIERARCHY、NEXTUPID、NEXTDOWNID；NEXTUPID为逗号分隔多上游，0为空，不把字符串当单个站。
- Gauge_attributes实际包含govnr/name/river、area_gov/area_ratio、nrs_euhyd/nrs_rivat和degimpact/typimpact/diur_art/diur_glac。area_calc在A/B/C Catchment_attributes；不是猜测替代字段。
- CSV名为lon/lat的两列实际是EPSG:3035米坐标，与Gauges.shp逐点一致；station_metadata明确coordinate_crs，另列转换后的WGS84经纬度。禁止直接把原字段当度数。
- 日径流真实表头为YYYY;MM;DD;qobs;ckhs;qceq;qcol。qobs仅用于识别缺失token；ckhs/qceq/qcol为ELIGIBILITY_ONLY。ckhs=1的语义经官方源码的checked/ja/validierte映射核实，未执行该源码。
- **整表黑名单**：Table A5的两个Hydro_indices文件、Table A10的Water_balance.csv、整个F_hydrol_model。即使A10含气象字段也不从目标Q依赖表中偷选“看起来合法”的列。
- degimpact/typimpact/diur_art/diur_glac可能依赖人工过程线判断，限预设资格/敏感性，不作无资料模型特征。qceq/qcol本身也是已由Q计算的标记，允许本轮统计其现成代码，禁止将其作为预测输入。
- RiverATLAS未知丰富属性不默认合法；流量相关列未读取数值。UNKNOWN全部拒绝未来输入。
- Crossbasin_water_transfers的ID、To_ID只用于依赖合并；model/estimated标记不作真值认证，阈值不作为目标Q输入。

气象2172文件均核对实际表头，未读数值或扫描全日期；实际逐站可用时刻、气象QA和单位完整字典尚待协议冻结。允许回顾性重建与实时预测须分轨，归档UTC日期不等于发布时刻。
''')
write('b1a_topology_audit.md',prefix+'真实拓扑审查\n\n'+scope+f'''
882测站中859有A/B划分，形成834条直接有向站间边；DAG无环、ID唯一、NEXTUPID/NEXTDOWNID互相一致，没有未解析外部站号。所有834边的area_calc及area_gov均下游大于上游。A目标面积=自身B增量面积+各直接上游A面积的检查859/859在1%容差内通过。另23站无明确集水区，不加入图以凑数。

全部祖先→后代组合共7701，仅为图的传递闭包，不是7701独立样本；主候选CSV保留834个直接对，hops=1，确保多支流每一上游都正确标记为连通。

RiverATLAS独立命名空间HYRIV_ID→NEXT_DOWN：808路径PASS，23 NOT_TESTABLE（ID缺失）、3 NOT_TESTABLE_BOUNDARY；未把不可测计PASS。808对也通过≥98% donor A多边形位于target A的嵌套几何检查。这是官方资料间的可复核结构证据，仍不等于独立现场测站认证。

EU-Hydro OBJECT_ID→NEXTDOWNID单独核查：832 PASS、2同一河段NOT_TESTABLE，未将RL/CL字符串与HydroRIVERS数字混用。核查路径未见STRAHLER=-1的人工河段，但缺失人工渠系不能因此判无调水。详细路径结果见eu_hydro_path_checks.csv。

站点与指定RiverATLAS线的距离840站可测：约{snap['distance_min_m']:.2f}–{snap['distance_max_m']:.2f}m，43站>500m；其余42站缺映射，其中19在A/B图内、23不在A/B。808对中726对两端≤500m。500m只用于暂缓大偏差候选，剩余仍未核对竞争河段、迁站与日界时效，不能叫可靠snapping全面PASS。

本地原HydroRIVERS为亚洲图层，对欧洲对照为NOT_TESTABLE_WRONG_GEOGRAPHIC_COVERAGE；不额外下载欧洲图层。使用的是此次官方包自带RiverATLAS，不能冒称已用本地亚洲文件交叉验证。

降级/未核实对全部保留在connected_candidates.csv，并明确fully_admitted=false。沿程坝库、灌渠、回流、支流观测站及物理行程仍需复核。真实结构候选808，完整准入0；两者不得混报。
''')
write('b1a_pair_eligibility.md',prefix+'站点对准入与损耗\n\n'+scope+f'''
逐级计数见attrition.csv：882有日文件→859有A/B划分→834直接边→808有RiverATLAS和嵌套几何→717联合覆盖通过→162两端低/无影响→141两端指定河段距离≤500m的暂定候选，涉及92个unique目标。完整科学准入仍0。

覆盖规则在本轮不看Q数值的前提下执行：qobs不是官方缺失token且ckhs=1；每完整公历年至少90%有效日，至少10年。全882站有800满足单站规则；这不等于800有可用真实上游。coverage_by_year含29775站年行，不包含Q均值、极值、分位、相关性或误差。

两站的checked日期mask逐年求交，实际共同有效日计数用于717对筛选，不用两个单站覆盖率的最小值假装联合覆盖。bit mask仅日期/缺失/QC，不能恢复Q数值。当前以公历年做metadata可行性筛选；未来水文年/最后5年、连续窗口与样本掩码在B2重新明确冻结，不能声称已完成最终评价划分。

141候选不是无条件自然河道真值：两端degimpact低/无只属既有资格信息，沿程全部调节、缺口插补日、发布时间和供数特殊许可尚待闭合。qceq/qcol只统计现成代码，不由其新筛掉洪峰；缺口日期另存230文件，本轮未把插补后非缺测一律称原始无插补日。

先前规划40/60目标数量在92目标这个局部门槛上达到，但不保证功效，不抵消独立系统和负对照不足。完整准入0，禁止自动训练。
''')
write('b1a_independent_groups.md',prefix+'独立系统与输水依赖\n\n'+scope+f'''
站点图有25个连通分量；不能把它们当25个独立流域。RiverATLAS MAIN_RIV实际对应3个自然系统：20282220（Elbe）、20323928（Rhine）、20498112（Danube）。明确映射站数分别6、43、791；A/B内另19站缺river reach映射，不能补造ID。

官方River_regions的18个region与Danube_A/Danube_B等宏区只作区域元数据；Danube_A/B共享同MAIN_RIV，全部合并到Danube，不按行政/区域拆独立重复。地形A多边形用于实际重叠检查，站间有向路径与同terminal系统分别保存。

81条Crossbasin_water_transfers记录中，有5条明确连接Danube和Rhine自然root（33→7、48→9、49→9、50→9、817→1）。保守合并后只有**2个已知输水依赖组**：Danube+Rhine与Elbe。这是临时依赖上界，不是两个已经证明完全独立的重复；还存在6条未完全定位的转移关系，含4个To_ID=0的域外去向，需要维护者补充。

141暂定候选只涉及两个自然root，但其目标全部位于同一输水依赖组：{target_groups}。因此当前暂定目标组数为**1**，完整认证独立目标组数0。Elbe的少量可用站作为邻站输入候选，不能凭此创造有连通上游对的独立Elbe目标。

模型学习标签不得在未来测试上下游组成中回流；因此共享干流、重叠集水区和已知输水要整体分组，不能忽略输水换取组数。空间/气候共同驱动还需额外区块敏感性，不把不同root当统计完全独立。

完整跨系统train/dev/test验证当前BLOCKED。不是计算功效后判定，而是结构上可用目标组不足；没有擅自拆开Danube或放宽调节等级。需新独立系统或经明确批准修改估计目标，不能靠更多同河网边数修复。
''')
write('b1a_neighbor_matching.md',prefix+'不连通邻站与共同支持\n\n'+scope+f'''
当前严格临时池377站（10年checked覆盖、低/无影响、明确输水组、可用静态描述符、指定河段距离≤500m）。候选必须donor→target与target→donor均无路径，且不同已知输水关联组；再做A多边形实际intersection，面积>1m²则拒绝，避免近邻/支流误标。

对141暂定连通对执行metadata-only匹配提案：面积相对真实连通donor为0.5–2倍、干湿度比0.5–2、目标距邻站≤500km，至少10年联合checked覆盖。此处干湿度比是合法气象共同支持筛选，不冒称已有独立气候区分类。排序用面积、干湿度、海拔、降水季节性和相对目标距离偏差；未计算Q相关性或预测损失。规则在B2尚需冻结，不能称最终随机化/因果匹配。

得到116条候选关联（不是116个独立站），70个unique目标至少一个控制；实际只用了**2个unique负对照站ID377与378**。99个连通donor-target对有控制：82对一个、17对两个；没有任何目标/连通对达到三个。

实际共同支持记录在matching_common_support.json：282个跨组候选比较中120满足面积卡尺、261满足干湿度卡尺、116同时满足；距离卡尺并非瓶颈。未经匹配原始面积比范围0.0083–68.10，不能外推到面积比r→0处回归截距并解释额外传播因果效应。匹配后区域与供数站高度受限，两个被反复使用的邻站不是几十个独立控制重复。

由于Danube与Rhine已因输水合并，不能把它们互当主负对照；同一目标上方汇合的两条支流都是真上游，不当负对照。更弱的同系统非嵌套支流控制可以另提协议，但本轮不自动改主估计目标或放宽。

许可/遗漏输水/相同输入可得时刻和地域共同支持仍CONDITIONAL。候选记录明确NOT_FINAL_MATCH。LEVEL_A为增量预测价值；LEVEL_B为共同支持内连通相关优势；LEVEL_C物理路由因果不可声称。未来需同时保留统一C0的绝对RMSE/MSE与各供数站气象基线下增量，不能把不同分母skill相减叫纯连通效应；具体模型统计留待B2冻结。
''')
write('b1a_label_blindness_validation.md',prefix+'标签盲受限读取验证\n\n'+scope+f'''
两个合成测试层均在真实Q读取前完成：通用缺失/QC输出不变性，以及真实YYYY/MM/DD/qobs/ckhs/qceq/qcol schema、逐年checked mask不变性。替换所有非缺失Q为数量级或符号完全不同字符串，输出完全一致；修改缺失token或QC可改变计数；未知schema/QC值拒绝。结果见blind_coverage_synthetic.json、actual_schema_synthetic.json。

实际程序scan_coverage.py仅读sealed_runoff中的882份日文件，日期转datetime，qobs只做字符串缺失比较，QC只读取代码；不执行float(qobs)、求和、均值、方差、最大、分位、相关、图或评分。输出29775行日期/QC覆盖计数及checked日期位掩码。签名表仅表头识别，签名数值和COSERO输出未解码；气象仅读表头。

零真实Q数值统计不等于零接触字节：下载、哈希、提取和受限解析均访问含Q文件；非缺失Q字符串只用于存在性测试，没有记录。交互工具未打印真实Q行；不把允许的checked/缺失比例当水文签名。

隔离级别：同Windows账户目录+程序政策，**不是OS访问隔离、沙箱账户或密码学封存**。完整archive仍含标签。未来模型开发前需冻结读取入口、权限/角色分离、日志与泄漏测试；本B1A程序性通过不能替代独立评分器部署。

输出机读表禁止Q数值列，station_metadata的coverage为ELIGIBILITY_ONLY；impact/QC既有字段可能源于目标Q，不能用于模型。B0历史汇总显示例外保留在冻结B0验证报告，本轮未重复该访问。
''')
write('b1a_license_audit.md',prefix+'许可与供数条件\n\n'+scope+f'''
三项实际证据：Zenodo正文CC BY-SA 4.0；API metadata.license.id=cc-by-4.0；归档Info_english/4_Creative_commons_license_4.txt为CC Attribution 4.0正文。**仍存在不一致**，不选择更宽松标识，公开发布/派生benchmark授权CONDITIONAL，需维护者澄清。

Info_english/3_References明确供数来源HZB、GKD、LUBW、BAFU、CHMI及其他气象/地形/地类来源；已经读取，引用条件不等于每个原供数合同条款完整附在包内。Zenodo正文有捷克不得设运行性预警系统条件；本轮是离线科研数据审查，不宣称获准预警部署。未发现需要停止本轮离线清点的新增禁止条款；研究以外用途、原始再分发或商用部署不据此授权。[官方记录]({source})

Info没有完整提供原供数方特殊合同/日值发布时间；德国来源可能事后修订，需保留本版本。包内有Impacts.shp和Crossbasin_water_transfers.csv，不能称完全没有影响资料；额外坝库/输水点线、库容和有效面积的更新补充仍REQUIRES_PROVIDER_SUPPLEMENT。[资料说明]({paper})

typimpact/degimpact/diur_art/diur_glac只限资格/敏感性；不能因为官方提供就默认独立于Q。许可不一致、域外输水和影响资料不足均保留，未向维护者发送邮件；仅起草联系文稿。完整许可审查状态CONDITIONAL，不将引用论文的开放许可替代数据产品许可。
''')
write('b1a_provider_email_draft.md','''# 维护者联系草稿（未发送）

To: christoph.klingler@boku.ac.at
Subject: LamaH-CE v1.0 license clarification and metadata for label-blind network benchmark

Dear LamaH-CE maintainers,

We are preparing a research benchmark on connected versus unconnected donor information for ungauged target stations. We downloaded the official daily v1.0 archive (Zenodo 5153305) and verified its published checksum. Target discharge remains accessible only to a restricted date/missing/QC counter; no target discharge summaries or model evaluation have been conducted.

Could you clarify the intended data license? The Zenodo description states CC BY-SA 4.0, whereas the API license and bundled English license text indicate CC BY 4.0. Please also provide the source-provider special conditions relevant to research use and redistribution.

Could you share metadata-only reservoir/diversion/transfer supplements, especially terminal destinations for transfers with To_ID=0, effective catchment areas and storage metadata, and clarification of omitted or unresolved cross-basin links? We would also appreciate station migration/snapping documentation and the daily observation/publication time convention. No discharge-value attachment is requested.

We will cite the dataset, paper, version and required source references. We are not requesting authorization for operational warning systems. Name and affiliation will be supplied by the project owner before sending.

Best regards,
Project owner (to complete)
''')
statuses={'B1A_DATA_ACQUISITION_COMPLETE':'PASS','B1A_ARCHIVE_CHECKSUM_PASS':'PASS','B1A_LABEL_BLIND_SCAN_PASS':'PASS_PROGRAM_POLICY_ONLY','B1A_TOPOLOGY_CANDIDATES_VERIFIED':'CONDITIONAL','B1A_PAIR_INVENTORY_COMPLETE':'PASS','B1A_INDEPENDENT_GROUPS_ESTIMATED':'CONDITIONAL','B1A_MATCHING_POOL_ASSESSED':'PASS','B1A_LICENSE_REVIEW_COMPLETE':'CONDITIONAL','B1A_READY_FOR_B2_REVIEW':'BLOCKED'}
# Preserve allowed status vocabulary, with isolation qualifier as a separate field.
statuses['B1A_LABEL_BLIND_SCAN_PASS']='PASS'
decision=dict(stage='VHS-NEXT-B1A',status='COMPLETED_AND_STOPPED',date_singapore='2026-10-16',overall='NO_GO_CURRENT_MULTISYSTEM_BENCHMARK',gates=statuses,label_blindness_scope='program-policy only, no OS or cryptographic boundary',counts=dict(direct_gauge_edges=834,riveratlas_nested_candidates=808,both_endpoint_snap_le500m_candidates=726,joint_checked_coverage_pairs=717,low_no_impact_pairs_before_snap=162,provisional_pairs=141,provisional_targets=92,sufficient_single_station_coverage=800,natural_systems=3,known_transfer_merged_groups=2,provisional_target_transfer_groups=len(target_groups),fully_certified_independent_target_groups=0,targets_with_any_control=70,unique_control_stations=2,targets_with_three_controls=0,fully_admitted_pairs=0),training_authorized=False,training_runs=0,spatial_scores=0,gpu_runs=0,auto_next_stage=False)
(E/'b1a_decision.json').write_text(json.dumps(decision,ensure_ascii=False,indent=2),encoding='utf-8')
write('b1a_go_no_go.md',prefix+'最终准入判断\n\n'+scope+f'''
**B1A已完成获批清点，停止。当前多独立系统benchmark：NO-GO；B2/B3/B4未启动。** B0“数据未取得”的阻断已经实际突破，但不能把下载成功升级为研究设计通过。

'''+''.join(f'- {k}：**{v}**。\n' for k,v in statuses.items())+'''
标签盲PASS限受限程序及合成测试；拓扑CONDITIONAL保留snap/影响/边界缺映射；PAIR_INVENTORY_COMPLETE表示真实候选与损耗已清点，不表示834/808全部科学准入。MATCHING_POOL_ASSESSED表示已执行评估，其结果不达三对照规划。

## 对用户十个问题的实际回答

1. 官方完整日包已获得；只下载指定归档。
2. 大小1,477,248,617字节、官方MD5一致，SHA-256已记录。
3. 882日Q文件已分类隔离并通过只输出日期/缺失/QC的合成不变性测试；仅同账户程序策略，未声称OS或密码学封存。
4. 834直接站间边；808有RiverATLAS有向路径及嵌套几何，726两端指定河段距离≤500m。逐级资格后141暂定对、92目标；完整准入0。
5. 800/882站具有至少10个≥90%已检查且非缺失的公历年。使用权限仍附许可/供数条件，不把覆盖计数叫无条件合法再发布。
6. 25图分量、3自然主河系统；已知输水合并为2组，而141暂定候选目标仅1组，全部认证独立目标组0。
7. 70目标有至少一个暂定邻站，实际仅2个unique供数站；达到三个控制的目标0。没有凑数或看Q表现择邻站。
8. 主要阻断是Danube–Rhine跨流域输水、未完全定位/域外转移和snap/调节补充；许可正文/机器/包内文本冲突与原供数附加条件仍待澄清。
9. 已有足够真实资料开展未来获批的“B2设计问题审议”，但不足宣布当前多独立系统、公平三邻站方案READY。B1A_READY_FOR_B2_REVIEW保守BLOCKED，不自动启动B2，更无任何训练授权。
10. 当前最重要缺失证据是：**更多真正独立、具有连通目标对且位于公平邻站共同支持范围内的水文系统**。在现数据中未证实该条件；追加同一Danube/Rhine网内站点对不能解决。

## 最小后续动作（建议，未执行）

先由项目持有人核准并发送已起草维护者邮件，获取许可澄清、完整输水去向及最新坝库/有效面积/迁站资料。没有代发邮件。若保持原主估计目标，需经下一次明确批准调查补充独立系统与邻站的metadata；不自动下载其他数据。若改用同系统非嵌套支流控制，必须明确是较弱的LEVEL_B估计目标并另行预注册，不能伪装跨完整系统验证。

LEVEL_A增量预测价值与LEVEL_B共同支持内的连通相关优势分别定义；LEVEL_C物理路由因果不作主张。具体模型/统计留B2冻结：保留统一C0绝对RMSE/MSE以及供数站气象基线下增量，不用不同分母skill相减冒充连通因果；r→0回归截距不直接可识别。

E4/E5、S0/S0.1、R0/R1/R2/R3、B0、原始新疆数据与论文哈希复核见验证报告。无真实训练/重拟合、Q数值探索、评分、GPU、GNN、路由或旧结果改写。完成后停止等待下一次批准。
''')
# Keep pre-download validation as a separate immutable historical record before current-stage report replaces it.
old=R/'b1a_validation_report.md';saved=R/'b1a_preflight_validation.md'
if old.exists() and not saved.exists():shutil.copyfile(old,saved)
write('b1a_validation_report.md',prefix+'验证报告（最终检查待执行）\n\n'+scope+'真实清点已完成；最终脚本将核验冻结哈希、机读表、输出边界与交付清单后补写本报告。不得把此暂态报告作为最终PASS。')
lines=['stage=VHS-NEXT-B1A','date_singapore=2026-10-16','status=COMPLETED_AND_STOPPED','overall=NO_GO_CURRENT_MULTISYSTEM_BENCHMARK']+[k+'='+v for k,v in statuses.items()]+['isolation=PROGRAM_POLICY_ONLY','training_runs=0','spatial_scores=0','gpu_runs=0','B2_started=false','B3_started=false','B4_started=false','auto_next_stage=false']
write('b1a_status.txt','\n'.join(lines))
provenance=dict(record='https://zenodo.org/records/5153305',version='1.0',archive=arc,download_events='evidence/download_events.json',archive_member_manifest='evidence/archive_members.csv',extraction_manifest='evidence/extraction_manifest.csv',label_policy='sealed_runoff; restricted missing/date/QC only',official_Info_read=['1_Folder_structure.txt','2_Timeseries.txt','3_References.txt','4_Creative_commons_license_4.txt'],license=dict(page='CC BY-SA 4.0',API='CC BY 4.0',bundled_text='CC BY 4.0',status='CONDITIONAL_CONFLICT_UNRESOLVED'),model_output_and_signatures='quarantine; not decoded except blacklist header identification',date_singapore='2026-10-16',user_authorization='B1A only, explicit current-turn approval')
(H/'provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(decision,ensure_ascii=False))
