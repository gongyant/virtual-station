"""Synthetic → S1 QC → ledger → LOYO → nested fit → OOF → sealed artifacts."""
import json
import platform
from pathlib import Path
import numpy as np
from .contracts import GROUP_A, GROUP_B, MODELS_A, MODELS_B, TASK, TrainingBatch, ScienceError, digest, ids_hash
from .models.baselines import model_factory, VERSION
from .synthetic import make_dataset
from .ledger import synthetic_ledger
from .folds import make_folds, support
from .invariants import enforce_fold, select_model_features, target_label_invariance
from .evaluate import evaluate_oof
from .provenance import code_hash, sha_file, write_run, validate_run_artifact

ROOT = Path(__file__).resolve().parents[1]


def run_scenario(scenario, output_root=None, seed=20261025, scramble=False, persist=True, invariance=True):
    protocol = json.loads((ROOT / "protocol.json").read_text(encoding="utf-8"))
    features, labels, upstream = make_dataset(scenario, seed, scramble)
    ledger = synthetic_ledger(features, labels, upstream)
    group = GROUP_B if scenario == "D" else GROUP_A
    models = MODELS_B if group == GROUP_B else MODELS_A
    folds = make_folds(ledger, group)
    legal = support(ledger, group)
    eligible = features.take([r["sample_id"] for r in legal])
    indices = {k.sample_id: i for i, k in enumerate(features.keys)}
    eligible_y = np.array([labels[indices[k.sample_id]] for k in eligible.keys])
    predictions = {m: {} for m in models}
    model_records, invariant_records = [], []
    for fold in folds:
        train, test = features.take(fold.train_ids), features.take(fold.test_ids)
        enforce_fold(train, test, fold)
        train_y = np.array([labels[indices[k.sample_id]] for k in train.keys])
        test_y = np.array([labels[indices[k.sample_id]] for k in test.keys])
        for mid in models:
            model = model_factory(mid)
            tx, vx = select_model_features(train, model), select_model_features(test, model)
            model.fit(TrainingBatch(tx, train_y))
            pred = model.predict(vx)
            for k, raw, bounded in zip(pred.keys, pred.raw, pred.constrained):
                if k.sample_id in predictions[mid]:
                    raise ScienceError("DUPLICATE_OOF_ID")
                predictions[mid][k.sample_id] = {"raw": float(raw), "constrained": float(bounded), "fold_id": fold.fold_id}
            model_records.append({"fold_id": fold.fold_id, **model.record()})
            # Representative full refit checks per model, including tuned Ridge.
            if invariance and fold == folds[0]:
                evidence = target_label_invariance(lambda: model_factory(mid), tx, train_y, vx, test_y)
                invariant_records.append({"model_id": mid, "fold_id": fold.fold_id, **evidence})
    metrics = evaluate_oof(eligible, eligible_y, predictions, group, seed)
    summary = {"scenario": scenario, "negative_control": scramble, "group": group, "n_folds": len(folds),
               "n_months": len(eligible.keys), "n_years": len(set(eligible.years.tolist())),
               "raw_RMSE": {m: metrics["models"][m]["pooled_raw"]["RMSE"]["value"] for m in models},
               "label_invariance": invariant_records, "synthetic": True}
    if not persist:
        return {"summary": summary, "metrics": metrics, "models": model_records, "predictions": predictions,
                "folds": folds, "features": eligible, "labels": eligible_y}
    c_hash = code_hash(ROOT)
    run_id = f"S2-{scenario}{'-NEGATIVE' if scramble else ''}-" + digest({"snapshot": features.keys[0].snapshot_id,
                "protocol": digest(protocol), "code": c_hash, "group": group})[:16]
    manifest = {"dataset_id": features.keys[0].dataset_id, "snapshot_id": features.keys[0].snapshot_id,
                "task_class": TASK, "experiment_group": group, "quality_scheme": "claude_core",
                "model_id": list(models), "model_version": VERSION,
                "train_ids_hash": digest({f.fold_id: ids_hash(f.train_ids) for f in folds}),
                "test_ids_hash": digest({f.fold_id: ids_hash(f.test_ids) for f in folds}),
                "protocol_hash": digest(protocol), "protocol_file_sha256": sha_file(ROOT / "protocol.json"),
                "code_hash": c_hash, "seed": seed, "synthetic": True, "authorization_status": "SYNTHETIC_ONLY",
                "unit_status": "SYNTHETIC_ARBITRARY_UNITS", "scenario": scenario, "negative_control": scramble,
                "environment": {"python": platform.python_version(), "numpy": np.__version__},
                "ledger_hash": folds[0].ledger_hash,
                "prediction_policy": protocol["nonnegative_policy"], "real_trained_models": 0, "real_evaluated_models": 0}
    p_rows = [{"sample_id": k.sample_id, "fold_id": predictions[m][k.sample_id]["fold_id"], "model_id": m,
               "y_hat_raw": predictions[m][k.sample_id]["raw"], "y_hat_nonnegative": predictions[m][k.sample_id]["constrained"],
               "synthetic": True, "unit_status": "SYNTHETIC_ARBITRARY_UNITS"} for m in models for k in eligible.keys]
    yearly_rows = [{"model_id": m, "year": y, "MAE": v["MAE"]["value"], "RMSE": v["RMSE"]["value"],
                    "NSE": v["NSE"]["value"], "KGE": v["KGE"]["value"], "PBIAS": v["PBIAS"]["value"], "synthetic": True}
                   for m in models for y, v in metrics["models"][m]["yearly_raw"].items()]
    obs = [{"sample_id": k.sample_id, "synthetic_observed_label": float(eligible_y[i]), "synthetic": True} for i, k in enumerate(eligible.keys)]
    inputs = [{"sample_id": k.sample_id, **{n: float(v[i]) for n, v in eligible.columns.items()}, "synthetic": True}
              for i, k in enumerate(eligible.keys)]
    report = "# VHS-SCI-S2 SYNTHETIC_ONLY\n\n此处所有数值来自人工合成情景，不能用于真实锡尔河性能声明。\n\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    path = write_run(output_root or ROOT / "synthetic_runs", run_id, manifest,
                     {"model.json": model_records, "folds.json": [f.record() for f in folds], "metrics.json": metrics,
                      "sample_ledger.json": ledger, "invariants.json": invariant_records, "protocol.json": protocol},
                     p_rows, yearly_rows, obs, inputs, report)
    verification = validate_run_artifact(path, {features.keys[0].dataset_id: features.keys[0].snapshot_id})
    return {"summary": summary, "path": str(path), "artifact_verification": verification}
