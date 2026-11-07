"""Dormant future adapter. R0 configuration rejects access BEFORE opening data.

No CLI is supplied. Enabling real execution requires a separately authorized
phase and reviewed configuration; this module is never invoked on real data in R0.
"""
from pathlib import Path
import csv
import hashlib
import numpy as np
from methods_v2 import Upstream, FitLabels, EvalLabels, days

def _gate(config, scoring=False):
    if config.get('phase') == 'VHS-NEXT-S1A-R0' or not config.get('real_execution_authorized', False):
        raise PermissionError('R0 real-data fit, prediction and scoring are prohibited')
    if scoring and not config.get('predictions_frozen_sha256'):
        raise PermissionError('Freeze predictions before opening development labels')

def _source(config, root):
    p = (Path(root) / config['input']['path']).resolve()
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != config['input']['sha256']:
        raise ValueError('Source hash mismatch')
    return p

def load_fit_views(config, root, fold):
    _gate(config)
    path = _source(config, root)
    ud, uq, td, tq = [], [], [], []
    with path.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            d = np.datetime64(row['date'][:10], 'D')
            if np.datetime64('1978-01-01') <= d <= fold.dev[-1]:
                ud.append(d)
                uq.append(float(row['Q_input_byblk']))
            # Explicitly do NOT parse dev target cells in this path.
            if fold.train[0] <= d <= fold.train[-1]:
                td.append(d)
                tq.append(float(row['Q_target_dsk']))
    up, labels = Upstream(ud,uq), FitLabels(td,tq)
    if not np.array_equal(up.dates, days('1978-01-01', str(fold.dev[-1]))):
        raise ValueError('Unexpected upstream source calendar')
    if not np.array_equal(labels.dates, fold.train):
        raise ValueError('Unexpected fit-label calendar')
    return up, labels

def load_evaluation_labels(config, root, fold, prediction_file):
    _gate(config, scoring=True)
    if hashlib.sha256(Path(prediction_file).read_bytes()).hexdigest() != config['predictions_frozen_sha256']:
        raise ValueError('Prediction freeze hash mismatch')
    path = _source(config, root)
    dd, qq = [], []
    with path.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            d = np.datetime64(row['date'][:10], 'D')
            if fold.dev[0] <= d <= fold.dev[-1]:
                dd.append(d)
                qq.append(float(row['Q_target_dsk']))
    if not np.array_equal(np.asarray(dd), fold.dev):
        raise ValueError('Unexpected development-label calendar')
    return EvalLabels(np.asarray(dd),np.asarray(qq))
