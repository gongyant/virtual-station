from pathlib import Path
import csv,json,hashlib,statistics
from collections import Counter
from datetime import datetime,timezone
P=Path(r"E:\VHS_Public_Baseline_Lab\p5_robustness_and_external_validation")
R=P.parent;P4=R/"p4_final_reconstruction"
def read(n):
 with (P/n).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def jl(p):return json.loads(p.read_text(encoding="utf-8-sig"))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,s):
 with (P/n).open("x",encoding="utf-8") as f:f.write(s)
def jw(n,x):write(n,json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False))
def cw(n,rr):
 with (P/n).open("x",encoding="utf-8",newline="") as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
cmp=read("P5_SHRINK_COMPARISON.csv");fail=read("P5_FAILURE_DIAGNOSTICS.csv");unc=read("P5_UNCERTAINTY_DIAGNOSTICS.csv")
stat={}
for mid in ["P2-L1","P5-L1-SHRINK"]:
 rr=[r for r in cmp if r["candidate"]==mid and r["outer_test_start"]=="ALL"]
 stat[mid]={"mean_skill_vs_C0PT":statistics.mean(float(r["skill_vs_C0PT"]) for r in rr),"mean_skill_vs_L1":statistics.mean(float(r["skill_vs_L1"]) for r in rr),"positive_vs_C0PT":sum(float(r["skill_vs_C0PT"])>0 for r in rr),"positive_vs_L1":sum(float(r["skill_vs_L1"])>0 for r in rr)}
sel=jl(P/"runs/P5_SHRINK_BLOCKED_V1/prediction_bundle/WEIGHT_SELECTION.json")
weights=dict(Counter(str(r["selected_weight"]) for r in sel))
cross=read("P5_EXTERNAL_STATION_CROSSWALK.csv")
meta=read("external_metadata/extracted/streamflow_gauges/estreams_gauging_stations.csv")
providers={r["provider_id"]:r for r in read("external_metadata/extracted/streamflow_gauges/estreams_streamflow_catalogue.csv")}
by={r["basin_id"]:r for r in meta};ex=[]
for r in cross:
 m=by[r["candidate_basins"]];p=providers[m["gauge_provider"]]
 ex.append({**r,"external_name":m["gauge_name"],"external_river":m["river"],"longitude_WGS84":m["lon"],"latitude_WGS84":m["lat"],"official_area_km2":m["area_official"],"catalogue_QC":m["gauge_flag"],"new_Q_units":"NOT_VERIFIED_AT_NUMERIC_SOURCE","new_Q_time_basis":"NOT_VERIFIED_AT_NUMERIC_SOURCE","daily_definition_missing_codes":"NOT_VERIFIED_AT_NUMERIC_SOURCE","identity_overlap":"SAME_EXISTING_LAMAH_STATION_NOT_NEW_BASIN","provider_website":p["website"]})
cw("P5_EXTERNAL_CANDIDATES.csv",ex)
poor=[r["gauge_id"] for r in fail if r["model_id"]=="P2-L1" and float(r["NSE"])<0]
unstable=[r["gauge_id"] for r in fail if r["model_id"]=="P2-L1" and int(r["negative_NSE_years"])>0]
lines=[]
for g in [378,383,455,533,818,10,142]:
 r=next(r for r in fail if int(r["gauge_id"])==g and r["model_id"]=="P2-L1")
 lines.append(f'- ID{g}：NSE={float(r["NSE"]):.4f}、KGE={float(r["KGE"]):.4f}、PBIAS={float(r["PBIAS"]):+.1f}%；最大MSE年份{r["worst_MSE_year"]}；逐年NSE中位数{float(r["median_year_NSE"]):.4f}。')
cover=[]
for r in unc:
 if r["scope"]=="ALL_MONTHS_DESCRIPTIVE" and r["model_id"]=="P2-L1":
  cover.append(f'- 名义{float(r["nominal"]):.0%}：实际覆盖{float(r["coverage"]):.2%}，平均宽度{float(r["mean_width_m3s"]):.3f}m³/s，宽度/各站训练Q均值的站月平均比{float(r["mean_width_over_train_Qmean"]):.3f}，Interval Score={float(r["mean_interval_score"]):.3f}。')
accept=f"""# P5发布应用验收
54/54已保存P4-V2模型在54个新进程加载，输出648条2016年应用推理，fit调用0。此时期参与V2训练，明确不是新OOF。
直接公式与加载推理最大差0；缺真实前月、错误单位、错站号、目标Q字段拒绝。CLI支持显式单位，错误单位在写输出前拒绝。推理没有训练标签追加路径。
P4原始保存加载测试只读引用，不重新拟合。
负总体NSE站：{', '.join(poor)}。有负NSE年份的站：{', '.join(unstable)}。这是事后应用风险告知，不用来删站、切换模型或选权重。全部模型尚无业务精度认证。
611与688无合法V1测试Q，明确N/A，仍正常加载；不能虚构成绩。
真缺档仍0。图像回放原P4真正排除2016Q的ID2人工12月遮蔽模型；L1 NSE=0.872586，基线=0.882737。不把最终V2已训练月预测当作样本外。
"""
write("P5_P4_RELEASE_ACCEPTANCE.md",accept)
write("P5_APPLICATION_REPORT_ZH.md",accept+"\n## 重点站点\n"+"\n".join(lines)+"\n## 区间\n"+"\n".join(cover))
cw("P5_UNEVALUATED_STATIONS.csv",[{"gauge_id":g,"model_id":m,"V1_score_status":"N/A","reason":"NO_SOURCE_CHECKED_2015_2017_TEST_Q","application_loaded":True} for g in [611,688] for m in ["C0+PT","P2-L1"]])
external="""# 外部资料可行性
当前只取得新目录元数据，未取得独立数值Q或匹配的2018年后ERA5-Land流域驱动。本轮不生成外部冻结/评分文件。
从[EStreams v1.4官方记录](https://zenodo.org/records/17598150)取得约2.86MB README、许可附录及测站目录，官方MD5及本地SHA256均核验，未下载Q或大气象包。
27站全部按官方编号、国别匹配，并将LamaH EPSG3035转换至WGS84核对位置与官方上游面积；最大距离0.543km、面积差≤5%。这是强元数据身份，不自动授权拼接新Q。
24站AT_EHYD目录终点2021-12-31，许可字段“-”；[eHYD官方说明](https://ehyd.gv.at/assets/eHYD/pdf/eHYD_Allgemein.pdf)存在使用与再分发条件，不能套用其它OGD站的一般CC许可。
1站CH_CAMELS终点2020-12-31，目录CC-BY-4.0；[Swiss官方数据服务](https://www.bafu.admin.ch/en/hydrological-data-service-for-watercourses-and-lakes)需进一步核对所取得实际版本与日值/QC。
2站DE_BY终点2023-08-19、目录Redistribution allowed；[Stegen官方站页](https://m.hnd.bayern.de/pegel.php?pgnr=16602303)可核对编号，但即时水位/瞬时Q不等于多年日均Q。
新Q单位、日/月聚合定义、时区、QC、缺失码仍NOT_VERIFIED_AT_NUMERIC_SOURCE。目录终点不是本地实得Q。
EStreams v1.4采用E-OBS0.1°，P4采用LamaH ERA5-Land流域聚合，不能直接换驱动后宣称纯时间验证。没有取得同几何/生产方式的2018年后驱动。
[Caravan原始论文](https://www.nature.com/articles/s41597-023-01975-w)包含479个LamaH流域，因此重复下载不成为独立Q；[官方代码库](https://github.com/kratzert/Caravan)也要求核对来源许可与时间基准。MultiMet不自动延长观测Q。
下一步优先小规模核验同站后2017日Q及匹配ERA5-Land驱动，再在未评分前冻结；若换全新站并用其历史Q校准，属于新流域重复，不是零目标Q泛化。
"""
write("P5_EXTERNAL_DATA_FEASIBILITY.md",external)
science=f"""# P5公开水文应用与稳健性结果
已完成P5-A批量推理及历史诊断、P5-B预注册训练期内部探索。没有新的独立外部评价，教师锡尔河未读取。

## 应用与失败
54模型、54新进程、648条应用输出、0次fit。过程线真实回放P4排除2016标签的人工遮蔽模型，不冒充真实历史缺档。
50个站模型诊断覆盖有合格测试的25站；另2站明确N/A。以下是旧P4测试的事后诊断而非新实验：
"""+"\n".join(lines)+"""
\nP4冬季和5–6月平均相对技能负；2016 Elbe/Danube、2017 Rhine平均负。MAE/KGE/PBIAS逐站成对差异、各年最坏误差完整保留。
输入支持正常不能认证水文精度；无HIGH_EXTRAPOLATION样本，故不能估计该类与高误差的关系。

## 区间
"""+"\n".join(cover)+f"""
\n平均迁移膨胀kappa约1.355且只增不减；每季仅12个校准残差，80/90分位分别取升序第11/12个绝对残差，90%接近样本最大值；季节内等宽结构使低流量月尤其宽。
覆盖率明显偏高且宽度较大，不等于有用/精确。568行区间诊断覆盖站点、季节、水系、年份、低高流量及风险。归一化尺度是各站训练均值，不混合跨流域原始MSE推断。
没有利用V1重新调整区间并宣称新独立验证，无严格无条件覆盖保证。

## 唯一新增候选SHRINK
预注册DEVELOPMENT_BLOCKED_VALIDATION。四外层前向窗1995–99、2000–04、2005–09、2010–14；每外层用训练窗中两个更早3年块选择w；所有基础模型/alpha/变换均只用更早Q拟合。
27站108次权重选择；648次基础块模型拟合、59820次内层alpha拟合，共60468次fit。19329条预测对应6443个真实站月，三模型同样本，2015–2017 Q未用于w。
L1相对基线平均MSE技能{stat['P2-L1']['mean_skill_vs_C0PT']:+.2%}、27站正；SHRINK为{stat['P5-L1-SHRINK']['mean_skill_vs_C0PT']:+.2%}、{stat['P5-L1-SHRINK']['positive_vs_C0PT']}站正。
SHRINK相对L1平均技能{stat['P5-L1-SHRINK']['mean_skill_vs_L1']:+.2%}，0/27站总体改善。权重分布{weights}，77/108选择w=0。
因此不替换P4默认，不改权重网格再刷分；两个内层块的oneSE很粗，保留其限制。所有时期已参与先前研究，不称新独立测试。

## 外部与下一步
目录/许可元数据已取得，27站强身份对应；新的数值Q尚未取得，匹配的后2017 ERA5-Land驱动尚未取得，故本轮没有外部评分/冻结文件。详见外部可行性报告与逐站交叉表。
下一阶段优先同站2018年后Q+同源气象的小规模未评分资料核验，先冻结再单次评分原P4-V2。SHRINK内部表现不足，保留负结果，不晋升候选。
如只能替换E-OBS驱动，须另设驱动变更研究，不能混为纯时间泛化。教师锡尔河仍需真实数据负责人许可和现有授权执行链，公开成绩不能代替。

## 最终十项回答
1. 54个模型全部可独立加载和调用。
2. 负总体NSE及有负年份站不适合作高置信度结果，其余仍无业务认证。
3. 区间偏保守、偏宽；需同时看宽度与Interval Score。
4. 冬季、5–6月及部分水系年份易失效。
5. 本次SHRINK没有改善内部整体稳健性。
6. 新目录已得，新独立Q未得。
7. 没有进行未用于模型选择的新外部评价。
8. 真缺档0、人工遮蔽回放、V2应用均分开标识。
9. CLI、CSV、哈希/日期/单位/风险门禁和静态过程线已形成。
10. 优先时间稳健性的同站新资料，再扩展流域；锡尔河走独立合法授权路线。

图像源码预检19通过/2栅格建议警告，文本最小7pt，人工视觉检查通过。PyMuPDF在两个现有环境均不可用，PDF自动碰撞检查NOT_AUDITABLE，不声称出版级验收；未安装依赖。
"""
write("P5_SCIENTIFIC_REPORT_ZH.md",science)
guide=r"""# P5命令
    $py='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
    $cli='E:\VHS_Public_Baseline_Lab\p5_robustness_and_external_validation\code\p5_cli.py'
    & $py -B $cli verify-release
    & $py -B $cli predict --station 2 --model P2-L1 --start 2016-01 --end 2016-12 --met E:\VHS_Public_Baseline_Lab\p5_robustness_and_external_validation\runs\P5_A_SAVED_MODEL_APPLICATION\MET_2.json --precip-unit mm/month --temp-unit degC --output "$env:TEMP\P5_ID2_predictions.csv"
单位需如实声明，不能从数值猜单位。输入不得包含Q。2016为V2应用示例，不是新OOF。
demo真实实现54进程批次，但本次目录独占创建，勿覆盖封存。重跑请使用新独立根/run身份。
SHRINK入口freeze.py→shrink.py；完整验证verify_p5.py，均会写记录，交付后在新目录运行，不覆写此封存。
诊断diagnose.py只作历史再分析；最终绘图plot_demo.py。外部只取得目录，不存在外部评分文件。
"""
write("P5_REPRODUCTION_GUIDE.md",guide)
before=jl(P/"evidence/HISTORY_BEFORE.json")
for root,info in before.items():
 root=Path(root)
 assert sha(root/"SHA256SUMS.txt")==info["seal"]
 for ln in (root/"SHA256SUMS.txt").read_text(encoding="utf-8-sig").splitlines():
  h,n=ln.split("  ",1);assert sha(root/n)==h,n
jw("P5_COMPLETION_STATUS.json",{"UTC":datetime.now(timezone.utc).isoformat(),"status":"P5_A_AND_INTERNAL_B_COMPLETED_EXTERNAL_TEST_NOT_RUN","loaded_models":54,"fresh_processes":54,"application_predictions":648,"application_fit_calls":0,"internal_fit_calls":60468,"internal_predictions":19329,"weight_selections":108,"SHRINK":stat,"candidate_promoted":False,"external_metadata_matches":27,"new_external_Q_acquired":False,"external_test_performed":False,"true_gaps":0,"true_gap_status":"NO_ELIGIBLE_TRUE_GAPS","historical_freezes_unchanged":True,"SYRDARYA":"NOT_GRANTED_UNTOUCHED"})
with (P/"RUN_ATTEMPTS.jsonl").open("a",encoding="utf-8") as f:f.write(json.dumps({"event":"P5_REPORTS_AND_DELIVERY_COMPLETED","UTC":datetime.now(timezone.utc).isoformat(),"external_test":False})+"\n")
items=[(sha(p),p.relative_to(P).as_posix()) for p in sorted(P.rglob("*")) if p.is_file() and p.name!="SHA256SUMS.txt"]
(P/"SHA256SUMS.txt").write_text("".join(f"{h}  {n}\n" for h,n in items),encoding="utf-8")
for h,n in items:assert sha(P/n)==h
print(json.dumps({"sealed_files":len(items),"seal":sha(P/"SHA256SUMS.txt"),"P5_completed":True,"new_external_test":False,"SHRINK":stat}))
