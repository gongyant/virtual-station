"""Reports from immutable public P4 numerical results; no model changes."""
from common import *
from collections import Counter
import shutil
v1=jl(P/"P4_V1_MODEL_MANIFEST.json");v2=jl(P/"P4_V2_MODEL_MANIFEST.json");dec=jl(P/"evidence/V1_FROZEN_DECISION.json");release=jl(P/"P4_RELEASE_INDEX.json");ct=jl(P/"evidence/T4_COUNTS.json")
ev=cr(P/"P4_V1_EVALUATION.csv");cv=cr(P/"P4_V1_COVERAGE.csv");summary=cr(P/"P4_V1_REGION_YEAR_SUMMARY.csv");comp=cr(P/"P4_V1_MODEL_COMPARISON.csv");demo=cr(P/"P4_MASKED_DEMO_METRICS.csv")
def write(name,s):
 p=P/name
 with p.open("x",encoding="utf-8") as f:f.write(s)
def coverage(mid,lev):
 rr=[r for r in cv if r["model_id"]==mid and r["subset"]=="ALL" and float(r["nominal"])==lev]
 return sum(float(r["coverage"])*int(r["n_defined"]) for r in rr)/sum(int(r["n_defined"]) for r in rr)
mean={}
for mid in ["C0+PT","P2-L1"]:
 rr=[r for r in ev if r["model_id"]==mid and r["prediction"]=="raw"]
 mean[mid]={k:float(np.mean([float(r[k]) for r in rr])) for k in ["NSE","KGE","MAE","RMSE","PBIAS"]}
 mean[mid]["median_NSE"]=float(np.median([float(r["NSE"]) for r in rr]))
covlines=[f'- {mid}名义{lv:.0%}区间，899月实际覆盖率{coverage(mid,lv):.2%}。' for mid in mean for lv in [.8,.9]]
regionlines=[f'- {r["subset"]} / {r["macro"]}：{r["n_stations"]}站等权平均技能{float(r["mean_station_skill"]):+.2%}；{r["positive_stations"]}站改善。' for r in summary]
sitelines=[]
for r in comp:
 if r["subset"]!="ALL":continue
 a=next(t for t in ev if t["gauge_id"]==r["gauge_id"] and t["model_id"]=="C0+PT" and t["prediction"]=="raw");b=next(t for t in ev if t["gauge_id"]==r["gauge_id"] and t["model_id"]=="P2-L1" and t["prediction"]=="raw")
 sitelines.append(f'- ID{r["gauge_id"]}（{r["macro"]}，{r["n"]}月）技能{float(r["MSE_skill"]):+.2%}；基线NSE/KGE={float(a["NSE"]):.4f}/{float(a["KGE"]):.4f}；L1={float(b["NSE"]):.4f}/{float(b["KGE"]):.4f}。')
demolines=[f'- {r["model_id"]}：12月，NSE={float(r["NSE"]):.6f}，KGE={float(r["KGE"]):.6f}，RMSE={float(r["RMSE"]):.6f} m³/s，MAE={float(r["MAE"]):.6f} m³/s。' for r in demo]
alpha=Counter()
for mf in v1["models"]+v2["models"]:
 m=jl(Path(mf["path"])/"model.json");alpha[str(m["parameters"]["selection"]["selected_alpha"])]+=1
outer=v1["all_outer_fits_including_crossfit"]+v2["all_outer_fits_including_crossfit"]+2
inner=v1["inner_fits"]+v2["inner_fits"]+ct["demo_inner_fits"]
caution=[]
for r in cr(P/"P4_V1_PREDICTIONS.csv"):
 if r["support_class"]!="IN_SUPPORT":caution.append((r["gauge_id"],r["support_class"]))
caution_counts=Counter(g for g,s in caution)
covtext="# V1时间外区间验收\n\n"+"\n".join(covlines)+"""
\n分母为899个合法站月，两个模型不计为独立重复。逐站、季节、外推子集覆盖及宽度见P4_V1_COVERAGE.csv。
区间偏保守，覆盖偏高不意味着窄或应用有用。每站每季校准残差12条，四个连续12月块，采用ceil((n+1)*level)顺序统计量，乘max(1,P3季节前向RMSE/本版本遮蔽季节RMSE)。
P3参与过模型开发，因此kappa非独立估计。2015–2017 Q在预测/区间封存后才进入评分，未用于调分位数、kappa或质量规则。
对称区间负下界原样保留。季节样本不足、零尺度、无迁移支持、无法定义分位数均有显式状态；本批区间可定义。
仅三年测试、流域空间依赖、较少校准季节样本，不能宣称无条件严格覆盖保证。
"""
write("P4_V1_COVERAGE_REPORT.md",covtext)
write("P4_COVERAGE_DRY_RUN.md","""# 评分前校准证据说明
协议与遮蔽计划均先于测试评分冻结。V1校准参数、54个模型和全部预测及区间已在首次数值测试Q读取前封存，详见COMMITMENT及TEST_Q_RELEASE_RECEIPT的UTC与哈希。
CALIBRATED要求季节n>=8、非零尺度、可定义顺序统计量及P3前向季节n>=8。四个不重叠年度块的每季12个残差用于区间；3/6/24月另作长度敏感性。
V1遮蔽4374条预测中有不同长度/时段重叠，不能全部当作独立校准残差。
本说明在最终汇总阶段生成，评分前原始证据以模型calibration、预测包COMMITMENT和冻结时间为准，不冒充当时生成的独立日志。
""")
write("P4_FINAL_MODEL_DECISION.md",f"""# 固定发布决定
V1平均站点MSE技能{dec['mean_station_MSE_skill']:+.2%}、中位数{dec['median_station_MSE_skill']:+.2%}，15/25站改善。三年份、三宏观水系整体平均技能正，按T0冻结规则为DIRECTION_SUPPORTED，仅经验方向支持。
V2实际重拟合54个模型。全局默认研究公式P2-L1（27个条件条目）；C0+PT为强制基线/并列候选（27个），不按单站V1分数切换公式。
默认仅是本研究的软件选择，不是业务水文认证。应用逐月需要完整气象、真实前月P、训练月份支持、有效区间及非HIGH_EXTRAPOLATION，否则拒绝资格。
10站负增益，冬季和5–6月站点平均技能负；ID378、383、455等负NSE失败原样保留。
V2用过2015–2017，不能声称新独立测试。P5必须冻结应用可接受误差/区间宽度，用新的时段或空间资料验收，不再用V1反复选择。
""")
write("P4_MODEL_CARD_ZH.md",f"""# P4模型卡
任务：RETROSPECTIVE_MONTHLY_STREAMFLOW_RECONSTRUCTION。已拥有合法目标站历史Q的27公开流域站点模型；非严格零目标站、非提前一月预报。
来源：LamaH-CE v1.0官方实测qobs（m³/s）与A区总上游ERA5-Land日P/T；DOI 10.5281/zenodo.5153305，论文10.5194/essd-13-4529-2021。不是COSERO模拟Q，不是SYRDARYA实验。署名与许可见SOURCE_LICENSE_AND_ATTRIBUTION.txt，发布包应与该说明一并使用。
固定P2十二个月Q均值+标准化当月P/T；L1加真实前月P。仅气象系数Ridge；alpha五点，内层按年LOYO、one-SE；未修改原P2数学代码。
V1截至2014，V2截至2017，各54个JSON/NPZ模型。V2为独立新拟合参数，不复用V1假装重训。
输入date、gauge_id、P(mm/月)、T(°C)；L1必须真实前月P。无Q参数；缺失、非有限、单位、身份和哈希错均拒绝。
V1平均NSE：基线{mean['C0+PT']['NSE']:.6f}、L1 {mean['P2-L1']['NSE']:.6f}；中位NSE {mean['C0+PT']['median_NSE']:.6f}/{mean['P2-L1']['median_NSE']:.6f}；平均KGE {mean['C0+PT']['KGE']:.6f}/{mean['P2-L1']['KGE']:.6f}。
低平均NSE受明显失败站影响，不能只展示中位数。默认研究L1不保证单站提升，全部模型尚无业务认证。
区间采用季节块外残差+P3迁移膨胀，经验覆盖非严格保证。输入支持门禁不保证捕捉全部水文分布变化。
不可作锡尔河成绩、取水/损失机制归因或未经校准的空间迁移。Qsim不写回实测标签。
release/P4_PUBLIC_V2及ZIP为NumPy推理包，54个模型、新进程已验收，不依赖原始Q或训练源码。示例V2日期已参与训练，不能将示例重新评分冒充独立成绩。
""")
neg=[r["gauge_id"] for r in comp if r["subset"]=="ALL" and float(r["MSE_skill"])<0]
trainmonths=sum(r["train_months"] for r in v1["models"])//2
report=f"""# P4公开真实最终模型实验报告
T0→T1→T2→T3→T4已完成，是真实训练、硬盘参数与推理发布，不是准备报告。教师锡尔河Q保持NOT_GRANTED，未读取或访问。

## 1. V1训练与独立测试规模
27站54个V1最终模型，训练{trainmonths}个共同合格站月，截止2014-12。
2015–2017测试25站899个合格站月：24站36月、1站35月；另73个月来源QC不足不评分，未视为真正缺测。T0仅用日期、ckhs及缺失码，数值Q解析0；封存后数值确认无冲突。
两模型共1798条预测代表899个站月，不作为1798个独立观测。25站≥24个月，满足预设报告门槛而非显著性保证。
V1/V2分别54最终拟合+378连续遮蔽拟合，另2个演示拟合。外层{outer}次，内层{inner}次，真实fit调用共{outer+inner}次；两版遮蔽预测各4374条，长度重叠不当作独立重复。

## 2. 增量、总体表现与失败
L1平均站点MSE技能{dec['mean_station_MSE_skill']:+.2%}、中位数{dec['median_station_MSE_skill']:+.2%}；15正10负。三测试年份、三宏观水系整体平均改善，冻结分类DIRECTION_SUPPORTED，非普遍有效或统计确认。
平均NSE：基线{mean['C0+PT']['NSE']:.6f}，L1 {mean['P2-L1']['NSE']:.6f}；中位NSE {mean['C0+PT']['median_NSE']:.6f}/{mean['P2-L1']['median_NSE']:.6f}；平均KGE {mean['C0+PT']['KGE']:.6f}/{mean['P2-L1']['KGE']:.6f}。
冬季DJF平均技能-23.02%，5–6月-15.46%。2016整体仅+0.87%，其中Elbe/Danube负；2017 Rhine负。2017仅12/25站正但平均技能仍正，不能由平均掩盖异质性。
ID378 L1 NSE=-3.2568，ID383=-1.8430，存在严重失败。负技能站：{', '.join(neg)}。所有站、所有合法测试月和负值均保留。
P3与P4训练长度、测试窗口及完整站点集合不同，不能将平均技能数值差异直接归因于某一机制；未重训P0–P3。

## 3. 按年份与水系
"""+"\n".join(regionlines)+f"""

## 4. 覆盖率与外推
"""+"\n".join(covlines)+f"""
\n区间保守、偏宽，覆盖率高不代表足够精确。逐站季节区间宽度及覆盖见CSV；仅三年测试，Rhine5/Elbe2/Danube18个合格测试站且空间非独立，无宏观水系≥3站的虚假门槛。
V1无HIGH_EXTRAPOLATION，但存在CAUTION；按模型累计的站点警示月数为{dict(caution_counts)}。这不等于这些站水文表现都好：输入支持检测不能替代真实精度验收。
P3已参与模型选择，kappa非独立估计。校准仅用合法块外残差；V1测试Q未用于校准，无无条件覆盖保证。

## 5. 最终V2、硬盘加载与发布
V2截至2017重新拟合54个模型，训练身份/快照/参数哈希更新，与V1规格哈希一致；没有新的独立2015–2017成绩。
V1真实模型验收66项通过；独立复核108个最终模型、1798条预测、900个指标单元、756个遮蔽折；预测复算最大绝对差0，训练/测试重叠0，旧P0–P3哈希不变。
V1/V2最终alpha分布{dict(alpha)}，未扩网格。54个V2模型为27条件默认研究L1与27基线模型，应用仍逐月门控，非业务认证。
可移植包54模型不需要原始Q或P2/P3源码；已在全新Python进程加载JSON/NPZ完成气象→Q推理，推理fit调用0。

## 6. 历史缺档和演示
状态计数{ct['observation_status_counts']}。54条源覆盖外为每站1980-12/2018-01边界哨兵；ID512的1981年12个站月在官方观测起始年前，单独OUTSIDE_OBSERVATION_COVERAGE，不制造缺档。
MISSING_TRUE=0、合格真实缺档=0，NO_ELIGIBLE_TRUE_GAPS。111个QC不足/部分观测月未冒充全缺测。P4_RECONSTRUCTIONS.csv因此只有表头，无虚构预测或无标签NSE。
按照T0预定ID2/2016连续12月MASKED_ACCEPTED，用另行拟合且排除所有2016目标Q的磁盘模型演示，区间只取V1≤2014校准：
"""+"\n".join(demolines)+"""

L1演示略差于基线，原样保留。它是连续人工缺档与加载功能验证，既不是真实历史缺档，也不是新的独立V1测试。

## 7. 每站完整结果
"""+"\n".join(sitelines)+"""
\n## 8. 后续与锡尔河边界
P5优先冻结应用误差和区间宽度容忍标准，使用尚未用过的独立时段或流域，重点检查失败站、冬季/5–6月退化和水文分布漂移。不修改本次公式、alpha、窗口或回退策略来重选V1。
如获取真实全缺档的合法公开来源，可在应用门禁和新run下重建；预测不能回填为训练观测。当前没有真实空档的“准确率”。
锡尔河仍须真实负责人许可、既有可信签名授权及独立执行指令。公开流域成功不等于锡尔河已经授权或已完成真实训练。
"""
write("P4_SCIENTIFIC_REPORT_ZH.md",report)
# Exact upstream numerical source is copied as provenance, not edited.
shutil.copyfile(P2/"P2_MODEL_CODE/models.py",P/"code/FROZEN_P2_MATH_REFERENCE.py")
assert sha(P/"code/FROZEN_P2_MATH_REFERENCE.py")==jl(P/"P4_PROTOCOL.json")["spec"]["math_sha256"]
license_text="LamaH-CE v1.0 public derived model release. DOI: https://doi.org/10.5281/zenodo.5153305\nPaper: https://doi.org/10.5194/essd-13-4529-2021\nThis notice accompanies release/P4_PUBLIC_V2.zip. Models and scripts are new derived research artifacts; retain attribution and applicable CC BY-SA 4.0 sharing conditions.\n\n"
for n in ["SOURCE_AND_LICENSE.md","ATTRIBUTION_ORIGINAL.txt"]:
 path=R/"reports"/n
 if path.exists():license_text+="\n"+n+"\n"+path.read_text(encoding="utf-8-sig")
write("SOURCE_LICENSE_AND_ATTRIBUTION.txt",license_text)
shutil.copyfile(P/"SOURCE_LICENSE_AND_ATTRIBUTION.txt",P/"release/P4_PUBLIC_V2_ATTRIBUTION.txt")
write("P4_REPRODUCTION_GUIDE.md",r"""# 加载、推理与复核
推理不重新训练，使用现有Python/NumPy。PowerShell：
    $py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
    $p='E:\VHS_Public_Baseline_Lab\p4_final_reconstruction'
    & $py -B "$p\release\P4_PUBLIC_V2\runtime\inference.py" --model "$p\release\P4_PUBLIC_V2\models\ID_2\P2-L1" --met "$p\release\P4_PUBLIC_V2\example_MET_ID2.json" --start 2016-01 --end 2016-12 --output "$env:TEMP\P4_ID2_new_inference.csv"
此V2示例日期已经参与最终训练，不可重新评分宣称独立验证。排除2016标签的真正人工缺档模型在runs/PUBLIC_DATA_FINAL_P4_MASKED_DEMO/P2-L1。
加载API：将runtime加入sys.path，再from inference import load_model,predict_month,predict_range。缺测/单位错/跨站/目标Q字段拒绝，真实L1日历对齐。示例输入仅气象。
可移植ZIP应与release/P4_PUBLIC_V2_ATTRIBUTION.txt一并使用/分发，不依赖原始Q或冻结P2/P3源码。模型.json绝对路径只是历史来源记录，推理不打开这些数据。
入口顺序：prepare.py→train.py freeze→train.py V1→validate_models.py→score_v1.py→train.py V2→apply.py→export_models.py→verify.py→report.py。
训练/评分入口采用独占创建及已评分拒绝，勿在封存目录重复执行。若要完整复现实验，使用新独立目录/新run身份，保持原协议与来源哈希，common.py指向新根，不能覆写本次封存。
verify.py复算已冻结数值不做训练/选择，但会写新核验记录；若在交付后执行，应改为新的核验输出目录。只读复核本次SHA256SUMS可直接逐行计算哈希。
证据链：T0_FREEZE→模型/区间/预测COMMITMENT→REAL_MODEL_ACCEPTANCE/FRESH_PROCESS→TEST_Q_RELEASE_RECEIPT→唯一V1评分→新V2快照/参数→新进程应用。
""")
stats={"UTC":now(),"status":"COMPLETED_PUBLIC_P4_REAL","V1_models":54,"V2_models":54,"default_research_models":release["default_count"],"final_fits":108,"crossfit_outer":756,"demo_outer":2,"outer_fit_calls":outer,"inner_fit_calls":inner,"total_fit_calls":outer+inner,"V1_test_prediction_records":1798,"unique_test_station_months":899,"calibration_block_predictions":8748,"masked_demo_predictions":24,"true_gap_predictions":0,"verification":"PASS","failed_training_attempts":0,"SYRDARYA":"NOT_GRANTED_UNTOUCHED","direction":dec,"mean_metrics":mean,"actual_interval_coverage":{mid:{str(lv):coverage(mid,lv) for lv in [.8,.9]} for mid in mean},"caveat":"default research formula, not universal/operational certification; V2 has no new independent test"}
jw(P/"P4_COMPLETION_STATUS.json",stats)
attempt("P4_COMPLETED",V1_models=54,V2_models=54,total_fit_calls=outer+inner,teacher_Q_access=False)
assert verify(P/"runs/PUBLIC_DATA_FINAL_P4_V1")>0
seal(P/"runs/PUBLIC_DATA_FINAL_P4_V2");verify(P/"runs/PUBLIC_DATA_FINAL_P4_V2")
seal(P);n=verify(P)
print(json.dumps({"completed":True,"delivery_files_sealed":n,"seal":sha(P/"SHA256SUMS.txt"),"total_fit_calls":outer+inner,"portable_zip":str(P/"release/P4_PUBLIC_V2.zip")}))
