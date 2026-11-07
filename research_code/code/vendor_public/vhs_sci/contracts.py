"""Typed, label-separated contracts and deterministic content identities."""
import public_runtime
from dataclasses import dataclass
import hashlib
import json
import math
import numpy as np
TASK = 'HISTORICAL_MISSING_RECONSTRUCTION'
GROUP_A = 'UPSTREAM_AVAILABLE_RECONSTRUCTION'
GROUP_B = 'NO_UPSTREAM_Q_ARCHIVE_RECONSTRUCTION'
MODELS_A = ('E0', 'C0', 'E1a', 'E1b', 'E2', 'E3', 'E3n')
MODELS_B = ('C0', 'E3n')

class ScienceError(Exception):

    def __init__(self, code, message='', status=409):
        super().__init__(f'{code}: {message}')
        self.code, self.status = (code, status)

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)

def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()

def ids_hash(ids):
    return digest(sorted(ids))

@dataclass(frozen=True, order=True)
class SampleKey:
    dataset_id: str
    snapshot_id: str
    station_id: str
    year: int
    month: int

    def __post_init__(self):
        if not isinstance(self.year, int) or not 1 <= self.month <= 12:
            raise ScienceError('INVALID_CALENDAR_KEY')
        if not self.station_id.startswith(self.dataset_id + ':'):
            raise ScienceError('NAMESPACE_MISMATCH')

    @property
    def sample_id(self):
        return f'{self.station_id}:{self.year:04d}-{self.month:02d}'

@dataclass(frozen=True)
class FeatureBatch:
    keys: tuple
    columns: dict
    synthetic: bool = False
    authorization_status: str = 'PUBLIC_DATA_REAL_EXPERIMENT'

    def __post_init__(self):
        if not self.keys or len({k.sample_id for k in self.keys}) != len(self.keys):
            raise ScienceError('EMPTY_OR_DUPLICATE_BATCH')
        if len({(k.dataset_id, k.snapshot_id) for k in self.keys}) != 1:
            raise ScienceError('DATASET_SNAPSHOT_MISMATCH')
        for v in self.columns.values():
            if np.asarray(v).shape != (len(self.keys),):
                raise ScienceError('COLUMN_LENGTH_MISMATCH')

    def require_synthetic(self):
        public_runtime.admit_batch(self)

    def take(self, ids):
        wanted = set(ids)
        idx = [i for i, k in enumerate(self.keys) if k.sample_id in wanted]
        if len(idx) != len(wanted):
            raise ScienceError('UNKNOWN_SAMPLE_ID')
        return FeatureBatch(tuple((self.keys[i] for i in idx)), {k: np.asarray(v)[idx].copy() for k, v in self.columns.items()}, self.synthetic, self.authorization_status)

    def select(self, fields):
        if not set(fields) <= set(self.columns):
            raise ScienceError('MISSING_FEATURE', str(set(fields) - set(self.columns)))
        return FeatureBatch(self.keys, {k: np.asarray(self.columns[k]).copy() for k in fields}, self.synthetic, self.authorization_status)

    @property
    def ids(self):
        return tuple((k.sample_id for k in self.keys))

    @property
    def years(self):
        return np.array([k.year for k in self.keys])

    @property
    def months(self):
        return np.array([k.month for k in self.keys])

@dataclass(frozen=True)
class TrainingBatch:
    features: FeatureBatch
    labels: np.ndarray

    def __post_init__(self):
        self.features.require_synthetic()
        if np.asarray(self.labels).shape != (len(self.features.keys),) or not np.isfinite(self.labels).all():
            raise ScienceError('INVALID_TRAINING_LABELS')
        if (np.asarray(self.labels) < 0).any():
            raise ScienceError('NEGATIVE_TRAINING_DISCHARGE')
        public_runtime.admit_training(self)

@dataclass(frozen=True)
class PredictionBatch:
    keys: tuple
    raw: np.ndarray
    constrained: np.ndarray
    model_id: str
    train_ids_hash: str
    synthetic: bool = False
    constraint_rule: str = 'PRIMARY_RAW_SECONDARY_MAX_ZERO'

    def __post_init__(self):
        if self.raw.shape != (len(self.keys),) or not np.isfinite(self.raw).all():
            raise ScienceError('NONFINITE_PREDICTION')
        if not np.array_equal(self.constrained, np.maximum(self.raw, 0)):
            raise ScienceError('CONSTRAINT_RULE_MISMATCH')
