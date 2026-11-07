from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.run_stage_d9_physics_increment import (
    DEVELOPMENT_END,
    DOWNSTREAM_ID,
    MEASUREMENTS,
    OUT as D9_OUT,
    PRIMARY_END,
    PRIMARY_START,
    ROOT,
    UPSTREAM_ID,
    apply_residual_blend,
    fit_residual_blend,
    prepare_daily_inputs,
    score_models,
    sha256,
)
from vhs.hydraulics import (
    HydraulicScenarioInterpolator,
    ReachHydraulics,
    add_hydraulic_lookup_features,
    build_hydraulic_scenario_library,
)
from vhs.metrics import regression_metrics


OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d9b_hydraulic_sensitivity"
SCENARIO_MANIFEST = ROOT / "outputs/hydraulic_scenario_library/byblk_to_dsk_2011/manifest.json"
ROUGHNESS_GRID = (0.02, 0.03, 0.04, 0.05, 0.06, 0.08)
SIDE_SLOPE_GRID = (1.0, 2.0, 4.0)


def physics_reference_for_parameters(
    daily: pd.DataFrame,
    upstream_states: pd.DataFrame,
    downstream_states: pd.DataFrame,
    reach_length_m: float,
    upstream_datum_m: float,
    downstream_datum_m: float,
    manning_n: float,
    side_slope: float,
) -> tuple[np.ndarray, float]:
    scenarios = build_hydraulic_scenario_library(
        upstream_states,
        downstream_states,
        ReachHydraulics(reach_length_m, manning_n, manning_n),
        upstream_stage_datum_m=upstream_datum_m,
        downstream_stage_datum_m=downstream_datum_m,
        side_slope_h_to_v=side_slope,
    )
    interpolator = HydraulicScenarioInterpolator(scenarios, neighbors=8, power=2.0)
    augmented = add_hydraulic_lookup_features(daily, interpolator, prefix="candidate_")
    reference = augmented.candidate_reference_q_m3s.to_numpy(float)
    coverage = float(np.isfinite(reference).mean())
    return reference, coverage


def main() -> None:
    daily = prepare_daily_inputs()
    measurements = pd.read_csv(MEASUREMENTS, dtype={"station_id": str})
    upstream_states = measurements.loc[measurements.station_id.eq(UPSTREAM_ID)].copy()
    downstream_states = measurements.loc[measurements.station_id.eq(DOWNSTREAM_ID)].copy()
    scenario_manifest = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    reach = scenario_manifest["reach"]
    development = daily.date.le(DEVELOPMENT_END)

    candidates: list[dict[str, float]] = []
    references: dict[tuple[float, float], np.ndarray] = {}
    for manning_n in ROUGHNESS_GRID:
        for side_slope in SIDE_SLOPE_GRID:
            reference, coverage = physics_reference_for_parameters(
                daily,
                upstream_states,
                downstream_states,
                float(reach["length_m"]),
                float(reach["upstream_stage_datum_m"]),
                float(reach["downstream_stage_datum_m"]),
                manning_n,
                side_slope,
            )
            references[(manning_n, side_slope)] = reference
            metrics = regression_metrics(
                daily.loc[development, "q_observed_m3s"], reference[development]
            )
            candidates.append(
                {
                    "manning_n": manning_n,
                    "side_slope_h_to_v": side_slope,
                    "all_period_coverage": coverage,
                    **{f"development_{key}": value for key, value in metrics.items()},
                }
            )
    search = pd.DataFrame(candidates).sort_values(
        ["development_rmse", "development_mae", "manning_n", "side_slope_h_to_v"]
    )
    best = search.iloc[0]
    key = (float(best.manning_n), float(best.side_slope_h_to_v))
    daily["hydraulic_reference_q_m3s"] = references[key]
    daily["hydraulic_reference_available"] = np.isfinite(
        daily.hydraulic_reference_q_m3s
    )
    residual_parameters = fit_residual_blend(
        daily.loc[development, "q_observed_m3s"],
        daily.loc[development, "q_m0_frozen_k10"],
        daily.loc[development, "hydraulic_reference_q_m3s"],
    )
    daily["q_m2_physics_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10, daily.hydraulic_reference_q_m3s, residual_parameters
    )
    daily["q_m3_stage_only"] = np.nan
    daily["window"] = np.select(
        [daily.date.le(DEVELOPMENT_END), daily.date.between(PRIMARY_START, PRIMARY_END)],
        ["development", "primary"],
        default="late_year_diagnostic",
    )
    metrics = score_models(daily)
    metrics = metrics.loc[~metrics.model.eq("M3_stage_only_circularity_control")].copy()

    ratio_rows = []
    for window, part in daily.groupby("window"):
        ratio = part.q_observed_m3s / part.hydraulic_reference_q_m3s
        ratio_rows.append(
            {
                "window": window,
                "rows": int(len(part)),
                "median_observed_to_physics_ratio": float(ratio.median()),
                "mean_observed_to_physics_ratio": float(ratio.mean()),
                "ratio_iqr": float(ratio.quantile(0.75) - ratio.quantile(0.25)),
            }
        )
    seasonal_ratios = pd.DataFrame(ratio_rows)

    primary = metrics.loc[metrics.window.eq("primary")].set_index("model")
    m0 = primary.loc["M0_frozen_K10"]
    m2 = primary.loc["M2_K10_plus_physics_residual"]
    delta_nse = float(m2.nse - m0.nse)
    rmse_improvement_pct = float(100.0 * (m0.rmse - m2.rmse) / m0.rmse)
    selected_at_roughness_boundary = bool(
        np.isclose(best.manning_n, min(ROUGHNESS_GRID))
        or np.isclose(best.manning_n, max(ROUGHNESS_GRID))
    )
    incremental_gate = bool(
        m2.nse > m0.nse
        and m2.rmse < m0.rmse
        and abs(m2.pbias) <= 15.0
        and m2.prediction_coverage >= 0.90
        and not selected_at_roughness_boundary
    )
    manifest = {
        "status": "completed_post_d9_root_cause_sensitivity",
        "selection_data": "development_window_only",
        "primary_already_revealed_before_d9b": True,
        "selected_parameters": {
            "manning_n": key[0],
            "side_slope_h_to_v": key[1],
            "selected_at_roughness_grid_boundary": selected_at_roughness_boundary,
        },
        "primary_delta_nse_M2_minus_M0": delta_nse,
        "primary_rmse_improvement_pct_M2_vs_M0": rmse_improvement_pct,
        "incremental_gate_passed": incremental_gate,
        "decision": (
            "retain_for_independent_multiyear_test"
            if incremental_gate
            else "do_not_promote; effective roughness/geometry is nontransferable or unidentifiable"
        ),
        "interpretation_limit": "D9B was initiated after D9 primary results were observed; it is root-cause analysis only.",
        "inputs": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in [MEASUREMENTS, SCENARIO_MANIFEST, D9_OUT / "manifest.json"]
        },
    }

    OUT.mkdir(parents=True, exist_ok=True)
    search.to_csv(OUT / "hydraulic_parameter_development_search.csv", index=False)
    daily.to_csv(OUT / "daily_selected_hydraulic_predictions.csv", index=False)
    metrics.to_csv(OUT / "selected_hydraulic_metrics.csv", index=False)
    seasonal_ratios.to_csv(OUT / "seasonal_observed_physics_ratios.csv", index=False)
    (OUT / "selected_parameters.json").write_text(
        json.dumps(
            {"selected": manifest["selected_parameters"], "residual_blend": residual_parameters},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    report = f"""# 阶段D9B：水力参数根因敏感性

本阶段在D9主窗口结果已经揭示后启动，只能用于根因分析。糙率候选为{list(ROUGHNESS_GRID)}，边坡系数候选为{list(SIDE_SLOPE_GRID)}；选择只读取2011-01-11至05-10开发窗。

开发窗选择结果为 `n={key[0]:.3f}`、边坡系数 `{key[1]:.1f}`，糙率是否触及网格边界：{'是' if selected_at_roughness_boundary else '否'}。固定主窗口M2相对M0的NSE变化为{delta_nse:+.4f}，RMSE改善率为{rmse_improvement_pct:+.2f}%，增量门槛{'通过' if incremental_gate else '未通过'}。

如果最优糙率触边，说明固定Manning参数正在吸收闸门控制、区间来水、断面变化或缺失DEM坡降，不能解释成稳定河道糙率。即使主窗口改善，本阶段也不能替代新的独立年份验证。
"""
    (OUT / "stage_d9b_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(search.head(10).to_string(index=False))
    print(metrics.to_string(index=False))
    print(seasonal_ratios.to_string(index=False))


if __name__ == "__main__":
    main()
