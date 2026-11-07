import numpy as np
import pandas as pd

from scripts.evaluate_irrigation_memory_falsification import (
    percentile_lower_is_better,
    smooth_warm_gate_with_phase,
)
from scripts.evaluate_irrigation_seasonal_dual_path import seasonal_gate


def test_zero_phase_reproduces_teacher_aligned_smooth_warm_gate():
    dates = pd.date_range("2004-01-01", "2004-12-31", freq="D")
    observed = smooth_warm_gate_with_phase(dates, 0.0)
    expected = seasonal_gate(dates, "smooth_warm")
    np.testing.assert_allclose(observed, expected)


def test_one_year_phase_shift_is_nearly_periodic():
    dates = pd.date_range("2003-01-01", "2005-12-31", freq="D")
    original = smooth_warm_gate_with_phase(dates, 0.0)
    shifted = smooth_warm_gate_with_phase(dates, 365.25)
    np.testing.assert_allclose(original, shifted, atol=1e-12)


def test_lower_rmse_percentile_counts_worse_controls():
    controls = pd.Series([1.0, 3.0, 4.0])
    assert percentile_lower_is_better(2.0, controls) == 2.0 / 3.0

