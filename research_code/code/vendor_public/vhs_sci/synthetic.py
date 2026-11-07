"""Known-answer synthetic hydrology, independent of all teacher Q values."""
import numpy as np
from .contracts import SampleKey, FeatureBatch, digest, ScienceError

YEARS = (2003, 2007, 2008, 2010, 2014, 2016, 2019, 2020, 2021, 2022, 2024)


def make_dataset(scenario, seed=20261025, scramble=False):
    if scenario not in ("A", "B", "C", "D"):
        raise ScienceError("UNKNOWN_SYNTHETIC_SCENARIO")
    rng = np.random.default_rng(seed)
    months = np.tile(np.arange(1, 13), len(YEARS))
    phase = 2 * np.pi * months / 12
    yr_p, yr_t = rng.normal(0, 6, len(YEARS)), rng.normal(0, 4, len(YEARS))
    P = 40 + 12 * np.sin(phase) + np.repeat(yr_p, 12)
    T = 20 + 7 * np.cos(phase) + np.repeat(yr_t, 12)
    Qu = 120 + 18 * np.sin(phase) + rng.normal(0, 12, len(months))
    if scenario == "A":
        y = Qu.copy()
    elif scenario == "B":
        y = 17 + 0.72 * Qu
    elif scenario == "C":
        y = 17 + 0.72 * Qu + 23 * np.sin(phase) - 11 * np.cos(phase)
    else:
        y = 200 + 2 * P + 3 * T
    if scramble:
        # Same-month cross-year permutation preserves season and support.
        for m in range(1, 13):
            ix = np.flatnonzero(months == m)
            perm = rng.permutation(len(ix))
            if scenario == "D":
                P[ix], T[ix] = P[ix][perm], T[ix][perm]
            else:
                Qu[ix] = Qu[ix][perm]
    ds = "SYNTHETIC_SYRDARYA"
    # Snapshot commits labels too, while model inputs never receive those labels.
    snap = "synthetic-snap-" + digest({"scenario": scenario, "seed": seed, "scramble": scramble,
        "P": P.tolist(), "T": T.tolist(), "Qu": None if scenario == "D" else Qu.tolist(), "labels": y.tolist()})[:20]
    keys = tuple(SampleKey(ds, snap, ds + ":16039", year, m) for year in YEARS for m in range(1, 13))
    columns = {"P": P, "T": T, "met_complete": np.ones(len(keys), dtype=bool)}
    if scenario != "D":
        columns["Qu"] = Qu
    return FeatureBatch(keys, columns), y, None if scenario == "D" else Qu.copy()
