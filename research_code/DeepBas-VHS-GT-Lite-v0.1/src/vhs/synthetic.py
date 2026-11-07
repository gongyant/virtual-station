from __future__ import annotations

import numpy as np

from .data import TensorBundle


def make_synthetic_bundle(num_days: int = 900, num_nodes: int = 8, seed: int = 42) -> TensorBundle:
    if num_nodes < 6:
        raise ValueError("Synthetic demo expects at least 6 nodes")
    rng = np.random.default_rng(seed)
    dates = np.datetime64("2000-01-01") + np.arange(num_days).astype("timedelta64[D]")
    station_ids = np.asarray([f"S{i:02d}" for i in range(num_nodes)])
    feature_names = np.asarray(["precip", "temperature", "wg_dis", "obs_q"])

    # Branched directed river: 0->2, 1->2, 2->3->5, 4->5, then chain onward.
    edge_list = [(0, 2), (1, 2), (2, 3), (3, 5), (4, 5)]
    edge_list += [(i, i + 1) for i in range(5, num_nodes - 1)]
    edge_index = np.asarray(edge_list, dtype=np.int64).T
    edge_attr = np.asarray([[1.0 + 0.2 * i] for i in range(len(edge_list))], dtype=np.float32)

    day = np.arange(num_days)
    seasonal_temp = 8.0 + 15.0 * np.sin(2 * np.pi * (day - 90) / 365.25)
    precip = rng.gamma(shape=0.8, scale=2.0, size=(num_days, num_nodes))
    dry = rng.random((num_days, num_nodes)) < 0.60
    precip[dry] = 0.0
    temperature = seasonal_temp[:, None] + rng.normal(0, 2.0, size=(num_days, num_nodes))

    q = np.zeros((num_days, num_nodes), dtype=np.float32)
    upstream = {i: [] for i in range(num_nodes)}
    for src, dst in edge_list:
        upstream[dst].append(src)
    for t in range(1, num_days):
        snowmelt = np.maximum(temperature[t] - 0.0, 0.0) * (0.04 + 0.01 * np.arange(num_nodes))
        local = 0.7 * precip[t] + snowmelt
        for n in range(num_nodes):
            routed = sum(0.55 * q[t - 1, u] for u in upstream[n])
            q[t, n] = max(0.0, 0.68 * q[t - 1, n] + local[n] + routed + rng.normal(0, 0.3))

    wg_dis = np.maximum(0.0, q * (0.82 + 0.05 * rng.normal(size=q.shape)) + 1.5)
    observed = q + rng.normal(0, 0.25, size=q.shape)
    x = np.stack([precip, temperature, wg_dis, observed], axis=-1).astype(np.float32)
    y = observed.astype(np.float32)
    y_mask = np.ones_like(y, dtype=bool)
    # Small random observation gaps on non-target stations.
    gaps = rng.random(y.shape) < 0.02
    x[gaps, 3] = np.nan
    y[gaps] = np.nan
    y_mask[gaps] = False
    static = np.stack(
        [
            np.linspace(2000, 600, num_nodes),
            np.linspace(300, 18000, num_nodes),
            np.zeros(num_nodes),
        ],
        axis=1,
    ).astype(np.float32)
    static[5, 2] = 1.0  # reservoir-affected demo node
    return TensorBundle(dates, station_ids, feature_names, x, y, y_mask, static, edge_index, edge_attr)

