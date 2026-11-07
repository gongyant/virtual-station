from __future__ import annotations

import argparse
import copy
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from .config import load_config, resolve_device
from .data import TensorBundle, WindowDataset, fit_normalization, split_window_indices
from .metrics import regression_metrics
from .model import DirectedSTGNN, DirectedSnapshotGNN
from .synthetic import make_synthetic_bundle


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _edge_normalize(edge_attr: np.ndarray) -> np.ndarray:
    mean = edge_attr.mean(axis=0, keepdims=True)
    std = edge_attr.std(axis=0, keepdims=True)
    return ((edge_attr - mean) / np.where(std > 1e-6, std, 1.0)).astype(np.float32)


def _loader(dataset: WindowDataset, batch_size: int, shuffle: bool, workers: int) -> DataLoader:
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle, num_workers=workers)


def _loss_for_batch(
    pred: torch.Tensor,
    batch: dict[str, torch.Tensor],
    training: bool,
    physics_loss_weight: float = 0.0,
) -> torch.Tensor | None:
    mask = batch["y_mask"].bool()
    target_nodes = batch["target_node_mask"].bool()
    # Entire target station is excluded from training labels and used only for validation/test.
    if training and target_nodes.any():
        mask = mask & ~target_nodes
    elif not training and target_nodes.any():
        mask = mask & target_nodes
    data_loss = torch.mean((pred[mask] - batch["y"][mask]) ** 2) if mask.any() else None
    physics_loss = None
    if training and physics_loss_weight > 0.0 and "physics_reference" in batch:
        physics_mask = batch["physics_reference_mask"].bool() & target_nodes
        if physics_mask.any():
            physics_loss = torch.mean(
                (pred[physics_mask] - batch["physics_reference"][physics_mask]) ** 2
            )
    if data_loss is None:
        return physics_loss_weight * physics_loss if physics_loss is not None else None
    if physics_loss is not None:
        return data_loss + physics_loss_weight * physics_loss
    return data_loss


@torch.no_grad()
def evaluate(
    model: DirectedSTGNN,
    loader: DataLoader,
    edge_index: torch.Tensor,
    edge_attr: torch.Tensor,
    device: str,
    y_mean: float,
    y_std: float,
    target_only: bool = True,
) -> tuple[float, dict[str, float], pd.DataFrame]:
    model.eval()
    losses, obs_all, pred_all, time_all, node_all = [], [], [], [], []
    station_ids = loader.dataset.bundle.station_ids
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        pred = model(
            batch["x"],
            batch["static"],
            edge_index,
            edge_attr,
            output_reference=batch.get("output_reference"),
        )
        # loss = _loss_for_batch(pred, batch, training=False)
        mask = batch["y_mask"].bool()
        target_mask = batch["target_node_mask"].bool()
        # target_only=True：只评价完整留出的目标站
        # target_only=False：只评价非目标站，用于模型选择和早停
        if target_mask.any():
            if target_only:
                mask &= target_mask
            else:
                mask &= ~target_mask

        if mask.any():
            loss = torch.mean((pred[mask] - batch["y"][mask]) ** 2)
            losses.append(float(loss))

        selected = mask.cpu().numpy()
        # if loss is not None:
        #     losses.append(float(loss))
        # mask = batch["y_mask"].bool()
        # if batch["target_node_mask"].any():
        #     mask &= batch["target_node_mask"].bool()
        # selected = mask.cpu().numpy()
        obs = batch["y"].cpu().numpy() * y_std + y_mean
        est = pred.cpu().numpy() * y_std + y_mean
        for b in range(selected.shape[0]):
            ids = np.where(selected[b])[0]
            obs_all.extend(obs[b, ids].tolist())
            pred_all.extend(est[b, ids].tolist())
            time_all.extend([int(batch["time_index"][b])] * len(ids))
            node_all.extend([str(station_ids[i]) for i in ids])
            
    metrics = regression_metrics(np.asarray(obs_all), np.asarray(pred_all))
    frame = pd.DataFrame({"time_index": time_all, "station_id": node_all, "observed": obs_all, "predicted": pred_all})
    mean_loss = (
        float(np.mean(losses))
        if losses
        else float("nan")
    )
    return mean_loss, metrics, frame


def train_from_config(config_path: str | Path) -> dict[str, float]:
    cfg = load_config(config_path)
    seed = int(cfg.get("seed", 42))
    seed_everything(seed)
    device = resolve_device(str(cfg.get("device", "auto")))
    output_dir = Path(cfg.get("output_dir", "outputs/run"))
    output_dir.mkdir(parents=True, exist_ok=True)

    data_cfg = cfg["data"]
    bundle_path = Path(data_cfg["bundle_path"])
    if data_cfg.get("mode") == "synthetic":
        bundle = make_synthetic_bundle(
            num_days=int(data_cfg.get("num_days", 900)),
            num_nodes=int(data_cfg.get("num_nodes", 8)),
            seed=seed,
        )
        bundle.save(bundle_path)
    else:
        bundle = TensorBundle.load(bundle_path)

    history = int(data_cfg.get("history", 30))
    if data_cfg.get("train_end_date") and data_cfg.get("validation_end_date"):
        dates = pd.DatetimeIndex(bundle.dates)
        train_end_date = pd.Timestamp(data_cfg["train_end_date"])
        validation_end_date = pd.Timestamp(data_cfg["validation_end_date"])
        all_idx = np.arange(history, len(bundle.dates))
        train_idx = all_idx[dates[all_idx] <= train_end_date]
        val_idx = all_idx[
            (dates[all_idx] > train_end_date)
            & (dates[all_idx] <= validation_end_date)
        ]
        test_idx = all_idx[dates[all_idx] > validation_end_date]
        train_end = int(dates.searchsorted(train_end_date, side="right"))
        if min(len(train_idx), len(val_idx), len(test_idx)) == 0:
            raise ValueError("Date-based train/validation/test split contains an empty period")
    else:
        train_idx, val_idx, test_idx, train_end, _ = split_window_indices(
            len(bundle.dates), history, float(data_cfg.get("train_fraction", 0.7)), float(data_cfg.get("val_fraction", 0.15))
        )
    target_station_ids = list(data_cfg.get("target_station_ids", []))
    flow_feature = str(data_cfg.get("flow_feature", "obs_q"))
    norm = fit_normalization(
        bundle,
        train_end,
        target_station_ids=target_station_ids,
        flow_feature=flow_feature,
        mode=str(data_cfg.get("normalization_mode", "global")),
        reference_feature=data_cfg.get("normalization_reference_feature"),
    )
    common = dict(
        bundle=bundle,
        history=history,
        normalization=norm,
        flow_feature=flow_feature,
        target_station_ids=target_station_ids,
        input_feature_names=list(data_cfg.get("input_features", [])) or None,
        physics_reference_feature=data_cfg.get("physics_reference_feature"),
        output_reference_feature=data_cfg.get("output_reference_feature"),
        mask_target_input_features=list(data_cfg.get("mask_target_input_features", [])),
        current_snapshot=bool(data_cfg.get("current_snapshot", False)),
    )
    train_ds = WindowDataset(
        indices=train_idx,
        flow_dropout_probability=float(data_cfg.get("training_flow_dropout_probability", 0.0)),
        node_dropout_probability=float(data_cfg.get("training_node_dropout_probability", 0.0)),
        **common,
    )
    val_ds = WindowDataset(
        indices=val_idx,
        node_dropout_probability=float(data_cfg.get("validation_node_dropout_probability", 0.0)),
        **common,
    )
    test_ds = WindowDataset(indices=test_idx, **common)
    tr_cfg = cfg["training"]
    train_loader = _loader(train_ds, int(tr_cfg["batch_size"]), True, int(tr_cfg.get("num_workers", 0)))
    val_loader = _loader(val_ds, int(tr_cfg["batch_size"]), False, int(tr_cfg.get("num_workers", 0)))
    test_loader = _loader(test_ds, int(tr_cfg["batch_size"]), False, int(tr_cfg.get("num_workers", 0)))

    edge_index = torch.from_numpy(bundle.edge_index).long().to(device)
    edge_attr = torch.from_numpy(_edge_normalize(bundle.edge_attr)).float().to(device)
    model_cfg = cfg["model"]
    output_floor = None
    if bool(model_cfg.get("nonnegative_output", False)):
        floor = -np.asarray(norm.y_mean) / np.asarray(norm.y_std)
        output_floor = (
            float(floor)
            if floor.ndim == 0
            else torch.from_numpy(floor.reshape(-1).astype(np.float32)).to(device)
        )
    architecture = str(model_cfg.get("architecture", "stgnn"))
    common_model = dict(
        dynamic_dim=train_ds.x.shape[-1],
        static_dim=bundle.static.shape[-1],
        edge_dim=bundle.edge_attr.shape[-1],
        hidden_dim=int(model_cfg.get("hidden_dim", 64)),
        graph_layers=int(model_cfg.get("graph_layers", 2)),
        dropout=float(model_cfg.get("dropout", 0.1)),
        output_floor=output_floor,
        residual_output=bool(model_cfg.get("residual_output", False)),
        residual_scale=float(model_cfg.get("residual_scale", 1.0)),
    )
    if architecture == "snapshot_gnn":
        if not bool(data_cfg.get("current_snapshot", False)):
            raise ValueError("snapshot_gnn requires data.current_snapshot=true")
        model = DirectedSnapshotGNN(**common_model).to(device)
    elif architecture == "stgnn":
        model = DirectedSTGNN(
            **common_model,
            temporal_layers=int(model_cfg.get("temporal_layers", 1)),
        ).to(device)
    else:
        raise ValueError(f"Unknown model architecture: {architecture}")
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=float(tr_cfg.get("learning_rate", 1e-3)),
        weight_decay=float(tr_cfg.get("weight_decay", 1e-4)),
    )

    best_state, best_val, patience_count = None, float("inf"), 0
    history_rows = []
    for epoch in range(1, int(tr_cfg.get("epochs", 100)) + 1):
        model.train()
        losses = []
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            pred = model(
                batch["x"],
                batch["static"],
                edge_index,
                edge_attr,
                output_reference=batch.get("output_reference"),
            )
            loss = _loss_for_batch(
                pred,
                batch,
                training=True,
                physics_loss_weight=float(tr_cfg.get("physics_loss_weight", 0.0)),
            )
            if loss is None:
                continue
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach()))
        train_loss = float(np.mean(losses)) if losses else float("nan")
        val_loss, val_metrics, _ = evaluate(model, val_loader, edge_index, edge_attr, device, norm.y_mean, norm.y_std, target_only=False,)
        history_rows.append({"epoch": epoch, "train_loss": train_loss, "val_loss": val_loss, **{f"val_{k}": v for k, v in val_metrics.items()}})
        print(f"epoch={epoch:03d} train_mse={train_loss:.4f} val_mse={val_loss:.4f} val_nse={val_metrics['nse']:.3f}")
        criterion = val_loss if np.isfinite(val_loss) else train_loss
        if criterion < best_val:
            best_val = criterion
            best_state = copy.deepcopy(model.state_dict())
            patience_count = 0
        else:
            patience_count += 1
            if patience_count >= int(tr_cfg.get("patience", 12)):
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    torch.save({"model_state": model.state_dict(), "config": cfg}, output_dir / "best_model.pt")
    normalization_record = {
        "mode": str(data_cfg.get("normalization_mode", "global")),
        "reference_feature": data_cfg.get("normalization_reference_feature"),
        "x_mean": np.asarray(norm.x_mean).tolist(),
        "x_std": np.asarray(norm.x_std).tolist(),
        "static_mean": np.asarray(norm.static_mean).tolist(),
        "static_std": np.asarray(norm.static_std).tolist(),
        "y_mean": np.asarray(norm.y_mean).tolist(),
        "y_std": np.asarray(norm.y_std).tolist(),
        "target_station_ids": target_station_ids,
        "target_observations_used": False if target_station_ids else None,
    }
    with (output_dir / "normalization.json").open("w", encoding="utf-8") as f:
        json.dump(normalization_record, f, ensure_ascii=False, indent=2)
    pd.DataFrame(history_rows).to_csv(output_dir / "training_history.csv", index=False)
    _, metrics, predictions = evaluate(model, test_loader, edge_index, edge_attr, device, norm.y_mean, norm.y_std, target_only=True,)
    if not predictions.empty:
        predictions["date"] = [str(bundle.dates[int(i)]) for i in predictions.time_index]
        predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    with (output_dir / "test_metrics.json").open("w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    if len(model.graph_layers) > 0:
        empty_edge_index = torch.empty((2, 0), dtype=torch.long, device=device)
        empty_edge_attr = torch.empty(
            (0, bundle.edge_attr.shape[-1]), dtype=torch.float32, device=device
        )
        _, no_edge_metrics, no_edge_predictions = evaluate(
            model,
            test_loader,
            empty_edge_index,
            empty_edge_attr,
            device,
            norm.y_mean,
            norm.y_std,
            target_only=True,
        )
        if not no_edge_predictions.empty:
            no_edge_predictions["date"] = [
                str(bundle.dates[int(i)]) for i in no_edge_predictions.time_index
            ]
            no_edge_predictions.to_csv(
                output_dir / "test_predictions_no_edges.csv", index=False
            )
        with (output_dir / "test_metrics_no_edges.json").open("w", encoding="utf-8") as f:
            json.dump(no_edge_metrics, f, ensure_ascii=False, indent=2)
        edge_ablation = {
            "full_graph": metrics,
            "same_model_no_edges": no_edge_metrics,
            "nse_edge_contribution": metrics["nse"] - no_edge_metrics["nse"],
            "rmse_edge_contribution_m3s": no_edge_metrics["rmse"] - metrics["rmse"],
        }
        with (output_dir / "edge_ablation.json").open("w", encoding="utf-8") as f:
            json.dump(edge_ablation, f, ensure_ascii=False, indent=2)
    print(json.dumps({"device": device, "parameters": sum(p.numel() for p in model.parameters()), **metrics}, ensure_ascii=False, indent=2))
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    train_from_config(args.config)


if __name__ == "__main__":
    main()
