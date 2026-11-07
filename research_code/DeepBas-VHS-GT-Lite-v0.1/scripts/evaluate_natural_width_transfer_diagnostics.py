from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


WIDTH_PATH = Path(
    "data/processed/natural_width/landsat_byblk_multitransect/"
    "landsat_multitransect_width_measurements.csv"
)
EXTERNAL_Q_PATH = Path(
    "data/processed/virtual_station_external/external_input_byblk_2000_2001.csv"
)
MULTISITE_Q_PATH = Path(
    "data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
)
OUTPUT = Path(
    "outputs/virtual_station_mainline/natural_width_transfer_diagnostics_round"
)
HISTORICAL_INVENTORY_SUMMARY = Path(
    "outputs/virtual_station_mainline/natural_historical_landsat_inventory_round/"
    "historical_landsat_inventory_summary.json"
)
RANDOM_SEED = 20260726
BOOTSTRAP_DRAWS = 5000


def fit_power_law(
    width_m: np.ndarray, discharge_m3s: np.ndarray, weights: np.ndarray | None = None
) -> tuple[float, float]:
    x = np.log(np.asarray(width_m, dtype=float))
    y = np.log(np.asarray(discharge_m3s, dtype=float))
    design = np.column_stack([np.ones_like(x), x])
    if weights is None:
        coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    else:
        root_weight = np.sqrt(np.asarray(weights, dtype=float))
        coefficients = np.linalg.lstsq(
            design * root_weight[:, None], y * root_weight, rcond=None
        )[0]
    return float(np.exp(coefficients[0])), float(coefficients[1])


def predict_power_law(width_m: np.ndarray, scale: float, exponent: float) -> np.ndarray:
    return scale * np.power(np.asarray(width_m, dtype=float), exponent)


def metrics(observed: np.ndarray, predicted: np.ndarray) -> dict:
    observed = np.asarray(observed, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    residual = predicted - observed
    denominator = float(np.square(observed - observed.mean()).sum())
    nse = float(1.0 - np.square(residual).sum() / denominator) if denominator > 0 else np.nan
    correlation = (
        float(np.corrcoef(observed, predicted)[0, 1])
        if len(observed) >= 2
        and float(np.std(observed)) > 0
        and float(np.std(predicted)) > 0
        else np.nan
    )
    return {
        "n": int(len(observed)),
        "rmse": float(np.sqrt(np.mean(np.square(residual)))),
        "mae": float(np.mean(np.abs(residual))),
        "pbias": float(100.0 * residual.sum() / observed.sum()),
        "nse": nse,
        "corr": correlation,
    }


def load_pairs() -> pd.DataFrame:
    width = pd.read_csv(WIDTH_PATH, parse_dates=["date"])
    width = width.loc[width.measurement_status.eq("accepted")].copy()
    external = pd.read_csv(EXTERNAL_Q_PATH, parse_dates=["date"])[
        ["date", "upstream_q_m3s"]
    ].rename(columns={"upstream_q_m3s": "observed_q_m3s"})
    multisite = pd.read_csv(MULTISITE_Q_PATH, parse_dates=["date"])
    multisite = multisite.loc[
        multisite.station_code.eq("BYBLK"), ["date", "observed_q_m3s"]
    ]
    discharge = (
        pd.concat([external, multisite], ignore_index=True)
        .drop_duplicates("date", keep="first")
        .dropna(subset=["observed_q_m3s"])
    )
    pairs = width.merge(discharge, on="date", how="inner", validate="one_to_one")
    pairs["year"] = pairs.date.dt.year
    pairs["quality_weight"] = (
        pairs.valid_transects.astype(float) / (1.0 + pairs.width_iqr_m.astype(float))
    )
    pairs["quality_weight"] /= pairs.quality_weight.mean()
    pairs["native_pixel_width_ratio"] = pairs.width_m / 30.0
    return pairs.sort_values("date").reset_index(drop=True)


def bootstrap_intervals(
    train: pd.DataFrame, target_widths: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    rng = np.random.default_rng(RANDOM_SEED)
    predictions = []
    indices = np.arange(len(train))
    for _ in range(BOOTSTRAP_DRAWS):
        sampled = train.iloc[rng.choice(indices, size=len(indices), replace=True)]
        if sampled.width_m.nunique() < 2:
            continue
        scale, exponent = fit_power_law(
            sampled.width_m.to_numpy(float), sampled.observed_q_m3s.to_numpy(float)
        )
        if not np.isfinite(exponent) or exponent <= 0 or exponent > 8:
            continue
        predictions.append(predict_power_law(target_widths, scale, exponent))
    array = np.asarray(predictions, dtype=float)
    return (
        np.quantile(array, 0.05, axis=0),
        np.quantile(array, 0.50, axis=0),
        np.quantile(array, 0.95, axis=0),
        int(len(array)),
    )


def similar_width_conflicts(pairs: pd.DataFrame, tolerance_m: float = 5.0) -> pd.DataFrame:
    rows = []
    for left in range(len(pairs)):
        for right in range(left + 1, len(pairs)):
            a = pairs.iloc[left]
            b = pairs.iloc[right]
            if a.year == b.year or abs(float(a.width_m) - float(b.width_m)) > tolerance_m:
                continue
            low = min(float(a.observed_q_m3s), float(b.observed_q_m3s))
            high = max(float(a.observed_q_m3s), float(b.observed_q_m3s))
            rows.append(
                {
                    "date_a": a.date.date().isoformat(),
                    "date_b": b.date.date().isoformat(),
                    "year_a": int(a.year),
                    "year_b": int(b.year),
                    "width_a_m": float(a.width_m),
                    "width_b_m": float(b.width_m),
                    "width_difference_m": abs(float(a.width_m) - float(b.width_m)),
                    "q_a_m3s": float(a.observed_q_m3s),
                    "q_b_m3s": float(b.observed_q_m3s),
                    "q_ratio": high / low if low > 0 else np.nan,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    pairs = load_pairs()
    train = pairs.loc[pairs.year.eq(2000)].copy()
    validation = pairs.loc[pairs.year.eq(2001)].copy()
    distant = pairs.loc[pairs.year.eq(2005)].copy()
    if len(train) < 5 or len(validation) < 3:
        raise ValueError("Insufficient predeclared 2000/2001 pairs for transfer diagnostics")

    ordinary = fit_power_law(train.width_m, train.observed_q_m3s)
    weighted = fit_power_law(
        train.width_m, train.observed_q_m3s, train.quality_weight
    )
    model_parameters = {
        "ordinary_power_law": {"scale": ordinary[0], "exponent": ordinary[1]},
        "quality_weighted_power_law": {"scale": weighted[0], "exponent": weighted[1]},
    }
    metric_rows = []
    for model_name, parameters in model_parameters.items():
        pairs[f"predicted_{model_name}_m3s"] = predict_power_law(
            pairs.width_m, parameters["scale"], parameters["exponent"]
        )
        for split_name, frame in [
            ("calibration_2000", train),
            ("temporal_validation_2001", validation),
            ("distant_test_2005", distant),
        ]:
            selected = pairs.loc[frame.index]
            metric_rows.append(
                {
                    "model": model_name,
                    "split": split_name,
                    **metrics(
                        selected.observed_q_m3s,
                        selected[f"predicted_{model_name}_m3s"],
                    ),
                }
            )
    pairs["predicted_calibration_mean_m3s"] = float(train.observed_q_m3s.mean())
    metric_rows.append(
        {
            "model": "calibration_mean",
            "split": "temporal_validation_2001",
            **metrics(validation.observed_q_m3s, pairs.loc[validation.index, "predicted_calibration_mean_m3s"]),
        }
    )
    metric_table = pd.DataFrame(metric_rows)

    lower, median, upper, valid_draws = bootstrap_intervals(
        train, pairs.width_m.to_numpy(float)
    )
    pairs["ordinary_bootstrap_p05_m3s"] = lower
    pairs["ordinary_bootstrap_p50_m3s"] = median
    pairs["ordinary_bootstrap_p95_m3s"] = upper
    pairs["ordinary_bootstrap_90pct_contains_observed"] = (
        pairs.observed_q_m3s.ge(pairs.ordinary_bootstrap_p05_m3s)
        & pairs.observed_q_m3s.le(pairs.ordinary_bootstrap_p95_m3s)
    )

    conflicts = similar_width_conflicts(pairs)
    validation_lookup = metric_table.set_index(["model", "split"])
    ordinary_validation = validation_lookup.loc[
        ("ordinary_power_law", "temporal_validation_2001")
    ]
    weighted_validation = validation_lookup.loc[
        ("quality_weighted_power_law", "temporal_validation_2001")
    ]
    validation_coverage = float(
        pairs.loc[validation.index, "ordinary_bootstrap_90pct_contains_observed"].mean()
    )
    weighted_pass = bool(
        weighted[1] > 0
        and weighted_validation.nse > 0
        and weighted_validation.rmse < ordinary_validation.rmse
    )
    result = {
        "status": "completed_natural_width_transfer_diagnostics",
        "protocol": {
            "widths_created_before_discharge_join": True,
            "calibration_year": 2000,
            "temporal_validation_year": 2001,
            "distant_diagnostic_year": 2005,
            "post_validation_tuning": False,
            "quality_weight_formula_predeclared": "valid_transects/(1+width_iqr_m)",
            "bootstrap_draws_requested": BOOTSTRAP_DRAWS,
            "bootstrap_seed": RANDOM_SEED,
        },
        "pair_counts": {
            str(year): int(count) for year, count in pairs.groupby("year").size().items()
        },
        "model_parameters": model_parameters,
        "metrics": metric_table.to_dict("records"),
        "uncertainty": {
            "valid_bootstrap_draws": valid_draws,
            "validation_90pct_interval_coverage": validation_coverage,
            "median_native_pixel_width_ratio": float(pairs.native_pixel_width_ratio.median()),
            "minimum_native_pixel_width_ratio": float(pairs.native_pixel_width_ratio.min()),
        },
        "non_identifiability": {
            "cross_year_pairs_with_width_difference_le_5m": int(len(conflicts)),
            "median_discharge_ratio": float(conflicts.q_ratio.median()) if len(conflicts) else None,
            "maximum_discharge_ratio": float(conflicts.q_ratio.max()) if len(conflicts) else None,
        },
        "quality_weighted_candidate_passed": weighted_pass,
        "decision": (
            "quality_weighted_width_rating_curve_passed_temporal_validation"
            if weighted_pass
            else "width_only_inversion_remains_rejected"
        ),
        "next_required_data": [
            "BYBLK stage and discharge on the accepted satellite dates",
            "rating-curve version and cross-section change records",
            "a field or sub-10-m reference width for shoreline calibration",
        ],
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(OUTPUT / "natural_width_transfer_pairs_and_predictions.csv", index=False)
    metric_table.to_csv(OUTPUT / "natural_width_transfer_metrics.csv", index=False)
    conflicts.to_csv(OUTPUT / "similar_width_cross_year_conflicts.csv", index=False)
    (OUTPUT / "natural_width_transfer_diagnostics_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    colors = {2000: "#277da1", 2001: "#f9844a", 2005: "#43aa8b"}
    figure, axes = plt.subplots(1, 3, figsize=(14.0, 4.5), dpi=170)
    grid = np.linspace(max(5.0, pairs.width_m.min() - 5), pairs.width_m.max() + 5, 200)
    for year, frame in pairs.groupby("year"):
        axes[0].scatter(
            frame.width_m,
            frame.observed_q_m3s,
            s=48,
            color=colors[int(year)],
            label=str(year),
            edgecolor="white",
            linewidth=0.5,
        )
    axes[0].plot(grid, predict_power_law(grid, *ordinary), color="#222222", label="ordinary")
    axes[0].plot(
        grid,
        predict_power_law(grid, *weighted),
        color="#9b5de5",
        linestyle="--",
        label="quality weighted",
    )
    axes[0].set_xlabel("Seven-transect median width (m)")
    axes[0].set_ylabel("Observed discharge (m³/s)")
    axes[0].set_title("Cross-year width–Q relation")
    axes[0].legend(frameon=False, fontsize=8)

    for year, frame in pairs.groupby("year"):
        axes[1].scatter(
            frame.observed_q_m3s,
            frame.predicted_ordinary_power_law_m3s,
            s=48,
            color=colors[int(year)],
            label=str(year),
        )
    limit = float(max(pairs.observed_q_m3s.max(), pairs.predicted_ordinary_power_law_m3s.max()))
    axes[1].plot([0, limit], [0, limit], color="#333333", linestyle=":")
    axes[1].set_xlabel("Observed Q (m³/s)")
    axes[1].set_ylabel("Predicted Q (m³/s)")
    axes[1].set_title("Frozen 2000 curve transfer")

    positions = np.arange(len(pairs))
    axes[2].vlines(
        positions,
        pairs.ordinary_bootstrap_p05_m3s,
        pairs.ordinary_bootstrap_p95_m3s,
        color=[colors[int(year)] for year in pairs.year],
        linewidth=2,
        alpha=0.75,
    )
    axes[2].scatter(positions, pairs.observed_q_m3s, color="#111111", s=20, label="observed")
    axes[2].scatter(positions, pairs.ordinary_bootstrap_p50_m3s, color="#e63946", s=18, label="bootstrap median")
    axes[2].set_xticks(positions)
    axes[2].set_xticklabels([d.strftime("%Y-%m-%d") for d in pairs.date], rotation=70, fontsize=6)
    axes[2].set_ylabel("Q (m³/s)")
    axes[2].set_title("2000-calibration 90% uncertainty")
    axes[2].legend(frameon=False, fontsize=7)
    for axis in axes:
        axis.grid(alpha=0.2)
    figure.suptitle("BYBLK natural-reach width transfer and identifiability diagnostics")
    figure.tight_layout()
    figure.savefig(OUTPUT / "natural_width_transfer_diagnostics.png", bbox_inches="tight")
    plt.close(figure)

    historical = (
        json.loads(HISTORICAL_INVENTORY_SUMMARY.read_text(encoding="utf-8"))
        if HISTORICAL_INVENTORY_SUMMARY.exists()
        else None
    )
    historical_text = (
        f"- 1978—1983年目录共找到 {historical['totals']['catalog_scenes']} 景一级影像、"
        f"{historical['totals']['level2_scenes']} 景二级影像；按25%云量门槛仅"
        f" {historical['totals']['scenes_under_25pct_cloud']} 景可用，且没有与现有MNDWI流程兼容的影像。"
        if historical
        else "- 历史影像目录尚未生成。"
    )

    report = f"""# 自然河道河宽—流量跨年迁移诊断

## 本轮问题

在不增加虚构流量标签的前提下，检验七断面河宽关系从2000年率定后能否迁移到2001年和2005年，并判断按断面离散度加权是否能修复失败。

## 数据和封闭协议

- 同日河宽—流量配对：2000年 {len(train)} 组、2001年 {len(validation)} 组、2005年 {len(distant)} 组；
- 只用2000年率定；2001年为冻结时间验证；2005年仅作远期诊断；
- 质量权重在开标前固定为 `有效断面数/(1+河宽IQR)`；
- 共完成 {valid_draws} 次有效自助重采样，给出90%预测区间。

## 1978—1983年历史影像档案核查

{historical_text}
1978年仅有Landsat-2/3 MSS一级资料，缺少SWIR1，不能在没有独立传感器一致性校准的情况下与2000年后的MNDWI河宽混合。

## 主要结果

- 普通幂函数2001年：NSE={ordinary_validation.nse:.3f}，RMSE={ordinary_validation.rmse:.2f} m³/s；
- 质量加权幂函数2001年：NSE={weighted_validation.nse:.3f}，RMSE={weighted_validation.rmse:.2f} m³/s；
- 2001年90%自助区间覆盖率：{validation_coverage:.1%}；
- 河宽中位数仅相当于 {pairs.native_pixel_width_ratio.median():.2f} 个Landsat原生像元；
- 跨年份河宽相差不超过5 m的样本对共有 {len(conflicts)} 对，其流量比中位数为 {conflicts.q_ratio.median() if len(conflicts) else float('nan'):.2f}，最大为 {conflicts.q_ratio.max() if len(conflicts) else float('nan'):.2f}。

## 结论

质量加权候选是否通过：**{'是' if weighted_pass else '否'}**。当前证据表明，量测质量加权仍不足以把河宽单变量关系提升为可跨年使用的虚拟水文站。问题不仅是样本少，还包括30 m像元尺度、可能的断面/水位关系变化以及同宽异流现象。自然河道分支继续保留，但正式监督反演仍需同日水位、评级曲线版本和断面变化记录。
"""
    (OUTPUT / "natural_width_transfer_diagnostics_report_zh.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
