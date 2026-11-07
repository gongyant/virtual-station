"""Generate Chinese outcome report from immutable public run, never substitute synthetic scores."""
import csv,hashlib,json,collections,shutil
from pathlib import Path
R=Path(__file__).resolve().parents[1];run=next((R/"runs").glob("PUBLIC_DATA_REAL_EXPERIMENT-*"));out=R/"reports"
def load(p):return json.loads(p.read_text(encoding="utf-8"))
def csvrows(p):
 with p.open(encoding="utf-8",newline="") as f:return list(csv.DictReader(f))
m=load(run/"manifest.json");meta=load(run/"data_provenance.json");data=csvrows(run/"OVERALL_METRICS.csv");yearly=csvrows(run/"YEARLY_EVALUATION.csv");comp=csvrows(run/"MODEL_COMPARISON.csv");details=load(run/"model_comparison_details.json")
def scorelines(exp):
 result=[]
 for gid in meta["selected_gauge_ids"]:
  name=meta["selected_gauge_attributes"][str(gid)]["name"]
  result.append(f"### ID {gid} — {name}\n")
  for mid in ("C0","E3n"):
   row=next(x for x in data if x["experiment"]==exp and int(x["gauge_id"])==gid and x["model_id"]==mid)
   result.append(f"- {mid}：NSE **{float(row['NSE']):.6f}**；KGE **{float(row['KGE']):.6f}**（r={float(row['KGE_r']):.6f}，α={float(row['KGE_alpha']):.6f}，β={float(row['KGE_beta']):.6f}）；RMSE={float(row['RMSE']):.6f} m³/s，MAE={float(row['MAE']):.6f} m³/s，PBIAS={float(row['PBIAS']):.6f}%；相对C0技能={float(row['skill_vs_C0']):.6f}。")
  cr=next(x for x in comp if x["experiment"]==exp and int(x["gauge_id"])==gid)
  worse=sorted([x for x in yearly if x["experiment"]==exp and int(x["gauge_id"])==gid and x["model_id"]=="E3n"],key=lambda x:float(x["RMSE"]),reverse=True)[:3]
  result.append(f"\nE3n按年度MSE改善的年份比例={100*float(cr['fraction_years_improved']):.0f}%；删除任一年度后仍全部为正：{cr['jackknife_all_deletions_positive']}。E3n最差三个RMSE年度："+", ".join(f"{x['year']}（{float(x['RMSE']):.3f} m³/s）" for x in worse)+"。\n")
 return "\n".join(result)
params=load(run/"model_parameters.json");alphas=collections.Counter(str(x["record"]["parameters"]["selection"]["selected_alpha"]) for x in params if x["record"]["model_id"]=="E3n")
source=f"""# 真实公开数据来源、许可与署名

实验统一标记 PUBLIC_DATA_REAL_EXPERIMENT；绝不标记SYRDARYA_REAL_EXPERIMENT。独立下载，不读取原工程sealed_runoff或教师Q。

- 官方数据集：[LamaH-CE v1.0](https://zenodo.org/records/5153305)，DOI 10.5281/zenodo.5153305。
- 数据集署名：Klingler, Christoph; Kratzert, Frederik; Schulz, Karsten; Herrnegger, Mathew (2021), LamaH-CE, version1.0。
- 数据论文：Klingler, C., Schulz, K., and Herrnegger, M. (2021), Earth System Science Data13,4529–4565，[DOI10.5194/essd-13-4529-2021](https://doi.org/10.5194/essd-13-4529-2021)。
- 实际文件：2_LamaH-CE_daily.tar.gz，1,477,248,617 bytes；只下载日尺度包，未下载14.8GB小时包。
- 官方公布MD5：69fd2733e969513403f923ecc5eaa3dc；本次下载实算匹配。
- 本次实算SHA256：b692afc817fc7d92c003b3203fa04def9bbc04c3db39fa58b94c37f8d5376dd0。
- 气象使用 A_basins_total_upstrm/2_timeseries/daily/ID_*.csv 的ERA5-Land全上游流域加权平均；Q使用D_gauges/2_timeseries/daily/ID_*.csv的水文部门观测，**没有使用F_hydrol_model模拟输出**。
- 所选ID2/6/9均为AUT，原始水文来源按Info归属HZB (2020)；ERA5-Land引用Muñoz Sabater (2019a)/Muñoz Sabater et al. (2021)，完整官方要求的附加来源保留在ATTRIBUTION_ORIGINAL.txt。

## 许可差异如实保留

官网描述为CC BY-SA4.0；本次API metadata和包内Info_english/4_Creative_commons_license_4.txt为CC BY4.0。三份原始证据均已保存，没有宣称完全一致或只选宽松版本。两者均允许带署名的本地研究和改编；本实验对派生月数据、结果、图表遵循更严格的CC BY-SA4.0条件，注明来源、版本和修改，并附同许可链接。尚未对外发布，也未取得任何教师数据许可。不是向外部机构发出的法律认证。

许可：[CC BY-SA4.0](https://creativecommons.org/licenses/by-sa/4.0/)。保留免责声明和原参考文献，不将研究输出用于运行性预警。

## 修改与时间/单位定义

只在新目录中把完整UTC日序列聚合为完整自然月，筛选固定实验年；不填缺、不平移月份、不根据成绩改值。Q为日平均的月平均，m³/s；prec为日累计降水的月累计，mm/月；2m_temp_mean为日平均气温的月平均，°C，源数据已为°C，未错误减273.15。

Info明确所有时间序列UTC无夏令时；论文4.1说明AUT等国日Q与气象按00:00–23:59UTC汇总。本实验只用原生日尺度，无小时包。源方LamaH在日汇总前可能线性填补不超过6小时的小缺口；所以这是水文部门观测经公开数据集处理后的日Q，不声称每个原始小时都无处理。本实验没有新增插值。

ckhs=1为水文部门已检查，不等于所有误差已消失。qceq/qcol分别为重复值和离群诊断，原规则仅统计不自动删除，避免把合法极端值或真实恒流当作错误；ID2/6/9在16个联合年份分别有0/51/0个qceq日和1/0/0个qcol日。本结论以此公开QC规则为条件。

源API JSON、官网HTML、论文HTML、原Info八文件、TableA1/A2截图和下载哈希均在source保存，来源URL见ACQUISITION.json。初次尝试论文外置supplement.pdf得到404，实际使用包内官方Info文本完成核实，没有制造补充材料。
"""
(out/"SOURCE_AND_LICENSE.md").write_text(source,encoding="utf-8")
shutil.copyfile(R/"source/extracted/Info_english/3_References.txt",out/"ATTRIBUTION_ORIGINAL.txt")
permission="""# 锡尔河主线：必要材料与简短申请

当前仍为NOT_GRANTED；本公开实验不授予或扩大教师数据权限。原R0运行器、S1/S2/S3及网站未修改，没有新增真实审批系统，没有把本次公开数据分数写入锡尔河成绩表。

实际负责人需要提供：①审批者身份、数据许可权与公钥所有权核验；②两站月均Q用于A五模型十折LOYO的具体许可，含期限、快照、用途、输出路径及E0等值Qu预测保存；③据此登记真实公钥生成的新release及签名envelope；④独立执行指令。不得交付私钥，不得将本公共数据许可当成锡尔河许可。

简短申请：

“申请在本地使用SYRDARYA:16037与16039的合格月平均Q，依冻结claude_core120月/10年及10折LOYO，运行E0/C0/E1a/E1b/E2，进行训练、最终评分并保存参数和样本外预测；其中E0预测数值等于上游Qu，申请明确允许该预测保存。不批量导出目标Qobs，不进行共同缺档推理，不写网站。请有权负责人确认数据使用权限、审批者身份、授权期限及指定输出路径，并按现有可信公钥机制签署新release范围；许可齐备后另给独立执行指令。”

材料到位后直接使用既有：
E:\\VHS_WorkBuddy_S1T_Sandbox\\output\\vhs_sci_s3b_real_r0\\r0_run.py
及NEXT_APPROVED_REAL_RUN.md，不再重写模型或重复准备。当前待批准release不是登记真实公钥后的最终ID。
"""
(out/"SYRDARYA_PERMISSION_REQUEST_ZH.md").write_text(permission,encoding="utf-8")
summary={"status":"COMPLETED_VERIFIED","experiment_label":"PUBLIC_DATA_REAL_EXPERIMENT","synthetic":False,"public_observed_Q_used":True,"run_id":m["run_id"],"run_dir":str(run),"gauge_ids":meta["selected_gauge_ids"],"model_families":["C0","E3n"],"PUBLIC_REAL_OUTER_FITS":120,"PUBLIC_REAL_INNER_FITS":2700,"PUBLIC_REAL_TOTAL_FIT_CALLS":2820,"PUBLIC_REAL_OOF_RECORDS":1440,"SYRDARYA_REAL_AUTHORIZATION_STATUS":"NOT_GRANTED","SYRDARYA_REAL_TRAINED_MODELS":0,"SYRDARYA_REAL_EVALUATED_MODELS":0,"SYRDARYA_REAL_PREDICTION_RECORDS":0,"main_result":"E3n has lower NSE and KGE than C0 in every preselected basin; no robust meteorological gain demonstrated","fixed_sparse_result":"OnlyID6 has tiny positive MSE skill(+0.83%), no positive deletion-robust or year-majority gain","S2_numerical_AST_methods_unchanged":47,"source_sha256":meta["source_acquisition"]["sha256"],"training_code_hash":m["code_hash"],"protocol_hash":m["protocol_hash"],"snapshot_id":m["snapshot_id"]}
(out/"PUBLIC_REAL_EXPERIMENT_STATUS.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
doc=f"""# 首次公开实测水文基线实验结果

**已完成真正的公开水文观测模型训练、留年预测和评价；锡尔河教师数据仍未授权、未训练。**

实验标记：PUBLIC_DATA_REAL_EXPERIMENT；synthetic=false。本次Q来自新下载LamaH-CE v1.0水文部门观测，并非合成Q或公开包内COSERO模拟流量。P/T是ERA5-Land再分析，不冒称站点实测气象。

run_id：{m['run_id']}

## 实际运行规模

先固定1990–1999十个自然年主实验，并另固定1983、1987、1990、1994、1996、1999、2000、2001、2002、2004稀疏十年实验。后者仅在公开流域模拟S1年度间隔，不是锡尔河观测，两个方案部分共享年份，不能视为独立重复实验。

按官方ID升序选择在两个窗口联合16年、每个月Q/P/T均100%日完整的前三站：ID2 Schruns(Vonbunweg)/Litz，ID6 Garsella/Lutz，ID9 Gisingen/Ill。共576条唯一公开月观测。ID1/3/4/5/7/8因固定早期年份不完整而拒绝，非根据模型分数拒绝；完整选择日志在BASIN_SELECTION.json。三站同属Rhine区域，可能有河网依赖，未当作独立流域样本池做确认性推断。

两个方案每站各120月，C0与E3n同样本。每个方案每站10折，108月训练、12月留出。
- C0外层实际拟合60次。
- E3n外层实际拟合60次。
- E3n内层实际拟合2700次（60个外层×5个alpha×9个内部留年折）。
- **实际总拟合调用2820次，完成60个外层折、120条外层模型记录，1440条真实OOF预测。**
- 没有失败折、没有跳折或重试挑高分。拟合事件逐条保存，verify_public_run校验通过。

## 主实验：1990–1999真实LOYO成绩

{scorelines("CONSECUTIVE_10Y")}

主实验三个流域E3n均弱于C0。相对C0的MSE分别增加约63.94%、18.14%、22.41%。这不是训练失败，而是已冻结的模型比较结果。没有因此调整年份、换样本或扩大超参数候选。

## 固定稀疏十年实验

{scorelines("SPARSE_10Y_PUBLIC_SUBSAMPLING")}

稀疏ID6的MSE技能仅+0.83%，KGE仍低于C0，改善年份只占40%，jackknife不能保证删除任意一年仍为正；不构成稳定气象增益。其余两站也不支持增益。不能从这些固定但不同年份的分数差异中因果认定“稀疏采样改善/恶化性能”。

## 数值与科研解释

- C0有12个月分别估计的季节均值；E3n只有一组季节正余弦加P/T异常，两者不是仅相差气象项的严格嵌套模型。因此差异包含季节表达能力差异，**不能据此证明气象没有信息**。
- C0的总体PBIAS接近0是完整平衡LOYO月气候态的汇总性质，不是物理水量平衡得到验证。
- 所有原始预测均非负，预登记max(raw,0)次分析与原始成绩相同，未依次分析挑结果。
- 逐年RMSE/MAE/NSE/KGE/PBIAS和KGE分量、年份等权MSE、相对C0技能、年度bootstrap/jackknife及单年敏感性均保留。内层alpha选择计数：{dict(alphas)}。
- 比较中的符号翻转p为未校正描述性结果；没有预注册跨流域确认性家族，年份可交换性与独立性也非既定事实，不能宣称确认性“SUPPORTED”。锡尔河原四项Holm家族完全未动，仍NOT_RUN。
- 不研究严格无资料站、跨河段泛化或物理损失机制。模型使用本流域其他年份标签和目标月完整P/T，属于历史月尺度重建验证，不是可提前发布的未来流量预报。
- Q为m³/s，P为mm/月，T为°C，来自官方单位说明，不能把该单位认证迁移到锡尔河教师数据。源数据有已检查标记，但也可能包含LamaH上游处理中的≤6小时插值和QC诊断日，详见来源记录。

## 可复核产物

- [真实OOF观测/预测CSV]({(run/'OOF_PREDICTIONS.csv').as_posix()})
- [全部总体指标]({(run/'OVERALL_METRICS.csv').as_posix()})
- [逐年评价]({(run/'YEARLY_EVALUATION.csv').as_posix()})
- [同样本模型比较]({(run/'MODEL_COMPARISON.csv').as_posix()})
- [年度不确定性和jackknife]({(run/'model_comparison_details.json').as_posix()})
- [各折完整年月及ID哈希]({(run/'folds.json').as_posix()})
- [实际拟合事件]({(run/'fit_events.json').as_posix()})
- [来源许可与署名]({(out/'SOURCE_AND_LICENSE.md').as_posix()})
- [真实run验证结果]({(R/'evidence/REAL_RUN_VERIFICATION.json').as_posix()})

六份过程线全部显示120个合法OOF月份；稀疏年之间断线，不做视觉插值。三站主实验：
"""+"\n".join(f"- [ID{gid} Qobs/Qsim过程线]({(out/'figures'/f'CONSECUTIVE_10Y_ID_{gid}.png').as_posix()})" for gid in meta["selected_gauge_ids"])+f"""

## 实现、复现与剩余限制

原冻结S2文件未修改，47个数学方法AST相同。独立副本仅适配公开来源数据契约和真实输出标记；训练标签按外层训练ID限制，所有折内气候态/标准化及alpha内部验证均使用合法训练范围。没有把public数据写成synthetic=true，也没有借此放行教师数据。

训练code_hash={m['code_hash']}
protocol_hash={m['protocol_hash']}
snapshot_id={m['snapshot_id']}
官方日包SHA256={meta['source_acquisition']['sha256']}

此处code_hash是实际训练时代码集合；之后新增的绘图、报告与验证脚本由交付清单另行哈希，不冒充已参与训练的代码。不可变run及SHA256SUMS不被后续报告改写。

~~~powershell
$Lab = 'E:\\VHS_Public_Baseline_Lab'
$Py = 'E:\\CodexProject\\CodexProject\\DeepBas-VHS-GT-Lite-v0.1\\.venv\\Scripts\\python.exe'
& $Py -B "$Lab\\code\\verify_public_run.py"
# 只有明确需要另开一次复现实验才运行；会保存新run，不覆盖本次首次结果：
& $Py -B "$Lab\\code\\run_public_experiment.py"
~~~

过程线源代码和六份PDF文字≥5pt检查通过，已逐图目视核查。现有环境无PyMuPDF，自动PDF几何碰撞审查为NOT_AUDITABLE，未安装依赖，未将这些研究图标作投稿级QA已通过。该图形检查限制不影响已核验的数值成绩。

首次公开实测模型实验已完成。本轮没有增加模型以追求更高分；若继续研究气象增量，应预先固定相同季节结构的对照再比较，而不是把C0与E3n的结构差异全部归因气象。

## 锡尔河并行状态

SYRDARYA_REAL_AUTHORIZATION_STATUS=NOT_GRANTED。
SYRDARYA_REAL_TRAINED_MODELS=0；SYRDARYA_REAL_EVALUATED_MODELS=0；SYRDARYA_REAL_PREDICTION_RECORDS=0。

没有读取教师Q或原封存LamaH径流，不向锡尔河成绩表/网站导入公开结果。必要材料及简短申请单独写在SYRDARYA_PERMISSION_REQUEST_ZH.md；许可与独立执行指令到位后直接使用原R0 A五模型十折入口，不再开发审批系统或重写模型。
"""
(out/"FIRST_PUBLIC_REAL_BASELINE_REPORT_ZH.md").write_text(doc,encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))

