import torch

from vhs.regime_model import PartiallySharedRegimeSnapshotGNN


def make_model(graph_layers: int = 1):
    torch.manual_seed(11)
    return PartiallySharedRegimeSnapshotGNN(
        dynamic_dim=2,
        static_dim=1,
        edge_dim=1,
        hidden_dim=8,
        graph_layers=graph_layers,
        dropout=0.0,
        correction_scales={"natural": 5.0, "reservoir": 5.0, "agriculture": 5.0},
    )


def sample():
    return (
        torch.randn(2, 1, 3, 2),
        torch.zeros(3, 1),
        torch.tensor([[0, 1], [1, 2]], dtype=torch.long),
        torch.ones(2, 1),
        torch.tensor([0, 1, 2]),
        torch.tensor([[10.0, 20.0, 30.0], [11.0, 21.0, 31.0]]),
    )


def test_partial_model_closed_gate_returns_exact_reference():
    model = make_model().eval()
    x, static, edge_index, edge_attr, regimes, reference = sample()
    output = model(
        x, static, edge_index, edge_attr, regimes, reference, torch.zeros(3)
    )
    torch.testing.assert_close(output, reference, rtol=0, atol=0)


def test_regime_adapter_gradients_are_isolated_without_graph_edges():
    model = make_model(graph_layers=0)
    x, static, _, _, regimes, reference = sample()
    output = model(
        x[:1],
        static,
        torch.empty((2, 0), dtype=torch.long),
        torch.empty((0, 1)),
        regimes,
        reference[:1],
        torch.tensor([0.0, 1.0, 0.0]),
    )
    output[0, 1].backward()
    reservoir_grad = sum(
        float(parameter.grad.abs().sum())
        for parameter in model.adapters["reservoir"].parameters()
        if parameter.grad is not None
    )
    natural_grad = sum(
        float(parameter.grad.abs().sum())
        for parameter in model.adapters["natural"].parameters()
        if parameter.grad is not None
    )
    agriculture_grad = sum(
        float(parameter.grad.abs().sum())
        for parameter in model.adapters["agriculture"].parameters()
        if parameter.grad is not None
    )
    assert reservoir_grad > 0
    assert natural_grad == 0
    assert agriculture_grad == 0
