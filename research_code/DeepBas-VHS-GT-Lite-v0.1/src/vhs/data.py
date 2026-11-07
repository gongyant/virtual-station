from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import warnings

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset

from .graph import edge_arrays


@dataclass
class TensorBundle:
    dates: np.ndarray
    station_ids: np.ndarray
    feature_names: np.ndarray
    x: np.ndarray
    y: np.ndarray
    y_mask: np.ndarray
    static: np.ndarray
    edge_index: np.ndarray
    edge_attr: np.ndarray

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path,
            dates=self.dates.astype("datetime64[D]").astype(str),
            station_ids=self.station_ids.astype(str),
            feature_names=self.feature_names.astype(str),
            x=self.x.astype(np.float32),
            y=self.y.astype(np.float32),
            y_mask=self.y_mask.astype(bool),
            static=self.static.astype(np.float32),
            edge_index=self.edge_index.astype(np.int64),
            edge_attr=self.edge_attr.astype(np.float32),
        )

    @classmethod
    def load(cls, path: str | Path) -> "TensorBundle":
        z = np.load(path, allow_pickle=False)
        return cls(
            dates=z["dates"].astype("datetime64[D]"),
            station_ids=z["station_ids"].astype(str),
            feature_names=z["feature_names"].astype(str),
            x=z["x"],
            y=z["y"],
            y_mask=z["y_mask"],
            static=z["static"],
            edge_index=z["edge_index"],
            edge_attr=z["edge_attr"],
        )


def build_bundle(
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    timeseries: pd.DataFrame,
    dynamic_features: list[str],
    static_features: list[str] | None = None,
) -> TensorBundle:
    nodes = nodes.copy()
    nodes["station_id"] = nodes.station_id.astype(str)
    station_ids = nodes.station_id.to_numpy()
    dates = np.sort(pd.to_datetime(timeseries.date).dt.normalize().unique())
    timeseries = timeseries.copy()
    timeseries["date"] = pd.to_datetime(timeseries.date).dt.normalize()
    timeseries["station_id"] = timeseries.station_id.astype(str)

    x = np.full((len(dates), len(station_ids), len(dynamic_features)), np.nan, dtype=np.float32)
    for f_idx, feature in enumerate(dynamic_features):
        if feature not in timeseries:
            continue
        pivot = timeseries.pivot_table(index="date", columns="station_id", values=feature, aggfunc="mean")
        pivot = pivot.reindex(index=dates, columns=station_ids)
        x[:, :, f_idx] = pivot.to_numpy(np.float32)

    if "obs_q" not in timeseries:
        raise KeyError("timeseries must contain obs_q as the supervised target")
    target = timeseries.pivot_table(index="date", columns="station_id", values="obs_q", aggfunc="mean")
    target = target.reindex(index=dates, columns=station_ids)
    y = target.to_numpy(np.float32)
    y_mask = np.isfinite(y)

    static_features = static_features or [
        c for c in ["reservoir_flag", "UP_AREA", "SUB_AREA", "kmz_CATCHAREA"] if c in nodes
    ]
    if static_features:
        static = nodes[static_features].apply(pd.to_numeric, errors="coerce").fillna(0.0).to_numpy(np.float32)
    else:
        static = np.zeros((len(nodes), 1), dtype=np.float32)
    edge_index, edge_attr = edge_arrays(nodes, edges)
    return TensorBundle(
        dates=np.asarray(dates, dtype="datetime64[D]"),
        station_ids=station_ids,
        feature_names=np.asarray(dynamic_features),
        x=x,
        y=y,
        y_mask=y_mask,
        static=static,
        edge_index=edge_index,
        edge_attr=edge_attr,
    )


@dataclass
class Normalization:
    x_mean: np.ndarray
    x_std: np.ndarray
    static_mean: np.ndarray
    static_std: np.ndarray
    y_mean: float | np.ndarray
    y_std: float | np.ndarray


def fit_normalization(
    bundle: TensorBundle,
    train_end: int,
    target_station_ids: list[str] | None = None,
    flow_feature: str | None = None,
    mode: str = "global",
    reference_feature: str | None = None,
) -> Normalization:
    """Fit scalers on training data without looking at held-out station flow."""
    train_x = bundle.x[:train_end].copy()
    target_set = set(map(str, target_station_ids or []))
    target_mask = np.asarray([str(s) in target_set for s in bundle.station_ids], dtype=bool)
    if target_mask.any() and flow_feature is not None:
        flow_idx = list(bundle.feature_names).index(flow_feature)
        train_x[:, target_mask, flow_idx] = np.nan
    if mode not in {"global", "station_reference"}:
        raise ValueError(f"Unknown normalization mode: {mode}")
    if mode == "station_reference":
        # Per-station feature scaling prevents high-flow stations from dominating
        # shared weights. The held-out station flow is already NaN here, so its
        # observed discharge cannot enter these statistics.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=RuntimeWarning)
            x_mean = np.nanmean(train_x, axis=0, keepdims=True)
            x_std = np.nanstd(train_x, axis=0, keepdims=True)
    else:
        x_mean = np.nanmean(train_x, axis=(0, 1), keepdims=True)
        x_std = np.nanstd(train_x, axis=(0, 1), keepdims=True)
    x_mean = np.where(np.isfinite(x_mean), x_mean, 0.0)
    x_std = np.where((x_std > 1e-6) & np.isfinite(x_std), x_std, 1.0)
    static_mean = np.nanmean(bundle.static, axis=0, keepdims=True)
    static_std = np.nanstd(bundle.static, axis=0, keepdims=True)
    static_std = np.where(static_std > 1e-6, static_std, 1.0)
    if mode == "station_reference":
        if reference_feature is None:
            raise ValueError("station_reference normalization requires reference_feature")
        reference_idx = list(map(str, bundle.feature_names)).index(reference_feature)
        train_reference = bundle.x[:train_end, :, reference_idx].astype(float)
        y_mean = np.nanmean(train_reference, axis=0, keepdims=True)
        y_std = np.nanstd(train_reference, axis=0, keepdims=True)
        if not np.isfinite(y_mean).all():
            missing = np.asarray(bundle.station_ids)[~np.isfinite(y_mean.reshape(-1))]
            raise ValueError(
                "Reference feature has no training-period values for stations: "
                + ", ".join(map(str, missing))
            )
        y_std = np.where((y_std > 1e-6) & np.isfinite(y_std), y_std, 1.0)
    else:
        train_y_mask = bundle.y_mask[:train_end].copy()
        if target_mask.any():
            train_y_mask[:, target_mask] = False
        train_y = bundle.y[:train_end][train_y_mask]
        if train_y.size == 0:
            raise ValueError("No observed discharge exists in the training period")
        y_mean = float(np.mean(train_y))
        y_std = float(max(np.std(train_y), 1e-6))
    return Normalization(
        x_mean=x_mean,
        x_std=x_std,
        static_mean=static_mean,
        static_std=static_std,
        y_mean=y_mean,
        y_std=y_std,
    )


class WindowDataset(Dataset):
    def __init__(
        self,
        bundle: TensorBundle,
        indices: np.ndarray,
        history: int,
        normalization: Normalization,
        flow_feature: str,
        target_station_ids: list[str],
        input_feature_names: list[str] | None = None,
        physics_reference_feature: str | None = None,
        output_reference_feature: str | None = None,
        flow_dropout_probability: float = 0.0,
        node_dropout_probability: float = 0.0,
        mask_target_input_features: list[str] | None = None,
        current_snapshot: bool = False,
    ) -> None:
        self.bundle = bundle
        self.indices = np.asarray(indices, dtype=np.int64)
        self.history = int(history)
        self.norm = normalization
        feature_names = list(map(str, bundle.feature_names))
        self.flow_idx = feature_names.index(flow_feature)
        selected_names = input_feature_names or feature_names
        self.input_indices = np.asarray(
            [feature_names.index(name) for name in selected_names], dtype=np.int64
        )
        self.physics_reference_idx = (
            feature_names.index(physics_reference_feature)
            if physics_reference_feature is not None
            else None
        )
        self.output_reference_idx = (
            feature_names.index(output_reference_feature)
            if output_reference_feature is not None
            else None
        )
        self.flow_dropout_probability = float(flow_dropout_probability)
        if not 0.0 <= self.flow_dropout_probability <= 1.0:
            raise ValueError("flow_dropout_probability must be between 0 and 1")
        self.node_dropout_probability = float(node_dropout_probability)
        self.current_snapshot = bool(current_snapshot)
        if self.current_snapshot and self.history != 1:
            raise ValueError("current_snapshot requires history=1")
        if not 0.0 <= self.node_dropout_probability <= 1.0:
            raise ValueError("node_dropout_probability must be between 0 and 1")
        self.flow_input_position = (
            int(np.where(self.input_indices == self.flow_idx)[0][0])
            if self.flow_idx in self.input_indices
            else None
        )
        target_set = set(map(str, target_station_ids))
        self.target_node_mask = np.asarray([str(s) in target_set for s in bundle.station_ids], dtype=bool)
        masked_names = set(map(str, mask_target_input_features or []))
        self.masked_target_input_positions = [
            pos for pos, feature_idx in enumerate(self.input_indices)
            if feature_names[int(feature_idx)] in masked_names
        ]
        incoming_nodes = np.unique(bundle.edge_index[1]) if bundle.edge_index.size else np.array([], dtype=int)
        self.dropout_eligible_nodes = np.zeros(len(bundle.station_ids), dtype=bool)
        self.dropout_eligible_nodes[incoming_nodes] = True
        self.dropout_eligible_nodes &= ~self.target_node_mask

        x = (bundle.x - normalization.x_mean) / normalization.x_std
        availability = np.isfinite(x).astype(np.float32)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
        if self.target_node_mask.any() and self.flow_idx in self.input_indices:
            x[:, self.target_node_mask, self.flow_idx] = 0.0
            availability[:, self.target_node_mask, self.flow_idx] = 0.0
        x = x[:, :, self.input_indices]
        availability = availability[:, :, self.input_indices]
        for position in self.masked_target_input_positions:
            x[:, self.target_node_mask, position] = 0.0
            availability[:, self.target_node_mask, position] = 0.0
        self.x = np.concatenate([x, availability], axis=-1)
        self.static = ((bundle.static - normalization.static_mean) / normalization.static_std).astype(np.float32)
        self.y = ((bundle.y - normalization.y_mean) / normalization.y_std).astype(np.float32)

    def __len__(self) -> int:
        return len(self.indices)

    def __getitem__(self, item: int) -> dict[str, torch.Tensor]:
        t = int(self.indices[item])
        x_window = (
            self.x[t : t + 1].copy()
            if self.current_snapshot
            else self.x[t - self.history : t].copy()
        )
        if self.flow_dropout_probability > 0.0 and self.flow_input_position is not None:
            dropped = self.dropout_eligible_nodes & (
                np.random.random(len(self.bundle.station_ids)) < self.flow_dropout_probability
            )
            if dropped.any():
                availability_position = len(self.input_indices) + self.flow_input_position
                x_window[:, dropped, self.flow_input_position] = 0.0
                x_window[:, dropped, availability_position] = 0.0
        if self.node_dropout_probability > 0.0:
            dropped_nodes = self.dropout_eligible_nodes & (
                np.random.random(len(self.bundle.station_ids)) < self.node_dropout_probability
            )
            if dropped_nodes.any():
                input_count = len(self.input_indices)
                x_window[:, dropped_nodes, :input_count] = 0.0
                x_window[:, dropped_nodes, input_count:] = 0.0
        sample = {
            "x": torch.from_numpy(x_window),
            "static": torch.from_numpy(self.static),
            "y": torch.from_numpy(self.y[t]),
            "y_mask": torch.from_numpy(self.bundle.y_mask[t]),
            "target_node_mask": torch.from_numpy(self.target_node_mask),
            "time_index": torch.tensor(t, dtype=torch.long),
        }
        if self.physics_reference_idx is not None:
            reference = self.bundle.x[t, :, self.physics_reference_idx].astype(np.float32)
            reference_mask = np.isfinite(reference)
            y_mean = np.asarray(self.norm.y_mean).reshape(-1)
            y_std = np.asarray(self.norm.y_std).reshape(-1)
            reference = (reference - y_mean) / y_std
            sample["physics_reference"] = torch.from_numpy(
                np.nan_to_num(reference, nan=0.0).astype(np.float32)
            )
            sample["physics_reference_mask"] = torch.from_numpy(reference_mask)
        if self.output_reference_idx is not None:
            output_reference = self.bundle.x[
                t, :, self.output_reference_idx
            ].astype(np.float32)
            output_reference_mask = np.isfinite(output_reference)
            y_mean = np.asarray(self.norm.y_mean).reshape(-1)
            y_std = np.asarray(self.norm.y_std).reshape(-1)
            output_reference = (output_reference - y_mean) / y_std
            sample["output_reference"] = torch.from_numpy(
                np.nan_to_num(output_reference, nan=0.0).astype(np.float32)
            )
            sample["output_reference_mask"] = torch.from_numpy(
                output_reference_mask
            )
        return sample


def split_window_indices(
    num_times: int,
    history: int,
    train_fraction: float,
    val_fraction: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    train_end = int(num_times * train_fraction)
    val_end = int(num_times * (train_fraction + val_fraction))
    if train_end <= history or val_end <= train_end or val_end >= num_times:
        raise ValueError("Invalid temporal split for available time length/history")
    train = np.arange(history, train_end)
    val = np.arange(train_end, val_end)
    test = np.arange(val_end, num_times)
    return train, val, test, train_end, val_end
