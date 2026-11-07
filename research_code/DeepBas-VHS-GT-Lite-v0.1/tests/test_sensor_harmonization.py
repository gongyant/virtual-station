import pandas as pd

from scripts.evaluate_recent_landsat_harmonization import greedy_date_pairs


def test_greedy_date_pairs_are_one_to_one():
    left = pd.DataFrame(
        {"date": pd.to_datetime(["2025-01-01", "2025-01-03"]), "width_m": [10, 11], "width_iqr_m": [1, 1]}
    )
    right = pd.DataFrame(
        {"date": pd.to_datetime(["2025-01-02"]), "width_m": [12], "width_iqr_m": [1]}
    )
    pairs = greedy_date_pairs(left, right, maximum_days=2)
    assert len(pairs) == 1
    assert pairs.sentinel_date.nunique() == 1
