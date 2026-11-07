"""Boundary and leakage invariants used by runner and tests."""
import numpy as np
from .contracts import ScienceError, TrainingBatch, digest


def enforce_fold(train, test, fold):
    if set(train.ids) != set(fold.train_ids) or set(test.ids) != set(fold.test_ids):
        raise ScienceError("BATCH_FOLD_IDS_MISMATCH")
    if set(train.ids) & set(test.ids) or set(train.years.tolist()) & set(test.years.tolist()):
        raise ScienceError("TRAIN_TEST_OVERLAP")
    if (train.keys[0].dataset_id, train.keys[0].snapshot_id) != (test.keys[0].dataset_id, test.keys[0].snapshot_id):
        raise ScienceError("DATASET_SNAPSHOT_MISMATCH")


def select_model_features(features, model):
    return features.select(model.required_fields)


def target_label_invariance(factory, train_x, train_y, test_x, test_y):
    """Refit independently after changing only evaluation labels; predict has no y argument."""
    first = factory().fit(TrainingBatch(train_x, train_y.copy()))
    p1 = first.predict(test_x).raw.copy()
    mutated_labels = np.asarray(test_y) * 987.0 + 12345.0
    second = factory().fit(TrainingBatch(train_x, train_y.copy()))
    p2 = second.predict(test_x).raw.copy()
    if not np.array_equal(p1, p2):
        raise ScienceError("HELD_OUT_LABEL_INVARIANCE_FAILED")
    return {"status": "PASS", "prediction_exact_equal": True,
            "original_test_label_hash": digest(np.asarray(test_y).tolist()),
            "mutated_test_label_hash": digest(mutated_labels.tolist()),
            "original_prediction_hash": digest(p1.tolist()), "mutated_prediction_hash": digest(p2.tolist()),
            "labels_are_not_predict_arguments": True}
