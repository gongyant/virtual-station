import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round3"
R2 = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5_round2"


def load_json(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def test_round2_all_34_files_are_immutable_and_decision_is_unchanged():
    audit = load_json("stage_d5_round2_immutability_audit.json")
    assert audit["declared_file_count"] == 34
    assert audit["audited_file_count"] == 34
    assert audit["all_hashes_match"] is True
    assert audit["all_sizes_match"] is True
    decision = json.loads((R2 / "model_promotion_decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "reject_current_single_upstream_model_family"
    assert decision["M3_development_authorized"] is False


def test_round1_manifest_is_explicitly_reconstructed_not_backdated():
    manifest = load_json("stage_d5_round1_reconstructed_manifest.json")
    assert manifest["manifest_type"] == "reconstructed_after_completion"
    assert manifest["original_freeze_time_unknown"] is True
    assert manifest["file_count"] > 0
    assert all(x["original_freeze_time_unknown"] for x in manifest["files"])
    assert not any(x["file_path"].endswith("stage_d5_round1_manifest.json") for x in manifest["files"])


def test_m2_reparameterization_is_exact_and_uses_no_refit():
    p = pd.read_csv(OUT / "m2_reparameterized_parameters.csv")
    audit = load_json("m2_prediction_equivalence_audit.json")
    assert len(p) == 6
    assert p["fit_reused_without_refit"].all()
    assert np.allclose(p["normalized_g"], p["original_a"]/(1-p["rho"]), atol=1e-12)
    assert audit["refitted"] is False
    assert audit["equivalent_within_tolerance"] is True
    assert audit["maximum_absolute_prediction_difference"] < 1e-8


def test_memory_timescales_follow_frozen_rho_and_exceed_15_days():
    p = pd.read_csv(OUT / "m1_m2_memory_timescale_comparison.csv")
    expected_half = np.log(.5)/np.log(p["rho"])
    expected_efold = -1/np.log(p["rho"])
    assert np.allclose(p["half_life_days"], expected_half)
    assert np.allclose(p["e_folding_time_days"], expected_efold)
    assert p["m1_width_at_frozen_upper_boundary"].all()
    assert p["m2_90pct_exceeds_15_days"].all()
    assert p["days_to_90pct_cumulative_response"].min() >= 72


def test_1979_and_1982_bias_shapes_are_preserved_not_hidden():
    annual = pd.read_csv(OUT / "annual_gain_and_volume_diagnostics.csv")
    detail = pd.read_csv(OUT / "year_specific_bias_diagnostics.csv")
    y79 = annual.set_index("year").loc[1979]
    assert y79["dsk_byblk_mean_ratio"] == annual["dsk_byblk_mean_ratio"].max()
    assert y79["m2_pbias_percent"] < -30
    d79 = detail[(detail.year==1979)&(detail.model=="M2")&(detail.row_type=="year_summary")].iloc[0]
    assert d79["top10pct_flow_share_of_net_underestimate"] < .70
    assert d79["longest_negative_error_run_days"] >= 100
    y82 = annual.set_index("year").loc[1982]
    assert y82["m2_pbias_percent"] > 17
    regimes = detail[(detail.year==1982)&(detail.model=="M2")&(detail.row_type=="flow_regime")].set_index("group")
    assert regimes.loc["low","pbias_percent"] > 0
    assert regimes.loc["middle","pbias_percent"] > 0
    assert abs(regimes.loc["high","pbias_percent"]) < 3


def test_era5_is_complete_causal_and_does_not_explain_1979_annual_gain_alone():
    audit = pd.read_csv(OUT / "era5_interval_input_audit.csv")
    base = audit[audit["source_type"] != "derived"]
    assert (base["row_count"] == 2191).all()
    assert (base["missing_count"] == 0).all()
    assert base["time_complete"].all()
    assert audit["interval_precip_mass_balance_max_abs_diff_mm"].max() < 1e-5
    associations = pd.read_csv(OUT / "posthoc_additional_input_associations.csv")
    annual = associations[associations.analysis_scope=="annual_1978_1983"]
    assert annual["pearson"].abs().max() < .8
    snow = associations[(associations.analysis_scope=="daily_m2_outer_residual") & (associations.candidate=="interval_snowmelt_mm_antecedent_14d")].iloc[0]
    assert snow["month_anomaly_same_sign_year_count"] == 6


def test_only_m2c_is_admitted_and_2011_is_not_used():
    decision = load_json("next_branch_decision.json")
    access = load_json("stage_d5_round3_input_access_audit.json")
    assert decision["selected_branch"] == "M2C_single_storage_plus_interval_weather"
    assert decision["M3_authorized"] is False
    assert decision["new_model_trained"] is False
    assert decision["performance_claim_allowed"] is False
    assert len(decision["frozen_candidate_variable_group"]) == 1
    assert decision["frozen_candidate_variable_group"][0]["variable"] == "interval_snowmelt_mm_antecedent_14d"
    assert access["2011_semantic_data_read"] is False
    assert access["2011_used_for_variable_selection"] is False
    assert access["new_nse_generated"] is False
    assert access["m3_developed"] is False

