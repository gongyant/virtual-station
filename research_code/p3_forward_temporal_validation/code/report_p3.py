"""P3 scientific interpretation and final-model decision from fixed verified results."""
import csv,json,shutil
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];R=P.parent;run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_TEMPORAL_P3-"))
def rr(path):
 with path.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
n=lambda x:float(x)
S={r["scope"]:r for r in rr(P/"P3_COHORT_SUMMARY.csv")};primary=S["PRIMARY_COMPLETE_10Y_24"];all27=S["ALL_SUPPORTED_27"]
spl=jl(P/"P3_SPLIT_FROZEN.json");man=jl(run/"P3_RUN_MANIFEST.json");reg=rr(P/"P3_REGION_SUMMARY.csv");vs=rr(P/"P3_VS_P2_SUMMARY.csv");failure=rr(P/"P3_FAILURE_ANALYSIS.csv");meta=rr(P/"P3_OVERALL_METRICS.csv");diag=rr(P/"P3_SEASON_FLOW_SUMMARY.csv")
lines=["# P3：固定前月降水模型的较晚时段实测检验",
"真实训练、全局预测封存、评分和独立核验均已完成。2005–2014年未换时段，未训练SNOW、未修改模型或alpha网格。结论：L1增量在较晚时期继续存在，但部分年份、季节和站点仍有失败或不确定；适合固定为P4主候选，不能据此宣布通用或机制已验证。",
f"run：{run.name}。任务严格标为 RECONSTRUCTION_WITH_OBSERVED_MET：使用测试当月已知P/T和前月P作月末历史重建，不是提前一个月流量预报，不是新独立流域试验。LamaH-CE v1.0公开实测qobs来自D_gauges，气象是ERA5-Land再分析，非COSERO输出。教师锡尔河Q及R0均未访问。",
"## 1. 时间支持与冻结（先于任何P3评分）",
"27站全部具备训练资格；训练候选期1981–2004，使用按原规则合格且对两模型共同可用的全部月份，保留不完整训练年；每个日历月至少23个训练年参考。测试固定2005-01至2014-12，24站完整120月作为预定主分析；三个部分支持站保留全部合法月份作单独与全体支持次分析。替代时段未使用。",
"总训练7737个月，测试3203个唯一站—月份；54次外层参数拟合、6470次训练期内层拟合（两模型各27+3235），总6524次真实拟合调用，测试预测6406条。无失败拟合、无丢弃合法测试月份、无重复样本身份。一次完整数值尝试，没有按分数重试。",
"ID611和688分别仅102月，均是2013-07起至2014-12共18个月不符合源方质量标志；这些36个月原始Q存在，但ckhs=0，不能统称真实缺档。ID428的2009-03有2日Q缺测/未检查，该月排除，保留119月。排除规则是评分前统一冻结的，不因模型误差而变。见P3_EXCLUDED_TEST_Q_REASONS.csv。",
"各站1981-01因无1980-12合法上月气象而从共同训练集排除；ID512从1982年起有276个训练月，ID460另有1985年一个不合格月，合计286月。其余多为287月。没有把稀疏表上一行替代真正前月，也没有将缺测填零。",
"预审可检查测试Q的有效日数和覆盖；模型进程加载的features.csv不含Q，训练Q单独文件且只含≤2004年。测试Q文件直到27站×两个模型预测全部生成、写成无Qobs预测包并封存SHA256后，才由评分角色加载。预测包、提交时间、释放收据和attempt顺序均保留。",
"## 2. A/B：增量是否延续，正技能站数多少？",
f'预定主分析24个完整十年站：24/24正技能，站等权平均MSE技能={100*n(primary["mean_station_MSE_skill"]):.2f}%，中位={100*n(primary["median_station_MSE_skill"]):.2f}%；平均NSE C0+PT {n(primary["C0PT_mean_NSE"]):.6f} → L1 {n(primary["L1_mean_NSE"]):.6f}，平均KGE {n(primary["C0PT_mean_KGE"]):.6f} → {n(primary["L1_mean_KGE"]):.6f}。',
f'全27站全部合法测试月份次分析：27/27正技能，站均={100*n(all27["mean_station_MSE_skill"]):.2f}%，中位={100*n(all27["median_station_MSE_skill"]):.2f}%；平均NSE {n(all27["C0PT_mean_NSE"]):.6f} → {n(all27["L1_mean_NSE"]):.6f}，KGE {n(all27["C0PT_mean_KGE"]):.6f} → {n(all27["L1_mean_KGE"]):.6f}。三个部分支持站的均值31.49%较大，故不能用全体12.47%替代完整十年的主要10.10%结果。',
"未混合不同站原始m³/s平方误差计算总体技能；先在每站相同日期/标签上算1−MSE_L1/MSE_C0PT，再站等权平均或取中位数。各年、冬季、高低流量也遵循同站相同支持。所有原始预测保留，非负截断仅为预设次分析。",
"主分析非负次分析仍24/24改善、平均技能10.07%；全27站仍27/27、12.45%。原始C0+PT与L1分别6/4个负预测，未因负值删月或用截断成绩替换主结果。",
"## 3. C：相对P2的LOYO是下降还是改善？"]
for scope,label in [("PRIMARY_COMPLETE_10Y_24","同24个完整测试站"),("P2_DEVELOPMENT_9","原九站"),("P2_EXTERNAL_18_SAME_SITES","P2原18站")]:
 for r in vs:
  if r["scope"]==scope:
   old="连续十年LOYO" if r["P2_scenario"]=="CONSECUTIVE_10Y" else "稀疏十年LOYO"
   lines.append(f'- {label}，P2 {old}平均技能{100*n(r["P2_mean_station_skill"]):.2f}% → P3 {100*n(r["P3_mean_station_skill"]):.2f}%；{r["n_stations_P3_skill_greater"]}/{r["n_same_stations"]}站的技能增加。')
lines+=["因此总体及原18站更强，原九站平均增量反而下降。P3扩展了训练期资料（约23–24年，而P2外层通常9年），测试分布也不同，不能把差值当作纯时间漂移效应或宣称所有站时间泛化都变好。没有为分离此原因重新训练P2或增加新实验。",
"## 4. D：必须保留的年份、季节和水系失败",
"虽然没有站的全测试期MSE技能为负，共有50个合法站—年份的L1技能为负（完整24站占47个）。P3_NEGATIVE_YEAR_CASES.csv完整保留；2014年ID611/688无合法测试月，两模型对应4行年度统计为N/A及NO_ADMISSIBLE_TEST_MONTHS，不用0代替。",
"2012是共同失败：完整24站仅8站改善，站均年度技能−8.40%、中位−8.91%；Rhine5站全退步，组均−30.04%；Elbe2站全退步，−11.87%；Danube17站仅8站改善，组均−1.63%。其他年份的主分析站均年度技能均为正。该失败不改时段、不删年份、不加SNOW。",
"2012逐月归一化年度技能贡献的站等权分解显示，1–2月、6–8月贡献主要负项，4/11月部分抵消。它是固定误差的事后诊断，不是窗口/模型重新选择依据；见P3_2012_MONTH_CONTRIBUTIONS.csv。",
"主分析DJF冬季平均技能7.88%，19/24站改善；5–6月10.62%，19/24改善；低流量8.09%，18/24改善；高流量10.26%，22/24改善。全时段正技能不代表全季节或全流量范围都改善。",
"弱证据站ID2、533、545的全时段技能分别0.45%、1.30%、0.77%，都仅6/10年改善；删除一个测试年后的平均改善可能反转，年度bootstrap跨零。未对这些站事后改用另一个模型来抬高成绩。",
"完整24站中21站删除任一测试年仍保持平均改善，15站的年度bootstrap描述区间完全位于零以上。该jackknife基于已固定测试损失，不是删除测试年后重新训练；bootstrap只描述条件测试误差，不包含全部参数不确定性。",
"## 5. 水系依赖与不确定性",
"主分析宏观分布Rhine5、Elbe2、Danube17；全27站Danube增加为20。原2/6与9存在上下游嵌套，同水系站点及共享气候年代都不独立；本轮没有把27个相关站当作27个无条件独立重复。"]
for r in reg:
 if r["scope"]=="PRIMARY_COMPLETE_10Y_24" and r["group_type"]=="macro_group":
  lines.append(f'- {r["group"]}：{r["positive_skill_stations"]}/{r["n_stations"]}全时段改善，站均技能{100*n(r["mean_station_MSE_skill"]):.2f}%，中位{100*n(r["median_station_MSE_skill"]):.2f}%。')
lines+=["按宏观水系整块bootstrap999次，完整24站的站等权均值描述范围为[4.56%,17.31%]；删除一个水系后均值范围[8.20%,11.55%]。仅三个不平衡水系，这不是可靠的总体置信保证或确认性普适声明。逐官方区域结果另列P3_REGION_SUMMARY.csv。",
"## 6. 外推、气候态与极端误差检查",
"没有训练同月常数气象特征，训练每月有至少23年参考，不能把当前失败简单归为只有几个训练样本。所有54次外层都按原one-SE规则选alpha=100，未扩大网格。全部月气候态/标准差均从≤2004训练集估计，并在内层重拟合。",
"27站的当月T相对训练月气候态平均标准化异常均为正，站均约+0.327训练SD，说明较晚时期协变量分布存在偏移。部分观测Q月均值也偏离训练气候态，详见P3_MONTHLY_Q_DRIFT.csv；这些目标期诊断只在预测封存后计算，不作为特征或调参依据。",
"最大气象异常约5.86训练SD：ID255在2009-06当月P、2009-07前月P；温度最大约5.64SD见ID270的2007-04。模型外推确实存在，但本轮没有约296SD的雪代理，不应把P2-SNOW问题套用到此处。",
"错误也会集中在少数月份：ID185在2006-04的L1预测3.996681、观测10.811167 m³/s，该月占其测试总SSE约37.40%；ID383在2009-03占约28.15%；ID377在2013-06占约22.68%。全部最坏月份、年份和占比在P3_ERROR_CONCENTRATION.csv，没有删掉极端月份。",
"现有诊断支持存在温度分布偏移、观测季节幅度变化和极端响应不足；不能仅据这些误差归因于积雪、人工调节或其他具体机制，也不能证明其中某一因素导致2012退步。无需为本轮结果另调窗口或加特征。",
"## 7. E：P2的18/18在新的时间维度是否得到支持？",
"得到带覆盖限定的支持：P2原18站在P3全部可评价月份上18/18正技能，平均13.85%；其中只有16站有完整120个月，完整16站16/16改善、平均11.82%。另外ID428保留119月、ID688保留102月。不能表述为18站均通过完整十年验证。",
"这是相同已开发流域的独立较晚年份检验，不是再次取得18个全新的空间独立流域；P3结果一旦参与P4模型选择，不能再称为选择后P4模型完全独立的最终测试。",
"## 8. F/G：下一阶段决定",
"建议P4预先固定P2-L1为主模型候选，C0+PT保留为强制基线。现有证据支持这个固定规格，没必要继续筛滞后或增加SNOW；不逐站按P3分数切换模型。ID2/533/545等弱证据站继续明确标记增量不确定。",
"可以有条件进入单独P4的最终应用拟合和公开数据缺档试点：先固定真正要重建的年月、训练资料截止、数据质量资格、气象可用性、外推标记和不确定性方案，区分真实缺测与原值存在但未检查的记录。未检查的36个月不能自动当作真实缺档、更不能拿模型值覆盖原值。",
"最终应用拟合可在明确范围内使用更多合法观测，但若把2005–2014纳入最终训练，P3成绩只属于当前冻结的时间外模型；不能当作那个全资料重拟合模型的新独立测试成绩。若要确认最终选择后的误差，需要另保留未参与选择的时期/数据；源资料中的2015–2017等仅是以后可核查覆盖的候选，本轮未纳入这些年的训练、诊断或评分。",
"本轮停止于P3，不训练P4最终模型、不实际填补缺档、不读教师数据。锡尔河仍NOT_GRANTED；没有改HTTP门禁。",
"## 9. 可复核证据",
"6/6前向边界测试通过。独立核验覆盖11016个Q月准入判断、11043个气象月聚合、10940个共同特征行、6406条参数预测重算、54次Ridge梯度最优性、6470个内层分割及6524个真实拟合事件。所有训练日期在测试期前，所有预测身份唯一，两个模型支持完全一致。",
"历史P0/P1/P2冻结文件分别206/206、120/120、207/207通过；真实run及无Qobs预测包另有独立SHA256。首次核验脚本因Windows路径分隔符查找报错，修正仅限只读脚本，未重训、未改预测；记录在evidence/VERIFIER_PATH_CORRECTION.json。",
"数据许可和归属沿用原合法公开来源记录：Zenodo页面CC BY-SA4.0与API/包内CC BY4.0既有差异继续按更严格CC BY-SA4.0处理，保留官方归属和参考文献。Q为m³/s，P为mm/月，T为°C；不把公开结果写入SYRDARYA成绩表。"]
(P/"P3_SCIENTIFIC_REPORT_ZH.md").write_text("\n\n".join(lines),encoding="utf-8")
decision="""# P3 → P4 固定模型决定
决定：固定 P2-L1 为下一阶段 P4 主候选；C0+PT 保留为强制基准。不增加滞后、不加SNOW、不逐站依据P3分数切换模型。

依据：24个完整十年站24/24正增量，站均10.10%；原P2的18站在P3可评价月份18/18，完整16站16/16。该结论有真实预测提交与评分分离证据。
限制：2012年完整站总体退步，ID2/533/545增量不稳定，只有三个不平衡水系，部分极端月份误差集中；不是普适性或物理机制证明。

可以在单独P4中有条件启动公开数据最终应用拟合：
1. 先固定实际缺档目标、训练截止与源方QC规则、气象覆盖及输出标签。
2. 保留原观测，区分真实缺测与原值存在但ckhs未检查；本轮36个被排除月属于后者，不能自动替换。
3. 冻结L1公式和alpha网格，记录新训练范围与参数，不将全资料拟合曲线称样本外验证。
4. 若最终拟合纳入2005–2014，P3作为当时冻结模型的时间外验证保留，但不再作为P4选择后模型的新独立最终测试。需要新的未用评估数据才能作此声明。
5. 真实缺档年份没有Q直接评分，产物单独run，并报告外推和不确定性。

本轮未启动P4，未生成最终缺档重建结果。教师锡尔河Q仍未授权。
"""
(P/"P3_FINAL_MODEL_DECISION.md").write_text(decision,encoding="utf-8")
failreport="""# P3 时间验证失败与薄弱证据报告
全部站全时段平均技能为正不代表没有失败。固定模型与全部合法测试月均保持原样。

- 2012年：完整24站仅8站改善，站均技能−8.40%；Rhine5站全退步（−30.04%），Elbe2站全退步（−11.87%），Danube17站仅8站改善（−1.63%）。
- 全部可评价站—年份中50个负技能，完整24站中47个；P3_NEGATIVE_YEAR_CASES.csv保留所有案例。2012负贡献主要在1–2月及6–8月。
- ID2/533/545仅有0.45%/1.30%/0.77%全期技能，删除一个测试年后平均优势可消失。未事后改用C0+PT替换这些站的主结果。
- 完整24站冬季和5–6月各5站退步，高流量2站、低流量6站退步。
- ID185 2006-04占其L1测试总SSE37.40%，ID383 2009-03占28.15%，未剔除极端月。
- 温度分布相对训练月气候态偏移，测试P/L1最高约5.86训练SD。训练每月至少23年、无常数特征，不支持将失败简单归因于极少训练样本；具体物理原因未被识别。
- 36个排除月不是原始Q缺失，而是原值存在但ckhs=0；另一个月缺2日Q。未放宽QC换取完整27站成绩。

P3_FAILURE_ANALYSIS.csv列出每站最坏年/月和jackknife；P3_GROUP_DIAGNOSTICS.csv列出水系年度/季节差异；P3_EXTRAPOLATION_SUMMARY.csv和P3_MONTHLY_Q_DRIFT.csv列出分布诊断。
本报告不提出本轮重新调参、换时段、删数据或加SNOW。
"""
(P/"P3_TEMPORAL_FAILURE_REPORT.md").write_text(failreport,encoding="utf-8")
guide=f"""# P3 复现与交付索引
已完成run：{run.name}
任务：RECONSTRUCTION_WITH_OBSERVED_MET；真实公开Q，非合成，非教师锡尔河。

优先只读核验：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\code\\verify_p3.py'
~~~
该命令不重新拟合、不修改run或报告，验证预测/参数/评分、日期、全局预测提交先于测试Q释放和历史哈希。

科学复现入口（仅未来明确要重跑时；不是本轮要求继续执行）：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\code\\run_p3.py'
~~~
会创建另一个run并追加attempt；先保留当前完整交付快照。重跑不再是一次全新未见测试，不能把多次复现当独立科学重复。
不要重跑prepare_p3.py覆盖已经冻结的协议和切分；不得修改P2模型文件。
初始边界单元测试可在未封存副本中运行code/test_p3.py；历史P2完整训练未重复。

源数据：公开副本原有日尺度文件，路径/哈希见source/SNAPSHOT.json。source/features.csv无Q；train_labels.csv只含≤2004；test_labels_SCORE_ONLY.csv仅在全局预测包封存后由评分角色读取。
source/weather_monthly.csv及P3_TEMPORAL_SUPPORT_AUDIT.csv记录真实月聚合与前月对齐。缺测不为0。
在预测阶段会读取测试气象，符合月末历史重建；不支持提前流量预报。

run内prediction_bundle含无Qobs预测、参数、内层记录、拟合事件和单独SHA256；外层run再封存评分结果、测试Q释放收据及日志。
根目录SHA256覆盖本次完成交付；RUN_ATTEMPTS是该时间点快照，后续追加会改变交付点哈希，但不得改变原run。
后验汇总代码analyze_p3.py/postmortem_p3.py/diagnose_p3_support.py/report_p3.py只分析封存结果；新CSV以x模式写入，默认拒绝覆盖已有结果。

主报告P3_SCIENTIFIC_REPORT_ZH.md；决定P3_FINAL_MODEL_DECISION.md；失败P3_TEMPORAL_FAILURE_REPORT.md。
P3_COHORT_SUMMARY.csv完整24站为主，全27及部分3站另列。
P3_VS_P2_COMPARISON.csv / P3_VS_P2_SUMMARY.csv是同站不同训练期/测试期的描述比较，不是纯时间效应估计。
环境Python{man["environment"]["python"]}、NumPy{man["environment"]["numpy"]}，CPU单线程，无安装/网络下载。
"""
(P/"P3_REPRODUCTION_GUIDE.md").write_text(guide,encoding="utf-8")
for old,new in [("ATTRIBUTION_ORIGINAL.txt","ATTRIBUTION_ORIGINAL.txt"),("SOURCE_AND_LICENSE.md","SOURCE_AND_LICENSE_ORIGINAL.md")]:shutil.copyfile(R/"reports"/old,P/"reports"/new)
completion={"label":man["label"],"task":man["task"],"run_id":run.name,"complete_10year_stations":24,"partial_support_stations":[611,428,688],"positive_primary_stations":24,"positive_all_supported_stations":27,"primary_mean_skill":n(primary["mean_station_MSE_skill"]),"primary_median_skill":n(primary["median_station_MSE_skill"]),"all_supported_mean_skill":n(all27["mean_station_MSE_skill"]),"outer_fits":54,"inner_fits":6470,"test_predictions":6406,"failed_fits":0,"P4_decision":"fixed L1 main candidate; C0PT compulsory benchmark; application final fitting only in separate P4 with explicit target/support","P4_executed":False,"SYRDARYA_trained_models":0}
(P/"P3_COMPLETION_STATUS.json").write_text(json.dumps(completion,indent=2),encoding="utf-8")
print(json.dumps(completion,indent=2))

