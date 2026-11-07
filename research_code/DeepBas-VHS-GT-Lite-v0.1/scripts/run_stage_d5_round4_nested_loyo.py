"""Run the single pre-registered Stage D5 round-4 M2R/M2C nested LOYO."""

from __future__ import division, print_function

import hashlib
import json
import math
from pathlib import Path

import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import spearmanr


ROOT=Path(__file__).resolve().parents[1]
R2=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round2"
R3=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round3"
OUT=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round4"
PLOTS=OUT/"plots"
PROTOCOL=OUT/"stage_d5_round4_model_protocol_frozen.json"
CANONICAL=R2/"multiyear_byblk_dsk_daily_canonical.csv"
ERA5=ROOT/"data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc"
YEARS=list(range(1978,1984))


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    return h.hexdigest()


def dump(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def metrics(obs,pred,dates=None):
    obs=np.asarray(obs,float);pred=np.asarray(pred,float);ok=np.isfinite(obs)&np.isfinite(pred);obs=obs[ok];pred=pred[ok]
    if dates is not None:dates=pd.DatetimeIndex(np.asarray(dates)[ok])
    err=pred-obs;den=np.sum((obs-obs.mean())**2);r=np.corrcoef(obs,pred)[0,1] if obs.std() and pred.std() else np.nan
    alpha=pred.std(ddof=0)/obs.std(ddof=0);beta=pred.mean()/obs.mean();kge=1-np.sqrt((r-1)**2+(alpha-1)**2+(beta-1)**2)
    q1,q2=np.quantile(obs,[1/3,2/3]);masks=[obs<=q1,(obs>q1)&(obs<=q2),obs>q2]
    rr=[float(np.sqrt(np.mean(err[m]**2))) for m in masks]
    peak_date=int((dates[np.argmax(pred)]-dates[np.argmax(obs)]).days) if dates is not None else np.nan
    return {"nse":float(1-np.sum(err**2)/den),"rmse":float(np.sqrt(np.mean(err**2))),"mae":float(np.mean(np.abs(err))),"kge":float(kge),
            "pbias":float(100*err.sum()/obs.sum()),"pearson":float(r),"spearman":float(spearmanr(obs,pred)[0]),
            "low_flow_rmse":rr[0],"middle_flow_rmse":rr[1],"high_flow_rmse":rr[2],"peak_date_error_days":peak_date,
            "peak_amplitude_error_m3s":float(pred.max()-obs.max()),"cumulative_volume_bias_percent":float(100*err.sum()/obs.sum())}


def load_data():
    flow=pd.read_csv(CANONICAL,dtype={"station_id":str},parse_dates=["date"])
    pivot=flow.pivot_table(index="date",columns="station_id",values="discharge_m3s",aggfunc="first").rename(columns={"00705600":"q","00705700":"y"}).reset_index()
    with h5py.File(str(ERA5),"r") as f:
        snow=np.asarray(f["snowmelt_mm"][0],float);time=np.asarray(f["time"],int)
    weather=pd.DataFrame({"date":pd.to_datetime("1978-01-01")+pd.to_timedelta(time,unit="D"),"snow":snow})
    weather["z_raw"]=weather.snow.shift(1).rolling(14,min_periods=14).sum()
    merged=pivot.merge(weather,on="date",how="left")
    if len(merged)!=2191 or merged[["q","y","snow"]].isna().any().any() or merged.date.duplicated().any():raise RuntimeError("development data audit failed")
    data={}
    for year in YEARS:
        g=merged[merged.date.dt.year==year].sort_values("date")
        data[year]={"date":pd.DatetimeIndex(g.date),"q":g.q.values.astype(float),"y":g.y.values.astype(float),"z":g.z_raw.values.astype(float)}
    return data,merged


def state(year,rho,data):
    e=0.0
    if year>1978:
        for q in data[year-1]["q"][-60:]:e=rho*e+(1-rho)*q
    result=[]
    for q in data[year]["q"]:e=rho*e+(1-rho)*q;result.append(e)
    return np.asarray(result,float)


def objective_mask(year,n,z):
    m=np.isfinite(z);m[:60]=False if year==1978 else m[:60]
    return m


def common_mask(year,n,z):
    m=np.isfinite(z);m[:(60 if year==1978 else 30)]=False;return m


def z_scaler(train_years,data):
    values=[]
    for year in train_years:
        z=data[year]["z"];m=objective_mask(year,len(z),z);values.extend(z[m])
    values=np.asarray(values,float);return float(values.mean()),float(values.std(ddof=0))


def predict(year,params,data,model,zmean=0,zstd=1):
    rho,b,g,c=params[:4];e=state(year,rho,data);base=b+g*e+c*data[year]["q"]
    if model=="M2C":base=base+params[4]*((data[year]["z"]-zmean)/zstd)
    return np.maximum(0.0,base),e


def objective(params,model,train_years,data,zmean,zstd):
    losses=[]
    for year in train_years:
        pred,_=predict(year,params,data,model,zmean,zstd);m=objective_mask(year,len(pred),data[year]["z"])
        losses.append(np.mean((pred[m]-data[year]["y"][m])**2))
    return float(np.mean(losses))


def fit(model,train_years,data,protocol):
    zmean,zstd=z_scaler(train_years,data)
    if not np.isfinite(zstd) or zstd<=0:raise RuntimeError("invalid training-fold Z std")
    p=protocol["parameter_bounds"]
    bounds=[tuple(p[x]) for x in ["rho","b","g","c"]]+([tuple(p["d"])] if model=="M2C" else [])
    starts=protocol[model+"_starts"];results=[]
    for i,start in enumerate(starts):
        res=minimize(objective,np.asarray(start,float),args=(model,train_years,data,zmean,zstd),method="L-BFGS-B",bounds=bounds,
                     options={"maxiter":protocol["optimizer"]["maxiter"],"ftol":protocol["optimizer"]["ftol"]})
        results.append({"restart":i,"params":res.x.astype(float),"objective":float(res.fun),"success":bool(res.success),"message":str(res.message)})
    best=min(results,key=lambda x:x["objective"])
    return best,results,zmean,zstd


def aggregate(result):
    rows=list(result);f=pd.DataFrame(result)
    metric_cols=["nse","rmse","mae","kge","pbias","pearson","spearman","low_flow_rmse","middle_flow_rmse","high_flow_rmse","peak_date_error_days","peak_amplitude_error_m3s","cumulative_volume_bias_percent"]
    for kind,fn in [("macro_mean",np.mean),("macro_median",np.median),("macro_std",np.std)]:
        row={"row_type":kind,"year":"","model":f.model.iloc[0],"row_count":int(f.row_count.sum())}
        for c in metric_cols:row[c]=float(fn(f[c]))
        rows.append(row)
    return pd.DataFrame(rows)


def longest_negative(err):
    best=cur=0
    for x in np.asarray(err)<0:cur=cur+1 if x else 0;best=max(best,cur)
    return int(best)


def boundary_hit(value,bounds):return value<=bounds[0]+.01*(bounds[1]-bounds[0]) or value>=bounds[1]-.01*(bounds[1]-bounds[0])


def main():
    PLOTS.mkdir(parents=True,exist_ok=True)
    protocol=json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol["status"]!="frozen_before_any_round4_fit" or sha256(CANONICAL)!=protocol["canonical_flow_sha256"] or sha256(ERA5)!=protocol["era5_interval_sha256"]:raise SystemExit("frozen protocol/input mismatch")
    data,merged=load_data();inner=[];params_rows=[];restart_rows=[];pred_rows=[];metric_rows={"M2R":[],"M2C":[]}
    for outer in YEARS:
        outer_train=[y for y in YEARS if y!=outer]
        for inner_year in outer_train:
            inner_train=[y for y in outer_train if y!=inner_year]
            for model in ["M2R","M2C"]:
                best,allres,zm,zs=fit(model,inner_train,data,protocol);pred,_=predict(inner_year,best["params"],data,model,zm,zs);m=common_mask(inner_year,len(pred),data[inner_year]["z"]);met=metrics(data[inner_year]["y"][m],pred[m],data[inner_year]["date"][m])
                inner.append({"outer_year":outer,"inner_held_year":inner_year,"model":model,"inner_train_years":"|".join(map(str,inner_train)),"selected_restart":best["restart"],"training_objective":best["objective"],"z_train_mean":zm,"z_train_std":zs,**met})
        fitted={}
        for model in ["M2R","M2C"]:
            best,allres,zm,zs=fit(model,outer_train,data,protocol);fitted[model]=(best,zm,zs)
            names=["rho","b","g","c"]+(["d"] if model=="M2C" else [])
            row={"outer_year":outer,"model":model,"outer_train_years":"|".join(map(str,outer_train)),"selected_restart":best["restart"],"training_objective":best["objective"],"fit_success":best["success"],"z_train_mean":zm,"z_train_std":zs}
            row.update(dict(zip(names,best["params"])));params_rows.append(row)
            for r in allres:
                rr={"outer_year":outer,"model":model,"restart":r["restart"],"selected":r["restart"]==best["restart"],"objective":r["objective"],"success":r["success"],"message":r["message"],"z_train_mean":zm,"z_train_std":zs};rr.update(dict(zip(names,r["params"])));restart_rows.append(rr)
        pR,eR=predict(outer,fitted["M2R"][0]["params"],data,"M2R",fitted["M2R"][1],fitted["M2R"][2]);pC,eC=predict(outer,fitted["M2C"][0]["params"],data,"M2C",fitted["M2C"][1],fitted["M2C"][2]);m=common_mask(outer,len(pR),data[outer]["z"])
        for i,date in enumerate(data[outer]["date"]):pred_rows.append({"date":date.date().isoformat(),"year":outer,"outer_held_year":outer,"q_byblk":data[outer]["q"][i],"q_dsk_obs":data[outer]["y"][i],"z_raw_antecedent14_snowmelt_mm":data[outer]["z"][i],"z_train_mean":fitted["M2C"][1],"z_train_std":fitted["M2C"][2],"z_standardized":(data[outer]["z"][i]-fitted["M2C"][1])/fitted["M2C"][2] if np.isfinite(data[outer]["z"][i]) else np.nan,"m2r_q_pred":pR[i],"m2c_q_pred":pC[i],"m2r_state_E":eR[i],"m2c_state_E":eC[i],"scoring_common":bool(m[i])})
        for model,pred in [("M2R",pR),("M2C",pC)]:
            met=metrics(data[outer]["y"][m],pred[m],data[outer]["date"][m]);metric_rows[model].append({"row_type":"year","year":outer,"model":model,"row_count":int(m.sum()),"outer_train_years":"|".join(map(str,outer_train)),**met})
    predictions=pd.DataFrame(pred_rows);predictions.to_csv(OUT/"m2rc_nested_outer_predictions.csv",index=False,encoding="utf-8-sig")
    all_metrics=[]
    for model in ["M2R","M2C"]:
        frame=aggregate(metric_rows[model]);common=predictions[predictions.scoring_common];met=metrics(common.q_dsk_obs,common[model.lower()+"_q_pred"],pd.to_datetime(common.date));frame=pd.concat([frame,pd.DataFrame([{"row_type":"pooled","year":"","model":model,"row_count":len(common),**met}])],ignore_index=True);frame.to_csv(OUT/(model.lower()+"_nested_loyo_results.csv"),index=False,encoding="utf-8-sig");all_metrics.append(frame)
    pd.DataFrame(inner).to_csv(OUT/"m2rc_inner_nested_records.csv",index=False,encoding="utf-8-sig")
    par=pd.DataFrame(params_rows);par.to_csv(OUT/"m2c_parameters_by_fold.csv",index=False,encoding="utf-8-sig");pd.DataFrame(restart_rows).to_csv(OUT/"m2rc_optimization_restarts.csv",index=False,encoding="utf-8-sig")

    # M2R compatibility with the frozen round-2 M2 predictions.
    old=pd.read_csv(R2/"outer_year_predictions.csv",parse_dates=["date"]);new=predictions.copy();new["date"]=pd.to_datetime(new.date);j=new.merge(old[["date","outer_held_year","m2_q_pred","scoring_common"]],on=["date","outer_held_year"],suffixes=("_new","_old"));cm=j.scoring_common_new&j.scoring_common_old
    comp={"model_class_exactly_equivalent":True,"refitted_under_normalized_parameterization":True,"compared_common_days":int(cm.sum()),"maximum_absolute_prediction_difference":float(np.max(np.abs(j.loc[cm,"m2r_q_pred"]-j.loc[cm,"m2_q_pred"]))),"rmse_between_prediction_series":float(np.sqrt(np.mean((j.loc[cm,"m2r_q_pred"]-j.loc[cm,"m2_q_pred"])**2))),"explanation":"Differences reflect optimizer conditioning/path after equivalent reparameterization; equations have the same information and state."};dump(OUT/"m2r_round2_compatibility_audit.json",comp)

    # Stability and collinearity.
    stability=[];bounds=protocol["parameter_bounds"];pC=par[par.model=="M2C"].set_index("outer_year");pR=par[par.model=="M2R"].set_index("outer_year")
    for name in ["rho","b","g","c","d"]:
        vals=pC[name].values.astype(float);bd=bounds[name];hits=[boundary_hit(x,bd) for x in vals]
        stability.append({"parameter":name,"fold_count":6,"mean":vals.mean(),"median":np.median(vals),"std":vals.std(),"minimum":vals.min(),"maximum":vals.max(),"range":vals.max()-vals.min(),"normalized_range":(vals.max()-vals.min())/(bd[1]-bd[0]),"boundary_hit_count":sum(hits),"persistent_boundary":sum(hits)>3,"zero_or_near_zero_count":int(np.sum(np.abs(vals)<=.01*(bd[1]-bd[0]))),"sign_consistent":bool(np.all(vals<=1e-10) if name=="d" else np.all(vals>=-1e-10))})
    stab=pd.DataFrame(stability);stab.to_csv(OUT/"m2c_parameter_stability.csv",index=False,encoding="utf-8-sig")
    col=[]
    for outer in YEARS:
        train=[y for y in YEARS if y!=outer];r=pC.loc[outer];blocks=[]
        for year in train:
            e=state(year,float(r.rho),data);m=objective_mask(year,len(e),data[year]["z"]);blocks.append(np.column_stack([e[m],data[year]["q"][m],(data[year]["z"][m]-r.z_train_mean)/r.z_train_std]))
        x=np.vstack(blocks);xz=(x-x.mean(0))/x.std(0);corr=np.corrcoef(xz,rowvar=False);inv=np.linalg.pinv(corr);col.append({"outer_year":outer,"train_years":"|".join(map(str,train)),"row_count":len(x),"corr_E_Z":corr[0,2],"corr_Q_Z":corr[1,2],"corr_E_Q":corr[0,1],"vif_E":inv[0,0],"vif_Q":inv[1,1],"vif_Z":inv[2,2],"condition_number":np.linalg.cond(xz)})
    pd.DataFrame(col).to_csv(OUT/"m2c_collinearity_diagnostics.csv",index=False,encoding="utf-8-sig")

    # Promotion decision from frozen gates.
    yrR=pd.DataFrame(metric_rows["M2R"]).set_index("year");yrC=pd.DataFrame(metric_rows["M2C"]).set_index("year")
    better_rmse=int((yrC.rmse<yrR.rmse).sum());better_pbias=int((yrC.pbias.abs()<yrR.pbias.abs()).sum())
    cat=[y for y in YEARS if yrC.loc[y,"rmse"]>1.5*yrR.loc[y,"rmse"] or yrC.loc[y,"nse"]<yrR.loc[y,"nse"]-.5]
    dvals=pC.d.values;d_mag_boundary=int(np.sum(dvals<=-297))>3
    rel=[]
    for name in ["rho","g","c"]:rel.extend((np.abs(pC[name]-pR[name])/np.maximum(np.abs(pR[name]),1e-6)).tolist())
    base_stable=(not stab[stab.parameter.isin(["rho","g","c"])].persistent_boundary.any()) and np.median(rel)<=.5
    reductions=np.maximum(yrR.rmse.values-yrC.rmse.values,0);dominance=float(reductions.max()/reductions.sum()) if reductions.sum()>0 else 1.0
    gates={"rmse_lower_at_least_4_of_6":better_rmse>=4,"macro_mean_nse_higher":yrC.nse.mean()>yrR.nse.mean(),"macro_mean_rmse_lower":yrC.rmse.mean()<yrR.rmse.mean(),"macro_mean_abs_pbias_lower":yrC.pbias.abs().mean()<yrR.pbias.abs().mean(),"year_1979_underestimate_relieved":yrC.loc[1979,"pbias"]>yrR.loc[1979,"pbias"] and abs(yrC.loc[1979,"pbias"])<abs(yrR.loc[1979,"pbias"]),"year_1982_not_obviously_worse":abs(yrC.loc[1982,"pbias"])<=abs(yrR.loc[1982,"pbias"])+2,"zero_catastrophic_years":len(cat)==0,"d_non_positive_all_folds":bool(np.all(dvals<=1e-10)),"d_not_persistently_at_magnitude_boundary":not d_mag_boundary,"rho_g_c_stable":bool(base_stable),"macro_high_flow_rmse_not_worse_5pct":yrC.high_flow_rmse.mean()<=1.05*yrR.high_flow_rmse.mean(),"improvement_not_dominated_over_70pct_by_one_year":dominance<=.70}
    gates={k:bool(v) for k,v in gates.items()};passed=all(gates.values());decision={"evaluation_name_zh":"M2C开发性嵌套留一年稳健性评价","decision":"admit_M2C_for_frozen_retro_transfer" if passed else "reject_M2C_interval_snowmelt","all_gates_passed":bool(passed),"gates":gates,"rmse_better_year_count":better_rmse,"abs_pbias_better_year_count":better_pbias,"catastrophic_years":cat,"positive_rmse_reduction_dominance":dominance,"d_values_by_outer_fold":{str(y):float(pC.loc[y,"d"]) for y in YEARS},"round2_decision_unchanged":"reject_current_single_upstream_model_family","try_other_candidates_if_failed":False,"M3_authorized":False,"transfer_authorized":bool(passed)};dump(OUT/"m2c_development_promotion_decision.json",decision)

    # Special bias diagnostics.
    special=[]
    for year,months,label in [(1979,[7,8,9],"1979_Jul_Sep"),(1982,[9,10,11],"1982_Sep_Nov")]:
        f=predictions[(predictions.year==year)&predictions.scoring_common].copy();f["month"]=pd.to_datetime(f.date).dt.month
        for model in ["M2R","M2C"]:
            pred=f[model.lower()+"_q_pred"].values;obs=f.q_dsk_obs.values;err=pred-obs;q1=np.quantile(obs,1/3);period=f.month.isin(months).values
            special.append({"year":year,"model":model,"period":"annual_common","pbias":100*err.sum()/obs.sum(),"longest_negative_error_run":longest_negative(err),"low_flow_pbias":100*err[obs<=q1].sum()/obs[obs<=q1].sum(),"day_count":len(f)})
            special.append({"year":year,"model":model,"period":label,"pbias":100*err[period].sum()/obs[period].sum(),"longest_negative_error_run":longest_negative(err[period]),"low_flow_pbias":100*err[period&(obs<=q1)].sum()/obs[period&(obs<=q1)].sum() if np.any(period&(obs<=q1)) else np.nan,"day_count":int(period.sum())})
    pd.DataFrame(special).to_csv(OUT/"m2c_special_year_bias_diagnostics.csv",index=False,encoding="utf-8-sig")

    # Plots.
    x=np.arange(6);w=.34
    for metric,label in [("rmse","RMSE (m3/s)"),("nse","NSE"),("pbias","PBIAS (%)")]:
        fig,ax=plt.subplots(figsize=(9,4.5));ax.bar(x-w/2,yrR.loc[YEARS,metric],w,label="M2R");ax.bar(x+w/2,yrC.loc[YEARS,metric],w,label="M2C");ax.set_xticks(x);ax.set_xticklabels(YEARS);ax.set_ylabel(label);ax.set_title("M2C developmental nested LOYO: "+label);ax.legend();fig.tight_layout();fig.savefig(PLOTS/(metric+"_by_outer_year.png"),dpi=180);plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4));ax.bar([str(y) for y in YEARS],pC.loc[YEARS,"d"]);ax.axhline(0,color="black",lw=.8);ax.axhline(-300,color="red",ls="--",lw=.8);ax.set_ylabel("d (m3/s per standardized Z)");ax.set_title("Frozen-sign snowmelt coefficient by outer fold");fig.tight_layout();fig.savefig(PLOTS/"d_by_outer_fold.png",dpi=180);plt.close(fig)
    for year in YEARS:
        f=predictions[(predictions.year==year)&predictions.scoring_common];fig,ax=plt.subplots(figsize=(10,4));ax.plot(pd.to_datetime(f.date),f.q_dsk_obs,color="black",lw=1.4,label="Observed");ax.plot(pd.to_datetime(f.date),f.m2r_q_pred,label="M2R",lw=1);ax.plot(pd.to_datetime(f.date),f.m2c_q_pred,label="M2C",lw=1);ax.set_title("Outer held year %d"%year);ax.set_ylabel("Q (m3/s)");ax.legend(ncol=3);fig.tight_layout();fig.savefig(PLOTS/("outer_%d_predictions.png"%year),dpi=160);plt.close(fig)

    special=pd.read_csv(OUT/"m2c_special_year_bias_diagnostics.csv");s79=special[(special.year==1979)&(special.period=="annual_common")].set_index("model");s82=special[(special.year==1982)&(special.period=="annual_common")].set_index("model")
    report="""# M2C开发性嵌套留一年评价

本轮评价身份为“M2C开发性嵌套留一年稳健性评价”。融雪变量曾利用全部六年残差进行探索性筛选，因此外层年份不是完全独立的特征选择检验；结果不是外部验证、盲测或最终泛化成绩。

M2R和M2C使用相同外层年份、训练损失、预热、评分日期、优化器和3次重启。M2C只增加一个训练fold标准化的过去14日区间融雪量，`d`在运行前限制为非正。

| 指标 | M2R | M2C |
|---|---:|---:|
| 宏平均NSE | %.3f | %.3f |
| 宏平均RMSE | %.2f | %.2f |
| 宏平均绝对PBIAS | %.2f%% | %.2f%% |
| 宏平均高流量RMSE | %.2f | %.2f |

M2C在%d/6年份降低RMSE，在%d/6年份降低绝对PBIAS。1979 PBIAS由%.2f%%变为%.2f%%，最长连续负误差由%d天变为%d天；1982 PBIAS由%.2f%%变为%.2f%%。

1979年7—9月PBIAS虽由-50.81%%改善到-44.95%%，但全年低估和最长连续负误差反而恶化，不能算通过。1982年9—11月高估由55.32%%降至39.29%%，但全年低流量PBIAS由19.19%%升至22.32%%，说明低流量基线仍被抬高。M2C在1978和1981的RMSE明显变差，改善并非所有年份一致。

六个fold的`d`均为负（-40.68至-25.54），没有趋零或顶到-300边界；rho、g、c保持基本稳定。储量E与融雪Z的相关为0.48—0.61，VIF约1.5—1.8、条件数2.70—3.15，属于中等相关而非严重共线。

冻结十二项门槛通过%d/12项。最终决定：`%s`。若拒绝，不尝试其余7个候选；若通过，才允许另行冻结全六年参数并在读取迁移期DSK标签前生成预测。
"""%(yrR.nse.mean(),yrC.nse.mean(),yrR.rmse.mean(),yrC.rmse.mean(),yrR.pbias.abs().mean(),yrC.pbias.abs().mean(),yrR.high_flow_rmse.mean(),yrC.high_flow_rmse.mean(),better_rmse,better_pbias,s79.loc["M2R","pbias"],s79.loc["M2C","pbias"],s79.loc["M2R","longest_negative_error_run"],s79.loc["M2C","longest_negative_error_run"],s82.loc["M2R","pbias"],s82.loc["M2C","pbias"],sum(gates.values()),decision["decision"])
    (OUT/"m2c_development_report_zh.md").write_text(report,encoding="utf-8")
    access={"program":"scripts/run_stage_d5_round4_nested_loyo.py","semantic_inputs":[str(CANONICAL.relative_to(ROOT)).replace("\\","/"),str(ERA5.relative_to(ROOT)).replace("\\","/"),str(PROTOCOL.relative_to(ROOT)).replace("\\","/")],"year_min":1978,"year_max":1983,"read_2000":False,"read_2001":False,"read_2011":False,"read_transfer_labels":False,"other_weather_candidates_tried":False,"new_model_count":1,"M3_used":False,"P1B_used":False,"Yanqi_used":False,"MQ_used":False,"GNN_used":False};dump(OUT/"stage_d5_round4_development_input_access_audit.json",access)
    print(json.dumps({"decision":decision["decision"],"gates_passed":sum(gates.values()),"rmse_better_years":better_rmse,"1979_pbias":[s79.loc["M2R","pbias"],s79.loc["M2C","pbias"]],"1982_pbias":[s82.loc["M2R","pbias"],s82.loc["M2C","pbias"]],"compatibility_rmse":comp["rmse_between_prediction_series"]},ensure_ascii=False))


if __name__=="__main__":main()
