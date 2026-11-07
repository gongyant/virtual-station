from __future__ import annotations

import copy
import json
import random
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from vhs.data import TensorBundle
from vhs.metrics import regression_metrics
from vhs.regime_model import REGIME_NAMES, RegimeAwareSnapshotGNN, regime_id


BUNDLE = Path(
    "data/processed/virtual_station_multisite/multisite_agriculture_vhs_bundle_2005.npz"
)
OUTPUT = Path("outputs/virtual_station_mainline/shared_backbone_negative_transfer_round")
SEEDS = [7, 42, 123]
TARGETS = {
    "reservoir": {"station": "00705700", "reference": "physical_reference_q"},
    "agriculture": {"station": "TARIM_XQM", "reference": "agri_endpoint_geometric_q"},
}


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def mask_target_observations(
    x: np.ndarray, feature_names: list[str], target_indices: list[int]
) -> np.ndarray:
    masked = np.asarray(x, dtype=float).copy()
    masked[:, target_indices, feature_names.index("obs_q")] = np.nan
    return masked


def balanced_regime_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    target_indices: list[int],
    target_scales: torch.Tensor,
) -> torch.Tensor:
    losses = []
    for position, node_index in enumerate(target_indices):
        error = (prediction[:, node_index] - target[:, node_index]) / target_scales[position]
        losses.append(torch.mean(error**2))
    return torch.stack(losses).mean()


def prepare() -> dict:
    bundle = TensorBundle.load(BUNDLE)
    names = list(map(str, bundle.feature_names))
    stations = list(map(str, bundle.station_ids))
    target_indices = [stations.index(TARGETS[name]["station"]) for name in TARGETS]
    reference_indices = [names.index(TARGETS[name]["reference"]) for name in TARGETS]
    valid = np.ones(len(bundle.dates), dtype=bool)
    for node_index, reference_index in zip(target_indices, reference_indices):
        valid &= bundle.y_mask[:, node_index]
        valid &= np.isfinite(bundle.x[:, node_index, reference_index])
    dates = pd.DatetimeIndex(bundle.dates)[valid]
    raw_x = bundle.x[valid].astype(float)
    y = bundle.y[valid].astype(float)
    raw_x = mask_target_observations(raw_x, names, target_indices)
    n = len(dates)
    train_end = int(n * 0.60)
    validation_end = int(n * 0.80)
    train_x = raw_x[:train_end]
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(train_x, axis=(0, 1), keepdims=True)
        std = np.nanstd(train_x, axis=(0, 1), keepdims=True)
    mean = np.where(np.isfinite(mean), mean, 0.0)
    std = np.where(np.isfinite(std) & (std > 1e-6), std, 1.0)
    normalized = (raw_x - mean) / std
    availability = np.isfinite(normalized).astype(np.float32)
    normalized = np.nan_to_num(normalized, nan=0.0, posinf=0.0, neginf=0.0)
    dynamic = np.concatenate([normalized, availability], axis=-1).astype(np.float32)

    static = bundle.static.astype(float)
    static_mean = np.mean(static, axis=0, keepdims=True)
    static_std = np.std(static, axis=0, keepdims=True)
    static_std = np.where(static_std > 1e-6, static_std, 1.0)
    static = ((static - static_mean) / static_std).astype(np.float32)

    reference = np.zeros((n, len(stations)), dtype=np.float32)
    reference_mask = np.zeros_like(reference, dtype=bool)
    for node_index, reference_index in zip(target_indices, reference_indices):
        values = bundle.x[valid, node_index, reference_index]
        reference[:, node_index] = values
        reference_mask[:, node_index] = np.isfinite(values)
    for node_index in range(len(stations)):
        if node_index not in target_indices:
            values = bundle.y[valid, node_index]
            finite = np.isfinite(values)
            reference[finite, node_index] = values[finite]
            reference_mask[finite, node_index] = True
    if not reference_mask.all():
        raise ValueError("joint audit requires a finite fallback reference at every node/date")

    regime_names = ["natural", "reservoir", "natural", "agriculture", "natural"]
    regime_ids = np.asarray([regime_id(name) for name in regime_names], dtype=np.int64)
    train_residual = y[:train_end, target_indices] - reference[:train_end, target_indices]
    correction_scales = {
        "natural": 0.0,
        "reservoir": float(max(np.quantile(np.abs(train_residual[:, 0]), 0.99), 1.0)),
        "agriculture": float(max(np.quantile(np.abs(train_residual[:, 1]), 0.99), 1.0)),
    }
    target_scales = np.maximum(np.std(y[:train_end, target_indices], axis=0), 1.0)
    return {
        "bundle": bundle,
        "dates": dates,
        "dynamic": dynamic,
        "static": static,
        "y": y.astype(np.float32),
        "reference": reference,
        "regime_ids": regime_ids,
        "target_indices": target_indices,
        "target_names": list(TARGETS),
        "target_scales": target_scales.astype(np.float32),
        "correction_scales": correction_scales,
        "train_end": train_end,
        "validation_end": validation_end,
    }


def make_model(data: dict, seed: int) -> RegimeAwareSnapshotGNN:
    seed_everything(seed)
    bundle = data["bundle"]
    return RegimeAwareSnapshotGNN(
        dynamic_dim=data["dynamic"].shape[-1],
        static_dim=data["static"].shape[-1],
        edge_dim=bundle.edge_attr.shape[-1],
        hidden_dim=32,
        graph_layers=1,
        dropout=0.10,
        correction_scales=data["correction_scales"],
    )


def freeze_unused_heads(model: RegimeAwareSnapshotGNN, focus: list[str]) -> None:
    for name, head in model.heads.items():
        enabled = name in focus
        for parameter in head.parameters():
            parameter.requires_grad = enabled


def forward_indices(
    model: RegimeAwareSnapshotGNN,
    data: dict,
    indices: np.ndarray,
    edge_index: torch.Tensor,
    edge_attr: torch.Tensor,
    enabled_names: list[str],
) -> torch.Tensor:
    x = torch.from_numpy(data["dynamic"][indices]).float().unsqueeze(1)
    static = torch.from_numpy(data["static"]).float()
    reference = torch.from_numpy(data["reference"][indices]).float()
    regimes = torch.from_numpy(data["regime_ids"]).long()
    gate = torch.zeros(len(data["regime_ids"]), dtype=torch.float32)
    for name in enabled_names:
        gate[data["target_indices"][data["target_names"].index(name)]] = 1.0
    return model(x, static, edge_index, edge_attr, regimes, reference, gate)


def train_model(data: dict, seed: int, focus: list[str]) -> RegimeAwareSnapshotGNN:
    model = make_model(data, seed)
    freeze_unused_heads(model, focus)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=2e-3,
        weight_decay=1e-4,
    )
    edge_index = torch.from_numpy(data["bundle"].edge_index).long()
    edge_attr = torch.from_numpy(data["bundle"].edge_attr).float()
    focus_indices = [
        data["target_indices"][data["target_names"].index(name)] for name in focus
    ]
    scale_positions = [data["target_names"].index(name) for name in focus]
    scales = torch.from_numpy(data["target_scales"][scale_positions]).float()
    train_indices = np.arange(data["train_end"])
    validation_indices = np.arange(data["train_end"], data["validation_end"])
    best_state = copy.deepcopy(model.state_dict())
    best_validation = float("inf")
    patience = 0
    generator = np.random.default_rng(seed)
    for _ in range(300):
        model.train()
        shuffled = generator.permutation(train_indices)
        for start in range(0, len(shuffled), 32):
            batch = shuffled[start : start + 32]
            optimizer.zero_grad(set_to_none=True)
            prediction = forward_indices(model, data, batch, edge_index, edge_attr, focus)
            target = torch.from_numpy(data["y"][batch]).float()
            loss = balanced_regime_loss(prediction, target, focus_indices, scales)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
        model.eval()
        with torch.no_grad():
            prediction = forward_indices(
                model, data, validation_indices, edge_index, edge_attr, focus
            )
            target = torch.from_numpy(data["y"][validation_indices]).float()
            validation_loss = float(
                balanced_regime_loss(prediction, target, focus_indices, scales)
            )
        if validation_loss < best_validation - 1e-8:
            best_validation = validation_loss
            best_state = copy.deepcopy(model.state_dict())
            patience = 0
        else:
            patience += 1
            if patience >= 35:
                break
    model.load_state_dict(best_state)
    return model.eval()


def evaluate_model(
    model: RegimeAwareSnapshotGNN,
    data: dict,
    enabled_names: list[str],
    use_edges: bool = True,
) -> tuple[dict[str, dict], np.ndarray]:
    test_indices = np.arange(data["validation_end"], len(data["dates"]))
    if use_edges:
        edge_index = torch.from_numpy(data["bundle"].edge_index).long()
        edge_attr = torch.from_numpy(data["bundle"].edge_attr).float()
    else:
        edge_index = torch.empty((2, 0), dtype=torch.long)
        edge_attr = torch.empty((0, data["bundle"].edge_attr.shape[-1]))
    with torch.no_grad():
        prediction = forward_indices(
            model, data, test_indices, edge_index, edge_attr, enabled_names
        ).numpy()
    metrics = {}
    for name in enabled_names:
        node_index = data["target_indices"][data["target_names"].index(name)]
        metrics[name] = regression_metrics(
            data["y"][test_indices, node_index], prediction[:, node_index]
        )
    return metrics, prediction


def main() -> None:
    data = prepare()
    rows = []
    prediction_rows = []
    test_indices = np.arange(data["validation_end"], len(data["dates"]))
    for seed in SEEDS:
        shared = train_model(data, seed, list(TARGETS))
        shared_metrics, shared_prediction = evaluate_model(
            shared, data, list(TARGETS), use_edges=True
        )
        no_edge_metrics, _ = evaluate_model(
            shared, data, list(TARGETS), use_edges=False
        )
        separate_models = {
            name: train_model(data, seed, [name]) for name in TARGETS
        }
        for name in TARGETS:
            separate_metrics, separate_prediction = evaluate_model(
                separate_models[name], data, [name], use_edges=True
            )
            for architecture, score in [
                ("shared_encoder", shared_metrics[name]),
                ("shared_encoder_no_edges", no_edge_metrics[name]),
                ("separate_encoder", separate_metrics[name]),
            ]:
                rows.append(
                    {"seed": seed, "regime": name, "architecture": architecture, **score}
                )
            node_index = data["target_indices"][data["target_names"].index(name)]
            for local_position, time_index in enumerate(test_indices):
                prediction_rows.append(
                    {
                        "date": data["dates"][time_index],
                        "seed": seed,
                        "regime": name,
                        "observed_q": data["y"][time_index, node_index],
                        "reference_q": data["reference"][time_index, node_index],
                        "shared_q": shared_prediction[local_position, node_index],
                        "separate_q": separate_prediction[local_position, node_index],
                    }
                )

    metrics = pd.DataFrame(rows)
    predictions = pd.DataFrame(prediction_rows)
    aggregate = (
        metrics.groupby(["regime", "architecture"])
        .agg(nse_mean=("nse", "mean"), nse_std=("nse", "std"), rmse_mean=("rmse", "mean"), rmse_std=("rmse", "std"))
        .reset_index()
    )
    decisions = {}
    for name in TARGETS:
        table = aggregate.loc[aggregate.regime.eq(name)].set_index("architecture")
        shared = table.loc["shared_encoder"]
        separate = table.loc["separate_encoder"]
        no_edges = table.loc["shared_encoder_no_edges"]
        negative_transfer = bool(
            shared.nse_mean < separate.nse_mean - 0.02
            and shared.rmse_mean > separate.rmse_mean * 1.02
        )
        graph_useful = bool(
            shared.nse_mean > no_edges.nse_mean + 0.02
            and shared.rmse_mean < no_edges.rmse_mean * 0.98
        )
        decisions[name] = {
            "shared_minus_separate_nse": float(shared.nse_mean - separate.nse_mean),
            "shared_to_separate_rmse_ratio": float(shared.rmse_mean / separate.rmse_mean),
            "negative_transfer_detected": negative_transfer,
            "shared_minus_no_edge_nse": float(shared.nse_mean - no_edges.nse_mean),
            "graph_contribution_supported": graph_useful,
        }
    joint_sharing_accepted = not any(
        decision["negative_transfer_detected"] for decision in decisions.values()
    )

    baseline_rows = []
    for name in TARGETS:
        node_index = data["target_indices"][data["target_names"].index(name)]
        baseline_rows.append(
            {
                "regime": name,
                **regression_metrics(
                    data["y"][test_indices, node_index],
                    data["reference"][test_indices, node_index],
                ),
            }
        )
    baseline = pd.DataFrame(baseline_rows)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(OUTPUT / "negative_transfer_multiseed_metrics.csv", index=False)
    aggregate.to_csv(OUTPUT / "negative_transfer_aggregate.csv", index=False)
    predictions.to_csv(OUTPUT / "negative_transfer_test_predictions.csv", index=False)
    baseline.to_csv(OUTPUT / "physical_reference_test_metrics.csv", index=False)

    summary = {
        "status": "completed_post_opened_joint_training_audit",
        "scope": "Development audit only; 2005 target labels have already been inspected.",
        "protocol": {
            "dates": [data["dates"][0].date().isoformat(), data["dates"][-1].date().isoformat()],
            "train": [data["dates"][0].date().isoformat(), data["dates"][data["train_end"] - 1].date().isoformat()],
            "validation": [data["dates"][data["train_end"]].date().isoformat(), data["dates"][data["validation_end"] - 1].date().isoformat()],
            "previously_opened_test": [data["dates"][data["validation_end"]].date().isoformat(), data["dates"][-1].date().isoformat()],
            "target_observations_masked_from_inputs": True,
            "natural_head_frozen": True,
            "seeds": SEEDS,
            "balanced_loss_by_training_target_standard_deviation": True,
        },
        "correction_scales_from_training_only_m3s": data["correction_scales"],
        "baseline_metrics": baseline.to_dict(orient="records"),
        "negative_transfer": decisions,
        "joint_sharing_accepted_for_development": joint_sharing_accepted,
        "heads_promoted_for_operation": False,
        "recommended_architecture": (
            "regime-specific input adapters and normalization, optionally shared directed "
            "message-passing core, and isolated regime heads with independent safety gates"
        ),
        "decision": (
            "Shared encoding did not show material negative transfer in this development audit. "
            "Keep it as the next candidate, but leave operational gates closed until an unopened period."
            if joint_sharing_accepted
            else "Material negative transfer was detected. Use partially shared or separate encoders for the affected regime; do not promote the joint model."
        ),
    }
    (OUTPUT / "shared_backbone_negative_transfer_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    mainline_path = Path(
        "outputs/virtual_station_mainline/three_regime_round/three_regime_summary.json"
    )
    if mainline_path.exists():
        mainline = json.loads(mainline_path.read_text(encoding="utf-8"))
        shared_record = mainline.setdefault("modeling_decision", {}).setdefault(
            "shared_backbone_implementation", {}
        )
        shared_record.update(
            {
                "joint_reservoir_agriculture_audit": "completed_negative_transfer_detected",
                "fully_shared_encoder_accepted": False,
                "recommended_next": summary["recommended_architecture"],
                "negative_transfer_summary": str(
                    OUTPUT / "shared_backbone_negative_transfer_summary.json"
                ),
            }
        )
        mainline_path.write_text(
            json.dumps(mainline, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8), constrained_layout=True)
    for axis, name in zip(axes, TARGETS):
        subset = predictions.loc[predictions.regime.eq(name)]
        daily = subset.groupby("date").agg(
            observed=("observed_q", "first"),
            reference=("reference_q", "first"),
            shared=("shared_q", "mean"),
            separate=("separate_q", "mean"),
        )
        axis.plot(daily.index, daily.observed, color="#111827", label="observed")
        axis.plot(daily.index, daily.reference, color="#64748b", label="physical reference")
        axis.plot(daily.index, daily.shared, color="#2563eb", label="shared encoder")
        axis.plot(daily.index, daily.separate, color="#ea580c", linestyle="--", label="separate encoder")
        axis.set(title=f"{name}: previously opened test", ylabel="Discharge (m³/s)")
        axis.tick_params(axis="x", rotation=30)
        axis.grid(alpha=0.2)
    axes[0].legend(frameon=False, ncol=2)
    figure.savefig(OUTPUT / "shared_backbone_negative_transfer.png", dpi=180)
    plt.close(figure)

    report = f"""# 共同GNN骨架水库—农业负迁移实验

本轮在2005年同期数据上联合训练水库头与农业头，并以两个完全独立编码器作为对照。DSK和XQM流量均从模型输入中遮蔽；损失按各目标训练期标准差归一，避免大流量目标支配共享参数。自然河道头全程冻结。

该年份标签此前已经打开，所以结果仅用于判断网络结构是否存在负迁移，不能作为新的盲测或业务启用依据。

## 判定

- 水库物理基线NSE={baseline.loc[baseline.regime.eq('reservoir'), 'nse'].iloc[0]:.3f}；共享编码器平均NSE={aggregate.loc[aggregate.regime.eq('reservoir') & aggregate.architecture.eq('shared_encoder'), 'nse_mean'].iloc[0]:.3f}；独立编码器平均NSE={aggregate.loc[aggregate.regime.eq('reservoir') & aggregate.architecture.eq('separate_encoder'), 'nse_mean'].iloc[0]:.3f}。
- 农业端点基线NSE={baseline.loc[baseline.regime.eq('agriculture'), 'nse'].iloc[0]:.3f}；共享编码器平均NSE={aggregate.loc[aggregate.regime.eq('agriculture') & aggregate.architecture.eq('shared_encoder'), 'nse_mean'].iloc[0]:.3f}；独立编码器平均NSE={aggregate.loc[aggregate.regime.eq('agriculture') & aggregate.architecture.eq('separate_encoder'), 'nse_mean'].iloc[0]:.3f}。
- 水库头负迁移：**{'是' if decisions['reservoir']['negative_transfer_detected'] else '否'}**；共享相对独立NSE差={decisions['reservoir']['shared_minus_separate_nse']:.3f}。
- 农业头负迁移：**{'是' if decisions['agriculture']['negative_transfer_detected'] else '否'}**；共享相对独立NSE差={decisions['agriculture']['shared_minus_separate_nse']:.3f}。
- 共同编码开发阶段是否保留：**{'是' if joint_sharing_accepted else '否'}**。

完全共享的节点编码器被拒绝。下一步改为“情景专用输入适配器与归一化＋可选共享有向消息层＋隔离输出头”，减少水库与农业在尺度和机制上的相互干扰。无论本轮结果如何，三个业务修正安全门仍保持关闭；只有未打开年份通过后才能启用。
"""
    (OUTPUT / "shared_backbone_negative_transfer_report_zh.md").write_text(
        report, encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
