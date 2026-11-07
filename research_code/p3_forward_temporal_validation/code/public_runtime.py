"""P3 data roles: train labels before2005; score labels unopened until all predictions sealed."""
import csv,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
P=Path(__file__).parents[1];R=P.parent
DATASET="LAMAH_CE_PUBLIC_V1";_registered={};_training_labels={};_score_labels={};_train_ids=set();_metric=None;_snapshot=None;_scoring_released=False
ACCESS_LOG=[]
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def previous_month(y,m):return (y,m-1) if m>1 else (y-1,12)
def register(features,trainlabels,snapshot):
 global _registered,_training_labels,_snapshot
 assert snapshot.startswith("lamah-public-p3-")
 assert all(r["year"]<=2004 for r in trainlabels),"TEST_Q_IN_TRAIN_LABEL_FILE"
 assert all("Q_m3s" not in r for r in features),"Q_IN_FEATURE_FILE"
 _registered={r["sample_id"]:r for r in features};_training_labels={r["sample_id"]:r["Q_m3s"] for r in trainlabels};_snapshot=snapshot
 ACCESS_LOG.append({"event":"TRAIN_LABELS_REGISTERED","n":len(trainlabels),"max_train_year":max(r["year"] for r in trainlabels),"test_labels_loaded":False,"UTC":datetime.now(timezone.utc).isoformat()})
def set_outer_train(ids):
 global _train_ids
 _train_ids=set(ids)
def admit_input(x):
 assert set(x.values)<={"P","T","L1"},"UNREGISTERED_FEATURE_OR_SNOW"
 assert len(x.ids)>0 and len(x.ids)==len(set(x.ids))
 assert all(np.isfinite(v).all() for v in x.values.values())
 if x.synthetic:
  assert all(i.startswith("SYNTHETIC_P3:") for i in x.ids);return
 assert x.snapshot==_snapshot
 for z,i in enumerate(x.ids):
  r=_registered[i];assert (int(x.years[z]),int(x.months[z]))==(r["year"],r["month"])
  for k,v in x.values.items():assert float(v[z])==float(r[k])
def admit_training_matrix(x,y):
 admit_input(x)
 assert max(x.years)<=2004,"FORWARD_CUTOFF_VIOLATION"
 assert set(x.ids)<=_train_ids,"HELD_OUT_IDS_IN_TRAIN"
 assert np.asarray(y).shape==(len(x.ids),) and np.isfinite(y).all() and np.min(y)>=0
 if not x.synthetic:
  for i,v in zip(x.ids,y):assert float(v)==_training_labels[i],"TRAIN_LABEL_SOURCE_MISMATCH"
def read_training(ids):
 assert set(ids)<=_train_ids
 assert all(int(i[-7:-3])<=2004 for i in ids)
 return np.array([_training_labels[i] for i in ids])
def release_scoring(bundle):
 global _score_labels,_scoring_released
 assert (bundle/"SHA256SUMS.txt").is_file(),"PREDICTIONS_NOT_SEALED"
 for line in (bundle/"SHA256SUMS.txt").read_text().splitlines():
  h,n=line.split("  ",1);assert sha(bundle/n)==h,"PREDICTION_BUNDLE_CHANGED"
 commit=json.loads((bundle/"COMMITMENT.json").read_text())
 assert commit["all_predictions_complete"] and commit["test_Q_loaded"] is False
 with (bundle/"TEST_PREDICTIONS_WITHOUT_QOBS.csv").open(encoding="utf-8-sig") as f:
  reader=csv.DictReader(f);assert not any("qobs" in k.lower() for k in reader.fieldnames)
  preds=list(reader)
 assert len(preds)==commit["n_predictions"]
 snap=json.loads((P/"source/SNAPSHOT.json").read_text())
 qpath=P/"source/test_labels_SCORE_ONLY.csv";assert sha(qpath)==snap["test_score_labels_sha256"]
 with qpath.open(encoding="utf-8-sig") as f:labels=list(csv.DictReader(f))
 assert all(2005<=int(r["year"])<=2014 for r in labels)
 _score_labels={r["sample_id"]:float(r["Q_m3s"]) for r in labels};_scoring_released=True
 ACCESS_LOG.append({"event":"TEST_LABELS_RELEASED_AFTER_ALL_PREDICTIONS_SEALED","prediction_bundle_seal_sha256":sha(bundle/"SHA256SUMS.txt"),"n_score_labels":len(labels),"UTC":datetime.now(timezone.utc).isoformat()})
 return ACCESS_LOG[-1]
def permit_metric(ids,p):
 global _metric
 assert _scoring_released,"TEST_SCORE_BEFORE_PREDICTION_COMMIT"
 y=np.array([_score_labels[i] for i in ids]);_metric=digest(y.tolist()),digest(np.asarray(p).tolist());return y
def admit_metric(observed,predicted,synthetic):
 assert synthetic is False and _scoring_released and _metric==(digest(np.asarray(observed).tolist()),digest(np.asarray(predicted).tolist())),"INVALID_SCORE_ROLE"
