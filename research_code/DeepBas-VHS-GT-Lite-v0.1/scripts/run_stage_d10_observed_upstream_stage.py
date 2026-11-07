from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

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
from vhs.metrics import regression_metrics


BYBLK_STAGE = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10_byblk_stage/daily_stage_byblk_2011_reviewed.csv"
BYBLK_STAGE_MANIFEST = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10_byblk_stage/manifest.json"
D9B_PARAMETERS = ROOT / "outputs/diagnosis_2005_snapshot/stage_d9b_hydraulic_sensitivity/selected_parameters.json"
D9B_DAILY = ROOT / "outputs/diagnosis_2005_snapshot/stage_d9b_hydraulic_sensitivity/daily_selected_hydraulic_predictions.csv"
SCENARIO_MANIFEST = ROOT / "outputs/hydraulic_scenario_library/byblk_to_dsk_2011/manifest.json"
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d10_observed_upstream_stage"


def score(frame: pd.DataFrame) -> pd.DataFrame:
    windows = {
        "development": frame.date.between("2011-01-11", DEVELOPMENT_END),
        "primary": frame.date.between(PRIMARY_START, PRIMARY_END),
        "late_year_diagnostic": frame.date.between("2011-09-01", "2011-12-31"),
        "full_year_diagnostic": frame.date.between("2011-01-11", "2011-12-31"),
    }
    models = {
        "M0_frozen_K10": "q_m0_frozen_k10",
        "M1_observed_stage_physics": "hydraulic_reference_q_m3s",
        "M2_frozen_D9B_residual": "q_m2_frozen_d9b_residual",
        "M2R_refit_observed_stage_residual": "q_m2r_refit_residual",
    }
    rows = []
    for window, mask in windows.items():
        total = int(mask.sum())
        for model, column in models.items():
            part = frame.loc[mask, ["q_observed_m3s", column]]
            rows.append(
                {
                    "window": window,
                    "model": model,
                    "total_days": total,
                    "prediction_coverage": float(part[column].notna().sum() / total),
                    **regression_metrics(part.q_observed_m3s, part[column]),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    daily = prepare_daily_inputs()
    byblk_stage = pd.read_csv(BYBLK_STAGE, parse_dates=["date"])
    daily = daily.merge(
        byblk_stage[["date", "stage_m", "confirmation_status"]].rename(
            columns={
                "stage_m": "observed_upstream_stage_m",
                "confirmation_status": "upstream_stage_confirmation_status",
            }
        ),
        on="date",
        how="left",
        validate="one_to_one",
    )
    measurements = pd.read_csv(MEASUREMENTS, dtype={"station_id": str})
    upstream_states = measurements.loc[measurements.station_id.eq(UPSTREAM_ID)].copy()
    downstream_states = measurements.loc[measurements.station_id.eq(DOWNSTREAM_ID)].copy()
    upstream_geometry = interpolate_geometry_by_driver(
        upstream_states,
        "stage_m",
        daily.observed_upstream_stage_m.to_numpy(float),
        output_columns=("width_m", "mean_depth_m", "area_m2"),
    ).add_prefix("observed_stage_upstream_")
    daily["upstream_stage_m"] = daily.observed_upstream_stage_m
    for column in ("width_m", "mean_depth_m", "area_m2"):
        daily[f"upstream_{column}"] = upstream_geometry[
            f"observed_stage_upstream_{column}"
        ].to_numpy()
    daily["upstream_stage_geometry_inside_domain"] = upstream_geometry[
        "observed_stage_upstream_geometry_driver_inside_domain"
    ].to_numpy(bool)

    scenario_manifest = json.loads(SCENARIO_MANIFEST.read_text(encoding="utf-8"))
    reach = scenario_manifest["reach"]
    d9b_parameters = json.loads(D9B_PARAMETERS.read_text(encoding="utf-8"))
    selected = d9b_parameters["selected"]
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
    interpolator = HydraulicScenarioInterpolator(scenarios, neighbors=8, power=2.0)
    daily = add_hydraulic_lookup_features(daily, interpolator)

    frozen_residual = d9b_parameters["residual_blend"]
    daily["q_m2_frozen_d9b_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10,
        daily.hydraulic_reference_q_m3s,
        frozen_residual,
    )
    development = daily.date.le(DEVELOPMENT_END)
    refit_parameters = fit_residual_blend(
        daily.loc[development, "q_observed_m3s"],
        daily.loc[development, "q_m0_frozen_k10"],
        daily.loc[development, "hydraulic_reference_q_m3s"],
    )
    daily["q_m2r_refit_residual"] = apply_residual_blend(
        daily.q_m0_frozen_k10,
        daily.hydraulic_reference_q_m3s,
        refit_parameters,
    )
    daily["window"] = np.select(
        [daily.date.le(DEVELOPMENT_END), daily.date.between(PRIMARY_START, PRIMARY_END)],
        ["development", "primary"],
        default="late_year_diagnostic",
    )

    old = pd.read_csv(D9B_DAILY, parse_dates=["date"])[
        ["date", "upstream_stage_m", "hydraulic_reference_q_m3s"]
    ].rename(
        columns={
            "upstream_stage_m": "q_indexed_upstream_stage_m",
            "hydraulic_reference_q_m3s": "q_d9b_q_indexed_physics",
        }
    )
    daily = daily.merge(old, on="date", how="left", validate="one_to_one")
    daily["observed_stage_minus_q_indexed_physics_m3s"] = (
        daily.hydraulic_reference_q_m3s - daily.q_d9b_q_indexed_physics
    )
    metrics = score(daily)
    relationship_rows = []
    for window, part in daily.groupby("window"):
        relationship_rows.append(
            {
                "window": window,
                "rows": int(len(part)),
                "upstream_stage_q_pearson": float(
                    part.observed_upstream_stage_m.corr(part.q_upstream_m3s)
                ),
                "downstream_stage_q_pearson": float(
                    part.downstream_stage_m.corr(part.q_observed_m3s)
                ),
                "observed_stage_physics_q_pearson": float(
                    part.hydraulic_reference_q_m3s.corr(part.q_observed_m3s)
                ),
                "q_indexed_physics_q_pearson": float(
                    part.q_d9b_q_indexed_physics.corr(part.q_observed_m3s)
                ),
                "observed_vs_q_indexed_stage_pearson": float(
                    part.observed_upstream_stage_m.corr(
                        part.q_indexed_upstream_stage_m
                    )
                ),
                "observed_vs_q_indexed_stage_mae_m": float(
                    (part.observed_upstream_stage_m - part.q_indexed_upstream_stage_m)
                    .abs()
                    .mean()
                ),
                "new_vs_old_physics_mae_m3s": float(
                    (
                        part.hydraulic_reference_q_m3s
                        - part.q_d9b_q_indexed_physics
                    )
                    .abs()
                    .mean()
                ),
                "upstream_stage_geometry_domain_coverage": float(
                    part.upstream_stage_geometry_inside_domain.mean()
                ),
            }
        )
    relationships = pd.DataFrame(relationship_rows)
    primary = metrics.loc[metrics.window.eq("primary")].set_index("model")
    baseline = primary.loc["M0_frozen_K10"]
    frozen = primary.loc["M2_frozen_D9B_residual"]
    refit = primary.loc["M2R_refit_observed_stage_residual"]
    physics_coverage = float(
        primary.loc["M1_observed_stage_physics", "prediction_coverage"]
    )
    frozen_delta_nse = float(frozen.nse - baseline.nse)
    frozen_rmse_improvement = float(
        100.0 * (baseline.rmse - frozen.rmse) / baseline.rmse
    )
    frozen_gate = bool(
        physics_coverage >= 0.90
        and frozen.nse > baseline.nse
        and frozen.rmse < baseline.rmse
        and abs(frozen.pbias) <= 15.0
    )
    stage_manifest = json.loads(BYBLK_STAGE_MANIFEST.read_text(encoding="utf-8"))
    manifest = {
        "status": "completed_diagnostic_observed_upstream_stage",
        "upstream_stage_status": stage_manifest["status"],
        "upstream_stage_rows": stage_manifest["rows"],
        "upstream_stage_monthly_summary_discrepancies": stage_manifest[
            "monthly_summary_discrepancy_months"
        ],
        "hydraulic_parameters_frozen_from_d9b": selected,
        "d9b_residual_parameters_refitted": False,
        "primary_physics_coverage": physics_coverage,
        "primary_frozen_delta_nse_vs_M0": frozen_delta_nse,
        "primary_frozen_rmse_improvement_pct_vs_M0": frozen_rmse_improvement,
        "frozen_incremental_gate_passed": frozen_gate,
        "refit_primary_nse": float(refit.nse),
        "scientific_scope": "diagnostic_only; 2011 is revealed and upstream stage awaits second review",
        "decision": (
            "observed_upstream_stage_supports_incremental_signal"
            if frozen_gate
            else "observed_upstream_stage_does_not_transfer_frozen_d9b_correction"
        ),
        "primary_relationship_diagnostics": relationships.loc[
            relationships.window.eq("primary")
        ].iloc[0].to_dict(),
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
    daily.to_csv(OUT / "daily_observed_stage_physics_predictions.csv", index=False)
    metrics.to_csv(OUT / "observed_stage_physics_metrics.csv", index=False)
    relationships.to_csv(OUT / "stage_physics_relationship_diagnostics.csv", index=False)
    (OUT / "refit_parameters_diagnostic.json").write_text(
        json.dumps(refit_parameters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# 阶段D10：上游实测日水位替代流量索引代理

巴音布鲁克2011逐日平均水位已完成第一轮逐格视觉转录，共365天；11个月月均与表底打印值闭合，12月按原格重建为3.9919 m而表底印为4.00 m，保留差异并等待第二位复核。

D10冻结D9B选出的 `n={float(selected['manning_n']):.3f}`、边坡系数 `{float(selected['side_slope_h_to_v']):.1f}` 以及D9B残差参数，只把上游几何索引由已知Q改为实测H。固定主窗口物理覆盖率为{physics_coverage:.1%}；冻结修正相对M0的NSE变化为{frozen_delta_nse:+.4f}，RMSE改善率为{frozen_rmse_improvement:+.2f}%，增量门槛{'通过' if frozen_gate else '未通过'}。

另列M2R仅用早期开发窗重新拟合残差，主窗口NSE为{float(refit.nse):.4f}，只用于判断输入尺度变化，不作为冻结迁移结论。

本阶段仍不是外部验证：2011结果已揭示，上游日水位仅完成第一轮复核，DEM与闸门状态仍缺失。
"""
    (OUT / "stage_d10_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))
    print(relationships.to_string(index=False))


if __name__ == "__main__":
    main()
