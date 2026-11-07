"""Assemble evidence-linked Chinese S0 reports; no scientific experiment execution."""
import json, re, sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE=ROOT/'research_next/vhs_transfer'
R=BASE/'reports'
F=json.loads((BASE/'data_audit/live_audit_facts.json').read_text(encoding='utf-8'))
M=json.loads((BASE/'data_audit/source_manifest.json').read_text(encoding='utf-8'))
T=json.loads((BASE/'tests/synthetic_results.json').read_text(encoding='utf-8'))
def link(rel,label=None):return f'[{label or rel}]({(ROOT/rel).as_posix()})'
def ev(rel,pattern):
    p=ROOT/rel; lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
    for i,line in enumerate(lines,1):
        if re.search(pattern,line): return f'[{rel}:{i}]({p.as_posix()}:{i}) (`{line.strip()[:180]}`)'
    raise ValueError(f'Missing evidence {rel}: {pattern}')
def write(name,text):
    (R/f'vhs_next_s0_{name}.md').write_text('# VHS-NEXT-S0｜'+text.strip()+'\n',encoding='utf-8')
intro='''
审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。
'''
write('source_inventory',f'''数据来源清单与检查范围

{intro}

## 核心资产

1. **1978–1983 日流量**：`data/raw/runoff/BYBLK-DSK日数据.xlsx/Sheet1`，日期列 Q，BYBLK→00705600（巴音布鲁克）、DSK→00705700（大山口）。首个非日期行为 OQ 标记，作为说明行剔除，不是缺测插补。两站各2191日、1978-01-01至1983-12-31，无重复、无日历缺日、无 Q 缺值。两站4382个站日与 `timeseries.csv`、E0 数据集逐值差为0；基础NPZ的 obs_q/y 与原值转float32后完全一致。原始单位打印、水文日界、官方供数者和原始整编历史仍未核实；OQ只是文件内语义标记。
2. **2005 OQ/MQ**：`data/raw/runoff/Q-新疆.xls`；支流sheet index9（2005-支流），干流index11（2005-干流）。BYBLK/DSK各184日（2005-05-01..10-31），ALAR/XQM/AQK各300日（01-02..10-28），每站自身范围内无缺测。合并张量303日×5站×2字段，缺测期间保持NaN和可用性标志。五站所有已导入 OQ/MQ 值、日期行号与工作簿一致，最大差0；这证明复制链，不证明MQ生成链或观测独立性。
3. **外部月序列**：`data/raw/runoff/Q-dsk-byblk.xlsx/DSK` A列年月、B列候选流量，另有BYBLK/Sheet3。文件creator刘铁、2018-06-09创建，仅是文件属性。官方提供者、单位、观测/模拟身份和与日序列共同来源关系仍未核实。E4D仅允许称 external monthly-series consistency evaluation。
4. **ERA5-Land**：下载脚本 `scripts/download_era5_land.py` 的CDS dataset为reanalysis-era5-land；`prepare_era5_land_daily.py`做00 UTC累计量前移一天、m→mm、K→°C；之后 `area_weight_era5_land.py` 与 `area_weight_incremental_era5.py` 面积加权。已读取1978–1983上游流域与增量流域NetCDF的实际变量、单位、时间及非有限值；均2191日。E4B0五个t−1滚动字段确定性重算最大绝对差<5.01e−9，缺失掩码一致。没有重跑原始逐小时下载/完整网格加权流程，原始下载证据以本地原文件哈希及历史审计为限。再分析不是实时预报。
5. **河网**：`data/raw/hydrorivers/HydroRIVERS_v10_as.*`、`data/raw/hydrobasins/hybas_as_lev12_v1c.*`、站点KMZ及 `src/vhs/graph.py`。实际DBF重新读出68条HYRIV_ID/NEXT_DOWN/LENGTH_KM，67条链内边与原始指针吻合；长度212.61 km，末reach40282031的NEXT_DOWN=DSK匹配reach40282189。HydroBASINS几何和站点原始身份未全面复核，文件名/本地存在不能替代官方下载认证。
6. **地形/宽度**：本地 `data/raw/dem/FABDEM_BYBLK_DSK.tif` 与 `data/raw/sword_v2`，衍生 `channel_slope_final.csv`、`channel_width_final.csv`、物理特征表。历史报告提供DEM覆盖和SWORD最近几何匹配；本轮对相关资产做哈希并读取代码/报告，没有重新生成坡度或宽度。现代地形/宽度用于历史时期是静态近似，不能认作1978–1983同步观测。
7. **另一个参考流量**：基础bundle的wg_dis来自本地WaterGAP `dis` NetCDF最近站点采样；面积比lag3参考来自上游Q与UP_AREA；两者均不同于MQ导入字段，也不同于E4线性水库输出。WaterGAP外部率定是否含目标站信息本轮未核实。

## 源码和冻结证据

- 日流量配置：{ev('configs/real_data.yaml','BYBLK-DSK')}
- 导入规则：{ev('scripts/prepare_timeseries.py','groupby')}
- MQ字段赋值：{ev('scripts/extract_multisite_runoff_2005.py','physical_reference_q_m3s')}
- E0目标映射：{ev('scripts/build_bd1m_model_dataset_audit.py','Q_target_dsk.*=')}
- E4/E5A冻结：{link('outputs/vhs_bd1m/experiments/e4b3_method_freeze.json')}；{link('outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json')}。
- 已审查D5四轮分支，特别保留M1/M2拒绝与M2C开发评价的限制，避免重复造轮子。

## 可复核清单

`data_audit/source_manifest.json`含{len(M)}个机器读取/索引资产的绝对路径、字节数、SHA-256；这不是声称逐篇人工精读{len(M)}文件。`data_audit/code_evidence.txt`保存相关源码/报告匹配行及行号；深读范围在各专题报告明确引用。`live_audit_facts.json`记录全量逐值检查、日期范围、NetCDF元数据、边和原始DBF核验。`historical_before.json`还覆盖全部本地raw/processed以及scripts/src/configs/tests/reports/outputs的2398文件。
可确认本地加工链一致；不能由哈希确认第三方科学真实性。更早未被当前脚本保留的插补/整编过程标记UNVERIFIED。
''')
write('provenance_audit',f'''来源真实性与 physical_reference_q 血缘审计

{intro}

## MQ的实际链路

`Q-新疆.xls` → `2005-支流/MQ-DSK-2005-SB`（B列、零基1） → `extract_multisite_runoff_2005.py`直接读取 → `physical_reference_q_m3s` → `multisite_discharge_2005.csv` → `prepare_multisite_gnn_bundle_2005.py`改名 → NPZ `x[..., physical_reference_q]` → `WindowDataset`输入、output_reference和physics_reference → 模型残差锚点/物理损失 → 与独立存放于y的DSK OQ评分。

BYBLK MQ是同sheet D列（零基3），OQ分别DSK C列、BYBLK E列；干流MQ为index11的B/C/D列，OQ为E/F/G列。干流首行表头并不明确MQ物理模型名称，不能借支流表头补造其生成机制。

证据：{ev('scripts/extract_multisite_runoff_2005.py','reference =')}; {ev('scripts/prepare_multisite_gnn_bundle_2005.py','physical_reference_q_m3s.*physical_reference_q')}; {ev('configs/multisite2005_snapshot_gnn.yaml','output_reference_feature')}; {ev('src/vhs/train.py','physics_mask =')}; {ev('src/vhs/data.py','output_reference = self.bundle.x')}。

本轮逐单元格核对工作簿→CSV，逐float32核对CSV→NPZ，均一致。但在工作簿值**之前**，没有发现可核查生成脚本、公式、输入清单、校准年份、站点标签使用记录或参数文件。最终生成链状态：**PROVENANCE_UNVERIFIED**。不能认定为独立物理模型，也不能反向断定确有目标标签泄漏。模型可能复制MQ中的目标信息是POTENTIAL_LEAKAGE。

历史D5已明确相同阻断：{link('outputs/diagnosis_2005_snapshot/stage_d5/d5b_mq_lineage/mq_2005_lineage_report_zh.md')}。本轮不重建MQ、不补造2011 MQ。

## obs_q与不同参考量的关系

- obs_q来自日工作簿或2005 OQ列，是监督/评分标签，同时在上游节点可作为合法输入。名称“obs”或OQ不证明它未经过供数者外部整编。
- `physical_reference_q`是2005 MQ列复制，两者不同列、不同数值并不意味着统计独立或无共同率定来源。
- `physics_area_scaled_q_lag3`由上游Q(t−3)×UP_AREA比率算得，仓库生成链可追；它不是MQ。{ev('scripts/prepare_virtual_station_bundle.py','physical_reference = routed')}
- `residual_reference_q`还可由lag3上游Q加本地降水产流代理构成，不能与68河段routing或MQ合并解释。见 `scripts/prepare_residual_gnn_bundle.py`。
- E4 R1的route_daily在本地有完整计算公式与初始状态规定，但tau通过DSK训练期Q校准，因此不是strict zero-shot参考；68个相同tau构成串联水库，0.7071228027 day是**单河段**tau，非整个212.61km的实测传播时长。其总一阶平均驻留尺度约48.08435 day，不可等同洪峰延迟。
- WaterGAP的wg_dis是另一个外部模型字段，其内部目标站率定独立性UNVERIFIED。

## 数据可信度分层及缺证请求

本地复制与数值一致性已核实：1978–1983两站日流量、2005 OQ/MQ导入、E0列映射、E4B0严格滞后特征、E5A17源文件哈希。
元数据/独立性未核实：日流量官方供数者、打印单位和日界；MQ原始模型/校准及目标信息；外部月序列单位/提供者/原始变量；WaterGAP目标站校准；现代几何与历史时期对应。
向原提供者索取：原始供数说明、站号/站址沿革、单位、日统计窗口、质控及插补记录；MQ公式/脚本/参数/输入与校准清单；月序列原始供数机构、变量和单位、与日序列的关系。获取前不得将任一未知填为PASS。

最严格来源门槛尚未满足；MQ与外部月序列不得进入独立验证或Protocol C主张。可用同源日Q做带警告的回顾性开发，但本阶段并未获准执行。
''')
write('leakage_audit',f'''目标站信息泄漏与协议分类

{intro}

## 协议定义

**A Historical reconstruction**：目标站训练期Q可用于监督/校准；预测构造不能读取测试期目标标签，包括测试期更早日期的实测Q回填。
**B Temporally held-out reconstruction**：A的时间严格化；训练、开发验证、最终测试按时序，所有选择先于最终测试。历史已揭示测试不能再作为新方法盲测。
**C Strict ungauged / zero-shot**：该目标站任何时期Q都不能进入监督、校准、目标专用参数、选模或预测回填。只屏蔽x中的obs_q不足以证明C。
若研究明确允许上一日目标观测，那是观测辅助的一步预测，必须另立协议，不能混进A/B/C的缺测重建比较。

## 逐实验族判定

1. **E1 Model-0 Persistence**：{ev('scripts/run_bd1m_baselines.py','persistence_prediction.*shift')}
   **CONFIRMED_LEAKAGE（相对本轮A/B/C重建边界）**：全序列shift后按split评分，1983-01-02起使用1983测试期DSK Q(t−1)。这是已明示的持久性诊断，不是发现隐瞒；没有未来t+1泄漏，但不能作为无目标观测预测。首个测试日可以使用测试前历史值，不改变其后364日的结论。
2. **E2 DSK_history**：{ev('scripts/run_bd1m_e2_temporal_memory.py','dsk_features =')}; {ev('scripts/run_bd1m_e2_temporal_memory.py',r'data\[name\].*shift')}
   **CONFIRMED_LEAKAGE（同一重建边界）**：测试窗口包含测试期内t−1..t−30目标观测；仅适用于有观测的记忆诊断，不能称C或无标签A/B。
3. **E1 upstream transfer、LR/RF；E2 BYBLK_history；E3 MLP/GRU/TCN**：A、按源码固定时间切分的B式历史开发。LR/RF/神经模型使用DSK训练Q，不能C。E1训练中位数填特征；E3 scaler仅train。**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**：未发现测试目标作为这些模型输入或标准化来源。历史测试已多次揭示，不能保证后续人工决策从未使用测试；整体独立性UNVERIFIED。same-day上游Q是日末历史重建可用信息，不是日初预报信息。
4. **E1.5滞后扫描与E2分区相关**：0..30天仅为诊断；各split都报告不能用于选择新方法lag。统计相关及最大NSE不是实测传播时间。把1983最优lag拿来选模将构成泄漏，当前未找到已经这样选择的直接证据，记**POTENTIAL_LEAKAGE**。两个滞后诊断脚本都输出同名结果，不能由文件名证明唯一生成命令；源码全序列shift允许合法跨split历史，而旧某报告“不同split不借用”文字过强，应在新记录中澄清，不修改历史。
5. **E4A2 R1/R2**：A、B的训练校准步骤；{ev('scripts/bd1m_e4a2_optimizer.py','TRAIN_OBJECTIVE =')}。训练DSK进入RMSE目标，不能C。检查train-only输入映射1461日、无1982/1983参与fit；**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**，限可见源码/注册文件。
6. **E4B1/B2A/B2B/B2C、Fourier6**：A及B式开发，目标是train的DSK减routing残差，1982用于开发选模，LOYO在开发范围内。{ev('scripts/run_bd1m_e4b1_incremental_residual.py','model.fit')}; `e4b3_method_freeze.json`。不能C。t−1增量气象5字段已独立重算；未见测试标签进入这些特征。不能把修正项解释为观测证实的侧向流量。
7. **E4C**：冻结方法下B式固定1983评价。读取冻结tau及Fourier系数，1978一次初始化、连续推进，不使用DSK测试流量重置。{ev('scripts/run_bd1m_e4c_fixed_1983_holdout.py',r'initialize_steady_state\(')}; {link('outputs/vhs_bd1m/experiments/e4c_1983_holdout_report.md')}。**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**；没有重算此实验。本轮不能证明历史执行文件与当前源码逐字相同；E5A登记结果源17/17哈希匹配。E1–E3已报告1983，因此E4的“固定方法”身份应与全球从未查看过的盲测严格区分。
8. **E4D**：冻结预测的外部月一致性评分，承接A/B训练的模型；未知单位及来源，独立性**UNVERIFIED / POTENTIAL_LEAKAGE**，不属于C或官方独立验证。
9. **2005五站snapshot GNN/no-graph**：设计为整站留出，DSK OQ从训练标签及全窗口x排除，早停evaluate(target_only=False)只用非目标站；scaler只用训练前缀。{ev('src/vhs/train.py','target_only=False')}; {ev('src/vhs/data.py',r'train_x\[:, target_mask, flow_idx\] = np.nan')}; {ev('src/vhs/data.py',r'availability\[:, self.target_node_mask, self.flow_idx\] = 0')}
   当前源码直接标签路径为**NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE**；合成扰动验证global/station_reference两模式目标obs及非训练数据改变不影响scaler，目标obs/availability确实遮蔽。但是目标MQ保持为输入、归一化参考、残差锚点和训练physics loss，MQ生成链未知，故**POTENTIAL_LEAKAGE**，不能认证C。历史checkpoint是否正由当前代码构造**UNVERIFIED**；未训练或载入checkpoint推理。
10. **早期1978–1983 holdout_dsk/mainline STGNN**：与五站2005不是同一图。基础NPZ含{len(F['base_bundle']['stations'])}站，许多站无Q；遮蔽机制见当前data.py，wg_dis外部校准独立性未知。属于C设计意图但严格C**UNVERIFIED**，不凭配置命名批准。
11. **calibrated_residual、Stage C P1**：使用DSK训练期Q拟合线性/残差校正，A，不能C；2005既有test被标作legacy diagnostic而非盲测。Stage C的P2分支即使不监督目标也仍受MQ来源限制；见 `scripts/run_stage_c_boundary_lag_residual.py` 与 `evaluate_calibrated_residual.py`。
12. **D5 round2 M1/M2与round4 M2R/M2C**：A的回顾性嵌套LOYO，不是B，因为留出较早年份时会训练于其后的年份；同一DSK其他年份Q参与拟合，不能C。未见目标Q作预测时状态重置；状态用上游Q预热。round3用全部六年残差筛选weather，包含各外层测试年DSK信息，round4继承此选择。**CONFIRMED_LEAKAGE（特征选择对外层独立评估的污染）**，历史报告已明确承认，故其开发性结果本身可保留；禁止包装成完全独立nested test。{ev('outputs/diagnosis_2005_snapshot/stage_d5_round4/candidate_selection_report_zh.md','同一批')}

## 检查项总答

- 原始Q本地加工无插补；供数前处理UNVERIFIED。模型缺特征用train中位数或NaN+availability，不等于目标Q未来插补。
- 已查train/global/station_reference、E3 scaler、D5 weather fold scaler，未见全时期目标scaler；全部历史脚本所有路径未穷举，不能宣布全项目零泄漏。
- 未查到E4测试目标状态重置；上游实测日平均输入可合法用于日末重建，跨split合法历史不是目标标签泄漏。
- 图消息输入目标obs被当前代码屏蔽；隐藏共享MQ来源及WaterGAP率定不能由屏蔽证明无泄漏。
- 历史“future_information_leakage=False”在E0生成器为常量赋值，旧单测只断言此标志，证据不足。本轮增加真实赋值链核查与合成扰动，仍保持范围限定。

完整分类机读版见 `evaluation/protocol_classification.json`。确认事项均注明违规所相对的协议，不把允许的训练监督误称泄漏，不把未知来源断言为已确认泄漏。
''')
write('topology_audit',f'''拓扑、传播与不可比设置

{intro}

## 设置1：2005五站有向图

- 5个站点节点：BYBLK/00705600、DSK/00705700、ALAR/TARIM_ALAR、XQM/TARIM_XQM、AQK/TARIM_AQK；3条有向边，2个弱连通分量（2站开都河、3站塔里木）。实际NPZ边0→1、2→3、3→4，无环；不是跨流域连边。
- BYBLK→DSK 212.61 km；另外两条塌缩边的距离缺证。`prepare_multisite_gnn_bundle_2005.py`主动丢弃距离，实际edge_attr全部1，仅拓扑；不能当作米或公里。
- BYBLK/DSK为2005-05-01至10-31各184日；其他三站01-02至10-28各300日；合并303日，不同站有缺窗。
- snapshot history1用当日非目标站OQ与所有节点MQ，history current_snapshot=True；2005-06-30 train截止、08-31 validation截止，之后test。损失用非目标站，MQ在目标仍保留。没有显式物理库容递推或测定时滞；C设计未经MQ血缘认证。
- 方向来自项目边及文献顺序声明；本轮复核本地边/张量一致，未重新进行塔里木野外站址或文献验证，collapsed边并非三个连续实体河段。

证据：{link('data/processed/virtual_station_multisite/multisite_edges_2005.csv')}；{ev('scripts/prepare_multisite_gnn_bundle_2005.py','topology_edges =')}; {link('configs/multisite2005_snapshot_gnn.yaml')}。

## 设置2：BYBLK→DSK 68河段

- 两个有观测Q的站点，68个HydroRIVERS河段空间单元，67条链内边，1个弱连通分量；顺序1..68全部对应上游→下游。
- 本轮直接重读原始DBF：匹配68/68，链内67条NEXT_DOWN无矛盾；总LENGTH_KM=212.61。最后包含河段40282031→DSK匹配河段40282189；后者是终点边界，不是第69个被路由库容。没有靠历史PASS标志代替核查。
- 日Q 1978–1983；首端当日Q作为边界，终端DSK作train校准/评价。68河段无逐河段Q标签；气象仅流域或增量流域，不是68份独立观测。
- R1为68个相同tau串联，R2为68个由L/S/W共享四参数生成的tau。初始S_i=tau_i×首日上游Q；日内Euler，原生接口外步固定1day；无侧向、取水、显式闸门或回水方程。
- 1978–1981 train、1982开发、1983原冻结方法评价；R1/R2使用DSK训练期标签，A/B而非C。

## 另一套早期图

`real_bundle.npz`实际含{len(F['base_bundle']['stations'])}个站节点，动态wg_dis/obs_q，仅BYBLK/DSK有1978–1983观测，许多其他节点只有外部模型流量。`holdout_dsk_graph1`/`mainline_formal_graph`不能自动归入2005五站设置，更不能等同68河段库容图。实际station_ids/edge_index见live_audit_facts.json。

## 不能直接比较的结果

2005 snapshot GNN vs 1978–1983 R1/R2：年份、站点/空间单元、输入MQ、标签监督与容量均不同。五站图局部性能降低不能证明68河段图负迁移，更不能证明GNN普遍失败。
R2约0.047227%改善是训练目标在该参数化的微小差异，不是独立测试图贡献，也不证明河道异质性没有物理作用。
D5 M1/M2为单路径统计传递与宏平均嵌套LOYO；E4为固定时序与68库容；参数、预热、有效日和监督范围不同，不能直接比较NSE认定某结构优越。
E1 persistence/E2目标历史窗使用额外目标观测，不能与无目标Q模型作同信息比较。外部月结果也不能与逐日结果直接排序。
''')
write('physics_baseline_inventory',f'''已有物理基线与复用边界

{intro}

1. **same-day transfer：已实现并有历史输出**。`run_bd1m_baselines.py` Model1和E4 R0；直接Q_BYBLK(t)，不重复运行。
2. **fixed lag：已实现并做0..30日历史诊断**。两个lag脚本共享结果文件；`prepare_virtual_station_bundle.py`还生成lag3面积比参考。固定lag存在不意味着统计最优lag是真实传播时长。
3. **分布式非负归一化响应核：已实现**。D5 round2的kernel_weights与M1 family支持Gaussian/Gamma-Nash，归一化核外另拟合增益a与截距b；Stage C还含自由分布式和低维核。不能把这些既有模型伪装成本轮新方法。{ev('scripts/run_stage_d5_round2_nested_loyo.py','def kernel_weights')}
4. **线性水库：已实现并验证**。E4 route_daily的68串联R1及纯Python测试；另有D5 `s=rho*s+Q_up` 单记忆状态M2、归一化M2R。D5统计状态加gain/direct/intercept并不自动具有物理m³库容或严格质量闭合。
5. **异质串联水库R2：已实现并完成train多起点**。tau0,a,b,c经L/S/W生成，训练RMSE R1=118.905450，R2=118.849295，改善0.047227%，这是E5A登记数值。参数不可辨识与触边仅限该数据/参数化。原结果、参数和方法冻结，禁止本轮重拟合。
6. **Muskingum：当前scripts/src/tests未发现可调用实现或其单测**。文献矩阵出现术语不算实现。本轮只给规范与测试计划，不临时实现。
7. **残差修正：已存在**。E4B OLS气象修正、月气候态、Fourier6及温度/季节对照；Stage C线性与非线性残差；D5 M2C区间融雪扩展。Fourier6为冻结最终方法；D5 M2C保持reject_M2C_interval_snowmelt，不能为了新阶段重新开放其余候选。

## 可复用与无需重复

直接复用算法：纯Python route_daily（适配器提取原函数AST，方程未重写）；流量原始导入、t−1特征定义、静态L/S/W来源规则、现有评价指标实现可作审阅参考。
直接复用冻结参考：R1 tau=0.7071228027343739 day/河段、substeps3、初始化和已保存预测；Fourier6原系数和1983结果只作已完成历史证据。**不重新计算真实数据预测**。
无需重复：E4 R1/R2拟合、E1滞后扫描、Fourier/温度季节区分、E4B稳定性、1983固定方法评价、外部月一致性、D5 M1/M2嵌套LOYO、M2C单融雪变量搜索。
后续若采用历史R1作跨年外层折基线，必须标出其已经见过1978–1981 DSK标签；它在那些年份不能称outer-fold独立训练。不得偷偷为每个折重拟合历史R1以“解决”此问题。

## 实现限制与缺资料

- 参数tau是等效响应参数，非独立实测传播速度；宽度/坡度不提供完整断面、水深、糙率、闸控、侧向径流与取水。
- R2负坡度取abs并设0.01m/km下限，数学合法不保证水力方向或回水过程得到物理解读。
- 原route_daily输出日平均Q，内部S为Q·day；docstring“discharge per day”应按原方程理解为Q，不是m³/s/day。以Q=m³/s时物理库容V=86400S m³；本轮仅在新规范澄清。
- 公共router会校验非负有限Q、正tau、68节点、非负状态和dt/tau≤0.5。initialize_steady_state独立调用未完整验证tau，substeps整数类型未显式检查；后续新接口需统一契约。本轮测试通过不表示所有辅助函数非法输入均已穷举。
- 本轮只测纯Python route_daily，没有启动Numba编译/复测JIT性能，也没有验证真实水文机理有效性。

详细数学规范见 {link('research_next/vhs_transfer/physics/physics_baseline_specification.md')}。
''')
physics='''# VHS-NEXT-S0 物理基线技术规范

状态：SPECIFICATION_ONLY；现有router的单元核验另记SYNTHETIC_UNIT_TEST_ONLY。任何新参数拟合均须下一阶段授权。本规范时间t以day表示，Q以项目约定m³/s表示（原始打印单位仍待核实），物理V为m³，内部S为(m³/s)·day，V=86400S。

## 1. 水量守恒

dV/dt_seconds = Q_in + Q_lateral − Q_out − Q_withdrawal。
若以day和S写：dS/dt_day = Q_in + Q_lateral − Q_out − Q_withdrawal。
所有流量及物理V非负，取水不得使储量负值；空间单元所有流入流出要用同一日界。初始V≥0由目标测试前上游forcing和预先规定状态给出，不得用测试目标反求。累计体积闭合为V_end−V_start=86400Σ(Q_in+Q_lat−Q_out−Q_withdraw)Δt_day，有限窗必须包含末端残余储量。
现有E4只有边界输入和终端输出，默认Q_lat=Q_withdraw=0；闭合只验证该简化系统的数值守恒，不证明真实河道没有其他水量项。仅首末Q不能独立识别侧向流入、取水及蓄水变化。

## 2. 固定时滞与仿射转移

Q_down(t)=a Q_up(t−tau)+b，tau≥0 day、a≥0无量纲、b为m³/s。整数日lag仅用当前/过去可用上游Q；分数时滞需预注册只使用已知样本的插值，禁止跨越预测起点读取未来Q。same-day tau=0用于日末历史重建；若日初预报则不能使用当日完整平均Q。
初期缺窗用合法上游warm-up或保留缺失，禁止目标Q填补。纯无源延迟要求a=1,b=0；a≠1或b≠0是经验水量增益/损失，不是已观测侧向补给。统计滞后受共同季节性、日界和库容影响，不独立识别波速。已有E1.5和Stage C，不重跑。

## 3. 分布式响应核

Q_route(t)=Σ_{k=0..K} alpha_k Q_up(t−k)，alpha_k≥0、Σalpha=1，权重无量纲、lag单位day。仅固定非负索引；若预测信息截至t−1则alpha_0禁用。固定核对完整时间积分守恒；有限窗的未释放尾部和初始历史贡献需计入，不能丢掉尾巴宣称缺水。
归一化核只能重新分配输入时间，不能创造未知侧向流量、取水或固定增益。若再乘g或加b，必须另列经验修正项与水量预算。已有D5 M1 normalized核外另有a,b；平滑核可防任意尖峰但不能独自解决信息不足。核宽度、形状和增益可能高度共线，必须用开发折、参数稳定性和物理资料评估，禁止按测试选择。

## 4. 线性水库与68河段串联

Q_out_i=S_i/tau_i，dS_i/dt_day=Q_in_i−Q_out_i；tau_i>0 day，Q_in_{i+1}=Q_out_i。
原Euler更新：先算旧S对应outflow，再 S_i←S_i+(Q_in_i−Q_out_i)dt；下游用该substep上游旧状态outflow。不能把最后河段刚更新后的S/tau误当同substep排出量。
public route_daily固定Δt_outer=1day，m个substeps，dt=1/m day；原规则dt/tau_i≤0.5，m=max(1,ceil(1/(0.5min tau)))。这是保守非负/稳定规则：标量Euler衰减稳定需dt/tau≤2，非负单调需≤1，本项目采用更严格0.5；通过稳定不等于步长误差足够小，需要收敛对照。
初始S_i=tau_i Q_BYBLK(first_train_day)，仅一次；train/validation/test连续传状态，禁用DSK状态重置。输出为一天积分的终端排出量除以1day，数值与Q·day在固定一天步长下相同；更改外步必须显式除Δt。
R1：68个tau均0.7071228027343739day，m=3；全链一阶平均时间尺度Σtau约48.08435day，不是观测传播时滞。
R2：tau_i=tau0(L_i/median L)^a(Slope_i/median Slope)^b(W_i/median W)^c。
L为km、W为m，Slope=max(abs(median_slope_m_per_m)×1000,0.01)m/km；比值无量纲。tau0>0，原优化上界30day；a∈[0,2]、b,c∈[−2,2]，原数值门槛substeps≤576。指数仅拟合参数，不是真实水力指数。截断/abs坡度不能证明正确回水机制。单上下游Q不能唯一识别68状态或四指数；保留现有不可辨识证据。
对应：scripts/bd1m_physics_routing_model.py、bd1m_e4a2_optimizer.py、E4A协议。S0适配器执行精确原函数AST，避免导入Numba写旧cache；未修改历史源码。

## 5. Muskingum（仅规范，无实现）

S=K[X I+(1−X)O]，K>0 day，0≤X≤0.5；S为Q·day，I/O为m³/s。连续守恒dS/dt=I−O。
梯形积分：O_{n+1}=C0 I_{n+1}+C1 I_n+C2 O_n；
D=2K(1−X)+dt，C0=(dt−2KX)/D，C1=(dt+2KX)/D，C2=(2K(1−X)−dt)/D，ΣC=1。
所有系数非负的充分范围为2KX≤dt≤2K(1−X)。这比仅检查有限输出更明确；不满足时拒绝/按预注册规则改离散或子河段，不能裁剪负流量来掩盖问题。减小dt不一定更好（X>0时也有下限），K/X/分段方案需一起检查。
初值O0≥0、S0=K[X I0+(1−X)O0]，不得用未来目标校准；稳态O0=I0可由合法上游指定。I_{n+1}在后验区间末重建中可已知，但在区间起点预报中未知，必须明确时间语义。原式以时点流量及梯形积分定义；不能无说明直接把日均Q当瞬时端点。侧向/取水若存在要扩展守恒方程。
K/X从可审查河道/波速先验或训练站校准获得；若目标站专属Q校准则不能C。仅L/S/W不够保证Muskingum或Muskingum-Cunge水力参数可识别；两者不能混称。本轮未实现、不生成真数据拟合。
后续测试计划：恒流稳态；脉冲非负及响应；梯形守恒+初末S；系数和1；合法/不合法dt与边界X；分段时间收敛；连续初值；目标未来扰动不改前缀。先明确日均/端点约定再写代码。

## 6. 路由+预测残差

Q_pred(t)=Q_route(t)+DeltaQ_model(t)，修正项单位m³/s，可正可负；最终若clip到0，必须独立记录裁剪引入的体积变化。修正的fit用训练残差Q_obs−Q_route；正负号不得与D5使用prediction−observation的诊断残差混用。
模型输入只能使用协议规定的上游Q、静态资料、合法过去气象/日历，不得用目标测试Q或带未知目标来源的参考量。模型初态仅训练/上游预热。残差可能包含侧向来水、取水、库容模型错误、观测误差和日界差异，不能直接解释为真实观测侧向流量。
DeltaQ使总输出不再自动满足route-only闭合；必须同时报告route数值质量误差与最终预测对观测的体积偏差，并承认未观测侧向项的不可识别性。已有Fourier6、月残差、气象OLS、Stage C/D5修正；全部冻结不重拟合。

## 一手技术来源（2026-10-11在线核对）

- [USACE HEC Muskingum routing](https://www.hec.usace.army.mil/confluence/cwmsdocs/rsum/muskingum-routing-58631546.html)：K、X及分段含义；本规范系数与非负区间由守恒/梯形代数展开给出。
- [ECMWF ERA5-Land data documentation](https://confluence.ecmwf.int/pages/viewpage.action?pageId=501029136)：00UTC累计对应前一天，支持本地日处理时间约定；不证明本项目流量水文日界。
原始文件与代码哈希见data_audit/source_manifest.json与historical_before.json。
'''
(BASE/'physics/physics_baseline_specification.md').write_text(physics,encoding='utf-8')
write('research_protocol',f'''下一轮实验协议（设计，不执行）

{intro}

## 核心研究问题和可证伪范围

Q1上游可解释多少下游变化，应测量相对于训练季节气候态的增量样本外贡献，不能只报告同季节相关。Q2方向/时滞/蓄水贡献要用同输入的成对消融。Q3–Q4的图负迁移是待检验现象，拓扑错误、时滞缺失、容量/监督来源、泄漏和物理缺项均是竞争假设。Q5比较独立定义的路由与预测修正，Q6仅在真实站/年/流域资料足够时谈迁移；没有观测的中间河段不被创造为监督站。

## 数据与测试身份门槛

原E4 train1978–1981/开发1982/固定方法1983身份保留，禁止重新调整R1/R2/Fourier6或按1983选方法。**对新方法：1978–1983、2005以及历史已揭示的2000/2001/2011不自动成为新盲测**。D5四轮已对六年残差/候选开展开发，nested LOYO必须称retrospective/development。新B最终测试需要另一个未揭示、元数据完整的时间区间，选择/超参/代码/哈希先冻结，封存标签，独立一次评分；本轮不下载、不检查新标签数值。
当只用现有六年做探索时，报告“历史开发比较”，不得声称最终独立泛化。跨年滚动开发只能把过去用于未来，全部标准化与候选筛选在各训练折内；已受全时期探索影响的候选不能通过再套一个LOYO恢复盲测身份。
C分支要求目标站所有年份标签隔离；R1历史tau在DSK训练Q上拟合，因此不能作为DSK的C模型。可保留为标注A的参考栏，不能并入C排名。真正C需独立源站参数/外部合法先验且MQ/WaterGAP率定独立性可证明。跨站/流域存在性与真实连通方向要先认证；独立Caravan/CAMELS流域不能拼成真实河网。

## 公平对照N0–N8

- **N0季节气候态**：训练期月/DOY均值，闰日规则提前冻结；A/B可用目标train Q，C只能用source站迁移的合法气候态或外部先验，并单独标识。E4月残差气候态是route+residual，不等于纯Q气候态。
- **N1上游Q及合法lag**：复用已有转移/lag定义；只在开发期选择，含k0与仅t−1的可用信息分层，不能让一个模型拥有当日Q另一个只有过去。
- **N2原冻结R1**：复用参数、state规则及已保存参考预测，禁止重拟合；新日期若未来获准只可用合法上游暖启动/连续状态并先冻结规则。新跨年折中凡tau已见过目标年份标签必须标“历史已校准参考”，不能算该折无偏test。
- **N3 Muskingum**：仅在日界、K/X来源与稳定条件满足后加入；先完成独立单测，再谈实验，资料不足则NA。
- **N4 MLP/TCN非图**：以相同的全部合法上游输入向量和时间窗输入，容量匹配N5/N6；不复用E3结果当新公平比较。
- **N5 Directed GNN**：相同信息、相同target mask，实边/空边/反向/打乱边成对对照。若只有一个上下游对，只能回答该对局部传播结构的贡献，不能声称多站河网普遍规律。
- **N6 Lag-aware GNN**：每边lag先验或开发选定；与N4同一lag信息及参数预算，防止多了信息却归因于图。没有边距离/时滞证据不虚构。
- **N7 Physics Routing+Residual**：固定N2加低容量修正，与纯N0/N1/N4比较。只用训练残差fit，不许回调原tau。原Fourier6只作冻结参照；新修正须在独立数据或明示开发评价下进行，不重试被拒绝M2C及其余7候选。
- **N8 transfer**：cross-year时序外推、cross-station整站留出、cross-basin整流域留出分别报告。目标站/流域全标签封存；来源站特征/预训练、归一化也不得跨界。只有足够真实观测和元数据时执行，否则记录NOT_DATA_SUPPORTED。

## 信息、容量和搜索预算

主比较MQ-free；wg_dis如无法证明校准独立性也从C主比较排除。各比较组共享同一信息可用时刻、forcing、训练期、共同有效日期、warm-up、损失和非负输出规则。额外气象分为独立matched-information层，不能将信息差解释为结构差。
预注册学习模型每族最多12组超参、每组3个开发种子（7/42/123）、相同最多100epoch与patience15及同一优化/早停指标；最终冻结后5种子（7/42/123/2026/31415），逐种子报告，不挑最好test种子。每组相同数据样本数与训练迭代上限，并记录CPU/GPU资源实际预算；不是保证相同运行时间。S0不执行这些预算。
N4/N5/N6各用约1k/5k/20k三档参数容量，主要对照参数数差≤10%；做不到则完整报告容量曲线和计算量，不能用单一不匹配模型归因。三档容量计入12组预算，不额外追加。规则化/物理约束用同等开发机会；N0/N1/N2冻结无搜索，Muskingum若允许新校准也须计入12组，绝不修改原N2。
开发先冻结超参搜索空间、特征列表、评价support及停止规则；最终数据只允许一次评分。若原模型无目标输入却不能适应则报告失败，不事后补入目标观测。

## 统一评价

NSE=1−Σ(pred−obs)²/Σ(obs−mean(obs))²；KGE使用2009定义1−sqrt((r−1)²+(stdpred/stdobs−1)²+(meanpred/meanobs−1)²)，冻结样本方差约定，常量/零均值返回NA并说明。
RMSE、MAE、Bias=mean(pred−obs)单位m³/s；PBIAS=100Σ(pred−obs)/Σobs；物理volume bias=86400Σ(pred−obs)Δt，区分带符号Bias和绝对误差。
Peak timing：事件匹配阈值与时间容差在train/开发预注册，报告有符号/绝对日误差及未匹配事件，不能只挑最大峰。Low-flow用train的20%分位阈值固定评估，阈值外推时不按test重定；跨站转移需源站合法尺度。分区样本不足则NA。
Water balance分两栏：模型内部ΔS+O−I−L+W的数值闭合与最终pred-vs-obs体积偏差。未观测L/W不能由闭合推出真质量守恒。
Cross-year：逐年、宏平均/中位/最差年及pooled分开；多种子与时间自相关不被当作独立日样本。配对block bootstrap或按年汇总CI，block长度仅开发选择；多方法主要比较提前限定，避免多重选择。
训练性能、开发验证性能、最终留出性能独立列示；相同有效日交集作主比较，另报全可用support、缺测、warm-up与有效n，不能用不同n提高指标。

## 最推荐的三个实验（均未执行）

1. **季节条件化后的上游增量信息**：在新合法时序测试下对比纯季节气候态、相同日历+合法上游窗、冻结R1参考；报告去季节残差的样本外增益与volume/peak/low-flow误差。价值是区分共同季节性与可迁移上游信息，区别于已完成原始lag扫描及Fourier6拟合。若无未揭示测试，只允许明确标注探索性，不再重复历史训练。
2. **同信息同容量的方向×时滞消融**：N4/N5/N6成对，无图/实方向/反向、统一lag；与真数据同一输入边界。先决条件是拓扑和足够多的实观测站支持（目前五站仅两个分量），MQ来源解决或从所有模型同时删除。不开展10–30节点合成网络或GNN训练于S0。
3. **冻结路由与小残差的外推失效检验**：N2/N7固定原路由，先预注册哪些失效（年水量偏差、极端/低流）是上游信息不足；在新未揭示年份一次评价，不微调tau。跨站/跨流域只在数据足够时作为后续N8；不重开M2C搜索，不把残差当实测侧向流量。

## P0 / P1 / P2

**P0（按分支阻断）**：MQ生成/校准血缘未知，阻断MQ相关独立验证/C；日Q供数者、明确单位/日界和站点对应需补证，阻断强物理/官方观测真实性声明；外部月原始来源/单位未知，阻断其独立验证；所有旧年已揭示，缺新的封存test，阻断新方法最终独立性能结论；D5全六年特征筛选污染外层独立身份，禁止复用为盲测；明确C参数来源，不可用已DSK校准R1冒充C。
**P1（可做受限开发但须披露）**：侧向/取水/库容/闸控资料缺失、无reach-level Q；日平均不能辨亚日时滞；SWORD/FABDEM历史代表性与几何匹配不确定；R2弱可识别/坡度abs；两站/五站容量受限与参数预算；初态warm-up和共同support；原router辅助函数参数契约/JIT未本轮复测；Git原未提交状态无法判断。
**P2（延期）**：10–30节点合成稀疏状态重建、真实多站ST-GNN、Caravan/CAMELS跨流域、卫星融合、神经算子、扩散反演。现代SWOT不得作为1978–1983历史动态输入，独立流域不得虚构连通图。全部另行授权、数据和协议门槛。

当前READY_FOR_VHS_NEXT_S1=false，含义为尚不满足完整真实科研实验准入；S0审计完成并不等于数据门槛解决。下一步应先解决P0并提交具体S1数据/测试封存方案，或由用户明确批准限于既有数据的探索性分支。停止等待批准。
''')
classification=[
 {'experiment':'E1 Persistence / E2 DSK_history','protocol':'observed-target diagnostic; not reconstruction A/B/C','status':'CONFIRMED_LEAKAGE','scope':'test-period past target Q used at prediction time under missing-target reconstruction boundary'},
 {'experiment':'E1 upstream LR/RF; E2 BYBLK_history; E3','protocol':'A / historical chronological B-style development; not C','status':'NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE','scope':'current visible fit/scaler/features; global historical model-selection independence unverified'},
 {'experiment':'E4 R1/R2/residual/Fourier6','protocol':'A / chronological development and frozen B-style E4C; not C','status':'NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE','scope':'visible training/calibration/features/state; no real experiment rerun'},
 {'experiment':'E4D external monthly','protocol':'external monthly-series consistency only','status':'UNVERIFIED','scope':'source/units and shared target provenance; potential leakage unresolved'},
 {'experiment':'2005 five-node GNN','protocol':'station-holdout C intent; not C-certified','status':'POTENTIAL_LEAKAGE','scope':'retained target MQ generation/calibration unknown; current direct obs mask checked'},
 {'experiment':'early base-bundle STGNN / WaterGAP','protocol':'target-holdout intent; not C-certified','status':'UNVERIFIED','scope':'external model target calibration and historic runtime provenance'},
 {'experiment':'Stage C P1 / calibrated_residual','protocol':'A, supervised target calibration; legacy diagnostic','status':'NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE','scope':'target training supervision is permitted A; MQ independent lineage still potential leakage'},
 {'experiment':'D5 round2 M1/M2','protocol':'A retrospective nested LOYO; not chronological B or C','status':'NO_LEAKAGE_FOUND_WITHIN_CHECKED_SCOPE','scope':'outer-label fit exclusion in current code; source metadata warned'},
 {'experiment':'D5 round4 M2R/M2C feature-selection identity','protocol':'A development LOYO; not independent feature-selection test','status':'CONFIRMED_LEAKAGE','scope':'all-six-year residuals selected candidate before outer evaluation; expressly acknowledged historically'}]
(BASE/'evaluation').mkdir(exist_ok=True)
(BASE/'experiments').mkdir(exist_ok=True)
(BASE/'evaluation/protocol_classification.json').write_text(json.dumps(classification,ensure_ascii=False,indent=2),encoding='utf-8')
(BASE/'experiments/s1_design_gate.json').write_text(json.dumps({'phase':'DESIGN_ONLY','real_models_trained':False,'ready':False,'new_final_holdout_required':True,'historical_R1_refit_allowed':False,'MQ_C_gate':'PROVENANCE_UNVERIFIED','cross_station_basin':'NOT_DATA_SUPPORTED_UNTIL_VERIFIED','seeds_development':[7,42,123],'seeds_final':[7,42,123,2026,31415],'search_candidates_per_trainable_family':12,'max_epochs':100,'patience':15,'stop_after_S0':True},indent=2),encoding='utf-8')
Ipath=BASE/'data_audit/integrity_result.json'
if not Ipath.exists():raise RuntimeError('Run integrity.py after before finalizing reports')
I=json.loads(Ipath.read_text(encoding='utf-8'))
assert I['unchanged'] and T['failed']==0
write('validation_report',f'''中文最终验证报告

{intro}

## 1. 审计文件及证据

机器读取/索引{len(M)}项资产，重点深读三个runoff工作簿与导入/张量化代码、E0数据集、五站图和68河段图、E4A–E4D协议与脚本、E5A登记、E5I0状态、D5 round2/3/4代码及来源/选模审计。机器清单不等同全部逐篇精读。
`data_audit/source_manifest.json`记录绝对路径/哈希/大小，`code_evidence.txt`记录路径和行号，`live_audit_facts.json`包含原始值到衍生字段的实际检查。专题报告保存可点击核心代码证据。没有仅凭旧PASS或脚本名宣布通过。

## 2. 数据来源风险

日流量4382站日加工一致，无项目层目标插补/平滑；供数者、打印单位、日界仍需补证。MQ原工作簿→CSV→tensor链已确认，生成链**PROVENANCE_UNVERIFIED**。外部月序列与日序列独立性/单位/官方来源未知。WaterGAP目标校准独立性未知；ERA5-Land本地时间和单位链可检查，未重跑大规模原始网格流程。

## 3. 已确认及潜在泄漏

已确认：E1 persistence/E2 DSK_history在无目标测试Q的重建边界下读取过去测试目标；D5 M2C的候选天气特征在全六年目标残差上筛选，外层不是独立特征选择评估。这些历史记录已注明诊断/开发身份，不被本轮改写。
未确认但潜在：目标MQ可能来自目标监督校准；外部参考可能共享未知目标来源。当前GNN源码对目标obs/availability/scaler直接路径的遮蔽通过合成扰动，但保留MQ，不能认证C。
R1/R2/Fourier6、目标监督基线、Stage C P1和D5同站跨年拟合均不能叫strict zero-shot。E4C冻结预测未见测试目标回填/状态重置；结论只限已检查源码/注册文件。

## 4. 可复用基线

same-day、lag、归一化核、单储量、68串联R1/R2和残差修正均已有。直接复用冻结方法与参考，禁止重复拟合R1/R2/Fourier6以及D5已拒绝模型搜索。Muskingum没有找到现成本地实现，已交付规范和后续测试计划，本轮未实现。

## 5. CPU合成测试结果

标签：**SYNTHETIC_UNIT_TEST_ONLY**。7/7物理测试通过，0失败；另global/station_reference两种输入边界扰动检查通过。没有真实流量模型训练或真实预测重跑；CPU PyTorch版本为2.14.0+cpu，未启动GPU任务。
- 恒定入流：稳态输出最大差0，空初态长期收敛差0。
- 单脉冲：t=4入流，终端峰在t=11；累计输入10 Q·day、输出10、尾部残余0；这只是人为tau条件，不是真实传播时间。
- 守恒：最大单日闭合误差{T['tests'][2]['max_daily_closure_q_day']:.6g} Q·day，累计{T['tests'][2]['cumulative_closure_q_day']:.6g} Q·day；若Q=m³/s，累计约6.14e−10m³。
- 已知延迟3day：终端峰精确后移3day；改变未来forcing不改变预测前缀。
- 日内dt=0.05/0.025/0.0125/0.00625day均稳定、非负、守恒，相邻分辨率L1差1.306263→0.528118→0.247337。公共外步仍1day，不声称已测试可变日步接口。
- 10种非法Q/tau/shape/state/substep/参数情形全部清晰ValueError拒绝。
- 分段状态连续传递与整段输出/末态逐值一致。
这些测试仅验证当前纯Python代码的所测性质；不验证现实侧向过程、参数物理真实性、真实预测能力或历史JIT产物。
代码/日志：`tests/run_synthetic_tests.py`、`synthetic_results.json/.log`、`check_synthetic_input_boundary.py`、`synthetic_input_boundary.json`。适配器按原文件AST精确加载，避免Numba在历史目录写cache。

## 6. 不可直接比较

2005五节点snapshot图、早期{len(F['base_bundle']['stations'])}节点STGNN和1978–1983的68河段物理链是不同设置。信息源、训练监督、年份、标签、容量和有效日均不同；不能据此声称图结构造成普遍负迁移。R2训练0.047227%改善不等于图结构因果效应。D5回顾性LOYO不是E4固定时序测试，外部月不能替代日尺度独立检验。

## 7. 下一阶段推荐三项

先过数据/协议门槛，再按research_protocol设计执行：季节条件化的上游增量信息检验；同输入同容量的方向×时滞消融；冻结R1+小残差在新未揭示年份的外推失效检验。当前不重做历史lag/R1/R2/Fourier/LOYO/M2C，跨站与跨流域需真实数据。

## 8. P0/P1/P2

P0：MQ血缘、日Q单位/日界/供数说明、月数据源与单位、新封存测试区间、C独立参数来源、历史全期筛选的评价身份。具体阻断分支见研究协议；MQ不明不禁止MQ-free带警告探索，但禁止C/独立验证主张。
P1：侧向来水/取水/闸控/断面和reach标签缺失、参数可识别性、现代几何代表性、日尺度传播分辨率、容量预算和共同日期、初始化、辅助接口合法性及历史执行绑定证据。
P2：大合成网、多站GNN、Caravan/CAMELS、遥感、神经算子与扩散；全部延期且不虚构输入。

## 9. 历史冻结文件完整性

本轮前后SHA-256核对 **{I['checked_files']}文件、约4.43GB**：修改0、删除0、历史范围新增0。范围scripts/src/configs/tests/reports/outputs/data/processed/data/raw及根项目文件；包含E4、E5A、E5B图件、全部已有论文和审计。排除.git/.venv/node_modules/cache及data/remote_sensing；本轮未向这些目录写入。E5A登记源文件 **17/17哈希和大小匹配**，是与既存冻结记录的独立比较；前后快照则只证明本轮没有改变。
Git状态命令实际失败：fatal: not a git repository。无法判断本轮开始前是否存在未提交修改，记UNVERIFIED，未修复/重建Git、未reset/clean/checkout。完整差异见data_audit/integrity_result.json。

## 10. 准入与停止

S0来源清单、来源/泄漏/拓扑/物理基线审计、研究协议和最小合成测试已完成；来源/独立性仍存在P0，**READY_FOR_VHS_NEXT_S1=false**。审计完成不表示来源PASS。本轮真实模型训练=false、冻结结果修改=false、已有论文修改=false。已停止，等待用户对P0补证和具体S1分支的批准；不执行E5I1或任何Future任务。
''')
status='''VHS_NEXT_S0_SOURCE_INVENTORY_COMPLETE=true
VHS_NEXT_S0_PROVENANCE_AUDITED=true
VHS_NEXT_S0_LEAKAGE_AUDITED=true
VHS_NEXT_S0_TOPOLOGY_AUDITED=true
VHS_NEXT_S0_PHYSICS_BASELINES_AUDITED=true
VHS_NEXT_S0_SYNTHETIC_TESTS_COMPLETE=true
REAL_DATA_MODELS_TRAINED=false
E4_E5_FROZEN_RESULTS_CHANGED=false
EXISTING_MANUSCRIPT_CHANGED=false
READY_FOR_VHS_NEXT_S1=false
PHYSICAL_REFERENCE_Q_GENERATION=PROVENANCE_UNVERIFIED
EXTERNAL_MONTHLY_PRIMARY_PROVENANCE=UNVERIFIED
DAILY_Q_PRIMARY_PROVIDER_UNITS_DAY_BOUNDARY=UNVERIFIED
GIT_PREEXISTING_UNCOMMITTED_STATE=UNVERIFIED
S0_AUDIT_COMPLETE_DOES_NOT_MEAN_SOURCE_PASS=true
SYNTHETIC_TEST_LABEL=SYNTHETIC_UNIT_TEST_ONLY
STOPPED_AFTER_VHS_NEXT_S0=true
'''
(R/'vhs_next_s0_status.txt').write_text(status,encoding='utf-8')
(BASE/'README.md').write_text('''# VHS-NEXT-S0

本目录是独立新研究交付，历史文件只读。入口：reports/vhs_next_s0_validation_report.md。
详情：source_inventory / provenance_audit / leakage_audit / topology_audit / physics_baseline_inventory / research_protocol。
物理规范：physics/physics_baseline_specification.md。状态：reports/vhs_next_s0_status.txt。
哈希范围和逐值证据：data_audit/。合成测试：tests/。下一阶段仅设计：experiments/、evaluation/。

已执行命令（项目根，PowerShell）：
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/integrity.py before`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/collect_evidence.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/tests/run_synthetic_tests.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/tests/check_synthetic_input_boundary.py`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/data_audit/integrity.py after`
`.venv/Scripts/python.exe -B research_next/vhs_transfer/reports/build_s0_reports.py`

before基准脚本拒绝覆盖，勿当成可随意重置的状态。rerun仅限经批准的审计/合成核验，不能自动进入真实实验。
''',encoding='utf-8')
print(json.dumps({'reports_written':len(list(R.glob('vhs_next_s0_*'))),'source_assets':len(M),'ready_for_S1':False,'synthetic_passed':T['passed']},ensure_ascii=False))
