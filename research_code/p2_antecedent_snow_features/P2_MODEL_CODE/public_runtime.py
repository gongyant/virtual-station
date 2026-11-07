"""Scoped public snapshot reader and scoring adapter; reuses S2 metric contract."""
import hashlib,json
from pathlib import Path
import numpy as np
P=Path(__file__).parents[1];R=P.parent
DATASET="LAMAH_CE_PUBLIC_V1";_registered={};_train_ids=set();_metric=None;_snapshot=None
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def register(rows,snapshot):
 global _registered,_snapshot
 a=json.loads((R/"source/ACQUISITION.json").read_text())
 assert a["doi"]=="10.5281/zenodo.5153305" and a["sha256"]=="b692afc817fc7d92c003b3203fa04def9bbc04c3db39fa58b94c37f8d5376dd0"
 assert snapshot.startswith("lamah-public-p2-")
 _registered={r["sample_id"]:r for r in rows};_snapshot=snapshot
def set_outer_train(ids):
 global _train_ids
 _train_ids=set(ids)
def admit_input(x):
 assert set(x.values)<={"P","T","L1","S","M"},"FORBIDDEN_INPUT_COLUMN"
 assert len(x.ids)==len(set(x.ids)) and len(x.ids)>0
 assert all(np.isfinite(a).all() for a in x.values.values()),"MISSING_IS_NOT_ZERO"
 if x.synthetic:
  assert all(i.startswith("SYNTHETIC_P2:") for i in x.ids),"SYNTHETIC_CANNOT_USE_REAL_IDS"
  return
 assert x.snapshot==_snapshot
 for z,i in enumerate(x.ids):
  r=_registered[i];assert int(x.years[z])==r["year"] and int(x.months[z])==r["month"]
  for k,v in x.values.items():assert float(v[z])==float(r[k]),"SOURCE_FEATURE_CHANGED"
def admit_training_matrix(x,y):
 admit_input(x)
 assert set(x.ids)<=_train_ids,"HELD_OUT_LABEL_IN_TRAINING"
 assert np.isfinite(y).all() and np.min(y)>=0
 if not x.synthetic:
  for i,v in zip(x.ids,y):assert float(v)==float(_registered[i]["Q_m3s"]),"TRAIN_LABEL_MISMATCH"
def read_training(ids):
 assert set(ids)<=_train_ids
 return np.array([_registered[i]["Q_m3s"] for i in ids])
def permit_metric(ids,p):
 global _metric
 y=np.array([_registered[i]["Q_m3s"] for i in ids])
 _metric=digest(y.tolist()),digest(np.asarray(p).tolist());return y
def admit_metric(observed,predicted,synthetic):
 assert synthetic is False and _metric==(digest(np.asarray(observed).tolist()),digest(np.asarray(predicted).tolist())),"PUBLIC_SCORE_SOURCE_REQUIRED"
