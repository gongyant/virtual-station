import numpy as np
import torch

from scripts.evaluate_shared_backbone_negative_transfer import (
    balanced_regime_loss,
    mask_target_observations,
)


def test_target_observation_mask_does_not_remove_safe_features():
    x = np.arange(2 * 3 * 3, dtype=float).reshape(2, 3, 3)
    masked = mask_target_observations(x, ["obs_q", "reference", "proxy"], [1, 2])
    assert np.isnan(masked[:, 1:, 0]).all()
    np.testing.assert_allclose(masked[:, :, 1:], x[:, :, 1:])
    np.testing.assert_allclose(masked[:, 0, 0], x[:, 0, 0])


def test_balanced_loss_gives_equal_weight_to_regimes():
    prediction = torch.tensor([[10.0, 100.0], [10.0, 100.0]])
    target = torch.tensor([[8.0, 80.0], [8.0, 80.0]])
    scales = torch.tensor([2.0, 20.0])
    loss = balanced_regime_loss(prediction, target, [0, 1], scales)
    assert loss.item() == 1.0
