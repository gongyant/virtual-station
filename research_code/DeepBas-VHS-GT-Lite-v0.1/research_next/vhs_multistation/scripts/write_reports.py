"""Assemble B0 reports from metadata evidence only; no fitting or discharge access."""
from pathlib import Path
import json,csv,collections
H=Path(__file__).resolve().parents[1];ROOT=H.parents[1];E=H/'evidence';R=H/'reports'
def load(n):return json.loads((E/n).read_text(encoding='utf-8'))
def write(n,text):
    p=R/n
    if p.exists():raise RuntimeError('Preserve existing report: '+n)
    p.write_text(text.strip()+'\n',encoding='utf-8')
facts=load('local_complete.json');hist=load('integrity_before.json')
with (R/'b0_candidate_station_pairs.csv').open(encoding='utf-8',newline='') as f:pairs=list(csv.DictReader(f))
prefix='# VHS-NEXT-B0｜'
scope='审查日期：2026-10-11（Asia/Singapore）。仅数据结构、允许的元数据、河网属性与文献。新目标 Q 数值不进入本轮分析；不训练、不评分、不启动 GPU。\n\n'
CE='https://essd.copernicus.org/articles/13/4529/2021/'
ZEN='https://zenodo.org/records/5153305'
ICE='https://essd.copernicus.org/articles/16/2741/2024/'
HS='https://www.hydroshare.org/resource/705d69c0f77c48538d83cf383f8c63d6/'
HR='https://www.hydrosheds.org/products/hydrorivers'
HB='https://www.hydrosheds.org/products/hydrobasins'
LIC='https://data.hydrosheds.org/file/technical-documentation/HydroSHEDS_TechDoc_v1_4.pdf'
write('b0_dataset_inventory.md',prefix+'候选数据清单\n\n'+scope+f'''
## 本地资源及证据边界

1. `data/raw/stations/新疆基本水文站.kmz`：130 个 Placemark；`前苏联水文站点.kmz`：1382 个。它们是地理站点目录，不能当作1512条流量序列。B0读取站名、坐标、白名单身份字段；正式供数者、有效期和再发布权仍未核实。目录证据见 `../evidence/station_catalogs.json` 及两个 inventory JSON。
2. `data/raw/runoff/`仅见三个工作簿。`BYBLK-DSK日数据.xlsx`：Sheet1，声明范围 A1:C16803；`Q-dsk-byblk.xlsx`：BYBLK、DSK、Sheet3，声明范围 A1:B246、A1:H253、A1；`Q-新疆.xls`：12个工作表，包括2000/2005支流、2005干流及SB/RS标记表。只读sheet目录和XML dimension，未读取工作表Q单元格。范围不等于有效记录数；sheet年份不构成精确日期覆盖证明。SHA-256和完整sheet目录见 `../evidence/workbook_structures.json`。
3. 已冻结S0来源审查记录两站1978-01-01至1983-12-31、2191日；B0只引用历史元数据，不重新打开数值，不把旧开发站转成独立盲测站。单位打印、日界、整编史、正式供数身份仍缺证明。
4. 早期五站2005资产：BYBLK/DSK各184日（05-01..10-31），ALAR/XQM/AQK各300日（01-02..10-28）；全五站共同窗口181日。日期/计数来自已有覆盖元数据，不重新验证原始数值。TARIM_*是项目别名；不是已核实官方ID。旧bundle包含OQ和来源不明MQ，禁止直接用作strict zero-shot基准。两个塔里木边仅为历史文献顺序/折叠边。
5. 早期34节点资产：`data/processed/nodes.csv`34站、`edges.csv`19边；NPZ头为2191×34×2，不能据shape认定34站都有观测。历史S0区分实际两站obs_q与WaterGAP等加工输入；WaterGAP不是测站原始Q，率定独立性也未核实。B0仅读NPY头，所有数组payload均未加载。
6. 本地 `data/raw/hydrorivers/HydroRIVERS_v10_as.*` 与 `data/raw/hydrobasins/hybas_as_lev12_v1c.*`是地形衍生河网/集水区，不是观测序列。B0从区域bbox内217163个河段的HYRIV_ID/NEXT_DOWN/MAIN_RIV/LENGTH_KM/UPLAND_SKM复核19条路径。节点UP_AREA为项目HydroBASINS匹配字段，不能冒充官方测站集水面积。没有重算全体集水区多边形，也没有证明官方下载链。
7. 本地有ERA5-Land、WaterGAP、静态/DEM/SWORD目录。现有已审查气象覆盖服务旧BYBLK–DSK域；不能证明34站或前苏联目录具备逐站气象覆盖。WaterGAP、MQ、已率定物理输出均不自动成为合法无资料输入。其他原始Q文件在本轮有界 `data/raw/runoff` 清单中未发现；不宣称全磁盘不存在。

## 公开候选及可访问性

- **LamaH-CE，首选元数据获取对象**：正式说明区分859个集水区与882条站点径流序列，提供日/小时资料及有向关系字段；数量均不是嵌套对数。[数据论文]({CE})。真实合格对数和完整独立系统数尚未枚举。
- [Zenodo v1.0]({ZEN})可公开查看；概念记录4525244跳转到5153305，版本DOI为10.5281/zenodo.5153305。页面列daily包约1.5GB、daily/hourly约14.8GB；未下载。数据描述有CC BY-SA 4.0及来源附加条件，详见许可报告。[来源]({ZEN})
- **LamaH-Ice，补充候选**：论文描述107流域及日/小时资料。[论文]({ICE})。当前公开v1.5页面已核实存在；旧资源被新版本替代。未枚举该版本站点表、嵌套对或独立系统；不能把论文107流域无条件转为v1.5合格对数。[资源]({HS})
- **CAMELS-US，区域化参考候选**：正式数据说明已核对DOI10.5194/hess-21-5293-2017；不能由其流域数推断嵌套站点对。此次未核验其逐站拓扑及仓库许可，故不作为已确认拓扑样本或已授权完整下载来源。

本轮公开数据访问为论文、仓库目录与许可说明，没有下载流量归档。原始测站观测、资料编整后的观测产品、模拟输出和项目训练张量在以上条目中分别列明；哈希只证明文件一致性，不证明科学真实性或许可。
''')
rootcounts=collections.Counter(r['main_river_id'] for r in pairs if r['directed_path_verified']=='True')
write('b0_topology_verification.md',prefix+'拓扑核查\n\n'+scope+'''
## 当前结论

候选21对：原34站图19对，加五站图中2条TARIM别名边；BYBLK→DSK跨资产去重。19/19项目边的两个匹配河段确有NEXT_DOWN有向路径，距离与旧edges.csv一致，节点UP_AREA均下游大于上游；候选端点的项目snap距离约6.17–187.16 m。这只支持**被映射河段的几何连通**。

正式可信准入对0。全部候选 `topology_status=TOPOLOGY_UNVERIFIED`，并用独立布尔列 `directed_path_verified`保存部分成功证据。原因是官方身份与坐标时效、竞争河段snap、整条路径调节/人工水系等未闭合。不能由距离小或节点reservoir_flag=0证明正确河道或沿程无坝。

ALAR→XQM、XQM→AQK没有正式ID/坐标映射、河段有向路径或可信河距。后者是跨过Yingbaza/Usman的历史折叠关系，不能认定中间不存在观测支流站。均不得作为已确认拓扑效应样本。

## 十项逐对要求与当前证据

1. 身份：CSV保留项目ID/站名；官方供数部门站号、迁站历史和同名消歧未核实，TARIM仅别名。
2. 同网：19对在同一原始河网有路径；2对未知。几何网络与实际受调节水系需分别证明。
3. 有向路径：保留每条HYRIV_ID链与目标边界reach，见 `../evidence/directed_paths.json`；遇到缺失/环/边界截断不能以近距离补连。
4. Snapping：现有最近河段匹配只是候选；后续在统一投影下比较多个候选、汇流口上下方、平行渠系和原始站位置。500m是预筛复核提示值，不是自动真实性证书；本轮未做独立影像/官方河道复核。
5. 面积：项目UP_AREA19对单调；正式area_gov、精确站点集水区及与HydroRIVERS UPLAND_SKM的一致性仍需核验。面积差超过20%须解释，人工输水应提供有效面积，不能事后调面积追拟合。
6. 调节：全路径坝库、调水、灌渠、回流、跨流域转移和时效均UNVERIFIED；主分析优先元数据确认低/无调节，未知不并入自然组。
7. 其他测站：全路径支流汇入及观测站完整清单未获得；已有19条最短站间边不证明无遗漏支流站。
8. 距离：河距为完整上游匹配reach至目标前一个reach的LENGTH_KM之和；没有按端点在线上位置截取，不能称精确站间行程。BYBLK→DSK为68个前置reach的212.61km，目标边界reach另列，不混用其他历史口径。
9. 时间/单位：本地原始打印、日界、时区、单位与发布延迟尚未证明。日期覆盖引自S0/已有覆盖表，非B0逐值核验。
10. 权利：本地站点/流量供数与再发布许可UNVERIFIED；河网产品使用条件已查官网，但本地拷贝来源认证仍缺。

## 预定准入规则（任何新标签打开前适用）

- 官方ID、坐标/有效时期、合法观测来源、单位/日界、QA与完整路径为必需；不以模型分数决定准入。
- 日尺度主样本规划至少10年共同QA有效观测，按每年联合有效日比例≥90%预筛；需供数方只提供日期/QC/可用性掩码完成核查，不给开发者目标Q。主要比较使用C0/C1/C2完全相同评价日期。季节性短期资料只能明确报告局限，不放宽成长期主样本。
- 元数据完整但不达10年的候选可单独标记短记录探索层，不与主层汇总，不伪造功效。25–30对为规划目标，40对以上理想，均非功效阈值；0合格时不得凑数。
- 每个目标主分析预定选最近且合格的已观测上游站；若有多个上游支流，以完整支流清单定义，禁止看目标Q决定哪个上游最有利。共享站/共享路径的多对保留依赖标记。
- 数据集拓扑字段应与另一独立河网/官方图交叉核查；不得单靠同一加工图的自洽性宣告真实性。
''')
write('b0_metadata_and_license_audit.md',prefix+'元数据与许可\n\n'+scope+f'''
## 本地：UNVERIFIED

新疆及前苏联KMZ提供地理目录，不附可核实逐站原始观测供数合同；三个流量工作簿只证明文件存在。来源机构、原始单位打印、观测还是模拟、整编/补缺、迁站、日界、使用/公开再发布许可均不能由文件名或OQ标记推断。Q-dsk-byblk月序列不能自动称独立官方观测。不要再发布这些原始Q或把来源不明MQ作为输入。

34节点加工图、NPZ训练张量、WaterGAP采样和未知MQ均不能替代原始水文站观测。B0保存哈希及目录结构，不复制原始流量内容。

## 公开：产品逐项核验

1. **LamaH-CE**：仓库v1.0描述明确CC BY-SA 4.0，需作者/论文、版本、Info内各来源署名及改动说明、适用共享条件。捷克径流另列禁止用于运行性预警系统的条件；德国来源可能事后修订。正式用前获取Info和源部门条件，并审核兼容性；本轮未获得包内Info，故公开再发布整合benchmark仍CONDITIONAL。[仓库]({ZEN})。不能把论文CC BY 4.0当数据许可。
2. **LamaH-Ice**：v1.5仓库正文将径流设为CC BY-NC 4.0，其他资料CC BY 4.0；通用页面又显示CC BY，必须按分项限制审查，不能套用通用标签开放商业使用。原始供数IMO/NPC可追溯修订；下载与版本文件可取性未实际测试。[v1.5]({HS})。不复制数据、不代用户接受下载许可。
3. **HydroRIVERS/HydroBASINS v1**：官网允许科学、教育及商业使用，采用HydroSHEDS v1协议。该协议Appendix A §2.1.2限制独立原材料再分发，衍生产品仍受条款约束；不能改标通用CC BY。B0只发布项目审查及少量路径证据；完整原图层不重新打包。[河网]({HR})、[集水区]({HB})、[协议Appendix A]({LIC})。本地原始下载凭据/当时版本条款仍需归档。
4. HydroATLAS与以上产品许可不能混同；若后续使用其属性需另审。尤其长期平均流量、径流签名、目标Q率定产物不能因出现在“静态属性”表而成为无资料描述符。
5. CAMELS-US：文献标题/DOI已查，数据仓库细项授权及真实嵌套关系此次UNVERIFIED；不作为已审核许可来源。

## 时间制度与泄漏防线

LamaH-CE日流量为m³/s；奥/德/瑞日值按GMT 00:00–23:59整合，捷克制度须单独核验；数据论文说明1981–2017研究窗口。观测缺测标记−999、质量标记及插补信息需保留；不得按0流量解读缺测。[论文]({CE})

归档中的观测日期不是发布时间。只允许供数方给出的 `interval_start/end/timezone/release_time/QC_revision_time`在发行时点前可用输入；暂无release_time时仅能设计retrospective reconstruction，不能称实时预报。ERA5再分析也要采用其真实可用时刻；没有实时气象供给证明时只作回顾性信息重建。

只允许读取日期覆盖/QC缺测掩码、站点属性与许可；不允许目标Q均值、季节统计、FDC、runoff ratio、由Q反推area或率定参数。公开库中的hydrological signatures、COSERO已校准输出、未知MQ和目标依赖gap filling都需排除或单独封存审查。模型训练期可使用训练系统Q，测试系统任何站的Q不参与参数学习。
''')
write('b0_independent_network_count.md',prefix+'独立系统计数\n\n'+scope+f'''
完整准入站点对：**0**；可认证且具有准入对的独立河网系统：**0**。这里的0是“已完成全部证据门槛的计数”，不是断言真实世界没有这些站点。

原34节点覆盖6个不同MAIN_RIV ID：{', '.join(map(str,facts['graph_main_river_ids_all_nodes']))}。19条有向路径候选覆盖其中5组：

'''+''.join(f'- MAIN_RIV {k}：{v}个候选对。\n' for k,v in sorted(rootcounts.items()))+f'''

五站加工资产的2个component不等于2个独立系统；TARIM两边的MAIN_RIV未知。对跨盆地人工联通、内流区、共同干流及研究区外汇流均未核实，所以5组也不是已认证5个独立研究重复。不得把丹ube子支流或大河内部小子网任意改名独立系统。

## 后续计数与划分算法（只设计）

1. 使用完整域有向河网追至海洋/明确内流终端；记录terminal basin/root、全上游面积多边形与域外出口，不在研究区边界截断就宣布独立。
2. 构建依赖联合图：同terminal完整系统、共享目标/上游站、嵌套/重叠集水区、已知调水/回流联通均合并分组。自然不同root但存在跨域人工输水也合并；不确定连接为保守组或隔离，不拆小增加样本。
3. 气候/区域共同驱动不会自动等于同一河网，但统计层面增加空间/气候区块与距离缓冲；缓冲大小及规则由元数据和训练域决定，测试后不得修改。
4. 分别报告unique stations、unique targets、directed pairs、eligible pairs、complete systems、每组对数和最大组占比。各系统等权为主结果，站点对等权为补充；多条边共享目标不重复当独立样本。
5. 外层leave-one-complete-system-out或事先固定完整系统train/dev/test；内部超参也按完整训练系统划分。若数据仅一个大terminal系统，无法完成核心跨完整系统检验；分支留出只能标明较弱探索设置。

LamaH-CE文献包含丰富嵌套关系，但本轮未获取逐站拓扑表，完整系统数量UNKNOWN。是否主要集中于同一大河需按上面规则核验。LamaH-Ice可作为扩大独立系统的候选，但也未计数。25–30/40+对是采集规划，需同时给出系统数、组规模和训练域留组功效模拟；不以日样本量充当独立重复。[CE说明]({CE})、[Ice说明]({ICE})
''')
write('b0_strict_ungauged_protocol.md',prefix+'严格无资料协议 v1.0\n\n'+scope+'''
## 科学问题与预声明

Under what conditions does physically connected upstream discharge provide transferable predictive information for ungauged downstream stations, beyond seasonal, meteorological, and regionally correlated information?

H1：在完整未见河流系统上，C1相对C0的系统等权预测增益为正。H2：在预匹配且信息预算一致的负对照下，C1相对C2增益为正。两者都可被零/负增益证伪；不能挑选成功流域报告。

H3：事先描述符（上/下游面积比、对数河距、气候干湿度、元数据调节等级）能解释增益异质性，并预测未参与开发系统的增益。只在训练/开发系统拟合一个预限定低复杂度增益模型，外部比较其误差与训练域常数预测；没有足够系统则报告不可估计，不用目标结果筛描述符。调节可能改变信息传递，不预设所有系数方向。连通优于邻站只说明与连通性一致的可迁移预测信息，不能单独证明河道输移因果。

## 信息访问角色

- metadata curator：提供正式身份、日期/QC掩码、非Q描述符、拓扑和许可；不向开发者提供测试目标Q或其派生统计。QA分层不是根据模型表现筛站。
- developer：仅训练系统Q与合法描述符；测试系统全部站的Q都不用于训练、校准、季节气候态、归一化、超参、特征选择、状态订正或人工看图。
- inference service：模型冻结后仅按发行时点释放允许上游/负对照Q；这些是输入专用站，不是学习标签。目标站历史Q始终不可见，暖启动状态只由合法气象/上游输入生成。
- independent evaluator：冻结预测/哈希之后单次解封目标Q计算预定分数，保存受限日志。不得将逐站分数用于再次修改主模型或匹配。

本轮没有新建目标标签库或打开新标签；以上是待实现的访问控制方案，并非声称只靠文档已经完成技术隔离。已有BYBLK/DSK开发历史不可撤销，因此这两站不得作为新方法的盲测主样本。

## 合法输入与单位

C0从训练流域学习共享的区域季节/气象响应：日历正余弦、因果可用气象历史、独立静态面积/地形/土壤/气候描述符；共享输出采用由合法面积换算的mm/day或训练域尺度再转m³/s。训练域归一化参数冻结应用于目标；不得用目标Q均值/方差、月气候态、FDC或目标校准模型输出。

目标站完全无标签不代表无地形/气象；所有允许描述符必须记录来源、版本、时间覆盖和非Q依赖。不得输入未知MQ、目标专属嵌入率定、目标泄漏插补、目标校准COSERO/WaterGAP产物。训练站编号记忆不能替代可迁移描述符；未见站参数只能由共享模型产生。

明确任务为发行时刻T预测目标下一完整水文日，主时效24小时；历史归档缺发布时间时只能执行后来获批的回顾性重建轨道。任何Q/气象区间必须在T前结束且实际release_time≤T；简单t−1不自动证明可得。ERA5同日最终再分析不可当当时预报。不同国家日界先按正式说明映射，不能不看制度直接shift。

## 空间留出与冻结

完整河流系统分组算法见独立系统报告。目标、所有上游、同系统其他站、人工联通组及空间缓冲内风险站整体分配；任何测试上游Q只能在推理侧出现。训练、超参验证、测试使用不同完整组；多个同流域边不得跨集合。

目标清单、C2邻站匹配、时间窗、QA掩码规则、特征、延迟、超参搜索预算、随机种子、模型/指标代码和哈希均在评价前冻结。测试时期规划为预固定共同记录最后5个完整水文年，若有时间制度/覆盖不满足需元数据阶段说明并在任何标签评分前修订版本；不能按表现挑年份。训练系统同年份Q可用于空间外推任务，但不得用未来气象；若主张时间外推，另设先训练后评价的更严格时间轨道，不混称。

训练域气候描述符可采用预定固定气候期；不能用测试未来时期气象估计实时可用描述符。数据源方法开发者若已看过特定公开站Q/评分，应登记站点污染，转入开发集并另选未参与开发系统。公共数据并不自动成为独立盲测证据。

## 指标与不确定性（只设计）

主终点：各对同日期的ΔNSE(C1−C0)与ΔNSE(C1−C2)，先对unique目标汇总上游对，再对系统平均，最后系统等权平均；同时报告系统中位数、正/负增益比例及全部失败系统。两主比较采用Holm控制家族错误率0.05；证据不足不等于无效。

补充NSE、KGE2009（r、标准差比α、均值比β）、RMSE(m³/s)、有符号Bias=100×Σ(pred−obs)/Σobs、体积误差、低流量及洪峰幅值/时间误差。尺度化RMSE仅用训练域尺度或合法面积。评分器可以计算目标均值/方差作NSE/KGE分母，但这些统计不得返回模型、匹配或任何归一化步骤。零方差/零均值站按预定规则记undefined并报告，不能为了提高分数事后删除。

低流量/洪峰诊断由独立评分器按每站评价Q的20%/90%分位预定定义，**只用于预测冻结后的评分**，不得筛站/调参。峰事件为连续超阈值段合并，峰时误差单位天；具体相邻段合并间隔及缺测处理由下一次预注册在评价前固定。主要NSE比较不依赖事件阈值。缺失输入不许偷偷换对照或挑日期；共同掩码、覆盖率和全日期缺输入表现同时报告。

不把日样本当独立重复。置信区间以完整系统为外层cluster bootstrap，保留系统内嵌套关系；组内时间块长度从训练域自相关估计后冻结。建议2000次重采样，报告组数、小组敏感性和留一系统稳健性。组太少则区间仅描述性，不作大量独立证据；用训练域模拟估计可检测效应。跨系统共同天气另做区域/年份区块敏感性，bootstrap不是自动独立性证明。

## 停止与版本边界

B0仅设计，数据准入未通过，不启动上述任何真实拟合/评分。不得回到1978–1983搜索lag或模型，不改E4/E5/S0/S0.1/S1A-R0/R1/R2/R3，不装配E5I1。下阶段需要明确批准并先完成元数据补全、隔离实现、synthetic-only泄漏测试及协议冻结；只有随后另行获批才能打开训练域Q并执行独立实验。
''')
write('b0_connected_vs_unconnected_control.md',prefix+'连通与不连通信息对照\n\n'+scope+'''
## 对照定义

- C0：共享区域季节/气象/合法静态属性基线，目标无Q气候态。优先可审计低复杂度共享模型；研究价值由信息对照决定，不由最高NSE决定。
- C1：同一C0及相同训练预算，加真实有向连通上游Q（合法发布时间、共同回看窗、同一缺测机制）。面积换算仅用正式面积，不能由目标Q估计比例。
- C2：同一C0加预先匹配的不连通区域邻站Q，Q通道数量、回看窗、时间可用性、复杂度、优化预算均与C1一致。主分析一连通上游对应一邻站；多支流情况另冻结等通道匹配规则。
- C3：C0+独立可信路由描述/计算，只有几何、河坡、断面/参数及时间尺度可信且不依赖目标Q率定才准入。无可信参数时标记BLOCKED而不以未知MQ补位；单独明确是否含C1上游Q，以免把额外Q信息与路由效果混合。
- C4：未来Topology-aware GNN，B0不实现、不训练、不预设有效。

## C2预匹配算法

主候选池为与测试目标**完整河流系统不同**且没有双向有向路径、嵌套面积或人工输水联通的站；同terminal支流虽可能互不直接流经，也不作为最严格主负对照，可独立标注弱对照。只有距离近不能证明不连通。

主C2站所在系统也隔离为input-only测试/对照系统，Q从未参与共享模型训练；与C1上游的“未见系统、推理专用”角色一致。若采用训练域邻站Q是另一个seen-station次分析，不能混入主比较。

匹配只使用官方面积、固定期气候干湿度/降水季节性、平均海拔/坡度、地理距离、资料覆盖与调节类别。以训练域中位数/IQR缩放合法描述符，固定加权欧氏距离匹配；面积与干湿度权重各2，海拔/季节性/距离各1。初始卡尺：候选面积为上游站0.5–2倍、相同气候大类和调节类、优先500km内；这些为元数据预匹配提案，需在下一次站表取得后且目标Q不打开时固定，不以目标效果改变。无匹配则标记NO_MATCH，不能寻找最好击败的邻站。

邻站和真实上游相对目标的地理距离也须匹配/报告差异，避免把C1近邻优势当拓扑优势。遇到多个候选，按固定描述符距离、再按正式ID字典序取最小；缺必需描述符拒绝匹配。使用Top-3候选作为预定敏感性层，不根据其Q相关系数、NSE、残差或目标评价收益挑选。禁止用目标Q/目标与邻站相关性。一个邻站复用于多个目标时登记共享依赖，不增加有效系统数。

目前21对没有形成满足上述要求的已认证邻站匹配：**E=UNVERIFIED**。34站图的不同MAIN_RIV只能提供负对照候选，并非已经证实的独立不连通站。

## 可证伪与置换控制

主比较C1−C0检验上游信息增量，C1−C2检验连通一致的特异信息。保留所有负增益和分层失败；若C2与C1相当，区域共同驱动仍是可行解释。

后续预注册辅助控制：在相同面积/气候/时间制度匹配层内交换上游站身份；对允许的Q输入做完整水文年块置换以保留季节结构；同时保留原连通输入对照。对齐断裂和不同QA缺失需显式处理。不做按日独立洗牌的伪显著性检验；无可交换完整系统/年份时只作诊断，不能称严格随机化因果检验。置换数量、随机种子和多重比较规则在真实评价前冻结，不看测试结果决定。

置换是后续新增设计，不声称已有文献已证明本数据中的拓扑作用。小型GNN文献已有拓扑无增益结果，不能预设C1或C4一定胜出。主比较优先CPU可审计C0/C1/C2，C3/C4不抢先启动。
''')
gates={'A':'BLOCKED','B':'BLOCKED','C':'BLOCKED','D':'CONDITIONAL','E':'UNVERIFIED','F':'CONDITIONAL','G':'CONDITIONAL'}
decision=dict(stage='VHS-NEXT-B0',strategy='B',status='COMPLETED_AND_STOPPED',overall='NO_GO_MODELING',next_allowed_recommendation='METADATA_ONLY_ACQUISITION_AFTER_APPROVAL',gates=gates,fully_admitted_pairs=0,admitted_independent_systems=0,raw_directed_path_candidates=19,all_candidate_pairs=21,training_runs=0,spatial_evaluation_runs=0,gpu_runs=0,new_target_observation_payload_reads=0,auto_next_stage=False)
(E/'decision.json').write_text(json.dumps(decision,indent=2),encoding='utf-8')
write('b0_go_no_go_decision.md',prefix+'Go/No-Go判断\n\n'+scope+f'''
**战略B已接受；B0完成后停止。总判断：NO_GO_MODELING。** 可建议下一轮只获取元数据，不自动训练或打开新目标标签。

1. **A BLOCKED — 足够可靠的多站原始观测在手？** 本地只有两站冻结六年记录与五站不足一年历史覆盖，目录不等于流量。供数、单位/日界、权利未闭合；公开CE/Ice存在可信数据产品，但尚未完成站表、覆盖与本地取得核验。
2. **B BLOCKED — 足够真实嵌套准入对？** 19条原图有向路径成功，完整准入0；另2条TARIM别名边仍无路径证明。不能宣称达到25–30规划目标。
3. **C BLOCKED — 足够独立系统？** 5个候选MAIN_RIV组不等于认证独立系统，完整准入系统0。公开库系统分布未枚举，可能受少数大河集中限制。
4. **D CONDITIONAL — 严格零监督隔离？** 协议可设计，目标Q派生统计/未知MQ已禁止；尚无新数据的实际访问隔离与合成泄漏测试。旧开发站不能变成盲测站。
5. **E UNVERIFIED — 不连通邻站？** 合法描述符匹配规则已设计，未形成逐站可用、独立且同预算的邻站对照池。
6. **F CONDITIONAL — 合法气象/静态？** CE/Ice说明包含相应资料，许可已分项调查；Info来源与每站覆盖、无Q依赖、可用时刻未全部核验。本地两站气象不代表多站覆盖。
7. **G CONDITIONAL — 不开标签完成空间留出？** 元数据分组与封存方案可行，完整域拓扑、人工联通、独立系统数及技术隔离待实现。

PASS只用于已完成的具体检查（如19条路径、元数据审查和文件完整性），不把这些局部PASS升级成A–G数据门槛通过。BLOCKED是当前证据不足，不宣称数据产品永远不可行。

## 最小补充数据与责任人（计划；没有发送邮件）

- **项目持有人/新疆或原供数部门**：提供现有34站及TARIM别名的官方站号对照、坐标及迁站时段、河名/正式集水面积、日界/单位、可供年份和QA有效日期掩码、观测或模拟身份、许可/引用/再发布条件。前苏联目录由原整理者补国家/供数机构、官方ID和观测获取路径；不先向开发者提供目标Q数值。
- **LamaH-CE作者/仓库维护者**：优先只索取Info说明、Gauge_attributes与非Q静态白名单、NEXTUPID/NEXTDOWNID、stream-network几何或可校核reach IDs、日期/QC覆盖掩码、坝库/跨域输水补充元数据、原来源许可。包内文件命名以实际目录为准，不虚构“已下载”路径。仓库整体1.5GB不在本轮下载；若不能独立取元数据，请维护者打小包或以后另批。
- **HydroShare/LamaH-Ice作者与IMO/NPC**：补v1.5真实文件清单、正式站点/拓扑表、相同覆盖/调节信息与分项许可，作为新增独立完整系统的备选；不把107流域当107独立嵌套对。
- **GIS/水文资料管理员**：做正式站点snap人工消歧、全路径水库/人工渠系和支流站核对、完整域terminal分组与河距端点修正；记录复核者及证据，不用相邻距离补连。
- **独立数据保管人**：先建立标签封存和角色权限，输出仅日期/QC/来源的准入报告。下一轮通过元数据门槛后，再由用户批准获取训练域观测；测试目标Q只交评分器，开发者不接收。

规划25–30对、40+理想，需要同时报告真正独立系统数和组间差异；若系统不足应缩小论断，不放宽真实性。没有数据取得/身份确认/许可/零监督隔离，不进入模型阶段。

## 获批后第一个独立实验（本轮不执行）

先做无目标Q元数据闭环和synthetic-only隔离测试。随后在完整未见河流系统上，冻结相同共享低复杂度C0/C1/C2，进行一个预注册24小时信息对照实验；主比较系统等权ΔNSE(C1−C0)和ΔNSE(C1−C2)，同时报告负迁移与预定分层。若档案发布时间未知，则明确为回顾性重建实验。优先检验信息存在/失效条件，再讨论路由或GNN复杂化。

历史E4/E5、S0/S0.1、S1A-R0/R1/R2/R3及旧论文不修改；本轮完整性验证见validation报告。没有E5I1、BYBLK–DSK调参、真实拟合、GPU或空间评分。本阶段结束后等待下一次明确批准。
''')
write('b0_status.txt','''stage=VHS-NEXT-B0
strategy=B
status=COMPLETED_AND_STOPPED
overall=NO_GO_MODELING
A=BLOCKED
B=BLOCKED
C=BLOCKED
D=CONDITIONAL
E=UNVERIFIED
F=CONDITIONAL
G=CONDITIONAL
candidate_pairs=21
directed_path_verified_candidates=19
fully_admitted_pairs=0
admitted_independent_systems=0
new_target_observation_payload_reads=0
historical_aggregate_table_display_exception=DISCLOSED_IN_VALIDATION
training_runs=0
spatial_evaluation_runs=0
gpu_runs=0
large_dataset_downloads=0
historical_writes=0
auto_next_stage=false
awaiting_next_explicit_approval=true
''')
print('Reports assembled; literature and final validation are separate.')
