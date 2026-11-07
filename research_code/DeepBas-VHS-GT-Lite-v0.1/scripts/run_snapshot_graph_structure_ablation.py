from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import numpy as np
import yaml

from vhs.data import TensorBundle
from vhs.train import train_from_config


BASE_BUNDLE = Path("data/processed/virtual_station_multisite/multisite_residual_gnn_bundle_2005.npz")
BASE_CONFIG = Path("configs/multisite2005_snapshot_gnn.yaml")
ROOT = Path("outputs/diagnosis_2005_snapshot/graph_runs")
SEEDS = [7, 42, 123]


def save_variant(bundle: TensorBundle, edge_index: np.ndarray, name: str) -> Path:
    variant = copy.deepcopy(bundle)
    variant.edge_index = np.asarray(edge_index, dtype=np.int64)
    variant.edge_attr = np.ones((variant.edge_index.shape[1], 1), dtype=np.float32)
    path = ROOT / "bundles" / f"{name}.npz"
    variant.save(path)
    return path


def random_edges(node_count: int, edge_count: int) -> np.ndarray:
    rng = np.random.default_rng(20260728)
    candidates = [(i, j) for i in range(node_count) for j in range(node_count) if i != j]
    chosen = rng.choice(len(candidates), size=edge_count, replace=False)
    return np.asarray([candidates[int(i)] for i in chosen], dtype=np.int64).T


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    bundle = TensorBundle.load(BASE_BUNDLE)
    true_edges = bundle.edge_index.copy()
    variants = {
        "G1_self_loops": np.vstack([np.arange(len(bundle.station_ids)), np.arange(len(bundle.station_ids))]),
        "G3_reversed": true_edges[::-1].copy(),
        "G4_random": random_edges(len(bundle.station_ids), true_edges.shape[1]),
        "G5_self_transform_only": np.empty((2, 0), dtype=np.int64),
    }
    bundle_paths = {name: save_variant(bundle, edges, name) for name, edges in variants.items()}
    metadata = {
        "station_ids": list(map(str, bundle.station_ids)),
        "base_edges_index": true_edges.tolist(),
        "variants": {name: edges.tolist() for name, edges in variants.items()},
        "random_edge_seed": 20260728,
        "G5_note": "graph_layers=1 with an empty edge set; retains self_linear/residual/LayerNorm but receives no neighbor messages",
    }
    (ROOT / "graph_variants.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    base = yaml.safe_load(BASE_CONFIG.read_text(encoding="utf-8"))
    configs = []
    for name, bundle_path in bundle_paths.items():
        for seed in SEEDS:
            cfg = copy.deepcopy(base)
            cfg["seed"] = seed
            cfg["data"]["bundle_path"] = str(bundle_path)
            cfg["output_dir"] = str(ROOT / name / f"seed{seed}")
            config_path = ROOT / "configs" / f"{name}_seed{seed}.yaml"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True), encoding="utf-8")
            configs.append(config_path)
    if args.prepare_only:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        return
    for config_path in configs:
        print(f"RUN {config_path}")
        train_from_config(config_path)


if __name__ == "__main__":
    main()

