import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"outputs/diagnosis_2005_snapshot/stage_d5_round4"


def j(name):return json.loads((OUT/name).read_text(encoding="utf-8"))


def test_round3_28_files_are_immutable():
    a=j("round3_immutability_audit.json")
    assert a["declared_file_count"]==28
    assert a["audited_file_count"]==28
    assert a["all_hashes_match"] is True
    assert a["all_sizes_match"] is True


def test_candidate_lineage_exposes_multiple_screening_and_winner_bias():
    x=pd.read_csv(OUT/"candidate_variable_selection_lineage.csv")
    assert len(x)==20
    assert x["passed_same_sign_strength_screen"].sum()==8
    assert x["selected_final"].sum()==1
    selected=x[x.selected_final].iloc[0]
    assert selected.candidate_variable=="interval_snowmelt_mm_antecedent_14d"
    assert selected.residual_definition=="pred_minus_obs"
    assert all(selected["corr_%d"%y]>0 for y in range(1978,1984))
    assert x.multiple_screening_risk.all() and x.winner_bias_risk.all()


def test_protocol_was_frozen_to_one_past_only_variable_and_nonpositive_d():
    p=j("stage_d5_round4_model_protocol_frozen.json")
    assert p["status"]=="frozen_before_any_round4_fit"
    assert p["models"]["M2C"]["raw_Z"]=="sum snowmelt_mm over t-14..t-1"
    assert p["parameter_bounds"]["d"]==[-300.0,0.0]
    assert p["restart_count_each_model"]==3
    assert len(p["M2R_starts"])==len(p["M2C_starts"])==3
    assert p["frozen_d_direction"]["chosen_before_scores"] is True
    forbidden="|".join(p["forbidden_inputs"])
    for item in ["current-day snowmelt","precipitation","temperature","SWE","second storage","stage","Yanqi","MQ"]:
        assert item in forbidden


def test_frozen_snowmelt_audit_has_complete_source_and_no_future_leakage():
    a=j("frozen_candidate_variable_audit.json")
    assert a["raw_day_count"]==2191 and a["raw_missing_count"]==0
    assert a["dates_unique"] is True
    assert a["construction_order"]==["read daily snowmelt_mm","shift(1)","rolling(window=14,min_periods=14).sum()"]
    assert a["includes_current_day"] is False and a["includes_future_day"] is False
    assert abs(a["weight_sum"]-1)<1e-12
    assert a["2011_used_for_selection"] is False


def test_outer_folds_and_training_only_z_standardization_are_correct():
    par=pd.read_csv(OUT/"m2c_parameters_by_fold.csv")
    assert len(par)==12
    for row in par.itertuples(index=False):
        assert str(int(row.outer_year)) not in str(row.outer_train_years).split("|")
    era=ROOT/"data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc"
    with h5py.File(str(era),"r") as f:
        snow=np.asarray(f["snowmelt_mm"][0],float);time=np.asarray(f["time"],int)
    d=pd.DataFrame({"date":pd.to_datetime("1978-01-01")+pd.to_timedelta(time,unit="D"),"snow":snow})
    d["z"]=d.snow.shift(1).rolling(14,min_periods=14).sum();d["year"]=d.date.dt.year
    for outer in range(1978,1984):
        vals=[]
        for year in range(1978,1984):
            if year==outer:continue
            x=d[d.year==year].z.copy()
            if year==1978:x.iloc[:60]=np.nan
            vals.extend(x.dropna().tolist())
        rows=par[par.outer_year==outer]
        assert np.allclose(rows.z_train_mean,float(np.mean(vals)))
        assert np.allclose(rows.z_train_std,float(np.std(vals,ddof=0)))


def test_m2r_is_numerically_compatible_with_round2_m2():
    a=j("m2r_round2_compatibility_audit.json")
    assert a["model_class_exactly_equivalent"] is True
    assert a["rmse_between_prediction_series"]<1e-3


def test_m2c_is_rejected_only_after_frozen_gates_and_transfer_stops():
    d=j("m2c_development_promotion_decision.json")
    assert d["decision"]=="reject_M2C_interval_snowmelt"
    assert sum(d["gates"].values())==11
    assert d["gates"]["year_1979_underestimate_relieved"] is False
    assert all(v for k,v in d["gates"].items() if k!="year_1979_underestimate_relieved")
    assert d["transfer_authorized"] is False
    assert d["try_other_candidates_if_failed"] is False
    assert d["M3_authorized"] is False
    forbidden_outputs=["m2r_frozen_parameters_1978_1983.json","m2c_frozen_parameters_1978_1983.json","retro_transfer_predictions_frozen.csv","retro_transfer_metrics.csv"]
    assert not any((OUT/x).exists() for x in forbidden_outputs)


def test_failure_is_not_hidden_and_2011_was_not_read():
    r=pd.read_csv(OUT/"m2r_nested_loyo_results.csv");c=pd.read_csv(OUT/"m2c_nested_loyo_results.csv")
    r79=r[(r.row_type=="year")&(r.year==1979)].iloc[0];c79=c[(c.row_type=="year")&(c.year==1979)].iloc[0]
    assert c79.pbias<r79.pbias
    access=j("stage_d5_round4_development_input_access_audit.json")
    assert access["read_2000"] is False and access["read_2001"] is False and access["read_2011"] is False
    assert access["read_transfer_labels"] is False
    assert access["other_weather_candidates_tried"] is False

