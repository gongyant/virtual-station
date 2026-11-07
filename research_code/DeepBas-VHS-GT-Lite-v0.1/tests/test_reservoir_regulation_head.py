import numpy as np
import pandas as pd

from scripts.evaluate_reservoir_regulation_head import add_causal_features


def test_causal_rolling_features_do_not_change_when_future_is_modified():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2000-01-01", periods=10),
            "physical_q_m3s": np.arange(1.0, 11.0),
        }
    )
    original = add_causal_features(frame)
    changed = frame.copy()
    changed.loc[8:, "physical_q_m3s"] = 10000.0
    modified = add_causal_features(changed)
    columns = ["anomaly_7d", "anomaly_30d", "anomaly_90d"]
    assert np.allclose(original.loc[:7, columns], modified.loc[:7, columns])
