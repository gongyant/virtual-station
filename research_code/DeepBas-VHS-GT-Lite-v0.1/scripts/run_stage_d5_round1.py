import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/diagnosis_2005_snapshot"
D4A = BASE / "stage_d4a"
D4B = BASE / "stage_d4b"
OUT = BASE / "stage_d5"
A = OUT / "d5a_failure_diagnosis"
B = OUT / "d5b_mq_lineage"
C = OUT / "d5c_stage_and_features"
D = OUT / "d5d_model_development"
E = OUT / "d5e_multiyear_evaluation"
PLOTS = OUT / "plots"
for p in (A, B, C, D, E, PLOTS):
    p.mkdir(parents=True, exist_ok=True)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_md(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def metrics(obs, pred) -> dict:
    obs = np.asarray(obs, float); pred = np.asarray(pred, float)
    ok = np.isfinite(obs) & np.isfinite(pred); obs = obs[ok]; pred = pred[ok]
    if len(obs) < 2:
        return {k: np.nan for k in ("nse", "rmse", "mae", "kge", "pbias", "pearson", "spearman")}
    err = pred - obs
    denom = np.sum((obs - obs.mean()) ** 2)
    nse = 1 - np.sum(err ** 2) / denom if denom else np.nan
    rmse = np.sqrt(np.mean(err ** 2)); mae = np.mean(np.abs(err))
    r = np.corrcoef(obs, pred)[0, 1] if obs.std() and pred.std() else np.nan
    alpha = pred.std(ddof=0) / obs.std(ddof=0) if obs.std(ddof=0) else np.nan
    beta = pred.mean() / obs.mean() if obs.mean() else np.nan
    kge = 1 - np.sqrt((r-1)**2 + (alpha-1)**2 + (beta-1)**2) if np.isfinite(r*alpha*beta) else np.nan
    pbias = 100 * np.sum(err) / np.sum(obs) if np.sum(obs) else np.nan
    sp = pd.Series(obs).corr(pd.Series(pred), method="spearman")
    return {"nse": float(nse), "rmse": float(rmse), "mae": float(mae), "kge": float(kge),
            "pbias": float(pbias), "pearson": float(r), "spearman": float(sp)}


def verify_d4b() -> dict:
    pred_manifest = json.loads((D4B / "boundary_only_2011_prediction_manifest.json").read_text(encoding="utf-8"))
    completion = json.loads((D4B / "boundary_only_2011_scoring_completion.json").read_text(encoding="utf-8"))
    schema = json.loads((D4B / "daily_discharge_2011_schema_audit.json").read_text(encoding="utf-8"))
    checks = []
    def add(rel: str, expected: str, origin: str):
        path = ROOT / rel
        actual = sha256(path) if path.exists() else None
        checks.append({"path": rel.replace("\\", "/"), "manifest_source": origin,
                       "expected_sha256": expected, "actual_sha256": actual,
                       "matches": actual == expected})
    add(pred_manifest["parameter_file"], pred_manifest["parameter_sha256"], "prediction_manifest")
    add(pred_manifest["prediction_file"], pred_manifest["prediction_sha256"], "prediction_manifest")
    add(pred_manifest["predictor_input_file"], pred_manifest["input_sha256"], "prediction_manifest")
    add(pred_manifest["generator_program"], pred_manifest["generator_program_sha256"], "prediction_manifest")
    add("outputs/diagnosis_2005_snapshot/stage_d4b/boundary_only_2011_prediction_manifest.json",
        completion["prediction_manifest_sha256"], "scoring_completion")
    add("outputs/diagnosis_2005_snapshot/stage_d4b/boundary_only_2011_evaluation_protocol_frozen.json",
        completion["evaluation_protocol_sha256"], "scoring_completion")
    add("outputs/diagnosis_2005_snapshot/stage_d4b/daily_discharge_2011_canonical.csv",
        completion["label_file_sha256_at_scoring"], "scoring_completion")
    add("scripts/score_boundary_only_2011.py", completion["scoring_program_sha256"], "scoring_completion")
    for rel, expected in completion["output_sha256"].items():
        add(f"outputs/diagnosis_2005_snapshot/stage_d4b/{rel}", expected, "scoring_completion.output_sha256")
    for rel, expected in schema["canonical_files"].items():
        add(f"outputs/diagnosis_2005_snapshot/stage_d4b/{rel}", expected, "schema_audit.canonical_files")
    passed = all(x["matches"] for x in checks)
    result = {"audit_time": "2026-07-31", "scope": "manifest-covered D4B immutable artifacts",
              "passed": passed, "d4b_read_only": True, "rerun_scoring": False,
              "checked_file_count": len(checks), "checks": checks,
              "supplemental_unmanifested_files": ["stage_d4b_review_workbook.xlsx"]}
    dump(OUT / "d4b_immutability_audit.json", result)
    if not passed:
        raise SystemExit("D4B immutability mismatch; D5 stopped")
    return result


def nnls_centered(X: np.ndarray, y: np.ndarray, max_iter: int = 20000, tol: float = 1e-12):
    X = np.asarray(X, float); y = np.asarray(y, float)
    xm = X.mean(axis=0); ym = y.mean(); xc = X - xm; yc = y - ym
    w = np.zeros(X.shape[1], float); denom = np.sum(xc * xc, axis=0)
    for _ in range(max_iter):
        old = w.copy()
        fitted = xc @ w
        for j in range(X.shape[1]):
            if denom[j] <= 0: continue
            partial = yc - fitted + xc[:, j] * w[j]
            new = max(0.0, float(np.dot(xc[:, j], partial) / denom[j]))
            fitted += xc[:, j] * (new - w[j]); w[j] = new
        if np.max(np.abs(w - old)) < tol:
            break
    return float(ym - xm @ w), w


def kernel_and_collinearity():
    param_path = D4A / "boundary_only_frozen_parameters_2005.json"
    param = json.loads(param_path.read_text(encoding="utf-8"))
    weights = np.array([x["weight"] for x in sorted(param["weights"], key=lambda z: z["lag_day"])], float)
    lags = np.arange(11); total = weights.sum(); shares = weights / total if total else np.zeros_like(weights)
    center = float(np.sum(lags * shares)); std = float(np.sqrt(np.sum(shares * (lags-center)**2)))
    effective_support = float(1 / np.sum(shares ** 2)) if np.sum(shares ** 2) else 0.0
    nonzero = weights > 1e-10
    rows = [{"lag_day": int(k), "weight": float(w), "share_of_weight_sum": float(s),
             "nonzero_gt_1e_10": bool(nz), "near_zero_stored": bool(0 < abs(w) <= 1e-10),
             "intercept_b": param["intercept_b"], "weight_sum": total, "nonzero_weight_count": int(nonzero.sum()),
             "center_of_mass_days": center, "weighted_std_days": std, "effective_support_length": effective_support,
             "kernel_shape_diagnosis": "degenerate_two_spike_lag0_lag5"}
            for k, w, s, nz in zip(lags, weights, shares, nonzero)]
    pd.DataFrame(rows).to_csv(A / "frozen_kernel_structure.csv", index=False, encoding="utf-8-sig")

    train = pd.read_csv(BASE / "stage_c/byblk_dsk_daily_features.csv", parse_dates=["date"])
    cols = [f"q_byblk_lag{k}" for k in range(11)]
    train = train[(train.date >= "2005-05-11") & (train.date <= "2005-08-31")].dropna(subset=cols+["q_dsk_obs"])
    if len(train) != 113: raise AssertionError(len(train))
    X = train[cols].values.astype(float); y = train.q_dsk_obs.values.astype(float)
    b0, w0 = nnls_centered(X, y)
    if not (np.allclose(w0, weights, atol=2e-7) and abs(b0-param["intercept_b"]) < 2e-7):
        raise AssertionError("official parameter JSON cannot be reproduced from frozen source")
    corr = train[cols].corr(); corr.to_csv(A / "lag_feature_correlation_2005.csv", encoding="utf-8-sig")
    Z = (X - X.mean(0)) / X.std(0, ddof=0)
    singular = np.linalg.svd(Z, compute_uv=False)
    cond = float(singular[0] / singular[-1])
    vifs = {}
    for j, name in enumerate(cols):
        target = Z[:, j]; other = np.delete(Z, j, axis=1)
        beta = np.linalg.lstsq(other, target, rcond=None)[0]
        r2 = 1 - np.sum((target-other@beta)**2)/np.sum(target**2)
        vifs[name] = float(1/(1-r2)) if r2 < 1 else math.inf
    p = singular**2 / np.sum(singular**2)
    erank = float(np.exp(-np.sum(p*np.log(p))))
    diagnostics = {"row_count": len(train), "date_range": [str(train.date.min().date()), str(train.date.max().date())],
                   "condition_number_standardized_X": cond, "matrix_rank": int(np.linalg.matrix_rank(Z)),
                   "effective_rank_entropy": erank, "min_pairwise_correlation": float(corr.values[np.triu_indices(11,1)].min()),
                   "max_pairwise_correlation": float(corr.values[np.triu_indices(11,1)].max()),
                   "vif": vifs, "max_vif": max(vifs.values()), "singular_values": singular.tolist(),
                   "interpretation": "severe" if cond > 30 or max(vifs.values()) > 10 else "moderate_or_low",
                   "diagnostic_only": True}
    dump(A / "lag_collinearity_diagnostics.json", diagnostics)

    rng = np.random.default_rng(20260731); boot_rows = []
    n = len(train)
    for block_len in (7, 14):
        for rep in range(200):
            idx = []
            while len(idx) < n:
                start = int(rng.integers(0, n-block_len+1)); idx.extend(range(start, start+block_len))
            idx = np.array(idx[:n]); bb, ww = nnls_centered(X[idx], y[idx])
            row = {"experiment": "moving_block_bootstrap", "block_length_days": block_len, "replicate": rep,
                   "intercept_b": bb, "nonzero_count": int((ww>1e-8).sum())}
            row.update({f"lag{k}_weight": ww[k] for k in range(11)}); boot_rows.append(row)
    for block_len in (7, 14):
        for start in range(0, n-block_len+1, block_len):
            keep = np.ones(n, bool); keep[start:start+block_len] = False
            bb, ww = nnls_centered(X[keep], y[keep])
            row = {"experiment": "contiguous_block_deletion", "block_length_days": block_len,
                   "replicate": start//block_len, "deleted_start": str(train.date.iloc[start].date()),
                   "deleted_end": str(train.date.iloc[start+block_len-1].date()), "intercept_b": bb,
                   "nonzero_count": int((ww>1e-8).sum())}
            row.update({f"lag{k}_weight": ww[k] for k in range(11)}); boot_rows.append(row)
    boot = pd.DataFrame(boot_rows); boot.to_csv(A / "lag_weight_block_bootstrap.csv", index=False, encoding="utf-8-sig")
    folds = []
    fold_specs = [(0,55),(14,69),(28,83),(42,97),(56,112),(0,69),(0,83),(0,97),(0,112)]
    for i,(s,e) in enumerate(fold_specs,1):
        bb,ww=nnls_centered(X[s:e+1],y[s:e+1]); row={"fold":f"rolling_{i}","start":str(train.date.iloc[s].date()),
            "end":str(train.date.iloc[e].date()),"row_count":e-s+1,"intercept_b":bb,"nonzero_count":int((ww>1e-8).sum())}
        row.update({f"lag{k}_weight":ww[k] for k in range(11)}); folds.append(row)
    pd.DataFrame(folds).to_csv(A / "lag_weight_fold_stability.csv", index=False, encoding="utf-8-sig")

    plt.figure(figsize=(7,4)); plt.bar(lags, weights, color="#1f77b4"); plt.xticks(lags); plt.xlabel("Lag (day)"); plt.ylabel("Frozen weight")
    plt.title("Frozen K=10 kernel: only lag 0 and lag 5 are active"); plt.tight_layout(); plt.savefig(PLOTS/"frozen_lag_weights.png",dpi=180); plt.close()
    plt.figure(figsize=(7,6)); im=plt.imshow(corr, vmin=0, vmax=1, cmap="viridis"); plt.colorbar(im,label="Pearson correlation")
    plt.xticks(range(11),range(11)); plt.yticks(range(11),range(11)); plt.xlabel("Lag (day)"); plt.ylabel("Lag (day)"); plt.title("2005 lag-feature correlation")
    plt.tight_layout(); plt.savefig(PLOTS/"lag_correlation_matrix.png",dpi=180); plt.close()
    bplot=boot[boot.experiment=="moving_block_bootstrap"]
    arr=[bplot[f"lag{k}_weight"].values for k in range(11)]
    plt.figure(figsize=(9,4)); plt.boxplot(arr,positions=lags,showfliers=False); plt.xlabel("Lag (day)"); plt.ylabel("NNLS weight"); plt.title("Time-block bootstrap weight instability")
    plt.tight_layout(); plt.savefig(PLOTS/"lag_weight_bootstrap.png",dpi=180); plt.close()

    active_freq={f"lag{k}":float((bplot[f'lag{k}_weight']>1e-8).mean()) for k in range(11)}
    report=f"""# 冻结K=10核结构诊断

## 结论

官方参数JSON可由2005-05-11至2005-08-31的113条开发期数据准确复现。冻结式为：

`Q_DSK(t) = {param['intercept_b']:.6f} + {weights[0]:.6f} Q_BYBLK(t) + {weights[5]:.6f} Q_BYBLK(t-5)`。

名义上有lag0—lag10共11个自由权重，实际只有lag0和lag5非零；非零数为{int(nonzero.sum())}，权重和为{total:.6f}，权重质心为{center:.3f}天，加权标准差为{std:.3f}天，逆Herfindahl有效支撑长度仅{effective_support:.3f}个lag。因此它不是平滑的“分布式传播核”，而是退化为两个尖峰的稀疏NNLS解。

## 共线性证据

标准化时滞矩阵条件数为{cond:.2f}，最大VIF为{max(vifs.values()):.2f}，熵有效秩为{erank:.2f}/11，判定为“{diagnostics['interpretation']}”。相邻日流量高度相关，使NNLS能用不同尖峰组合表达近似相同的平滑过程。时间块自助法中各lag被选中的频率为：{json.dumps(active_freq,ensure_ascii=False)}。这说明尖峰位置对抽取的连续水文片段敏感，不能把lag0与lag5直接解释为稳定的物理传播时间。

## 可迁移性判断

当前权重可作为已冻结的经验回归系数，但物理可迁移性不足。后续若重新开发，只能在非2011年份中比较低参数平滑核或储量状态模型；2011已揭示结果不得参与核形、lag或正则化选择。
"""
    write_md(A/"frozen_kernel_diagnosis_zh.md",report)
    return diagnostics, active_freq


def failure_morphology():
    pred=pd.read_csv(D4B/"boundary_only_2011_predictions_frozen.csv",parse_dates=["date"])
    q=pd.read_csv(D4B/"daily_discharge_2011_canonical.csv",dtype={"station_id":str},parse_dates=["date"])
    by=q[q.station_id=="00705600"][["date","discharge_m3s"]].rename(columns={"discharge_m3s":"q_byblk"})
    ds=q[q.station_id=="00705700"][["date","discharge_m3s"]].rename(columns={"discharge_m3s":"q_obs"})
    z=pred.merge(by,on="date").merge(ds,on="date"); z["error"]=z.q_pred-z.q_obs; z["month"]=z.date.dt.month
    z["obs_diff_1d"]=z.q_obs.diff(); z["limb"]=np.where(z.obs_diff_1d>0,"rising",np.where(z.obs_diff_1d<0,"falling","flat"))
    windows={"primary":z[z.window_primary.astype(bool)].copy(),"full_year_diagnostic":z[z.window_full_year_diagnostic.astype(bool)].copy()}
    monthly=[]; regime=[]; peaks=[]; ac=[]; runs=[]
    for wname,g in windows.items():
        for month,h in g.groupby("month"):
            mm=metrics(h.q_obs,h.q_pred); monthly.append({"window":wname,"month":month,"row_count":len(h),**mm,
                "mean_obs":h.q_obs.mean(),"mean_pred":h.q_pred.mean(),"mean_byblk":h.q_byblk.mean(),
                "dsk_byblk_mean_ratio":h.q_obs.mean()/h.q_byblk.mean(),"cumulative_volume_bias_percent":100*h.error.sum()/h.q_obs.sum(),
                "status":"post_hoc_diagnostic_only"})
        q1,q2=g.q_obs.quantile([1/3,2/3])
        g=g.copy(); g["flow_regime"]=pd.cut(g.q_obs,[-np.inf,q1,q2,np.inf],labels=["low","middle","high"],include_lowest=True)
        for key,h in g.groupby("flow_regime",observed=False):
            regime.append({"window":wname,"diagnostic_axis":"flow_regime","group":str(key),"row_count":len(h),**metrics(h.q_obs,h.q_pred),"mean_error":h.error.mean(),"status":"post_hoc_diagnostic_only"})
        for key,h in g.groupby("limb"):
            regime.append({"window":wname,"diagnostic_axis":"hydrograph_limb","group":key,"row_count":len(h),**metrics(h.q_obs,h.q_pred),"mean_error":h.error.mean(),"status":"post_hoc_diagnostic_only"})
        oi=g.q_obs.idxmax(); pi=g.q_pred.idxmax()
        peaks.append({"window":wname,"observed_peak_date":str(g.loc[oi,"date"].date()),"predicted_peak_date":str(g.loc[pi,"date"].date()),
            "peak_timing_error_days":int((g.loc[pi,"date"]-g.loc[oi,"date"]).days),"observed_peak":g.loc[oi,"q_obs"],"predicted_peak":g.loc[pi,"q_pred"],
            "peak_amplitude_error":g.loc[pi,"q_pred"]-g.loc[oi,"q_obs"],"peak_amplitude_error_percent":100*(g.loc[pi,"q_pred"]-g.loc[oi,"q_obs"])/g.loc[oi,"q_obs"],
            "status":"post_hoc_diagnostic_only"})
        for lag in range(1,31): ac.append({"window":wname,"lag_day":lag,"error_autocorrelation":g.error.autocorr(lag),"status":"post_hoc_diagnostic_only"})
        signs=np.sign(g.error.values); start=0
        all_runs=[]
        for i in range(1,len(g)+1):
            if i==len(g) or signs[i]!=signs[start]:
                if signs[start]!=0:
                    h=g.iloc[start:i]; all_runs.append({"sign":"positive_overprediction" if signs[start]>0 else "negative_underprediction",
                        "start":str(h.date.iloc[0].date()),"end":str(h.date.iloc[-1].date()),"length_days":len(h),"mean_error":h.error.mean(),"sum_error":h.error.sum()})
                start=i
        for sign in ("positive_overprediction","negative_underprediction"):
            subset=[r for r in all_runs if r["sign"]==sign]
            if subset:
                best=max(subset,key=lambda r:r["length_days"]); runs.append({"window":wname,**best,"status":"post_hoc_diagnostic_only"})
    pd.DataFrame(monthly).to_csv(A/"d4b_monthly_failure_metrics.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(regime).to_csv(A/"d4b_flow_regime_failure_metrics.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(peaks).to_csv(A/"d4b_peak_failure_diagnostics.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(ac).to_csv(A/"d4b_error_autocorrelation.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(runs).to_csv(A/"d4b_error_runs.csv",index=False,encoding="utf-8-sig")
    shifts=[]
    for wname,g in windows.items():
        for shift in range(-15,16):
            h=g[["date","q_obs","q_pred"]].copy(); h["q_shifted"]=h.q_pred.shift(shift); m=metrics(h.q_obs,h.q_shifted)
            shifts.append({"window":wname,"prediction_shift_days":shift,"row_count":h.q_shifted.notna().sum(),**m,"status":"post_hoc_diagnostic_only"})
    shift_df=pd.DataFrame(shifts); shift_df.to_csv(A/"d4b_posthoc_shift_diagnostics.csv",index=False,encoding="utf-8-sig")
    lagrows=[]
    for month,g in z.groupby("month"):
        tmp=[]
        for lag in range(21):
            r=g.q_byblk.shift(lag).corr(g.q_obs); tmp.append((lag,r)); lagrows.append({"month":month,"lag_day":lag,"pearson":r,"is_best_monthly":False,"status":"post_hoc_diagnostic_only"})
        best=max(tmp,key=lambda x: -np.inf if not np.isfinite(x[1]) else x[1])[0]
        for row in lagrows:
            if row["month"]==month and row["lag_day"]==best: row["is_best_monthly"]=True
    pd.DataFrame(lagrows).to_csv(A/"d4b_monthly_lag_diagnostics.csv",index=False,encoding="utf-8-sig")
    z["obs_month_anomaly"]=z.q_obs-z.groupby("month").q_obs.transform("mean")
    z["pred_month_anomaly"]=z.q_pred-z.groupby("month").q_pred.transform("mean")
    extra={}
    for wname,g in windows.items():
        obs_anom=g.q_obs-g.groupby(g.date.dt.month).q_obs.transform("mean")
        pred_anom=g.q_pred-g.groupby(g.date.dt.month).q_pred.transform("mean")
        extra[wname]={"std_ratio_pred_over_obs":float(g.q_pred.std(ddof=0)/g.q_obs.std(ddof=0)),
            "monthly_anomaly_correlation":float(obs_anom.corr(pred_anom)),
            "cumulative_volume_bias_percent":float(100*g.error.sum()/g.q_obs.sum()),
            "low_flow_mean_error":float(g.loc[g.q_obs<=g.q_obs.quantile(1/3),"error"].mean()),
            "high_flow_mean_error":float(g.loc[g.q_obs>=g.q_obs.quantile(2/3),"error"].mean())}
    primary=windows["primary"]; bestshift=shift_df[shift_df.window=="primary"].sort_values("nse",ascending=False).iloc[0]
    ac1=pd.DataFrame(ac).query("window=='primary' and lag_day==1").iloc[0].error_autocorrelation
    pmet=metrics(primary.q_obs,primary.q_pred)
    report=f"""# D4B跨年失败形态诊断

本报告属于2011已揭示年份的回顾性诊断，只解释一次性D4B结果，不形成修正版模型。

主窗口NSE={pmet['nse']:.3f}、RMSE={pmet['rmse']:.2f} m³/s。预测/实测标准差比为{extra['primary']['std_ratio_pred_over_obs']:.3f}；去除各月均值后的异常相关为{extra['primary']['monthly_anomaly_correlation']:.3f}。低流量段平均误差为{extra['primary']['low_flow_mean_error']:.2f} m³/s，高流量段平均误差为{extra['primary']['high_flow_mean_error']:.2f} m³/s，表明主要问题不是单一总量偏差，而是状态依赖的幅度与过程形态失真。

误差lag-1自相关为{ac1:.3f}，说明错误连续成段出现，不是孤立噪声。事后平移扫描的主窗口最佳NSE出现在预测平移{int(bestshift.prediction_shift_days):+d}天（NSE={bestshift.nse:.3f}）；该值仅是诊断证据，禁止用于改动正式窗口或生成修正预测。

月度、流量区间、涨落水段、误差连续段、峰值和lag结果均见同目录CSV。2011结果已揭示，不得据此重选lag、核、正则化、截距或高流量权重。
"""
    write_md(A/"d4b_failure_summary_zh.md",report)
    plt.figure(figsize=(11,4)); plt.plot(z.date,z.q_obs,label="Observed DSK",color="black",lw=1.3); plt.plot(z.date,z.q_pred,label="Frozen prediction",color="#d62728",alpha=.85)
    plt.legend(); plt.ylabel("Q (m3/s)"); plt.title("2011 revealed-year retrospective diagnosis"); plt.tight_layout(); plt.savefig(PLOTS/"d4b_failure_timeseries.png",dpi=180); plt.close()
    plt.figure(figsize=(11,3.5)); plt.axhline(0,color="black",lw=.8); plt.plot(z.date,z.error,color="#9467bd"); plt.ylabel("Prediction - observed"); plt.title("Persistent frozen-prediction error states"); plt.tight_layout(); plt.savefig(PLOTS/"d4b_error_timeseries.png",dpi=180); plt.close()
    return z, extra


def daily_aggregation_audit():
    text="""# 逐日汇总口径审计

## 已确认

- Doc1扫描页标题使用“逐日平均水位表”和“逐日平均流量表”，因此变量语义是逐日平均值，而不是瞬时极值。
- D4B的BYBLK与DSK逐日流量来自同一份Doc1年度资料，日历日期均为2011-01-01至2011-12-31。
- 表底“最高/最低”及其日期为独立统计项；不能把这些瞬时或统计极值写入逐日平均序列。

## 仍未知

- 一日边界究竟是00:00—24:00、08:00—次日08:00，还是自记水位/流量的积分平均：现有项目文件和Doc1页脚未说明。
- BYBLK与DSK是否绝对使用同一水文日边界：未找到明确文字证明。
- 闸门启闭造成日内突变时，日平均采用何种加权或剔除规则：未找到说明。
- Q-新疆.xls中的2005日期列与Doc1 2011表是否遵循相同水文日：未找到说明。

## 判定

状态为`blocked_unknown_daily_aggregation_boundary`。这不会否定现有逐日数值，但会给0—1天时滞解释带来结构性不确定性；在老师或原资料说明确认前，不得把事后最佳平移解释成真实传播时间。
"""
    write_md(A/"daily_aggregation_definition_audit_zh.md",text)
    draft=pd.read_csv(BASE/"stage_d3/daily_stage_2011_ocr_draft.csv",dtype={"station_id":str})
    by=draft[draft.station_id=="00705600"].copy()
    pd.DataFrame([{"station_id":"00705600","station_name":"巴音布鲁克","source_page":"embedded_image_order_009",
        "table_exists":True,"calendar_rows":int(len(by)),"ocr_candidate_nonmissing":int(pd.to_numeric(by.value,errors="coerce").notna().sum()),
        "manual_confirmed_rows":0,"usable_for_modeling":False,"status":"blocked_pending_manual_cell_transcription",
        "note":"第一轮最低交付优先完成DSK；BYBLK页存在，但当前OCR候选过少且未经逐格人工复核，不得进入模型。"}]).to_csv(
            C/"byblk_daily_stage_availability_audit_2011.csv",index=False,encoding="utf-8-sig")


def mq_lineage():
    raw=ROOT/"data/raw/runoff/Q-新疆.xls"; processed=ROOT/"data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
    nodes=[
      {"id":"raw_xls","type":"raw_workbook","path":"data/raw/runoff/Q-新疆.xls","sha256":sha256(raw)},
      {"id":"sheet_2005_tributary","type":"worksheet","workbook_node":"raw_xls","sheet":"2005-支流","range":"A1:J185"},
      {"id":"mq_dsk_column","type":"source_field","sheet_node":"sheet_2005_tributary","header":"MQ-DSK-2005-SB","column_index_zero_based":1},
      {"id":"extract_script","type":"script","path":"scripts/extract_multisite_runoff_2005.py","sha256":sha256(ROOT/"scripts/extract_multisite_runoff_2005.py")},
      {"id":"processed_csv","type":"processed_table","path":"data/processed/virtual_station_multisite/multisite_discharge_2005.csv","field":"physical_reference_q_m3s","sha256":sha256(processed)},
      {"id":"bundle_script","type":"script","path":"scripts/prepare_multisite_gnn_bundle_2005.py","sha256":sha256(ROOT/"scripts/prepare_multisite_gnn_bundle_2005.py")},
      {"id":"bundle_feature","type":"npz_feature","path":"data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz","feature":"physical_reference_q"},
      {"id":"stage_c_extract","type":"script","path":"scripts/run_stage_c_boundary_lag_residual.py","field":"q_dsk_mq"},
      {"id":"stage_c_input","type":"processed_table","path":"outputs/diagnosis_2005_snapshot/stage_c/byblk_dsk_daily_features.csv","field":"q_dsk_mq"},
    ]
    edges=[{"from":"raw_xls","to":"sheet_2005_tributary","operation":"select sheet index 9"},
           {"from":"sheet_2005_tributary","to":"mq_dsk_column","operation":"select existing column 1"},
           {"from":"mq_dsk_column","to":"processed_csv","operation":"direct numeric copy; no formula in extraction script"},
           {"from":"processed_csv","to":"bundle_feature","operation":"rename physical_reference_q_m3s -> physical_reference_q and tensorize"},
           {"from":"bundle_feature","to":"stage_c_input","operation":"direct tensor extraction to q_dsk_mq"}]
    graph={"status":"blocked_unknown_mq_lineage","nodes":nodes,"edges":edges,"confirmed_lineage_endpoints":True,
           "unconfirmed_upstream_generation_formula":True,"notes":"The workbook contains values, but repository does not contain the model/formula that created MQ-DSK-2005-SB."}
    dump(B/"mq_2005_lineage_graph.json",graph)
    audit=pd.DataFrame([
      {"question":"source raw file","finding":"data/raw/runoff/Q-新疆.xls; 2005-支流; MQ-DSK-2005-SB","confirmed":True,"2011_label_free_reproducible":False},
      {"question":"project computed or Excel existing","finding":"existing Excel column; repository only copies it","confirmed":True,"2011_label_free_reproducible":False},
      {"question":"area ratio","finding":"unknown; no generating formula found","confirmed":False,"2011_label_free_reproducible":False},
      {"question":"Manning","finding":"unknown; no generating formula found","confirmed":False,"2011_label_free_reproducible":False},
      {"question":"lag routing","finding":"unknown; no generating formula found","confirmed":False,"2011_label_free_reproducible":False},
      {"question":"historical DSK Q calibration","finding":"unknown; cannot exclude target-site calibration","confirmed":False,"2011_label_free_reproducible":False},
      {"question":"target-year information","finding":"unknown upstream generation; 2005 values are year-specific workbook entries","confirmed":False,"2011_label_free_reproducible":False},
      {"question":"legal 2011 reconstruction","finding":"blocked_unknown_mq_lineage; do not fabricate MQ","confirmed":True,"2011_label_free_reproducible":False},
    ])
    audit.to_csv(B/"mq_2011_reproducibility_audit.csv",index=False,encoding="utf-8-sig")
    report="""# 2005 MQ来源链路报告

## 可以确认的链路

`data/raw/runoff/Q-新疆.xls` → 工作表`2005-支流` → 已存在字段`MQ-DSK-2005-SB` → `scripts/extract_multisite_runoff_2005.py`按列直接复制为`physical_reference_q_m3s` → `scripts/prepare_multisite_gnn_bundle_2005.py`改名为`physical_reference_q`并写入NPZ → `scripts/run_stage_c_boundary_lag_residual.py`提取为`q_dsk_mq`。

## 不能确认的上游生成过程

仓库没有生成`MQ-DSK-2005-SB`的脚本、公式、参数清单或原始输入清单。因而不能确认其是否使用汇水面积比例、Manning、传播时滞、2005 DSK实测Q率定、目标年信息或其他人工处理。Excel中的现成值本身不是可复现的生成公式。

## 2011结论

状态固定为`blocked_unknown_mq_lineage`。在来源公式得到老师或原作者确认前，不能合法重建2011 MQ，也不能把阶段C主模型称为完成了2011外部验证。若MQ曾用DSK实测Q率定，其协议级别最多为P1校准参考，不是P2严格无站参考。
"""
    write_md(B/"mq_2005_lineage_report_zh.md",report)


def stage_relationships(z: pd.DataFrame):
    stage=pd.read_csv(C/"daily_stage_dsk_2011_reviewed.csv",parse_dates=["date"])
    g=z.merge(stage[["date","stage_m"]],on="date",how="left")
    for lag in (1,3,7,14): g[f"stage_change_{lag}d"]=g.stage_m-g.stage_m.shift(lag)
    feats=["stage_m","stage_change_1d","stage_change_3d","stage_change_7d","stage_change_14d"]
    rows=[]
    for window,mask in (("primary",g.window_primary.astype(bool)),("full_year_diagnostic",g.window_full_year_diagnostic.astype(bool))):
        h=g[mask]
        for f in feats:
            rows.append({"window":window,"feature":f,"row_count":h[[f,"error"]].dropna().shape[0],
                "pearson_with_error":h[f].corr(h.error),"spearman_with_error":h[f].corr(h.error,method="spearman"),
                "pearson_with_observed_q":h[f].corr(h.q_obs),"status":"post_hoc_diagnostic_only"})
    rel=pd.DataFrame(rows); rel.to_csv(C/"dsk_stage_error_relationships_2011.csv",index=False,encoding="utf-8-sig")
    g["stage_bin_0_05m"]=(g.stage_m/0.05).round()*0.05
    hq=[]
    for key,h in g.groupby("stage_bin_0_05m"):
        if len(h)>=2:
            hq.append({"stage_bin_m":key,"row_count":len(h),"q_min":h.q_obs.min(),"q_max":h.q_obs.max(),"q_range":h.q_obs.max()-h.q_obs.min(),
                "q_mean":h.q_obs.mean(),"mean_error":h.error.mean(),"same_stage_different_q_candidate":(h.q_obs.max()-h.q_obs.min())>30,
                "status":"candidate_control_regime_post_hoc"})
    pd.DataFrame(hq).to_csv(C/"dsk_hq_daily_diagnostics_2011.csv",index=False,encoding="utf-8-sig")
    meas=pd.read_csv(D4B/"discharge_measurements_2011_canonical.csv",dtype={"station_id":str},parse_dates=["date"])
    meas=meas[meas.station_id=="00705700"][["measurement_id","date","stage_m","discharge_m3s","control_note","condition_code"]]
    note_diag=meas.merge(g[["date","q_obs","q_pred","error"]],on="date",how="left")
    note_diag["gate_state_observed"] = False
    note_diag["status"] = "generic_station_control_note_only_no_date_specific_gate_state"
    note_diag.to_csv(C/"dsk_control_note_error_diagnostics_2011.csv",index=False,encoding="utf-8-sig")
    prim=rel[rel.window=="primary"].set_index("feature")
    maxcorr=prim.pearson_with_error.abs().max(); top=prim.pearson_with_error.abs().idxmax()
    report=f"""# DSK水位控制代理诊断

DSK逐日水位已完成365/365逐格视觉复核，12个月复算均值均与原表底四舍五入一致。没有用Q反推H，没有插值，也没有用H-Q曲线自动补值。

在D4B主窗口中，冻结预测误差与水位及其过去1/3/7/14日变化的最大绝对Pearson相关为{maxcorr:.3f}（变量：`{top}`）。这只是2011已揭示年份的回顾性关系，不能直接用于选结构或宣称闸门开度状态。按0.05 m水位分箱后，同一近似水位下仍可出现明显不同流量，支持“controlled_or_mixed”及多分支H-Q的既有判断。

结论：可靠日水位值得列为下一阶段P1B候选输入，但只能在非2011年份完成结构和约束选择；模型输入当前H时不再是P2严格无站模型。48条DSK测流记录的备注都只说明“站在闸下且无启闭资料”，没有逐日闸门状态，因此无法比较真实启闭状态相邻误差；自动分组只能称`candidate_control_regime`。
"""
    write_md(C/"dsk_control_proxy_assessment_zh.md",report)
    outp=PLOTS/"dsk_stage_error_relationships"; outp.mkdir(exist_ok=True)
    plt.figure(figsize=(7,4)); plt.scatter(g.stage_m,g.error,s=10,alpha=.55); plt.axhline(0,color="black",lw=.8); plt.xlabel("DSK daily mean stage (m)"); plt.ylabel("Frozen prediction error (m3/s)"); plt.title("Stage-error relationship (post-hoc only)"); plt.tight_layout(); plt.savefig(outp/"stage_vs_error.png",dpi=180); plt.close()
    plt.figure(figsize=(10,4)); plt.plot(g.date,g.stage_m,color="#1f77b4",label="Stage"); plt.ylabel("Stage (m)"); plt.title("DSK reviewed daily mean stage, 2011"); plt.tight_layout(); plt.savefig(outp/"dsk_daily_stage.png",dpi=180); plt.close()
    return rel


def multiyear_audit():
    rows=[]
    bundle=np.load(ROOT/"data/processed/virtual_station/virtual_station_bundle_1978_1983.npz",allow_pickle=True)
    dates=pd.to_datetime(bundle["dates"]); ids=list(map(str,bundle["station_ids"])); bi=ids.index("00705600"); di=ids.index("00705700")
    fn=list(map(str,bundle["feature_names"])); oi=fn.index("obs_q")
    for year in range(1978,1984):
        mask=dates.year==year
        rows.append({"year":year,"BYBLK_Q_days":int(np.isfinite(bundle["x"][mask,bi,oi]).sum()),"DSK_Q_days":int(bundle["y_mask"][mask,di].sum()),"DSK_H_days":0,
            "MQ_days":0,"ERA5_days":int(mask.sum()),"precipitation_available":True,"temperature_available":True,"snow_available":True,
            "quality_status":"processed_bundle_requires_source_lineage_review","source_file":"data/processed/virtual_station/virtual_station_bundle_1978_1983.npz",
            "protocol_role":"candidate_development_year_non_2011"})
    inp=pd.read_csv(ROOT/"data/processed/virtual_station_external/external_input_byblk_2000_2001.csv",parse_dates=["date"])
    lab=pd.read_csv(ROOT/"data/processed/virtual_station_external/external_label_dsk_2000_2001.csv",parse_dates=["date"])
    for year in (2000,2001):
        rows.append({"year":year,"BYBLK_Q_days":int((inp.date.dt.year==year).sum()),"DSK_Q_days":int((lab.date.dt.year==year).sum()),"DSK_H_days":0,"MQ_days":0,
            "ERA5_days":366 if year==2000 else 365,"precipitation_available":True,"temperature_available":True,"snow_available":True,"quality_status":"processed_external_files; original protocol status must be retained",
            "source_file":"data/processed/virtual_station_external/*.csv; data/processed/era5_land_external/*.nc","protocol_role":"previously_used_external_period_not_new_blind_year"})
    m=pd.read_csv(ROOT/"data/processed/virtual_station_multisite/multisite_discharge_2005.csv",dtype={"station_id":str},parse_dates=["date"])
    rows.append({"year":2005,"BYBLK_Q_days":int(m[(m.station_id=="00705600")].observed_q_m3s.notna().sum()),"DSK_Q_days":int(m[(m.station_id=="00705700")].observed_q_m3s.notna().sum()),"DSK_H_days":0,
        "MQ_days":int(m[(m.station_id=="00705700")].physical_reference_q_m3s.notna().sum()),"ERA5_days":0,"precipitation_available":False,"temperature_available":False,"snow_available":False,
        "quality_status":"development_and_legacy_labels_already_used","source_file":"data/raw/runoff/Q-新疆.xls -> multisite_discharge_2005.csv","protocol_role":"development_only"})
    rows.append({"year":2011,"BYBLK_Q_days":365,"DSK_Q_days":365,"DSK_H_days":365,"MQ_days":0,"ERA5_days":0,"precipitation_available":False,"temperature_available":False,"snow_available":False,
        "quality_status":"manual_reviewed_Doc1; D4B already revealed","source_file":"Doc1 -> stage_d4b canonical Q; stage_d5 reviewed H","protocol_role":"revealed_year_retrospective_diagnosis_only"})
    avail=pd.DataFrame(rows)
    avail.to_csv(C/"multiyear_data_availability.csv",index=False,encoding="utf-8-sig")
    usable=avail[(avail.year!=2011)&(avail.BYBLK_Q_days>300)&(avail.DSK_Q_days>300)]
    report=f"""# 多年份协议角色

- 1978—1983：共有{len(usable[usable.year.between(1978,1983)])}个年份在处理后bundle中同时具备BYBLK与DSK日流量，并附有ERA5气温、降水、积雪/融雪候选变量；进入新开发前仍须复核原始观测与缺失口径。
- 2000—2001：已在旧外部流程中使用，不能再称新的盲测年份；可作为已揭示时期的稳健性诊断或在预注册协议中明确其历史角色。
- 2005：阶段C与D4A系数开发年份，只能用于开发与内部时序验证。
- 2011：D4B已一次性解封，今后只允许回顾性诊断，禁止选择模型结构和超参数。

因此，当前最多有1978—1983六个候选非2011年份可支持leave-one-year-out开发；是否全部合法进入正式开发，取决于对这些bundle中实测Q来源和质量标志的再次审计。
"""
    write_md(C/"multiyear_protocol_roles_zh.md",report)
    return avail


def model_protocol(avail: pd.DataFrame):
    protocol={"schema_version":"1.0","frozen_at":"2026-07-31","round":"D5 round 1 protocol only",
      "no_model_training_in_this_round":True,"revealed_year":"2011","forbidden_uses_of_2011":["model selection","lag selection","kernel selection","regularization selection","intercept fitting","window selection","feature-group selection","high-flow weighting"],
      "selection_data":"non-2011 years only after source-quality audit","validation":"leave-one-year-out when >=3 eligible years; otherwise rolling-origin within non-2011 data",
      "scaling":"fit on each training fold only","promotion":"multi-metric and parameter-stability evidence; no single-NSE promotion",
      "complexity_order":["M0 frozen D4B","M1 smooth nonnegative kernel","M2 one-storage state","M3 constrained fast/slow states","M4 state-related smooth kernel if sufficient years","M5 P1B bounded stage correction","M6 bidirectional historical reconstruction with Yanqi"],
      "climate_feature_rules":{"causal_current_or_past_only":True,"basin_or_incremental_basin_weighting":True,"no_future_values":True,"no_2011_feature_selection":True,"ablation_by_variable_group":True},
      "status":"frozen_protocol_not_executed"}
    dump(D/"model_development_protocol_frozen.json",protocol)
    registry=pd.DataFrame([
      ["M0","C_EXT_boundary_only_K10","frozen baseline; no refit","BYBLK Q lag0..10","P1 cross-year transfer","frozen_not_trainable"],
      ["M1","smooth_nonnegative_kernel","Gaussian/Gamma/Nash/triangular; <=4 parameters b,gain,mu,sigma","BYBLK Q history","candidate P1","eligible_after_non2011_audit"],
      ["M2","single_storage_state","one constrained storage state","BYBLK Q history","candidate P1","eligible_after_non2011_audit"],
      ["M3","fast_slow_dual_state","two constrained states, low dimension","BYBLK Q history","candidate P1","eligible_after_non2011_audit"],
      ["M4","state_related_smooth_kernel","only with enough eligible years","BYBLK Q + causal non-2011 state proxies","candidate P1","conditional"],
      ["M5","bounded_stage_correction","current/past DSK H; no DSK Q input","M0/M1 base + DSK H","P1B not P2","conditional_on_reliable_multiyear_stage"],
      ["M6","bidirectional_historical_reconstruction","Yanqi allowed only for historical reconstruction","BYBLK Q + Yanqi historical Q","historical reconstruction only","not_realtime_not_P2"],
    ],columns=["model_id","model_name","structure","allowed_inputs","protocol_class","round1_status"])
    registry.to_csv(D/"model_candidate_registry.csv",index=False,encoding="utf-8-sig")
    empty_cols=["model_id","held_out_year","train_years","status","nse","rmse","mae","kge","pbias","pearson","spearman","note"]
    pd.DataFrame([["NOT_RUN","","","not_run_round1_protocol_only",*[np.nan]*7,"No model training authorized"]],columns=empty_cols).to_csv(D/"leave_one_year_out_results.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame([{"model_id":"NOT_RUN","parameter":"","across_year_mean":np.nan,"across_year_std":np.nan,"status":"not_run_round1_protocol_only"}]).to_csv(D/"parameter_stability_across_years.csv",index=False,encoding="utf-8-sig")


def final_report(immut, diag, extra, avail):
    top_years=avail[(avail.year.between(1978,1983))&(avail.BYBLK_Q_days>300)&(avail.DSK_Q_days>300)].year.tolist()
    report=f"""# 阶段D5第一轮报告

本轮只完成D5A、D5B、D5C与后续模型协议冻结，没有训练新模型，也没有改动D3、D4A或D4B。

## 十二项停止问题

1. **D4B哈希是否完整？** 是。{immut['checked_file_count']}项清单核验全部一致；D4B保持只读，未重跑评分。
2. **K=10是否退化为尖峰？** 是。11个权重只有lag0和lag5非零，冻结式约为`1.655 + 3.295Q(t) + 0.683Q(t-5)`。
3. **时滞共线性多严重？** 标准化条件数{diag['condition_number_standardized_X']:.2f}，最大VIF {diag['max_vif']:.2f}，有效秩{diag['effective_rank_entropy']:.2f}/11；判定为{diag['interpretation']}，块自助与删块结果显示尖峰位置不稳定。
4. **是否有持续误差状态？** 有。2011主窗口误差存在明显自相关和连续高估/低估段，问题不是由单个洪峰日期独占。
5. **逐日口径一致吗？** 数值均标为逐日平均，但00—24或08—08等水文日边界、两站是否同口径及闸门日内突变处理均未知。
6. **MQ来源是什么？** 可追到`Q-新疆.xls/2005-支流/MQ-DSK-2005-SB`现成列；仓库只复制该列，没有其生成公式。
7. **能否合法重建2011 MQ？** 不能。状态`blocked_unknown_mq_lineage`，不得猜测面积比例、Manning或时滞公式。
8. **DSK逐日水位完整吗？** 是。2011年365/365已逐格视觉复核，所有月均复算到0.01 m均与表底一致；仍建议第二位人工抽查。
9. **水位能解释误差吗？** 存在回顾性关联和同水位不同Q分支，足以把H列入P1B候选，但不足以把自动状态称为闸门开度，也不能用2011选模型。
10. **有多少年可供多年份开发？** 当前处理后资料显示{len(top_years)}个候选非2011年份（{', '.join(map(str,top_years))}）同时有较完整BYBLK/DSK Q；正式开发前需再审计原始来源。2000—2001和2011均已揭示。
11. **哪些模型可合法开发？** 经非2011来源审计后可开发M1平滑核、M2单储量、M3快慢双状态；M4取决于年份，M5取决于多年份可靠H，M6只做历史重建。M0只能冻结比较。
12. **下一项最小实验是什么？** 先对1978—1983六年做观测Q来源与日界审计；通过后，严格按冻结协议比较M0、M1和M2的leave-one-year-out稳定性。不得先看2011再选核。

## 冻结结论

D4B失败更符合“高共线性下的稀疏尖峰核 + 年份间状态/控制关系改变 + 日界口径未知”的组合，而不是简单地说样本少。MQ主线仍被来源不明阻断。2011只保留为已揭示年份回顾性诊断。
"""
    write_md(OUT/"stage_d5_round1_report_zh.md",report)


def main():
    immut=verify_d4b()
    diag,_=kernel_and_collinearity()
    z,extra=failure_morphology()
    daily_aggregation_audit()
    mq_lineage()
    stage_relationships(z)
    avail=multiyear_audit()
    model_protocol(avail)
    final_report(immut,diag,extra,avail)
    manifest_path=OUT/"stage_d5_round1_manifest.json"
    files=[]
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and p != manifest_path:
            files.append({"path":str(p.relative_to(OUT)).replace("\\","/"),"size_bytes":p.stat().st_size,"sha256":sha256(p)})
    dump(manifest_path,{"status":"complete_round1_stop","frozen_at":"2026-07-31","no_new_model_training":True,
        "d4b_modified":False,"2011_role":"revealed_year_retrospective_diagnosis_only","output_file_count":len(files),"output_files":files})


if __name__ == "__main__":
    main()
