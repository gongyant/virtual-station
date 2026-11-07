"""Pre-fit freeze for Stage D5 round 4. Must run before any M2C fitting."""

from __future__ import print_function

import datetime
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


ROOT=Path(__file__).resolve().parents[1]
R2=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round2"
R3=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round3"
OUT=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round4"
ERA5=ROOT/"data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc"
WEIGHTS=ROOT/"data/processed/era5_land/incremental_grid_weights.csv"


def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    manifest_path=R3/"stage_d5_round3_manifest.json"
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    rows=[]
    for item in manifest["files"]:
        path=ROOT/item["file_path"]
        current=sha256(path) if path.exists() else None
        size=path.stat().st_size if path.exists() else None
        rows.append({"file_path":item["file_path"],"expected_sha256":item["sha256"],"current_sha256":current,
                     "expected_size":item["file_size"],"current_size":size,"hash_match":current==item["sha256"],"size_match":size==item["file_size"]})
    immutable={"audit_time":datetime.datetime.now().isoformat(),"manifest_path":str(manifest_path.relative_to(ROOT)).replace("\\","/"),
               "manifest_sha256":sha256(manifest_path),"declared_file_count":manifest["file_count"],"audited_file_count":len(rows),
               "all_hashes_match":all(r["hash_match"] for r in rows),"all_sizes_match":all(r["size_match"] for r in rows),
               "stage_d5_round2_read_only":True,"stage_d5_round3_read_only":True,"files":rows}
    dump(OUT/"round3_immutability_audit.json",immutable)
    if len(rows)!=28 or not immutable["all_hashes_match"] or not immutable["all_sizes_match"]:
        raise SystemExit("round3 immutability audit failed; no model fitting authorized")

    decision=json.loads((R3/"next_branch_decision.json").read_text(encoding="utf-8"))
    frozen=decision["frozen_candidate_variable_group"]
    if decision["selected_branch"]!="M2C_single_storage_plus_interval_weather" or len(frozen)!=1 or frozen[0]["variable"]!="interval_snowmelt_mm_antecedent_14d":
        raise SystemExit("frozen branch or variable mismatch")
    assoc=pd.read_csv(R3/"posthoc_additional_input_associations.csv")
    daily=assoc[assoc.analysis_scope=="daily_m2_outer_residual"].copy()
    passed=daily[daily.cross_year_anomaly_consistent.fillna(False)==True].copy()
    selected=daily[daily.candidate=="interval_snowmelt_mm_antecedent_14d"].iloc[0]
    sign_cols=["month_anomaly_year_%d_pearson"%y for y in range(1978,1984)]
    if not all(float(selected[c])>0 for c in sign_cols):
        raise SystemExit("third-round sign lineage does not support d <= 0")
    lineage=[]
    for r in daily.itertuples(index=False):
        row={"candidate_variable":r.candidate,"candidate_count_total":len(daily),"passed_same_sign_strength_screen":bool(r.cross_year_anomaly_consistent),
             "selected_final":r.candidate=="interval_snowmelt_mm_antecedent_14d","residual_definition":"pred_minus_obs",
             "diagnostic_status":"development_diagnostic_only","multiple_screening_risk":True,"winner_bias_risk":True,
             "month_anomaly_pooled_pearson":r.month_anomaly_pooled_pearson,"same_sign_year_count":r.month_anomaly_same_sign_year_count}
        for y,c in zip(range(1978,1984),sign_cols):
            value=float(getattr(r,c));row["corr_%d"%y]=value;row["sign_%d"%y]="positive" if value>0 else ("negative" if value<0 else "zero")
        lineage.append(row)
    pd.DataFrame(lineage).to_csv(OUT/"candidate_variable_selection_lineage.csv",index=False,encoding="utf-8-sig")
    pass_names=passed.candidate.tolist()
    report="""# 候选变量筛选血缘

第三轮共检查%d个逐日气象候选，其中%d个通过季节去均值后的同号/强度筛选：

%s

最终只保留`interval_snowmelt_mm_antecedent_14d`，原因是它是直接ERA5-Land融雪量、采用过去完整14日、六个年份相关符号均为正，且比“融雪×温度”代理更少一层派生；不继续尝试7/30/60日窗口，也不加入降水、气温或SWE。

第三轮残差定义为`prediction - observation`。六年相关系数依次为：%s。正相关表示融雪较高时原M2更偏高，因此在看第四轮结果前把修正系数`d`冻结为非正。

候选产生和筛选明确属于`development_diagnostic_only`。同一批1978—1983数据同时参与了候选诊断，存在多重筛选与赢家偏差；第四轮外层年份不具备完全独立的特征选择身份，结果不得称为无偏外部评价。
"""%(len(daily),len(pass_names),"\n".join("- `%s`"%x for x in pass_names),"、".join("%d: %.3f"%(y,float(selected[c])) for y,c in zip(range(1978,1984),sign_cols)))
    (OUT/"candidate_selection_report_zh.md").write_text(report,encoding="utf-8")

    with h5py.File(str(ERA5),"r") as f:
        time=np.asarray(f["time"][()]);snow=np.asarray(f["snowmelt_mm"][0],float)
        unit=f["snowmelt_mm"].attrs["units"].decode("utf-8")
        attrs={k:(v.decode("utf-8") if isinstance(v,bytes) else v) for k,v in f.attrs.items() if k!="_NCProperties"}
    weights=pd.read_csv(WEIGHTS,dtype={"station_id":str})
    var_audit={"variable":"interval_snowmelt_mm_antecedent_14d","definition":"sum of interval ERA5-Land snowmelt_mm over t-14 through t-1",
               "construction_order":["read daily snowmelt_mm","shift(1)","rolling(window=14,min_periods=14).sum()"],
               "includes_current_day":False,"includes_future_day":False,"raw_day_count":len(snow),"raw_missing_count":int(np.isnan(snow).sum()),
               "dates_unique":len(np.unique(time))==len(time),"date_start":"1978-01-01","date_end":"1983-12-31","source_unit":unit,
               "model_raw_Z_unit":"mm over prior 14 complete UTC days","standardization":"mean and population std fitted only on current training fold objective rows",
               "interval_basin_definition":attrs.get("basin_definition"),"spatial_aggregation":attrs.get("spatial_aggregation"),
               "daily_boundary":attrs.get("daily_boundary"),"accumulation_convention":attrs.get("accumulation_convention"),
               "weight_sum":float(weights.weight.sum()),"era5_sha256":sha256(ERA5),"weights_sha256":sha256(WEIGHTS),
               "third_round_residual_definition":"pred_minus_obs","six_fold_correlations":[float(selected[c]) for c in sign_cols],
               "frozen_d_sign":"non_positive","d_bounds":[-300.0,0.0],"2011_used_for_selection":False,"audit_passed":True}
    dump(OUT/"frozen_candidate_variable_audit.json",var_audit)

    canonical=R2/"multiyear_byblk_dsk_daily_canonical.csv"
    protocol={
      "schema_version":"1.0","frozen_at":datetime.datetime.now().isoformat(),"status":"frozen_before_any_round4_fit",
      "evaluation_name_zh":"M2C开发性嵌套留一年稳健性评价","identity_limit":"candidate was selected using all six years; outer folds are not independent feature-selection tests",
      "canonical_flow_file":str(canonical.relative_to(ROOT)).replace("\\","/"),"canonical_flow_sha256":sha256(canonical),
      "era5_interval_file":str(ERA5.relative_to(ROOT)).replace("\\","/"),"era5_interval_sha256":sha256(ERA5),
      "round3_manifest_sha256":sha256(manifest_path),"round3_decision_sha256":sha256(R3/"next_branch_decision.json"),
      "eligible_years":list(range(1978,1984)),"outer_validation":"leave one calendar year out","inner_validation":"leave one year out inside each outer-training set; diagnostic only, no hyperparameter selection",
      "models":{
        "M2R":{"state":"E_t=rho*E_(t-1)+(1-rho)*Q_BYBLK(t)","output":"max(0,b+g*E_t+c*Q_BYBLK(t))","parameters":["rho","b","g","c"]},
        "M2C":{"state":"same as M2R","raw_Z":"sum snowmelt_mm over t-14..t-1","standardized_Z":"(raw_Z-training_fold_mean)/training_fold_population_std","output":"max(0,b+g*E_t+c*Q_BYBLK(t)+d*standardized_Z)","parameters":["rho","b","g","c","d"]}},
      "parameter_bounds":{"rho":[0.0,0.995],"b":[-300.0,300.0],"g":[0.0,10.0],"c":[0.0,10.0],"d":[-300.0,0.0]},
      "restart_count_each_model":3,
      "M2R_starts":[[0.2,0.0,0.125,2.0],[0.7,0.0,0.16666666666666669,1.0],[0.95,0.0,0.2,0.5]],
      "M2C_starts":[[0.2,0.0,0.125,2.0,0.0],[0.7,0.0,0.16666666666666669,1.0,-10.0],[0.95,0.0,0.2,0.5,-50.0]],
      "optimizer":{"name":"L-BFGS-B","maxiter":500,"ftol":1e-12},"loss":"macro mean of per-training-year daily MSE; years equally weighted",
      "training_rows":{"1978":"day 61 onward","1979_1983":"all days with valid state and Z"},
      "warmup":{"1978":"E0=0; first 60 days unscored","1979_1983":"previous calendar year final 60 BYBLK days warm E; no DSK used"},
      "common_outer_scoring":{"1978":"day 61 onward","1979_1983":"day 31 onward","models":"identical rows for M2R and M2C"},
      "standardization":"M2C raw Z mean and population std from current training fold objective rows only; never outer-held statistics",
      "frozen_d_direction":{"residual":"pred_minus_obs","association":"positive in 6/6 years","constraint":"d <= 0","chosen_before_scores":True},
      "forbidden_inputs":["current-day snowmelt","precipitation","temperature","SWE","month or season interactions","second storage","neural network","stage","Yanqi","MQ","2011 for development selection"],
      "catastrophic_definition":"RMSE > 1.5*M2R RMSE or NSE < M2R NSE-0.5",
      "stability_definitions":{"boundary_tolerance":"within 1% of full frozen range","persistent_boundary":"boundary hit in >3 of 6 folds","base_parameter_stable":"no persistent boundary and median relative absolute M2C-vs-M2R change for rho,g,c <= 0.50","high_flow_not_obviously_worse":"macro high-flow RMSE <= 1.05*M2R","improvement_not_single_year":"largest positive RMSE reduction <=70% of total positive reduction"},
      "promotion_gates":["RMSE lower in >=4/6 years","macro mean NSE higher","macro mean RMSE lower","macro mean absolute PBIAS lower","1979 PBIAS less negative and absolute PBIAS lower","1982 absolute PBIAS no worse by >2 percentage points","zero catastrophic years","d non-positive in all folds","d not persistently at -300 bound","rho,g,c stable by frozen definition","macro high-flow RMSE not worse by >5%","improvement not dominated >70% by one year"],
      "if_failed":"reject_M2C_interval_snowmelt and do not try other seven candidates","M3_authorized":False,"2011_used_for_variable_selection":False}
    dump(OUT/"stage_d5_round4_model_protocol_frozen.json",protocol)
    print(json.dumps({"round3_files_verified":len(rows),"candidate_count":len(daily),"passed_count":len(pass_names),"selected":frozen[0]["variable"],"d_bounds":[-300,0]},ensure_ascii=False))


if __name__=="__main__":
    main()
