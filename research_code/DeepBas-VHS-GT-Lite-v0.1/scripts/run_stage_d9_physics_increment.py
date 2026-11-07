from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from vhs.hydraulics import HydraulicScenarioInterpolator, add_hydraulic_lookup_features
from vhs.metrics import regression_metrics


ROOT = Path(__file__).resolve().parents[1]
MEASUREMENTS = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/discharge_measurements_2011_canonical.csv"
DAILY_Q = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/daily_discharge_2011_canonical.csv"
DSK_STAGE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d5/d5c_stage_and_features/daily_stage_dsk_2011_reviewed.csv"
FROZEN = ROOT / "outputs/diagnosis_2005_snapshot/stage_d4b/boundary_only_2011_predictions_frozen.csv"
SCENARIOS = ROOT / "outputs/hydraulic_scenario_library/byblk_to_dsk_2011/hydraulic_scenarios.csv"
SCENARIO_MANIFEST = ROOT / "outputs/hydraulic_scenario_library/byblk_to_dsk_2011/manifest.json"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d9_physics_increment"

UPSTREAM_ID = "00705600"
DOWNSTREAM_ID = "00705700"
DEVELOPMENT_END = pd.Timestamp("2011-05-10")
PRIMARY_START = pd.Timestamp("2011-05-11")
PRIMARY_END = pd.Timestamp("2011-08-31")
RIDGE_LAMBDA = 1.0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def interpolate_geometry_by_driver(
    reference: pd.DataFrame,
    driver_column: str,
    query: np.ndarray,
    output_columns: tuple[str, ...] = ("stage_m", "width_m", "mean_depth_m", "area_m2"),
) -> pd.DataFrame:
    """Interpolate observed hydraulic states without extrapolating their domain."""

    required = {driver_column, *output_columns}
    missing = required - set(reference)
    if missing:
        raise KeyError(f"geometry reference missing columns: {sorted(missing)}")
    grouped = (
        reference.loc[:, list(required)]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .groupby(driver_column, as_index=False)
        .mean(numeric_only=True)
        .sort_values(driver_column)
    )
    if len(grouped) < 2:
        raise ValueError("at least two distinct hydraulic reference states are required")
    driver = grouped[driver_column].to_numpy(float)
    query = np.asarray(query, dtype=float)
    inside = np.isfinite(query) & (query >= driver.min()) & (query <= driver.max())
    result = pd.DataFrame(index=np.arange(len(query)))
    for column in output_columns:
        values = np.full(len(query), np.nan, dtype=float)
        values[inside] = np.interp(query[inside], driver, grouped[column].to_numpy(float))
        result[column] = values
    result["geometry_driver_inside_domain"] = inside
    result["geometry_driver_distance_to_domain"] = np.where(
        inside,
        0.0,
        np.minimum(np.abs(query - driver.min()), np.abs(query - driver.max())),
    )
    return result


def fit_residual_blend(
    observed: np.ndarray,
    baseline: np.ndarray,
    physics: np.ndarray,
    ridge_lambda: float = RIDGE_LAMBDA,
) -> dict[str, float]:
    observed = np.asarray(observed, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    physics = np.asarray(physics, dtype=float)
    mask = np.isfinite(observed) & np.isfinite(baseline) & np.isfinite(physics)
    if mask.sum() < 20:
        raise ValueError("residual blend requires at least 20 complete development rows")
    delta = physics[mask] - baseline[mask]
    target = observed[mask] - baseline[mask]
    x_mean = float(delta.mean())
    x_std = float(delta.std())
    if x_std <= 1e-12:
        raise ValueError("physics-minus-baseline has no development variance")
    z = (delta - x_mean) / x_std
    intercept = float(target.mean())
    beta = float(np.dot(z, target - intercept) / (np.dot(z, z) + ridge_lambda))
    return {
        "intercept_m3s": intercept,
        "beta_standardized": beta,
        "delta_mean_m3s": x_mean,
        "delta_std_m3s": x_std,
        "ridge_lambda": float(ridge_lambda),
        "fit_rows": int(mask.sum()),
    }


def apply_residual_blend(
    baseline: np.ndarray, physics: np.ndarray, parameters: dict[str, float]
) -> np.ndarray:
    baseline = np.asarray(baseline, dtype=float)
    physics = np.asarray(physics, dtype=float)
    complete = np.isfinite(baseline) & np.isfinite(physics)
    predicted = np.maximum(baseline, 0.0)
    z = (
        physics[complete]
        - baseline[complete]
        - parameters["delta_mean_m3s"]
    ) / parameters["delta_std_m3s"]
    predicted[complete] = np.maximum(
        baseline[complete]
        + parameters["intercept_m3s"]
        + parameters["beta_standardized"] * z,
        0.0,
    )
    return predicted


def fit_stage_only_control(stage: np.ndarray, observed: np.ndarray) -> dict[str, object]:
    stage = np.asarray(stage, dtype=float)
    observed = np.asarray(observed, dtype=float)
    mask = np.isfinite(stage) & np.isfinite(observed)
    if mask.sum() < 20:
        raise ValueError("stage-only control requires at least 20 development rows")
    mean = float(stage[mask].mean())
    std = float(stage[mask].std())
    z = (stage[mask] - mean) / std
    design = np.column_stack([np.ones(mask.sum()), z, z**2])
    penalty = np.diag([0.0, RIDGE_LAMBDA, RIDGE_LAMBDA])
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ observed[mask])
    return {
        "stage_mean_m": mean,
        "stage_std_m": std,
        "coefficients": coefficients.tolist(),
        "ridge_lambda": RIDGE_LAMBDA,
        "fit_rows": int(mask.sum()),
    }


def apply_stage_only_control(stage: np.ndarray, parameters: dict[str, object]) -> np.ndarray:
    stage = np.asarray(stage, dtype=float)
    z = (stage - float(parameters["stage_mean_m"])) / float(parameters["stage_std_m"])
    design = np.column_stack([np.ones(len(stage)), z, z**2])
    return np.maximum(design @ np.asarray(parameters["coefficients"], dtype=float), 0.0)


def prepare_daily_inputs() -> pd.DataFrame:
    measurements = pd.read_csv(MEASUREMENTS, dtype={"station_id": str}, parse_dates=["date"])
    daily_q = pd.read_csv(DAILY_Q, dtype={"station_id": str}, parse_dates=["date"])
    stage = pd.read_csv(DSK_STAGE, dtype={"station_id": str}, parse_dates=["date"])
    frozen = pd.read_csv(FROZEN, parse_dates=["date"]).rename(columns={"q_pred": "q_m0_frozen_k10"})

    q_pivot = daily_q.pivot(index="date", columns="station_id", values="discharge_m3s")
    daily = frozen.merge(
        q_pivot[[UPSTREAM_ID, DOWNSTREAM_ID]].rename(
            columns={UPSTREAM_ID: "q_upstream_m3s", DOWNSTREAM_ID: "q_observed_m3s"}
        ),
        left_on="date",
        right_index=True,
        how="left",
        validate="one_to_one",
    ).merge(
        stage[["date", "stage_m"]].rename(columns={"stage_m": "downstream_stage_m"}),
        on="date",
        how="left",
        validate="one_to_one",
    )

    upstream_measurements = measurements.loc[
        measurements.station_id.eq(UPSTREAM_ID)
    ].copy()
    downstream_measurements = measurements.loc[
        measurements.station_id.eq(DOWNSTREAM_ID)
    ].copy()
    upstream_geometry = interpolate_geometry_by_driver(
        upstream_measurements,
        "discharge_m3s",
        daily.q_upstream_m3s.to_numpy(float),
    ).add_prefix("upstream_")
    downstream_geometry = interpolate_geometry_by_driver(
        downstream_measurements,
        "stage_m",
        daily.downstream_stage_m.to_numpy(float),
        output_columns=("width_m", "mean_depth_m", "area_m2"),
    ).add_prefix("downstream_")
    daily = pd.concat(
        [daily.reset_index(drop=True), upstream_geometry, downstream_geometry], axis=1
    )
    return daily


def score_models(frame: pd.DataFrame) -> pd.DataFrame:
    windows = {
        "development": frame.date.between("2011-01-11", DEVELOPMENT_END),
        "primary": frame.date.between(PRIMARY_START, PRIMARY_END),
        "late_year_diagnostic": frame.date.between("2011-09-01", "2011-12-31"),
        "full_year_diagnostic": frame.date.between("2011-01-11", "2011-12-31"),
    }
    models = {
        "M0_frozen_K10": "q_m0_frozen_k10",
        "M1_physics_lookup": "hydraulic_reference_q_m3s",
        "M2_K10_plus_physics_residual": "q_m2_physics_residual",
        "M3_stage_only_circularity_control": "q_m3_stage_only",
    }
    rows = []
    for window, window_mask in windows.items():
        total = int(window_mask.sum())
        for model, column in models.items():
            part = frame.loc[window_mask, ["q_observed_m3s", column]]
            metrics = regression_metrics(part.q_observed_m3s, part[column])
            rows.append(
                {
                    "window": window,
                    "model": model,
                    "total_days": total,
                    "prediction_coverage": float(np.isfinite(part[column]).sum() / total),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    daily = prepare_daily_inputs()
    scenarios = pd.read_csv(SCENARIOS)
    interpolator = HydraulicScenarioInterpolator(scenarios, neighbors=8, power=2.0)
    daily = add_hydraulic_lookup_features(daily, interpolator)

    development = daily.date.le(DEVELOPMENT_END)
    residual_parameters = fit_residual_blend(
        daily.loc[development, "q_observed_m3s"],
        daily.loc[development, "q_m0_frozen_k10"],
        daily.loc[development, "hydraulic_reference_q_m3s"],
    )
    stage_parameters = fit_stage_only_control(
        daily.loc[development, "downstream_stage_m"],
        daily.loc[development, "q_observed_m3s"],
    )
    daily["q_m2_physics_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10, daily.hydraulic_reference_q_m3s, residual_parameters
    )
    daily["q_m3_stage_only"] = apply_stage_only_control(
        daily.downstream_stage_m, stage_parameters
    )
    daily["physics_residual_applied"] = daily.hydraulic_reference_available.astype(bool)
    daily["window"] = np.select(
        [daily.date.le(DEVELOPMENT_END), daily.date.between(PRIMARY_START, PRIMARY_END)],
        ["development", "primary"],
        default="late_year_diagnostic",
    )
    metrics = score_models(daily)

    primary = metrics.loc[metrics.window.eq("primary")].set_index("model")
    baseline = primary.loc["M0_frozen_K10"]
    physics = primary.loc["M2_K10_plus_physics_residual"]
    physics_reference_coverage = float(
        primary.loc["M1_physics_lookup", "prediction_coverage"]
    )
    delta_nse = float(physics.nse - baseline.nse)
    rmse_improvement_pct = float(100.0 * (baseline.rmse - physics.rmse) / baseline.rmse)
    incremental_gate = bool(
        physics_reference_coverage >= 0.90
        and delta_nse > 0
        and rmse_improvement_pct > 0
        and abs(physics.pbias) <= 15.0
    )
    scenario_manifest = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    parameters = {
        "protocol": {
            "identity": "Stage D9 revealed-year physics increment diagnostic",
            "development_window": "2011-01-11..2011-05-10",
            "primary_window": "2011-05-11..2011-08-31",
            "primary_used_for_fitting": False,
            "geometry_inventory": "2011 sparse measurement geometry; target Q column excluded from downstream H-to-geometry mapping",
        },
        "residual_blend": residual_parameters,
        "stage_only_control": stage_parameters,
    }
    manifest = {
        "status": "completed_revealed_year_diagnostic",
        "incremental_gate_passed": incremental_gate,
        "primary_delta_nse_M2_minus_M0": delta_nse,
        "primary_rmse_improvement_pct_M2_vs_M0": rmse_improvement_pct,
        "primary_physics_reference_coverage": physics_reference_coverage,
        "scientific_scope": "diagnostic_only_not_external_validation",
        "scenario_library_status": scenario_manifest["status"],
        "physics_reference_authorized_as_label": False,
        "stage_discharge_circularity_risk": "high; M3 is a diagnostic control, not evidence of independent prediction",
        "known_limitations": [
            "BYBLK daily stage is unavailable; upstream geometry is indexed by observed upstream discharge.",
            "DSK is downstream of a gate and gate state is unavailable.",
            "DEM raster slope is unavailable; the scenario library remains diagnostic-only.",
            "The 2011 DSK daily Q series may have been derived from an H-Q rating procedure.",
        ],
        "inputs": {str(path.relative_to(ROOT)): sha256(path) for path in [MEASUREMENTS, DAILY_Q, DSK_STAGE, FROZEN, SCENARIOS, SCENARIO_MANIFEST]},
        "outputs": ["daily_physics_increment_predictions.csv", "physics_increment_metrics.csv", "frozen_parameters.json", "stage_d9_report_zh.md"],
    }

    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "daily_physics_increment_predictions.csv", index=False)
    metrics.to_csv(OUT / "physics_increment_metrics.csv", index=False)
    (OUT / "frozen_parameters.json").write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    def metric_line(model: str) -> str:
        row = primary.loc[model]
        return f"|{model}|{row.nse:.4f}|{row.rmse:.3f}|{row.mae:.3f}|{row.kge:.4f}|{row.pbias:.2f}%|{row.prediction_coverage:.1%}|"

    report = f"""# 阶段D9：2011已揭示年份物理增量诊断

## 协议

本阶段固定使用2011-01-11至05-10拟合物理残差修正，2011-05-11至08-31沿用D4B主窗口评分。主窗口未参与M2或M3参数估计。M0为冻结K10；M1为质量/能量约束情景查表；M2为冻结K10加非负输出物理残差；M3为水位单变量循环风险对照。

## 主窗口结果

|模型|NSE|RMSE|MAE|KGE|PBIAS|覆盖率|
|---|---:|---:|---:|---:|---:|---:|
{metric_line('M0_frozen_K10')}
{metric_line('M1_physics_lookup')}
{metric_line('M2_K10_plus_physics_residual')}
{metric_line('M3_stage_only_circularity_control')}

M2相对M0的NSE变化为{delta_nse:+.4f}，RMSE改善率为{rmse_improvement_pct:+.2f}%。预声明增量门槛结果：{'通过' if incremental_gate else '未通过'}。

## 解释边界

本轮只能判断物理状态是否为冻结上游边界模型提供增量信息。它不是新外部验证：2011结果已经揭示；大山口日Q可能由H-Q关系整编；闸门状态和真实DEM坡降仍缺失；巴音布鲁克日水位未完成可靠转录。M3即使表现很好，也主要量化H-Q标签循环上限，不能解释为独立恢复真实流量。
"""
    (OUT / "stage_d9_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
