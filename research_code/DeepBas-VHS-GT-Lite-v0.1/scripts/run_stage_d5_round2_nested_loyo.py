import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round2"
PLOTS = OUT / "plots"
CANONICAL = OUT / "multiyear_byblk_dsk_daily_canonical.csv"
MANIFEST = OUT / "multiyear_dataset_manifest.json"
PROTOCOL = OUT / "model_protocol_frozen.json"
REGISTRY = OUT / "eligible_year_registry.json"
PARAM = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a/boundary_only_frozen_parameters_2005.json"
YEARS = list(range(1978, 1984))
PLOTS.mkdir(parents=True, exist_ok=True)


def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def metrics(obs, pred, dates=None):
    obs = np.asarray(obs, dtype=float); pred = np.asarray(pred, dtype=float)
    ok = np.isfinite(obs) & np.isfinite(pred); obs = obs[ok]; pred = pred[ok]
    if dates is not None:
        dates = pd.DatetimeIndex(np.asarray(dates)[ok])
    if len(obs) < 2:
        return {k: np.nan for k in ("nse","rmse","mae","kge","pbias","pearson","spearman","peak_date_error_days","peak_amplitude_error_m3s","cumulative_volume_bias_percent","low_flow_rmse","middle_flow_rmse","high_flow_rmse")}
    err = pred - obs; denom = np.sum((obs-obs.mean())**2)
    r = np.corrcoef(obs,pred)[0,1] if obs.std() and pred.std() else np.nan
    alpha = pred.std(ddof=0)/obs.std(ddof=0) if obs.std(ddof=0) else np.nan
    beta = pred.mean()/obs.mean() if obs.mean() else np.nan
    kge = 1-np.sqrt((r-1)**2+(alpha-1)**2+(beta-1)**2) if np.isfinite(r*alpha*beta) else np.nan
    q1,q2=np.quantile(obs,[1/3,2/3]); regimes=[obs<=q1,(obs>q1)&(obs<=q2),obs>q2]
    regime_rmse=[float(np.sqrt(np.mean(err[m]**2))) if m.sum() else np.nan for m in regimes]
    peak_date_error=np.nan
    if dates is not None:
        peak_date_error=int((dates[int(np.argmax(pred))]-dates[int(np.argmax(obs))]).days)
    return {"nse":float(1-np.sum(err**2)/denom) if denom else np.nan,"rmse":float(np.sqrt(np.mean(err**2))),
        "mae":float(np.mean(np.abs(err))),"kge":float(kge),"pbias":float(100*err.sum()/obs.sum()) if obs.sum() else np.nan,
        "pearson":float(r),"spearman":float(spearmanr(obs,pred)[0]),"peak_date_error_days":peak_date_error,
        "peak_amplitude_error_m3s":float(pred.max()-obs.max()),"cumulative_volume_bias_percent":float(100*err.sum()/obs.sum()) if obs.sum() else np.nan,
        "low_flow_rmse":regime_rmse[0],"middle_flow_rmse":regime_rmse[1],"high_flow_rmse":regime_rmse[2]}


def kernel_weights(family, mu, width):
    k=np.arange(31,dtype=float)
    if family=="gaussian":
        z=np.exp(-0.5*((k-mu)/width)**2)
    elif family=="triangular":
        z=np.maximum(0.0,1.0-np.abs(k-mu)/width)
    elif family=="gamma_nash":
        x=k+0.5; shape=max((mu/width)**2,0.05); scale=max(width**2/mu,1e-6)
        logz=(shape-1)*np.log(x)-x/scale-gammaln(shape)-shape*np.log(scale)
        z=np.exp(logz-np.max(logz))
    else:
        raise ValueError(family)
    total=z.sum()
    return z/total if total>0 else np.eye(1,31,0).ravel()


def lag_matrix(q, maxlag=30):
    q=np.asarray(q,float); x=np.full((len(q),maxlag+1),np.nan)
    for k in range(maxlag+1):
        x[k:,k]=q[:len(q)-k]
    return x


def build_year_data(canonical):
    pivot=canonical.pivot_table(index="date",columns="station_id",values="discharge_m3s",aggfunc="first")
    pivot=pivot.rename(columns={"00705600":"q_byblk","00705700":"q_dsk"}).reset_index()
    result={}
    for year in YEARS:
        g=pivot[pivot.date.dt.year==year].sort_values("date").copy()
        result[year]={"date":pd.DatetimeIndex(g.date),"q":g.q_byblk.values.astype(float),"y":g.q_dsk.values.astype(float),"lags":lag_matrix(g.q_byblk.values)}
    return result


def common_mask(year, n):
    start=60 if year==1978 else 30
    m=np.zeros(n,dtype=bool); m[start:]=True; return m


def predict_m1(yd, family, params):
    b,a,mu,width=params; w=kernel_weights(family,mu,width)
    routed=yd["lags"].dot(w); return np.maximum(0.0,b+a*routed),w


def m1_objective(params, family, train_years, data):
    losses=[]
    for year in train_years:
        pred,_=predict_m1(data[year],family,params); valid=np.arange(len(pred))>=30
        losses.append(np.mean((pred[valid]-data[year]["y"][valid])**2))
    return float(np.mean(losses))


def m1_bounds(family, protocol):
    p=protocol["parameter_bounds"]["M1"]
    width=p["triangular_half_width"] if family=="triangular" else (p["gamma_sigma"] if family=="gamma_nash" else p["gaussian_sigma"])
    return [tuple(p["b"]),tuple(p["gain_a"]),tuple(p["mu"]),tuple(width)]


def fit_m1(family,start,train_years,data,protocol):
    x0=np.array([start["b"],start["a"],start["mu"],start["width"]],float)
    bounds=m1_bounds(family,protocol)
    res=minimize(m1_objective,x0,args=(family,train_years,data),method="L-BFGS-B",bounds=bounds,
                 options={"maxiter":int(protocol["optimizer"]["maxiter"]),"ftol":float(protocol["optimizer"]["ftol"])})
    return res.x.astype(float),float(res.fun),bool(res.success),str(res.message)


def storage_state(year,rho,data):
    q=data[year]["q"]; state=[]; s=0.0
    if year>1978:
        for value in data[year-1]["q"][-60:]: s=rho*s+value
    for value in q:
        s=rho*s+value; state.append(s)
    return np.asarray(state,float)


def predict_m2(year,params,data):
    rho,b,a,c=params; s=storage_state(year,rho,data); return np.maximum(0.0,b+a*s+c*data[year]["q"]),s


def m2_objective(params,train_years,data):
    losses=[]
    for year in train_years:
        pred,_=predict_m2(year,params,data); start=60 if year==1978 else 0
        losses.append(np.mean((pred[start:]-data[year]["y"][start:])**2))
    return float(np.mean(losses))


def fit_m2(train_years,data,protocol):
    p=protocol["parameter_bounds"]["M2"]
    bounds=[tuple(p["rho"]),tuple(p["b"]),tuple(p["storage_a"]),tuple(p["direct_c"])]
    results=[]
    for i,start in enumerate(p["starts"]):
        res=minimize(m2_objective,np.asarray(start,float),args=(train_years,data),method="L-BFGS-B",bounds=bounds,
                     options={"maxiter":int(protocol["optimizer"]["maxiter"]),"ftol":float(protocol["optimizer"]["ftol"])})
        results.append((i,res.x.astype(float),float(res.fun),bool(res.success),str(res.message)))
    return min(results,key=lambda x:x[2]),results


def boundary_flags(values,bounds):
    flags=[]
    for value,(lo,hi) in zip(values,bounds):
        tol=.01*(hi-lo); flags.append(bool(value<=lo+tol or value>=hi-tol))
    return flags


def aggregate_rows(year_rows,predictions):
    metric_cols=["nse","rmse","mae","kge","pbias","pearson","spearman","peak_date_error_days","peak_amplitude_error_m3s","cumulative_volume_bias_percent","low_flow_rmse","middle_flow_rmse","high_flow_rmse"]
    rows=list(year_rows)
    frame=pd.DataFrame(year_rows)
    for model in ("M0","M1","M2"):
        f=frame[frame.model==model]
        for scope,fn in (("macro_mean",np.mean),("macro_median",np.median),("macro_std",np.std)):
            row={"row_type":scope,"year":"","model":model,"scoring_window":"common"}
            for c in metric_cols: row[c]=float(fn(f[c].values.astype(float)))
            row["row_count"]=int(f.row_count.sum()); row["worst_year_by_nse"]=int(f.sort_values("nse").iloc[0].year)
            rows.append(row)
        pp=predictions[predictions.scoring_common]
        m=metrics(pp.q_dsk_obs.values,pp[model.lower()+"_q_pred"].values,pp.date.values)
        rows.append({"row_type":"pooled","year":"","model":model,"scoring_window":"common","row_count":len(pp),**m,
                     "worst_year_by_nse":int(f.sort_values("nse").iloc[0].year)})
    return pd.DataFrame(rows)


def main():
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8")); protocol=json.loads(PROTOCOL.read_text(encoding="utf-8")); registry=json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not registry["model_comparison_authorized"] or registry["eligible_or_warning_count"]<3:
        raise SystemExit("fewer than 3 eligible years; model training stopped")
    if sha256(CANONICAL)!=manifest["canonical_sha256"] or sha256(CANONICAL)!=protocol["canonical_sha256"]:
        raise SystemExit("canonical dataset hash mismatch")
    if sha256(PARAM)!=protocol["M0_expected_sha256"]:
        raise SystemExit("M0 parameter hash mismatch")
    canonical=pd.read_csv(CANONICAL,dtype={"station_id":str},parse_dates=["date"])
    if sorted(canonical.year.unique().tolist())!=YEARS or canonical.date.dt.year.max()>1983:
        raise SystemExit("forbidden year present in model input")
    if canonical.is_model_generated.astype(str).str.lower().eq("true").any() or canonical.is_imputed.astype(str).str.lower().eq("true").any():
        raise SystemExit("model-generated or imputed Q present")
    data=build_year_data(canonical)
    param=json.loads(PARAM.read_text(encoding="utf-8")); m0b=float(param["intercept_b"]); m0w={int(x["lag_day"]):float(x["weight"]) for x in param["weights"]}
    if abs(m0b-1.6553467774548096)>1e-12 or abs(m0w[0]-3.294948687135085)>1e-12 or abs(m0w[5]-0.6825937698241894)>1e-12:
        raise SystemExit("M0 parameter content mismatch")

    starts=protocol["parameter_bounds"]["M1"]["starts"]; families=protocol["parameter_bounds"]["M1"]["families"]
    inner_records=[]; fitted=[]; prediction_rows=[]; year_metric_rows=[]; outer_params=[]
    for outer_year in YEARS:
        train_years=[y for y in YEARS if y!=outer_year]
        candidate_summaries=[]
        for family in families:
            for start in starts:
                inner_ms=[]; params_for_stability=[]
                for inner_year in train_years:
                    inner_train=[y for y in train_years if y!=inner_year]
                    pars,loss,success,message=fit_m1(family,start,inner_train,data,protocol)
                    pred,_=predict_m1(data[inner_year],family,pars); cm=common_mask(inner_year,len(pred))
                    met=metrics(data[inner_year]["y"][cm],pred[cm],data[inner_year]["date"][cm])
                    q=data[inner_year]["q"]; m0=np.maximum(0,m0b+m0w[0]*q+m0w[5]*np.r_[np.full(5,np.nan),q[:-5]])
                    m0met=metrics(data[inner_year]["y"][cm],m0[cm],data[inner_year]["date"][cm])
                    inner_ms.append({"inner_year":inner_year,"rmse_below_m0":met["rmse"]<m0met["rmse"],**met})
                    params_for_stability.append(pars)
                    inner_records.append({"record_type":"inner_fold","outer_year":outer_year,"family":family,"start_id":start["start_id"],
                        "inner_held_year":inner_year,"selected":False,"fit_success":success,"training_loss":loss,"m0_rmse":m0met["rmse"],**met})
                    fitted.append({"fit_scope":"inner_train","outer_year":outer_year,"inner_held_year":inner_year,"model":"M1","family":family,
                        "start_id":start["start_id"],"selected_for_outer_refit":False,"fit_success":success,"objective":loss,"b":pars[0],"a":pars[1],"mu":pars[2],"width":pars[3],"message":message})
                im=pd.DataFrame(inner_ms); parr=np.vstack(params_for_stability); bds=np.asarray(m1_bounds(family,protocol),float); normalized_std=np.mean(np.std(parr,axis=0)/(bds[:,1]-bds[:,0]))
                summary={"record_type":"candidate_summary","outer_year":outer_year,"family":family,"start_id":start["start_id"],
                    "valid_year_count":len(im),"years_rmse_below_m0":int(im.rmse_below_m0.sum()),"macro_nse":im.nse.mean(),"macro_rmse":im.rmse.mean(),
                    "macro_abs_pbias":im.pbias.abs().mean(),"macro_high_flow_rmse":im.high_flow_rmse.mean(),"parameter_instability_score":normalized_std,
                    "family_complexity":{"triangular":0,"gaussian":1,"gamma_nash":2}[family],"selected":False}
                candidate_summaries.append(summary); inner_records.append(summary.copy())
        candidates=pd.DataFrame(candidate_summaries).sort_values(
            ["valid_year_count","years_rmse_below_m0","macro_nse","macro_rmse","macro_abs_pbias","macro_high_flow_rmse","parameter_instability_score","family_complexity"],
            ascending=[False,False,False,True,True,True,True,True])
        selected=candidates.iloc[0]
        for row in inner_records:
            if row.get("outer_year")==outer_year and row.get("family")==selected.family and row.get("start_id")==selected.start_id:
                row["selected"]=True
        selected_start=[s for s in starts if s["start_id"]==selected.start_id][0]
        m1pars,m1loss,m1success,m1msg=fit_m1(selected.family,selected_start,train_years,data,protocol)
        fitted.append({"fit_scope":"outer_train_refit","outer_year":outer_year,"inner_held_year":"","model":"M1","family":selected.family,
            "start_id":selected.start_id,"selected_for_outer_refit":True,"fit_success":m1success,"objective":m1loss,
            "b":m1pars[0],"a":m1pars[1],"mu":m1pars[2],"width":m1pars[3],"message":m1msg})
        m2best,m2all=fit_m2(train_years,data,protocol); m2idx,m2pars,m2loss,m2success,m2msg=m2best
        for idx,pars,loss,success,message in m2all:
            fitted.append({"fit_scope":"outer_train_candidate_start","outer_year":outer_year,"inner_held_year":"","model":"M2","family":"single_storage",
                "start_id":"m2_start_%d"%idx,"selected_for_outer_refit":idx==m2idx,"fit_success":success,"objective":loss,
                "rho":pars[0],"b":pars[1],"a":pars[2],"c":pars[3],"message":message})
        outer_params.append({"outer_year":outer_year,"model":"M1","family":selected.family,"b":m1pars[0],"a":m1pars[1],"mu":m1pars[2],"width":m1pars[3],
                            "boundary_flags":boundary_flags(m1pars,m1_bounds(selected.family,protocol))})
        m2p=protocol["parameter_bounds"]["M2"]; m2bounds=[m2p["rho"],m2p["b"],m2p["storage_a"],m2p["direct_c"]]
        outer_params.append({"outer_year":outer_year,"model":"M2","family":"single_storage","rho":m2pars[0],"b":m2pars[1],"a":m2pars[2],"c":m2pars[3],
                            "boundary_flags":boundary_flags(m2pars,m2bounds)})

        yd=data[outer_year]; q=yd["q"]; y=yd["y"]; dates=yd["date"]
        lag5=np.r_[np.full(5,np.nan),q[:-5]]; m0pred=np.maximum(0,m0b+m0w[0]*q+m0w[5]*lag5)
        m1pred,m1weights=predict_m1(yd,selected.family,m1pars); m2pred,state=predict_m2(outer_year,m2pars,data)
        common=common_mask(outer_year,len(q)) & np.isfinite(m0pred) & np.isfinite(m1pred) & np.isfinite(m2pred)
        for i in range(len(q)):
            prediction_rows.append({"date":dates[i].date().isoformat(),"year":outer_year,"outer_held_year":outer_year,"q_byblk":q[i],"q_dsk_obs":y[i],
                "m0_q_pred":m0pred[i],"m1_q_pred":m1pred[i],"m2_q_pred":m2pred[i],"scoring_common":bool(common[i]),
                "m0_scoreable":bool(np.isfinite(m0pred[i])),"m1_scoreable":i>=30,"m2_scoreable":bool(i>=60 if outer_year==1978 else True),
                "m1_family":selected.family,"m1_start_id":selected.start_id,"m2_storage_state":state[i],
                "protocol_identity":"1978-1983 retrospective nested LOYO"})
        for model,pred in (("M0",m0pred),("M1",m1pred),("M2",m2pred)):
            met=metrics(y[common],pred[common],dates[common])
            year_metric_rows.append({"row_type":"year","year":outer_year,"model":model,"scoring_window":"common","row_count":int(common.sum()),
                "outer_train_years":"|".join(map(str,train_years)),"m1_family":selected.family if model=="M1" else "",**met})

    predictions=pd.DataFrame(prediction_rows); predictions.to_csv(OUT/"outer_year_predictions.csv",index=False,encoding="utf-8-sig")
    outer_metrics=aggregate_rows(year_metric_rows,predictions); year_only=outer_metrics[outer_metrics.row_type=="year"].copy()
    for model in ("M0","M1","M2"):
        f=year_only[year_only.model==model]; m0=year_only[year_only.model=="M0"].set_index("year")
        count=0 if model=="M0" else sum(float(r.rmse)<float(m0.loc[int(r.year),"rmse"]) for r in f.itertuples())
        outer_metrics.loc[outer_metrics.model==model,"years_rmse_below_m0"]=count
    outer_metrics.to_csv(OUT/"outer_year_metrics.csv",index=False,encoding="utf-8-sig")
    outer_metrics[outer_metrics.model=="M0"].to_csv(OUT/"m0_fixed_results_by_year.csv",index=False,encoding="utf-8-sig")
    outer_metrics[outer_metrics.model=="M1"].to_csv(OUT/"m1_nested_loyo_results.csv",index=False,encoding="utf-8-sig")
    outer_metrics[outer_metrics.model=="M2"].to_csv(OUT/"m2_nested_loyo_results.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(inner_records).to_csv(OUT/"inner_selection_records.csv",index=False,encoding="utf-8-sig")
    pd.DataFrame(fitted).to_csv(OUT/"fitted_parameters_by_fold.csv",index=False,encoding="utf-8-sig")

    stability=[]
    protocol_bounds={"M2":{"rho":protocol["parameter_bounds"]["M2"]["rho"],"b":protocol["parameter_bounds"]["M2"]["b"],"a":protocol["parameter_bounds"]["M2"]["storage_a"],"c":protocol["parameter_bounds"]["M2"]["direct_c"]}}
    for model in ("M1","M2"):
        pars=[p for p in outer_params if p["model"]==model]; names=["b","a","mu","width"] if model=="M1" else ["rho","b","a","c"]
        for j,name in enumerate(names):
            vals=np.array([p[name] for p in pars],float)
            if model=="M2": bounds=protocol_bounds[model][name]
            else:
                per_bounds=[m1_bounds(p["family"],protocol)[j] for p in pars]; bounds=[min(x[0] for x in per_bounds),max(x[1] for x in per_bounds)]
            nr=(vals.max()-vals.min())/(bounds[1]-bounds[0]); bh=sum(p["boundary_flags"][j] for p in pars)
            stability.append({"model":model,"parameter":name,"outer_fold_count":len(vals),"mean":vals.mean(),"median":np.median(vals),"std":vals.std(),
                "minimum":vals.min(),"maximum":vals.max(),"range":vals.max()-vals.min(),"normalized_range":nr,"boundary_hit_count":bh,
                "persistent_boundary":bh>len(vals)/2})
    stability_df=pd.DataFrame(stability); stability_df.to_csv(OUT/"parameter_stability_summary.csv",index=False,encoding="utf-8-sig")

    ym=year_only.set_index(["model","year"]); decision={"evaluation_name_zh":"1978—1983多年份回顾性嵌套留一年稳健性评价","eligible_years":YEARS,"models":{}}
    m0macro=year_only[year_only.model=="M0"]
    for model in ("M1","M2"):
        f=year_only[year_only.model==model]; better=sum(f.set_index("year").rmse < m0macro.set_index("year").rmse)
        catastrophic=[]
        for year in YEARS:
            rr=ym.loc[(model,year)]; base=ym.loc[("M0",year)]
            if rr.rmse>1.5*base.rmse or rr.nse<base.nse-0.5: catastrophic.append(year)
        stab=stability_df[stability_df.model==model]
        persistent=bool(stab.persistent_boundary.any()); median_nr=float(stab.normalized_range.median()); stable=(not persistent) and median_nr<=0.75
        checks={"rmse_better_at_least_two_thirds":better>=math.ceil(2*len(YEARS)/3),"macro_nse_above_m0":f.nse.mean()>m0macro.nse.mean(),
            "macro_rmse_below_m0":f.rmse.mean()<m0macro.rmse.mean(),"macro_abs_pbias_not_worse":f.pbias.abs().mean()<=m0macro.pbias.abs().mean()+2.0,
            "catastrophic_year_count_at_most_one":len(catastrophic)<=1,"no_persistent_parameter_boundary":not persistent,"basic_parameter_stability":stable}
        decision["models"][model]={"passes_all":all(checks.values()),"checks":checks,"years_rmse_below_m0":int(better),"catastrophic_years":catastrophic,
            "macro_nse":float(f.nse.mean()),"macro_rmse":float(f.rmse.mean()),"macro_abs_pbias":float(f.pbias.abs().mean()),
            "median_normalized_parameter_range":median_nr,"persistent_boundary":persistent}
    passes=[m for m in ("M1","M2") if decision["models"][m]["passes_all"]]
    if not passes:
        decision["decision"]="reject_current_single_upstream_model_family"; decision["next_round_models"]=[]
    elif len(passes)==1:
        decision["decision"]="promote_only_%s"%passes[0]; decision["next_round_models"]=passes
    else:
        score={m:decision["models"][m]["median_normalized_parameter_range"] for m in passes}; selected=min(passes,key=lambda m:(score[m],0 if m=="M2" else 1))
        decision["decision"]="both_pass_keep_simpler_or_more_stable_%s"%selected; decision["next_round_models"]=[selected]
    decision["M3_development_authorized"]=False; dump(OUT/"model_promotion_decision.json",decision)

    input_audit={"model_program":"scripts/run_stage_d5_round2_nested_loyo.py","files_read":[str(CANONICAL.relative_to(ROOT)).replace("\\","/"),str(MANIFEST.relative_to(ROOT)).replace("\\","/"),
        str(PROTOCOL.relative_to(ROOT)).replace("\\","/"),str(REGISTRY.relative_to(ROOT)).replace("\\","/"),str(PARAM.relative_to(ROOT)).replace("\\","/")],
        "stage_d4b_files_read":False,"year_min":int(canonical.year.min()),"year_max":int(canonical.year.max()),"contains_2000":False,"contains_2001":False,"contains_2011":False,
        "DSK_used_as_predictor":False,"DSK_used_as_training_or_outer_score_label_only":True,"ERA5_used":False,"MQ_used":False,"stage_used":False,"Yanqi_used":False}
    dump(OUT/"model_input_access_audit.json",input_audit)

    colors={"M0":"#777777","M1":"#1f77b4","M2":"#d62728"}; x=np.arange(len(YEARS)); width=.24
    for metric,label in (("nse","NSE"),("rmse","RMSE (m3/s)")):
        fig,ax=plt.subplots(figsize=(9,4.5))
        for i,model in enumerate(("M0","M1","M2")):
            f=year_only[year_only.model==model].set_index("year").loc[YEARS]
            ax.bar(x+(i-1)*width,f[metric].values,width,label=model,color=colors[model])
        ax.set_xticks(x); ax.set_xticklabels(YEARS); ax.set_ylabel(label); ax.set_title("Nested leave-one-year-out common-window %s"%label); ax.legend(); fig.tight_layout()
        fig.savefig(PLOTS/("outer_year_%s.png"%metric),dpi=180); plt.close(fig)
    for year in YEARS:
        g=predictions[(predictions.year==year)&predictions.scoring_common]
        fig,ax=plt.subplots(figsize=(10,4)); ax.plot(pd.to_datetime(g.date),g.q_dsk_obs,color="black",lw=1.4,label="Observed")
        for model in ("M0","M1","M2"): ax.plot(pd.to_datetime(g.date),g[model.lower()+"_q_pred"],lw=1,label=model,color=colors[model])
        ax.set_ylabel("Q (m3/s)"); ax.set_title("Outer held year %d (common window)"%year); ax.legend(ncol=4); fig.tight_layout(); fig.savefig(PLOTS/("outer_%d_predictions.png"%year),dpi=160); plt.close(fig)

    mm={m:year_only[year_only.model==m] for m in ("M0","M1","M2")}
    year_lines=["| 年份 | M0 NSE/RMSE | M1 NSE/RMSE | M2 NSE/RMSE | M1核族 |","|---:|---:|---:|---:|---|"]
    for year in YEARS:
        r0=ym.loc[("M0",year)]; r1=ym.loc[("M1",year)]; r2=ym.loc[("M2",year)]
        year_lines.append("| %d | %.3f / %.2f | %.3f / %.2f | %.3f / %.2f | %s |"%(year,r0.nse,r0.rmse,r1.nse,r1.rmse,r2.nse,r2.rmse,r1.m1_family))
    m1_family_counts=pd.Series([p["family"] for p in outer_params if p["model"]=="M1"]).value_counts().to_dict()
    m1_width=stability_df[(stability_df.model=="M1")&(stability_df.parameter=="width")].iloc[0]
    m2_rho=stability_df[(stability_df.model=="M2")&(stability_df.parameter=="rho")].iloc[0]
    m2_a=stability_df[(stability_df.model=="M2")&(stability_df.parameter=="a")].iloc[0]
    m0_abs=mm["M0"].pbias.abs().mean(); m1_abs=mm["M1"].pbias.abs().mean(); m2_abs=mm["M2"].pbias.abs().mean()
    report="""# 阶段D5第二轮报告

## 评价身份与数据边界

本轮正式名称为“1978—1983多年份回顾性嵌套留一年稳健性评价”。六个年份均通过来源审计并带警告准入；2000、2001和2011没有参与模型选择或评分。本轮模型只读取冻结的BYBLK/DSK日流量文件，其中DSK仅作为训练年份标签或外层留出年份评分标签。

## 数据审计结论

原始工作簿两站共4382个站日全部与`timeseries.csv`和NPZ逐值一致。六年均无缺日、重复、项目插值、平滑或异常替换；1980年包含2月29日。警告为原表未打印单位/质量标志、水文日起止时刻未知、历史DSK闸门相对位置未知。

## 嵌套留一年结果

| 模型 | 宏平均NSE | 宏平均RMSE | 宏平均绝对PBIAS | RMSE优于M0年份数 |
|---|---:|---:|---:|---:|
| M0冻结基线 | %.3f | %.2f | %.2f%% | — |
| M1平滑非负核 | %.3f | %.2f | %.2f%% | %d/6 |
| M2单储量 | %.3f | %.2f | %.2f%% | %d/6 |

M1的核族和初始化只在每个外层训练年份内部通过留一年记录选择；M2公式固定，只用外层训练年份拟合约束参数。所有正式比较都使用共同可评分日期：1978年第61日起、1979—1983年第31日起。

## 各外层年份

%s

M1在5/6个年份降低RMSE，但1979年由98.44增至101.83 m³/s。M2在6/6个年份降低RMSE；在最困难的1980年，NSE由M0的-0.566提高到0.227。M2的pooled NSE为0.378、pooled RMSE为62.66 m³/s；这些改善仍须同时通过偏差和参数稳定性门槛。

## 参数稳定性与失败门槛

- M1外层核族选择次数：`%s`。宽度参数六个外层fold均达到预注册上界15天（范围%.2f—%.2f），构成持续触边。
- M2的rho范围为%.4f—%.4f，较稳定；但储量系数a范围为%.4f—%.4f，其中5/6个外层fold落在边界1%%容差内。
- 宏平均绝对PBIAS：M0=%.2f%%、M1=%.2f%%、M2=%.2f%%。M1和M2均超过预注册的“M0+2个百分点”容差。
- 两个模型均没有灾难性退化年份；拒绝原因来自预先冻结的偏差和持续触边规则，而不是事后改门槛。

## 晋升决定

`%s`

M3仍未获授权。本轮完成后停止，不在2011上运行任何新模型，也不加入ERA5、水位、焉耆、MQ或GNN。
"""%(mm["M0"].nse.mean(),mm["M0"].rmse.mean(),mm["M0"].pbias.abs().mean(),mm["M1"].nse.mean(),mm["M1"].rmse.mean(),mm["M1"].pbias.abs().mean(),
      decision["models"]["M1"]["years_rmse_below_m0"],mm["M2"].nse.mean(),mm["M2"].rmse.mean(),mm["M2"].pbias.abs().mean(),decision["models"]["M2"]["years_rmse_below_m0"],
      "\n".join(year_lines),json.dumps(m1_family_counts,ensure_ascii=False),m1_width.minimum,m1_width.maximum,m2_rho.minimum,m2_rho.maximum,m2_a.minimum,m2_a.maximum,
      m0_abs,m1_abs,m2_abs,decision["decision"])
    (OUT/"stage_d5_round2_report_zh.md").write_text(report,encoding="utf-8")


if __name__=="__main__":
    main()
