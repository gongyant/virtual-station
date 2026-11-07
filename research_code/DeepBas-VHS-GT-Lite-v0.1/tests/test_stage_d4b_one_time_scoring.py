import hashlib
import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
D4A = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4a"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b"
EXPECTED_PARAMETER_SHA = "a24e946ae16b3ebb72f2f0765d1562f9c945a18692bd48471ec1300231f1a838"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_discharge_canonical_schema_ids_counts_uniqueness_and_values():
    path = OUT / "daily_discharge_2011_canonical.csv"
    q = pd.read_csv(path, dtype={"station_id": str})
    assert list(q.columns) == ["station_id", "station_name", "date", "discharge_m3s", "unit", "confirmation_status", "source_file", "source_page", "source_cell", "reviewer", "review_date"]
    assert q.groupby("station_id").size().to_dict() == {"00705600": 365, "00705700": 365, "00705850": 365}
    assert q[["station_id", "date"]].duplicated().sum() == 0
    assert q.discharge_m3s.notna().all()
    assert q.station_id.str.match(r"^\d{8}$").all()
    src = pd.read_csv(D4A / "daily_discharge_2011_reviewed_v2.csv", dtype={"station_id": str})
    src = src[src.station_id.isin(q.station_id.unique())].copy()
    src["expected"] = src.apply(lambda r: r["value"] if r.station_id in {"00705600", "00705700"} else r["discharge"], axis=1)
    joined = q.merge(src[["station_id", "date", "expected"]], on=["station_id", "date"], validate="one_to_one")
    assert (joined.discharge_m3s.astype(float) == joined.expected.astype(float)).all()


def test_stage_and_measurement_canonical_schemas():
    h = pd.read_csv(OUT / "daily_stage_2011_canonical.csv", dtype={"station_id": str})
    assert len(h) == 365 and h.stage_m.notna().all()
    assert h.station_id.eq("00705850").all()
    m = pd.read_csv(OUT / "discharge_measurements_2011_canonical.csv", dtype={"station_id": str, "measurement_id": str})
    assert len(m) == 125 and m.measurement_id.is_unique
    assert m.station_id.str.match(r"^\d{8}$").all()
    assert {"stage_m", "discharge_m3s", "area_m2", "mean_velocity_ms", "width_m"}.issubset(m.columns)
    same_day = m.groupby(["station_id", "date"]).size()
    assert same_day.max() == 3
    assert m.groupby(["station_id", "date"]).sequence.nunique().eq(same_day).all()


def test_qav_summary_and_yanqi_rounding_review_are_frozen():
    m = pd.read_csv(OUT / "discharge_measurements_2011_canonical.csv", dtype={"station_id": str})
    counts = m.groupby(["station_id", "qav_check"]).size().to_dict()
    assert counts == {("00705600", "pass"): 24, ("00705700", "pass"): 48, ("00705850", "pass"): 52, ("00705850", "review_rounding"): 1}
    r = m[(m.station_id == "00705850") & (m.date == "2011-02-28")].iloc[0]
    assert (r.discharge_m3s, r.area_m2, r.mean_velocity_ms, r.q_derived_m3s) == (37.2, 182.0, 0.2, 36.4)
    assert abs(r.relative_error - 0.021505) < 1e-12


def test_parameter_integrity_gate_passed_exact_hash():
    audit = json.loads((OUT / "boundary_only_parameter_integrity_audit.json").read_text(encoding="utf-8"))
    assert audit["passed"] is True and audit["prediction_authorized"] is True
    assert audit["actual_sha256"] == EXPECTED_PARAMETER_SHA
    assert digest(D4A / "boundary_only_frozen_parameters_2005.json") == EXPECTED_PARAMETER_SHA
    assert all(audit["checks"].values())


def test_evaluation_protocol_was_frozen_without_target_window_selection():
    p = json.loads((OUT / "boundary_only_2011_evaluation_protocol_frozen.json").read_text(encoding="utf-8"))
    assert p["primary_window"]["start"] == "2011-05-11"
    assert p["primary_window"]["end"] == "2011-08-31"
    assert p["primary_window"]["expected_day_count"] == 113
    assert p["full_year_extrapolation_diagnostic"]["expected_day_count"] == 355
    assert p["window_selection_used_2011_dsk_labels"] is False


def test_prediction_generator_is_target_isolated_and_manifest_is_frozen():
    source = (ROOT / "scripts/generate_boundary_only_2011_predictions.py").read_text(encoding="utf-8")
    assert "daily_discharge_2011_canonical.csv" not in source
    assert "00705700" not in source
    manifest = json.loads((OUT / "boundary_only_2011_prediction_manifest.json").read_text(encoding="utf-8"))
    assert manifest["used_2011_target_discharge"] is False
    assert manifest["used_2011_target_stage"] is False
    assert manifest["used_2011_target_measurements"] is False
    assert manifest["prediction_frozen_before_scoring"] is True


def test_prediction_hash_rows_windows_and_parameter_hash_columns():
    pred_path = OUT / "boundary_only_2011_predictions_frozen.csv"
    manifest = json.loads((OUT / "boundary_only_2011_prediction_manifest.json").read_text(encoding="utf-8"))
    pred = pd.read_csv(pred_path)
    assert digest(pred_path) == manifest["prediction_sha256"]
    assert len(pred) == 355 and pred.window_primary.sum() == 113
    assert pred.date.iloc[0] == "2011-01-11" and pred.date.iloc[-1] == "2011-12-31"
    assert pred.parameter_sha256.nunique() == 1 and pred.parameter_sha256.iloc[0] == EXPECTED_PARAMETER_SHA
    assert pred.input_sha256.nunique() == 1


def test_scoring_program_does_not_recompute_predictions_or_read_parameters():
    source = (ROOT / "scripts/score_boundary_only_2011.py").read_text(encoding="utf-8")
    assert "boundary_only_frozen_parameters_2005.json" not in source
    assert "intercept_b" not in source
    assert "lag_day" not in source
    completion = json.loads((OUT / "boundary_only_2011_scoring_completion.json").read_text(encoding="utf-8"))
    assert completion["one_time_scoring_completed"] is True
    assert completion["post_score_model_changes_authorized"] is False
    assert completion["prediction_sha256"] == digest(OUT / "boundary_only_2011_predictions_frozen.csv")


def test_metric_outputs_have_both_frozen_windows_and_required_metrics():
    m = pd.read_csv(OUT / "boundary_only_2011_external_metrics.csv")
    assert set(m.window_id) == {"primary", "full_year_extrapolation_diagnostic"}
    assert m.set_index("window_id").loc["primary", "n_days"] == 113
    assert m.set_index("window_id").loc["full_year_extrapolation_diagnostic", "n_days"] == 355
    assert {"NSE", "RMSE", "MAE", "KGE", "PBIAS", "Pearson", "Spearman", "cumulative_volume_bias_m3"}.issubset(m.columns)
    assert len(pd.read_csv(OUT / "boundary_only_2011_flow_regime_metrics.csv")) == 6
    assert len(pd.read_csv(OUT / "boundary_only_2011_monthly_metrics.csv")) == 16
    assert len(pd.read_csv(OUT / "boundary_only_2011_peak_diagnostics.csv")) == 2


def test_result_naming_and_single_model_output_only():
    report = (OUT / "stage_d4b_report_zh.md").read_text(encoding="utf-8")
    assert "C_EXT_boundary_only_K10" in report and "预注册跨年份评估" in report
    for forbidden in ["阶段C主模型外部验证", "完全盲测", "P2严格无站最终结果"]:
        assert forbidden not in report
    assert len(list(OUT.glob("boundary_only_2011_predictions*.csv"))) == 1
