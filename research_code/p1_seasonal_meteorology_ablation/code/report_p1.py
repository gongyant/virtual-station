"""Render source-linked Chinese P1 report from already sealed real results; no fits."""
import csv,json,collections,hashlib,shutil
from pathlib import Path
P=Path(__file__).parents[1];R=P.parent
run=next(x for x in (P/"runs").iterdir() if x.name.startswith("PUBLIC_DATA_EXPLORATORY_P1-"))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def read(p):
 with p.open(encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def n(x):return float(x)
met=read(run/"P1_OVERALL_METRICS.csv");comp=read(run/"P1_MODEL_COMPARISON.csv");dec=read(run/"P1_MSE_DECOMPOSITION.csv");season=read(run/"P1_SEASONAL_BIAS.csv");alpha=read(run/"P1_ALPHA_SELECTION.csv");con=read(P/"P1_YEAR_CONCENTRATION.csv");details=jl(run/"comparison_details.json");manifest=jl(run/"manifest.json");sel=jl(P/"NEW_BASIN_SELECTION_FROZEN.json")
for f in run.glob("P1_*.csv"):shutil.copyfile(f,P/f.name)
# Deliver separate original-cohort and frozen-new-cohort result views, without altering run.
for cohort in ["EXPLORATORY_ORIGINAL_3","FROZEN_NEW_BASINS"]:
 dest=P/"reports"/cohort;dest.mkdir(exist_ok=True)
 for filename in ["P1_OVERALL_METRICS.csv","P1_YEARLY_METRICS.csv","P1_SEASONAL_BIAS.csv","P1_MODEL_COMPARISON.csv"]:
  rows=[r for r in read(run/filename) if r["cohort"]==cohort]
  with (dest/filename).open("x",encoding="utf-8",newline="") as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def mrow(ex,g,mid):return next(r for r in met if r["experiment"]==ex and int(r["gauge_id"])==g and r["model_id"]==mid)
C="CONSECUTIVE_10Y";S="SPARSE_10Y_PUBLIC_SUBSAMPLING"
lines=["# P1：季节表达与气象增量解耦实测结果",
"所有新结果标记 PUBLIC_DATA_EXPLORATORY_P1。这是看过原三站结果后设计的探索性消融；新增六站在评分前冻结，但共享年代、部分气候和河网大区，不能当作完全独立的确认性重复。未访问锡尔河教师 Q，锡尔河主线继续 NOT_GRANTED。",
f"已完成 run：{run.name}。使用公开 LamaH-CE v1.0（DOI 10.5281/zenodo.5153305）原始日尺度 Q 与 A 类完整上游流域 ERA5-Land P/T。Q 是水文机构观测；P/T 为再分析，不是气象站实测。按原规则保留 qceq/qcol 诊断，要求每个日历月全部日期的 Q/P/T 有效且 Q 的 ckhs=1，不插值。",
"## 已执行规模与验证",
"原三站 ID2/6/9：新增 H0、C0+PT 各60个外层拟合，共120次，新增1440条 OOF；原C0/E3n共1440条仅按哈希只读引用。新增六站：两套十年方案全部四模型，共480个外层拟合、5760条新OOF。合计600个新外层拟合、13500个新内层拟合、7200条新预测；四模型共同评价8640条模型—月份记录。独立源月观测仅1728条，两个时间方案重叠、四模型同月记录均不增加独立样本量。",
"180个外层 LOYO 折，每折108月训练、12月测试；720条折—模型结果含120条旧参照。没有数值拟合失败或丢折。开始时曾因读取 FoldSpec 哈希属性的调度错误退出，尚未拟合（0次）；修正为读取既有 record 字段后执行一次完整数值实验。原错误及代码身份保留在 RUN_ATTEMPTS.jsonl 与失败 staging，不按成绩重试。",
"10/10合成单元与防泄漏测试通过，包括 H0参数恢复、十二月气候态保持、月份截距不受惩罚、与联合月哑变量Ridge的等价性、折内标准化、内层重拟合、留出标签不变性及合法训练标签敏感性。",
"独立复核从公共日数据重聚合1728个月，逐条重算8640个预测及总体NSE/KGE，检查所有180个外层折、13500次内层训练身份、旧OOF精确一致和180组H0/E3n季节系数等价性。原公开交付封存206/206文件与新run的17/17封存文件通过。见 REAL_RUN_VERIFICATION.json。",
"## A. 原 E3n 落后 C0 有多少来自季节表达？",
"使用精确的样本内误差恒等分解：MSE(E3n)−MSE(C0) = [MSE(H0)−MSE(C0)] + [MSE(E3n)−MSE(H0)]。这是这些固定样本上的消融误差分解，不是总体因果归因百分比。"]
for r in dec:
 if r["experiment"]==C and r["cohort"]=="EXPLORATORY_ORIGINAL_3":
  lines.append(f'- ID{r["gauge_id"]}：原差距 {n(r["E3n_minus_C0_MSE"]):.6f} = 季节结构代价 {n(r["H0_minus_C0_structure_MSE"]):.6f} + 气象变化 {n(r["E3n_minus_H0_weather_MSE"]):.6f} (m³/s)²；结构项是净差距的 {100*n(r["structure_signed_fraction_of_gap"]):.1f}%。')
lines+=["三个比例超过100%，表示气象部分抵消了更大的谐波结构代价，并非不合理的归因上限。180个外层折中，H0与E3n的截距/正余弦系数在浮点精度内一致：逐月中心化的气象异常与日历月份函数正交。该检查加强了结构对照解释，但不能据此推断所有流域都应使用十二个月参数。",
"## B. 完全相同的十二月气候态下，P/T 是否有增量？",
"C0+PT先固定训练折十二个月 Q 均值，只对标准化 P/T 异常的两个系数做 Ridge。无新增截距、无月份均值惩罚。每个外层与内层都重新计算训练气象月均值和样本标准差。主分析使用原始预测；负值截断仅为预定次分析。"]
for ex,name in [(C,"连续1990–1999"),(S,"固定稀疏十年")]:
 lines.append(f"### 原三站：{name}")
 for g in [2,6,9]:
  c=mrow(ex,g,"C0");p=mrow(ex,g,"C0+PT");h=mrow(ex,g,"H0");e=mrow(ex,g,"E3n")
  lines.append(f'- ID{g}：NSE C0/H0/E3n/C0+PT = {n(c["NSE"]):.6f}/{n(h["NSE"]):.6f}/{n(e["NSE"]):.6f}/{n(p["NSE"]):.6f}；C0+PT KGE={n(p["KGE"]):.6f}；相对C0的MSE技能={100*n(p["skill_vs_C0"]):.2f}%；去季节异常相关={n(p["anomaly_correlation"]):.3f}。')
lines+=["原三站两方案6个比较均有正的平均MSE技能。该结果否定了“原E3n落后C0即可认定P/T无贡献”的解释；没有证明P/T已充分恢复全部年际水文异常。去季节异常统一扣除当前外层训练 C0 月均值，未扣除测试期气候态；异常NSE相对零基准恰等于相对C0的MSE技能。C0的预测异常恒为零，相关系数为N/A（CONSTANT_PREDICTED_ANOMALY）。",
"## C. 气象贡献是否集中于少数年份？",
"每个年份等权。给出年份块bootstrap 999次、逐年配对差异及删除一年后的平均改善；这是对固定OOF损失的jackknife，不是删掉该年后重新训练整个模型。按年重采样/符号翻转的独立、交换性假设尚未得到保证；未校正描述性p值不能作为确认性发现。"]
for ex,g in [(C,2),(C,818),(S,255),(S,378)]:
 key=f"{ex}|{g}|C0+PT_vs_C0";d=details[key];z=next(r for r in con if r["experiment"]==ex and int(r["gauge_id"])==g and r["comparison"]=="C0+PT_vs_C0")
 lines.append(f'- {ex} ID{g}：改善{int(round(d["fraction_years_improved"]*10))}/10年；最大贡献年{z["year_of_largest_improvement"]}占净改善 {100*n(z["largest_positive_year_signed_share"]):.1f}%；删任一年仍改善={d["jackknife"]["all_deletions_positive"]}；平均年度MSE改善bootstrap95%区间[{n(z["bootstrap95_low"]):.6f}, {n(z["bootstrap95_high"]):.6f}]。')
lines+=["ID818连续方案的1.05%平均技能依赖1993，去掉该年会反转。ID255稀疏方案仅5/10年改善，1996贡献98.8%的净改善，bootstrap区间跨零。ID2连续方案虽9/10年改善且删除任一年仍正，bootstrap区间仍跨零，不能仅凭年度胜率宣布稳定确认。",
"## D. 新流域是否重复原负结果？",
"选择规则先于任何新站模型成绩：六个指定官方河网区域×面积/积雪区间；按距目标面积的绝对log距离排序、ID破同值，再按与原实验一致的完整日数据规则准入。所有首选均通过，无按分数换站。新增六站彼此及与原三站之间无上下游嵌套；原三站内部ID2和ID6均处于ID9上游，明确不能作为三个独立空间重复；官方跨流域调水表未发现将选定流域上游控制区互相连接的记录。这不是对未知人工连通的完整物理认证。"]
for x in sel["selected_metadata"]:
 g=x["gauge_id"];c=mrow(C,g,"C0");h=mrow(C,g,"H0");e=mrow(C,g,"E3n");p=mrow(C,g,"C0+PT");sp=mrow(S,g,"C0+PT")
 lines.append(f'- ID{g} {x["name"]}，{x["region"]}，面积{x["area_calc_km2"]}km²、官方frac_snow={x["frac_snow"]}：连续方案 NSE C0/H0/E3n/C0+PT={n(c["NSE"]):.4f}/{n(h["NSE"]):.4f}/{n(e["NSE"]):.4f}/{n(p["NSE"]):.4f}；C0+PT连续/稀疏MSE技能={100*n(p["skill_vs_C0"]):.2f}%/{100*n(sp["skill_vs_C0"]):.2f}%。')
lines+=["原负结果只在新增雪影响较高的ID533、818、255重复：谐波H0明显弱于C0，E3n略有补偿仍落后C0；三站两方案均如此。ID611、460、378两方案中E3n均超过C0，说明原结论不能推广到所有流域。十二月固定季节结构后，新增六站两方案12个C0+PT比较平均技能全为正；其中10/12的年度bootstrap区间位于零以上，但不作跨独立流域显著性推断。",
"ID611/460连续方案的C0 NSE分别为−0.0073/−0.1442；虽然气象增益较大，C0+PT最终NSE也只有0.3079/0.0990。ID378连续方案C0+PT NSE=0.0922。不能只展示ID533的0.9082而隐藏弱结果。ID460/378中E3n总体强于C0+PT，说明弱季节流域中十二个独立月均值也可能估计噪声更大，C0+PT不保证是最佳模型。",
"## 季节偏差、alpha与边界",
"原三站连续方案中，H0与E3n均重复3–4月高估、5–6月低估、8月高估及12月低估；C0+PT消除了大部分系统性季节形状偏差，但去偏不等于所有月份RMSE下降。C0按月汇总OOF偏差接近零是完整平衡LOYO代数性质，不表示其逐年月份均准确。"]
for g in [2,6,9]:
 for per,label in [("MAY_JUN","5–6月"),("M08","8月"),("DJF","冬季DJF")]:
  rs={r["model_id"]:r for r in season if r["experiment"]==C and int(r["gauge_id"])==g and r["period"]==per}
  lines.append(f'- ID{g} {label}：RMSE C0/H0/E3n/C0+PT={n(rs["C0"]["RMSE"]):.4f}/{n(rs["H0"]["RMSE"]):.4f}/{n(rs["E3n"]["RMSE"]):.4f}/{n(rs["C0+PT"]["RMSE"]):.4f} m³/s。')
lines+=["ID2的5–6月C0+PT稍差于C0，原三站DJF的C0+PT也均略差于C0；气象总体改善不能替代季节/年份局部失败检查。",
"原三站E3n和C0+PT各60/60外层折选择100，但各自仅10/60折的内层最小均值MSE对应100，其余50折best_alpha=10。选择100主要符合预设one-SE偏向强正则规则，不能把“最终选择上边界”直接当成未找到最优值的证明。新增六站E3n119/120选100（1折10）；C0+PT114/120选100（6折10）。网格没有扩大。",
"ID533中H0/E3n连续方案分别有22/21个负预测，稀疏方案11/17个；C0/C0+PT没有负预测。截断可改善H0/E3n，但其NSE仍明显低于该站C0；原始值保持主分析，没有用截断替换首次主结果。",
"## E. 下一轮P2的具体方向（本轮未实施）",
"优先在固定C0+PT季节基线下预注册少量前期储存/融雪候选，而非扩大神经网络或枚举高分特征。理由：新流域验证已经显示“P/T完全无增量”不成立；雪影响较高站点的当月P/T异常技能较小，5–6月和冬季仍有局部失败，表明前期水分/积雪储存是值得检验的候选机制，尚未证明机制。",
"建议P2只比较：P2-L1（增加上月累计降水，必须从实际前一月公开日期读取，不能用稀疏样本上一行替代）、P2-SNOW（预先固定寒季累计降水与温度相关融雪指标及一个有限季节交互版本）。冷季边界/温度阈值在下一批未评分数据前固定，气候态/标准化及参数全部折内拟合，不再依据当前九站测试成绩挑窗口。与C0+PT使用相同共同支持集，以年度MSE技能、去季节异常、逐年稳健性为主要判据。",
"扩充流域是外部验证的必要并行工作：本轮只有两个宏观水系大区且年代重叠；下一轮应冻结更多非嵌套支流/独立水系或未评分年代，并按网络/气候依赖分组报告。当前证据足以推进小规模滞后/融雪实验，尚不足以宣布普适的融雪改进。",
"## 文件与复现",
"协议 P1_PROTOCOL.json；选择 NEW_BASIN_SELECTION_FROZEN.json；代码 code/p1_models.py；运行 code/run_p1.py；独立核验 code/verify_p1.py；真实run内含全部OOF、参数、内层CV记录、fit_events、折、快照、代码哈希与SHA256SUMS。",
"根目录四份P1结果CSV与run副本一致，reports/EXPLORATORY_ORIGINAL_3和reports/FROZEN_NEW_BASINS提供分组视图。P1_YEAR_CONCENTRATION.csv提供最大贡献年、年度bootstrap与jackknife范围。P1_FROZEN_BASELINE_DIAGNOSIS.md与evidence保留原OOF诊断。",
"来源许可延续首次合法公开副本：Zenodo页面CC BY-SA4.0与API/包内CC BY4.0记录不一致，采用较严格CC BY-SA4.0要求，保留原作者、官方参考文献和来源声明；未对外发布数据。Q单位m³/s、P为mm/月、T为°C，均按官方定义，无教师流量单位假设混入。",
"所有推断仅是公开流域历史月尺度留年重建，不是锡尔河性能、无资料流域预测、实时预报或物理损失机制识别。"]
(P/"P1_SCIENTIFIC_REPORT_ZH.md").write_text("\n\n".join(lines),encoding="utf-8")
readme=f"""# PUBLIC_DATA_EXPLORATORY_P1
实际完成四模型真实结构消融，已封存run：
{run.name}

先读 P1_SCIENTIFIC_REPORT_ZH.md。原三站与新增六站结果分别在reports两个子目录。
本轮7200条新真实OOF，另引用旧1440条；600新外层拟合、13500内层拟合。
不访问教师Q；无锡尔河真实结果；没有实施P2。

只读核验（不重新拟合、不改已有run）：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\code\\verify_p1.py'
~~~
如用户以后明确要求重新复现，以下命令会创建另一个run，绝不覆盖原run：
~~~powershell
& 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe' -B '{P}\\code\\run_p1.py'
~~~
不要重新执行prepare_p1.py、select_candidates.py或freeze_data.py来改变已冻结方案。
SHA256SUMS.txt覆盖P1交付，真实run另有独立SHA256SUMS。RUN_ATTEMPTS保留最初零拟合调度失败。
"""
(P/"README.md").write_text(readme,encoding="utf-8")
shutil.copyfile(R/"reports/ATTRIBUTION_ORIGINAL.txt",P/"reports/ATTRIBUTION_ORIGINAL.txt")
shutil.copyfile(R/"reports/SOURCE_AND_LICENSE.md",P/"reports/SOURCE_AND_LICENSE_ORIGINAL.md")
summary={"label":"PUBLIC_DATA_EXPLORATORY_P1","run_id":run.name,"new_outer_real_fits":600,"new_inner_real_fits":13500,"new_real_OOF":7200,"old_OOF_referenced":1440,"four_model_records":8640,"unique_source_months":1728,"new_cohort_gauges":sel["selected_new_ids"],"new_C0PT_mean_skill_positive":12,"new_C0PT_comparisons":12,"SYRDARYA_REAL_TRAINED_MODELS":0,"SYRDARYA_AUTHORIZATION":"NOT_GRANTED","P2_implemented":False}
(P/"P1_COMPLETION_STATUS.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
print(json.dumps(summary,indent=2))

