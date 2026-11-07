import numpy as np
import pytest
import torch

from vhs.regime_model import REGIME_NAMES, RegimeAwareSnapshotGNN, regime_id


def make_model() -> RegimeAwareSnapshotGNN:
    torch.manual_seed(3)
    return RegimeAwareSnapshotGNN(
        dynamic_dim=2,
        static_dim=1,
        edge_dim=1,
        hidden_dim=8,
        graph_layers=1,
        dropout=0.0,
        correction_scales={name: 5.0 for name in REGIME_NAMES},
    )


def inputs():
    x = torch.randn(2, 1, 3, 2)
    static = torch.zeros(3, 1)
    edge_index = torch.tensor([[0, 1], [1, 2]], dtype=torch.long)
    edge_attr = torch.ones(2, 1)
    regimes = torch.tensor([0, 1, 2])
    reference = torch.tensor([[10.0, 20.0, 30.0], [11.0, 21.0, 31.0]])
    return x, static, edge_index, edge_attr, regimes, reference


def test_closed_safety_gate_returns_exact_reference():
    model = make_model().eval()
    x, static, edge_index, edge_attr, regimes, reference = inputs()
    output = model(
        x, static, edge_index, edge_attr, regimes, reference, torch.zeros(3)
    )
    torch.testing.assert_close(output, reference, rtol=0, atol=0)


def test_each_node_is_routed_only_to_its_regime_head():
    model = make_model().eval()
    biases = {"natural": 0.1, "reservoir": 0.2, "agriculture": -0.3}
    with torch.no_grad():
        for name, head in model.heads.items():
            for parameter in head.parameters():
                parameter.zero_()
            head[-1].bias.fill_(biases[name])
    x, static, edge_index, edge_attr, regimes, reference = inputs()
    output = model(
        x, static, edge_index, edge_attr, regimes, reference, torch.ones(3)
    )
    expected_correction = 5.0 * np.tanh([0.1, 0.2, -0.3])
    expected = reference + torch.tensor(expected_correction, dtype=reference.dtype)
    torch.testing.assert_close(output, expected)


def test_negative_output_is_clipped_at_physical_zero():
    model = RegimeAwareSnapshotGNN(1, 1, 1, hidden_dim=4, graph_layers=0, dropout=0.0, correction_scales={"natural": 100.0})
    with torch.no_grad():
        for parameter in model.heads["natural"].parameters():
            parameter.zero_()
        model.heads["natural"][-1].bias.fill_(-10.0)
    output = model(
        torch.zeros(1, 1, 1, 1),
        torch.zeros(1, 1),
        torch.empty(2, 0, dtype=torch.long),
        torch.empty(0, 1),
        torch.tensor([0]),
        torch.tensor([2.0]),
        torch.tensor([1.0]),
    )
    assert output.item() == 0.0


def test_invalid_regime_and_gate_are_rejected():
    model = make_model()
    x, static, edge_index, edge_attr, regimes, reference = inputs()
    with pytest.raises(ValueError, match="unsupported regime"):
        model(x, static, edge_index, edge_attr, torch.tensor([0, 1, 9]), reference, torch.zeros(3))
    with pytest.raises(ValueError, match="must be in"):
        model(x, static, edge_index, edge_attr, regimes, reference, torch.tensor([0.0, 1.2, 0.0]))


def test_regime_name_mapping_is_stable():
    assert regime_id("natural") == 0
    assert regime_id("reservoir") == 1
    assert regime_id("agriculture") == 2
    with pytest.raises(ValueError, match="unknown regime"):
        regime_id("unknown")
