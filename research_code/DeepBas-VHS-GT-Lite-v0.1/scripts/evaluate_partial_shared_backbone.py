from __future__ import annotations

import copy
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch

from scripts.evaluate_shared_backbone_negative_transfer import (
    SEEDS,
    TARGETS,
    balanced_regime_loss,
    evaluate_model,
    forward_indices,
    prepare,
    seed_everything,
)
from vhs.regime_model import PartiallySharedRegimeSnapshotGNN


PRIOR = Path("outputs/virtual_station_mainline/shared_backbone_negative_transfer_round")
OUTPUT = Path("outputs/virtual_station_mainline/partial_shared_backbone_round")


def make_partial_model(data: dict, seed: int) -> PartiallySharedRegimeSnapshotGNN:
    seed_everything(seed)
    bundle = data["bundle"]
    return PartiallySharedRegimeSnapshotGNN(
        dynamic_dim=data["dynamic"].shape[-1],
        static_dim=data["static"].shape[-1],
        edge_dim=bundle.edge_attr.shape[-1],
        hidden_dim=32,
        graph_layers=1,
        dropout=0.10,
        correction_scales=data["correction_scales"],
    )


def freeze_natural_branch(model: PartiallySharedRegimeSnapshotGNN) -> None:
    for module in [model.adapters["natural"], model.heads["natural"]]:
        for parameter in module.parameters():
            parameter.requires_grad = False


def train_partial_model(data: dict, seed: int) -> PartiallySharedRegimeSnapshotGNN:
    focus = list(TARGETS)
    model = make_partial_model(data, seed)
    freeze_natural_branch(model)
    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad],
        lr=2e-3,
        weight_decay=1e-4,
    )
    edge_index = torch.from_numpy(data["bundle"].edge_index).long()
    edge_attr = torch.from_numpy(data["bundle"].edge_attr).float()
    target_indices = data["target_indices"]
    target_scales = torch.from_numpy(data["target_scales"]).float()
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
            prediction = forward_indices(
                model, data, batch, edge_index, edge_attr, focus
            )
            target = torch.from_numpy(data["y"][batch]).float()
            loss = balanced_regime_loss(
                prediction, target, target_indices, target_scales
            )
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
                balanced_regime_loss(
                    prediction, target, target_indices, target_scales
                )
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


def main() -> None:
    data = prepare()
    existing = pd.read_csv(PRIOR / "negative_transfer_multiseed_metrics.csv")
    baseline = pd.read_csv(PRIOR / "physical_reference_test_metrics.csv")
    rows = []
    prediction_rows = []
    test_indices = np.arange(data["validation_end"], len(data["dates"]))
    for seed in SEEDS:
        model = train_partial_model(data, seed)
        metrics, prediction = evaluate_model(
            model, data, list(TARGETS), use_edges=True
        )
        no_edge_metrics, _ = evaluate_model(
            model, data, list(TARGETS), use_edges=False
        )
        for name in TARGETS:
            for architecture, score in [
                ("partial_shared", metrics[name]),
                ("partial_shared_no_edges", no_edge_metrics[name]),
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
                        "partial_shared_q": prediction[local_position, node_index],
                    }
                )
    partial = pd.DataFrame(rows)
    combined = pd.concat([existing, partial], ignore_index=True)
    aggregate = (
        combined.groupby(["regime", "architecture"])
        .agg(
            nse_mean=("nse", "mean"),
            nse_std=("nse", "std"),
            rmse_mean=("rmse", "mean"),
            rmse_std=("rmse", "std"),
        )
        .reset_index()
    )
    decisions = {}
    for name in TARGETS:
        table = aggregate.loc[aggregate.regime.eq(name)].set_index("architecture")
        partial_row = table.loc["partial_shared"]
        full_row = table.loc["shared_encoder"]
        separate_row = table.loc["separate_encoder"]
        no_edge_row = table.loc["partial_shared_no_edges"]
        negative_transfer = bool(
            partial_row.nse_mean < separate_row.nse_mean - 0.02
            and partial_row.rmse_mean > separate_row.rmse_mean * 1.02
        )
        decisions[name] = {
            "partial_minus_full_shared_nse": float(
                partial_row.nse_mean - full_row.nse_mean
            ),
            "partial_minus_separate_nse": float(
                partial_row.nse_mean - separate_row.nse_mean
            ),
            "partial_to_separate_rmse_ratio": float(
                partial_row.rmse_mean / separate_row.rmse_mean
            ),
            "negative_transfer_detected": negative_transfer,
            "partial_minus_no_edge_nse": float(
                partial_row.nse_mean - no_edge_row.nse_mean
            ),
            "shared_message_layer_supported": bool(
                partial_row.nse_mean > no_edge_row.nse_mean + 0.02
                and partial_row.rmse_mean < no_edge_row.rmse_mean * 0.98
            ),
        }
    partial_accepted = not any(
        item["negative_transfer_detected"] for item in decisions.values()
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    partial.to_csv(OUTPUT / "partial_shared_multiseed_metrics.csv", index=False)
    aggregate.to_csv(OUTPUT / "architecture_comparison_aggregate.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(
        OUTPUT / "partial_shared_test_predictions.csv", index=False
    )

    summary = {
        "status": "completed_partial_sharing_development_audit",
        "scope": "Post-opened 2005 structural audit; not a new blind validation.",
        "architecture": {
            "regime_specific": ["input adapters", "normalization inputs", "output heads", "correction bounds", "safety gates"],
            "shared": ["directed message-passing layer"],
            "natural_head_frozen": True,
        },
        "protocol": {
            "seeds": SEEDS,
            "same_dates_splits_and_loss_as_full_sharing_audit": True,
            "target_observations_masked_from_inputs": True,
        },
        "baseline_metrics": baseline.to_dict(orient="records"),
        "decisions": decisions,
        "partial_sharing_accepted_for_development": partial_accepted,
        "heads_promoted_for_operation": False,
        "decision": (
            "Regime-specific adapters removed material negative transfer. Retain partial sharing as the development architecture, while keeping operational gates closed."
            if partial_accepted
            else "Partial sharing still shows material negative transfer. Use fully separate encoders and combine only through the external safety router."
        ),
    }
    (OUTPUT / "partial_shared_backbone_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    figure, axes = plt.subplots(1, 2, figsize=(11.5, 4.8), constrained_layout=True)
    architectures = ["shared_encoder", "partial_shared", "separate_encoder"]
    colors = ["#64748b", "#2563eb", "#ea580c"]
    for axis, name in zip(axes, TARGETS):
        table = aggregate.loc[
            aggregate.regime.eq(name) & aggregate.architecture.isin(architectures)
        ].set_index("architecture").reindex(architectures)
        axis.bar(
            ["full shared", "partial shared", "separate"],
            table.nse_mean,
            yerr=table.nse_std.fillna(0.0),
            color=colors,
            capsize=4,
        )
        base_nse = float(baseline.loc[baseline.regime.eq(name), "nse"].iloc[0])
        axis.axhline(base_nse, color="#111827", linestyle="--", label="physical baseline")
        axis.axhline(0.0, color="#94a3b8", linewidth=0.8)
        axis.set(title=f"{name}: encoder sharing audit", ylabel="Mean test NSE (3 seeds)")
        axis.grid(axis="y", alpha=0.2)
        axis.legend(frameon=False)
    figure.savefig(OUTPUT / "partial_shared_architecture_comparison.png", dpi=180)
    plt.close(figure)

    report = f"""# 部分共享GNN骨架实验报告

本轮将完全共享节点编码器改成三个情景专用输入适配器，仅共享有向消息传播层，输出头、修正边界与安全门继续隔离。实验沿用上一轮相同日期、目标遮蔽、损失平衡和三个随机种子。

## 结果

- 水库：部分共享相对完全共享NSE变化={decisions['reservoir']['partial_minus_full_shared_nse']:.3f}；相对独立编码器NSE变化={decisions['reservoir']['partial_minus_separate_nse']:.3f}；负迁移={'是' if decisions['reservoir']['negative_transfer_detected'] else '否'}。
- 农业：部分共享相对完全共享NSE变化={decisions['agriculture']['partial_minus_full_shared_nse']:.3f}；相对独立编码器NSE变化={decisions['agriculture']['partial_minus_separate_nse']:.3f}；负迁移={'是' if decisions['agriculture']['negative_transfer_detected'] else '否'}。
- 部分共享结构是否保留：**{'是' if partial_accepted else '否'}**。

本轮属于已打开年份的结构审计，不启用任何业务修正门。
"""
    (OUTPUT / "partial_shared_backbone_report_zh.md").write_text(
        report, encoding="utf-8"
    )

    mainline_path = Path(
        "outputs/virtual_station_mainline/three_regime_round/three_regime_summary.json"
    )
    if mainline_path.exists():
        mainline = json.loads(mainline_path.read_text(encoding="utf-8"))
        record = mainline.setdefault("modeling_decision", {}).setdefault(
            "shared_backbone_implementation", {}
        )
        record.update(
            {
                "partial_sharing_audit": "completed",
                "partial_sharing_accepted_for_development": partial_accepted,
                "partial_sharing_summary": str(
                    OUTPUT / "partial_shared_backbone_summary.json"
                ),
            }
        )
        mainline_path.write_text(
            json.dumps(mainline, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
