"""Trusted whitelist splitter and separate evaluation reader.

Fitting workers receive exported feature/train views only. The trusted CSV
splitter necessarily sees raw strings but converts only authorized fit labels.
No target history is exported as a model input. This is procedural isolation,
not a security sandbox against arbitrary Python or a human with file access.
"""
import csv
import re
import numpy as np
from common import HERE, ROOT, load, verify_freeze, write_csv, read_csv, sha, dump, event
from methods_v2 import Fold, days, Upstream, FitLabels, EvalLabels, values

def source_rows(config):
    p=ROOT/config['input']['path']
    if sha(p)!=config['input']['sha256']: raise ValueError('Input hash mismatch')
    with p.open(encoding='utf-8-sig',newline='') as f:
        r=csv.reader(f)
        header=next(r)
        names=config['input']['parse_allowlist']
        if any(header.count(n)!=1 for n in names): raise ValueError('Whitelist columns missing or duplicated')
        idx=[header.index(n) for n in names]
        for row in r:
            if len(row)!=len(header): raise ValueError('Malformed input row')
            date,u,y=[row[i] for i in idx]
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',date): raise ValueError('Unexpected date format')
            # No other columns are yielded, interpreted or used as features.
            yield np.datetime64(date,'D'),u,y

def split_fit_views():
    frozen=verify_freeze(); cfg=load(HERE/'execution_config.json')
    out=HERE/'views'
    out.mkdir(exist_ok=False)
    upstream=[]; train={y:[] for y in (1981,1982,1983)}; seen=[]
    for d,u,y in source_rows(cfg):
        seen.append(d)
        upstream.append({'date':str(d),'Q_input_byblk':float(u)})
        # A date may be dev for F1981 but legal train for F1982/F1983.
        # Roles are always fold-specific; F1983 dev values are never converted here.
        for year in train:
            f=Fold(year)
            if f.train[0]<=d<=f.train[-1]:
                train[year].append({'date':str(d),'Q_target_dsk':float(y)})
    expected=days('1978-01-01','1983-12-31')
    if not np.array_equal(np.asarray(seen),expected): raise ValueError('Unexpected/duplicate/missing/reordered source dates')
    values([r['Q_input_byblk'] for r in upstream],len(expected))
    write_csv(out/'feature_view.csv',upstream)
    for year,rows in train.items():
        if not np.array_equal(np.array([r['date'] for r in rows],dtype='datetime64[D]'),Fold(year).train):
            raise ValueError('Train label role mismatch')
        values([r['Q_target_dsk'] for r in rows],len(rows))
        write_csv(out/f'fit_labels_F{year}.csv',rows)
    files={p.relative_to(ROOT).as_posix():sha(p) for p in out.glob('*.csv')}
    dump(HERE/'views_manifest.json',{'files':files,'source_sha256':cfg['input']['sha256'],
        'feature_columns':['date','Q_input_byblk'],'train_columns':['date','Q_target_dsk'],
        'evaluation_values_exported':False,'ownpast_input_exported':False},exclusive=True)
    event('SPLIT_FIT_VIEWS',source_sha256=cfg['input']['sha256'],source_n=len(expected),
          roles='upstream features only; each fold train DSK only; no evaluation view',
          train_counts={str(y):len(v) for y,v in train.items()},code_hashes=frozen['frozen_hashes'])

def load_fit_view(year):
    vm=load(HERE/'views_manifest.json')
    for k,v in vm['files'].items():
        if sha(ROOT/k)!=v: raise RuntimeError('View hash mismatch')
    rows=read_csv(HERE/'views/feature_view.csv')
    up=Upstream(np.array([r['date'] for r in rows],dtype='datetime64[D]'),[float(r['Q_input_byblk']) for r in rows])
    rows=read_csv(HERE/f'views/fit_labels_F{year}.csv')
    labels=FitLabels(np.array([r['date'] for r in rows],dtype='datetime64[D]'),[float(r['Q_target_dsk']) for r in rows])
    if not np.array_equal(labels.dates,Fold(year).train): raise ValueError('Invalid label role')
    return up,labels

def evaluation_views():
    frozen=verify_freeze()
    seal=load(HERE/'prediction_freeze.json')
    for k,v in seal['files'].items():
        if sha(ROOT/k)!=v: raise RuntimeError('Prediction freeze mismatch')
    if not seal['all_folds_predictions_saved_before_evaluation']: raise RuntimeError('Premature evaluation access')
    cfg=load(HERE/'execution_config.json'); data={y:[] for y in (1981,1982,1983)}
    for d,_,y in source_rows(cfg):
        year=int(str(d)[:4])
        if year in data: data[year].append((d,float(y)))
    views={}
    for year,rows in data.items():
        d=np.asarray([r[0] for r in rows]); q=values([r[1] for r in rows],365)
        if not np.array_equal(d,Fold(year).dev): raise ValueError('Evaluation date mismatch')
        views[year]=EvalLabels(d,q)
    event('EVALUATION_LABELS_OPENED',prediction_freeze_sha256=sha(HERE/'prediction_freeze.json'),
          roles='development labels evaluation only; no further fit',
          evaluation_years=[1981,1982,1983],code_hashes=frozen['frozen_hashes'])
    return views
