import numpy as np
import pandas as pd

from vhs.agriculture import (
    AgricultureHeadPolicy,
    apply_agriculture_head,
    build_agriculture_features,
    split_conformal_radius,
)


def test_features_require_only_endpoint_flows_and_calendar():
    dates = pd.date_range("2005-05-01", periods=4, freq="D")
    features = build_agriculture_features(
        dates, np.array([100.0, 121.0, 144.0, 169.0]), np.array([25.0] * 4)
    )
    np.testing.assert_allclose(features.agri_endpoint_geometric_q, [50.0, 55.0, 60.0, 65.0])
    assert features.index.equals(dates)
    assert np.isfinite(features.to_numpy()).all()


def test_rejected_mechanism_cannot_change_virtual_station_prediction():
    policy = AgricultureHeadPolicy(False, False, False)
    baseline = np.array([10.0, 20.0])
    correction = np.array([100.0, -100.0])
    np.testing.assert_allclose(
        apply_agriculture_head(baseline, correction, policy), baseline
    )


def test_all_promotion_gates_are_required_for_correction():
    policy = AgricultureHeadPolicy(True, True, True)
    prediction = apply_agriculture_head(
        np.array([10.0, 20.0]), np.array([5.0, -30.0]), policy
    )
    np.testing.assert_allclose(prediction, [15.0, 0.0])


def test_split_conformal_uses_finite_sample_higher_rank():
    residuals = np.arange(1.0, 11.0)
    assert split_conformal_radius(residuals, 0.80) == 9.0
