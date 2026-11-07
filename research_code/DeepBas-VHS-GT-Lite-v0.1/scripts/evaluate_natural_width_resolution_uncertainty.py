from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from scripts.evaluate_natural_width_transfer_diagnostics import (
    fit_power_law,
    load_pairs,
    metrics,
    predict_power_law,
)


SENTINEL_PATH = Path(
    "data/processed/natural_width/sentinel2_byblk_multitransect/"
    "sentinel2_multitransect_width_measurements.csv"
)
SWOT_PATH = Path(
    "data/processed/natural_width/swot_byblk_reach/"
    "swot_reach_observations_accepted.csv"
)
OUTPUT = Path(
    "outputs/virtual_station_mainline/natural_width_resolution_uncertainty_round"
)
RANDOM_SEED = 20260726
MONTE_CARLO_DRAWS = 5000

SCENARIOS = {
    "landsat_30m": {
        "pixel_size_m": 30.0,
        "spatial_dispersion_scale": 1.0,
        "interpretation": "Current Landsat native-resolution uncertainty",
    },
    "optimistic_10m": {
        "pixel_size_m": 10.0,
        "spatial_dispersion_scale": 1.0 / 3.0,
        "interpretation": "Counterfactual 10 m sensor with reduced transect dispersion",
    },
}


def perturb_widths(
    frame: pd.DataFrame,
    rng: np.random.Generator,
    pixel_size_m: float,
    spatial_dispersion_scale: float,
) -> np.ndarray:
    quantisation = rng.uniform(-pixel_size_m / 2.0, pixel_size_m / 2.0, len(frame))
    robust_sigma = (
        frame.width_iqr_m.to_numpy(float)
        / 1.349
        / np.sqrt(frame.valid_transects.to_numpy(float))
        * spatial_dispersion_scale
    )
    spatial = rng.normal(0.0, robust_sigma)
    return np.clip(frame.width_m.to_numpy(float) + quantisation + spatial, 5.0, None)


def run_scenario(
    pairs: pd.DataFrame, scenario: dict, draws: int = MONTE_CARLO_DRAWS
) -> pd.DataFrame:
    rng = np.random.default_rng(RANDOM_SEED + int(scenario["pixel_size_m"] * 10))
    train_mask = pairs.year.eq(2000).to_numpy()
    validation_mask = pairs.year.eq(2001).to_numpy()
    rows = []
    for draw in range(draws):
        perturbed = perturb_widths(
            pairs,
            rng,
            pixel_size_m=float(scenario["pixel_size_m"]),
            spatial_dispersion_scale=float(scenario["spatial_dispersion_scale"]),
        )
        train_width = perturbed[train_mask]
        if len(np.unique(np.round(train_width, 8))) < 2:
            continue
        scale, exponent = fit_power_law(
            train_width, pairs.loc[train_mask, "observed_q_m3s"].to_numpy(float)
        )
        if not np.isfinite(exponent) or exponent <= 0 or exponent > 8:
            continue
        predicted = predict_power_law(perturbed[validation_mask], scale, exponent)
        score = metrics(
            pairs.loc[validation_mask, "observed_q_m3s"].to_numpy(float), predicted
        )
        rows.append(
            {
                "draw": draw,
                "scale": scale,
                "exponent": exponent,
                "validation_nse": score["nse"],
                "validation_rmse_m3s": score["rmse"],
                "validation_pbias_percent": score["pbias"],
            }
        )
    return pd.DataFrame(rows)


def build_ground_request_manifest() -> pd.DataFrame:
    sentinel = pd.read_csv(SENTINEL_PATH, parse_dates=["date"])
    sentinel = sentinel.loc[sentinel.measurement_status.eq("accepted")].copy()
    sentinel = sentinel[["date", "width_m", "width_iqr_m", "valid_transects"]]
    sentinel["source"] = "Sentinel-2"

    swot = pd.read_csv(SWOT_PATH)
    swot["date"] = pd.to_datetime(swot.time_str).dt.tz_convert(None).dt.normalize()
    swot = swot[["date", "wse_u", "width_u", "obs_frac_n", "n_good_nod"]]
    swot["source"] = "SWOT"

    sentinel_dates = set(sentinel.date.dt.normalize())
    swot_dates = set(swot.date.dt.normalize())
    dates = sorted(sentinel_dates | swot_dates)
    rows = []
    for date in dates:
        sources = []
        if date in sentinel_dates:
            sources.append("Sentinel-2")
        if date in swot_dates:
            sources.append("SWOT")
        simultaneous = len(sources) == 2
        rows.append(
            {
                "priority": "P0" if simultaneous else "P1",
                "date": date.date().isoformat(),
                "satellite_sources": "+".join(sources),
                "requested_discharge": "daily mean Q; instantaneous Q near overpass if available",
                "requested_stage": "daily mean H; instantaneous H near overpass if available",
                "requested_hydraulic_metadata": (
                    "rating-curve version; gauging method; cross-section/change note"
                ),
                "acceptable_window": "same day; +/-1 day only with hourly Q/H",
            }
        )
    return pd.DataFrame(rows).sort_values(["priority", "date"])


def summarise_draws(frame: pd.DataFrame, mean_baseline_rmse: float) -> dict:
    return {
        "valid_draws": int(len(frame)),
        "nse_median": float(frame.validation_nse.median()),
        "nse_p05": float(frame.validation_nse.quantile(0.05)),
        "nse_p95": float(frame.validation_nse.quantile(0.95)),
        "rmse_median_m3s": float(frame.validation_rmse_m3s.median()),
        "rmse_p05_m3s": float(frame.validation_rmse_m3s.quantile(0.05)),
        "rmse_p95_m3s": float(frame.validation_rmse_m3s.quantile(0.95)),
        "probability_nse_above_zero": float(frame.validation_nse.gt(0).mean()),
        "probability_beats_mean_baseline_rmse": float(
            frame.validation_rmse_m3s.lt(mean_baseline_rmse).mean()
        ),
        "probability_passes_both": float(
            (
                frame.validation_nse.gt(0)
                & frame.validation_rmse_m3s.lt(mean_baseline_rmse)
            ).mean()
        ),
    }


def main() -> None:
    pairs = load_pairs()
    train = pairs.loc[pairs.year.eq(2000)]
    validation = pairs.loc[pairs.year.eq(2001)]
    mean_baseline_rmse = metrics(
        validation.observed_q_m3s,
        np.full(len(validation), float(train.observed_q_m3s.mean())),
    )["rmse"]
    deterministic_scale, deterministic_exponent = fit_power_law(
        train.width_m, train.observed_q_m3s
    )
    deterministic_score = metrics(
        validation.observed_q_m3s,
        predict_power_law(
            validation.width_m, deterministic_scale, deterministic_exponent
        ),
    )

    all_draws = []
    summaries = {}
    for name, scenario in SCENARIOS.items():
        draws = run_scenario(pairs, scenario)
        draws.insert(0, "scenario", name)
        all_draws.append(draws)
        summaries[name] = {
            **scenario,
            **summarise_draws(draws, mean_baseline_rmse),
        }
    draw_table = pd.concat(all_draws, ignore_index=True)
    manifest = build_ground_request_manifest()

    optimistic_probability = summaries["optimistic_10m"]["probability_passes_both"]
    decision = (
        "prioritise_sub_10m_width_calibration_then_repeat_transfer_test"
        if optimistic_probability >= 0.5
        else "resolution_improvement_alone_is_insufficient_prioritise_stage_and_rating_curve"
    )
    result = {
        "status": "completed_resolution_aware_uncertainty_experiment",
        "protocol": {
            "calibration_year": 2000,
            "temporal_validation_year": 2001,
            "validation_labels_used_only_for_scoring": True,
            "post_validation_tuning": False,
            "monte_carlo_draws_requested_per_scenario": MONTE_CARLO_DRAWS,
            "random_seed": RANDOM_SEED,
            "width_error_model": (
                "uniform half-pixel shoreline error plus robust transect-median error "
                "estimated from width IQR and valid transect count"
            ),
        },
        "pair_counts": {"calibration_2000": int(len(train)), "validation_2001": int(len(validation))},
        "mean_baseline_rmse_m3s": float(mean_baseline_rmse),
        "deterministic_width_only_baseline": {
            "scale": deterministic_scale,
            "exponent": deterministic_exponent,
            **deterministic_score,
        },
        "scenarios": summaries,
        "decision": decision,
        "request_manifest": {
            "unique_dates": int(len(manifest)),
            "p0_simultaneous_dates": int(manifest.priority.eq("P0").sum()),
            "p1_single_sensor_dates": int(manifest.priority.eq("P1").sum()),
        },
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    draw_table.to_csv(OUTPUT / "resolution_uncertainty_monte_carlo_draws.csv", index=False)
    manifest.to_csv(OUTPUT / "byblk_exact_ground_data_request_manifest.csv", index=False)
    (OUTPUT / "resolution_uncertainty_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(10.8, 4.2), dpi=170)
    colors = {"landsat_30m": "#f9844a", "optimistic_10m": "#277da1"}
    for name, frame in draw_table.groupby("scenario"):
        axes[0].hist(
            frame.validation_nse,
            bins=55,
            density=True,
            alpha=0.5,
            color=colors[name],
            label=name,
        )
        axes[1].hist(
            frame.validation_rmse_m3s,
            bins=55,
            density=True,
            alpha=0.5,
            color=colors[name],
            label=name,
        )
    axes[0].axvline(0.0, color="#222222", linestyle="--", linewidth=1.3)
    axes[0].set_xlabel("2001 validation NSE")
    axes[0].set_ylabel("Density")
    axes[0].set_title("Resolution-aware NSE distribution")
    axes[1].axvline(mean_baseline_rmse, color="#222222", linestyle="--", linewidth=1.3)
    axes[1].set_xlabel("2001 validation RMSE (m³/s)")
    axes[1].set_ylabel("Density")
    axes[1].set_title("RMSE versus calibration-mean baseline")
    for axis in axes:
        axis.legend(frameon=False)
        axis.grid(alpha=0.2)
    figure.suptitle("BYBLK river-width resolution uncertainty propagation")
    figure.tight_layout()
    figure.savefig(OUTPUT / "resolution_uncertainty_distributions.png", bbox_inches="tight")
    plt.close(figure)

    landsat = summaries["landsat_30m"]
    optimistic = summaries["optimistic_10m"]
    report = f"""# 自然河道分辨率感知不确定性实验

## 目的

检验30 m Landsat河宽量测误差是否足以解释跨年验证失败，并用一个明确标注为反事实的10 m乐观场景判断“单纯换高分辨率影像”能否解决问题。本实验不生成流量伪标签，2001年Q只用于最终评分。

## 结果

| 场景 | NSE中位数 | NSE>0概率 | RMSE中位数 | 同时通过概率 |
|---|---:|---:|---:|---:|
| 当前确定性七断面模型 | {deterministic_score['nse']:.3f} | — | {deterministic_score['rmse']:.2f} m³/s | 未通过 |
| Landsat 30 m不确定性 | {landsat['nse_median']:.3f} | {landsat['probability_nse_above_zero']:.1%} | {landsat['rmse_median_m3s']:.2f} m³/s | {landsat['probability_passes_both']:.1%} |
| 乐观10 m反事实 | {optimistic['nse_median']:.3f} | {optimistic['probability_nse_above_zero']:.1%} | {optimistic['rmse_median_m3s']:.2f} m³/s | {optimistic['probability_passes_both']:.1%} |

## 决策

`{decision}`

如果10 m乐观场景的同时通过概率仍低于50%，说明提高影像分辨率本身不足以恢复稳定Q；下一优先级应是同日水位H、评级曲线版本和断面变化记录。精确地面数据申请清单已生成，共 {len(manifest)} 个唯一日期，其中卫星同日重合P0日期 {manifest.priority.eq('P0').sum()} 个。
"""
    (OUTPUT / "resolution_uncertainty_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
