from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from vhs.quality import evaluate_physical_reference, evaluate_specialist_output
from vhs.router import SafetyEvidence, route_virtual_station_output


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs" / "virtual_station_mainline"
OUTPUT = BASE / "unified_virtual_station_stress_round"
RESERVOIR = BASE / "reservoir_regulation_head_round" / "reservoir_regulation_daily_predictions.csv"
AGRICULTURE = BASE / "agriculture_vhs_integration_round" / "agriculture_vhs_daily_output.csv"
NATURAL = ROOT / "data" / "processed" / "natural_width" / "gnn_inputs" / "byblk_natural_reach_daily_features.csv"
SEED = 20260727
RATIO_BOUNDS = (0.3803267861502814, 4.10469250180117)


@dataclass(frozen=True)
class Scenario:
    name: str
    family: str
    magnitude: float
    expected_response: str


SCENARIOS = [
    Scenario("clean", "clean", 0.0, "nominal routing"),
    Scenario("random_missing_10pct", "random_missing", 0.10, "withhold affected baseline rows"),
    Scenario("random_missing_30pct", "random_missing", 0.30, "withhold affected baseline rows"),
    Scenario("random_missing_50pct", "random_missing", 0.50, "withhold affected baseline rows"),
    Scenario("contiguous_gap_30d", "contiguous_gap", 30.0, "withhold gap rows"),
    Scenario("contiguous_gap_90d", "contiguous_gap", 90.0, "withhold gap rows"),
    Scenario("gaussian_noise_05pct", "gaussian_noise", 0.05, "retain routing; quantify degradation"),
    Scenario("gaussian_noise_15pct", "gaussian_noise", 0.15, "retain routing; quantify degradation"),
    Scenario("gaussian_noise_30pct", "gaussian_noise", 0.30, "reject implausible specialist values"),
    Scenario("specialist_spike_x5", "specialist_spike", 5.0, "reject specialist and fall back"),
    Scenario("specialist_negative", "specialist_negative", -1.0, "reject specialist and fall back"),
    Scenario("baseline_spike_x5", "baseline_spike", 5.0, "withhold implausible physical reference"),
]


def nse(observed: np.ndarray, predicted: np.ndarray) -> float:
    mask = np.isfinite(observed) & np.isfinite(predicted)
    if mask.sum() < 2:
        return float("nan")
    denominator = np.sum((observed[mask] - np.mean(observed[mask])) ** 2)
    if denominator <= 0:
        return float("nan")
    return float(1.0 - np.sum((observed[mask] - predicted[mask]) ** 2) / denominator)


def rmse(observed: np.ndarray, predicted: np.ndarray) -> float:
    mask = np.isfinite(observed) & np.isfinite(predicted)
    if mask.sum() == 0:
        return float("nan")
    return float(np.sqrt(np.mean((observed[mask] - predicted[mask]) ** 2)))


def deterministic_mask(n: int, fraction: float, salt: int) -> np.ndarray:
    rng = np.random.default_rng(SEED + salt)
    mask = np.zeros(n, dtype=bool)
    count = max(1, int(round(n * fraction)))
    mask[rng.choice(n, size=count, replace=False)] = True
    return mask


def contiguous_mask(n: int, days: int, salt: int) -> np.ndarray:
    rng = np.random.default_rng(SEED + salt)
    length = min(days, n)
    start = int(rng.integers(0, max(n - length + 1, 1)))
    mask = np.zeros(n, dtype=bool)
    mask[start : start + length] = True
    return mask


def perturb_pair(
    baseline: np.ndarray,
    specialist: np.ndarray,
    scenario: Scenario,
    salt: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    baseline = baseline.astype(float).copy()
    specialist = specialist.astype(float).copy()
    attacked = np.zeros(len(baseline), dtype=bool)
    if scenario.family == "random_missing":
        attacked = deterministic_mask(len(baseline), scenario.magnitude, salt)
        baseline[attacked] = np.nan
        specialist[attacked] = np.nan
    elif scenario.family == "contiguous_gap":
        attacked = contiguous_mask(len(baseline), int(scenario.magnitude), salt)
        baseline[attacked] = np.nan
        specialist[attacked] = np.nan
    elif scenario.family == "gaussian_noise":
        rng = np.random.default_rng(SEED + salt)
        baseline *= 1.0 + rng.normal(0.0, scenario.magnitude, len(baseline))
        specialist *= 1.0 + rng.normal(0.0, scenario.magnitude, len(specialist))
        attacked[:] = True
    elif scenario.family == "specialist_spike":
        attacked = deterministic_mask(len(baseline), 0.05, salt)
        specialist[attacked] *= scenario.magnitude
    elif scenario.family == "specialist_negative":
        attacked = deterministic_mask(len(baseline), 0.05, salt)
        specialist[attacked] = -np.abs(specialist[attacked]) - 1.0
    elif scenario.family == "baseline_spike":
        threshold = np.nanquantile(baseline, 0.95)
        candidates = np.flatnonzero(baseline >= threshold)
        attacked[candidates] = True
        baseline[attacked] *= scenario.magnitude
    return baseline, specialist, attacked


def route_reservoir(frame: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    baseline_clean = frame.physical_q_m3s.to_numpy(float)
    specialist_clean = frame.bounded_regulation_q_m3s.to_numpy(float)
    baseline, specialist, attacked = perturb_pair(baseline_clean, specialist_clean, scenario, 11)
    baseline_cap = float(np.nanmax(baseline_clean) * 1.01)
    specialist_cap = float(np.nanmax(specialist_clean) * 1.01)
    records = []
    for index, (bq, sq) in enumerate(zip(baseline, specialist)):
        baseline_decision = evaluate_physical_reference(
            bq,
            upper_envelope_m3s=baseline_cap,
        )
        specialist_decision = evaluate_specialist_output(
            sq,
            bq if baseline_decision.accepted else None,
            specialist_upper_envelope_m3s=specialist_cap,
            ratio_lower=RATIO_BOUNDS[0],
            ratio_upper=RATIO_BOUNDS[1],
        )
        evidence = SafetyEvidence(
            required_inputs_available=baseline_decision.accepted,
            physical_reference_available=baseline_decision.accepted,
            specialist_validated=specialist_decision.accepted,
            specialist_authorized=specialist_decision.accepted,
            scope="stress_test_historically_gauged_gap_reconstruction",
        )
        routed = route_virtual_station_output(
            bq if baseline_decision.accepted else None,
            sq if specialist_decision.accepted else None,
            evidence,
            "physical_area_routed_reference",
            "bounded_reservoir_regulation_head",
        )
        records.append(
            {
                "date": frame.date.iloc[index],
                "observed_q_m3s": frame.observed_q_m3s.iloc[index],
                "clean_output_q_m3s": specialist_clean[index],
                "perturbed_baseline_q_m3s": bq,
                "perturbed_specialist_q_m3s": sq,
                "point_q_m3s": routed.point_q_m3s,
                "output_status": routed.output_status,
                "attacked": attacked[index],
                "quality_rejected": baseline_decision.rejected or specialist_decision.rejected,
            }
        )
    return pd.DataFrame(records)


def route_agriculture(frame: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    baseline_clean = frame.agri_endpoint_geometric_q.to_numpy(float)
    specialist_clean = frame.vhs_agriculture_head_q.to_numpy(float)
    baseline, specialist, attacked = perturb_pair(baseline_clean, specialist_clean, scenario, 29)
    baseline_cap = float(np.nanmax(baseline_clean) * 1.01)
    records = []
    for index, (bq, sq) in enumerate(zip(baseline, specialist)):
        baseline_decision = evaluate_physical_reference(
            bq,
            upper_envelope_m3s=baseline_cap,
        )
        evidence = SafetyEvidence(
            required_inputs_available=baseline_decision.accepted,
            physical_reference_available=baseline_decision.accepted,
            specialist_validated=False,
            specialist_authorized=False,
            scope="stress_test_strict_endpoint_baseline",
        )
        routed = route_virtual_station_output(
            bq if baseline_decision.accepted else None,
            sq,
            evidence,
            "strict_geometric_endpoint_baseline",
            "agriculture_storage_return_head",
        )
        records.append(
            {
                "date": frame.date.iloc[index],
                "observed_q_m3s": frame.XQM.iloc[index],
                "clean_output_q_m3s": baseline_clean[index],
                "perturbed_baseline_q_m3s": bq,
                "perturbed_specialist_q_m3s": sq,
                "point_q_m3s": routed.point_q_m3s,
                "output_status": routed.output_status,
                "attacked": attacked[index],
                "quality_rejected": baseline_decision.rejected,
            }
        )
    return pd.DataFrame(records)


def route_natural(frame: pd.DataFrame, scenario: Scenario) -> pd.DataFrame:
    observed = frame.any_satellite_observation_mask.eq(1).to_numpy()
    attacked = np.zeros(len(frame), dtype=bool)
    available = observed.copy()
    if scenario.family == "random_missing":
        candidates = np.flatnonzero(observed)
        local = deterministic_mask(len(candidates), scenario.magnitude, 41)
        attacked[candidates[local]] = True
        available[attacked] = False
    elif scenario.family == "contiguous_gap":
        attacked = contiguous_mask(len(frame), int(scenario.magnitude), 41)
        available[attacked] = False
    elif scenario.family in {"gaussian_noise", "specialist_spike", "specialist_negative", "baseline_spike"}:
        attacked = observed.copy()
    records = []
    for index in range(len(frame)):
        evidence = SafetyEvidence(False, False, False, False, "satellite_geometry_only")
        routed = route_virtual_station_output(None, None, evidence, "no_rating_baseline", "natural_width_head")
        records.append(
            {
                "date": frame.date.iloc[index],
                "observed_q_m3s": np.nan,
                "clean_output_q_m3s": np.nan,
                "perturbed_baseline_q_m3s": np.nan,
                "perturbed_specialist_q_m3s": np.nan,
                "point_q_m3s": routed.point_q_m3s,
                "output_status": routed.output_status,
                "attacked": attacked[index],
                "quality_rejected": True,
                "geometry_available": available[index],
            }
        )
    return pd.DataFrame(records)


def summarize(regime: str, scenario: Scenario, result: pd.DataFrame) -> dict:
    status_counts = result.output_status.value_counts()
    attacked = result.attacked.to_numpy(bool)
    output = result.point_q_m3s.to_numpy(float)
    clean = result.clean_output_q_m3s.to_numpy(float)
    observed = result.observed_q_m3s.to_numpy(float)
    attacked_count = int(attacked.sum())
    unsafe_specialist_leak = 0
    if scenario.family in {"specialist_spike", "specialist_negative"} and attacked_count:
        leak_mask = (
            np.isfinite(output[attacked])
            & np.isfinite(result.perturbed_specialist_q_m3s.to_numpy(float)[attacked])
            & np.isclose(
                output[attacked],
                result.perturbed_specialist_q_m3s.to_numpy(float)[attacked],
                equal_nan=False,
            )
        )
        unsafe_specialist_leak = int(leak_mask.sum())
    attacked_safe = 1.0
    if attacked_count:
        if scenario.family in {"random_missing", "contiguous_gap", "baseline_spike"}:
            attacked_safe = float(np.mean(~np.isfinite(output[attacked])))
        elif scenario.family in {"specialist_spike", "specialist_negative"}:
            attacked_safe = float(1.0 - unsafe_specialist_leak / attacked_count)
    finite = np.isfinite(output)
    return {
        "regime": regime,
        "scenario": scenario.name,
        "family": scenario.family,
        "rows": int(len(result)),
        "attacked_rows": attacked_count,
        "authorized_rows": int(status_counts.get("specialist_output_authorized", 0)),
        "fallback_rows": int(status_counts.get("physical_baseline_fallback", 0)),
        "withheld_rows": int(status_counts.get("withheld_insufficient_evidence", 0) + status_counts.get("withheld_missing_baseline", 0)),
        "negative_output_rows": int(np.sum(output[finite] < 0)),
        "finite_output_rate": float(np.mean(finite)),
        "attacked_rows_safe_response_rate": attacked_safe,
        "unsafe_specialist_leak_rows": unsafe_specialist_leak,
        "rmse_vs_observed": rmse(observed, output),
        "nse_vs_observed": nse(observed, output),
        "rmse_vs_clean_output": rmse(clean, output),
    }


def make_figure(summary: pd.DataFrame) -> None:
    selected = summary.loc[
        summary.scenario.isin(
            ["clean", "random_missing_30pct", "gaussian_noise_30pct", "specialist_spike_x5", "baseline_spike_x5"]
        )
    ].copy()
    scenario_order = ["clean", "random_missing_30pct", "gaussian_noise_30pct", "specialist_spike_x5", "baseline_spike_x5"]
    regime_order = ["natural", "reservoir", "agriculture"]
    canvas = Image.new("RGB", (1600, 1450), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        title_font = ImageFont.truetype("arial.ttf", 36)
        label_font = ImageFont.truetype("arial.ttf", 23)
        small_font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        title_font = label_font = small_font = ImageFont.load_default()
    colors = {"natural": "#2CA25F", "reservoir": "#2E74B5", "agriculture": "#F28E2B"}
    draw.text((70, 40), "Unified virtual-station stress audit", fill="#1F4D78", font=title_font)
    draw.text((70, 100), "Safe response rate for attacked rows", fill="#222222", font=label_font)
    left, top, bar_width, row_gap = 330, 155, 1050, 34
    row_index = 0
    for scenario_name in scenario_order:
        draw.text((70, top + row_index * row_gap), scenario_name, fill="#333333", font=small_font)
        row_index += 1
        for regime in regime_order:
            value = float(
                selected.loc[
                    selected.scenario.eq(scenario_name) & selected.regime.eq(regime),
                    "attacked_rows_safe_response_rate",
                ].iloc[0]
            )
            y = top + row_index * row_gap
            draw.text((95, y), regime, fill=colors[regime], font=small_font)
            draw.rectangle((left, y + 4, left + bar_width, y + 28), fill="#EDF1F5")
            draw.rectangle((left, y + 4, left + int(bar_width * value), y + 28), fill=colors[regime])
            draw.text((left + bar_width + 18, y), f"{value:.3f}", fill="#222222", font=small_font)
            row_index += 1
        row_index += 1
    divider_y = 1080
    draw.line((70, divider_y, 1530, divider_y), fill="#B8C2CC", width=2)
    draw.text((70, divider_y + 30), "RMSE against observations (m3/s)", fill="#222222", font=label_font)
    reservoir = summary.loc[summary.regime.eq("reservoir")].set_index("scenario").reindex(scenario_order)
    agriculture = summary.loc[summary.regime.eq("agriculture")].set_index("scenario").reindex(scenario_order)
    headers = ["scenario", "reservoir", "agriculture"]
    x_positions = [70, 850, 1180]
    for x, header in zip(x_positions, headers):
        draw.text((x, divider_y + 85), header, fill="#1F4D78", font=small_font)
    for idx, scenario_name in enumerate(scenario_order):
        y = divider_y + 125 + idx * 29
        draw.text((70, y), scenario_name, fill="#333333", font=small_font)
        draw.text((850, y), f"{reservoir.loc[scenario_name, 'rmse_vs_observed']:.2f}", fill=colors["reservoir"], font=small_font)
        draw.text((1180, y), f"{agriculture.loc[scenario_name, 'rmse_vs_observed']:.2f}", fill=colors["agriculture"], font=small_font)
    canvas.save(OUTPUT / "unified_stress_diagnostics.png")


def write_report(summary: pd.DataFrame, manifest: dict) -> None:
    key = summary.loc[
        summary.scenario.isin(["clean", "random_missing_30pct", "gaussian_noise_30pct", "specialist_spike_x5", "baseline_spike_x5"])
    ]
    lines = [
        "# 统一虚拟水文站压力测试与消融实验",
        "",
        f"- 随机种子：`{SEED}`",
        f"- 情景数：{len(SCENARIOS)}；情景—制度组合：{len(summary)}",
        f"- 负流量输出：{int(summary.negative_output_rows.sum())}",
        f"- 专家异常泄漏：{int(summary.unsafe_specialist_leak_rows.sum())}",
        "",
        "## 核心结论",
        "",
        "1. 自然河道在所有扰动下均保持 Q 暂缓，未因几何噪声或异常值越过监督证据门槛。",
        "2. 水库专家尖峰与负值被释放比/幅值质量门拒绝，并回退物理参考；物理参考缺失或尖峰时主动暂缓。",
        "3. 农业专家始终未授权，因此专家异常不会进入最终点流量；端点基线缺失或极端异常时主动暂缓。",
        "4. 30% 高斯噪声会降低水库和农业点预测精度，但不产生负流量；噪声本身仍需通过数据质量标记传递给下游。",
        "",
        "## 关键结果",
        "",
        "|制度|扰动|授权|回退|暂缓|受攻击行安全响应率|RMSE 对观测|",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in key.itertuples(index=False):
        rmse_text = "NA" if not np.isfinite(row.rmse_vs_observed) else f"{row.rmse_vs_observed:.2f}"
        lines.append(
            f"|{row.regime}|{row.scenario}|{row.authorized_rows}|{row.fallback_rows}|{row.withheld_rows}|{row.attacked_rows_safe_response_rate:.3f}|{rmse_text}|"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "压力测试证明的是路由器在预设故障模型下能够安全拒绝或回退，不等于模型在新流域上完成外部验证。自然河道仍需同期 Q/H；水库仍限于历史有测站缺测重建；农业循环仍不能宣称因果修正。",
            "",
            "## 输出",
            "",
            "- `stress_summary.csv`：36 个情景—制度汇总。",
            "- `stress_detailed_outputs.csv`：全部逐日扰动与路由结果。",
            "- `stress_manifest.json`：协议、阈值、断言与结论。",
            "- `unified_stress_diagnostics.png`：门控安全率和精度退化图。",
        ]
    )
    (OUTPUT / "unified_stress_report_zh.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    reservoir = pd.read_csv(RESERVOIR, parse_dates=["date"])
    agriculture = pd.read_csv(AGRICULTURE, parse_dates=["date"])
    natural = pd.read_csv(NATURAL, parse_dates=["date"])
    summaries = []
    details = []
    for scenario_index, scenario in enumerate(SCENARIOS):
        outputs = {
            "natural": route_natural(natural, scenario),
            "reservoir": route_reservoir(reservoir, scenario),
            "agriculture": route_agriculture(agriculture, scenario),
        }
        for regime, result in outputs.items():
            result.insert(0, "regime", regime)
            result.insert(1, "scenario", scenario.name)
            details.append(result)
            summaries.append(summarize(regime, scenario, result))

    summary = pd.DataFrame(summaries)
    detailed = pd.concat(details, ignore_index=True)
    summary.to_csv(OUTPUT / "stress_summary.csv", index=False, encoding="utf-8-sig")
    detailed.to_csv(OUTPUT / "stress_detailed_outputs.csv", index=False, encoding="utf-8-sig")

    assertions = {
        "no_negative_output": bool(summary.negative_output_rows.sum() == 0),
        "no_specialist_attack_leak": bool(summary.unsafe_specialist_leak_rows.sum() == 0),
        "natural_always_withheld": bool(
            (summary.loc[summary.regime.eq("natural"), "withheld_rows"] == len(natural)).all()
        ),
        "clean_reservoir_authorized": bool(
            summary.loc[
                summary.regime.eq("reservoir") & summary.scenario.eq("clean"), "authorized_rows"
            ].iloc[0]
            == len(reservoir)
        ),
        "clean_agriculture_fallback": bool(
            summary.loc[
                summary.regime.eq("agriculture") & summary.scenario.eq("clean"), "fallback_rows"
            ].iloc[0]
            == len(agriculture)
        ),
        "all_discrete_attacks_safely_contained": bool(
            summary.loc[
                summary.family.isin(
                    ["random_missing", "contiguous_gap", "specialist_spike", "specialist_negative", "baseline_spike"]
                ),
                "attacked_rows_safe_response_rate",
            ].ge(0.999999).all()
        ),
    }
    manifest = {
        "status": "completed_unified_virtual_station_stress_audit",
        "seed": SEED,
        "scenarios": [asdict(item) for item in SCENARIOS],
        "quality_policy": {
            "reservoir_release_ratio_bounds": list(RATIO_BOUNDS),
            "baseline_global_cap": "1.01 times the accepted historical-envelope maximum",
            "specialist_global_cap": "1.01 times the accepted historical-envelope maximum",
            "negative_values_rejected": True,
            "missing_physical_reference_withheld": True,
        },
        "assertions": assertions,
        "all_assertions_passed": bool(all(assertions.values())),
        "rows": int(len(detailed)),
        "summary_rows": int(len(summary)),
        "decision": (
            "The three-regime safety router contains all discrete missingness and outlier attacks under the declared quality policy. "
            "Natural discharge remains withheld, reservoir specialist anomalies fall back to the physical reference, and agriculture specialist anomalies remain isolated."
        ),
    }
    if not manifest["all_assertions_passed"]:
        raise AssertionError(json.dumps(assertions, indent=2))
    (OUTPUT / "stress_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    make_figure(summary)
    write_report(summary, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
