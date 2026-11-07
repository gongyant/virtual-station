"""Freeze E4A1 numerical, state-continuity, and optimizer readiness rules."""

from __future__ import annotations

import itertools
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
NODES = ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv"
EXPERIMENT_DIR = ROOT / "outputs/vhs_bd1m/experiments"
FEASIBILITY = EXPERIMENT_DIR / "e4a1_numerical_feasibility.csv"
REPORT = EXPERIMENT_DIR / "e4a1_training_readiness_report.md"
YAML = EXPERIMENT_DIR / "e4a1_optimizer_protocol.yaml"

EPSILON = 0.01
SAFETY = 0.5
MAX_SUBSTEPS_PER_DAY = 576
CANDIDATE_CAPS = (144, 288, 576)
TAU0_VALUES = (0.001, 0.01, 0.1, 1.0, 30.0)
EXPONENT_VALUES = ((0.0, 2.0), (-2.0, 2.0), (-2.0, 2.0))


def main() -> None:
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    nodes = pd.read_csv(NODES)
    length = nodes["length_km"].to_numpy(float)
    slope = np.maximum(np.abs(nodes["median_slope_m_per_m"].to_numpy(float)) * 1000.0, EPSILON)
    width = nodes["width_m"].to_numpy(float)
    medians = np.array([np.median(length), np.median(slope), np.median(width)])
    ratios = np.column_stack([length, slope, width]) / medians

    rows = []
    for cap in CANDIDATE_CAPS:
        for tau0 in TAU0_VALUES:
            for a, b, c in itertools.product(*EXPONENT_VALUES):
                tau = tau0 * ratios[:, 0] ** a * ratios[:, 1] ** b * ratios[:, 2] ** c
                min_tau = float(tau.min())
                required = int(np.ceil(1.0 / (SAFETY * min_tau)))
                rows.append({
                    "max_substeps_per_day": cap,
                    "tau0_days": tau0,
                    "a": a,
                    "b": b,
                    "c": c,
                    "min_tau_days": min_tau,
                    "required_substeps_per_day": required,
                    "numerically_admissible": required <= cap,
                })
    feasibility = pd.DataFrame(rows)
    feasibility.to_csv(FEASIBILITY, index=False)

    threshold_rows = []
    for cap in CANDIDATE_CAPS:
        base_minima = []
        for a, b, c in itertools.product(*EXPONENT_VALUES):
            base = ratios[:, 0] ** a * ratios[:, 1] ** b * ratios[:, 2] ** c
            base_minima.append(float(base.min()))
        worst_base = min(base_minima)
        tau0_threshold = (1.0 / SAFETY) / cap / worst_base
        cost = 68 * 2191 * cap
        threshold_rows.append((cap, worst_base, tau0_threshold, cost))

    yaml = f"""protocol: VHS-BD1M-PHASE-E4A1-TRAINING-READINESS-AUDIT
formal_training_performed: false
max_substeps_per_day: {MAX_SUBSTEPS_PER_DAY}
candidate_substep_caps: [144, 288, 576]
substep_safety_fraction: {SAFETY}
daily_timestep_days: 1.0
stability_rule: dt_over_tau_leq_0.5
slope_transform:
  definition: max(abs(median_slope_m_per_m) * 1000, epsilon_slope_m_per_km)
  epsilon_slope_m_per_km: {EPSILON}
tau_parameterization:
  tau0_days: {{min_exclusive: 0.0, max_inclusive: 30.0}}
  a: {{min_inclusive: 0.0, max_inclusive: 2.0}}
  b: {{min_inclusive: -2.0, max_inclusive: 2.0}}
  c: {{min_inclusive: -2.0, max_inclusive: 2.0}}
initialization:
  rule: one_time_train_start_steady_state
  storage_i_0: tau_i_times_first_train_day_Q_BYBLK
  reinitialize_at_validation: false
  reinitialize_at_test: false
forcing:
  boundary: Q_BYBLK
  basin_met_forcing_in_routing_v1: false
  copy_basin_met_to_reaches: false
splits:
  train: 1978-1981
  validation: 1982
  test: 1983
optimizer:
  objective: train_RMSE_or_equivalent_train_MSE
  validation_used_for_selection: false
  test_used_for_selection: false
  random_seed: 42
  r0: {{parameters: 0, definition: same_day_upstream_transfer}}
  r1: {{parameters: 1, parameter: tau_global_days, bounds: [0.0, 30.0]}}
  r2: {{parameters: 4, parameters_named: [tau0_days, a, b, c], multi_start_count: 20}}
  multi_start_seeds: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
results_role:
  daily_results: METHOD_DEVELOPMENT_ONLY
  final_independent_validation: false
  required_final_boundary: daily_DSK_prediction_to_monthly_aggregation_against_admissible_official_DSK_monthly_Q
"""
    YAML.write_text(yaml, encoding="utf-8")

    costs = "\n".join(
        f"| {cap} | {base:.6g} | {threshold:.6g} days | {cost:,} reach-substeps/day-set |"
        for cap, base, threshold, cost in threshold_rows
    )
    report = f"""# VHS-BD1M Phase E4A1 训练就绪性审计

## 最终状态

- `E4B_NUMERICAL_DOMAIN_FROZEN=true`
- `SPLIT_STATE_CONTINUITY_FROZEN=true`
- `OPTIMIZER_PROTOCOL_FROZEN=true`
- `PARAMETER_IDENTIFIABILITY_AUDIT_READY=true`
- `DAILY_RESULTS_FINAL_VALIDATION_ALLOWED=false`
- `READY_FOR_E4B_TRAINING=false`

本阶段没有训练 R1/R2 正式参数，没有输出正式 test NSE/KGE/RMSE，也没有依据 validation/test 修改结构、范围、objective、substeps、初始化或物理变量。

## A. 数值可行域

审计输入：`{NODES.relative_to(ROOT)}`，真实 68 reach physical features。

冻结规则：

- slope 正值变换：`S_i = max(abs(median_slope_m_per_m) * 1000, epsilon)`；
- `epsilon = {EPSILON} m/km`；
- `dt / tau_i <= {SAFETY}`；
- `required_substeps_per_day = ceil(1 / ({SAFETY} * min_tau_days))`；
- 若 required substeps 超过冻结上限，则 `numerically_admissible=false`，不降低稳定性标准。
- 冻结 `MAX_SUBSTEPS_PER_DAY = {MAX_SUBSTEPS_PER_DAY}`。

| 候选上限 | 最坏指数项 min | tau0 最低阈值（近似） | 68 reach × 2191 日 × 上限的计算量 |
|---:|---:|---:|---:|
{costs}

tau0 的理论范围仍为 `(0, 30]`，但由于 tau0 趋近 0 会使 required substeps 无界，数值门会拒绝这些组合。冻结上限不根据 prediction performance 选择；采用 576 是在候选中保留最大预注册计算预算，同时仍严格执行 `dt/tau <= 0.5`。所有逐组合结果见：`{FEASIBILITY.relative_to(ROOT)}`。

注意：因为 tau0 下界是开区间 0，不能声称整个 `(0,30]` 都可计算；可行域由 numerical gate 明确筛选。

## B. Split state continuity

正式规则冻结为：仅在 1978 训练起点初始化一次：

`Storage_i(0) = tau_i * Q_BYBLK(first_train_day)`

之后连续传播 1978→1979→1980→1981→1982→1983。1982 validation 和 1983 test 开始时不重新初始化。对应日期的 Q_BYBLK 可以推进状态，但 Q_DSK、未来气象和未来 state 不得参与初始化或状态修正。

新增测试 `test_state_continuity_across_splits` 将分段运行与一次性连续运行的状态进行逐步一致性比较。

## C. 参数拟合协议

- R0：same-day upstream transfer，无拟合参数；
- R1：68 reach homogeneous routing，一个共享 tau 全局参数；
- R2：四个共享参数 `tau0, a, b, c`，按照 length/slope/width 参数化 tau_i；
- objective：仅 train RMSE 或等价 train MSE；
- train：1978–1981；validation/test 只评价；
- 不根据 validation/test 选择 objective、范围、substeps、结构或初始化。

## D. Multi-start 与可识别性

R2 预注册 20 个 deterministic starts，seed 为 0–19。每个 start 只记录 train objective、参数、是否收敛和 numerical admissibility。不会只保存一次优化结果。a/b/c 仅作为参数化指数记录，不直接解释为已测量的物理指数；其稳定性与可识别性需由后续审计判断。

配置见：`{YAML.relative_to(ROOT)}`。

## E. 最终验证边界

`DAILY_RESULTS_ROLE = METHOD_DEVELOPMENT_ONLY`。

当前 DSK 日 Q 仍是方法开发标签。论文主验证必须采用：

`predicted daily DSK Q → monthly aggregation → admissible official DSK monthly Q`

在官方月观测尚未最终准入前，不得把 daily NSE/KGE/RMSE 写作最终独立验证结果。

## 测试与范围

新增或更新测试覆盖：

- state continuity across split；
- numerical feasibility gate；
- no DSK target in state propagation；
- deterministic multi-start configuration；
- 既有 mass conservation、graph order、68 reach continuity、positive tau、stability、identical reach、steady-state。

测试通过后才允许进入 E4B；本阶段仍冻结 `READY_FOR_E4B_TRAINING=false`，因为尚未进行正式参数拟合和月尺度准入验证。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(feasibility)} max_substeps={MAX_SUBSTEPS_PER_DAY} protocol_frozen=true")


if __name__ == "__main__":
    main()
