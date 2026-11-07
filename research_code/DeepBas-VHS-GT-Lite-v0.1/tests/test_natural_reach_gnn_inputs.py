from pathlib import Path

import pandas as pd
import pytest

from scripts.prepare_natural_reach_gnn_inputs import (
    load_ground_observations,
    same_day_pair_count,
)


def test_ground_observation_loader_rejects_duplicate_dates():
    path = "tests/fixtures/duplicate_ground_observations.csv"
    with pytest.raises(ValueError, match="duplicate dates"):
        load_ground_observations(Path(path))


def test_pair_count_requires_same_day_and_nonmissing_ground_value():
    frame = pd.DataFrame(
        {
            "satellite": [1, 1, 0],
            "discharge": [2.0, float("nan"), 4.0],
        }
    )
    assert same_day_pair_count(frame, "satellite", "discharge") == 1
