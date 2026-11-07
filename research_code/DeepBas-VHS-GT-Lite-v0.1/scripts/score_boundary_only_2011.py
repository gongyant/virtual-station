from __future__ import annotations

import csv
import hashlib
import json
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"E:\CodexProject\DeepBas-VHS-GT-Lite-v0.1")
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b"
PLOTS = OUT / "plots"
PREDICTION_FILE = OUT / "boundary_only_2011_predictions_frozen.csv"
MANIFEST_FILE = OUT / "boundary_only_2011_prediction_manifest.json"
LABEL_FILE = OUT / "daily_discharge_2011_canonical.csv"
PROTOCOL_FILE = OUT / "boundary_only_2011_evaluation_protocol_frozen.json"
COMPLETION_FILE = OUT / "boundary_only_2011_scoring_completion.json"
MODEL = "C_EXT_boundary_only_K10"
EVAL_NAME = "预注册跨年份评估"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(np.corrcoef(a, b)[0, 1])


def metrics(obs: np.ndarray, pred: np.ndarray) -> dict:
    err = pred - obs
    den = float(np.sum((obs - np.mean(obs)) ** 2))
    nse = float(1 - np.sum(err ** 2) / den) if den > 0 else float("nan")
    pearson = safe_corr(obs, pred)
    obs_rank = pd.Series(obs).rank(method="average").to_numpy(float)
    pred_rank = pd.Series(pred).rank(method="average").to_numpy(float)
    spearman = safe_corr(obs_rank, pred_rank)
    alpha = float(np.std(pred, ddof=0) / np.std(obs, ddof=0)) if np.std(obs, ddof=0) > 0 else float("nan")
    beta = float(np.mean(pred) / np.mean(obs)) if np.mean(obs) != 0 else float("nan")
    kge = float(1 - math.sqrt((pearson - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)) if all(np.isfinite([pearson, alpha, beta])) else float("nan")
    obs_volume = float(np.sum(obs) * 86400.0)
    pred_volume = float(np.sum(pred) * 86400.0)
    return {
        "NSE": nse,
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "MAE": float(np.mean(np.abs(err))),
        "KGE": kge,
        "PBIAS": float(100 * np.sum(err) / np.sum(obs)) if np.sum(obs) != 0 else float("nan"),
        "Pearson": pearson,
        "Spearman": spearman,
        "observed_volume_m3": obs_volume,
        "predicted_volume_m3": pred_volume,
        "cumulative_volume_bias_m3": pred_volume - obs_volume,
        "cumulative_volume_bias_pct": float(100 * (pred_volume - obs_volume) / obs_volume) if obs_volume else float("nan"),
        "observed_mean_m3s": float(np.mean(obs)),
        "predicted_mean_m3s": float(np.mean(pred)),
    }


def clean(v):
    if isinstance(v, (float, np.floating)):
        return "" if not np.isfinite(v) else round(float(v), 10)
    return v


def write_rows(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: clean(v) for k, v in row.items()})


def get_font(size: int):
    for p in [Path(r"C:\Windows\Fonts\msyh.ttc"), Path(r"C:\Windows\Fonts\simhei.ttf")]:
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def line_plot(df: pd.DataFrame, path: Path, title: str, shade_primary: bool = False) -> None:
    W, H, m = 1500, 760, 85
    im = Image.new("RGB", (W, H), "#FFFFFF")
    dr = ImageDraw.Draw(im)
    x0, x1, y0, y1 = m, W - 45, H - m, 70
    ymax = max(float(df.q_obs.max()), float(df.q_pred.max())) * 1.08
    n = len(df)
    def xp(i): return x0 + i / max(1, n - 1) * (x1 - x0)
    def yp(v): return y0 - float(v) / ymax * (y0 - y1)
    if shade_primary:
        mask = (df.date >= pd.Timestamp("2011-05-11")) & (df.date <= pd.Timestamp("2011-08-31"))
        idx = np.flatnonzero(mask.to_numpy())
        if len(idx): dr.rectangle((xp(idx[0]), y1, xp(idx[-1]), y0), fill="#FFF4D6")
    dr.line((x0, y0, x1, y0), fill="#34495E", width=2)
    dr.line((x0, y1, x0, y0), fill="#34495E", width=2)
    obs_pts = [(xp(i), yp(v)) for i, v in enumerate(df.q_obs)]
    pred_pts = [(xp(i), yp(v)) for i, v in enumerate(df.q_pred)]
    dr.line(obs_pts, fill="#17202A", width=3)
    dr.line(pred_pts, fill="#C0392B", width=3)
    dr.text((m, 18), title, fill="#17202A", font=get_font(30))
    dr.line((W - 410, 32, W - 365, 32), fill="#17202A", width=4); dr.text((W - 355, 17), "实测DSK Q", fill="#17202A", font=get_font(20))
    dr.line((W - 210, 32, W - 165, 32), fill="#C0392B", width=4); dr.text((W - 155, 17), "冻结预测", fill="#C0392B", font=get_font(20))
    for frac in [0, .25, .5, .75, 1]:
        y = yp(ymax * frac); dr.line((x0 - 5, y, x0, y), fill="#34495E", width=1); dr.text((8, y - 10), f"{ymax*frac:.0f}", fill="#566573", font=get_font(17))
    im.save(path)


def scatter_plot(df: pd.DataFrame, path: Path) -> None:
    W, H, m = 760, 760, 85
    im = Image.new("RGB", (W, H), "white"); dr = ImageDraw.Draw(im)
    vmax = max(float(df.q_obs.max()), float(df.q_pred.max())) * 1.05
    def xy(a, b): return (m + a / vmax * (W - 2*m), H - m - b / vmax * (H - 2*m))
    dr.line((*xy(0,0), *xy(vmax,vmax)), fill="#7F8C8D", width=2)
    for a,b in zip(df.q_obs, df.q_pred):
        x,y=xy(float(a),float(b)); dr.ellipse((x-3,y-3,x+3,y+3),fill="#2471A3")
    dr.line((m,H-m,W-m,H-m),fill="#34495E",width=2); dr.line((m,m,m,H-m),fill="#34495E",width=2)
    dr.text((m,18),"主窗口：实测与冻结预测散点",fill="#17202A",font=get_font(28))
    dr.text((W//2-80,H-45),"实测Q (m³/s)",fill="#34495E",font=get_font(19))
    dr.text((8,m-30),"预测Q",fill="#34495E",font=get_font(19))
    im.save(path)


def monthly_plot(monthly: pd.DataFrame, path: Path) -> None:
    d = monthly[monthly.window_id == "full_year_extrapolation_diagnostic"].copy()
    W,H,m=1400,720,80
    im=Image.new("RGB",(W,H),"white"); dr=ImageDraw.Draw(im)
    ymax=max(float(d.observed_mean_m3s.max()),float(d.predicted_mean_m3s.max()))*1.15
    base=H-m; plot_h=H-2*m; group_w=(W-2*m)/12
    for i,r in enumerate(d.itertuples()):
        cx=m+(i+.5)*group_w; bw=group_w*.28
        oh=float(r.observed_mean_m3s)/ymax*plot_h; ph=float(r.predicted_mean_m3s)/ymax*plot_h
        dr.rectangle((cx-bw-2,base-oh,cx-2,base),fill="#34495E")
        dr.rectangle((cx+2,base-ph,cx+bw+2,base),fill="#C0392B")
        dr.text((cx-12,base+12),str(int(r.month)),fill="#34495E",font=get_font(17))
    dr.line((m,base,W-m,base),fill="#34495E",width=2)
    dr.text((m,18),"全年外推诊断：月平均流量",fill="#17202A",font=get_font(30))
    dr.text((W-330,24),"黑：实测  红：预测",fill="#566573",font=get_font(20))
    im.save(path)


def regime_plot(regime: pd.DataFrame, path: Path) -> None:
    d=regime[regime.window_id=="primary"].copy(); labels=["低流量","中流量","高流量"]
    W,H,m=900,650,85; im=Image.new("RGB",(W,H),"white"); dr=ImageDraw.Draw(im)
    ymax=float(d.RMSE.max())*1.2
    for i,(r,label) in enumerate(zip(d.itertuples(),labels)):
        x=m+(i+.5)*(W-2*m)/3; bw=110; height=float(r.RMSE)/ymax*(H-2*m)
        dr.rectangle((x-bw/2,H-m-height,x+bw/2,H-m),fill=["#5DADE2","#F5B041","#C0392B"][i])
        dr.text((x-40,H-m+12),label,fill="#34495E",font=get_font(19)); dr.text((x-38,H-m-height-28),f"{r.RMSE:.1f}",fill="#17202A",font=get_font(18))
    dr.line((m,H-m,W-m,H-m),fill="#34495E",width=2)
    dr.text((m,18),"主窗口分流量区间RMSE",fill="#17202A",font=get_font(30))
    im.save(path)


def main() -> None:
    if COMPLETION_FILE.exists():
        raise SystemExit("one-time 2011 scoring already completed; rerun is forbidden")
    manifest = json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
    prediction_sha = sha256(PREDICTION_FILE)
    if prediction_sha != manifest.get("prediction_sha256") or not manifest.get("prediction_frozen_before_scoring"):
        raise SystemExit("prediction file is not hash-frozen; label access forbidden")
    protocol = json.loads(PROTOCOL_FILE.read_text(encoding="utf-8"))
    if protocol.get("window_selection_used_2011_dsk_labels") is not False:
        raise SystemExit("evaluation window protocol is not valid")

    pred = pd.read_csv(PREDICTION_FILE, parse_dates=["date"])
    if len(pred) != 355 or pred.parameter_sha256.nunique() != 1 or pred.input_sha256.nunique() != 1:
        raise SystemExit("frozen prediction schema/hash columns are inconsistent")
    labels = pd.read_csv(LABEL_FILE, dtype={"station_id": str}, parse_dates=["date"])
    labels = labels[labels.station_id == "00705700"][["date", "discharge_m3s"]].rename(columns={"discharge_m3s":"q_obs"})
    if len(labels) != 365 or labels.q_obs.isna().any():
        raise SystemExit("DSK scoring labels are not a complete reviewed 2011 series")
    df = pred.merge(labels, on="date", how="left", validate="one_to_one")
    df["q_pred"] = pd.to_numeric(df.q_pred)
    df["q_obs"] = pd.to_numeric(df.q_obs)
    if df.q_obs.isna().any():
        raise SystemExit("missing DSK labels in frozen prediction dates")

    windows = [
        ("primary", "2011-05-11", "2011-08-31", df.window_primary.astype(bool)),
        ("full_year_extrapolation_diagnostic", "2011-01-11", "2011-12-31", df.window_full_year_diagnostic.astype(bool)),
    ]
    metric_rows=[]; regime_rows=[]; monthly_rows=[]; peak_rows=[]
    for window_id,start,end,mask in windows:
        d=df.loc[mask].copy().sort_values("date")
        obs=d.q_obs.to_numpy(float); pr=d.q_pred.to_numpy(float)
        mm=metrics(obs,pr)
        metric_rows.append({"model_name":MODEL,"evaluation_name_zh":EVAL_NAME,"window_id":window_id,"start_date":start,"end_date":end,"n_days":len(d),**mm,"pbias_sign_convention":"positive=overprediction"})
        q1,q2=np.quantile(obs,[1/3,2/3])
        groups=[("low",obs<=q1),("medium",(obs>q1)&(obs<=q2)),("high",obs>q2)]
        for regime,m in groups:
            e=pr[m]-obs[m]
            regime_rows.append({"model_name":MODEL,"evaluation_name_zh":EVAL_NAME,"window_id":window_id,"flow_regime":regime,"observed_tercile_low_threshold":q1,"observed_tercile_high_threshold":q2,"n_days":int(m.sum()),"RMSE":float(np.sqrt(np.mean(e**2))),"MAE":float(np.mean(np.abs(e))),"mean_error":float(np.mean(e)),"PBIAS":float(100*np.sum(e)/np.sum(obs[m]))})
        oi=int(np.argmax(obs)); pi=int(np.argmax(pr)); od=d.date.iloc[oi]; pdte=d.date.iloc[pi]
        peak_rows.append({"model_name":MODEL,"evaluation_name_zh":EVAL_NAME,"window_id":window_id,"observed_peak_date":od.date().isoformat(),"predicted_peak_date":pdte.date().isoformat(),"peak_date_error_days":int((pdte-od).days),"observed_peak_m3s":float(obs[oi]),"predicted_peak_m3s":float(pr[pi]),"peak_amplitude_error_m3s":float(pr[pi]-obs[oi]),"peak_amplitude_error_pct":float(100*(pr[pi]-obs[oi])/obs[oi])})
        for month,g in d.groupby(d.date.dt.month):
            x=metrics(g.q_obs.to_numpy(float),g.q_pred.to_numpy(float))
            monthly_rows.append({"model_name":MODEL,"evaluation_name_zh":EVAL_NAME,"window_id":window_id,"month":int(month),"start_date":g.date.min().date().isoformat(),"end_date":g.date.max().date().isoformat(),"n_days":len(g),**x})

    metrics_path=OUT/"boundary_only_2011_external_metrics.csv"; regime_path=OUT/"boundary_only_2011_flow_regime_metrics.csv"; monthly_path=OUT/"boundary_only_2011_monthly_metrics.csv"; peak_path=OUT/"boundary_only_2011_peak_diagnostics.csv"
    write_rows(metrics_path,metric_rows); write_rows(regime_path,regime_rows); write_rows(monthly_path,monthly_rows); write_rows(peak_path,peak_rows)
    PLOTS.mkdir(parents=True,exist_ok=True)
    line_plot(df,PLOTS/"boundary_only_2011_timeseries.png",f"{MODEL}：2011全年外推诊断",shade_primary=True)
    primary=df[df.window_primary.astype(bool)].copy()
    line_plot(primary,PLOTS/"boundary_only_2011_primary_window_timeseries.png",f"{MODEL}：主窗口 2011-05-11至2011-08-31")
    scatter_plot(primary,PLOTS/"boundary_only_2011_primary_scatter.png")
    monthly_df=pd.DataFrame(monthly_rows); monthly_plot(monthly_df,PLOTS/"boundary_only_2011_monthly_means.png")
    regime_df=pd.DataFrame(regime_rows); regime_plot(regime_df,PLOTS/"boundary_only_2011_primary_flow_regime_rmse.png")

    md=pd.DataFrame(metric_rows).set_index("window_id"); pk=pd.DataFrame(peak_rows).set_index("window_id")
    def row(w,label):
        r=md.loc[w]
        return f"|{label}|{int(r.n_days)}|{r.NSE:.4f}|{r.RMSE:.3f}|{r.MAE:.3f}|{r.KGE:.4f}|{r.PBIAS:.2f}%|{r.Pearson:.4f}|{r.Spearman:.4f}|"
    report=f"""# 阶段D4B：{MODEL}一次性评分报告

## 评估身份

本结果正式称为“{MODEL}预注册跨年份评估”。模型只使用巴音布鲁克当日及前10日流量，系数由2005开发期标签拟合，属于P1跨年迁移。预测文件在读取2011大山口评分标签前已生成并冻结哈希。

## 一次性结果

|窗口|天数|NSE|RMSE|MAE|KGE|PBIAS|Pearson|Spearman|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{row('primary','主窗口：2011-05-11至08-31')}
{row('full_year_extrapolation_diagnostic','全年外推诊断：2011-01-11至12-31')}

PBIAS采用“预测减实测”的符号，正值表示总体高估。累计水量偏差已写入指标CSV，冬季结果完整保留。

## 洪峰诊断

- 主窗口：实测峰值{pk.loc['primary'].observed_peak_m3s:.1f} m³/s（{pk.loc['primary'].observed_peak_date}）；预测峰值{pk.loc['primary'].predicted_peak_m3s:.1f} m³/s（{pk.loc['primary'].predicted_peak_date}）；日期误差{int(pk.loc['primary'].peak_date_error_days)}天，幅度误差{pk.loc['primary'].peak_amplitude_error_m3s:.1f} m³/s。
- 全年外推诊断：实测峰值{pk.loc['full_year_extrapolation_diagnostic'].observed_peak_m3s:.1f} m³/s；预测峰值{pk.loc['full_year_extrapolation_diagnostic'].predicted_peak_m3s:.1f} m³/s；日期误差{int(pk.loc['full_year_extrapolation_diagnostic'].peak_date_error_days)}天。

## 纪律与解释边界

- 本次评分后不修改K=10、权重、截距、正则化或主窗口。
- 没有使用焉耆、水位、DEM、MQ或GNN修补结果。
- 分流量区间、月尺度、累计水量及峰值诊断均为同一冻结预测的派生评分，不是再次选模。
- 后续任何改进必须另开阶段，并以本次结果作为已揭示结果。
"""
    report_path=OUT/"stage_d4b_report_zh.md"; report_path.write_text(report,encoding="utf-8")

    outputs=[metrics_path,regime_path,monthly_path,peak_path,report_path,*sorted(PLOTS.glob("*.png"))]
    completion={"schema_version":"1.0","model_name":MODEL,"evaluation_name_zh":EVAL_NAME,"scoring_completed_at":datetime.now(timezone(timedelta(hours=8))).isoformat(),"one_time_scoring_completed":True,"prediction_sha256":prediction_sha,"prediction_manifest_sha256":sha256(MANIFEST_FILE),"evaluation_protocol_sha256":sha256(PROTOCOL_FILE),"label_file_sha256_at_scoring":sha256(LABEL_FILE),"scoring_program_sha256":sha256(Path(__file__)),"output_sha256":{str(p.relative_to(OUT)).replace('\\','/'):sha256(p) for p in outputs},"post_score_model_changes_authorized":False}
    COMPLETION_FILE.write_text(json.dumps(completion,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"one_time_scoring_complete","prediction_sha256":prediction_sha,"primary_NSE":metric_rows[0]["NSE"],"full_year_NSE":metric_rows[1]["NSE"]},ensure_ascii=False))


if __name__ == "__main__":
    main()
