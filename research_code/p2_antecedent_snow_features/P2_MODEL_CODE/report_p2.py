"""Chinese research delivery generated exclusively from completed sealed P2 outputs."""
import csv,json,collections,shutil,hashlib
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];R=P.parent;run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_EXPLORATORY_P2-"))
def rr(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def cw(p,rows):
 with p.open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
n=lambda v:float(v)
man=jl(run/"manifest.json");sel=jl(P/"P2_NEW_BASINS_FROZEN.json");summ=rr(P/"P2_COHORT_SUMMARY.csv");met=rr(P/"P2_OVERALL_METRICS.csv");comp=rr(P/"P2_MODEL_COMPARISON.csv");ds=rr(P/"P2_DIAGNOSTIC_SUMMARY.csv");support=rr(P/"P2_FOLD_FEATURE_SUPPORT.csv");alpha=rr(P/"P2_ALPHA_SELECTION.csv")
score_summary=[]
for cohort in ["DEVELOPMENT_9","EXTERNAL_FROZEN_NEW"]:
 for ex in ["CONSECUTIVE_10Y","SPARSE_10Y_PUBLIC_SUBSAMPLING"]:
  for model in ["C0+PT","P2-L1","P2-SNOW"]:
   rs=[r for r in met if (r["cohort"],r["scenario"],r["model_id"])==(cohort,ex,model)]
   score_summary.append({"cohort":cohort,"scenario":ex,"model_id":model,"n_basins":len(rs),**{f"{metric}_{summary}":float(getattr(np,summary)([n(r[metric]) for r in rs])) for metric in ["NSE","KGE"] for summary in ["mean","median","min","max"]},"interpretation":"EQUAL_BASIN_DESCRIPTIVE_SUMMARY_NOT_INDEPENDENT_REPLICATES"})
cw(P/"P2_SCORE_SUMMARY.csv",score_summary)
def score(ex,g,mid):return next(r for r in met if r["scenario"]==ex and int(r["gauge_id"])==g and r["model_id"]==mid)
C="CONSECUTIVE_10Y";S="SPARSE_10Y_PUBLIC_SUBSAMPLING"
lines=["# P2：前期降水与融雪统计代理的公开实测训练结果",
"本轮已实际执行，标签 PUBLIC_DATA_EXPLORATORY_P2。结论：日历前月降水 L1 在新18站两套固定方案中均带来正的平均样本外增量；固定三个月/0°C融雪代理不具备同样稳定性，稀疏方案中有严重尾部外推失败。建议优先对 P2-L1 做未使用时段压力验证，不把 P2-SNOW 选为通用模型。",
f"不可变 run：{run.name}。仅使用既有合法公开 LamaH-CE v1.0 副本（DOI 10.5281/zenodo.5153305）。Q源为D_gauges实测qobs，非COSERO模拟；P/T为A类完整上游流域ERA5-Land再分析。未访问教师锡尔河Q、旧私有隔离目录或R0授权环境。P1代码、协议、结果与120项交付封存均保持一致。",
"## 1. 冻结与真实执行",
"原九站2、6、9、533、818、255、611、460、378；新18站22、10、377、103、142、270、230、545、480、512、401、383、428、455、171、343、185、688。新站在任何P2模型评分前冻结，连原九站P2分数也尚未查看。选择仅用官方面积/积雪比例/区域、观测年起点/影响等级、完整日数与河网；未用水文模型成绩或源Q派生水文指数。",
"候选430因1993年7/8月和1999年9月Q不完整而排除，使用预先排序下一候选428。未降低质量条件或按分数换站。原九站及18新站的全部固定窗口均保留，两个方案分别1990–1999及[1983,1987,1990,1994,1996,1999,2000,2001,2002,2004]；没有删月或失效折。",
"三模型在完全相同支持集合上重新拟合，原九站540条折—模型结果/6480条OOF，新18站1080条/12960条OOF。总计540个外层折、1620次外层拟合、72900次内层拟合，实际74520次参数拟合调用、19440条OOF。每模型540次外层+24300次内层；CPU单线程，训练与写入约49秒；一次完整尝试，无失败拟合或重试。",
"唯一源标签月5184条（27站×192个月），不能把19440条模型—月份记录当作独立观测。外生气象月5508条，其中324条只是前期气象月份，未解析或保留其Q数值。两个时间方案共享部分年份，不是两组独立流域样本。",
"## 2. 特征、基线和隔离",
"固定P2-L1=P/T异常+实际日历上月P异常；P2-SNOW=P/T异常+S/M异常，S=前三个月P×I(T≤0°C)之和，M=S×max(当月T,0°C)。三个月与0°C从头到尾未改变；S单位为mm的统计代理，M单位mm·°C的统计代理，均不是真实雪水当量、融雪量或融雪径流。",
"所有模型固定外层训练Q的十二个月均值，联合估计当月P/T及新增异常系数；同一alpha惩罚全部气象系数，不惩罚或重新改变月份气候态。alpha固定[0.01,0.1,1,10,100]，内层按年交叉验证、one-SE选择最强合格正则。每次内层和外层均仅以该训练目标月份的特征值计算气候态与样本标准差。",
"前期输入允许来自无Q标签月份，也可能与另一个留出年份的原始气象日期重叠；它们是已知外生天气，不包含该年Q。标签训练/最终评分角色隔离，预测函数只接收输入。LOYO用于历史重建，可使用其他观测年份训练；本轮没有证明时间前向预报或严格无资料站能力。",
"原九站C0+PT在P2共同集重新拟合，18个站—方案与P1预测最大差为8.53e-14 m³/s，证明基线数值一致；评价没有直接引用旧分数。没有重新执行P0/P1。",
"13/13合成测试通过：跨年/稀疏日期、0°C边界、缺测不变零、零代理支持、未罚月份截距、与联合月哑变量Ridge的数学等价、内层重拟合、测试标签拒绝、不变性和确定性等。独立核验重新聚合5184个月实测Q、5508个月P/T、独立重算日历特征及19440条OOF，并检查1620组Ridge梯度最优性和72900组内层身份。见P2_REAL_RUN_VERIFICATION.json。",
"## 3. 总体气象增量：流域等权，原九站和外部站分开"]
for r in summ:
 name="原九站开发" if r["cohort"]=="DEVELOPMENT_9" else "新增18站验证";ex="连续十年" if r["scenario"]==C else "固定稀疏十年"
 lines.append(f'- {name}，{ex}，{r["candidate"]}：平均/中位MSE技能={100*n(r["equal_basin_mean_MSE_skill"]):.2f}%/{100*n(r["equal_basin_median_MSE_skill"]):.2f}%；正技能{r["positive_basin_count"]}/{r["n_basins"]}站；年度改善比例的站均值{100*n(r["mean_fraction_years_improved"]):.1f}%；删除任一年仍改善{r["jackknife_positive_all_year_deletions_count"]}/{r["n_basins"]}站。')
lines+=["A：P2-L1在原九站18项平均比较全部改善，新18站两方案也各18/18改善。B：P2-SNOW原九站连续9/9、稀疏7/9，新18站连续15/18、稀疏16/18改善，但新站稀疏均值为负，不能以多数站改善掩盖大失败。",
"## 4. 外部检验的独立性和不确定性",
"新站包括莱茵河2站、易北河1站、多瑙河15站，面积与高程/积雪分布见P2_NEW_BASINS_FROZEN.json。官方NEXTDOWNID未发现新站彼此或与原九站嵌套；跨流域调水表未发现将这些上游控制区连接的记录。这不证明未知人工连通不存在。多瑙河大区的15站及相同气候年代仍相关，不能当18个完全独立空间重复。",
"本轮新增流域检验是在每个新站用其自己其他年份的Q标签训练，再留一年验证；它是同一方法在新流域的外部重复检验，不是跨流域零目标标签迁移。",
"按宏观水系整块bootstrap999次，保留块内所有站点，主估计仍为每站等权；另报水系等权均值和删除一个水系的范围。只有三个且极不平衡的水系块，这些区间仅描述性，不宣称可靠覆盖率、总体显著性或确认性普遍增益。"]
for r in summ:
 if r["cohort"]!="EXTERNAL_FROZEN_NEW":continue
 ex="连续" if r["scenario"]==C else "稀疏"
 lines.append(f'- 新站{ex} {r["candidate"]}：站等权均值的水系块bootstrap95%描述范围[{100*n(r["river_block_bootstrap_basin_weighted95_low"]):.2f}%, {100*n(r["river_block_bootstrap_basin_weighted95_high"]):.2f}%]；水系等权均值{100*n(r["macro_equal_mean_skill"]):.2f}%；删一个水系后均值范围[{100*n(r["leave_one_macro_out_min_mean_skill"]):.2f}%, {100*n(r["leave_one_macro_out_max_mean_skill"]):.2f}%]。')
lines+=["新站P2-L1的年度bootstrap区间连续12/18、稀疏11/18完全位于零以上。ID171连续方案仅6/10年改善，1991贡献超过净改善100%，删除该年后优势反转，因此18站平均为正不等于每个站都稳定。原九站内部2/6处于9上游，不能将原九站的开发结果当独立确认样本。",
"ID688的L1技能较大，但1999贡献连续方案净改善约52.7%、稀疏约68.6%；稀疏的年度bootstrap仍跨零。全部逐年差异、jackknife和bootstrap均保留，未按p值删模型或样本。",
"## 5. 5–6月、冬季与高低流量",
"以下是相同月份/相同高低流量子集上的每站技能再等权平均，并非把不同站原始m³/s误差混合。高低流量分别采用外层训练Q的20%/80%分位数，阈值不用于模型输入或调参。"]
for r in ds:
 if r["cohort"]!="EXTERNAL_FROZEN_NEW":continue
 ex="连续" if r["scenario"]==C else "稀疏";label={"MAY_JUN":"5–6月","DJF":"冬季DJF","LOW_Q_LE_TRAIN_Q20":"低流量","HIGH_Q_GE_TRAIN_Q80":"高流量"}[r["subset"]]
 lines.append(f'- 新站{ex} {r["candidate"]} {label}：站均MSE技能{100*n(r["mean_skill"]):.2f}%，中位{100*n(r["median_skill"]):.2f}%，改善{r["positive_basins"]}/{r["n_basins_with_defined_skill"]}站。')
lines+=["C：L1在新站5–6月平均改善连续5.88%、稀疏10.21%；冬季则连续平均退步2.81%、稀疏改善9.71%，不存在全季节一致优势。SNOW在新站5–6月平均改善2.22%/10.37%，冬季平均退步23.58%/137.11%，后者严重受ID383失效影响；该站完整保留。",
"## 6. 代理支持、响应和一次真实失败",
"E：原始前期气象没有缺测，27站两方案共同支持均完整；这与统计代理是否有信息是两件事。所有SNOW外层折中，S有2–7个日历月、M有5–9个日历月的训练标准差为零，统一标记ZERO_STD_ZERO_ANOMALY。没有整年S/M都恒定的折，但只有部分季节有信息。另有76个特征—测试月份在训练同月恒定而测试原值发生变化，均保留标志；没有通过全局标准差或测试期数据“救活”特征。",
"非零训练支持、常数月份、测试偏离见P2_FOLD_FEATURE_SUPPORT.csv。原始真实零值保留；标准化零仅表示训练没有可估计的该月异常尺度，不代表原始缺测被填成零。",
"固定预测的气象响应保存于P2_INPUT_RESPONSE.csv和P2_RESPONSE_SUMMARY.csv：各折每个气象异常系数均以m³/s/训练月标准差记录；额外计算当月温度+1°C且保持前期天气不变、同步重新计算M的条件预测变化。这是模型坐标响应，不是温度或融雪的物理因果效应；不把不同面积站的原始系数直接平均解释。",
"ID383（Morava区）稀疏方案P2-SNOW的MSE技能=−270.21%，NSE=−2.118442、KGE=−0.055219；基线NSE=0.157648、KGE=0.191165。最严重月份1994-01：实测1.379935 m³/s，预测26.969338 m³/s。",
"该折一月M训练均值0.087211、样本标准差0.261634，最大训练原值0.784903；测试M=77.422065，标准化后为295.583648个训练标准差，单项贡献25.974965 m³/s。这是稀疏的近零代理训练支持遇到未见暖冬组合产生的巨大线性外推；日期、源值、标准化和Ridge解均已独立核验，无非有限数值或错位证据。",
"没有缩尾、修改零温阈值、扩大窗口、改用全局尺度、删掉1994年或替换该站来改善分数。非负截断也不能修复正向外推，次分析NSE仍为−2.098833。说明此固定SNOW代理尚不适合作为稳健通用模型，并非证明真实积雪/融雪过程没有信息。",
"原九站ID533的SNOW稀疏NSE=0.946527、KGE=0.964089，确有局部强增益；但不能用它覆盖ID383等失败，也不能据最高分确定通用模型。",
"alpha上边界选择次数：C0+PT507/540、P2-L1482/540、P2-SNOW466/540。候选网格未扩大；one-SE本来就偏向强正则，边界频率不能单独证明最优值在网格外。",
"## 7. 真实NSE/KGE实例与完整记录"]
for ex,name in [(C,"连续"),(S,"稀疏")]:
 for g in [2,533,688,383]:
  rs=[score(ex,g,m) for m in ["C0+PT","P2-L1","P2-SNOW"]]
  lines.append(f'- ID{g} {name}：按C0+PT / P2-L1 / P2-SNOW顺序，NSE={n(rs[0]["NSE"]):.6f} / {n(rs[1]["NSE"]):.6f} / {n(rs[2]["NSE"]):.6f}；KGE={n(rs[0]["KGE"]):.6f} / {n(rs[1]["KGE"]):.6f} / {n(rs[2]["KGE"]):.6f}。')
lines+=["完整27站×两方案×三模型的162行总体指标、1620行逐年指标以及全部19440条OOF，均在P2_OVERALL_METRICS.csv、P2_YEARLY_METRICS.csv、P2_OOF_PREDICTIONS.csv。NA_reasons保存不满足定义条件的原因，禁止以0替代未定义指标。流域等权NSE/KGE分布另存P2_SCORE_SUMMARY.csv，不隐藏负NSE站点。",
"## 8. 进入P3的决定",
"优先推进固定P2-L1的独立时段压力验证。它在本轮新站18/18×两方案的总体技能均正，且水系分组均值和多数年度敏感性支持正增量，但冬季失败、个别年份依赖、三个不平衡水系及共同年代限制了普适性声明。",
"P3建议先冻结尚未评分的2005–2014等候选时段（先按同样规则核实完整性，不能假定每站都完整）；只使用测试期之前的合法Q训练/调参，一次性评估C0+PT与冻结P2-L1。模型形式、真实日历月滞后、alpha网格、原始/非负主次口径保持固定，按水系和年份报告，不能再把本轮27站当全新确认样本。",
"在独立时段验证成立后，再考虑预注册多流域统计模型、最终模型选择及全部合格年份拟合和缺档应用。不得从当前结果直接宣布已可填补所有历史空白；真实缺档没有Q可直接评价，需单独run和不确定性研究。",
"P2-SNOW保留为本轮明确的局部有效但不稳健结果，不在本轮调整窗口/温阈/尺度继续刷分。后续如要改雪代理，必须另提数值稳定性和过程合理性的预设方案，并在新数据上评价。当前无需扩展神经网络或穷举特征。",
"## 9. 复现、许可和边界",
f"只读核验：用既有Python -B运行 {P/'P2_MODEL_CODE/verify_p2.py'}；训练入口为同目录run_p2.py，未来显式复现会产生另一run及追加attempt，不覆盖本run。不要重新执行prepare_p2.py/freeze_samples.py改动本轮冻结内容。",
"每个真实run包含manifest、协议、选择清单、源快照、折、模型参数、72900项内层验证记录、74520项拟合事件、代码哈希、P1原封存映射及独立SHA256SUMS。根目录结果副本、后验诊断和中文报告由本轮交付SHA256SUMS再次封存。",
"数据许可沿用既有合法来源记录：Zenodo页面CC BY-SA4.0与API/包内CC BY4.0存在既有记录差异，继续遵循更严格CC BY-SA4.0与官方归属引用；完整归属和原来源说明保存在reports。公开数据本地研究产物，不写入SYRDARYA成绩表；锡尔河真实授权保持NOT_GRANTED，真实训练/评价/预测仍为0。"]
(P/"P2_SCIENTIFIC_REPORT_ZH.md").write_text("\n\n".join(lines),encoding="utf-8")
external=["# P2 冻结新增流域的外部验证",
"新18站在任何P2成绩之前冻结。ID清单、候选排除、逐日完整性、官方属性、河网路径和协议哈希见P2_NEW_BASINS_FROZEN.json。站点不是按分数筛选。",
"与原九站分开报告。每个站仍使用自己的其他年份Q训练；这不是无资料站/跨站零标签预测。共同支持完整，没有模型专属删月。",
"## 总体增量"]
for r in summ:
 if r["cohort"]=="EXTERNAL_FROZEN_NEW":
  external.append(f'- {r["scenario"]} {r["candidate"]}：均值/中位技能 {100*n(r["equal_basin_mean_MSE_skill"]):.2f}%/{100*n(r["equal_basin_median_MSE_skill"]):.2f}%，改善{r["positive_basin_count"]}/18，逐年jackknife全正{r["jackknife_positive_all_year_deletions_count"]}/18。')
external+=["## 全部新站连续方案（顺序：C0+PT / P2-L1 / P2-SNOW）"]
for info in sel["new_metadata"]:
 g=info["gauge_id"];rs=[score(C,g,m) for m in ["C0+PT","P2-L1","P2-SNOW"]]
 external.append(f'- ID{g} {info["name"]}，{info["macro_group"]}/{info["region"]}，面积{info["area_calc_km2"]}km²，高程{info["elev_mean_m"]}m，frac_snow={info["frac_snow"]}；NSE {" / ".join(f"{n(r['NSE']):.5f}" for r in rs)}；KGE {" / ".join(f"{n(r['KGE']):.5f}" for r in rs)}。')
external+=["稀疏全部结果及逐年结果见reports/EXTERNAL_FROZEN_NEW。ID383稀疏SNOW失败必须保留：NSE−2.118442、MSE技能−270.21%；真实日历和Ridge数学核验通过，295.6训练SD的代理外推是可直接观察的失效证据，未更改样本/公式。",
"## 空间依赖和结论边界",
"宏观分布Rhine2/Elbe1/Danube15；官方路径中无新站嵌套，但共享多瑙河网络/气候并不独立。只有三个不平衡水系，水系bootstrap及删除水系结果仅描述性。两个时间方案不能视为36个独立流域。",
"L1提供了比原九站开发结果更有价值的外部重复证据，足以优先推进未评分时段验证；仍不宣布确认性普适改进。SNOW为站点/季节依赖且尾部不稳健，不能作为通用最终模型。",
"P2_REGION_SUMMARY.csv逐水系和官方区域列出均值/中位技能；P2_COHORT_SUMMARY.csv保存所有组权重、区间和敏感性口径。"]
(P/"P2_EXTERNAL_VALIDATION_REPORT.md").write_text("\n\n".join(external),encoding="utf-8")
for old,new in [("ATTRIBUTION_ORIGINAL.txt","ATTRIBUTION_ORIGINAL.txt"),("SOURCE_AND_LICENSE.md","SOURCE_AND_LICENSE_ORIGINAL.md")]:shutil.copyfile(R/"reports"/old,P/"reports"/new)
readme=f"""# PUBLIC_DATA_EXPLORATORY_P2
已完成真实公开观测训练；未更改P1/私有VHS；无P3训练。
先读 P2_SCIENTIFIC_REPORT_ZH.md 和 P2_EXTERNAL_VALIDATION_REPORT.md。

不可变run：runs/{run.name}
540外层折、1620外层参数拟合、72900内层拟合、19440条OOF。
原九站与新增18站分组CSV位于reports两个子目录。

只读复核（不重新拟合，不写已有run）：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\P2_MODEL_CODE\\verify_p2.py'
~~~

将来显式复现会生成新run并追加attempt；当前交付封存是此时间点快照，先保留完整交付副本再重跑：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\P2_MODEL_CODE\\run_p2.py'
~~~

P2_FEATURE_SUPPORT.csv是原始年月及前期日期支持；P2_FOLD_FEATURE_SUPPORT.csv是训练折常数/弱支持。
P2_PROXY_EXTRAPOLATION.csv保留每个雪代理测试异常与同月训练范围，未作剔除。
P2_FLOW_DIAGNOSTICS.csv/P2_DIAGNOSTIC_COMPARISONS.csv保留高低流量与季节公平比较。
原始预测主分析；非负预测为预定次分析。没有按测试分数改变模型、阈值、网格或流域。
"""
(P/"README.md").write_text(readme,encoding="utf-8")
status={"label":"PUBLIC_DATA_EXPLORATORY_P2","run_id":run.name,"actual_models":3,"development_gauges":9,"external_new_gauges":18,"macro_groups":["Rhine","Elbe","Danube"],"outer_fits":1620,"inner_fits":72900,"actual_fit_calls":74520,"OOF":19440,"development_OOF":6480,"external_OOF":12960,"failed_fits":0,"P2_L1_new_mean_skills":[.07347040574272173,.09067905109067337],"P2_SNOW_new_mean_skills":[.044475312459328495,-.0934342193659505],"P3_recommendation":"fixed L1 independent unused-time evaluation first; SNOW not stable","P3_executed":False,"SYRDARYA_real_training":0,"SYRDARYA_authorization":"NOT_GRANTED"}
(P/"P2_COMPLETION_STATUS.json").write_text(json.dumps(status,indent=2),encoding="utf-8")
print(json.dumps(status,indent=2))

