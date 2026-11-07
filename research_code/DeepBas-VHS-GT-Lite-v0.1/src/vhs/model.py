from __future__ import annotations

import torch
from torch import nn
from torch.nn import functional as F


class DirectedMessageLayer(nn.Module):
    """Upstream-to-downstream message passing using edge_index[0] -> edge_index[1]."""

    def __init__(self, hidden_dim: int, edge_dim: int, dropout: float) -> None:
        super().__init__()
        self.self_linear = nn.Linear(hidden_dim, hidden_dim)
        self.msg_linear = nn.Linear(hidden_dim, hidden_dim, bias=False)
        self.edge_gate = nn.Sequential(nn.Linear(edge_dim, hidden_dim), nn.Sigmoid())
        self.norm = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.activation = nn.GELU()

    def forward(self, h: torch.Tensor, edge_index: torch.Tensor, edge_attr: torch.Tensor) -> torch.Tensor:
        # h: [batch, nodes, hidden]
        source, target = edge_index[0], edge_index[1]
        messages = self.msg_linear(h[:, source, :]) * self.edge_gate(edge_attr).unsqueeze(0)
        agg = torch.zeros_like(h)
        agg.index_add_(1, target, messages)
        degree = torch.zeros(h.shape[1], device=h.device, dtype=h.dtype)
        degree.index_add_(0, target, torch.ones_like(target, dtype=h.dtype))
        agg = agg / degree.clamp_min(1.0).view(1, -1, 1)
        update = self.activation(self.self_linear(h) + agg)
        return self.norm(h + self.dropout(update))


class DirectedSTGNN(nn.Module):
    def __init__(
        self,
        dynamic_dim: int,
        static_dim: int,
        edge_dim: int,
        hidden_dim: int = 64,
        temporal_layers: int = 1,
        graph_layers: int = 2,
        dropout: float = 0.1,
        output_floor: float | None = None,
        residual_output: bool = False,
        residual_scale: float = 1.0,
    ) -> None:
        super().__init__()
        self.temporal = nn.GRU(
            input_size=dynamic_dim + static_dim,
            hidden_size=hidden_dim,
            num_layers=temporal_layers,
            dropout=dropout if temporal_layers > 1 else 0.0,
            batch_first=True,
        )
        self.graph_layers = nn.ModuleList(
            [DirectedMessageLayer(hidden_dim, edge_dim, dropout) for _ in range(graph_layers)]
        )
        self.output_floor = output_floor
        self.residual_output = residual_output
        self.residual_scale = float(residual_scale)
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(
        self,
        x: torch.Tensor,
        static: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        output_reference: torch.Tensor | None = None,
    ) -> torch.Tensor:
        # x [B, history, N, F], static [B, N, S] or [N, S]
        if static.ndim == 2:
            static = static.unsqueeze(0).expand(x.shape[0], -1, -1)
        static_time = static.unsqueeze(1).expand(-1, x.shape[1], -1, -1)
        z = torch.cat([x, static_time], dim=-1)
        batch, history, nodes, features = z.shape
        z = z.permute(0, 2, 1, 3).reshape(batch * nodes, history, features)
        _, hidden = self.temporal(z)
        h = hidden[-1].reshape(batch, nodes, -1)
        for layer in self.graph_layers:
            h = layer(h, edge_index, edge_attr)
        raw_output = self.decoder(h).squeeze(-1)
        if self.residual_output:
            if output_reference is None:
                raise ValueError("Residual output mode requires an output reference")
            output = output_reference + self.residual_scale * torch.tanh(raw_output)
        else:
            output = raw_output
        if self.output_floor is not None:
            if self.residual_output:
                # A residual model must preserve an already-valid physical
                # reference when the learned correction is zero. Softplus here
                # would add a systematic positive offset even at zero residual.
                output = torch.maximum(output, torch.as_tensor(self.output_floor, device=output.device, dtype=output.dtype))
            else:
                output = self.output_floor + F.softplus(output - self.output_floor)
        return output


class DirectedSnapshotGNN(nn.Module):
    """Directed graph reconstruction from one same-time river-network snapshot.

    This model intentionally has no recurrent or temporal encoder. It is used for
    virtual-station state reconstruction: observed nodes and a physical reference
    at time ``t`` are propagated across the river graph to reconstruct masked nodes
    at the same time ``t``.
    """

    def __init__(
        self,
        dynamic_dim: int,
        static_dim: int,
        edge_dim: int,
        hidden_dim: int = 64,
        graph_layers: int = 2,
        dropout: float = 0.1,
        output_floor: float | torch.Tensor | None = None,
        residual_output: bool = False,
        residual_scale: float = 1.0,
    ) -> None:
        super().__init__()
        self.node_encoder = nn.Sequential(
            nn.Linear(dynamic_dim + static_dim, hidden_dim),
            nn.GELU(),
            nn.LayerNorm(hidden_dim),
            nn.Dropout(dropout),
        )
        self.graph_layers = nn.ModuleList(
            [DirectedMessageLayer(hidden_dim, edge_dim, dropout) for _ in range(graph_layers)]
        )
        self.output_floor = output_floor
        self.residual_output = residual_output
        self.residual_scale = float(residual_scale)
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(
        self,
        x: torch.Tensor,
        static: torch.Tensor,
        edge_index: torch.Tensor,
        edge_attr: torch.Tensor,
        output_reference: torch.Tensor | None = None,
    ) -> torch.Tensor:
        if x.shape[1] != 1:
            raise ValueError("Snapshot model requires exactly one same-time graph snapshot")
        if static.ndim == 2:
            static = static.unsqueeze(0).expand(x.shape[0], -1, -1)
        h = self.node_encoder(torch.cat([x[:, 0], static], dim=-1))
        for layer in self.graph_layers:
            h = layer(h, edge_index, edge_attr)
        raw_output = self.decoder(h).squeeze(-1)
        if self.residual_output:
            if output_reference is None:
                raise ValueError("Residual output mode requires an output reference")
            output = output_reference + self.residual_scale * torch.tanh(raw_output)
        else:
            output = raw_output
        if self.output_floor is not None:
            if self.residual_output:
                output = torch.maximum(
                    output,
                    torch.as_tensor(
                        self.output_floor, device=output.device, dtype=output.dtype
                    ),
                )
            else:
                output = self.output_floor + F.softplus(output - self.output_floor)
        return output
