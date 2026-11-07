"""Explicit future reader contract. No real source backend is connected."""
from datetime import datetime, timezone
from .contracts import ScienceError

ROLES = {"TRAINING_LABEL", "INFERENCE_INPUT", "PREPROCESSING_PARAM", "MODEL_SELECTION", "FINAL_SCORING"}


class AuthorizedBatchReader:
    def __init__(self, registry, synthetic_batches=None):
        self.registry, self.synthetic_batches = dict(registry), synthetic_batches or {}
        self.real_source_open_count = 0

    def read(self, keys, fields, role, grant, fold):
        if role not in ROLES or not keys:
            raise ScienceError("INVALID_ROLE_OR_KEYS", status=400)
        ds, snap = keys[0].dataset_id, keys[0].snapshot_id
        if self.registry.get(ds) != snap or any((k.dataset_id, k.snapshot_id) != (ds, snap) for k in keys):
            raise ScienceError("DATASET_SNAPSHOT_MISMATCH", status=409)
        if fold.dataset_id != ds or fold.snapshot_id != snap:
            raise ScienceError("FOLD_BINDING_MISMATCH")
        if not grant or grant.get("dataset_id") != ds or grant.get("snapshot_id") != snap:
            raise ScienceError("REAL_EXECUTION_NOT_AUTHORIZED", status=403)
        if role not in grant.get("roles", []) or not set(fields) <= set(grant.get("fields", [])):
            raise ScienceError("GRANT_SCOPE_MISMATCH", status=403)
        if set(fields) - {"Qu", "Qd", "P", "T", "met_complete", "Wd", "residual", "intake", "Qd_smooth"}:
            raise ScienceError("UNKNOWN_READER_FIELD", status=400)
        if fold.experiment_group == "NO_UPSTREAM_Q_ARCHIVE_RECONSTRUCTION" and "Qu" in fields:
            raise ScienceError("UPSTREAM_Q_FORBIDDEN_IN_NO_UPSTREAM_MODEL", status=403)
        ids = {k.sample_id for k in keys}
        if not ids <= set(fold.train_ids) | set(fold.test_ids):
            raise ScienceError("ILLEGAL_FOLD_MEMBERSHIP")
        if "Qd" in fields:
            legal = set(fold.test_ids) if role == "FINAL_SCORING" else set(fold.train_ids)
            if role not in ("TRAINING_LABEL", "MODEL_SELECTION", "FINAL_SCORING") or not ids <= legal:
                raise ScienceError("HELD_OUT_TARGET_ACCESS_FORBIDDEN", status=403)
        if any(f in fields for f in ("Wd", "residual", "intake", "Qd_smooth")):
            raise ScienceError("TARGET_DERIVED_FEATURE_FORBIDDEN", status=403)
        if ds.startswith("SYNTHETIC_") and grant.get("authorization_status") == "SYNTHETIC_ONLY":
            if ds not in self.synthetic_batches:
                raise ScienceError("SYNTHETIC_DATASET_NOT_REGISTERED")
            batch, labels = self.synthetic_batches[ds]
            x = batch.take(ids)
            indices = {k.sample_id: i for i, k in enumerate(batch.keys)}
            return {f: [float(labels[indices[k.sample_id]]) for k in x.keys] if f == "Qd" else x.columns[f].copy()
                    for f in fields}
        if grant.get("authorization_status") != "REAL_TRAIN_EVAL" or not grant.get("authorization_id") or not grant.get("result_save_authorized"):
            raise ScienceError("REAL_EXECUTION_NOT_AUTHORIZED", status=403)
        try:
            expiry = datetime.fromisoformat(grant["expires_UTC"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            raise ScienceError("INVALID_GRANT_EXPIRY", status=403)
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ScienceError("GRANT_EXPIRED", status=403)
        raise ScienceError("REAL_BACKEND_NOT_ENABLED_IN_S2", status=403)


def execution_endpoint(synthetic=False):
    return (200, {"status": "SYNTHETIC_ONLY", "prediction": None}) if synthetic else (403, {"status": "NOT_AUTHORIZED", "prediction": None})
