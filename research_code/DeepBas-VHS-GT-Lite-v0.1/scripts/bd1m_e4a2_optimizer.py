from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml
from scipy.optimize import minimize

from bd1m_physics_routing_model import (
    RoutingParameters, initialize_steady_state, numba_available, residence_times, route_daily,
    route_daily_fast, substep_count, verify_fast_parity,
)

logger = logging.getLogger("bd1m_e4a2")

MAX_SUBSTEPS = 576
PENALTY = 1.0e30
BOUNDS_R2 = ((1e-12, 30.0), (0.0, 2.0), (-2.0, 2.0), (-2.0, 2.0))
CHECKPOINT_FILENAME = "e4a2_r2_multistart_train_fit_checkpoint.csv"
CONFIG_FILENAME = "e4a2_optimizer_config.yaml"
R2_START_SEEDS = tuple(range(20))
R2_MAXFEV = 500
R2_OPTIMIZER = "scipy.optimize.minimize(method=Nelder-Mead)"
TRAIN_OBJECTIVE = "train RMSE only, 1978-01-01..1981-12-31"
CHECKPOINT_COLUMNS = (
    "start_id", "seed", "tau0_days", "a", "b", "c", "train_RMSE",
    "required_substeps", "numerically_admissible", "converged", "function_evaluations",
)


@dataclass(frozen=True)
class FitResult:
    params: tuple[float, ...]
    train_rmse: float
    required_substeps: int
    numerically_admissible: bool
    converged: bool
    function_evaluations: int


def tau_r2(nodes: pd.DataFrame, values: tuple[float, ...]) -> np.ndarray:
    tau0, a, b, c = values
    return residence_times(nodes, RoutingParameters(tau0, a, b, c))


def _validate_training(inflow: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.asarray(inflow, dtype=float), np.asarray(target, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) == 0:
        raise ValueError("train inflow and target must be nonempty aligned vectors")
    if not np.isfinite(x).all() or not np.isfinite(y).all() or (x < 0).any():
        raise ValueError("train data must be finite and inflow nonnegative")
    return x, y


Router = Callable[..., tuple[np.ndarray, np.ndarray, np.ndarray]]

_FAST_PARITY_VERIFIED = False
_PROGRESS_EVERY_EVALUATIONS = 10


def validate_resume_protocol(checkpoint_dir: Path | str) -> None:
    """Require the on-disk protocol to match the frozen E4A2 R2 definition."""
    config_path = Path(checkpoint_dir) / CONFIG_FILENAME
    if not config_path.is_file():
        raise ValueError(f"Cannot resume without frozen config: {config_path}")
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot read frozen E4A2 config: {config_path}") from exc
    if not isinstance(config, dict) or not isinstance(config.get("r2"), dict):
        raise ValueError("Frozen E4A2 config is missing the r2 section")

    r2 = config["r2"]
    checks = {
        "optimizer": config.get("optimizer") == R2_OPTIMIZER,
        "bounds": r2.get("bounds") == [list(bound) for bound in BOUNDS_R2],
        "maxfev": r2.get("maxfev") == R2_MAXFEV,
        "MAX_SUBSTEPS": config.get("numerical_gate_max_substeps") == MAX_SUBSTEPS,
        "train_period": config.get("objective") == TRAIN_OBJECTIVE,
        "start_seeds": r2.get("start_seeds") == list(R2_START_SEEDS),
    }
    mismatches = [name for name, matches in checks.items() if not matches]
    if mismatches:
        raise ValueError(f"E4A2 protocol mismatch; resume forbidden: {', '.join(mismatches)}")


def _strict_integer_column(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all() or not np.equal(values, np.floor(values)).all():
        raise ValueError(f"Checkpoint column {column} must contain finite integers")
    return values.astype(int)


def _strict_boolean(value: object, column: str) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
        return value.strip().lower() == "true"
    raise ValueError(f"Checkpoint column {column} must contain booleans")


def _load_checkpoint(checkpoint_path: Path) -> list[FitResult]:
    try:
        frame = pd.read_csv(checkpoint_path, float_precision="round_trip")
    except Exception as exc:
        raise ValueError(f"Cannot read R2 checkpoint: {checkpoint_path}") from exc
    missing = [column for column in CHECKPOINT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Malformed R2 checkpoint; missing fields: {missing}")
    if len(frame) > len(R2_START_SEEDS):
        raise ValueError("Malformed R2 checkpoint; more than 20 starts")

    start_ids = _strict_integer_column(frame, "start_id")
    seeds = _strict_integer_column(frame, "seed")
    expected = np.arange(len(frame), dtype=int)
    if len(np.unique(start_ids)) != len(start_ids) or len(np.unique(seeds)) != len(seeds):
        raise ValueError("Malformed R2 checkpoint; duplicate start_id or seed")
    if not np.array_equal(start_ids, expected):
        raise ValueError("Malformed R2 checkpoint; start_id must be continuous from 0")
    if not np.array_equal(seeds, start_ids):
        raise ValueError("Malformed R2 checkpoint; seed must equal start_id")
    if np.any(seeds < 0) or np.any(seeds > 19):
        raise ValueError("Malformed R2 checkpoint; seed must be in 0..19")

    numeric_columns = ("tau0_days", "a", "b", "c", "train_RMSE")
    numeric = {column: pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
               for column in numeric_columns}
    if any(not np.isfinite(values).all() for values in numeric.values()):
        raise ValueError("Malformed R2 checkpoint; fitted parameters and RMSE must be finite")
    required_substeps = _strict_integer_column(frame, "required_substeps")
    function_evaluations = _strict_integer_column(frame, "function_evaluations")
    if np.any(required_substeps < 1) or np.any(function_evaluations < 0):
        raise ValueError("Malformed R2 checkpoint; invalid substeps or evaluation count")

    output = []
    for index, row in frame.iterrows():
        output.append(FitResult(
            (numeric["tau0_days"][index], numeric["a"][index], numeric["b"][index], numeric["c"][index]),
            numeric["train_RMSE"][index], int(required_substeps[index]),
            _strict_boolean(row["numerically_admissible"], "numerically_admissible"),
            _strict_boolean(row["converged"], "converged"), int(function_evaluations[index]),
        ))
    return output


def _checkpoint_rows(results: list[FitResult]) -> list[dict[str, object]]:
    return [{
        "start_id": i, "seed": i, "tau0_days": result.params[0], "a": result.params[1],
        "b": result.params[2], "c": result.params[3], "train_RMSE": result.train_rmse,
        "required_substeps": result.required_substeps,
        "numerically_admissible": result.numerically_admissible, "converged": result.converged,
        "function_evaluations": result.function_evaluations,
    } for i, result in enumerate(results)]


def _write_checkpoint_atomic(checkpoint_path: Path, results: list[FitResult]) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = checkpoint_path.with_suffix(checkpoint_path.suffix + ".tmp")
    pd.DataFrame(_checkpoint_rows(results), columns=CHECKPOINT_COLUMNS).to_csv(
        temporary_path, index=False, float_format="%.17g"
    )
    temporary_path.replace(checkpoint_path)


def select_router() -> tuple[Router, bool]:
    """Return (router, fast_path_ready); fast path only after a parity check passes."""
    global _FAST_PARITY_VERIFIED
    if not numba_available():
        logger.warning("numba unavailable; using reference route_daily")
        return route_daily, False
    if not _FAST_PARITY_VERIFIED:
        rng = np.random.default_rng(0)
        probe_inflow = np.abs(rng.normal(10.0, 3.0, size=30))
        probe_tau = np.linspace(0.2, 5.0, 68)
        probe_steps = substep_count(probe_tau)
        probe_init = initialize_steady_state(float(probe_inflow[0]), probe_tau)
        diffs = verify_fast_parity(probe_inflow, probe_tau, probe_steps, probe_init)
        logger.info("fast-path parity PASS: %s", diffs)
        _FAST_PARITY_VERIFIED = True
    return route_daily_fast, True


def train_objective(nodes: pd.DataFrame, inflow: np.ndarray, target: np.ndarray, tau_days: np.ndarray,
                    router: Router | None = None) -> tuple[float, int, bool]:
    x, y = _validate_training(inflow, target)
    steps = substep_count(tau_days)
    if steps > MAX_SUBSTEPS:
        return PENALTY, steps, False
    route = route_daily if router is None else router
    initial = initialize_steady_state(float(x[0]), tau_days)
    prediction, _, _ = route(x, tau_days, steps, initial)
    return float(np.sqrt(np.mean((prediction - y) ** 2))), steps, True


def fit_r1_train_only(nodes: pd.DataFrame, train_inflow: np.ndarray, train_target: np.ndarray) -> FitResult:
    x, y = _validate_training(train_inflow, train_target)
    evaluations = 0

    def objective(z: np.ndarray) -> float:
        nonlocal evaluations
        evaluations += 1
        tau = np.full(68, float(z[0]))
        value, _, _ = train_objective(nodes, x, y, tau)
        return value

    result = minimize(objective, np.array([2.0]), method="Nelder-Mead", bounds=[(1e-12, 30.0)],
                      options={"xatol": 1e-5, "fatol": 1e-6, "maxfev": 200, "adaptive": False})
    tau = np.full(68, float(result.x[0]))
    score, steps, admissible = train_objective(nodes, x, y, tau)
    return FitResult((float(result.x[0]),), score, steps, admissible, bool(result.success and admissible), evaluations)


def fit_r2_train_only(nodes: pd.DataFrame, train_inflow: np.ndarray, train_target: np.ndarray,
                      checkpoint_dir: Path | str | None = None,
                      router: Router | None = None) -> list[FitResult]:
    x, y = _validate_training(train_inflow, train_target)
    checkpoint_path = Path(checkpoint_dir) / CHECKPOINT_FILENAME if checkpoint_dir is not None else None
    output: list[FitResult] = []
    if checkpoint_path is not None and checkpoint_path.exists():
        validate_resume_protocol(checkpoint_path.parent)
        output = _load_checkpoint(checkpoint_path)
        logger.info("R2 checkpoint validated: %d/20 completed starts", len(output))
        if len(output) == len(R2_START_SEEDS):
            logger.info("R2 checkpoint complete; zero optimizer calls")
            return output

    active_router, fast_ready = (router, router is route_daily_fast) if router is not None else select_router()
    logger.info("R2 multistart: 20 starts, maxfev=500/start, fast_path=%s", fast_ready)
    factors = []
    length = nodes["length_km"].to_numpy(float)
    slope = np.maximum(np.abs(nodes["median_slope_m_per_m"].to_numpy(float)) * 1000.0, 0.01)
    width = nodes["width_m"].to_numpy(float)
    factors = (length / np.median(length), slope / np.median(slope), width / np.median(width))
    best_rmse = min((result.train_rmse for result in output if np.isfinite(result.train_rmse)), default=float("inf"))
    for seed in R2_START_SEEDS[len(output):]:
        rng = np.random.default_rng(seed)
        start = np.array([rng.uniform(5, 25), rng.uniform(0, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)])
        calls = 0
        last_steps = 0
        logger.info("R2 start %d/20", seed + 1)

        def objective(z: np.ndarray) -> float:
            nonlocal calls, last_steps, best_rmse
            calls += 1
            try:
                tau = z[0] * factors[0] ** z[1] * factors[1] ** z[2] * factors[2] ** z[3]
                steps = substep_count(tau)
            except (ValueError, FloatingPointError, OverflowError):
                if calls == 1 or calls % _PROGRESS_EVERY_EVALUATIONS == 0:
                    logger.info(
                        "R2 progress: start %d/20 objective_evaluations=%d "
                        "current_best_train_RMSE=%.6g required_substeps=unavailable",
                        seed + 1, calls, best_rmse,
                    )
                return PENALTY
            last_steps = steps
            if steps > MAX_SUBSTEPS:
                if calls == 1 or calls % _PROGRESS_EVERY_EVALUATIONS == 0:
                    logger.info(
                        "R2 progress: start %d/20 objective_evaluations=%d "
                        "current_best_train_RMSE=%.6g required_substeps=%d",
                        seed + 1, calls, best_rmse, steps,
                    )
                return PENALTY
            value = train_objective(nodes, x, y, tau, router=active_router)[0]
            if np.isfinite(value) and value < best_rmse:
                best_rmse = float(value)
            if calls == 1 or calls % _PROGRESS_EVERY_EVALUATIONS == 0:
                logger.info(
                    "R2 progress: start %d/20 objective_evaluations=%d "
                    "current_best_train_RMSE=%.6g required_substeps=%d",
                    seed + 1, calls, best_rmse, steps,
                )
                sys.stdout.flush()
            return value

        result = minimize(objective, start, method="Nelder-Mead", bounds=BOUNDS_R2,
                          options={"xatol": 1e-4, "fatol": 1e-6, "maxfev": R2_MAXFEV, "adaptive": False})
        params = tuple(float(v) for v in result.x)
        try:
            tau = tau_r2(nodes, params)
            score, steps, admissible = train_objective(nodes, x, y, tau, router=active_router)
        except (ValueError, FloatingPointError, OverflowError):
            score, steps, admissible = PENALTY, MAX_SUBSTEPS + 1, False
        output.append(FitResult(params, score, steps, admissible, bool(result.success and admissible), calls))
        if np.isfinite(score) and score < best_rmse:
            best_rmse = float(score)
        logger.info("R2 start %d/20 complete: evals=%d required_substeps=%d train_RMSE=%.6g best_RMSE=%.6g converged=%s",
                    seed + 1, calls, steps, score, best_rmse, bool(result.success and admissible))
        sys.stdout.flush()
        if checkpoint_path is not None:
            _write_checkpoint_atomic(checkpoint_path, output)
            logger.info("checkpoint written: %s (%d/20 starts)", checkpoint_path, len(output))
    return output
