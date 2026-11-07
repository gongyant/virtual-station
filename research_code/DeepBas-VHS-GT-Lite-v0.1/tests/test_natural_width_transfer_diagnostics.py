import numpy as np
import pandas as pd
import pytest

from scripts.evaluate_natural_width_transfer_diagnostics import (
    fit_power_law,
    predict_power_law,
    similar_width_conflicts,
)


def test_power_law_fit_recovers_known_monotonic_relation():
    width = np.array([10.0, 20.0, 40.0, 80.0])
    observed = 0.5 * width**1.4
    scale, exponent = fit_power_law(width, observed)
    predicted = predict_power_law(width, scale, exponent)
    assert scale == pytest.approx(0.5)
    assert exponent == pytest.approx(1.4)
    assert np.allclose(predicted, observed)


def test_similar_width_conflicts_only_compares_different_years():
    pairs = pd.DataFrame(
        {
            "date": pd.to_datetime(["2000-01-01", "2000-02-01", "2001-01-01"]),
            "year": [2000, 2000, 2001],
            "width_m": [40.0, 42.0, 44.0],
            "observed_q_m3s": [20.0, 30.0, 60.0],
        }
    )
    conflicts = similar_width_conflicts(pairs, tolerance_m=5.0)
    assert len(conflicts) == 2
    assert sorted(conflicts.q_ratio.tolist()) == [2.0, 3.0]
