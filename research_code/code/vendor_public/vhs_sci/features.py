"""Training-only meteorological transforms and recursive source checks."""
from dataclasses import dataclass, asdict
import numpy as np
from .contracts import ScienceError, ids_hash, digest


@dataclass(frozen=True)
class FeatureSpec:
    feature_id: str
    parents: tuple = ()
    source_class: str = "DERIVED"
    dataset_id: str = ""
    fit_scope: str = "none"
    fit_ids: tuple = ()
    available_at: str = "target_month_end"


class FeatureGraph:
    def __init__(self, nodes):
        self.nodes = {n.feature_id: n for n in nodes}
        if len(self.nodes) != len(nodes):
            raise ScienceError("DUPLICATE_FEATURE_NODE")

    def check(self, names, dataset_id, train_ids=(), forbidden_ids=()):
        if not names:
            return {"status": "PASS_VACUOUS", "ok": None, "badge": "NEUTRAL", "scientific_task_feasible": None}
        sources, visited, fitted = set(), set(), []
        def visit(name, stack):
            if name in stack:
                raise ScienceError("FEATURE_CYCLE")
            if name not in self.nodes:
                raise ScienceError("UNKNOWN_FEATURE_LINEAGE", name)
            node = self.nodes[name]
            if node.dataset_id != dataset_id:
                raise ScienceError("FEATURE_DATASET_MISMATCH", name)
            if node.source_class in ("TARGET_Q", "TARGET_W", "WATER_BALANCE", "INVERTED_INTAKE"):
                raise ScienceError("TARGET_DERIVED_FEATURE_FORBIDDEN", name)
            if node.fit_scope not in ("none", "train_fold"):
                raise ScienceError("UNREGISTERED_FIT_SCOPE")
            if node.fit_scope == "train_fold":
                if not node.fit_ids or not set(node.fit_ids) <= set(train_ids) or set(node.fit_ids) & set(forbidden_ids):
                    raise ScienceError("FEATURE_FIT_SCOPE_LEAKAGE", name)
                fitted.append({"feature": name, "fit_ids_hash": ids_hash(node.fit_ids)})
            visited.add(name)
            if not node.parents:
                if node.source_class == "DERIVED":
                    raise ScienceError("UNRESOLVED_SOURCE", name)
                sources.add(name)
            for p in node.parents:
                visit(p, stack | {name})
        for n in names:
            visit(n, set())
        return {"status": "PASS_LINEAGE_ONLY", "ok": True, "badge": "NEUTRAL",
                "sources": sorted(sources), "nodes": sorted(visited), "fitted": fitted,
                "uses_target_label": False,
                "feature_specs": [asdict(self.nodes[n]) for n in sorted(visited)],
                "scientific_task_feasible": None, "graph_hash": digest([asdict(self.nodes[n]) for n in sorted(visited)])}


def base_graph(dataset_id):
    return FeatureGraph([FeatureSpec(n, (), c, dataset_id) for n, c in
                         (("Qu", "UPSTREAM_Q"), ("P", "MET"), ("T", "MET"), ("month", "CALENDAR"),
                          ("Qd", "TARGET_Q"), ("Wd", "TARGET_W"), ("residual", "WATER_BALANCE"),
                          ("intake", "INVERTED_INTAKE"))])


def validate_features(batch, no_upstream=False):
    batch.require_synthetic()
    allowed = {"Qu", "P", "T", "met_complete"}
    unknown = set(batch.columns) - allowed
    if unknown:
        raise ScienceError("UNREGISTERED_FEATURE", str(sorted(unknown)))
    if no_upstream and "Qu" in batch.columns:
        raise ScienceError("UPSTREAM_Q_FORBIDDEN_IN_NO_UPSTREAM_MODEL")
    for name, values in batch.columns.items():
        if not np.isfinite(np.asarray(values, dtype=float)).all():
            raise ScienceError("NONFINITE_FEATURE", name)
    if "Qu" in batch.columns and (np.asarray(batch.columns["Qu"]) < 0).any():
        raise ScienceError("NEGATIVE_UPSTREAM_Q")
    if "P" in batch.columns and (np.asarray(batch.columns["P"]) < 0).any():
        raise ScienceError("NEGATIVE_PRECIPITATION")


class MeteorologyTransform:
    def fit(self, train_batch):
        x = train_batch.features
        validate_features(x)
        if not all(name in x.columns for name in ("P", "T", "met_complete")) or not np.all(x.columns["met_complete"]):
            raise ScienceError("INCOMPLETE_METEOROLOGY")
        self.binding = (x.keys[0].dataset_id, x.keys[0].snapshot_id)
        self.fit_ids = tuple(x.ids)
        self.stats, self.constant_flags = {}, []
        for name in ("P", "T"):
            for m in range(1, 13):
                ix = x.months == m
                if len(set(x.years[ix])) < 3 or int(ix.sum()) < 3:
                    raise ScienceError("INSUFFICIENT_MONTH_REFERENCE", f"{name}/{m}")
                vals = np.asarray(x.columns[name], dtype=float)[ix]
                mu, sd = float(np.mean(vals)), float(np.std(vals, ddof=1))
                constant = sd <= 1e-12 * max(1.0, float(np.max(np.abs(vals))))
                self.stats[(name, m)] = (mu, sd, constant)
                if constant:
                    self.constant_flags.append(f"{name}/{m}:ZERO_STD_ZERO_ANOMALY")
        return self

    def transform(self, x):
        if not hasattr(self, "stats"):
            raise ScienceError("TRANSFORM_NOT_FITTED")
        validate_features(x)
        if (x.keys[0].dataset_id, x.keys[0].snapshot_id) != self.binding:
            raise ScienceError("DATASET_SNAPSHOT_MISMATCH")
        if not all(name in x.columns for name in ("P", "T", "met_complete")) or not np.all(x.columns["met_complete"]):
            raise ScienceError("INCOMPLETE_METEOROLOGY")
        out = []
        for name in ("P", "T"):
            out.append(np.array([0.0 if self.stats[(name, k.month)][2] else
                (float(x.columns[name][i]) - self.stats[(name, k.month)][0]) / self.stats[(name, k.month)][1]
                for i, k in enumerate(x.keys)]))
        return np.column_stack(out)

    def record(self):
        nodes = list(base_graph(self.binding[0]).nodes.values())
        for name in ("P", "T"):
            nodes.append(FeatureSpec(name + "_anomaly", (name, "month"), "DERIVED", self.binding[0], "train_fold", self.fit_ids))
        graph = FeatureGraph(nodes)
        return {"fit_ids_hash": ids_hash(self.fit_ids), "fit_years": sorted({int(s[-7:-3]) for s in self.fit_ids}),
                "constants": self.constant_flags,
                "monthly_stats": {f"{n}/{m}": {"mean": mu, "sample_std": sd, "constant": c} for (n, m), (mu, sd, c) in self.stats.items()},
                "lineage": graph.check(["P_anomaly", "T_anomaly"], self.binding[0], self.fit_ids)}
