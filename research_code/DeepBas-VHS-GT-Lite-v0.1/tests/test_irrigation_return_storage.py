import numpy as np
import pytest

from scripts.evaluate_irrigation_return_storage import return_storage


def test_return_storage_is_causal_and_nonnegative():
    loss = np.array([10.0, 0.0, 0.0, 0.0])
    storage, release = return_storage(loss, 0.9)
    assert np.all(storage >= 0)
    assert np.all(release >= 0)
    assert np.all(np.diff(storage) < 0)
    changed = loss.copy()
    changed[-1] = 1000.0
    modified, _ = return_storage(changed, 0.9)
    assert np.allclose(storage[:-1], modified[:-1])


def test_return_storage_rejects_invalid_memory():
    with pytest.raises(ValueError, match="rho"):
        return_storage(np.array([1.0]), 1.0)
