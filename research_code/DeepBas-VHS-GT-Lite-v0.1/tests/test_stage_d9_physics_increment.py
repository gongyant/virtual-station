import numpy as np
import pandas as pd

from scripts.run_stage_d9_physics_increment import (
    apply_residual_blend,
    fit_residual_blend,
    interpolate_geometry_by_driver,
)


def test_geometry_interpolation_never_extrapolates():
    reference = pd.DataFrame(
        {
            "discharge_m3s": [10.0, 20.0, 30.0],
            "stage_m": [1.0, 2.0, 3.0],
            "width_m": [10.0, 20.0, 30.0],
            "mean_depth_m": [0.5, 1.0, 1.5],
            "area_m2": [5.0, 20.0, 45.0],
        }
    )
    result = interpolate_geometry_by_driver(
        reference, "discharge_m3s", np.array([5.0, 15.0, 35.0])
    )
    assert np.isnan(result.loc[0, "stage_m"])
    assert result.loc[1, "stage_m"] == 1.5
    assert np.isnan(result.loc[2, "stage_m"])
    assert result.geometry_driver_inside_domain.tolist() == [False, True, False]


def test_residual_blend_uses_frozen_parameters_and_nonnegative_output():
    observed = np.linspace(10.0, 40.0, 30)
    baseline = observed - 4.0
    physics = observed + np.linspace(-2.0, 2.0, 30)
    parameters = fit_residual_blend(observed, baseline, physics)
    prediction = apply_residual_blend(baseline, physics, parameters)
    assert len(prediction) == len(observed)
    assert np.isfinite(prediction).all()
    assert (prediction >= 0).all()
    assert parameters["fit_rows"] == 30
