import numpy as np
import pytest

from scripts.evaluate_manning_width_constraint import trapezoidal_manning_discharge


def test_manning_discharge_increases_with_top_width_for_fixed_geometry():
    discharge, depth = trapezoidal_manning_discharge(
        np.array([20.0, 30.0, 40.0]), 10.0, 2.0, 0.04, 0.001
    )
    assert np.all(np.diff(discharge) > 0)
    assert np.all(np.diff(depth) > 0)


def test_manning_rejects_nonpositive_roughness():
    with pytest.raises(ValueError, match="physically positive"):
        trapezoidal_manning_discharge(np.array([20.0]), 10.0, 2.0, 0.0, 0.001)
