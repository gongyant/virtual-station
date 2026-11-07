from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from .model import DirectedMessageLayer


REGIME_NAMES = ("natural", "reservoir", "agriculture")


class RegimeAwareSnapshotGNN(nn.Module):
    """Shared same-time graph encoder with isolated regime-specific residual heads.

    Every head predicts only a bounded correction to an externally supplied physical
    reference. A per-node safety gate controls whether that correction may be used.
    With the gate closed, the output is exactly the physical reference, independent
    of neural-network weights.
    """

    def __init__(
        self,
        dynamic_dim: int,
        static_dim: int,
        edge_dim: int,
        hidden_dim: int = 64,
        graph_layers: int = 2,
        dropout: float = 0.1,
        correction_scales: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__()
        scales = dict(correction_scales or {})
        unknown = set(scales) - set(REGIME_NAMES)
        if unknown:
            raise ValueError(f"unknown regimes in correction_scales: {sorted(unknown)}")
        ordered_scales = [float(scales.get(name, 1.0)) for name in REGIME_NAMES]
        if any(value < 0 for value in ordered_scales):
            raise ValueError("correction scales must be non-negative")
        self.node_encoder = nn.Sequential(
            nn.Linear(dynamic_dim + static_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout),
        )
        self.graph_layers = nn.ModuleList(
            [DirectedMessageLayer(hidden_dim, edge_dim, dropout) for _ in range(graph_layers)]
        )
        self.heads = nn.ModuleDict(
            {
                name: nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim // 2),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim // 2, 1),
                )
                for name in REGIME_NAMES
            }
        )
        self.register_buffer(
            "correction_scales",
            torch.tensor(ordered_scales, dtype=torch.float32),
        )

    @staticmethod
    def _expand_node_tensor(
        value: torch.Tensor, batch: int, nodes: int, name: str
    ) -> torch.Tensor:
        if value.ndim == 1:
            if value.shape[0] != nodes:
                raise ValueError(f"{name} must have one value per node")
            return value.unsqueeze(0).expand(batch, -1)
        if value.ndim == 2 and value.shape == (batch, nodes):
            return value
        raise ValueError(f"{name} must have shape [nodes] or [batch, nodes]")

    def forward(
        self,
        x: torch.Tensor,
        static: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        regime_ids: torch.Tensor,
        output_reference: torch.Tensor,
        correction_enabled: torch.Tensor,
    ) -> torch.Tensor:
        if x.ndim != 4 or x.shape[1] != 1:
            raise ValueError("RegimeAwareSnapshotGNN requires x shaped [batch, 1, nodes, features]")
        batch, _, nodes, _ = x.shape
        if static.ndim == 2:
            static = static.unsqueeze(0).expand(batch, -1, -1)
        if static.shape[:2] != (batch, nodes):
            raise ValueError("static must align with batch and node dimensions")
        regime_ids = self._expand_node_tensor(regime_ids, batch, nodes, "regime_ids").long()
        reference = self._expand_node_tensor(
            output_reference, batch, nodes, "output_reference"
        ).to(dtype=x.dtype)
        gate = self._expand_node_tensor(
            correction_enabled, batch, nodes, "correction_enabled"
        ).to(dtype=x.dtype)
        if torch.any((regime_ids < 0) | (regime_ids >= len(REGIME_NAMES))):
            raise ValueError("regime_ids contain an unsupported regime")
        if torch.any((gate < 0) | (gate > 1)):
            raise ValueError("correction_enabled values must be in [0, 1]")
        if not torch.isfinite(reference).all():
            raise ValueError("output_reference must be finite")

        h = self.node_encoder(torch.cat([x[:, 0], static], dim=-1))
        for layer in self.graph_layers:
            h = layer(h, edge_index, edge_attr)
        raw_by_regime = torch.stack(
            [self.heads[name](h).squeeze(-1) for name in REGIME_NAMES], dim=-1
        )
        routed_raw = raw_by_regime.gather(-1, regime_ids.unsqueeze(-1)).squeeze(-1)
        scales = self.correction_scales.to(dtype=x.dtype)[regime_ids]
        bounded_correction = scales * torch.tanh(routed_raw)
        return torch.clamp_min(reference + gate * bounded_correction, 0.0)


def regime_id(name: str) -> int:
    try:
        return REGIME_NAMES.index(name)
    except ValueError as error:
        raise ValueError(f"unknown regime: {name}") from error


class PartiallySharedRegimeSnapshotGNN(nn.Module):
    """Regime-specific input adapters with a shared directed graph core.

    This variant prevents raw feature-scale and mechanism differences from being
    forced through one node encoder. Only the river-network message-passing core
    is shared; input adapters, output heads, correction bounds, and gates remain
    regime specific.
    """

    def __init__(
        self,
        dynamic_dim: int,
        static_dim: int,
        edge_dim: int,
        hidden_dim: int = 64,
        graph_layers: int = 2,
        dropout: float = 0.1,
        correction_scales: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__()
        scales = dict(correction_scales or {})
        unknown = set(scales) - set(REGIME_NAMES)
        if unknown:
            raise ValueError(f"unknown regimes in correction_scales: {sorted(unknown)}")
        ordered_scales = [float(scales.get(name, 1.0)) for name in REGIME_NAMES]
        if any(value < 0 for value in ordered_scales):
            raise ValueError("correction scales must be non-negative")
        input_dim = dynamic_dim + static_dim
        self.adapters = nn.ModuleDict(
            {
                name: nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.GELU(),
                    nn.LayerNorm(hidden_dim),
                    nn.Dropout(dropout),
                )
                for name in REGIME_NAMES
            }
        )
        self.graph_layers = nn.ModuleList(
            [DirectedMessageLayer(hidden_dim, edge_dim, dropout) for _ in range(graph_layers)]
        )
        self.heads = nn.ModuleDict(
            {
                name: nn.Sequential(
                    nn.Linear(hidden_dim, hidden_dim // 2),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_dim // 2, 1),
                )
                for name in REGIME_NAMES
            }
        )
        self.register_buffer(
            "correction_scales",
            torch.tensor(ordered_scales, dtype=torch.float32),
        )

    def forward(
        self,
        x: torch.Tensor,
        static: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        regime_ids: torch.Tensor,
        output_reference: torch.Tensor,
        correction_enabled: torch.Tensor,
    ) -> torch.Tensor:
        if x.ndim != 4 or x.shape[1] != 1:
            raise ValueError("PartiallySharedRegimeSnapshotGNN requires x shaped [batch, 1, nodes, features]")
        batch, _, nodes, _ = x.shape
        if static.ndim == 2:
            static = static.unsqueeze(0).expand(batch, -1, -1)
        if static.shape[:2] != (batch, nodes):
            raise ValueError("static must align with batch and node dimensions")
        regime_ids = RegimeAwareSnapshotGNN._expand_node_tensor(
            regime_ids, batch, nodes, "regime_ids"
        ).long()
        reference = RegimeAwareSnapshotGNN._expand_node_tensor(
            output_reference, batch, nodes, "output_reference"
        ).to(dtype=x.dtype)
        gate = RegimeAwareSnapshotGNN._expand_node_tensor(
            correction_enabled, batch, nodes, "correction_enabled"
        ).to(dtype=x.dtype)
        if torch.any((regime_ids < 0) | (regime_ids >= len(REGIME_NAMES))):
            raise ValueError("regime_ids contain an unsupported regime")
        if torch.any((gate < 0) | (gate > 1)):
            raise ValueError("correction_enabled values must be in [0, 1]")
        if not torch.isfinite(reference).all():
            raise ValueError("output_reference must be finite")

        inputs = torch.cat([x[:, 0], static], dim=-1)
        adapted = torch.stack(
            [self.adapters[name](inputs) for name in REGIME_NAMES], dim=2
        )
        gather_index = regime_ids.unsqueeze(-1).unsqueeze(-1).expand(
            -1, -1, 1, adapted.shape[-1]
        )
        h = adapted.gather(2, gather_index).squeeze(2)
        for layer in self.graph_layers:
            h = layer(h, edge_index, edge_attr)
        raw_by_regime = torch.stack(
            [self.heads[name](h).squeeze(-1) for name in REGIME_NAMES], dim=-1
        )
        routed_raw = raw_by_regime.gather(-1, regime_ids.unsqueeze(-1)).squeeze(-1)
        scales = self.correction_scales.to(dtype=x.dtype)[regime_ids]
        bounded_correction = scales * torch.tanh(routed_raw)
        return torch.clamp_min(reference + gate * bounded_correction, 0.0)
