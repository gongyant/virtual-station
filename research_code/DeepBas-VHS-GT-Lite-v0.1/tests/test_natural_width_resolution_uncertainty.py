import numpy as np
import pandas as pd

from scripts.evaluate_natural_width_resolution_uncertainty import (
    perturb_widths,
    summarise_draws,
)


def test_width_perturbation_is_reproducible_and_positive():
    frame = pd.DataFrame(
        {
            "width_m": [10.0, 20.0, 30.0],
            "width_iqr_m": [5.0, 5.0, 5.0],
            "valid_transects": [7, 7, 7],
        }
    )
    first = perturb_widths(frame, np.random.default_rng(7), 30.0, 1.0)
    second = perturb_widths(frame, np.random.default_rng(7), 30.0, 1.0)
    assert np.allclose(first, second)
    assert np.all(first >= 5.0)


def test_draw_summary_uses_joint_pass_gate():
    draws = pd.DataFrame(
        {
            "validation_nse": [0.2, 0.1, -0.5],
            "validation_rmse_m3s": [10.0, 30.0, 12.0],
        }
    )
    summary = summarise_draws(draws, mean_baseline_rmse=20.0)
    assert summary["probability_nse_above_zero"] == 2 / 3
    assert summary["probability_beats_mean_baseline_rmse"] == 2 / 3
    assert summary["probability_passes_both"] == 1 / 3
