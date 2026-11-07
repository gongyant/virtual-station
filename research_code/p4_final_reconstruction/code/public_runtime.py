"""Public P4 only: role-scoped label admission, no teacher paths."""
import numpy as np
REGISTERED={};LABELS={};ALLOWED=set();SNAPSHOT=None;CUTOFF=None;METRIC=None
def register(features,labels,snapshot,cutoff):
 global REGISTERED,LABELS,SNAPSHOT,CUTOFF
 REGISTERED={r["sample_id"]:r for r in features};LABELS=dict(labels);SNAPSHOT=snapshot;CUTOFF=cutoff
 assert all(i[-7:]<=cutoff for i in LABELS),"FUTURE_Q_REGISTERED"
def set_outer_train(ids):
 global ALLOWED
 ALLOWED=set(ids);assert ALLOWED<=set(LABELS)
def admit_input(x):
 assert not x.synthetic and x.snapshot==SNAPSHOT and x.snapshot.startswith("lamah-public-p4-")
 assert set(x.values)<={"P","T","L1"} and len(x.ids)==len(set(x.ids)) and len(x.ids)>0
 for z,i in enumerate(x.ids):
  r=REGISTERED[i];assert int(x.years[z])==r["year"] and int(x.months[z])==r["month"]
  for k,v in x.values.items():assert np.isfinite(v[z]) and float(v[z])==r[k],"INPUT_SOURCE_MISMATCH"
def admit_training_matrix(x,y):
 admit_input(x);assert set(x.ids)<=ALLOWED and all(i[-7:]<=CUTOFF for i in x.ids),"TEST_Q_OR_FUTURE_IN_TRAIN"
 assert y.shape==(len(x.ids),) and np.isfinite(y).all()
 assert all(float(v)==LABELS[i] for i,v in zip(x.ids,y)),"LABEL_SOURCE_MISMATCH"
def read_training(ids):
 assert set(ids)<=ALLOWED
 return np.array([LABELS[i] for i in ids])
def permit_metric(y,p):
 global METRIC
 METRIC=(np.asarray(y).copy(),np.asarray(p).copy())
def admit_metric(y,p,synthetic):
 assert synthetic is False and METRIC is not None and np.array_equal(y,METRIC[0]) and np.array_equal(p,METRIC[1]),"INVALID_METRIC_ROLE"
