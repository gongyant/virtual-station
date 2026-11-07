from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from vhs.data import TensorBundle
from vhs.metrics import regression_metrics


ALPHAS = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]


def seasonal_features(dates: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    index = pd.DatetimeIndex(dates)
    angle = 2.0 * np.pi * (index.dayofyear.to_numpy() - 1.0) / 365.25
    return np.sin(angle), np.cos(angle)


def edge_samples(
    bundle: TensorBundle,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    time_indices: np.ndarray,
    excluded_target: str,
    velocity_m_s: float,
) -> pd.DataFrame:
    station_ids = list(map(str, bundle.station_ids))
    station_to_idx = {station: idx for idx, station in enumerate(station_ids)}
    feature_names = list(map(str, bundle.feature_names))
    obs_idx = feature_names.index("obs_q")
    wg_idx = feature_names.index("wg_dis")
    node_table = nodes.set_index("station_id")
    records = []
    for edge in edges.itertuples(index=False):
        source = str(edge.source)
        target = str(edge.target)
        if target == excluded_target or source not in station_to_idx or target not in station_to_idx:
            continue
        source_idx = station_to_idx[source]
        target_idx = station_to_idx[target]
        distance = float(edge.river_distance_km)
        lag = max(1, int(math.ceil(distance / (velocity_m_s * 86.4))))
        usable = time_indices[time_indices >= lag]
        source_flow = bundle.x[usable - lag, source_idx, obs_idx].astype(float)
        observed = bundle.y[usable, target_idx].astype(float)
        reference = source_flow * (
            float(node_table.loc[target, "UP_AREA"])
            / float(node_table.loc[source, "UP_AREA"])
        )
        sine, cosine = seasonal_features(bundle.dates[usable])
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(bundle.dates[usable]),
                "source": source,
                "target": target,
                "observed": observed,
                "physical_reference": reference,
                "source_flow": source_flow,
                "wg_target_lag1": bundle.x[usable - 1, target_idx, wg_idx],
                "wg_source_lag1": bundle.x[usable - 1, source_idx, wg_idx],
                "doy_sin": sine,
                "doy_cos": cosine,
                "area_ratio": float(node_table.loc[target, "UP_AREA"])
                / float(node_table.loc[source, "UP_AREA"]),
                "river_distance_km": distance,
                "routing_lag_days": lag,
                "target_reservoir_flag": float(node_table.loc[target, "reservoir_flag"]),
            }
        )
        frame["residual"] = frame["observed"] - frame["physical_reference"]
        valid_target = bundle.y_mask[usable, target_idx]
        valid_source = np.isfinite(source_flow)
        records.append(frame.loc[valid_target & valid_source])
    if not records:
        raise ValueError("No non-target graph-edge training samples are available")
    return pd.concat(records, ignore_index=True)


def target_samples(
    bundle: TensorBundle,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    time_indices: np.ndarray,
    upstream: str,
    target: str,
    velocity_m_s: float,
) -> pd.DataFrame:
    station_ids = list(map(str, bundle.station_ids))
    source_idx, target_idx = station_ids.index(upstream), station_ids.index(target)
    feature_names = list(map(str, bundle.feature_names))
    obs_idx, wg_idx = feature_names.index("obs_q"), feature_names.index("wg_dis")
    edge = edges.loc[edges["source"].eq(upstream) & edges["target"].eq(target)]
    if len(edge) != 1:
        raise ValueError("Expected exactly one upstream-to-target graph edge")
    distance = float(edge.iloc[0]["river_distance_km"])
    lag = max(1, int(math.ceil(distance / (velocity_m_s * 86.4))))
    usable = time_indices[time_indices >= lag]
    node_table = nodes.set_index("station_id")
    source_flow = bundle.x[usable - lag, source_idx, obs_idx].astype(float)
    ratio = float(node_table.loc[target, "UP_AREA"]) / float(
        node_table.loc[upstream, "UP_AREA"]
    )
    sine, cosine = seasonal_features(bundle.dates[usable])
    return pd.DataFrame(
        {
            "date": pd.to_datetime(bundle.dates[usable]),
            "observed": bundle.y[usable, target_idx].astype(float),
            "physical_reference": source_flow * ratio,
            "source_flow": source_flow,
            "wg_target_lag1": bundle.x[usable - 1, target_idx, wg_idx],
            "wg_source_lag1": bundle.x[usable - 1, source_idx, wg_idx],
            "doy_sin": sine,
            "doy_cos": cosine,
            "area_ratio": ratio,
            "river_distance_km": distance,
            "routing_lag_days": lag,
            "target_reservoir_flag": float(node_table.loc[target, "reservoir_flag"]),
        }
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Strict graph-transfer residual correction around an area-routing baseline."
    )
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--nodes", type=Path, default=Path("data/processed/nodes.csv"))
    parser.add_argument("--edges", type=Path, default=Path("data/processed/edges.csv"))
    parser.add_argument("--upstream", default="00705600")
    parser.add_argument("--target", default="00705700")
    parser.add_argument("--history", type=int, default=30)
    parser.add_argument("--train-end", required=True)
    parser.add_argument("--validation-end", required=True)
    parser.add_argument("--velocity-m-s", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = TensorBundle.load(args.bundle)
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str})
    edges = pd.read_csv(args.edges, dtype={"source": str, "target": str})
    dates = pd.DatetimeIndex(bundle.dates)
    all_indices = np.arange(args.history, len(dates))
    train_end = pd.Timestamp(args.train_end)
    validation_end = pd.Timestamp(args.validation_end)
    train_indices = all_indices[dates[all_indices] <= train_end]
    validation_indices = all_indices[
        (dates[all_indices] > train_end) & (dates[all_indices] <= validation_end)
    ]
    test_indices = all_indices[dates[all_indices] > validation_end]
    train = edge_samples(
        bundle, nodes, edges, train_indices, args.target, args.velocity_m_s
    )
    validation = edge_samples(
        bundle, nodes, edges, validation_indices, args.target, args.velocity_m_s
    )
    test = target_samples(
        bundle,
        nodes,
        edges,
        test_indices,
        args.upstream,
        args.target,
        args.velocity_m_s,
    )
    features = [
        "physical_reference",
        "source_flow",
        "wg_target_lag1",
        "wg_source_lag1",
        "doy_sin",
        "doy_cos",
        "area_ratio",
        "river_distance_km",
        "routing_lag_days",
        "target_reservoir_flag",
    ]
    train = train.dropna(subset=features + ["residual"])
    validation = validation.dropna(subset=features + ["residual"])
    test = test.dropna(subset=features + ["observed"])
    if train.empty or validation.empty:
        raise ValueError(
            "No contemporaneous non-target upstream/downstream observations are available; "
            "graph residual transfer cannot be fitted under the strict protocol."
        )
    best_alpha, best_rmse = None, np.inf
    for alpha in ALPHAS:
        model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
        model.fit(train[features], train["residual"])
        prediction = model.predict(validation[features])
        rmse = float(np.sqrt(np.mean((validation["residual"] - prediction) ** 2)))
        if rmse < best_rmse:
            best_alpha, best_rmse = alpha, rmse
    development = pd.concat([train, validation], ignore_index=True)
    model = make_pipeline(StandardScaler(), Ridge(alpha=best_alpha))
    model.fit(development[features], development["residual"])
    test["graph_physics_residual"] = np.maximum(
        test["physical_reference"] + model.predict(test[features]), 0.0
    )
    rows = []
    for name in ["physical_reference", "graph_physics_residual"]:
        rows.append({"model": name, **regression_metrics(test["observed"], test[name])})
    metrics = pd.DataFrame(rows).sort_values("nse", ascending=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    test.to_csv(args.output_dir / "test_predictions.csv", index=False)
    metrics.to_csv(args.output_dir / "metrics.csv", index=False)
    metadata = {
        "strict_target_station": args.target,
        "target_labels_used_for_fit_or_alpha_selection": False,
        "training_edge_samples": len(train),
        "validation_edge_samples": len(validation),
        "training_target_stations": int(train["target"].nunique()),
        "selected_alpha_on_non_target_validation": best_alpha,
        "assumed_velocity_m_s": args.velocity_m_s,
        "target_routing_lag_days": int(test["routing_lag_days"].iloc[0]),
        "test_start": str(test["date"].min().date()),
        "test_end": str(test["date"].max().date()),
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(metrics.to_string(index=False))
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
