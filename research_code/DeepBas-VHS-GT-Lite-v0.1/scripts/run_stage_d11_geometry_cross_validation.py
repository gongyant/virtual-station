from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/diagnosis_2005_snapshot/stage_d11_geometry_cross_validation"
PROTOCOL = OUT / "protocol_frozen.json"
VARIABLES = ("area_m2", "width_m", "mean_depth_m")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assign_regime(month: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(month.between(4, 10), "open_water", "cold_season"),
        index=month.index,
    )


def interpolate_geometry(reference: pd.DataFrame, query: np.ndarray) -> pd.DataFrame:
    """Interpolate only measured geometry, without extrapolating stage range."""

    grouped = (
        reference.loc[:, ["stage_m", *VARIABLES]]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .groupby("stage_m", as_index=False)
        .mean(numeric_only=True)
        .sort_values("stage_m")
    )
    if len(grouped) < 2:
        raise ValueError("at least two distinct training stages are required")
    stage = grouped.stage_m.to_numpy(float)
    query = np.asarray(query, dtype=float)
    inside = np.isfinite(query) & (query >= stage.min()) & (query <= stage.max())
    result = pd.DataFrame(index=np.arange(len(query)))
    for variable in VARIABLES:
        values = np.full(len(query), np.nan, dtype=float)
        values[inside] = np.interp(
            query[inside], stage, grouped[variable].to_numpy(float)
        )
        result[variable] = values
    result["inside_domain"] = inside
    return result


def predict(reference: pd.DataFrame, held: pd.DataFrame) -> pd.DataFrame:
    return interpolate_geometry(reference, held.stage_m.to_numpy(float))


def metric_rows(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scope, subset in [
        ("overall", predictions),
        ("cold_season", predictions.loc[predictions.regime.eq("cold_season")]),
        ("open_water", predictions.loc[predictions.regime.eq("open_water")]),
    ]:
        common = subset.loc[subset.common_support]
        for variable in VARIABLES:
            observed = common[variable].to_numpy(float)
            for model in ("M0_global", "M1_regime"):
                estimated = common[f"{model}_{variable}"].to_numpy(float)
                error = estimated - observed
                rows.append(
                    {
                        "scope": scope,
                        "variable": variable,
                        "model": model,
                        "total_rows": len(subset),
                        "common_rows": len(common),
                        "common_support_coverage": len(common) / len(subset),
                        "mae": float(np.mean(np.abs(error))),
                        "rmse": float(np.sqrt(np.mean(error**2))),
                        "bias": float(np.mean(error)),
                    }
                )
    return pd.DataFrame(rows)


def month_cluster_bootstrap(predictions: pd.DataFrame) -> dict[str, float | int]:
    common = predictions.loc[predictions.common_support].copy()
    common["global_abs_error"] = (
        common.M0_global_area_m2 - common.area_m2
    ).abs()
    common["regime_abs_error"] = (
        common.M1_regime_area_m2 - common.area_m2
    ).abs()
    months = np.sort(common.held_month.unique())
    rng = np.random.default_rng(20260828)
    improvements = []
    for _ in range(5000):
        sampled = rng.choice(months, size=len(months), replace=True)
        pieces = [common.loc[common.held_month.eq(month)] for month in sampled]
        boot = pd.concat(pieces, ignore_index=True)
        global_mae = boot.global_abs_error.mean()
        improvements.append((global_mae - boot.regime_abs_error.mean()) / global_mae)
    lower, median, upper = np.quantile(improvements, [0.025, 0.5, 0.975])
    return {
        "seed": 20260828,
        "resamples": 5000,
        "month_clusters": int(len(months)),
        "area_mae_relative_improvement_ci_2_5": float(lower),
        "area_mae_relative_improvement_median": float(median),
        "area_mae_relative_improvement_ci_97_5": float(upper),
    }


def main() -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    source = ROOT / protocol["source"]["path"]
    if sha256(source) != protocol["source"]["sha256"]:
        raise RuntimeError("D11 source hash differs from frozen protocol")
    data = pd.read_csv(source, dtype={"station_id": str}, parse_dates=["date"])
    data.station_id = data.station_id.str.zfill(8)
    data = data.loc[data.station_id.eq(protocol["source"]["station_id"])].copy()
    data["month"] = data.date.dt.month
    data["regime"] = assign_regime(data.month)
    data = data.sort_values(["date", "stage_m"]).reset_index(drop=True)

    folds = []
    for held_month in sorted(data.month.unique()):
        held = data.loc[data.month.eq(held_month)].copy()
        training = data.loc[~data.month.eq(held_month)].copy()
        global_prediction = predict(training, held)
        regime_prediction = predict(
            training.loc[training.regime.eq(held.regime.iloc[0])], held
        )
        fold = held[["date", "month", "regime", "stage_m", *VARIABLES]].copy()
        fold["held_month"] = held_month
        for model, estimated in [
            ("M0_global", global_prediction),
            ("M1_regime", regime_prediction),
        ]:
            for variable in VARIABLES:
                fold[f"{model}_{variable}"] = estimated[variable].to_numpy(float)
            fold[f"{model}_inside_domain"] = estimated["inside_domain"].to_numpy(bool)
        fold["common_support"] = (
            fold.M0_global_inside_domain & fold.M1_regime_inside_domain
        )
        folds.append(fold)
    predictions = pd.concat(folds, ignore_index=True)
    metrics = metric_rows(predictions)
    fold_coverage = (
        predictions.groupby(["held_month", "regime"], as_index=False)
        .agg(
            rows=("date", "size"),
            global_inside_rows=("M0_global_inside_domain", "sum"),
            regime_inside_rows=("M1_regime_inside_domain", "sum"),
            common_support_rows=("common_support", "sum"),
            held_stage_min_m=("stage_m", "min"),
            held_stage_max_m=("stage_m", "max"),
        )
    )
    indexed = metrics.set_index(["scope", "variable", "model"])
    global_area = indexed.loc[("overall", "area_m2", "M0_global")]
    regime_area = indexed.loc[("overall", "area_m2", "M1_regime")]
    relative_improvement = float(
        (global_area.mae - regime_area.mae) / global_area.mae
    )
    per_regime_nonworse = all(
        indexed.loc[(scope, "area_m2", "M1_regime"), "mae"]
        <= indexed.loc[(scope, "area_m2", "M0_global"), "mae"]
        for scope in ("cold_season", "open_water")
    )
    per_regime_rows = {
        scope: int(indexed.loc[(scope, "area_m2", "M1_regime"), "common_rows"])
        for scope in ("cold_season", "open_water")
    }
    gate = protocol["gate"]
    passed = bool(
        regime_area.common_support_coverage >= gate["common_support_coverage_min"]
        and relative_improvement >= gate["area_mae_relative_improvement_min"]
        and regime_area.rmse < global_area.rmse
        and per_regime_nonworse
        and min(per_regime_rows.values()) >= gate["each_regime_common_rows_min"]
    )
    bootstrap = month_cluster_bootstrap(predictions)
    result = {
        "status": "completed_against_frozen_protocol",
        "protocol_sha256": sha256(PROTOCOL),
        "source_sha256": sha256(source),
        "measurement_rows": int(len(data)),
        "held_months": sorted(int(value) for value in data.month.unique()),
        "common_support_rows": int(predictions.common_support.sum()),
        "common_support_coverage": float(predictions.common_support.mean()),
        "primary_area_mae_global_m2": float(global_area.mae),
        "primary_area_mae_regime_m2": float(regime_area.mae),
        "primary_area_rmse_global_m2": float(global_area.rmse),
        "primary_area_rmse_regime_m2": float(regime_area.rmse),
        "primary_area_mae_relative_improvement": relative_improvement,
        "per_regime_common_rows": per_regime_rows,
        "per_regime_area_mae_nonworse": per_regime_nonworse,
        "gate_passed": passed,
        "gate_failure_reasons": (
            []
            if passed
            else [
                reason
                for condition, reason in [
                    (
                        regime_area.common_support_coverage
                        < gate["common_support_coverage_min"],
                        "common_support_coverage_below_frozen_0.60_threshold",
                    ),
                    (
                        relative_improvement
                        < gate["area_mae_relative_improvement_min"],
                        "area_mae_improvement_below_frozen_0.10_threshold",
                    ),
                    (regime_area.rmse >= global_area.rmse, "area_rmse_not_improved"),
                    (not per_regime_nonworse, "at_least_one_regime_area_mae_worsened"),
                    (
                        min(per_regime_rows.values())
                        < gate["each_regime_common_rows_min"],
                        "at_least_one_regime_has_too_few_common_rows",
                    ),
                ]
                if condition
            ]
        ),
        "decision": (
            "regime_geometry_supported_out_of_month"
            if passed
            else "regime_geometry_not_supported_out_of_month"
        ),
        "scientific_scope": protocol["scientific_scope"],
        "bootstrap_descriptive": bootstrap,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(OUT / "outer_month_predictions.csv", index=False)
    metrics.to_csv(OUT / "outer_month_metrics.csv", index=False)
    fold_coverage.to_csv(OUT / "fold_coverage_audit.csv", index=False)
    (OUT / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report = f"""# 阶段D11：水位—断面关系整月留出验证

D11在运行前冻结协议，按月份整块留出巴音布鲁克实测断面；被留出月份的任何断面行均不进入查表。比较全年单一水位—断面关系（M0）和固定冷季/开敞水期关系（M1），禁止外推，并只在两模型共同覆盖的样本上评分。

共{len(data)}条实测断面、{data.month.nunique()}个有观测月份；共同覆盖{int(predictions.common_support.sum())}条（{predictions.common_support.mean():.1%}）。面积MAE由M0的{global_area.mae:.3f} m²降至M1的{regime_area.mae:.3f} m²，相对改善{relative_improvement:.1%}；面积RMSE由{global_area.rmse:.3f}降至{regime_area.rmse:.3f} m²。冻结门槛{'通过' if passed else '未通过'}。

本实验直接验证断面面积、宽度和平均水深，不使用日流量标签。但季节假设来自D10B结果，且只有2011年24条断面，因此仍属于事后确认性诊断，不能替代跨年份或新增现场断面的真正外部验证。
"""
    (OUT / "stage_d11_report_zh.md").write_text(report, encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(metrics.to_string(index=False))


if __name__ == "__main__":
    main()
