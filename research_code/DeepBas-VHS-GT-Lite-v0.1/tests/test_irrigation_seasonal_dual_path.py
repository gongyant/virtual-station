import numpy as np
import pandas as pd

from scripts.evaluate_irrigation_seasonal_dual_path import (
    gated_storage,
    seasonal_gate,
)


def test_fixed_warm_season_gate_is_calendar_only():
    dates = pd.DatetimeIndex(["2005-04-30", "2005-05-01", "2005-09-30", "2005-10-01"])
    assert seasonal_gate(dates, "fixed_may_sep").tolist() == [0.0, 1.0, 1.0, 0.0]


def test_gated_storage_is_causal_nonnegative_and_respects_closed_gate():
    loss = np.array([10.0, 100.0, 0.0])
    gate = np.array([1.0, 0.0, 0.0])
    storage, release = gated_storage(loss, gate, rho=0.5)
    assert np.all(storage >= 0)
    assert np.all(release >= 0)
    assert storage.tolist() == [10.0, 5.0, 2.5]
    assert release.tolist() == [5.0, 2.5, 1.25]


def test_smooth_warm_gate_stays_in_unit_interval():
    dates = pd.date_range("2005-01-01", "2005-12-31", freq="D")
    gate = seasonal_gate(dates, "smooth_warm")
    assert np.all((gate >= 0.0) & (gate <= 1.0))
    assert gate.max() > 0.99
