from __future__ import annotations

import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from verify_stage_d6_freeze import SPECS, verify


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "diagnosis_2005_snapshot"
OUT = BASE / "stage_d7"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fmt(value, digits=3) -> str:
    if value in (None, ""):
        return "—"
    return f"{float(value):.{digits}f}"


def md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def stage_for(path: Path) -> str:
    parts = path.relative_to(BASE).parts
    first = parts[0] if parts else ""
    if first == "stage_b" or first == "graph_runs" or first in {"graph_edge_ablation.csv", "lag_diagnosis.csv", "diagnosis_2005_snapshot_gnn.md"}:
        return "B"
    if first == "stage_c":
        return "C"
    if first == "stage_d":
        return "D1-D2"
    if first == "stage_d3":
        return "D3"
    if first == "stage_d4a":
        return "D4A"
    if first == "stage_d4b":
        return "D4B"
    if first == "stage_d5":
        return "D5R1"
    if first == "stage_d5_round2":
        return "D5R2"
    if first == "stage_d5_round3":
        return "D5R3"
    if first == "stage_d5_round4":
        return "D5R4"
    if first == "stage_d6":
        return "D6"
    return "A"


def describe(path: Path) -> str:
    name = path.name.lower()
    if "manifest" in name:
        return "冻结清单/哈希索引"
    if "protocol" in name or "preregistration" in name:
        return "预注册或冻结实验协议"
    if "metric" in name or "result" in name or "comparison" in name:
        return "正式指标或模型对照"
    if "prediction" in name:
        return "冻结预测或逐日诊断"
    if "audit" in name or "lineage" in name:
        return "来源、实现或完整性审计"
    if path.suffix.lower() == ".png":
        return "诊断图"
    if path.suffix.lower() == ".xlsx":
        return "人工审阅工作簿"
    if path.suffix.lower() == ".md":
        return "中文报告/说明"
    return "阶段工件"


def command_output(command: list[str]) -> str:
    try:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20)
        text = (p.stdout + p.stderr).strip()
        return text if text else f"exit_code={p.returncode}"
    except Exception as exc:
        return f"unavailable: {exc}"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    audits = [verify(*spec) for spec in SPECS]
    all_passed = all(a["count_ok"] and a["all_hashes_match"] and a["all_sizes_match"] for a in audits)
    audit_payload = {
        "audit_time_utc": datetime.now(timezone.utc).isoformat(),
        "all_passed": all_passed,
        "write_policy": "stages_A_to_D6_read_only; stage_D7_only_writable",
        "new_model_training_authorized": False,
        "new_NSE_generation_authorized": False,
        "audits": audits,
    }
    (OUT / "d6_immutability_audit.json").write_text(json.dumps(audit_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all_passed:
        raise RuntimeError("Frozen manifest verification failed; D7 stopped before writing drafts.")

    registry_path = BASE / "stage_d6" / "experiment_registry_A_to_D5.csv"
    registry = read_csv(registry_path)
    by_id = {r["experiment_id"]: r for r in registry}
    graph = read_csv(BASE / "graph_edge_ablation.csv")
    d4b = read_csv(BASE / "stage_d4b" / "boundary_only_2011_external_metrics.csv")
    d5r2 = read_csv(BASE / "stage_d5_round2" / "outer_year_metrics.csv")
    m2r = read_csv(BASE / "stage_d5_round4" / "m2r_nested_loyo_results.csv")
    m2c = read_csv(BASE / "stage_d5_round4" / "m2c_nested_loyo_results.csv")
    r2_decision = json.loads((BASE / "stage_d5_round2" / "model_promotion_decision.json").read_text(encoding="utf-8"))
    r2_protocol = json.loads((BASE / "stage_d5_round2" / "model_protocol_frozen.json").read_text(encoding="utf-8"))
    r4_decision = json.loads((BASE / "stage_d5_round4" / "m2c_development_promotion_decision.json").read_text(encoding="utf-8"))
    r4_protocol = json.loads((BASE / "stage_d5_round4" / "stage_d5_round4_model_protocol_frozen.json").read_text(encoding="utf-8"))
    eligible = json.loads((BASE / "stage_d5_round2" / "eligible_year_registry.json").read_text(encoding="utf-8"))
    go_no_go = json.loads((BASE / "stage_d6" / "research_go_no_go_decision.json").read_text(encoding="utf-8"))

    def R(experiment_id: str) -> dict[str, str]:
        return by_id[experiment_id]

    a_rows = []
    for eid, label in [("A_PHY", "MQ参考"), ("A_GNN", "有向快照GNN"), ("A_NG", "独立无图")]:
        r = R(eid)
        a_rows.append([label, fmt(r["NSE"]), fmt(r["RMSE"], 2), fmt(r["KGE"]), fmt(r["PBIAS"], 2) + "%"])
    graph_rows = [[r["structure"], fmt(r["nse_mean"]), fmt(r["nse_std"]), fmt(r["rmse_mean"], 2), fmt(r["kge_mean"])] for r in graph]
    c_rows = []
    for eid, label in [("A_PHY", "MQ reference"), ("A_NG", "无图"), ("B1_G1_self_loops", "仅自环"), ("A_GNN", "原有向GNN"), ("C_K10_LEGACY", "K=10非负分布式时滞"), ("C_KERNEL_LEGACY", "低维核")]:
        r = R(eid)
        c_rows.append([label, r["task_protocol"], fmt(r["NSE"]), fmt(r["RMSE"], 2), fmt(r["KGE"]), fmt(r["PBIAS"], 2) + "%"])
    d4b_rows = [[r["window_id"], r["start_date"] + "—" + r["end_date"], r["n_days"], fmt(r["NSE"]), fmt(r["RMSE"], 2), fmt(r["KGE"]), fmt(r["PBIAS"], 2) + "%"] for r in d4b]
    macro = {r["model"]: r for r in d5r2 if r["row_type"] == "macro_mean" and r["model"] in {"M0", "M1", "M2"}}
    m0_abs_pbias = sum(
        abs(float(r["pbias"]))
        for r in d5r2
        if r["row_type"] == "year" and r["model"] == "M0"
    ) / len({r["year"] for r in d5r2 if r["row_type"] == "year" and r["model"] == "M0"})
    macro_m2r = next(r for r in m2r if r["row_type"] == "macro_mean")
    macro_m2c = next(r for r in m2c if r["row_type"] == "macro_mean")
    d5_macro_rows = []
    for model in ["M0", "M1", "M2"]:
        r = macro[model]
        d5_macro_rows.append([model, fmt(r["nse"]), fmt(r["rmse"], 2), fmt(r["kge"]), fmt(r["pbias"], 2) + "%", fmt(r2_decision["models"].get(model, {}).get("macro_abs_pbias", ""), 2) + "%" if model in r2_decision["models"] else fmt(m0_abs_pbias, 2) + "%"])
    d5_macro_rows.extend([
        ["M2R", fmt(macro_m2r["nse"]), fmt(macro_m2r["rmse"], 2), fmt(macro_m2r["kge"]), fmt(macro_m2r["pbias"], 2) + "%", "13.19%"],
        ["M2C", fmt(macro_m2c["nse"]), fmt(macro_m2c["rmse"], 2), fmt(macro_m2c["kge"]), fmt(macro_m2c["pbias"], 2) + "%", "12.57%"],
    ])
    yearly_rows = []
    r2_year = {(r["model"], r["year"]): r for r in d5r2 if r["row_type"] == "year" and r["model"] in {"M0", "M1", "M2"}}
    r4_year = {r["year"]: r for r in m2c if r["row_type"] == "year"}
    for year in ["1978", "1979", "1980", "1981", "1982", "1983"]:
        yearly_rows.append([year] + [f"{fmt(r2_year[(m, year)]['nse'])} / {fmt(r2_year[(m, year)]['rmse'], 2)}" for m in ["M0", "M1", "M2"]] + [f"{fmt(r4_year[year]['nse'])} / {fmt(r4_year[year]['rmse'], 2)}"])

    results = f"""# 论文结果章节初稿

## 1. 数据与任务协议

研究对象为开都河巴音布鲁克—大山口河段，目标站为大山口（00705700），主要上游边界站为巴音布鲁克（00705600）。为避免把不同信息条件下的结果混为一谈，实验按P1、P1B和P2区分。P1允许用历史大山口Q拟合上游—下游关系，适用于历史有站条件下的连续缺测重建；P1B允许使用目标站当前或历史水位等本地状态，但不允许把目标Q作为输入；P2不使用大山口Q监督，只依赖外部参考、其他站信息或共享关系。当前项目没有满足准入条件的多年份大山口水位，因此P1B仅完成协议定义，未形成正式模型结果。

评价身份也分为三类。2005年9—10月的61天结果已在阶段A/B多次查看，只能称内部历史诊断；2011年评价采用先冻结参数和预测、后读取大山口标签的顺序，称“预注册跨年份评价”，但2011资料已经人工转录和揭示，不能称完全盲测；1978—1983采用嵌套留一年，属于多年份回顾性稳健性评价，而不是六次完全独立外部验证。

## 2. 阶段A普通GNN审计

原同日快照GNN包含巴音布鲁克、大山口、阿拉尔、新其满和阿其克五个节点，使用三条有向边，其中开都河分量只有巴音布鲁克→大山口。动态输入为同日观测Q、MQ参考及其可用性标志；静态输入包括节点顺序、流域分量、汇水面积及面积可用性。目标站大山口的观测Q在所有输入时刻被置零且可用性标志置零，训练损失和早停均排除大山口标签；大山口MQ保留为输入和残差锚点。

模型没有历史窗口，而是用巴音布鲁克当日状态预测大山口当日Q。原边表虽记录巴音布鲁克—大山口河段距离212.61 km，但构包后边属性均为1，标准化后全部为0，因此网络没有距离、坡度、流速、传播时滞或控制状态信息。2005年固定划分为2005-01-03至06-30训练、07-01至08-31验证、09-01至10-31测试。

{md_table(["方法", "NSE", "RMSE (m³/s)", "KGE", "PBIAS"], a_rows)}

MQ参考NSE为{fmt(R('A_PHY')['NSE'])}；有向GNN降至{fmt(R('A_GNN')['NSE'])}，而无图模型为{fmt(R('A_NG')['NSE'])}。因此，在相同数据、损失和划分下，真实有向边没有带来增益。

## 3. 图结构对照

{md_table(["结构", "NSE均值", "NSE标准差", "RMSE均值", "KGE均值"], graph_rows)}

仅自环取得最高NSE {fmt(next(r for r in graph if r['structure']=='G1_self_loops')['nse_mean'])}，真实有向边为{fmt(next(r for r in graph if r['structure']=='G2_true_directed')['nse_mean'])}，反向边和随机边分别为{fmt(next(r for r in graph if r['structure']=='G3_reversed')['nse_mean'])}和{fmt(next(r for r in graph if r['structure']=='G4_random')['nse_mean'])}。真实边、反向边和随机边彼此接近，却都弱于无图与自环，说明主要损害来自邻居消息混合，而不是普通随机波动。逐日比较还显示，有向GNN在61/61天的绝对误差均大于无图模型，测试期上游和目标输入没有缺失，因此不能把负贡献归因于测试缺测。

## 4. MQ参考与阶段C历史缺测结果

MQ只可追溯至`Q-新疆.xls/2005-支流/MQ-DSK-2005-SB`现成列，生成公式未知。阶段C在P1条件下以巴音布鲁克Q作为显式边界，使用2005年5—8月五个扩展窗口进行开发，在9—10月已揭示61天上只运行一次历史诊断。

{md_table(["模型", "协议", "NSE", "RMSE", "KGE", "PBIAS"], c_rows)}

K=10非负分布式时滞在已揭示61天取得NSE {fmt(R('C_K10_LEGACY')['NSE'])}，低维核取得{fmt(R('C_KERNEL_LEGACY')['NSE'])}。这两个数值表明上游边界具有信息，但它们都使用了大山口历史标签，属于P1，不能作为P2严格无站性能。五个开发fold中，K10有4/5个fold的RMSE低于MQ，低维核为3/5；两者的fold平均NSE仍为负，说明短期高分与开发稳定性并不一致。

## 5. 自由K10的共线性与尖峰退化

冻结K10名义上包含lag0—lag10共11个非负权重，实际只有lag0和lag5非零，形式约为`1.655 + 3.295Q(t) + 0.683Q(t-5)`。标准化时滞矩阵条件数为73.98，最大VIF为231.04，有效秩为2.36/11。块自助和删块诊断显示lag5附近的尖峰会在相邻位置间移动，因此这两个非零lag不能解释为稳定的物理传播时间。自由K10的高分本质上包含对高度相关滞后特征的稀疏择一。

## 6. 2011冻结跨年份评价

2011评价的模型名为`C_EXT_boundary_only_K10`。预测程序只读取冻结2005参数、2011巴音布鲁克Q和日期；预测文件和哈希形成后，评分程序才读取2011大山口Q。主窗口与2005拟合季节支持一致，全年窗口仅作为预先声明的外推诊断。

{md_table(["窗口", "日期", "天数", "NSE", "RMSE", "KGE", "PBIAS"], d4b_rows)}

主窗口NSE从2005已揭示期的{fmt(R('C_K10_LEGACY')['NSE'])}降至{fmt(R('D4B_primary')['NSE'])}，主窗口峰值日期提前9天。该结果不能通过修改K、权重、截距、正则化或评价窗口进行补救；它揭示的是同一冻结上游关系在年份间迁移不足。

## 7. 1978—1983来源审计

1978—1983原始工作簿中的巴音布鲁克与大山口两列经逐值核验，共2站×2191天=4382个站日，与`timeseries.csv`和NPZ一致。六年没有缺日、重复、项目插值、平滑或异常替换，1980年包含2月29日。六年均以`eligible_with_warning`准入；警告包括原表未打印单位和质量标志、水文日起止时刻未知、历史大山口相对闸门的位置未知。2000、2001和2011不参与本轮选模或评分。

## 8. M0、M1、M2嵌套留一年结果

M0为2005冻结K10，不重新拟合；M1为平滑非负核，核族和初始化仅在外层训练年份内部选择；M2为单储量状态。每次外层留出一个完整年份，训练损失为各训练年份日MSE的宏平均。共同评分范围为1978年第61日起、1979—1983年第31日起。

{md_table(["模型", "宏平均NSE", "宏平均RMSE", "宏平均KGE", "宏平均有符号PBIAS", "宏平均绝对PBIAS"], d5_macro_rows[:3])}

{md_table(["留出年份", "M0 NSE/RMSE", "M1 NSE/RMSE", "M2 NSE/RMSE", "M2C NSE/RMSE"], yearly_rows)}

M1在5/6年降低RMSE，但1979年RMSE由{fmt(r2_year[('M0','1979')]['rmse'],2)}升至{fmt(r2_year[('M1','1979')]['rmse'],2)} m³/s，且六个fold的核宽均达到15天上界。M2在6/6年降低RMSE，宏平均NSE由M0的{fmt(macro['M0']['nse'])}提高到{fmt(macro['M2']['nse'])}；最困难的1980年由{fmt(r2_year[('M0','1980')]['nse'])}提高到{fmt(r2_year[('M2','1980')]['nse'])}。然而M2宏平均绝对PBIAS为{fmt(r2_decision['models']['M2']['macro_abs_pbias'],2)}%，高于M0的{fmt(m0_abs_pbias,2)}%，并超过预注册的M0+2个百分点容差，因此M1和M2均未晋升，决定为`{r2_decision['decision']}`。

## 9. M2R等价参数化与长期记忆

M2R将原状态改写为`E_t=rho E_(t-1)+(1-rho)Q_BYBLK(t)`，输出为`max(0,b+gE_t+cQ_BYBLK(t))`。它没有重新拟合，而是对第二轮冻结参数作数学等价变换；逐日预测最大差为1.137×10^-13 m³/s。原参数a触边主要来自未归一化状态尺度，不能直接解释为储量作用消失。

六个fold的rho为0.9684—0.9757，对应半衰期21.6—28.2天、e-folding时间31.1—40.7天、90%累计响应72—94天。这说明数据支持数周记忆，10天或15天窗口不足以覆盖完整衰减尾部；但统计记忆不能自动命名为真实库容、地下水或闸门状态。

## 10. M2C融雪修正及拒绝原因

M2C在M2R基础上只增加过去14个完整UTC日的区间融雪总量，且先`shift(1)`再滚动，禁止使用当日或未来气象。融雪变量在各训练fold内标准化，系数d预先约束为非正。该变量曾利用六年残差作探索筛选，因此外层年份不是特征选择意义上的完全独立检验，评价身份只能称开发性嵌套留一年稳健性评价。

{md_table(["模型", "宏平均NSE", "宏平均RMSE", "宏平均KGE", "宏平均PBIAS", "宏平均绝对PBIAS"], d5_macro_rows[3:])}

M2C相对M2R在{r4_decision['rmse_better_year_count']}/6年降低RMSE、在{r4_decision['abs_pbias_better_year_count']}/6年降低绝对PBIAS，宏平均NSE由{fmt(macro_m2r['nse'])}升至{fmt(macro_m2c['nse'])}。但1979年PBIAS由{fmt(next(r for r in m2r if r['year']=='1979')['pbias'],2)}%变为{fmt(next(r for r in m2c if r['year']=='1979')['pbias'],2)}%，最长连续负误差由115天增至156天。冻结12项门槛仅通过11项，失败项为`year_1979_underestimate_relieved`，最终决定为`{r4_decision['decision']}`，不再测试其余气象变量。

## 11. 统一结果总结

普通图消息传递没有形成水文传播能力；显式上游边界能在同年历史期显著提高拟合，但自由lag因共线性退化为尖峰并在2011跨年下降；单储量模型用低维连续状态改善了六年过程形状，却不能稳定确定年度水量增益；单一融雪变量只能局部修正，未解决1979持续低估。综合证据支持冻结结论：**单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。**
"""
    write_text(OUT / "paper_results_full_draft_zh.md", results)

    discussion = f"""# 论文讨论章节初稿

## 1. 普通GNN为何没有产生水文传播能力

图拓扑只说明“谁在谁上游”，并不自动提供传播方程。原模型的三条边共享同一消息参数，边属性在标准化后全部为零，网络看不到212.61 km距离、坡度、流速、旅行时间或大山口控制状态。更重要的是，模型选择和早停只依据非目标节点；另一个塔里木分量的数据量与过程特征会影响共享消息层，却没有保证该层对大山口有效。真实边、反向边和随机边NSE均约0.31，而无图与自环更高，这种模式说明网络学到的是一般性隐藏特征混合，而不是可验证的开都河传播关系。

## 2. 同日图消息不等于河道传播

当前快照关系是`Q_BYBLK(t)→hidden_DSK(t)→Q_DSK(t)`。河道传播至少涉及时间延迟、弥散、河槽储量和沿程增减水；大山口还可能受闸门和水库调节。把同日上游Q与气象、月份、MQ等普通特征一起编码，既不满足质量守恒，也不保证时间因果。即使开发期lag0相关最高，也只能说明日尺度序列同步性强，不能证明水团在零天内通过整个河段。图消息只有在边界量、传播尺度和本地状态被明确表达并由目标任务监督时，才有可能获得水文含义。

## 3. 自由lag为何出现高共线尖峰

日流量序列连续且高度自相关，lag0—lag10并不是11条独立信息。条件数73.98、最大VIF 231.04和有效秩2.36/11表明设计矩阵接近低秩。非负最小二乘在这类矩阵上会从多个相似lag中选择少数代表列，从而形成lag0与lag5尖峰；换一个时间块，尖峰可移动到相邻位置而预测变化很小。因此自由lag的稀疏权重具有数值选择性，不具有稳定物理可识别性。对这类过程，更合理的约束是平滑核或低维状态，而不是把每个lag权重解释为分配比例。

## 4. 单储量模型说明了什么长期记忆

M2的rho跨fold保持在0.9684—0.9757，等价半衰期为21.6—28.2天，90%累计响应需要72—94天；同时，M2在6/6个留出年降低RMSE。这两条证据共同支持“数周记忆”的统计结构，并说明10天K10或15天平滑核对完整衰减尾部偏短。这里的“储量”是一个递推状态，用来压缩上游历史并约束记忆连续性；它证明长期记忆比自由尖峰更稳定，却不证明该状态就是某个可观测水库库容、河槽蓄量或地下水储量。

## 5. 单储量为何仍不能确定跨年水量增益

状态模型可以平滑和延迟过程，却仍然只接收巴音布鲁克Q。年度尺度上，大山口Q还包含区间支流、降雪融水、引退水、地下水交换以及人为调度。若这些分量随年份变化，固定的b、g和c只能把多种机制压缩成一个经验增益。M2宏平均NSE和RMSE改善，但绝对PBIAS反而从M0的{fmt(m0_abs_pbias,2)}%增至{fmt(r2_decision['models']['M2']['macro_abs_pbias'],2)}%，说明过程形状与年度水量闭合是两个不同问题。

## 6. 1979与1982相反偏差的意义

1979年M2 PBIAS为{fmt(r2_year[('M2','1979')]['pbias'],2)}%，表现为跨月持续低估并包含洪峰贡献，不能靠删除单一洪峰解决。1982年M2 PBIAS为{fmt(r2_year[('M2','1982')]['pbias'],2)}%，主要表现为若干月份和低流量基线抬高。一个年份需要增加水量，另一个年份需要降低基线，说明单一固定增益无法同时代表区间补给和控制释放。相反方向的失败是信息欠定的证据，而不仅是参数没有调到最佳。

## 7. 单一融雪变量为何只能局部修正

过去14日区间融雪为模型提供了上游Q之外的一条季节信息，因此M2C宏平均NSE提高、RMSE下降，并在1982等年份改善部分偏差。然而融雪不是闸门开度、库水位或全部区间水量的替代物。1979全年低估和连续负误差没有缓解，说明一个季节性变量只能校正与其相关的那部分残差，无法恢复未观测的人为控制或其他水量项。

## 8. 负融雪系数为何不能解释为确认因果

M2C的d在所有fold为负，是预先根据“预测减观测”残差方向设置的约束结果。该变量又曾用六年残差做探索筛选，因此符号一致只表示在当前条件模型和资料中的统计关联。融雪可能与季节、其他区间来水、调度策略或未观测状态共同变化；系数还依赖M2R基线误差定义。没有独立年份、独立物理观测和机制干预，不能把负系数表述为“融雪导致大山口流量下降”的物理因果。

## 9. 闸下控制站需要哪些新增观测

最高优先级不是扩大网络，而是补充决定出流的状态：闸前水位、闸后水位、库水位、闸门开度、发电流量和调度日志。第二优先级是区间水量，包括中间支流或区间站Q、引水、退水及地下水补给代理。若要合法使用水位，还需至少两个非2011年份的可靠大山口日水位和同期测流，并审计逐日Q与H的生成关系。只有这些观测能够区分“上游来水传播”“沿程增减水”和“控制释放”。

## 10. 对虚拟水文站任务设计的启示

首先，必须明确任务身份。P1是历史有站重建，可以用目标历史Q拟合关系；P1B允许目标站本地状态，适合控制站，但必须排查H-Q标签循环；P2不使用目标Q监督，不能用P1高分代替。其次，内部历史期、预注册跨年期与真正未揭示外部年份应分别报告。再次，模型晋升不能只看平均NSE，还应检查逐年RMSE、绝对PBIAS、洪峰、长期连续误差、参数触边和改进是否由单一年份主导。最后，负结果具有设计价值：本研究已把瓶颈从“是否需要更复杂网络”缩小到“是否拥有区间来水和控制状态”。

综上，冻结结论保持不变：**单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。**
"""
    write_text(OUT / "paper_discussion_full_draft_zh.md", discussion)

    methods = f"""# 论文方法章节：实验协议初稿

## 1. 站点与数据来源

研究主链为开都河巴音布鲁克（00705600）—大山口（00705700）。阶段A—C使用`data/raw/runoff/Q-新疆.xls`中的2005支流/干流数据；MQ直接读取`MQ-DSK-2005-SB`列，其外部生成公式不在仓库中。2011资料来自`data/teacher_raw/Doc1.docx`，经人工转录、月均复算、Q≈A×V核查和模式统一形成canonical文件。1978—1983流量来自`BYBLK-DSK日数据.xlsx`，原始两站4382个站日与处理CSV和NPZ逐值一致。

## 2. 时间划分

阶段A/B固定使用2005-01-03至06-30训练、07-01至08-31验证、09-01至10-31测试，测试期61天。阶段C因两站实测Q从5月开始，采用5月起步的五个扩展训练—验证fold，所有设计在9月1日前冻结，9—10月只作一次已揭示历史诊断。D4B主窗口为2011-05-11至08-31，共113天；次要全年外推窗口为01-11至12-31，共355天。D5使用1978—1983外层留一年；共同评分为1978年第61日起、1979—1983年第31日起。

## 3. 目标遮蔽

图模型中，大山口观测Q在所有输入时刻置0，availability置0；训练数据损失和验证早停排除大山口标签。其他缺失值先按训练期统计量标准化，再以0填入并保留availability=0。动态量按站点、按特征、仅用训练期标准化；大山口输出反标准化尺度使用训练期MQ统计量。D5模型允许大山口Q仅作为训练年份标签或外层留出年份评分标签，禁止作为预测输入。

## 4. P1、P1B与P2定义

- **P1：历史有站缺测重建。** 允许用历史大山口Q拟合上游边界—目标关系；部署输入可只含上游Q。阶段C、D4B和D5的边界模型属于P1。
- **P1B：本地状态辅助。** 不把目标Q作为输入，但允许当前或过去的大山口H、闸前后水位或控制状态。必须先审计Q是否由H构造，避免标签循环。本项目因缺少至少两个非2011年份可靠H而保持blocked。
- **P2：严格无目标Q监督。** 不使用大山口Q训练专属关系；阶段A/B按项目口径将MQ参考、无图、自环和原GNN列为P2对照。P1成绩不得宣传为P2能力。

## 5. 图模型

同日节点编码为`z_i(t)=Encoder([Qobs_i(t),QMQ_i(t),availability_i,static_i])`；邻居消息为`m_i(t)=mean_(j→i)(W_m z_j(t)·sigmoid(W_e e_ji))`；更新为`h_i(t)=LayerNorm(z_i(t)+GELU(W_s z_i(t)+m_i(t)))`。输出在标准化空间中采用MQ残差：`Qhat_i=QMQ_i+0.25·tanh(Decoder(h_i))`，并强制非负。图结构消融保持特征、隐藏层、训练轮数、损失和种子7、42、123相同，仅改变边或邻居消息。

## 6. 时滞模型

阶段B计算0—15天Pearson、Spearman和互相关，并建立同日到15日直接边界基线。阶段C比较单一lag、3/7/15日窗口、K=10自由非负分布式时滞和低维平滑核。K10形式为`Q_DSK(t)=b+Σ_(k=0)^10 w_k Q_BYBLK(t-k)`，约束`w_k≥0`。lag和结构仅在2005年9月前的开发fold选择，已揭示61天不参与选择。

## 7. 单储量模型

M2原状态为`S_t=rho S_(t-1)+Q_BYBLK(t)`，输出为非负截断的截距、状态项与当日直达项之和。M2R采用等价归一化：`E_t=rho E_(t-1)+(1-rho)Q_BYBLK(t)`，`Qhat=max(0,b+gE_t+cQ_BYBLK(t))`。参数范围为rho∈[0,0.995]，b∈[-300,300]，g/c∈[0,10]；L-BFGS-B最多500次迭代，训练损失为各训练年份MSE的等权宏平均。

## 8. M2C融雪修正

M2C只在M2R输出中增加`d·Z_t`：`Qhat=max(0,b+gE_t+cQ_BYBLK(t)+dZ_t)`。原始Z为`t-14`至`t-1`区间ERA5-Land融雪量之和，先平移一天，禁止当日和未来值；Z只用当前训练fold目标行的均值和总体标准差标准化。d∈[-300,0]。禁止加入降水、温度、SWE、月份交互、第二储量、神经网络、水位、焉耆、MQ或2011选模信息。

## 9. 嵌套留一年

外层每次留出1978—1983中的一个完整年份。M1核族与初始化仅在剩余五年内部留一年记录中选择；M2公式固定，只在外层训练年份拟合约束参数。1978无前一年暖启动，设状态初值为0并丢弃前60日；1979—1983只用上一日历年最后60天巴音布鲁克Q暖启动，不读取大山口Q。M2C沿用相同外层年份、损失、暖启动、评分日和三次重启。

## 10. 预注册晋升门槛

M1/M2需至少三分之二年份RMSE优于M0、宏平均NSE提高、宏平均RMSE降低、宏平均绝对PBIAS不超过M0加2个百分点、灾难性年份不超过1个，并通过持续触边和参数稳定性检查。M2C相对M2R设置12项门槛，包括至少4/6年降低RMSE、宏平均NSE/RMSE/绝对PBIAS改善、1979低估缓解、1982不明显恶化、无灾难年、参数与融雪系数约束稳定、高流RMSE不恶化超过5%，且提升不由单一年份贡献超过70%。所有门槛在评分前冻结。

## 11. 哈希冻结与预测—评分分离

阶段D4B在读取2011大山口标签前写入评价窗口协议，核验2005参数SHA-256，随后由预测程序只读取参数、日期和2011巴音布鲁克Q并生成预测及哈希；评分程序只读取冻结预测和大山口Q，禁止重算预测。D5第二、三、四轮和D6均以manifest记录文件大小与SHA-256；后续阶段先逐项验证，任何不一致均停止。

## 12. 防止2011反馈选模

2011不参与K、lag、正则化、截距、权重、窗口或M1/M2/M2C结构选择。D5的1978—1983开发明确禁止读取2011 Q/H、D4B月误差和峰值偏差。2011评分后不得删除冬季、改主窗口或补入水位、DEM、焉耆、MQ与GNN。由于2011已经揭示，后续只能作为回顾性诊断，不能再用于声称盲测。
"""
    write_text(OUT / "paper_methods_protocol_draft_zh.md", methods)

    limitations = """# 论文局限性章节初稿

## 1. MQ生成公式无法追溯

MQ只能追溯至2005原始工作簿中的现成列，仓库没有其计算公式、输入变量、参数或整编说明。因此本文可把MQ作为冻结参考序列比较，但不能将其进一步解释为Manning、面积比例、传播时滞或其他特定物理模型，也不能合法重建2011 MQ。

## 2. 历史日界未知

1978—1983和2005数据均以日为时间步，但现有资料没有说明日界是00—24时、08—次日08时还是其他水文日口径。日尺度比较仍可进行，但对0—1日传播差异、闸门日内突变和跨站精确对齐的解释受到限制。

## 3. 历史闸门位置和运行状态不完整

2011资料说明大山口水位经常受闸门启闭影响，但历史工作簿没有明确站点相对闸门的位置，项目也没有闸前/闸后水位、库水位、闸门开度、发电流量或调度日志。模型无法区分自然传播与人为控制。

## 4. 缺少区间支流流量

巴音布鲁克至大山口之间没有可靠的中间站或支流日流量，也缺少引水、退水和地下水补给代理。因此年度水量增益只能由经验参数吸收，无法闭合真实区间水量平衡。

## 5. 缺少多年份DSK水位

项目只有2011年完整、人工复核的大山口日水位，未找到至少两个非2011年份的同期水位与测流。2011已用于诊断，不能再用于选择P1B结构，故水位辅助模型保持blocked。

## 6. 2011逐日Q为临时曲线推求量

Doc1明确记载大山口逐日Q采用临时曲线法推求，主要曲线标准差为2.7%，并非365天逐日直接测流。临时曲线自变量、分期日期、版本和特殊修正规则仍不完整，限制了2011标签的独立物理含义。

## 7. H-Q标签循环风险

若2011逐日Q本身由H-Q临时曲线生成，再以同一H预测逐日Q，模型可能只是在复现整编曲线，而不是独立估计真实流量。48次离散测流虽然有Q、A、V等直接测验要素，但其是否参与临时曲线建立或校核尚未确认。最终H-Q模型必须等待来源审计或使用独立留出的直接测流Q评价。

## 8. 1978—1983不是六次完全独立外部验证

嵌套留一年保证每个外层年份不参与当次参数拟合；然而六个年份来自同一历史资料体系，模型家族和研究问题在整套项目中逐步形成。尤其M2C融雪变量经过六年残差探索筛选，外层年份不是特征选择意义上的独立检验。因此结果应称多年份回顾性稳健性评价。

## 9. 2011已揭示，不能再视为盲测

D4B在一次评分内部实现了预测—评分分离和窗口预注册，但2011资料已人工转录，结果也已查看。它可称预注册跨年份评价，不能称完全盲测、阶段C主模型外部验证或P2严格无站最终结果。

## 10. 缺少全新封闭年份

当前没有一个从未参与开发、诊断或结果查看的完整年份。因而本文能够报告内部诊断、预注册跨年评价和回顾性留一年稳健性，却不能给出最终外部泛化声明。获得新年份后需先冻结任务、模型、预处理、窗口与门槛，再一次性评分。

## 11. 单河段外推需谨慎

研究集中于巴音布鲁克—大山口单一受控河段。普通GNN失败和单储量有限改善受河段长度、资料结构和控制机制影响，不能直接推广至自然河道、其他气候区或不同水库。可推广的是协议层面的经验：区分P1/P1B/P2、隔离目标标签、冻结预测再评分，并把信息缺失与模型容量不足分开诊断。
"""
    write_text(OUT / "paper_limitations_full_draft_zh.md", limitations)

    teacher_script = f"""# 教师汇报讲稿（10—15分钟）

建议总时长约12分钟，主线只讲水文问题、关键证据和下一步选择。代码、参数哈希和完整消融表放在备份页。

## 1. 研究问题（约1分钟）

“老师，我们最初的问题是：当大山口站缺测时，能否利用上游巴音布鲁克和河网关系重建逐日流量。开始时希望把NSE提高到0.8左右，但后续把任务拆开后发现，更重要的是判断这个高分能否跨年份保持，以及模型是否真正使用了水文传播信息。”

## 2. 数据和站点（约1分钟）

“主研究链是巴音布鲁克到大山口。2005年用于原GNN复现和内部诊断；2011年用于一次冻结跨年评价；1978—1983年用于嵌套留一年稳健性检查。任务分为P1历史有站重建、P1B本地水位辅助和P2无目标流量监督，三类结果不互相替代。”

## 3. 原GNN为何失败（约1.5分钟）

“原GNN的真实边NSE只有{fmt(R('A_GNN')['NSE'])}，无图是{fmt(R('A_NG')['NSE'])}，自环是{fmt(R('B1_G1_self_loops')['NSE'])}。把边反向或随机后仍约0.31，说明真实拓扑没有被学成传播。原因是模型只做同日消息传递，边没有距离、坡度、时滞或控制状态，而且多个流域共享同一消息参数。”

## 4. 时滞模型为何跨年下降（约1.5分钟）

“显式K10在2005已揭示61天达到NSE {fmt(R('C_K10_LEGACY')['NSE'])}，看起来超过0.8。但11个lag高度共线，最终只有lag0和lag5两个尖峰，尖峰位置不稳定。冻结后迁移到2011主窗口，NSE降为{fmt(R('D4B_primary')['NSE'])}。这说明高分主要代表同年关系拟合，不能直接当作跨年能力。”

## 5. 储量模型带来的改善（约1分钟）

“我们随后不再增加大网络，而用一个连续储量状态表示历史。M2在六个留出年全部降低RMSE，宏平均NSE从M0的{fmt(macro['M0']['nse'])}提高到{fmt(macro['M2']['nse'])}。rho对应约数周记忆，说明上游影响不是两个孤立lag，而是较长的连续响应。”

## 6. 为什么仍不能晋升（约1分钟）

“虽然过程形状改善，M2宏平均绝对PBIAS为{fmt(r2_decision['models']['M2']['macro_abs_pbias'],2)}%，反而高于M0的{fmt(m0_abs_pbias,2)}%，超过预先允许的2个百分点容差。也就是说，模型能改善涨落，却不能稳定确定每一年该增加或减少多少水量。”

## 7. 融雪变量为何被拒绝（约1分钟）

“M2C只加了过去14日区间融雪，宏平均NSE升到{fmt(macro_m2c['nse'])}、RMSE降到{fmt(macro_m2c['rmse'],2)}。但1979低估由{fmt(next(r for r in m2r if r['year']=='1979')['pbias'],2)}%变为{fmt(next(r for r in m2c if r['year']=='1979')['pbias'],2)}%，连续负误差从115天增至156天。12项门槛只差这一项，因此仍按预注册规则拒绝，而且不再试其他七个气象变量。”

## 8. 2011逐日Q的曲线推求问题（约1分钟）

“Doc1附注明确写着大山口逐日流量采用临时曲线法推求，主要曲线标准差2.7%；逐日水位由自记资料整编，并经常受闸门启闭影响。2011 Q不是每天直接测量。若这个临时曲线本身是H-Q曲线，再用H预测Q会有标签构造循环，所以需要老师帮助确认曲线公式、分期和48次测流是否参与建曲线。”

## 9. 当前最需要补充的资料（约1分钟）

“优先级一是至少两个非2011年份的大山口逐日水位和同期测流；优先级二是闸前后水位、库水位、闸门开度、发电流量或调度日志；优先级三是区间支流、中间站、引水和退水；最后是一个从未参与开发的新完整年份。”

## 10. 下一步决策（约1分钟）

“如果能得到上述任一类信息，我们按预先写好的准入门重新开一个新阶段；如果没有，就停止扩模并完成论文。当前最稳妥的结论不是某个模型已经成功，而是：单一上游流量在缺少区间来水和控制状态时，无法跨年份稳定重建闸下控制站的日流量。”

## 可能追问的简短回答

- **为什么不继续调GNN？** 真边、反向边、随机边都差不多，说明缺的是边的水文信息，而不是层数。
- **0.88还能不能写？** 可以写，但必须标注为P1、2005已揭示历史诊断，不能写成外部或P2成绩。
- **M2是不是成功模型？** 它证明数周记忆有用，但未通过水量偏差门槛，所以是有价值但未晋升的模型。
- **负融雪系数说明什么？** 只说明当前条件残差中的关联方向，不是已确认物理因果。
- **没有新数据怎么办？** 保留所有负结果，按方法学和信息缺失主线完成论文。
"""
    write_text(OUT / "teacher_report_script_zh.md", teacher_script)

    figure_index = """# 教师汇报图表索引

主讲建议只放6—7张图，完整表格保留在`teacher_key_tables.xlsx`。

| 顺序 | 图件 | 汇报用途 | 建议讲法 |
|---:|---|---|---|
| 1 | `outputs/diagnosis_2005_snapshot/stage_d6/plots/model_evidence_overview/nse_evidence_by_protocol.png` | 全研究证据路线 | 强调协议不同，不能把柱形直接当排行榜；重点看K10从2005到2011下降。 |
| 2 | `outputs/diagnosis_2005_snapshot/stage_b/plots/daily_predictions.png` | 原GNN与无图逐日表现 | 指出有向消息没有改善洪峰，且整体继续低估。 |
| 3 | `outputs/diagnosis_2005_snapshot/stage_b/plots/gnn_error_increment.png` | 图边负贡献 | 说明变差不是平均值偶然波动，而是逐日系统性现象。 |
| 4 | `outputs/diagnosis_2005_snapshot/stage_d5/plots/frozen_lag_weights.png` | K10尖峰退化 | 展示11个lag最终只剩lag0和lag5，不能直接解释为旅行时间。 |
| 5 | `outputs/diagnosis_2005_snapshot/stage_d4b/plots/boundary_only_2011_primary_window_timeseries.png` | 2011冻结跨年失败 | 强调预测先冻结、再解封评分；不做事后调参。 |
| 6 | `outputs/diagnosis_2005_snapshot/stage_d5_round2/plots/outer_year_rmse.png` | M0/M1/M2多年份对照 | 说明单储量在6/6年降低RMSE，但这只是晋升条件之一。 |
| 7 | `outputs/diagnosis_2005_snapshot/stage_d5_round4/plots/pbias_by_outer_year.png` | M2C拒绝与年份相反偏差 | 聚焦1979低估和1982高估方向差异，说明固定增益不可识别。 |
| 8（结尾可选） | `outputs/diagnosis_2005_snapshot/stage_d6/plots/model_evidence_overview/new_information_gate.png` | 下一步数据决策 | 四类关键信息均未到位，因此停止扩模、转入论文写作。 |

## 备份图

- `stage_c/plots/rolling_validation_stability.png`：解释低维核历史高分为何仍需跨年检验。
- `stage_d5/plots/lag_correlation_matrix.png`：回答lag共线性问题。
- `stage_d5_round4/plots/rmse_by_outer_year.png`：回答M2C在哪些年份改善。
- `stage_d5_round4/plots/outer_1979_predictions.png`：回答1979是否由单一洪峰造成。
- `stage_d/doc1_electronic/previews/DSK_Daily_Q.png`与`DSK_Measurements.png`：说明逐日Q表和离散测流表是两类资料。

## 不建议主讲展示

不展示代码截图、完整哈希列表、优化重启记录和全部OCR页面。这些内容保留在复现包中，仅在老师追问数据可信度时调出。
"""
    write_text(OUT / "teacher_figure_index_zh.md", figure_index)

    # Comprehensive A-D6 artifact index. D7 is excluded by definition.
    tracked = set()
    for audit in audits:
        tracked.update(x["path"] for x in audit["checks"])
        tracked.add(audit["manifest_path"])
    artifact_rows = []
    for path in sorted(p for p in BASE.rglob("*") if p.is_file() and OUT not in p.parents):
        rp = rel(path)
        artifact_rows.append({
            "stage": stage_for(path),
            "artifact_name": path.name,
            "artifact_type": path.suffix.lower().lstrip(".") or "file",
            "description": describe(path),
            "artifact_path": rp,
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
            "manifest_tracked": rp in tracked,
            "freeze_status": "read_only_A_to_D6",
        })
    artifact_fields = ["stage", "artifact_name", "artifact_type", "description", "artifact_path", "size_bytes", "sha256", "manifest_tracked", "freeze_status"]
    write_csv(OUT / "artifact_index_A_to_D6.csv", artifact_rows, artifact_fields)

    commands = """# 阶段A—D6入口命令索引

以下命令用于说明历史入口，不授权在当前冻结目录重跑。凡会训练、评分或覆盖输出的命令，只能在仓库副本或明确改写到新输出目录后执行。

| 阶段 | 历史入口命令 | 当前是否允许 | 说明 |
|---|---|---|---|
| A | `python scripts/audit_2005_snapshot_gnn.py` | 仅副本复现 | 读取原GNN/无图运行并生成阶段A审计；当前A输出只读。 |
| B1 | `python scripts/diagnose_2005_snapshot_graph.py` | 仅副本复现 | G0—G5结构消融，会训练模型。 |
| B扩展 | `python scripts/run_stage_b_extended_diagnosis.py` | 仅副本复现 | 时滞消息和误差扩展诊断。 |
| C | `python scripts/run_stage_c_boundary_lag_residual.py` | 仅副本复现 | P1显式边界、时滞、核与残差比较。 |
| D2 | `python .codex_tmp/run_stage_d2_diagnostics.py` | 允许只读核验；不得覆盖 | Doc1水力与OCR人工复核准备。临时脚本路径应在正式发布前归档。 |
| D3 | `python .codex_tmp/build_stage_d3_2011.py` | 不得覆盖 | 2011结构化和人工确认数据构建。 |
| D4A | `python .codex_tmp/build_stage_d4a.py` | 不得覆盖 | 坐标、断面、焉耆和边界参数冻结。 |
| D4B-模式 | `python scripts/prepare_stage_d4b_canonical.py` | 不得覆盖 | 统一2011流量、水位与测流模式。 |
| D4B-预测 | `python scripts/generate_boundary_only_2011_predictions.py` | 禁止重跑正式预测 | 原预测程序不读取2011 DSK标签；正式预测已冻结。 |
| D4B-评分 | `python scripts/score_boundary_only_2011.py` | 禁止第二次正式评分 | 2011已揭示，只可核验现有文件。 |
| D5第一轮 | `python scripts/run_stage_d5_round1.py` | 仅只读复核 | K10共线、MQ来源、水位代理和后续协议准备。 |
| D5第二轮来源 | `python scripts/audit_stage_d5_round2_sources.py` | 允许在副本核验 | 1978—1983全量逐值来源审计。 |
| D5第二轮模型 | `python scripts/run_stage_d5_round2_nested_loyo.py` | 禁止当前阶段重跑 | M0/M1/M2嵌套留一年。 |
| D5第二轮封装 | `python scripts/finalize_stage_d5_round2.py` | 禁止覆盖 | 生成报告、工作簿和34项manifest。 |
| D5第三轮 | `python scripts/run_stage_d5_round3_diagnostics.py` | 仅副本诊断 | M2等价参数化、记忆和新增信息准入，不训练新模型。 |
| D5第三轮封装 | `python scripts/finalize_stage_d5_round3.py` | 禁止覆盖 | 生成28项manifest。 |
| D5第四轮准备 | `python scripts/prepare_stage_d5_round4.py` | 禁止重跑 | 冻结M2C单一候选和协议。 |
| D5第四轮模型 | `python scripts/run_stage_d5_round4_nested_loyo.py` | 明确禁止 | M2C已拒绝，不得重新训练或尝试其他气象变量。 |
| D5第四轮封装 | `python scripts/finalize_stage_d5_round4.py` | 禁止覆盖 | 生成29项manifest。 |
| D6 | `python scripts/run_stage_d6_research_closure.py` | 禁止覆盖 | 形成18项冻结研究结论。 |
| 冻结核验 | `python scripts/verify_stage_d6_freeze.py` | 允许 | 只读核验D6与D5第二至四轮，不写实验输出。 |

## 安全复现原则

1. 先复制仓库或设置新的输出根目录，绝不删除或覆盖`outputs/diagnosis_2005_snapshot`既有阶段。
2. D4B预测与评分顺序必须保持分离；2011已揭示，重跑只能称技术复现，不能再称预注册评价。
3. D5第四轮M2C禁止重跑；若未来获得新数据，应另开阶段并先写预注册，不得修改既有拒绝结论。
4. 所有复现先运行冻结核验；任何哈希不一致都应停止并查明原因。
"""
    write_text(OUT / "command_index_A_to_D6.md", commands)

    repro = f"""# REPRODUCIBILITY_D6

## 1. 复现范围

本说明封装阶段A—D6已经完成的审计、诊断、训练、冻结预测、评分与研究结论。D6最终决策为`{go_no_go['decision']}`。本阶段不重新运行任何模型；复现分为“只读完整性验证”和“在独立副本中的技术复现”两种。后者不能改变原结果的评价身份。

## 2. 当前冻结入口

在项目根目录运行：

```powershell
C:\\Users\\gytt\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe scripts/verify_stage_d6_freeze.py
```

预期D6为18项、D5第四轮29项、第三轮28项、第二轮34项，全部`hash_match=true`且进程退出码为0。详细逐文件结果见`outputs/diagnosis_2005_snapshot/stage_d7/d6_immutability_audit.json`。

## 3. 关键输入

- `data/raw/runoff/Q-新疆.xls`：2005支流/干流观测与现成MQ列。
- `data/raw/runoff/BYBLK-DSK日数据.xlsx`：1978—1983巴音布鲁克和大山口日流量。
- `data/teacher_raw/Doc1.docx`：2011八站年鉴扫描表。
- `data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz`：阶段A/B图模型张量。
- `outputs/diagnosis_2005_snapshot/stage_d5_round2/multiyear_byblk_dsk_daily_canonical.csv`：D5多年份冻结流量。
- `data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc`：M2C唯一允许的区间融雪来源。

## 4. 输出目录与协议

- A/B：`outputs/diagnosis_2005_snapshot/`根目录、`graph_runs/`和`stage_b/`；固定2005内部61天协议。
- C：`stage_c/`；P1历史有站边界与时滞，61天为已揭示诊断。
- D1—D4A：`stage_d/`、`stage_d3/`、`stage_d4a/`；Doc1电子化、人工复核、坐标/断面与参数冻结。
- D4B：`stage_d4b/`；P1预注册2011跨年评价，预测—评分分离。
- D5：`stage_d5/`、`stage_d5_round2/3/4/`；K10归因、1978—1983嵌套留一年、M2R和M2C开发性评价。
- D6：`stage_d6/`；统一登记、来源循环审计、科研结论和停止扩模决定。

## 5. 关键冻结哈希

- D6 manifest：`{audits[0]['manifest_sha256']}`。
- D5第四轮 manifest：`{audits[1]['manifest_sha256']}`。
- D5第三轮 manifest：`{audits[2]['manifest_sha256']}`。
- D5第二轮 manifest：`{audits[3]['manifest_sha256']}`。
- 2005 boundary-only参数：`{r2_protocol['M0_expected_sha256']}`。
- 1978—1983 canonical流量：`{r2_protocol['canonical_sha256']}`。
- M2C区间ERA5输入：`{r4_protocol['era5_interval_sha256']}`。

## 6. 允许与禁止重跑

允许：只读哈希核验、CSV模式/日期唯一性核验、报告渲染、工作簿公式检查，以及在完全独立副本中的技术复现。禁止：覆盖A—D6输出、第二次正式2011评分、重新训练M2C、测试其他气象变量、开发M3、恢复普通GNN或生成新的正式NSE。完整入口见`command_index_A_to_D6.md`。

## 7. 数据与标签边界

阶段A/B的大山口Q被输入遮蔽且不参与训练/早停；阶段C及D5的P1模型允许历史大山口Q作为拟合标签，但不作为部署输入；P1B尚未准入；P2结果不能由P1高分替代。2011预测文件在读取大山口评分标签前冻结。1978—1983每个外层留出年不参与当次拟合，但M2C候选曾通过六年残差探索筛选，因此不是完全独立特征检验。

## 8. 已知不可复现项

MQ的外部生成公式、参数和原始计算过程缺失，只能复现对现成MQ列的读取与评分。历史水文日边界、质量标志和大山口相对闸门位置不完整。2011大山口逐日Q虽确认由临时曲线推求，但曲线自变量、分期、版本及测流控制点关系未完全确认。早期CUDA训练可在同环境数值复现到约1e-8，但未启用全套确定性算法，不能保证跨硬件逐位一致。

## 9. 工件定位

`artifact_index_A_to_D6.csv`逐文件记录阶段、类型、路径、大小、SHA-256、是否被轮次manifest跟踪及只读状态。论文和教师材料只引用冻结工件，不复制或更改原实验文件。
"""
    write_text(OUT / "REPRODUCIBILITY_D6.md", repro)

    env_lines = [
        "Stage D7 environment snapshot",
        f"captured_utc={datetime.now(timezone.utc).isoformat()}",
        f"workspace_root={ROOT}",
        f"platform={platform.platform()}",
        f"machine={platform.machine()}",
        f"processor={platform.processor()}",
        f"writer_python_executable={sys.executable}",
        f"writer_python_version={sys.version.replace(chr(10), ' ')}",
        "git_metadata=unavailable (.git directory contains no repository metadata)",
        "",
        "Python launcher inventory:",
        command_output(["py", "-0p"]),
        "",
        "Bundled Python key packages:",
        command_output([sys.executable, "-c", "import importlib; mods=['numpy','pandas','scipy','sklearn','torch','matplotlib','docx'];\nfor m in mods:\n try:\n  x=importlib.import_module(m); print(m+'='+str(getattr(x,'__version__','installed')))\n except Exception as e: print(m+'=unavailable:'+type(e).__name__)"]),
        "",
        "Node runtime:",
        command_output([r"C:\Users\gytt\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe", "--version"]),
        "artifact_tool_runtime=workspace bundled dependencies, version family 2.8.6+",
        "",
        "GPU inventory:",
        command_output(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"]),
        "",
        "Frozen manifest SHA-256:",
        *[f"{a['name']}={a['manifest_sha256']}" for a in audits],
    ]
    for candidate in [
        ROOT / "data/raw/runoff/Q-新疆.xls",
        ROOT / "data/teacher_raw/Doc1.docx",
        BASE / "stage_d5_round2/multiyear_byblk_dsk_daily_canonical.csv",
        BASE / "stage_d4a/boundary_only_frozen_parameters_2005.json",
    ]:
        if candidate.exists():
            env_lines.append(f"input_sha256 {rel(candidate)}={sha256(candidate)}")
    write_text(OUT / "environment_snapshot.txt", "\n".join(env_lines))

    reopen = """# 重新开模准入门

当前状态为`stop_model_expansion_and_write`。只有获得下列A—E任一类真实新增资料，完成来源审计并在查看新标签结果前冻结协议，才允许另开新阶段。既有A—D6结果始终保留，不得用新模型覆盖或重命名。

## A. 至少两个非2011年份可靠DSK逐日水位及同期测流

- **可开启模型：** P1B水位辅助边界模型、分期H-Q诊断或有界本地状态修正。
- **任务身份：** P1B，不是P2；若使用历史DSK Q拟合则还含P1监督。
- **预注册要求：** 先确认日Q是否由H生成、评级曲线版本、测流是否参与建曲线；冻结输入时刻、年份划分、H缺失处理、曲线循环排除方案和评价指标。
- **必须保留：** 2011已揭示状态、D4B冻结结果、D6循环风险结论和所有P1/P2对照。

## B. 闸前/闸后水位、库水位、闸门开度或调度日志

- **可开启模型：** 控制状态识别、边界时滞＋有界控制修正、发电/泄洪分支模型。
- **任务身份：** 有目标站本地状态时为P1B；若状态来自独立水库系统，应明确实时可用性。
- **预注册要求：** 冻结状态变量含义、时间对齐、可用延迟、状态分类名称、缺失策略和控制前后评价窗口；自动聚类不得直接命名为真实闸门开度。
- **必须保留：** 普通GNN负贡献、M0—M2C全部失败年份及M2C拒绝决定。

## C. 可靠区间支流或中间站流量

- **可开启模型：** 多边界水量平衡、区间来水模型或受约束路由模型。
- **任务身份：** 通常为P1；若所有关系只在其他河段监督且不使用DSK Q，可另行定义P2协议。
- **预注册要求：** 冻结站点拓扑、上下游方向、时间滞后、汇水面积/单位换算、缺失处理和是否允许当日信息；不得用新年份DSK结果挑站。
- **必须保留：** 单一上游模型的结论，作为新增区间信息的基线和消融对照。

## D. 多年份焉耆或其他下游Q，且任务明确为历史重建

- **可开启模型：** 双边界历史事后重建、平滑器或缺测段插补。
- **任务身份：** P1历史重建；因为使用下游未来/同日信息，不属于实时P2预测。
- **预注册要求：** 明确是否允许未来信息、重建区间、边界可用性、留年方式和部署用途；结果名称必须包含“历史事后重建”。
- **必须保留：** D6对实时预测与历史重建的任务边界，不能把双向结果与单向部署结果直接比较。

## E. 一个从未参与开发的新完整年份

- **可开启模型：** 只允许对当前冻结候选做一次最终封闭评价；若同时带A—C新变量，应先在不含该年的历史资料上完成模型和门槛冻结。
- **任务身份：** 取决于输入：仅上游Q为P1跨年迁移；有目标H/控制状态为P1B；无目标监督且输入满足严格定义时才可称P2。
- **预注册要求：** 在读取目标Q前冻结参数文件、输入哈希、预处理、评价窗口、缺失/边界日策略和评分程序；预测文件先生成哈希，再解封标签一次评分。
- **必须保留：** 2011预注册评价和1978—1983回顾性结果；新年份不能用于回头选择lag、变量或窗口。

## 未达到准入门时

如果新增资料只有气温、降水、更多ERA5变量、同一2011水位或已揭示年份标签，不构成重新开模条件。继续执行论文收束，不开发M3、不恢复普通GNN、不重新训练M2C。
"""
    write_text(OUT / "model_reopen_gate_zh.md", reopen)

    # D7 manifest is finalized after the workbook exists; rerunning this script then includes it.
    files = [p for p in OUT.rglob("*") if p.is_file() and p.name != "stage_d7_manifest.json"]
    manifest = {
        "stage": "D7",
        "source_freeze_all_passed": all_passed,
        "decision_inherited": go_no_go["decision"],
        "new_model_trained": False,
        "new_NSE_generated": False,
        "stages_A_to_D6_modified": False,
        "file_count": len(files),
        "files": [{"file_path": rel(p), "file_size": p.stat().st_size, "sha256": sha256(p)} for p in sorted(files)],
    }
    (OUT / "stage_d7_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
