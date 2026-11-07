from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import bd1m_e4a2_optimizer as opt


def nodes() -> pd.DataFrame:
    return pd.read_csv(ROOT / "outputs/vhs_bd1m/bd1m_reach_graph_nodes.csv")


def write_frozen_config(directory: Path, **overrides) -> None:
    config = {
        "optimizer": opt.R2_OPTIMIZER,
        "r2": {
            "bounds": [list(bound) for bound in opt.BOUNDS_R2],
            "maxfev": opt.R2_MAXFEV,
            "start_seeds": list(opt.R2_START_SEEDS),
        },
        "objective": opt.TRAIN_OBJECTIVE,
        "numerical_gate_max_substeps": opt.MAX_SUBSTEPS,
    }
    config.update(overrides)
    (directory / opt.CONFIG_FILENAME).write_text(yaml.safe_dump(config), encoding="utf-8")


def synthetic_results(count: int) -> list[opt.FitResult]:
    return [
        opt.FitResult((2.0 + seed, 1.0, -0.5, 0.0), 10.0 + seed, 3, True, True, 12 + seed)
        for seed in range(count)
    ]


def deterministic_minimize(calls: list[np.ndarray]):
    def fake(fun, x0, **kwargs):
        point = np.asarray(x0, dtype=float).copy()
        calls.append(point)
        fun(point)
        return SimpleNamespace(x=point, success=True)

    return fake


def test_numerically_inadmissible_rejected_before_route(monkeypatch) -> None:
    called = False

    def fail_route(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("routing must not run")

    monkeypatch.setattr(opt, "route_daily", fail_route)
    tau = np.full(68, 1e-6)
    score, steps, admissible = opt.train_objective(nodes(), np.ones(2), np.ones(2), tau)
    assert not admissible and steps > opt.MAX_SUBSTEPS and score == opt.PENALTY
    assert not called


def test_objective_consumes_only_provided_training_vectors() -> None:
    x, y = np.ones(4), np.ones(4)
    score, _, accepted = opt.train_objective(nodes(), x, y, np.ones(68))
    assert accepted and score == 0
    with np.testing.assert_raises(ValueError):
        opt.train_objective(nodes(), x, np.ones(3), np.ones(68))


def test_r1_is_single_parameter() -> None:
    result = opt.fit_r1_train_only(nodes(), np.ones(2), np.ones(2))
    assert len(result.params) == 1


def test_r2_has_exactly_twenty_deterministic_starts(monkeypatch) -> None:
    class Result:
        x = np.array([2.0, 1.0, -0.5, 0.0])
        success = True

    calls = []

    def fake_minimize(fun, x0, **kwargs):
        calls.append(np.asarray(x0).copy())
        fun(np.asarray(x0))
        return Result()

    monkeypatch.setattr(opt, "minimize", fake_minimize)
    first = opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2))
    second = opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2))
    assert len(first) == len(second) == len(calls) // 2 == 20
    assert all(np.array_equal(a, b) for a, b in zip(calls[:20], calls[20:]))


def test_r2_checkpoints_after_every_completed_start(monkeypatch, tmp_path) -> None:
    class Result:
        x = np.array([2.0, 1.0, -0.5, 0.0])
        success = True

    checkpoint_sizes = []
    real_to_csv = pd.DataFrame.to_csv

    def fake_minimize(fun, x0, **kwargs):
        fun(np.asarray(x0))
        return Result()

    def recording_to_csv(self, path, *args, **kwargs):
        checkpoint_sizes.append(len(self))
        return real_to_csv(self, path, *args, **kwargs)

    monkeypatch.setattr(opt, "minimize", fake_minimize)
    monkeypatch.setattr(pd.DataFrame, "to_csv", recording_to_csv)
    opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path, router=opt.route_daily)
    checkpoint = tmp_path / opt.CHECKPOINT_FILENAME
    assert checkpoint.exists()
    assert checkpoint_sizes == list(range(1, 21))
    assert len(pd.read_csv(checkpoint)) == 20


def test_no_checkpoint_executes_starts_zero_through_nineteen(monkeypatch, tmp_path) -> None:
    calls = []
    monkeypatch.setattr(opt, "minimize", deterministic_minimize(calls))
    results = opt.fit_r2_train_only(
        nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path, router=opt.route_daily
    )
    assert len(results) == 20
    assert len(calls) == 20
    expected = []
    for seed in range(20):
        rng = np.random.default_rng(seed)
        expected.append(np.array([rng.uniform(5, 25), rng.uniform(0, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)]))
    assert all(np.array_equal(actual, wanted) for actual, wanted in zip(calls, expected))


def test_five_row_checkpoint_executes_only_seeds_five_through_nineteen(monkeypatch, tmp_path) -> None:
    write_frozen_config(tmp_path)
    opt._write_checkpoint_atomic(tmp_path / opt.CHECKPOINT_FILENAME, synthetic_results(5))
    calls = []
    monkeypatch.setattr(opt, "minimize", deterministic_minimize(calls))
    results = opt.fit_r2_train_only(
        nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path, router=opt.route_daily
    )
    assert len(results) == 20
    assert len(calls) == 15
    expected = []
    for seed in range(5, 20):
        rng = np.random.default_rng(seed)
        expected.append(np.array([rng.uniform(5, 25), rng.uniform(0, 2), rng.uniform(-2, 2), rng.uniform(-2, 2)]))
    assert all(np.array_equal(actual, wanted) for actual, wanted in zip(calls, expected))


def test_complete_checkpoint_makes_zero_optimizer_calls(monkeypatch, tmp_path) -> None:
    write_frozen_config(tmp_path)
    expected = synthetic_results(20)
    opt._write_checkpoint_atomic(tmp_path / opt.CHECKPOINT_FILENAME, expected)

    def forbidden(*args, **kwargs):
        raise AssertionError("optimizer must not run for a complete checkpoint")

    monkeypatch.setattr(opt, "minimize", forbidden)
    assert opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path) == expected


def test_malformed_checkpoint_hard_fails_without_overwrite(monkeypatch, tmp_path) -> None:
    write_frozen_config(tmp_path)
    checkpoint = tmp_path / opt.CHECKPOINT_FILENAME
    malformed = "start_id,seed,tau0_days\n0,1,2.0\n"
    checkpoint.write_text(malformed, encoding="utf-8")
    monkeypatch.setattr(opt, "minimize", lambda *args, **kwargs: pytest.fail("optimizer must not run"))
    with pytest.raises(ValueError, match="Malformed R2 checkpoint"):
        opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path)
    assert checkpoint.read_text(encoding="utf-8") == malformed


def test_protocol_mismatch_forbids_resume(monkeypatch, tmp_path) -> None:
    write_frozen_config(tmp_path, numerical_gate_max_substeps=144)
    opt._write_checkpoint_atomic(tmp_path / opt.CHECKPOINT_FILENAME, synthetic_results(5))
    monkeypatch.setattr(opt, "minimize", lambda *args, **kwargs: pytest.fail("optimizer must not run"))
    with pytest.raises(ValueError, match="protocol mismatch"):
        opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path)


def test_resumed_final_result_equals_uninterrupted_result(monkeypatch, tmp_path) -> None:
    uninterrupted_calls = []
    monkeypatch.setattr(opt, "minimize", deterministic_minimize(uninterrupted_calls))
    uninterrupted = opt.fit_r2_train_only(nodes(), np.ones(2), np.ones(2), router=opt.route_daily)

    write_frozen_config(tmp_path)
    opt._write_checkpoint_atomic(tmp_path / opt.CHECKPOINT_FILENAME, uninterrupted[:5])
    resumed_calls = []
    monkeypatch.setattr(opt, "minimize", deterministic_minimize(resumed_calls))
    resumed = opt.fit_r2_train_only(
        nodes(), np.ones(2), np.ones(2), checkpoint_dir=tmp_path, router=opt.route_daily
    )
    assert len(uninterrupted_calls) == 20
    assert len(resumed_calls) == 15
    assert resumed == uninterrupted


def test_storage_initialized_from_first_train_flow_and_propagated(monkeypatch) -> None:
    initializations, routes = [], []

    def init(flow, tau):
        initializations.append(flow)
        return tau * flow

    def route(flow, tau, steps, state):
        routes.append(state.copy())
        return np.zeros(len(flow)), state + 1, np.zeros(len(flow))

    monkeypatch.setattr(opt, "initialize_steady_state", init)
    monkeypatch.setattr(opt, "route_daily", route)
    opt.train_objective(nodes(), np.array([7.0, 8.0]), np.array([0.0, 0.0]), np.ones(68))
    assert initializations == [7.0]
    assert len(routes) == 1 and np.all(routes[0] == 7.0)
