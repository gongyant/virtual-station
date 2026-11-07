"""Data-source binding for isolated public experiment; no teacher authorization or synthetic impersonation."""
import hashlib,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parents[1]
DATASET="LAMAH_CE_PUBLIC_V1"
_registered={};_snapshot=None;_train_ids=set();_metric=None
def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def register(rows,snapshot):
 global _registered,_snapshot
 a=json.loads((R/"source/ACQUISITION.json").read_text(encoding="utf-8"))
 if a["doi"]!="10.5281/zenodo.5153305" or a["md5"]!="69fd2733e969513403f923ecc5eaa3dc":raise ValueError("UNREGISTERED_PUBLIC_SOURCE")
 if not snapshot.startswith("lamah-public-monthly-"):raise ValueError("WRONG_PUBLIC_SNAPSHOT")
 _registered={r["sample_id"]:r for r in rows};_snapshot=snapshot
def set_outer_train(ids):
 global _train_ids
 _train_ids=set(ids)
def admit_batch(batch):
 if batch.synthetic is not False or batch.authorization_status!="PUBLIC_DATA_REAL_EXPERIMENT":raise ValueError("PUBLIC_BATCH_MUST_BE_REAL")
 if set(batch.columns)-{"P","T","met_complete"}:raise ValueError("PUBLIC_NO_UPSTREAM_FIELDS_ONLY")
 for i,k in enumerate(batch.keys):
  if k.dataset_id!=DATASET or k.snapshot_id!=_snapshot or k.sample_id not in _registered:raise ValueError("PUBLIC_SOURCE_KEY_MISMATCH")
  r=_registered[k.sample_id]
  if (k.year,k.month,k.station_id)!=(r["year"],r["month"],r["station_id"]):raise ValueError("PUBLIC_TIME_KEY_MISMATCH")
  for name,values in batch.columns.items():
   field={"P":"P_mm","T":"T_C","met_complete":"complete"}[name]
   if float(values[i])!=float(r[field]):raise ValueError("PUBLIC_INPUT_VALUE_CHANGED")
def admit_training(batch):
 admit_batch(batch.features)
 if not set(batch.features.ids)<=_train_ids:raise ValueError("HELD_OUT_PUBLIC_LABEL_IN_TRAIN")
 for k,y in zip(batch.features.keys,batch.labels):
  if float(y)!=float(_registered[k.sample_id]["Q_m3s"]):raise ValueError("PUBLIC_LABEL_SOURCE_MISMATCH")
def permit_metric(ids,predicted):
 global _metric
 y=np.asarray([_registered[s]["Q_m3s"] for s in ids],float)
 _metric=(digest(y.tolist()),digest(np.asarray(predicted,float).tolist()))
 return y
def admit_metric(observed,predicted,synthetic):
 if synthetic is not False or _metric!=(digest(np.asarray(observed,float).tolist()),digest(np.asarray(predicted,float).tolist())):raise ValueError("PUBLIC_SCORING_PROVENANCE_REQUIRED")
