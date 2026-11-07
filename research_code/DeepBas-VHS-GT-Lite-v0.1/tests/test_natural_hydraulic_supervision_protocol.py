import pandas as pd

from scripts.prepare_natural_hydraulic_supervision_protocol import (
    chronological_split,
    completeness,
)


def test_completeness_treats_blank_strings_as_missing():
    values = pd.Series(["v1", " ", None, "v2"])
    assert completeness(values) == 0.5


def test_chronological_split_is_ordered_and_seals_only_final_block():
    dates = pd.Series(pd.date_range("2023-01-01", periods=10, freq="D"))
    split = chronological_split(dates)
    assert split.split.tolist() == [
        "calibration",
        "calibration",
        "calibration",
        "calibration",
        "calibration",
        "calibration",
        "validation",
        "validation",
        "sealed_test",
        "sealed_test",
    ]
    assert not split.loc[split.split.ne("sealed_test"), "sealed_label"].any()
    assert split.loc[split.split.eq("sealed_test"), "sealed_label"].all()
