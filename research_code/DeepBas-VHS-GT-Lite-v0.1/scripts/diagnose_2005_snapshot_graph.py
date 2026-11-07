from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from vhs.metrics import regression_metrics


BASE = Path("outputs/virtual_station_mainline/multisite_2005")
OUT = Path("outputs/diagnosis_2005_snapshot")
RUNS = OUT / "graph_runs"
DATA = Path("data/processed/virtual_station_multisite")
SEEDS = [7, 42, 123]
AREA_RATIO = 18641.1 / 6773.1


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def metric_path(structure: str, seed: int) -> Path:
    if structure == "G0_no_graph":
        return BASE / f"snapshot_nograph_seed{seed}" / "test_metrics.json"
    if structure == "G2_true_directed":
        return BASE / f"snapshot_gnn_seed{seed}" / "test_metrics.json"
    return RUNS / structure / f"seed{seed}" / "test_metrics.json"


def prediction_path(structure: str, seed: int) -> Path:
    if structure == "G0_no_graph":
        return BASE / f"snapshot_nograph_seed{seed}" / "test_predictions.csv"
    if structure == "G2_true_directed":
        return BASE / f"snapshot_gnn_seed{seed}" / "test_predictions.csv"
    return RUNS / structure / f"seed{seed}" / "test_predictions.csv"


def nse(obs: pd.Series, pred: pd.Series) -> float:
    return regression_metrics(obs.to_numpy(float), pred.to_numpy(float))["nse"]


def build_graph_ablation() -> pd.DataFrame:
    structures = [
        "G0_no_graph", "G1_self_loops", "G2_true_directed",
        "G3_reversed", "G4_random", "G5_self_transform_only",
    ]
    rows = []
    for structure in structures:
        by_seed = [load_json(metric_path(structure, seed)) for seed in SEEDS]
        row = {"structure": structure, "seeds": "7|42|123"}
        for key in ["nse", "rmse", "mae", "kge", "pbias", "corr"]:
            values = np.asarray([item[key] for item in by_seed], dtype=float)
            row[f"{key}_mean"] = values.mean()
            row[f"{key}_std"] = values.std(ddof=0)
        rows.append(row)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "graph_edge_ablation.csv", index=False)
    return frame


def discharge_wide() -> pd.DataFrame:
    frame = pd.read_csv(DATA / "multisite_discharge_2005.csv", parse_dates=["date"])
    observed = frame.pivot(index="date", columns="station_code", values="observed_q_m3s")
    physical = frame.pivot(index="date", columns="station_code", values="physical_reference_q_m3s")
    observed.columns = [f"obs_{column}" for column in observed.columns]
    physical.columns = [f"physical_{column}" for column in physical.columns]
    return observed.join(physical, how="outer").sort_index()


def lag_diagnosis(wide: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    source = wide.obs_BYBLK
    target = wide.obs_DSK
    development_mask = wide.index <= pd.Timestamp("2005-08-31")
    test_mask = wide.index >= pd.Timestamp("2005-09-01")
    development_threshold = float(target[development_mask].quantile(0.80))
    rows = []
    for split, split_mask in [("development", development_mask), ("test", test_mask)]:
        for regime in ["all", "normal", "high"]:
            for lag in range(16):
                aligned = pd.DataFrame({"upstream": source.shift(lag), "target": target})
                aligned = aligned.loc[split_mask].dropna()
                if regime == "high":
                    aligned = aligned.loc[aligned.target > development_threshold]
                elif regime == "normal":
                    aligned = aligned.loc[aligned.target <= development_threshold]
                if len(aligned) < 3:
                    continue
                pearson = float(aligned.upstream.corr(aligned.target, method="pearson"))
                spearman = float(spearmanr(aligned.upstream, aligned.target).correlation)
                upz = (aligned.upstream - aligned.upstream.mean()) / aligned.upstream.std(ddof=0)
                tgz = (aligned.target - aligned.target.mean()) / aligned.target.std(ddof=0)
                cross = float(np.mean(upz * tgz))
                raw_metrics = regression_metrics(aligned.target, aligned.upstream)
                area_metrics = regression_metrics(aligned.target, AREA_RATIO * aligned.upstream)
                rows.append({
                    "split": split, "flow_regime": regime, "lag_days": lag, "n": len(aligned),
                    "pearson": pearson, "spearman": spearman, "cross_correlation": cross,
                    "raw_upstream_nse": raw_metrics["nse"], "raw_upstream_rmse": raw_metrics["rmse"],
                    "area_scaled_nse": area_metrics["nse"], "area_scaled_rmse": area_metrics["rmse"],
                    "area_ratio": AREA_RATIO,
                })
    frame = pd.DataFrame(rows)
    frame.to_csv(OUT / "lag_diagnosis.csv", index=False)
    dev = frame.loc[frame.split.eq("development")]
    best = {}
    for regime in ["all", "normal", "high"]:
        part = dev.loc[dev.flow_regime.eq(regime)]
        best[regime] = {
            "pearson_lag": int(part.loc[part.pearson.idxmax(), "lag_days"]),
            "spearman_lag": int(part.loc[part.spearman.idxmax(), "lag_days"]),
            "cross_correlation_lag": int(part.loc[part.cross_correlation.idxmax(), "lag_days"]),
            "raw_nse_lag": int(part.loc[part.raw_upstream_nse.idxmax(), "lag_days"]),
            "area_nse_lag": int(part.loc[part.area_scaled_nse.idxmax(), "lag_days"]),
        }
    return frame, {"development_high_flow_threshold_m3s": development_threshold, "selected_on_development_only": best}


def ensemble_prediction(structure: str) -> pd.DataFrame:
    frames = []
    for seed in SEEDS:
        frame = pd.read_csv(prediction_path(structure, seed), parse_dates=["date"])
        frames.append(frame.set_index("date").predicted.rename(str(seed)))
    return pd.concat(frames, axis=1).mean(axis=1).rename(structure)


def error_diagnosis(wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    test = wide.loc["2005-09-01":"2005-10-31", ["obs_DSK", "physical_DSK", "obs_BYBLK"]].copy()
    test = test.rename(columns={"obs_DSK": "observed", "physical_DSK": "physical", "obs_BYBLK": "upstream"})
    test = test.join(ensemble_prediction("G0_no_graph").rename("no_graph"))
    test = test.join(ensemble_prediction("G2_true_directed").rename("directed_gnn"))
    q1, q2 = test.observed.quantile([1 / 3, 2 / 3]).tolist()
    test["flow_regime"] = pd.cut(test.observed, [-np.inf, q1, q2, np.inf], labels=["low", "middle", "high"], include_lowest=True)
    rows = []
    for model in ["physical", "no_graph", "directed_gnn"]:
        for regime, group in test.groupby("flow_regime", observed=False):
            metrics = regression_metrics(group.observed, group[model])
            rows.append({"model": model, "flow_regime": str(regime), **metrics,
                         "mean_error": float((group[model] - group.observed).mean())})
    regime = pd.DataFrame(rows)
    regime.to_csv(OUT / "error_by_flow_regime.csv", index=False)

    top_rows = []
    for model in ["physical", "no_graph", "directed_gnn"]:
        ranked = test.assign(abs_error=(test[model] - test.observed).abs(), error=test[model] - test.observed).nlargest(10, "abs_error")
        for date, row in ranked.iterrows():
            top_rows.append({"model": model, "date": date.date(), "observed_q": row.observed,
                             "predicted_q": row[model], "error": row.error, "abs_error": row.abs_error,
                             "flow_regime": str(row.flow_regime)})
    top = pd.DataFrame(top_rows)
    top.to_csv(OUT / "largest_error_dates.csv", index=False)

    test["abs_error_no_graph"] = (test.no_graph - test.observed).abs()
    test["abs_error_directed"] = (test.directed_gnn - test.observed).abs()
    test["gnn_minus_no_graph"] = test.directed_gnn - test.no_graph
    test["gnn_extra_abs_error"] = test.abs_error_directed - test.abs_error_no_graph
    test["upstream_daily_change"] = test.upstream.diff()
    jump_threshold = float(test.upstream.diff().abs().quantile(0.80))
    test["upstream_flow_jump"] = test.upstream_daily_change.abs() >= jump_threshold
    test["any_input_missing"] = test[["observed", "physical", "upstream", "no_graph", "directed_gnn"]].isna().any(axis=1)
    worse = test.loc[test.gnn_extra_abs_error > 0].sort_values("gnn_extra_abs_error", ascending=False)
    worse.to_csv(OUT / "gnn_worse_dates.csv", index_label="date")

    peaks = {}
    observed_peak_date = test.observed.idxmax()
    observed_peak = float(test.observed.max())
    for model in ["physical", "no_graph", "directed_gnn"]:
        date = test[model].idxmax()
        peaks[model] = {
            "peak_date": str(date.date()),
            "timing_error_days": int((date - observed_peak_date).days),
            "peak_q": float(test.loc[date, model]),
            "amplitude_bias_at_own_peak_percent": float(100 * (test.loc[date, model] - observed_peak) / observed_peak),
            "amplitude_bias_on_observed_peak_date_percent": float(100 * (test.loc[observed_peak_date, model] - observed_peak) / observed_peak),
        }
    peak_info = {"observed_peak_date": str(observed_peak_date.date()), "observed_peak_q": observed_peak,
                 "models": peaks, "worse_day_count": int(len(worse)), "test_days": int(len(test)),
                 "worse_days_with_upstream_jump": int(worse.upstream_flow_jump.sum()),
                 "input_missing_days": int(test.any_input_missing.sum()), "upstream_jump_threshold_m3s": jump_threshold}
    return regime, top, peak_info, test


def plots(test: pd.DataFrame, regime: pd.DataFrame, lag: pd.DataFrame, lag_info: dict) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(12, 5))
    for column, label, color in [("observed", "Observed DSK", "black"), ("physical", "Physical MQ", "#64748b"),
                                 ("no_graph", "No graph", "#2563eb"), ("directed_gnn", "Directed GNN", "#dc2626")]:
        ax.plot(test.index, test[column], label=label, color=color, linewidth=2 if column == "observed" else 1.5)
    ax.set_ylabel("Discharge (m3/s)"); ax.legend(ncol=4); ax.set_title("DSK 61-day test predictions")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(OUT / "predictions_61day.png", dpi=180); plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.axhline(0, color="black", linewidth=0.8); ax.plot(test.index, test.gnn_minus_no_graph, color="#7c3aed")
    ax.set_ylabel("GNN - no graph (m3/s)"); ax.set_title("Daily effect of directed messages")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(OUT / "gnn_minus_nograph_daily.png", dpi=180); plt.close(fig)

    best_lag = lag_info["selected_on_development_only"]["all"]["pearson_lag"]
    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.plot(test.index, test.observed, color="black", label="DSK observed")
    aligned = test.upstream.shift(best_lag)
    ax.plot(test.index, aligned, color="#16a34a", label=f"BYBLK shifted {best_lag}d")
    ax.plot(test.index, AREA_RATIO * aligned, color="#f59e0b", label=f"Area-scaled shifted {best_lag}d")
    ax.set_ylabel("Discharge (m3/s)"); ax.legend(); ax.set_title("Lag alignment selected on development period")
    fig.autofmt_xdate(); fig.tight_layout(); fig.savefig(OUT / "upstream_target_lag_alignment.png", dpi=180); plt.close(fig)

    pivot = regime.pivot(index="flow_regime", columns="model", values="rmse").reindex(["low", "middle", "high"])
    fig, ax = plt.subplots(figsize=(8, 4.5)); pivot.plot(kind="bar", ax=ax, color=["#64748b", "#2563eb", "#dc2626"])
    ax.set_ylabel("RMSE (m3/s)"); ax.set_title("Error by observed-flow regime"); ax.set_xlabel("")
    fig.tight_layout(); fig.savefig(OUT / "error_by_flow_regime.png", dpi=180); plt.close(fig)

    test_lag = lag[(lag.split == "test") & (lag.flow_regime == "all")]
    fig, ax = plt.subplots(figsize=(8, 4.5)); ax.plot(test_lag.lag_days, test_lag.raw_upstream_nse, marker="o", label="Raw upstream NSE")
    ax.plot(test_lag.lag_days, test_lag.area_scaled_nse, marker="o", label="Area-scaled NSE")
    ax2 = ax.twinx(); ax2.plot(test_lag.lag_days, test_lag.raw_upstream_rmse, linestyle="--", color="#16a34a", label="Raw upstream RMSE")
    ax.set_xlabel("Lag (days)"); ax.set_ylabel("NSE"); ax2.set_ylabel("RMSE (m3/s)"); ax.set_title("Lag baseline diagnostics (test; not used for selection)")
    lines, labels = ax.get_legend_handles_labels(); lines2, labels2 = ax2.get_legend_handles_labels(); ax.legend(lines + lines2, labels + labels2, loc="best")
    fig.tight_layout(); fig.savefig(OUT / "lag_nse_rmse_curve.png", dpi=180); plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    graph = build_graph_ablation()
    wide = discharge_wide()
    lag, lag_info = lag_diagnosis(wide)
    regime, top, peak_info, test = error_diagnosis(wide)
    plots(test, regime, lag, lag_info)

    g = graph.set_index("structure")
    physical_metrics = regression_metrics(test.observed, test.physical)
    no_graph_metrics = regression_metrics(test.observed, test.no_graph)
    directed_metrics = regression_metrics(test.observed, test.directed_gnn)
    high = regime[regime.flow_regime.eq("high")].set_index("model")
    lag_all = lag[(lag.split == "development") & (lag.flow_regime == "all")]
    best_corr_row = lag_all.loc[lag_all.pearson.idxmax()]
    best_raw_row = lag_all.loc[lag_all.raw_upstream_nse.idxmax()]
    best_area_row = lag_all.loc[lag_all.area_scaled_nse.idxmax()]
    variants = load_json(RUNS / "graph_variants.json")

    report = f"""# 2005年同日快照GNN阶段B：图边降低NSE的诊断

## 1. 约束与协议

所有G0—G5实验保持原动态/静态特征、48维隐藏层、100轮上限、早停15轮、节点遮蔽概率0.35、学习率、损失、2005年训练/验证/61天测试划分以及随机种子7/42/123不变。结构选择没有使用测试标签；随机边由固定种子20260728在训练前生成。

## 2. B1图结构对照

| 结构 | NSE均值±标准差 | RMSE均值±标准差 | KGE均值±标准差 |
|---|---:|---:|---:|
| G0 独立无图 | {g.loc['G0_no_graph','nse_mean']:.3f}±{g.loc['G0_no_graph','nse_std']:.3f} | {g.loc['G0_no_graph','rmse_mean']:.2f}±{g.loc['G0_no_graph','rmse_std']:.2f} | {g.loc['G0_no_graph','kge_mean']:.3f}±{g.loc['G0_no_graph','kge_std']:.3f} |
| G1 仅自环 | {g.loc['G1_self_loops','nse_mean']:.3f}±{g.loc['G1_self_loops','nse_std']:.3f} | {g.loc['G1_self_loops','rmse_mean']:.2f}±{g.loc['G1_self_loops','rmse_std']:.2f} | {g.loc['G1_self_loops','kge_mean']:.3f}±{g.loc['G1_self_loops','kge_std']:.3f} |
| G2 真实有向边 | {g.loc['G2_true_directed','nse_mean']:.3f}±{g.loc['G2_true_directed','nse_std']:.3f} | {g.loc['G2_true_directed','rmse_mean']:.2f}±{g.loc['G2_true_directed','rmse_std']:.2f} | {g.loc['G2_true_directed','kge_mean']:.3f}±{g.loc['G2_true_directed','kge_std']:.3f} |
| G3 真实边反向 | {g.loc['G3_reversed','nse_mean']:.3f}±{g.loc['G3_reversed','nse_std']:.3f} | {g.loc['G3_reversed','rmse_mean']:.2f}±{g.loc['G3_reversed','rmse_std']:.2f} | {g.loc['G3_reversed','kge_mean']:.3f}±{g.loc['G3_reversed','kge_std']:.3f} |
| G4 固定随机边 | {g.loc['G4_random','nse_mean']:.3f}±{g.loc['G4_random','nse_std']:.3f} | {g.loc['G4_random','rmse_mean']:.2f}±{g.loc['G4_random','rmse_std']:.2f} | {g.loc['G4_random','kge_mean']:.3f}±{g.loc['G4_random','kge_std']:.3f} |
| G5 关闭邻居消息 | {g.loc['G5_self_transform_only','nse_mean']:.3f}±{g.loc['G5_self_transform_only','nse_std']:.3f} | {g.loc['G5_self_transform_only','rmse_mean']:.2f}±{g.loc['G5_self_transform_only','rmse_std']:.2f} | {g.loc['G5_self_transform_only','kge_mean']:.3f}±{g.loc['G5_self_transform_only','kge_std']:.3f} |

G1和G5保留图层自身变换却不引入其他节点信息；它们优于G2，说明主要损害来自邻居消息，而不是“多一层网络”本身。G3反向后DSK不再接收BYBLK，G4随机边也不连接DSK；两者因此是额外的无邻居对照。随机边索引为 `{variants['variants']['G4_random']}`。

## 3. B2时间错位

当前G2使用 `Q_BYBLK(t) -> hidden_DSK(t) -> Q_DSK(t)`，没有历史窗口。开发期0—15天诊断中，全流量Pearson最高的lag为{int(best_corr_row.lag_days)}天（r={best_corr_row.pearson:.3f}）；普通期和高流期的开发期最佳lag分别见 `lag_diagnosis.csv`，阈值为DSK开发期80%分位数 {lag_info['development_high_flow_threshold_m3s']:.2f} m³/s。

不使用目标标签拟合参数的L0—L15直接上游基线中，开发期原始上游流量NSE最高lag为{int(best_raw_row.lag_days)}天（NSE={best_raw_row.raw_upstream_nse:.3f}），面积比例×上游流量最高lag为{int(best_area_row.lag_days)}天（NSE={best_area_row.area_scaled_nse:.3f}）。面积比例为 {AREA_RATIO:.6f}。测试期所有lag只作事后诊断，没有用于选择结构或超参数。

## 4. B3边界条件实现

当前数学实现是：

`z_i(t)=Encoder([Qobs_i(t), QMQ_i(t), availability_i, static_i])`

`m_i(t)=mean_{{j->i}}(Wm z_j(t) * sigmoid(We e_ji))`

`h_i(t)=LayerNorm(z_i(t)+GELU(Ws z_i(t)+m_i(t)))`

`Qhat_i(t)=QMQ_i(t)+0.25*tanh(Decoder(h_i(t)))`（在逐站标准化空间中）。

因此BYBLK流量只是普通节点特征，经隐藏向量和共享消息层进入DSK；它没有先形成满足连续性或传播关系的基础流量。当前实现属于“较弱的普通特征图聚合”，不属于明确的上游边界条件实现。

## 5. B4误差结构

三种子逐日均值结果：physical NSE={physical_metrics['nse']:.3f}，无图NSE={no_graph_metrics['nse']:.3f}，有向GNN NSE={directed_metrics['nse']:.3f}。高流量区RMSE分别为：physical {high.loc['physical','rmse']:.2f}、无图 {high.loc['no_graph','rmse']:.2f}、有向GNN {high.loc['directed_gnn','rmse']:.2f} m³/s。

实测最大洪峰发生在 {peak_info['observed_peak_date']}，Q={peak_info['observed_peak_q']:.1f} m³/s。各模型峰值日期、时间偏差和幅度偏差已记录在本报告配套诊断数据中；完整十大误差日期见 `largest_error_dates.csv`。

有向GNN在 {peak_info['worse_day_count']}/{peak_info['test_days']} 天的绝对误差大于无图模型，其中 {peak_info['worse_days_with_upstream_jump']} 天同时属于上游流量变化最大的20%。测试输入缺失天数为 {peak_info['input_missing_days']}；因此GNN劣化不能归因于BYBLK/DSK测试输入缺失。当前数据包没有气象变量、闸门运行或实测调控记录，无法把具体误差日期归因于异常气象或水库操作；只能标记流量突变关联。

三种预测均存在负PBIAS，主要问题是系统性低估；有向消息进一步降低预测，尤其在高流量区扩大误差。图见 `predictions_61day.png`、`gnn_minus_nograph_daily.png`、`upstream_target_lag_alignment.png`、`error_by_flow_regime.png` 和 `lag_nse_rmse_curve.png`。

## 6. B5数据和实现检查

1. 日期：节点时间轴来自同一日历索引，没有发现数组错一行；问题在于设计上强制同日传播，而不是数据文件意外错位。
2. 节点顺序：NPZ顺序与edge_index一致，`[BYBLK, DSK, ALAR, XQM, AQK]`；真实边索引为 `{variants['base_edges_index']}`，方向source→target正确。
3. 边属性：构包时丢弃了已知的212.61 km距离，全部赋1；标准化后全部为0，边门只能形成共享常数门。
4. 标准化：动态量逐站逐特征标准化，没有直接混淆站间量级；但输出尺度由MQ而非观测Q确定，且共享权重仍同时服务两个流域。
5. 目标掩码：DSK观测输入在训练、验证、测试均置0且availability=0；训练标签排除DSK，测试只评分DSK，逻辑一致。
6. 缺失填0：零值配有availability=0，不与真实0完全不可区分；但网络仍可能学习到零填充值。测试期BYBLK、DSK无缺失，塔里木节点10月29—31缺失且与DSK无图路径连接。
7. 过度平滑：只有一层消息，不能证明深层经典过平滑；但G1/G5优于G2，证明一次邻居混合已经有害。
8. physical锚点：MQ没有被覆盖，始终通过残差直连；但消息层改变残差项，实际把预测进一步推离MQ。
9. 测试洪峰：61天包含少量高流量日，NSE损失集中在高流区，详见分区CSV；这不是泛泛的“样本少”，而是高流误差的平方权重主导NSE。
10. 泄漏：测试标签不参与训练和早停；早停只看非目标节点验证MSE。反过来，这也意味着选模目标与DSK最终表现不一致。

## 7. 有证据支持的问题排序

1. **同日、无传播尺度的邻居消息是首要问题。** G2显著低于G1/G5；边属性归零；开发期lag诊断显示最佳相关并非由模型显式建模。
2. **上游Q没有作为物理边界，只是普通隐藏特征。** 消息修正系统性把结果推离MQ，高流区RMSE增加，且三种子删边贡献均为负。
3. **共享训练目标与DSK任务错位。** 两个不连通流域共享消息参数，早停只看非目标节点；反向/随机/无邻居结构对DSK并不更差，说明“真实拓扑”未在当前目标函数中被学成DSK有效关系。

## 阶段B停止点

阶段B仅完成结构、时滞、边界、误差和实现诊断。没有更改核心模型，也没有用测试标签选择超参数，更没有实现新复杂模型。
"""
    (OUT / "diagnosis_2005_snapshot_gnn.md").write_text(report, encoding="utf-8")
    (OUT / "diagnosis_details.json").write_text(json.dumps({"lag": lag_info, "peaks": peak_info}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

