from __future__ import annotations

import json

import numpy as np
import pandas as pd

from scripts.run_stage_d10_observed_upstream_stage import (
    BYBLK_STAGE,
    BYBLK_STAGE_MANIFEST,
    D9B_DAILY,
    D9B_PARAMETERS,
    SCENARIO_MANIFEST,
    score,
)
from scripts.run_stage_d9_physics_increment import (
    DEVELOPMENT_END,
    DOWNSTREAM_ID,
    MEASUREMENTS,
    PRIMARY_END,
    PRIMARY_START,
    ROOT,
    UPSTREAM_ID,
    apply_residual_blend,
    fit_residual_blend,
    interpolate_geometry_by_driver,
    prepare_daily_inputs,
    sha256,
)
from vhs.hydraulics import (
    HydraulicScenarioInterpolator,
    ReachHydraulics,
    add_hydraulic_lookup_features,
    build_hydraulic_scenario_library,
)


OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10b_regime_aware_geometry"


def regime_geometry(
    daily: pd.DataFrame, upstream_measurements: pd.DataFrame
) -> pd.DataFrame:
    open_reference = upstream_measurements.loc[
        upstream_measurements.date.dt.month.between(4, 10)
    ].copy()
    cold_reference = upstream_measurements.loc[
        ~upstream_measurements.date.dt.month.between(4, 10)
    ].copy()
    result = pd.DataFrame(
        index=daily.index,
        columns=["width_m", "mean_depth_m", "area_m2"],
        dtype=float,
    )
    result["geometry_driver_inside_domain"] = False
    result["geometry_regime"] = ""
    for regime, mask, reference in [
        (
            "open_water_apr_oct",
            daily.date.dt.month.between(4, 10),
            open_reference,
        ),
        (
            "cold_season_nov_mar",
            ~daily.date.dt.month.between(4, 10),
            cold_reference,
        ),
    ]:
        geometry = interpolate_geometry_by_driver(
            reference,
            "stage_m",
            daily.loc[mask, "observed_upstream_stage_m"].to_numpy(float),
            output_columns=("width_m", "mean_depth_m", "area_m2"),
        )
        for column in ("width_m", "mean_depth_m", "area_m2"):
            result.loc[mask, column] = geometry[column].to_numpy()
        result.loc[mask, "geometry_driver_inside_domain"] = geometry[
            "geometry_driver_inside_domain"
        ].to_numpy(bool)
        result.loc[mask, "geometry_regime"] = regime
    result["geometry_driver_inside_domain"] = result[
        "geometry_driver_inside_domain"
    ].astype(bool)
    return result


def main() -> None:
    daily = prepare_daily_inputs()
    stage = pd.read_csv(BYBLK_STAGE, parse_dates=["date"])
    daily = daily.merge(
        stage[["date", "stage_m"]].rename(
            columns={"stage_m": "observed_upstream_stage_m"}
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )
    measurements = pd.read_csv(
        MEASUREMENTS, dtype={"station_id": str}, parse_dates=["date"]
    )
    upstream_states = measurements.loc[measurements.station_id.eq(UPSTREAM_ID)].copy()
    downstream_states = measurements.loc[
        measurements.station_id.eq(DOWNSTREAM_ID)
    ].copy()
    geometry = regime_geometry(daily, upstream_states)
    daily["upstream_stage_m"] = daily.observed_upstream_stage_m
    for column in ("width_m", "mean_depth_m", "area_m2"):
        daily[f"upstream_{column}"] = geometry[column].to_numpy(float)
    daily["upstream_geometry_regime"] = geometry.geometry_regime.to_numpy(str)
    daily["upstream_stage_geometry_inside_domain"] = geometry[
        "geometry_driver_inside_domain"
    ].to_numpy(bool)

    scenario_manifest = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    reach = scenario_manifest["reach"]
    d9b = json.loads(D9B_PARAMETERS.read_text(encoding="utf-8"))
    selected = d9b["selected"]
    scenarios = build_hydraulic_scenario_library(
        upstream_states,
        downstream_states,
        ReachHydraulics(
            float(reach["length_m"]),
            float(selected["manning_n"]),
            float(selected["manning_n"]),
        ),
        upstream_stage_datum_m=float(reach["upstream_stage_datum_m"]),
        downstream_stage_datum_m=float(reach["downstream_stage_datum_m"]),
        side_slope_h_to_v=float(selected["side_slope_h_to_v"]),
    )
    daily = add_hydraulic_lookup_features(
        daily, HydraulicScenarioInterpolator(scenarios, neighbors=8, power=2.0)
    )
    daily["q_m2_frozen_d9b_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10,
        daily.hydraulic_reference_q_m3s,
        d9b["residual_blend"],
    )
    development = daily.date.le(DEVELOPMENT_END)
    refit = fit_residual_blend(
        daily.loc[development, "q_observed_m3s"],
        daily.loc[development, "q_m0_frozen_k10"],
        daily.loc[development, "hydraulic_reference_q_m3s"],
    )
    daily["q_m2r_refit_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10, daily.hydraulic_reference_q_m3s, refit
    )
    daily["window"] = np.select(
        [daily.date.le(DEVELOPMENT_END), daily.date.between(PRIMARY_START, PRIMARY_END)],
        ["development", "primary"],
        default="late_year_diagnostic",
    )
    old = pd.read_csv(D9B_DAILY, parse_dates=["date"])[
        [
            "date",
            "upstream_width_m",
            "upstream_mean_depth_m",
            "upstream_area_m2",
            "hydraulic_reference_q_m3s",
        ]
    ].rename(
        columns={
            "upstream_width_m": "q_indexed_upstream_width_m",
            "upstream_mean_depth_m": "q_indexed_upstream_mean_depth_m",
            "upstream_area_m2": "q_indexed_upstream_area_m2",
            "hydraulic_reference_q_m3s": "q_indexed_physics_q_m3s",
        }
    )
    daily = daily.merge(old, on="date", how="left", validate="one_to_one")
    metrics = score(daily)
    primary = metrics.loc[metrics.window.eq("primary")].set_index("model")
    baseline = primary.loc["M0_frozen_K10"]
    frozen = primary.loc["M2_frozen_D9B_residual"]
    refitted = primary.loc["M2R_refit_observed_stage_residual"]
    physics_coverage = float(
        primary.loc["M1_observed_stage_physics", "prediction_coverage"]
    )
    delta_nse = float(frozen.nse - baseline.nse)
    rmse_improvement = float(100.0 * (baseline.rmse - frozen.rmse) / baseline.rmse)
    frozen_gate = bool(
        physics_coverage >= 0.90
        and frozen.nse > baseline.nse
        and frozen.rmse < baseline.rmse
        and abs(frozen.pbias) <= 15.0
    )
    primary_daily = daily.loc[daily.window.eq("primary")]
    geometry_diagnostics = {
        "primary_stage_area_vs_q_indexed_area_pearson": float(
            primary_daily.upstream_area_m2.corr(
                primary_daily.q_indexed_upstream_area_m2
            )
        ),
        "primary_stage_area_vs_q_indexed_area_mae_m2": float(
            (
                primary_daily.upstream_area_m2
                - primary_daily.q_indexed_upstream_area_m2
            )
            .abs()
            .mean()
        ),
        "primary_new_vs_q_indexed_physics_mae_m3s": float(
            (
                primary_daily.hydraulic_reference_q_m3s
                - primary_daily.q_indexed_physics_q_m3s
            )
            .abs()
            .mean()
        ),
    }
    stage_manifest = json.loads(BYBLK_STAGE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "status": "completed_post_d10_regime_geometry_root_cause",
        "initiated_after_d10_primary_was_observed": True,
        "regime_definition": {
            "open_water": "April through October",
            "cold_season": "November through March",
            "basis": "pre-existing project heuristic seasons; geometry columns only",
        },
        "upstream_stage_status": stage_manifest["status"],
        "frozen_parameters": selected,
        "primary_physics_coverage": physics_coverage,
        "primary_frozen_delta_nse_vs_M0": delta_nse,
        "primary_frozen_rmse_improvement_pct_vs_M0": rmse_improvement,
        "frozen_incremental_gate_passed": frozen_gate,
        "refit_primary_nse": float(refitted.nse),
        "geometry_diagnostics": geometry_diagnostics,
        "decision": (
            "regime_separation_repairs_geometry_mapping_but_requires_independent_validation"
            if frozen_gate
            else "regime_separation_insufficient"
        ),
        "scientific_scope": "post-D10 root-cause diagnostic only",
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [
                BYBLK_STAGE,
                BYBLK_STAGE_MANIFEST,
                D9B_PARAMETERS,
                D9B_DAILY,
                SCENARIO_MANIFEST,
                MEASUREMENTS,
            ]
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUT / "daily_regime_aware_stage_physics.csv", index=False)
    metrics.to_csv(OUT / "regime_aware_stage_physics_metrics.csv", index=False)
    (OUT / "refit_parameters_diagnostic.json").write_text(
        json.dumps(refit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# 阶段D10B：冷季/开敞水期断面关系根因诊断

D10失败后发现全年单一H-断面关系混合了冷季与开敞水期：相近水位对应的面积可相差约一倍。D10B沿用项目既有季节定义，4至10月使用开敞水期断面样本，11至3月使用冷季样本；D9B糙率、边坡和残差参数均不重新选择。

主窗口物理覆盖率为{physics_coverage:.1%}；冻结残差相对M0的NSE变化为{delta_nse:+.4f}，RMSE改善率为{rmse_improvement:+.2f}%，门槛{'通过' if frozen_gate else '未通过'}。主窗口实测H索引面积与Q索引面积相关为{geometry_diagnostics['primary_stage_area_vs_q_indexed_area_pearson']:.4f}，MAE为{geometry_diagnostics['primary_stage_area_vs_q_indexed_area_mae_m2']:.3f} m²。

本阶段在D10主结果揭示后启动，且上游日水位仍待第二人复核，因此即使修复成功也只能支持“分状态断面关系值得独立验证”，不能改写D10冻结迁移结论。
"""
    (OUT / "stage_d10b_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
