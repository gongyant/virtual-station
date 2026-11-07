from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from bd1m_e4a2_optimizer import (
    CHECKPOINT_FILENAME, CONFIG_FILENAME, fit_r1_train_only, fit_r2_train_only,
    validate_resume_protocol,
)
from bd1m_physics_routing_model import ordered_reaches


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stdout,
        force=True,
    )
    parser = argparse.ArgumentParser(description="E4A2 train-only R1/R2 optimizer dry run")
    parser.add_argument("--daily-data", required=True, type=Path, help="CSV containing date,Q_BYBLK,Q_DSK; only 1978-1981 rows are loaded")
    args = parser.parse_args()
    exp = ROOT / "outputs/vhs_bd1m/experiments"
    exp.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.daily_data, parse_dates=["date"])
    required = {"date", "Q_BYBLK", "Q_DSK"}
    if not required.issubset(df.columns):
        raise ValueError(f"Input must include {sorted(required)}")
    train = df.loc[df.date.between("1978-01-01", "1981-12-31")].sort_values("date")
    if len(train) != 1461:
        raise ValueError(f"Expected 1461 contiguous train days, got {len(train)}")
    nodes = pd.read_csv(ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv")
    edges = pd.read_csv(ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_edges.csv")
    nodes = ordered_reaches(nodes, edges)
    x, y = train.Q_BYBLK.to_numpy(float), train.Q_DSK.to_numpy(float)

    config = {
        "protocol": "VHS-BD1M-PHASE-E4A2-OPTIMIZER-IMPLEMENTATION-AND-TRAIN-ONLY-DRYRUN",
        "optimizer": "scipy.optimize.minimize(method=Nelder-Mead)",
        "r1": {"bounds": [1e-12, 30.0], "xatol": 1e-5, "fatol": 1e-6, "maxfev": 200},
        "r2": {"bounds": [[1e-12, 30.0], [0, 2], [-2, 2], [-2, 2]], "xatol": 1e-4, "fatol": 1e-6, "maxfev": 500, "start_seeds": list(range(20))},
        "objective": "train RMSE only, 1978-01-01..1981-12-31", "numerical_gate_max_substeps": 576,
        "initialization": "once at first train date: tau_i * Q_BYBLK(first_train_day)",
        "validation_test_loaded_or_used": False,
    }
    checkpoint_path = exp / CHECKPOINT_FILENAME
    config_path = exp / CONFIG_FILENAME
    if checkpoint_path.exists():
        validate_resume_protocol(exp)
    else:
        config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    r1 = fit_r1_train_only(nodes, x, y)
    pd.DataFrame([{"tau_global_days": r1.params[0], "train_RMSE": r1.train_rmse, "required_substeps": r1.required_substeps,
                   "numerically_admissible": r1.numerically_admissible, "converged": r1.converged,
                   "function_evaluations": r1.function_evaluations}]).to_csv(exp / "e4a2_r1_train_fit.csv", index=False)
    r2 = fit_r2_train_only(nodes, x, y, checkpoint_dir=exp)
    columns = ["start_id", "seed", "tau0_days", "a", "b", "c", "train_RMSE", "required_substeps", "numerically_admissible", "converged", "function_evaluations"]
    rows = [{"start_id": i, "seed": i, "tau0_days": r.params[0], "a": r.params[1], "b": r.params[2], "c": r.params[3],
             "train_RMSE": r.train_rmse, "required_substeps": r.required_substeps, "numerically_admissible": r.numerically_admissible,
             "converged": r.converged, "function_evaluations": r.function_evaluations} for i, r in enumerate(r2)]
    out = pd.DataFrame(rows, columns=columns)
    out.to_csv(exp / "e4a2_r2_multistart_train_fit.csv", index=False)
    admissible = out[out.numerically_admissible & np.isfinite(out.train_RMSE)]
    best = admissible.train_RMSE.min() if len(admissible) else np.nan
    near = admissible[admissible.train_RMSE <= best * 1.01] if len(admissible) else admissible
    report = ["# E4A2 参数可识别性初审", "", "仅使用1978-1981训练目标；未加载或计算 validation/test 指标。",
              "a/b/c 为拟合参数化指数，不解释为真实物理指数。", "",
              f"- converged: {int(out.converged.sum())}/20", f"- admissible: {int(out.numerically_admissible.sum())}/20",
              f"- train RMSE range (admissible): {admissible.train_RMSE.min() if len(admissible) else 'NA'} 至 {admissible.train_RMSE.max() if len(admissible) else 'NA'}",
              "- near_optimal 定义：train_RMSE <= best_train_RMSE * 1.01", f"- near-optimal starts: {len(near)}"]
    for p in ("tau0_days", "a", "b", "c"):
        vals = admissible[p].to_numpy(float)
        cv = np.std(vals, ddof=1) / abs(np.mean(vals)) if len(vals) > 1 and np.mean(vals) != 0 else np.nan
        near_vals = near[p].to_numpy(float)
        report.append(f"- {p}: range=[{vals.min():.8g}, {vals.max():.8g}] CV={cv:.8g}; near-optimal range=[{near_vals.min():.8g}, {near_vals.max():.8g}]" if len(vals) and len(near_vals) else f"- {p}: insufficient admissible starts")
    report += ["", "近似 objective 与明显不同参数的对应关系需结合上述 near-optimal 参数范围判读。"]
    (exp / "e4a2_parameter_identifiability_report.md").write_text("\n".join(report) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
