import numpy as np
import pandas as pd
import torch
from pathlib import Path

from vhs.data import WindowDataset, fit_normalization, split_window_indices
from vhs.metrics import regression_metrics
from vhs.model import DirectedSTGNN, DirectedSnapshotGNN
from vhs.synthetic import make_synthetic_bundle
from scripts.prepare_era5_land_daily import expected_accumulated_paths, expected_times


def test_metrics_perfect_prediction():
    metrics = regression_metrics(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0]))
    assert metrics["rmse"] == 0.0
    assert np.isclose(metrics["nse"], 1.0)
    assert np.isclose(metrics["kge"], 1.0)


def test_virtual_station_flow_is_masked():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=1)
    train, _, _, train_end, _ = split_window_indices(120, 10, 0.7, 0.15)
    norm = fit_normalization(bundle, train_end, target_station_ids=["S05"], flow_feature="obs_q")
    ds = WindowDataset(bundle, train, 10, norm, "obs_q", ["S05"])
    item = ds[0]
    flow_idx = list(bundle.feature_names).index("obs_q")
    assert torch.all(item["x"][:, 5, flow_idx] == 0)
    availability_offset = len(bundle.feature_names)
    assert torch.all(item["x"][:, 5, availability_offset + flow_idx] == 0)


def test_model_forward_shape():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=2)
    model = DirectedSTGNN(dynamic_dim=8, static_dim=3, edge_dim=1, hidden_dim=16, graph_layers=2)
    x = torch.randn(4, 10, 8, 8)
    static = torch.randn(4, 8, 3)
    pred = model(x, static, torch.from_numpy(bundle.edge_index), torch.from_numpy(bundle.edge_attr))
    assert pred.shape == (4, 8)


def test_station_reference_normalization_uses_reference_for_holdout():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=3)
    _, _, _, train_end, _ = split_window_indices(120, 10, 0.7, 0.15)
    norm = fit_normalization(
        bundle,
        train_end,
        target_station_ids=["S05"],
        flow_feature="obs_q",
        mode="station_reference",
        reference_feature="wg_dis",
    )
    reference_idx = list(bundle.feature_names).index("wg_dis")
    expected = np.nanmean(bundle.x[:train_end, 5, reference_idx])
    assert np.isclose(np.asarray(norm.y_mean).reshape(-1)[5], expected)
    flow_idx = list(bundle.feature_names).index("obs_q")
    assert np.asarray(norm.x_mean)[0, 5, flow_idx] == 0.0
    assert np.asarray(norm.x_std)[0, 5, flow_idx] == 1.0


def test_training_station_dropout_masks_only_supervised_downstream_nodes():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=4)
    train, _, _, train_end, _ = split_window_indices(120, 10, 0.7, 0.15)
    norm = fit_normalization(bundle, train_end, target_station_ids=["S05"], flow_feature="obs_q")
    ds = WindowDataset(
        bundle,
        train,
        10,
        norm,
        "obs_q",
        ["S05"],
        flow_dropout_probability=1.0,
    )
    item = ds[0]
    flow_position = list(bundle.feature_names).index("obs_q")
    availability_position = len(bundle.feature_names) + flow_position
    # Nodes 2 and 3 have incoming edges and remain supervised, so dropout masks them.
    assert torch.all(item["x"][:, 2:4, flow_position] == 0)
    assert torch.all(item["x"][:, 2:4, availability_position] == 0)
    # Root node 0 has no incoming edge and must remain available.
    assert torch.any(item["x"][:, 0, availability_position] > 0)


def test_selected_target_reference_input_can_be_masked_without_removing_output_anchor():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=5)
    train, _, _, train_end, _ = split_window_indices(120, 10, 0.7, 0.15)
    norm = fit_normalization(bundle, train_end, target_station_ids=["S05"], flow_feature="obs_q")
    ds = WindowDataset(
        bundle,
        train,
        10,
        norm,
        "obs_q",
        ["S05"],
        input_feature_names=["obs_q", "wg_dis"],
        output_reference_feature="wg_dis",
        mask_target_input_features=["wg_dis"],
    )
    item = ds[0]
    assert torch.all(item["x"][:, 5, 1] == 0)
    assert torch.all(item["x"][:, 5, 3] == 0)
    assert item["output_reference_mask"][5]


def test_virtual_station_node_dropout_masks_all_dynamic_inputs():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=6)
    train, _, _, train_end, _ = split_window_indices(120, 10, 0.7, 0.15)
    norm = fit_normalization(bundle, train_end, target_station_ids=["S05"], flow_feature="obs_q")
    ds = WindowDataset(
        bundle,
        train,
        10,
        norm,
        "obs_q",
        ["S05"],
        input_feature_names=["obs_q", "wg_dis"],
        output_reference_feature="wg_dis",
        node_dropout_probability=1.0,
    )
    item = ds[0]
    assert torch.all(item["x"][:, 2:4, :] == 0)
    assert torch.any(item["x"][:, 0, :] != 0)
    assert item["output_reference_mask"][2]


def test_residual_nonnegative_constraint_preserves_positive_reference():
    model = DirectedSTGNN(
        dynamic_dim=2,
        static_dim=1,
        edge_dim=1,
        hidden_dim=8,
        graph_layers=0,
        output_floor=0.0,
        residual_output=True,
        residual_scale=0.25,
    )
    for parameter in model.decoder.parameters():
        torch.nn.init.zeros_(parameter)
    x = torch.zeros(2, 5, 3, 2)
    static = torch.zeros(2, 3, 1)
    reference = torch.tensor([[1.0, 2.0, 3.0], [0.5, 1.5, 2.5]])
    pred = model(
        x,
        static,
        torch.empty((2, 0), dtype=torch.long),
        torch.empty((0, 1)),
        output_reference=reference,
    )
    assert torch.allclose(pred, reference)


def test_current_snapshot_uses_same_time_inputs_and_masks_target_flow():
    bundle = make_synthetic_bundle(num_days=120, num_nodes=8, seed=7)
    train, _, _, train_end, _ = split_window_indices(120, 1, 0.7, 0.15)
    norm = fit_normalization(
        bundle, train_end, target_station_ids=["S05"], flow_feature="obs_q"
    )
    ds = WindowDataset(
        bundle,
        train,
        1,
        norm,
        "obs_q",
        ["S05"],
        current_snapshot=True,
    )
    item = ds[0]
    flow_idx = list(bundle.feature_names).index("obs_q")
    expected_root = (
        bundle.x[train[0], 0, flow_idx] - np.asarray(norm.x_mean).reshape(-1)[flow_idx]
    ) / np.asarray(norm.x_std).reshape(-1)[flow_idx]
    assert torch.isclose(item["x"][0, 0, flow_idx], torch.tensor(expected_root))
    assert item["x"][0, 5, flow_idx] == 0


def test_snapshot_model_has_no_recurrent_encoder_and_preserves_reference():
    model = DirectedSnapshotGNN(
        dynamic_dim=4,
        static_dim=2,
        edge_dim=1,
        hidden_dim=8,
        graph_layers=0,
        output_floor=0.0,
        residual_output=True,
        residual_scale=0.25,
    )
    assert not any(isinstance(module, torch.nn.GRU) for module in model.modules())
    for parameter in model.decoder.parameters():
        torch.nn.init.zeros_(parameter)
    reference = torch.tensor([[1.0, 2.0, 3.0]])
    pred = model(
        torch.zeros(1, 1, 3, 4),
        torch.zeros(1, 3, 2),
        torch.empty((2, 0), dtype=torch.long),
        torch.empty((0, 1)),
        output_reference=reference,
    )
    assert torch.allclose(pred, reference)


def test_accumulated_paths_support_external_years_and_year_end_supplement():
    raw_root = Path("dummy_raw_root")
    regular = expected_accumulated_paths(
        raw_root, pd.Timestamp("1999-01-01"), pd.Timestamp("2001-12-01")
    )
    assert [path.name for path in regular] == [
        "era5land_accumulated_1999_00utc.nc",
        "era5land_accumulated_2000_00utc.nc",
        "era5land_accumulated_2001_00utc.nc",
    ]
    year_end = expected_accumulated_paths(
        raw_root, pd.Timestamp("1978-01-01"), pd.Timestamp("1983-12-31")
    )
    assert year_end[-1].name == "era5land_accumulated_19840101_00utc.nc"
    supplement_times = expected_times(year_end[-1], "accumulated")
    assert supplement_times.equals(pd.DatetimeIndex([pd.Timestamp("1984-01-01")]))
