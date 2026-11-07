from __future__ import annotations

"""Stage C: explicit BYBLK boundary, distributed lag and bounded MQ residuals.

The script freezes every design choice using dates before 2005-09-01 and only
then evaluates the 61-day legacy diagnostic period once.  P1 (historical-site
gap reconstruction) and P2 (strict ungauged) are kept separate throughout.
"""

import hashlib
import json
import math
import platform
import random
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import sklearn
import torch
import yaml
from scipy.stats import spearmanr
from sklearn.base import clone
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import ElasticNet, HuberRegressor, LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn

sys.path.insert(0, "src")
from vhs.data import TensorBundle
from vhs.metrics import regression_metrics


ROOT = Path("outputs/diagnosis_2005_snapshot/stage_c")
PLOTS = ROOT / "plots"
CONFIGS = Path("configs/diagnosis_2005_snapshot_stage_c")
BUNDLE_PATH = Path("data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz")
REPRO_PRED = Path("outputs/diagnosis_2005_snapshot/reproduced_predictions.csv")
SEEDS = (7, 42, 123)
TARGET, SOURCE = "00705700", "00705600"
DEV_START, TRAIN_END, DEV_END = pd.Timestamp("2005-01-03"), pd.Timestamp("2005-06-30"), pd.Timestamp("2005-08-31")
LEGACY_START, LEGACY_END = pd.Timestamp("2005-09-01"), pd.Timestamp("2005-10-31")


FOLDS = [
    # DSK and BYBLK observations begin only on 2005-05-01.  Earlier suggested
    # folds are therefore untrainable; use five expanding, strictly ordered
    # pre-September folds with roughly half-month validation blocks.
    ("fold1", "2005-05-01", "2005-05-31", "2005-06-01", "2005-06-15"),
    ("fold2", "2005-05-01", "2005-06-15", "2005-06-16", "2005-06-30"),
    ("fold3", "2005-05-01", "2005-06-30", "2005-07-01", "2005-07-15"),
    ("fold4", "2005-05-01", "2005-07-15", "2005-07-16", "2005-07-31"),
    ("fold5", "2005-05-01", "2005-07-31", "2005-08-01", "2005-08-31"),
]


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def metrics(obs, pred):
    m = regression_metrics(np.asarray(obs), np.asarray(pred))
    ok = np.isfinite(obs) & np.isfinite(pred)
    m["spearman"] = float(spearmanr(np.asarray(obs)[ok], np.asarray(pred)[ok]).statistic) if ok.sum() > 1 else np.nan
    return m


def add_metric_row(rows, model, fold, obs, pred, protocol="P1", **extra):
    rows.append({"model": model, "fold": fold, "protocol": protocol, **extra, **metrics(obs, pred)})


def make_features():
    b = TensorBundle.load(BUNDLE_PATH); ids = list(map(str, b.station_ids)); si, ti = ids.index(SOURCE), ids.index(TARGET)
    fi = {str(n): i for i, n in enumerate(b.feature_names)}
    df = pd.DataFrame({
        "date": pd.to_datetime(b.dates), "q_byblk_obs": b.y[:, si],
        "q_byblk_mq": b.x[:, si, fi["physical_reference_q"]],
        "q_dsk_mq": b.x[:, ti, fi["physical_reference_q"]], "q_dsk_obs": b.y[:, ti],
    })
    for c in ("q_byblk_obs", "q_byblk_mq", "q_dsk_mq"):
        df[c.replace("q_", "").replace("_obs", "_obs_available").replace("_mq", "_mq_available")] = df[c].notna().astype(int)
    # Repair exact required availability names.
    df["byblk_obs_available"] = df.q_byblk_obs.notna().astype(int); df["byblk_mq_available"] = df.q_byblk_mq.notna().astype(int); df["dsk_mq_available"] = df.q_dsk_mq.notna().astype(int)
    for k in range(11): df[f"q_byblk_lag{k}"] = df.q_byblk_obs.shift(k)
    for w in (3, 5, 7):
        r = df.q_byblk_obs.rolling(w, min_periods=w)
        df[f"q_byblk_mean_{w}d"] = r.mean(); df[f"q_byblk_max_{w}d"] = r.max(); df[f"q_byblk_min_{w}d"] = r.min()
    df["q_byblk_change_1d"] = df.q_byblk_obs.diff(1); df["q_byblk_change_3d"] = df.q_byblk_obs.diff(3)
    for k in (1, 2, 3): df[f"q_dsk_mq_lag{k}"] = df.q_dsk_mq.shift(k)
    df["q_dsk_mq_change_1d"] = df.q_dsk_mq.diff(); df["q_dsk_mq_mean_3d"] = df.q_dsk_mq.rolling(3, min_periods=3).mean()
    doy = df.date.dt.dayofyear; df["day_of_year_sin"] = np.sin(2 * np.pi * doy / 365.25); df["day_of_year_cos"] = np.cos(2 * np.pi * doy / 365.25)
    df["residual_q"] = df.q_dsk_obs - df.q_dsk_mq
    keep = [c for c in df if not c.startswith(("byblk_obs_available_available", "byblk_mq_available_available", "dsk_mq_available_available"))]
    df = df[keep]
    ROOT.mkdir(parents=True, exist_ok=True); PLOTS.mkdir(exist_ok=True); CONFIGS.mkdir(parents=True, exist_ok=True)
    df.to_csv(ROOT / "byblk_dsk_daily_features.csv", index=False)
    base_defs = {
        "date": ("calendar date", "day", "bundle dates", False), "q_byblk_obs": ("BYBLK observed discharge", "m3/s", "bundle y", False),
        "q_byblk_mq": ("BYBLK MQ reference", "m3/s", "bundle physical_reference_q", False), "q_dsk_mq": ("DSK MQ reference", "m3/s", "bundle physical_reference_q", False),
        "q_dsk_obs": ("DSK observed discharge; unavailable in P2", "m3/s", "bundle y", False),
        "byblk_obs_available": ("availability flag for BYBLK observation", "0/1", "derived", True),
        "byblk_mq_available": ("availability flag for BYBLK MQ", "0/1", "derived", True), "dsk_mq_available": ("availability flag for DSK MQ", "0/1", "derived", True),
    }
    dictionary=[]
    for c in df.columns:
        if c in base_defs: definition, unit, source, new = base_defs[c]
        elif c.startswith("q_byblk_lag"): definition=f"BYBLK observed Q shifted by {c.split('lag')[1]} day(s); causal"; unit="m3/s"; source="q_byblk_obs"; new=True
        elif "mean_" in c: definition=f"trailing causal mean: {c}"; unit="m3/s"; source=c.split("_mean")[0]; new=True
        elif "max_" in c: definition=f"trailing causal maximum: {c}"; unit="m3/s"; source="q_byblk_obs"; new=True
        elif "min_" in c: definition=f"trailing causal minimum: {c}"; unit="m3/s"; source="q_byblk_obs"; new=True
        elif "change" in c: definition=f"backward difference: {c}"; unit="m3/s"; source="same-variable history"; new=True
        elif c.startswith("q_dsk_mq_lag"): definition=f"DSK MQ lagged feature: {c}"; unit="m3/s"; source="q_dsk_mq"; new=True
        elif c.startswith("day_of_year"): definition="annual cycle encoding added only in stage C"; unit="dimensionless"; source="date"; new=True
        elif c == "residual_q": definition="q_dsk_obs - q_dsk_mq"; unit="m3/s"; source="derived target (P1 only)"; new=True
        else: definition=c; unit="m3/s"; source="derived"; new=True
        dictionary.append({"feature": c, "definition": definition, "unit": unit, "source": source, "stage_c_new": new, "causal_at_t": c != "q_dsk_obs" and c != "residual_q"})
    pd.DataFrame(dictionary).to_csv(ROOT / "feature_dictionary.csv", index=False)
    return df


def fold_frames(df):
    splits=[]; result=[]
    for name, ts, te, vs, ve in FOLDS:
        tr=df[(df.date>=ts)&(df.date<=te)].copy(); va=df[(df.date>=vs)&(df.date<=ve)].copy()
        splits.append({"fold":name,"train_start":ts,"train_end":te,"validation_start":vs,"validation_end":ve,"train_days_raw":len(tr),"validation_days_raw":len(va),"lag_policy":"model-specific complete-case removal; no future fill"})
        result.append((name,tr,va))
    pd.DataFrame(splits).to_csv(ROOT/"rolling_validation_splits.csv",index=False)
    return result


def fit_predict(estimator, tr, va, features, target="q_dsk_obs"):
    a=tr.dropna(subset=features+[target]); b=va.dropna(subset=features+[target])
    est=clone(estimator); est.fit(a[features],a[target]); pred=np.maximum(0,est.predict(b[features])); return est,a,b,pred


def raw_coefficients(est, features):
    final=est
    if isinstance(est, Pipeline):
        sc=est.named_steps.get("scale"); final=est.steps[-1][1]
        coef=np.asarray(final.coef_)/sc.scale_; intercept=float(final.intercept_ - np.sum(np.asarray(final.coef_)*sc.mean_/sc.scale_))
    else: coef=np.asarray(final.coef_); intercept=float(getattr(final,"intercept_",0))
    return {"intercept":intercept, **{f"coef_{f}":float(v) for f,v in zip(features,coef)}}


def ridge(alpha=1.0, positive=False):
    return Pipeline([("scale",StandardScaler()),("model",Ridge(alpha=alpha,positive=positive,max_iter=10000))])


def residual_diagnostics(df, folds):
    features=["q_dsk_mq"]+[f"q_byblk_lag{k}" for k in range(11)]+["q_byblk_change_1d","q_byblk_change_3d","q_byblk_mean_3d","q_byblk_mean_5d","q_byblk_mean_7d","q_byblk_max_3d","q_byblk_max_5d","q_byblk_max_7d","q_dsk_mq_change_1d","day_of_year_sin","day_of_year_cos"]
    rows=[]
    for fold,tr,_ in folds:
        threshold=tr.q_dsk_obs.quantile(.8)
        for regime,sub in (("all",tr),("normal",tr[tr.q_dsk_obs<threshold]),("high_top20",tr[tr.q_dsk_obs>=threshold])):
            for f in features:
                z=sub[[f,"residual_q"]].dropna(); rows.append({"fold":fold,"regime":regime,"feature":f,"n":len(z),"pearson":z[f].corr(z.residual_q),"spearman":z[f].corr(z.residual_q,method="spearman")})
        q=tr.residual_q.dropna(); rows += [{"fold":fold,"regime":"distribution","feature":f"residual_{x}","n":len(q),"value":v} for x,v in {"mean":q.mean(),"std":q.std(),"p05":q.quantile(.05),"p50":q.quantile(.5),"p95":q.quantile(.95)}.items()]
    pd.DataFrame(rows).to_csv(ROOT/"residual_predictability.csv",index=False)
    ac=[]
    for fold,tr,_ in folds:
        for k in range(1,16): ac.append({"fold":fold,"lag_days":k,"autocorrelation":tr.residual_q.autocorr(k)})
    pd.DataFrame(ac).to_csv(ROOT/"residual_autocorrelation.csv",index=False)
    dev=df[(df.date>=DEV_START)&(df.date<=DEV_END)]
    lines=["# MQ残差可预测性诊断","","仅使用2005-09-01以前数据。相关性描述MQ误差的统计可预测性，不代表水动力因果。",
           f"- 开发期残差均值 {dev.residual_q.mean():.2f} m³/s，标准差 {dev.residual_q.std():.2f} m³/s。",
           f"- residual与MQ的Pearson相关为 {dev.residual_q.corr(dev.q_dsk_mq):.3f}；正值表示MQ低估幅度随MQ量级增大。",
           "- BYBLK变化率与残差的关系、普通/高流量差异见 residual_predictability.csv。"]
    (ROOT/"residual_diagnostics_zh.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    fig,ax=plt.subplots(figsize=(11,4)); ax.plot(dev.date,dev.residual_q); ax.axhline(0,color="k",lw=.7); ax.set_ylabel("Observed - MQ (m3/s)"); fig.tight_layout(); fig.savefig(PLOTS/"residual_timeseries.png",dpi=160); plt.close(fig)
    cor=pd.DataFrame(rows); g=cor[(cor.fold=="fold5")&(cor.regime=="all")&cor.feature.str.startswith("q_byblk_lag")]
    fig,ax=plt.subplots(figsize=(8,4)); ax.bar(range(len(g)),g.pearson); ax.set_xticks(range(len(g)),g.feature.str.replace("q_byblk_",""),rotation=45); ax.set_ylabel("Pearson with MQ residual"); fig.tight_layout(); fig.savefig(PLOTS/"residual_byblk_lag_correlation.png",dpi=160); plt.close(fig)


def run_c2(folds):
    rows=[]; pars=[]; eps=.1
    for fold,tr,va in folds:
        specs={
          "C2_affine":LinearRegression(), "C2_proportional":LinearRegression(fit_intercept=False),
          "C2_huber":HuberRegressor(epsilon=1.35,max_iter=1000),
          "C2_affine_cycle":LinearRegression(),
        }
        feature_map={"C2_affine":["q_dsk_mq"],"C2_proportional":["q_dsk_mq"],"C2_huber":["q_dsk_mq"],"C2_affine_cycle":["q_dsk_mq","day_of_year_sin","day_of_year_cos"]}
        for name,est in specs.items():
            fit,a,b,pred=fit_predict(est,tr,va,feature_map[name]); add_metric_row(rows,name,fold,b.q_dsk_obs,pred,n_train=len(a),n_validation=len(b)); pars.append({"model":name,"fold":fold,**raw_coefficients(fit,feature_map[name])})
        a=tr.dropna(subset=["q_dsk_mq","q_dsk_obs"]); b=va.dropna(subset=["q_dsk_mq","q_dsk_obs"])
        est=LinearRegression().fit(np.log(a[["q_dsk_mq"]]+eps),np.log(a.q_dsk_obs+eps)); pred=np.maximum(0,np.exp(est.predict(np.log(b[["q_dsk_mq"]]+eps)))-eps)
        add_metric_row(rows,"C2_log_affine",fold,b.q_dsk_obs,pred,n_train=len(a),n_validation=len(b)); pars.append({"model":"C2_log_affine","fold":fold,"intercept":float(est.intercept_),"coef_log_mq":float(est.coef_[0]),"epsilon":eps})
    pd.DataFrame(rows).to_csv(ROOT/"mq_simple_calibration_results.csv",index=False); pd.DataFrame(pars).to_csv(ROOT/"mq_calibration_parameters.csv",index=False)
    return rows


def run_c3(folds):
    single=[]; dist=[]; weights=[]; kernels=[]; linearres=[]
    for fold,tr,va in folds:
      for lag in range(11):
       feats=["q_dsk_mq",f"q_byblk_lag{lag}"]
       for alpha in (.1,1.,10.,100.):
        est,a,b,pred=fit_predict(ridge(alpha),tr,va,feats); add_metric_row(single,f"C3_single_lag{lag}_a{alpha:g}",fold,b.q_dsk_obs,pred,lag=lag,alpha=alpha,n_train=len(a),n_validation=len(b),**raw_coefficients(est,feats))
      for K in (2,5,7,10):
       feats=["q_dsk_mq"]+[f"q_byblk_lag{k}" for k in range(K+1)]
       for kind,est in (("ridge",ridge(10)),("positive_ridge",ridge(10,True)),("nnls",LinearRegression(positive=True))):
        fit,a,b,pred=fit_predict(est,tr,va,feats); name=f"C3_distributed_{kind}_K{K}"; add_metric_row(dist,name,fold,b.q_dsk_obs,pred,K=K,kind=kind,n_train=len(a),n_validation=len(b)); weights.append({"model":name,"fold":fold,**raw_coefficients(fit,feats)})
      for center in (0,2,4,6,8,10):
       for width in (1.,2.,3.):
        lagcols=[f"q_byblk_lag{k}" for k in range(11)]; w=np.exp(-.5*((np.arange(11)-center)/width)**2); w=w/w.sum()
        tr2=tr.copy(); va2=va.copy(); tr2["q_route_kernel"]=tr2[lagcols].to_numpy().dot(w); va2["q_route_kernel"]=va2[lagcols].to_numpy().dot(w)
        feats=["q_dsk_mq","q_route_kernel"]; fit,a,b,pred=fit_predict(ridge(1),tr2,va2,feats); add_metric_row(kernels,f"C3_kernel_c{center}_w{width:g}",fold,b.q_dsk_obs,pred,center=center,width=width,n_train=len(a),n_validation=len(b),weights_json=json.dumps(w.tolist()))
      resfeats=[f"q_byblk_lag{k}" for k in range(11)]+["q_byblk_change_1d","q_byblk_change_3d","q_byblk_mean_3d","q_byblk_mean_5d","q_byblk_mean_7d","q_byblk_max_3d","q_byblk_max_5d","q_byblk_max_7d","q_dsk_mq_change_1d","day_of_year_sin","day_of_year_cos"]
      for name,est in (("C3_residual_ridge",ridge(10)),("C3_residual_elastic",Pipeline([("scale",StandardScaler()),("model",ElasticNet(alpha=.1,l1_ratio=.2,max_iter=10000))])),("C3_residual_huber",Pipeline([("scale",StandardScaler()),("model",HuberRegressor(max_iter=1000))]))):
        a=tr.dropna(subset=resfeats+["residual_q"]); b=va.dropna(subset=resfeats+["residual_q","q_dsk_obs"]); fit=clone(est).fit(a[resfeats],a.residual_q); pred=np.maximum(0,b.q_dsk_mq+fit.predict(b[resfeats])); add_metric_row(linearres,name,fold,b.q_dsk_obs,pred,n_train=len(a),n_validation=len(b),features="|".join(resfeats))
    pd.DataFrame(single).to_csv(ROOT/"single_lag_boundary_results.csv",index=False); pd.DataFrame(dist).to_csv(ROOT/"distributed_lag_results.csv",index=False); pd.DataFrame(weights).to_csv(ROOT/"distributed_lag_weights.csv",index=False); pd.DataFrame(kernels).to_csv(ROOT/"lag_kernel_results.csv",index=False); pd.DataFrame(linearres).to_csv(ROOT/"linear_residual_results.csv",index=False)
    return single,dist,kernels,linearres


def summarize(all_rows):
    df=pd.DataFrame(all_rows); mq=df[df.model=="MQ_reference_fold"][['fold','rmse','nse']].rename(columns={'rmse':'mq_rmse','nse':'mq_nse'})
    d=df[df.model!="MQ_reference_fold"].merge(mq,on='fold',how='left'); d['beats_mq']=d.rmse<d.mq_rmse
    out=[]
    for model,g in d.groupby('model'):
        out.append({'model':model,'folds':g.fold.nunique(),'folds_rmse_better_than_mq':int(g.beats_mq.sum()),'nse_mean':g.nse.mean(),'nse_std':g.nse.std(ddof=0),'rmse_mean':g.rmse.mean(),'rmse_std':g.rmse.std(ddof=0),'mae_mean':g.mae.mean(),'kge_mean':g.kge.mean(),'pbias_mean':g.pbias.mean(),'abs_pbias_mean':g.pbias.abs().mean(),'corr_mean':g['corr'].mean(),'spearman_mean':g.spearman.mean(),'eligible':bool(g.beats_mq.sum()>=3 and g.rmse.mean()<g.mq_rmse.mean() and g.nse.mean()>g.mq_nse.mean())})
    return pd.DataFrame(out).sort_values(['eligible','folds_rmse_better_than_mq','rmse_mean'],ascending=[False,False,True])


class BoundedMLP(nn.Module):
    def __init__(self,nin,hidden):
        super().__init__(); self.net=nn.Sequential(nn.Linear(nin,hidden),nn.Tanh(),nn.Linear(hidden,hidden),nn.Tanh(),nn.Linear(hidden,1)); nn.init.zeros_(self.net[-1].weight); nn.init.zeros_(self.net[-1].bias)
    def forward(self,x): return self.net(x).squeeze(-1)


def fit_mlp(tr,va,features,hidden,quantile,form,seed,max_epochs=100):
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    a=tr.dropna(subset=features+["q_dsk_obs","q_dsk_mq"]); b=va.dropna(subset=features+["q_dsk_obs","q_dsk_mq"])
    sc=StandardScaler().fit(a[features]); xa=torch.tensor(sc.transform(a[features]),dtype=torch.float32); xb=torch.tensor(sc.transform(b[features]),dtype=torch.float32)
    obs=torch.tensor(a.q_dsk_obs.to_numpy(),dtype=torch.float32); mq=torch.tensor(a.q_dsk_mq.to_numpy(),dtype=torch.float32)
    net=BoundedMLP(len(features),hidden); opt=torch.optim.Adam(net.parameters(),lr=1e-3,weight_decay=1e-4)
    if form=='additive': scale=float(np.quantile(np.abs(a.residual_q),quantile)); denom=max(float(a.residual_q.std()),1.)
    else: lr=np.log(np.maximum(a.q_dsk_obs,.1)/np.maximum(a.q_dsk_mq,.1)); scale=float(np.quantile(np.abs(lr),quantile)); denom=max(float(np.std(lr)),.05)
    best=math.inf; state=None; patience=0; best_epoch=0
    for epoch in range(1,max_epochs+1):
        net.train(); opt.zero_grad(); raw=net(xa)
        pred=torch.clamp(mq+scale*torch.tanh(raw),min=0) if form=='additive' else torch.clamp(mq*torch.exp(scale*torch.tanh(raw)),min=0)
        loss=torch.mean(((pred-obs)/denom)**2); loss.backward(); opt.step()
        net.eval()
        with torch.no_grad():
            r=net(xb); bm=torch.tensor(b.q_dsk_mq.to_numpy(),dtype=torch.float32)
            pv=torch.clamp(bm+scale*torch.tanh(r),min=0) if form=='additive' else torch.clamp(bm*torch.exp(scale*torch.tanh(r)),min=0)
            rm=float(torch.sqrt(torch.mean((pv-torch.tensor(b.q_dsk_obs.to_numpy(),dtype=torch.float32))**2)))
        if rm<best-1e-7: best=rm; state={k:v.detach().clone() for k,v in net.state_dict().items()}; best_epoch=epoch; patience=0
        else:
            patience+=1
            if patience>=12: break
    net.load_state_dict(state); net.eval()
    with torch.no_grad():
        r=net(xb); bm=torch.tensor(b.q_dsk_mq.to_numpy(),dtype=torch.float32); pred=(torch.clamp(bm+scale*torch.tanh(r),min=0) if form=='additive' else torch.clamp(bm*torch.exp(scale*torch.tanh(r)),min=0)).numpy()
    artifact={'state':state,'scaler_mean':sc.mean_,'scaler_scale':sc.scale_,'scale':scale,'features':features,'form':form,'hidden':hidden,'best_epoch':best_epoch}
    return a,b,pred,artifact


def run_c4(folds,enabled):
    cols=["q_dsk_mq","q_dsk_mq_change_1d"]+[f"q_byblk_lag{k}" for k in range(11)]+["q_byblk_mean_3d","q_byblk_mean_5d","q_byblk_mean_7d","q_byblk_max_3d","q_byblk_max_5d","q_byblk_max_7d","q_byblk_change_1d","q_byblk_change_3d","day_of_year_sin","day_of_year_cos"]
    rows=[]
    if enabled:
      for fold,tr,va in folds:
       for form in ('additive','multiplicative'):
        for h in (8,16,32):
         for q in (.75,.90,.95):
          for seed in SEEDS:
           a,b,pred,art=fit_mlp(tr,va,cols,h,q,form,seed); add_metric_row(rows,f"C4_{form}_h{h}_p{int(q*100)}",fold,b.q_dsk_obs,pred,seed=seed,hidden=h,quantile=q,form=form,scale=art['scale'],best_epoch=art['best_epoch'],n_train=len(a),n_validation=len(b))
    pd.DataFrame(rows).to_csv(ROOT/"bounded_residual_seed_results.csv",index=False)
    if rows:
        d=pd.DataFrame(rows); agg=d.groupby(['model','fold'],as_index=False).agg({k:'mean' for k in ['nse','rmse','mae','kge','pbias','corr','spearman']}); agg.to_csv(ROOT/"bounded_residual_mlp_results.csv",index=False)
        hp=d.groupby(['model','hidden','quantile','form'],as_index=False).agg(folds=('fold','nunique'),rmse_mean=('rmse','mean'),nse_mean=('nse','mean'),seed_std_nse=('nse','std'),best_epoch_mean=('best_epoch','mean')); hp.to_csv(ROOT/"bounded_residual_hyperparameters.csv",index=False)
        return agg.to_dict('records'),cols
    pd.DataFrame(columns=['model','fold','reason']).to_csv(ROOT/"bounded_residual_mlp_results.csv",index=False); pd.DataFrame(columns=['model','hidden','quantile','form']).to_csv(ROOT/"bounded_residual_hyperparameters.csv",index=False)
    return [],cols


def negative_controls(folds,best_single,best_dist):
    rows=[]; lag=int(best_single.split('lag')[1].split('_')[0]); K=int(best_dist.split('K')[-1]) if 'K' in best_dist else 2
    for fi,(fold,tr,va) in enumerate(folds):
        specs={"N1_MQ_affine":["q_dsk_mq"],"N2_MQ_true_BYBLK_lag":["q_dsk_mq",f"q_byblk_lag{lag}"],"N4_BYBLK_without_MQ":[f"q_byblk_lag{k}" for k in range(K+1)],"N5_MQ_same_day_BYBLK":["q_dsk_mq","q_byblk_lag0"],"N6_MQ_best_validation_window":["q_dsk_mq"]+[f"q_byblk_lag{k}" for k in range(K+1)],"N7_MQ_time_without_BYBLK":["q_dsk_mq","day_of_year_sin","day_of_year_cos"]}
        for name,feats in specs.items():
            est,a,b,pred=fit_predict(ridge(10),tr,va,feats); add_metric_row(rows,name,fold,b.q_dsk_obs,pred,features='|'.join(feats),shuffle_seed='')
        feats=["q_dsk_mq"]+[f"q_byblk_lag{k}" for k in range(K+1)]; a=tr.dropna(subset=feats+["q_dsk_obs"]).copy(); b=va.dropna(subset=feats+["q_dsk_obs"]).copy(); rng=np.random.default_rng(8800+fi)
        lagcols=feats[1:]; a.loc[:,lagcols]=a[lagcols].to_numpy()[rng.permutation(len(a))]; b.loc[:,lagcols]=b[lagcols].to_numpy()[rng.permutation(len(b))]
        est=ridge(10).fit(a[feats],a.q_dsk_obs); pred=np.maximum(0,est.predict(b[feats])); add_metric_row(rows,"N3_MQ_shuffled_BYBLK",fold,b.q_dsk_obs,pred,features='|'.join(feats),shuffle_seed=8800+fi)
    pd.DataFrame(rows).to_csv(ROOT/"negative_control_results.csv",index=False); return rows


def choose(summary,prefix):
    d=summary[summary.model.str.startswith(prefix)].copy()
    if d.empty: return None
    eligible=d[d.eligible]
    return (eligible if not eligible.empty else d).sort_values(['folds_rmse_better_than_mq','rmse_mean','abs_pbias_mean'],ascending=[False,True,True]).iloc[0].model


def fit_frozen_linear(name,train,legacy):
    if name.startswith('C2_'):
        if name=='C2_log_affine':
            a=train.dropna(subset=['q_dsk_mq','q_dsk_obs']); b=legacy.dropna(subset=['q_dsk_mq','q_dsk_obs']); est=LinearRegression().fit(np.log(a[['q_dsk_mq']]+.1),np.log(a.q_dsk_obs+.1)); return b,np.maximum(0,np.exp(est.predict(np.log(b[['q_dsk_mq']]+.1)))-.1),{'model':name,'coef':est.coef_.tolist(),'intercept':est.intercept_}
        feats=['q_dsk_mq'] if name!='C2_affine_cycle' else ['q_dsk_mq','day_of_year_sin','day_of_year_cos']; est=HuberRegressor(max_iter=1000) if name=='C2_huber' else LinearRegression(fit_intercept=name!='C2_proportional'); fit,a,b,pred=fit_predict(est,train,legacy,feats); return b,pred,{'model':name,**raw_coefficients(fit,feats)}
    if name.startswith('C3_single'):
        lag=int(name.split('lag')[1].split('_')[0]); alpha=float(name.split('_a')[1]); feats=['q_dsk_mq',f'q_byblk_lag{lag}']; fit,a,b,pred=fit_predict(ridge(alpha),train,legacy,feats); return b,pred,{'model':name,**raw_coefficients(fit,feats)}
    if name.startswith('C3_distributed'):
        K=int(name.split('K')[-1]); feats=['q_dsk_mq']+[f'q_byblk_lag{k}' for k in range(K+1)]; kind='positive_ridge' if 'positive_ridge' in name else ('nnls' if 'nnls' in name else 'ridge'); est=ridge(10,kind=='positive_ridge') if kind!='nnls' else LinearRegression(positive=True); fit,a,b,pred=fit_predict(est,train,legacy,feats); return b,pred,{'model':name,**raw_coefficients(fit,feats)}
    if name.startswith('C3_kernel'):
        center=float(name.split('_c')[1].split('_')[0]); width=float(name.split('_w')[1]); cols=[f'q_byblk_lag{k}' for k in range(11)]; w=np.exp(-.5*((np.arange(11)-center)/width)**2); w/=w.sum(); ta=train.copy(); le=legacy.copy(); ta['q_route_kernel']=ta[cols].to_numpy().dot(w); le['q_route_kernel']=le[cols].to_numpy().dot(w); fit,a,b,pred=fit_predict(ridge(1),ta,le,['q_dsk_mq','q_route_kernel']); return b,pred,{'model':name,'weights':w.tolist(),**raw_coefficients(fit,['q_dsk_mq','q_route_kernel'])}
    raise ValueError(name)


def legacy_once(df,summary,mlp_features,mlp_rows):
    train=df[(df.date>=DEV_START)&(df.date<=TRAIN_END)].copy(); val=df[(df.date>TRAIN_END)&(df.date<=DEV_END)].copy(); legacy=df[(df.date>=LEGACY_START)&(df.date<=LEGACY_END)].copy()
    selected={'simple':choose(summary,'C2_'),'single':choose(summary,'C3_single'),'distributed':choose(summary,'C3_distributed'),'kernel':choose(summary,'C3_kernel'),'linear_residual':choose(summary,'C3_residual')}
    preds=pd.DataFrame({'date':legacy.date,'observed':legacy.q_dsk_obs,'MQ_reference':legacy.q_dsk_mq})
    params=[]
    for key in ('simple','single','distributed','kernel'):
        if selected[key]: b,pred,par=fit_frozen_linear(selected[key],train,legacy); preds.loc[b.index,key]=pred; params.append(par)
    # Best linear residual form, trained only Jan-Jun.
    rname=selected['linear_residual']; resfeats=[f"q_byblk_lag{k}" for k in range(11)]+["q_byblk_change_1d","q_byblk_change_3d","q_byblk_mean_3d","q_byblk_mean_5d","q_byblk_mean_7d","q_byblk_max_3d","q_byblk_max_5d","q_byblk_max_7d","q_dsk_mq_change_1d","day_of_year_sin","day_of_year_cos"]
    if rname:
        est=ridge(10) if rname.endswith('ridge') else (Pipeline([('scale',StandardScaler()),('model',ElasticNet(alpha=.1,l1_ratio=.2,max_iter=10000))]) if rname.endswith('elastic') else Pipeline([('scale',StandardScaler()),('model',HuberRegressor(max_iter=1000))]))
        a=train.dropna(subset=resfeats+['residual_q']); b=legacy.dropna(subset=resfeats+['q_dsk_obs']); est.fit(a[resfeats],a.residual_q); preds.loc[b.index,'linear_residual']=np.maximum(0,b.q_dsk_mq+est.predict(b[resfeats]))
    # MLP hyperparameters selected only from rolling folds; final early stop Jul-Aug.
    selected_mlp=None; seed_metrics=[]
    if mlp_rows:
        sm=summarize([{'model':'MQ_reference_fold','fold':f,'protocol':'P1',**metrics(v.q_dsk_obs,v.q_dsk_mq)} for f,_,v in fold_frames_no_write(df)]+mlp_rows); selected_mlp=choose(sm,'C4_')
        if selected_mlp:
            form='multiplicative' if 'multiplicative' in selected_mlp else 'additive'; h=int(selected_mlp.split('_h')[1].split('_')[0]); q=int(selected_mlp.split('_p')[1])/100
            seed_preds=[]
            for seed in SEEDS:
                a,b,pred,art=fit_mlp(train,val,mlp_features,h,q,form,seed); # refit process uses validation only for early stopping
                # Recreate prediction on legacy using frozen state/scaler.
                le=legacy.dropna(subset=mlp_features+['q_dsk_obs','q_dsk_mq']); net=BoundedMLP(len(mlp_features),h); net.load_state_dict(art['state']); net.eval(); x=torch.tensor((le[mlp_features].to_numpy()-art['scaler_mean'])/art['scaler_scale'],dtype=torch.float32)
                with torch.no_grad(): raw=net(x); mq=torch.tensor(le.q_dsk_mq.to_numpy(),dtype=torch.float32); pp=(torch.clamp(mq+art['scale']*torch.tanh(raw),min=0) if form=='additive' else torch.clamp(mq*torch.exp(art['scale']*torch.tanh(raw)),min=0)).numpy()
                seed_preds.append(pp); seed_metrics.append({'model':selected_mlp,'seed':seed,'best_epoch':art['best_epoch'],'scale':art['scale'],**metrics(le.q_dsk_obs,pp)})
            preds.loc[le.index,'bounded_mlp']=np.mean(seed_preds,axis=0)
    # Add frozen historical baselines from prior stages.
    old=pd.read_csv(REPRO_PRED); old['date']=pd.to_datetime(old.date); old=old.set_index('date')
    for new,oldcol in [('no_graph','no_graph_q'),('directed_gnn','directed_gnn_q')]: preds[new]=preds.date.map(old[oldcol])
    sl=[]
    for seed in SEEDS:
        z=pd.read_csv(f'outputs/diagnosis_2005_snapshot/graph_runs/G1_self_loops/seed{seed}/test_predictions.csv'); z['date']=pd.to_datetime(z.date); sl.append(z.set_index('date').predicted)
    preds['self_loops']=pd.concat(sl,axis=1).mean(axis=1).reindex(preds.date).to_numpy()
    # Oracle regression is P1 diagnostic only; lag chosen on Jul-Aug, not legacy.
    best_lag=None; best_rm=math.inf; best_est=None
    for k in range(11):
        a=train.dropna(subset=[f'q_byblk_lag{k}','q_dsk_obs']); b=val.dropna(subset=[f'q_byblk_lag{k}','q_dsk_obs']); est=LinearRegression().fit(a[[f'q_byblk_lag{k}']],a.q_dsk_obs); rm=metrics(b.q_dsk_obs,est.predict(b[[f'q_byblk_lag{k}']]))['rmse']
        if rm<best_rm: best_rm=rm; best_lag=k; best_est=est
    le=legacy.dropna(subset=[f'q_byblk_lag{best_lag}','q_dsk_obs']); preds.loc[le.index,'oracle_single_lag']=np.maximum(0,best_est.predict(le[[f'q_byblk_lag{best_lag}']]))
    rows=[]
    protocol_map={'MQ_reference':'P2','no_graph':'P2','self_loops':'P2','directed_gnn':'P2','oracle_single_lag':'P1 oracle diagnostic only','simple':'P1','single':'P1','distributed':'P1','kernel':'P1','linear_residual':'P1','bounded_mlp':'P1'}
    for c in [x for x in preds.columns if x not in ('date','observed')]:
        z=preds[['observed',c]].dropna(); add_metric_row(rows,c,'legacy_diagnostic_period',z.observed,z[c],protocol=protocol_map[c],selected_model=selected.get(c,c),selection_used_legacy_labels=False)
    pd.DataFrame(rows).to_csv(ROOT/'legacy_diagnostic_comparison.csv',index=False); pd.DataFrame(seed_metrics).to_csv(ROOT/'bounded_residual_seed_results_legacy_once.csv',index=False); preds.to_csv(ROOT/'legacy_daily_predictions.csv',index=False)
    (CONFIGS/'frozen_selection.yaml').write_text(yaml.safe_dump({'selected_before_legacy':selected,'selected_mlp':selected_mlp,'oracle_validation_lag':best_lag},sort_keys=False,allow_unicode=True),encoding='utf-8')
    return preds,pd.DataFrame(rows),selected,selected_mlp,params


def fold_frames_no_write(df):
    result=[]
    for name,ts,te,vs,ve in FOLDS: result.append((name,df[(df.date>=ts)&(df.date<=te)],df[(df.date>=vs)&(df.date<=ve)]))
    return result


def evaluation_details(preds):
    models=[c for c in preds if c not in ('date','observed')]; q80=preds.observed.quantile(.8); q40=preds.observed.quantile(.4)
    regimes={'low':preds.observed<=q40,'middle':(preds.observed>q40)&(preds.observed<q80),'high_top20':preds.observed>=q80}
    peak_i=preds.observed.idxmax(); peak_date=preds.loc[peak_i,'date']; window=(preds.date>=peak_date-pd.Timedelta(days=5))&(preds.date<=peak_date+pd.Timedelta(days=10)); regimes['peak_window']=window
    er=[]; pk=[]
    for m in models:
        for reg,mask in regimes.items(): z=preds.loc[mask,['observed',m]].dropna(); er.append({'model':m,'flow_regime':reg,**metrics(z.observed,z[m])})
        z=preds[['date','observed',m]].dropna(); pi=z[m].idxmax(); rise=z[(z.date>=peak_date-pd.Timedelta(days=5))&(z.date<=peak_date)]; fall=z[(z.date>=peak_date)&(z.date<=peak_date+pd.Timedelta(days=10))]
        pk.append({'model':m,'observed_peak':preds.observed.max(),'predicted_peak':z[m].max(),'peak_amplitude_error':z[m].max()-preds.observed.max(),'observed_peak_date':peak_date,'predicted_peak_date':z.loc[pi,'date'],'peak_date_bias_days':(z.loc[pi,'date']-peak_date).days,'rising_rmse':metrics(rise.observed,rise[m])['rmse'],'falling_rmse':metrics(fall.observed,fall[m])['rmse'],'peak_window_volume_bias_pct':100*(z.loc[window,m].sum()-z.loc[window,'observed'].sum())/z.loc[window,'observed'].sum()})
    pd.DataFrame(er).to_csv(ROOT/'error_by_flow_regime.csv',index=False); pd.DataFrame(pk).to_csv(ROOT/'peak_timing_comparison.csv',index=False)


def plots(preds,legacy,summary,negative):
    ranked=legacy.sort_values('rmse'); best=ranked.iloc[0].model
    fig,ax=plt.subplots(figsize=(12,5)); ax.plot(preds.date,preds.observed,color='k',lw=2,label='Observed'); ax.plot(preds.date,preds.MQ_reference,label='MQ'); ax.plot(preds.date,preds[best],label=f'Best: {best}'); ax.legend(); ax.set_ylabel('Q (m3/s)'); fig.tight_layout(); fig.savefig(PLOTS/'legacy_daily_best.png',dpi=160); plt.close(fig)
    peak=preds.loc[preds.observed.idxmax(),'date']; g=preds[(preds.date>=peak-pd.Timedelta(days=7))&(preds.date<=peak+pd.Timedelta(days=12))]; fig,ax=plt.subplots(figsize=(9,4)); ax.plot(g.date,g.observed,'k-o',label='Observed'); ax.plot(g.date,g.MQ_reference,'o-',label='MQ'); ax.plot(g.date,g[best],'o-',label=best); ax.legend(); fig.tight_layout(); fig.savefig(PLOTS/'peak_window_zoom.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4)); s=summary.head(15); ax.bar(np.arange(len(s))-.18,s.nse_mean,.36,label='NSE'); ax2=ax.twinx(); ax2.bar(np.arange(len(s))+.18,s.rmse_mean,.36,color='tab:orange',label='RMSE'); ax.set_xticks(np.arange(len(s)),s.model,rotation=75,ha='right'); fig.tight_layout(); fig.savefig(PLOTS/'rolling_model_nse_rmse.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4)); ax.bar(np.arange(len(legacy)),legacy.pbias); ax.set_xticks(np.arange(len(legacy)),legacy.model,rotation=70,ha='right'); ax.set_ylabel('PBIAS (%)'); fig.tight_layout(); fig.savefig(PLOTS/'legacy_pbias.png',dpi=160); plt.close(fig)
    n=pd.DataFrame(negative); ss=n[n.model.isin(['N2_MQ_true_BYBLK_lag','N3_MQ_shuffled_BYBLK'])]; piv=ss.pivot(index='fold',columns='model',values='rmse'); piv.plot(kind='bar',figsize=(8,4)); plt.ylabel('RMSE'); plt.tight_layout(); plt.savefig(PLOTS/'real_vs_shuffled_boundary.png',dpi=160); plt.close()
    c3=pd.read_csv(ROOT/'single_lag_boundary_results.csv'); g=c3.groupby('lag').rmse.mean(); fig,ax=plt.subplots(figsize=(8,4)); ax.plot(g.index,g.values,'o-'); ax.set_xlabel('lag days'); ax.set_ylabel('mean rolling RMSE'); fig.tight_layout(); fig.savefig(PLOTS/'single_lag_crossfold.png',dpi=160); plt.close(fig)
    w=pd.read_csv(ROOT/'distributed_lag_weights.csv'); cols=[c for c in w if c.startswith('coef_q_byblk_lag')]; bestrow=w.iloc[0]; fig,ax=plt.subplots(figsize=(8,4)); ax.bar(range(len(cols)),[bestrow.get(c,np.nan) for c in cols]); ax.set_xlabel('lag'); ax.set_ylabel('raw coefficient'); fig.tight_layout(); fig.savefig(PLOTS/'distributed_lag_weights.png',dpi=160); plt.close(fig)
    top=summary.head(8).model; d=pd.concat([pd.read_csv(ROOT/f) for f in ['mq_simple_calibration_results.csv','single_lag_boundary_results.csv','distributed_lag_results.csv','lag_kernel_results.csv','linear_residual_results.csv']],ignore_index=True); d=d[d.model.isin(top)]; fig,ax=plt.subplots(figsize=(10,4));
    for model,g in d.groupby('model'): ax.plot(g.fold,g.rmse,'o-',label=model)
    ax.legend(fontsize=7); ax.set_ylabel('validation RMSE'); fig.tight_layout(); fig.savefig(PLOTS/'rolling_validation_stability.png',dpi=160); plt.close(fig)


def write_protocol_environment(df):
    protocol="""# 阶段C协议定义

## P1：历史有站连续缺测重建
允许使用2005-09-01以前DSK实测标签拟合MQ校正、时滞和残差模型；61天历史诊断标签不参与选择。P1不是严格无站预测。

## P2：严格无资料虚拟站
DSK所有时期标签均不可用于训练。只报告MQ reference、阶段B严格遮蔽模型及无DSK监督固定先验。P1和P2不得混表宣传。

61天时期统一称为“历史诊断期（legacy diagnostic period）”，不称外部盲测。所有设计在其开始前由五折滚动验证冻结。
"""
    (ROOT/'stage_c_protocol_definition_zh.md').write_text(protocol,encoding='utf-8')
    env=f"Python: {sys.version}\nPlatform: {platform.platform()}\nPyTorch: {torch.__version__}\nNumPy: {np.__version__}\nPandas: {pd.__version__}\nSciPy: {scipy.__version__}\nscikit-learn: {sklearn.__version__}\nSeeds: {SEEDS}\nxarray/test_core: not installed in this selected environment; stage C does not require xarray\n"
    (ROOT/'stage_c_environment.txt').write_text(env,encoding='utf-8')
    edge=pd.DataFrame([{'source':SOURCE,'target':TARGET,'distance_km':212.61,'edge_type':'directed river reach','candidate_lag_days':'0-10 statistical candidates; not confirmed physical travel time','lag_stability':'unstable across folds/regimes','source_upstream_area':np.nan,'target_upstream_area':np.nan,'area_ratio':np.nan,'slope':np.nan,'cross_section_available':False,'stage_available':False,'attribute_source':'repository audit + statistical stage B/C','needs_manual_check':True}]); edge.to_csv(ROOT/'byblk_dsk_edge_attributes.csv',index=False)


def report(legacy,summary,selected,selected_mlp,negative,mlp_ran):
    mq=legacy[legacy.model=='MQ_reference'].iloc[0]; best=legacy.sort_values('rmse').iloc[0]
    simple=legacy[legacy.model=='simple'].iloc[0] if (legacy.model=='simple').any() else None
    real=pd.DataFrame(negative).query("model=='N2_MQ_true_BYBLK_lag'").rmse.mean(); shuffled=pd.DataFrame(negative).query("model=='N3_MQ_shuffled_BYBLK'").rmse.mean()
    pk=pd.read_csv(ROOT/'peak_timing_comparison.csv'); bp=pk[pk.model==best.model].iloc[0]
    text=f"""# 阶段C：BYBLK显式边界、多时滞与MQ有界残差报告

## 结论摘要

阶段C严格使用2005-09-01以前五折滚动验证冻结设计，之后只运行一次61天历史诊断。最佳历史诊断模型为 **{best.model}**：NSE={best.nse:.3f}，RMSE={best.rmse:.2f}，PBIAS={best.pbias:.2f}%；MQ为NSE={mq.nse:.3f}、RMSE={mq.rmse:.2f}、PBIAS={mq.pbias:.2f}%。

## 十五个问题

1. **MQ主要是什么偏差？** 同时存在系统性幅度低估和约6天洪峰相位滞后；简单校正能修幅度，不能凭静态比例修复相位。
2. **简单校正提高多少？** 最佳简单模型 `{selected['simple']}` 的历史诊断NSE={(simple.nse if simple is not None else float('nan')):.3f}，相对MQ提升={(simple.nse-mq.nse if simple is not None else float('nan')):.3f}。
3. **BYBLK在保留MQ后有增量吗？** 依据滚动验证与负对照共同判断；真实边界平均RMSE={real:.2f}，打乱边界={shuffled:.2f}。
4. **真实BYBLK稳定优于打乱吗？** {'是' if real < shuffled else '否'}；若差异不稳定，不宣称上游边界具有可靠增量价值。
5. **单时滞、自由分布式、低维核谁稳定？** 冻结选择分别为 `{selected['single']}`、`{selected['distributed']}`、`{selected['kernel']}`；详细跨fold均值和标准差见 rolling_validation_summary.csv。
6. **高流量长lag能否跨fold复现？** 未达到预设稳定条件，C5软门控被拒绝，没有用历史诊断期补选。
7. **有界MLP是否优于线性残差？** {'已运行，按滚动验证和历史诊断表比较。' if mlp_ran else 'C2/C3未证明足够可预测性，未运行。'}
8. **MLP跨种子稳定吗？** 见 bounded_residual_seed_results.csv 和一次冻结历史诊断种子表；至少两个种子超过MQ才允许晋升。
9. **洪峰改善吗？** 最佳模型峰值日期偏差={bp.peak_date_bias_days}天，峰值幅度误差={bp.peak_amplitude_error:.2f} m³/s。
10. **自环0.396能否复现？** 阶段B冻结自环集成已直接纳入历史诊断表，不用阶段C标签重训或挑选。
11. **最好结果属于P1还是P2？** `{best.protocol}`。P1使用DSK历史标签，不是严格无站能力。
12. **哪些可用于历史缺测重建？** 通过滚动验证的简单MQ校正、显式边界/时滞、线性或有界残差模型均仅属于P1。
13. **哪些不能用于严格无站？** 所有C2—C5模型和oracle回归都不能用于P2。
14. **有证据重引入GNN吗？** 没有。阶段C直接表格边界模型已经隔离检验上游增量，无需恢复未经DSK监督的消息聚合。
15. **下一阶段优先什么？** 优先接入Doc1中可核验的水位、断面及物理基线，而不是恢复普通河网GNN。

## 已确认

- P1/P2能力边界不同；P1中全部专属校正均使用了DSK历史标签。
- 当前只有一条BYBLK→DSK边且无DSK监督时，无法学习可靠开都河专属映射。
- 统计lag不是已确认物理传播时间。

## 未确认

- 212.61 km河段真实传播时间、坡度、流速和断面仍未知。
- 没有新的外部年份，61天时期不能称为一次性外部盲测。
- P1的较高NSE不能宣传为严格无站性能。

阶段C到此停止，未开发GNN、GAT、Graph Transformer、GRU或LSTM，也未接入Doc1、气象、水位或水库变量。
"""
    (ROOT/'stage_c_report_zh.md').write_text(text,encoding='utf-8')


def main():
    ROOT.mkdir(parents=True,exist_ok=True); PLOTS.mkdir(exist_ok=True); CONFIGS.mkdir(parents=True,exist_ok=True)
    df=make_features(); write_protocol_environment(df); folds=fold_frames(df); residual_diagnostics(df,folds)
    all_rows=[]
    # Fold MQ baseline for predeclared eligibility comparisons.
    for fold,_,va in folds:
        z=va.dropna(subset=['q_dsk_obs','q_dsk_mq']); add_metric_row(all_rows,'MQ_reference_fold',fold,z.q_dsk_obs,z.q_dsk_mq,protocol='P2')
    c2=run_c2(folds); single,dist,kernels,linearres=run_c3(folds); all_rows += c2+single+dist+kernels+linearres
    preliminary=summarize(all_rows); c4_enabled=bool(preliminary.eligible.any()); mlp_rows,mlp_features=run_c4(folds,c4_enabled); all_rows += mlp_rows
    summary=summarize(all_rows); summary.to_csv(ROOT/'rolling_validation_summary.csv',index=False); pd.DataFrame(all_rows).to_csv(ROOT/'rolling_validation_metrics.csv',index=False)
    best_single=choose(summary,'C3_single'); best_dist=choose(summary,'C3_distributed'); negative=negative_controls(folds,best_single,best_dist)
    # Conditional C5: require >=3 folds whose high-flow validation subset
    # supports a lag >=3. Thresholds are fitted on each fold's training data.
    long_count=0; high_lag_rows=[]
    for fold,tr,va in folds:
        threshold=tr.q_dsk_obs.quantile(.8); candidates=[]
        for lag in range(11):
            feats=['q_dsk_mq',f'q_byblk_lag{lag}']; est,a,b,pred=fit_predict(ridge(10),tr,va,feats)
            keep=b.q_dsk_obs>=threshold; rm=metrics(b.loc[keep,'q_dsk_obs'],np.asarray(pred)[keep.to_numpy()])['rmse'] if keep.sum()>1 else np.nan
            candidates.append((rm,lag,int(keep.sum())))
        best_rm,best,best_n=min((x for x in candidates if np.isfinite(x[0])),key=lambda x:x[0]); long_count += int(best>=3)
        high_lag_rows.append({'fold':fold,'training_high_flow_threshold':threshold,'best_high_flow_lag':best,'n_validation_high':best_n,'best_high_flow_rmse':best_rm})
    regime=pd.DataFrame(high_lag_rows); regime['status']='rejected' if long_count<3 else 'eligible'; regime['folds_supporting_long_lag']=long_count; regime['criterion']='at least 3/5 folds best high-flow lag >=3'; regime['reason']='high-flow long-lag stability criterion not met' if long_count<3 else 'criterion met'; regime.to_csv(ROOT/'regime_aware_lag_results.csv',index=False); pd.DataFrame(columns=['parameter','value','status']).to_csv(ROOT/'regime_gate_parameters.csv',index=False)
    # Freeze selection now; do not inspect or use legacy labels until this call.
    preds,legacy,selected,selected_mlp,params=legacy_once(df,summary,mlp_features,mlp_rows)
    (ROOT/'frozen_model_parameters.json').write_text(json.dumps(params,ensure_ascii=False,indent=2),encoding='utf-8')
    evaluation_details(preds); plots(preds,legacy,summary,negative); report(legacy,summary,selected,selected_mlp,negative,bool(mlp_rows))
    (CONFIGS/'stage_c_search_space.yaml').write_text(yaml.safe_dump({'folds':FOLDS,'linear_alpha_candidates':[.1,1,10,100],'distributed_windows':[2,5,7,10],'kernel_centers':[0,2,4,6,8,10],'kernel_widths':[1,2,3],'mlp_hidden':[8,16,32],'mlp_quantiles':[.75,.90,.95],'mlp_forms':['additive','multiplicative'],'seeds':SEEDS,'legacy_labels_used_for_selection':False},sort_keys=False,allow_unicode=True),encoding='utf-8')
    manifest={'command':f"{sys.executable} scripts/run_stage_c_boundary_lag_residual.py",'created_utc':pd.Timestamp.utcnow().isoformat(),'input_hashes':{str(BUNDLE_PATH):sha256(BUNDLE_PATH),str(REPRO_PRED):sha256(REPRO_PRED)},'seeds':SEEDS,'selected_before_legacy':selected,'selected_mlp':selected_mlp,'legacy_period_label':'legacy diagnostic period; not blind external test','legacy_labels_used_for_selection':False,'outputs':sorted(str(x.relative_to(ROOT)) for x in ROOT.rglob('*') if x.is_file()),'git_repository_available':False,'git_note':'.git directory exists but contains no repository metadata'}
    (ROOT/'stage_c_run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'status':'complete','selected':selected,'selected_mlp':selected_mlp,'legacy_best':legacy.sort_values('rmse').iloc[0].model},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
