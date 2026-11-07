"""
research/feature_dag.py  --  VHS v0.5.1 recursive feature lineage (Codex P1-01)

Replaces the v0.5 one-level ``target_q in f.lineage`` string test with a
feature-dependency DAG:

* every feature is a node with a transform and parent nodes; ancestors are
  followed recursively to the source columns, and every transform chain is
  kept (``lineage()``);
* unknown parents / unknown features, unknown transforms, unknown roles and
  unknown tasks are rejected; cycles are detected and reported;
* time access is tracked: for a feature used for a set of years, the years
  of every Q source it touches are derived through LAG / SMOOTH / fitted
  transforms (SEASONAL_CORRECTION, FIT_NORMALIZE use their ``fit_years``);
* roles are explicit: TRAINING_LABEL, INFERENCE_INPUT, PREPROCESSING_PARAM,
  MODEL_SELECTION, FINAL_SCORING. Only FINAL_SCORING may legally read
  held-out target labels.

``evaluate()`` executes transforms on SYNTHETIC series only (unit tests).
Nothing here trains, scores or predicts with real data;
MODEL_EXECUTION stays NOT_AUTHORIZED.

A passing lineage / counterfactual test is NOT a certification that
external remote-sensing products or pre-trained models are scientifically
independent of the target Q; their production chains are outside this graph.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MISSING_RECONSTRUCTION = "MISSING_RECONSTRUCTION"
ZERO_TARGET_Q = "ZERO_TARGET_Q_CALIBRATION"
CROSS_SYSTEM = "CROSS_SYSTEM_GENERALIZATION"
TASKS = (MISSING_RECONSTRUCTION, ZERO_TARGET_Q, CROSS_SYSTEM)

TRAINING_LABEL = "TRAINING_LABEL"
INFERENCE_INPUT = "INFERENCE_INPUT"
PREPROCESSING_PARAM = "PREPROCESSING_PARAM"
MODEL_SELECTION = "MODEL_SELECTION"
FINAL_SCORING = "FINAL_SCORING"
ROLES = (TRAINING_LABEL, INFERENCE_INPUT, PREPROCESSING_PARAM,
         MODEL_SELECTION, FINAL_SCORING)

SOURCE_CLASSES = ("OBSERVED_Q", "MET", "REMOTE_SENSING", "SCENARIO_PARAM",
                  "UNKNOWN")
TRANSFORMS = ("SOURCE", "SELECT", "RENAME", "UNIT_CONVERT", "MONTHLY_AGG",
              "ANNUAL_AGG", "LAG", "SMOOTH", "DIFF", "LINEAR", "INVERSION",
              "SEASONAL_CORRECTION", "FIT_NORMALIZE")
ALL = "ALL"
NOT_CERTIFIED_NOTE = ("测试通过只说明本图内的谱系与合成反事实检查成立，不代表外部遥感产品、"
                      "再分析气象或预训练模型已获“与目标 Q 科学独立”的认证。")


class LineageError(Exception):
    def __init__(self, code, detail):
        super().__init__("%s: %s" % (code, detail))
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class Node:
    name: str
    transform: str
    parents: Tuple[str, ...] = ()
    dataset: Optional[str] = None
    source_class: Optional[str] = None
    q_station: Optional[str] = None
    unit: str = "UNKNOWN"
    params: Tuple = ()
    fit_years: Optional[Tuple[int, ...]] = None
    note: str = ""

    def p(self, key, default=None):
        return dict(self.params).get(key, default)


class FeatureGraph:
    def __init__(self):
        self.nodes: Dict[str, Node] = {}

    # -- construction ---------------------------------------------------
    def add_source(self, name, dataset, source_class, q_station=None,
                   unit="UNKNOWN", note=""):
        if source_class not in SOURCE_CLASSES:
            raise LineageError("UNKNOWN_SOURCE_CLASS", source_class)
        self._put(Node(name, "SOURCE", (), dataset, source_class,
                       q_station, unit, (), None, note))
        return self

    def add(self, name, transform, parents, dataset=None, unit="UNKNOWN",
            fit_years=None, note="", **params):
        if transform not in TRANSFORMS or transform == "SOURCE":
            raise LineageError("UNKNOWN_TRANSFORM", transform)
        if isinstance(parents, str):
            parents = (parents,)
        fy = None if fit_years is None else (
            ALL if fit_years == ALL else tuple(sorted(fit_years)))
        self._put(Node(name, transform, tuple(parents), dataset, None, None,
                       unit, tuple(sorted(params.items())), fy, note))
        return self

    def _put(self, node):
        if node.name in self.nodes:
            raise LineageError("DUPLICATE_NODE", node.name)
        self.nodes[node.name] = node

    # -- validation -----------------------------------------------------
    def problems(self):
        """All unknown-parent and cycle problems of the whole graph."""
        out = []
        for n in self.nodes.values():
            for p in n.parents:
                if p not in self.nodes:
                    out.append({"code": "UNKNOWN_FEATURE", "node": n.name,
                                "missing_parent": p})
        WHITE, GREY, BLACK = 0, 1, 2
        color = {k: WHITE for k in self.nodes}
        for start in sorted(self.nodes):
            if color[start] != WHITE:
                continue
            stack = [(start, iter(self.nodes[start].parents))]
            path = [start]
            color[start] = GREY
            while stack:
                node, it = stack[-1]
                nxt = next(it, None)
                if nxt is None:
                    color[node] = BLACK
                    stack.pop()
                    path.pop()
                    continue
                if nxt not in self.nodes:
                    continue
                if color[nxt] == GREY:
                    cyc = path[path.index(nxt):] + [nxt]
                    out.append({"code": "CYCLE_DETECTED", "cycle": cyc})
                elif color[nxt] == WHITE:
                    color[nxt] = GREY
                    path.append(nxt)
                    stack.append((nxt, iter(self.nodes[nxt].parents)))
        return out

    def _require(self, name):
        """Reject unknown features, unknown ancestors and cycles."""
        if name not in self.nodes:
            raise LineageError("UNKNOWN_FEATURE", name)
        reach = self._reach(name, tolerant=True)
        for p in self.problems():
            if p["code"] == "CYCLE_DETECTED" and set(p["cycle"]) & reach:
                raise LineageError("CYCLE_DETECTED", p["cycle"])
            if p["code"] == "UNKNOWN_FEATURE" and p["node"] in reach:
                raise LineageError("UNKNOWN_FEATURE", p)

    def _reach(self, name, tolerant=False):
        seen, todo = set(), [name]
        while todo:
            n = todo.pop()
            if n in seen:
                continue
            seen.add(n)
            node = self.nodes.get(n)
            if node is None:
                if not tolerant:
                    raise LineageError("UNKNOWN_FEATURE", n)
                continue
            todo.extend(node.parents)
        return seen

    # -- lineage --------------------------------------------------------
    def ancestors(self, name):
        self._require(name)
        return self._reach(name) - {name}

    def sources(self, name):
        return sorted(a for a in self._reach(name)
                      if self.nodes[a].transform == "SOURCE")

    def chains(self, name):
        """Every transform chain from ``name`` down to a source."""
        self._require(name)
        out = []

        def rec(n, acc):
            node = self.nodes[n]
            acc = acc + ["%s[%s]" % (n, node.transform)]
            if not node.parents:
                out.append(acc)
            for p in node.parents:
                rec(p, acc)
        rec(name, [])
        return out

    def lineage(self, name):
        self._require(name)
        srcs = self.sources(name)
        return {"feature": name, "sources": srcs,
                "ancestors": sorted(self.ancestors(name)),
                "transform_chains": [" <- ".join(c) for c in self.chains(name)],
                "q_stations": sorted({self.nodes[s].q_station for s in srcs
                                      if self.nodes[s].q_station})}

    # -- time access ----------------------------------------------------
    def q_access(self, name, years):
        """station uid -> set of years (or ALL) of Q read when ``name`` is
        evaluated for ``years`` (iterable of int, or ALL)."""
        self._require(name)
        acc: Dict[str, object] = {}

        def merge(st, ys):
            if ys == ALL or acc.get(st) == ALL:
                acc[st] = ALL
            else:
                acc.setdefault(st, set()).update(ys)

        def rec(n, ys):
            node = self.nodes[n]
            t = node.transform
            if t == "SOURCE":
                if node.q_station:
                    merge(node.q_station, ys)
                return
            if t == "LAG":
                k = int(node.p("months", 1))
                ys2 = ALL if ys == ALL else {y - d for y in ys for d in
                                             {k // 12, -(-k // 12)}}
                for p in node.parents:
                    rec(p, ys2)
                return
            if t == "SMOOTH":
                w = int(node.p("window", 3))
                centered = bool(node.p("centered", False))
                span = -(-(w - 1) // 12) if w > 1 else 0
                ys2 = ALL if ys == ALL else {
                    y + d for y in ys for d in
                    range(-span, (span if centered else 0) + 1)}
                for p in node.parents:
                    rec(p, ys2)
                return
            if t == "SEASONAL_CORRECTION":
                rec(node.parents[0], ys)
                fy = node.fit_years if node.fit_years else ALL
                for p in node.parents[1:]:
                    rec(p, ALL if fy == ALL else set(fy))
                return
            if t == "FIT_NORMALIZE":
                fy = node.fit_years if node.fit_years else ALL
                for p in node.parents:
                    rec(p, ys)
                    rec(p, ALL if fy == ALL else set(fy))
                return
            for p in node.parents:
                rec(p, ys)

        rec(name, ALL if years == ALL else set(years))
        return acc


@dataclass
class TaskSpec:
    task: str
    target: str
    apply_dataset: str = "SYRDARYA"
    train_dataset: Optional[str] = None
    train_years: Tuple[int, ...] = ()
    eval_years: Tuple[int, ...] = ()


@dataclass
class Usage:
    feature: str
    role: str
    years: object = ALL          # tuple of years or ALL


@dataclass
class PlanReport:
    task: str
    target: str
    ok: bool
    violations: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)
    legal_label_use: List[dict] = field(default_factory=list)
    lineage: Dict[str, dict] = field(default_factory=dict)
    note: str = NOT_CERTIFIED_NOTE


def _years(ys):
    return ALL if ys == ALL else set(ys)


def _hits(access, years):
    if access is None:
        return set()
    if access == ALL:
        return ALL
    return set(access) & set(years)


def check_plan(graph, spec, usages):
    rep = PlanReport(spec.task, spec.target, True)
    if spec.task not in TASKS:
        rep.violations.append({"rule": "UNKNOWN_TASK", "task": spec.task,
                               "allowed": list(TASKS)})
        rep.ok = False
        return rep
    if not spec.target:
        rep.violations.append({"rule": "TARGET_MISSING"})
    if spec.task == MISSING_RECONSTRUCTION:
        if not spec.eval_years:
            rep.violations.append({"rule": "EVAL_YEARS_NOT_DECLARED"})
        if set(spec.train_years) & set(spec.eval_years):
            rep.violations.append({"rule": "SPLIT_OVERLAP", "years": sorted(
                set(spec.train_years) & set(spec.eval_years))})
    if spec.task == CROSS_SYSTEM and spec.train_dataset in (
            None, spec.apply_dataset):
        rep.violations.append({"feature": "*", "rule":
                               "CROSS_SYSTEM_REQUIRES_OTHER_TRAIN_SYSTEM"})
    for u in usages:
        base = {"feature": u.feature, "role": u.role}
        if u.role not in ROLES:
            rep.violations.append(dict(base, rule="UNKNOWN_ROLE"))
            continue
        try:
            lin = graph.lineage(u.feature)
            acc = graph.q_access(u.feature, _years(u.years))
        except LineageError as exc:
            rep.violations.append(dict(base, rule=exc.code,
                                       detail=str(exc.detail)))
            continue
        rep.lineage[u.feature] = lin
        tacc = acc.get(spec.target)
        if spec.task == ZERO_TARGET_Q:
            if tacc:
                if u.role == FINAL_SCORING:
                    rep.legal_label_use.append(dict(
                        base, rule="HELD_OUT_LABEL_IN_SCORING_ONLY"))
                else:
                    rep.violations.append(dict(
                        base, rule="TARGET_Q_IN_" + u.role,
                        chains=lin["transform_chains"]))
        elif spec.task == MISSING_RECONSTRUCTION:
            if tacc and u.role != FINAL_SCORING:
                hit = _hits(tacc, spec.eval_years)
                if hit:
                    rep.violations.append(dict(
                        base, rule="EVAL_LABEL_LEAKAGE_" + u.role,
                        target_years_read=("ALL" if tacc == ALL
                                           else sorted(tacc)),
                        eval_years_hit="ALL" if hit == ALL else sorted(hit),
                        chains=lin["transform_chains"]))
                elif not set(tacc) <= set(spec.train_years):
                    rep.violations.append(dict(
                        base, rule="TARGET_Q_OUTSIDE_TRAIN_YEARS",
                        target_years_read=sorted(tacc)))
                else:
                    rep.warnings.append(dict(
                        base, rule="TARGET_Q_TRAIN_YEARS_ONLY",
                        target_years_read=sorted(tacc)))
            elif tacc:
                rep.legal_label_use.append(dict(
                    base, rule="HELD_OUT_LABEL_IN_SCORING_ONLY"))
        elif spec.task == CROSS_SYSTEM:
            apply_q = {s for s in acc if s.startswith(spec.apply_dataset +
                                                      ":")}
            if u.role == FINAL_SCORING:
                if tacc:
                    rep.legal_label_use.append(dict(
                        base, rule="HELD_OUT_LABEL_IN_SCORING_ONLY"))
            elif u.role == INFERENCE_INPUT:
                if tacc:
                    rep.violations.append(dict(
                        base, rule="TARGET_Q_IN_INFERENCE_INPUT",
                        chains=lin["transform_chains"]))
                elif apply_q:
                    rep.warnings.append(dict(base, rule="ANCHOR_Q_INPUT",
                                             stations=sorted(apply_q)))
            elif apply_q:
                rep.violations.append(dict(base, rule="TRAIN_ON_APPLY_SYSTEM_Q",
                                           stations=sorted(apply_q)))
        for s in lin["sources"]:
            n = graph.nodes[s]
            if n.source_class in ("UNKNOWN", "REMOTE_SENSING"):
                rep.warnings.append(dict(
                    base, rule="INDEPENDENCE_NOT_CERTIFIED", source=s,
                    source_class=n.source_class))
            if n.unit == "UNKNOWN" and n.source_class != "OBSERVED_Q":
                rep.warnings.append(dict(base, rule="UNIT_UNKNOWN", source=s))
    rep.ok = not rep.violations
    return rep


# ---------------------------------------------------------------------------
# Synthetic executor (unit tests only)
# ---------------------------------------------------------------------------
def _shift(y, m, k):
    t = y * 12 + (m - 1) - k
    return t // 12, t % 12 + 1


def evaluate(graph, name, data, _memo=None):
    """Evaluate ``name`` on SYNTHETIC monthly series.

    ``data``: source name -> {(year, month): float}. Returns the same shape.
    Missing inputs propagate as absent keys (never 0).
    """
    graph._require(name)
    memo = {} if _memo is None else _memo
    if name in memo:
        return memo[name]
    node = graph.nodes[name]
    t = node.transform
    if t == "SOURCE":
        out = dict(data.get(name, {}))
    else:
        ps = [evaluate(graph, p, data, memo) for p in node.parents]
        a = ps[0] if ps else {}
        if t in ("SELECT", "RENAME", "MONTHLY_AGG"):
            out = dict(a)
        elif t == "UNIT_CONVERT":
            f = node.p("factor", 1.0)
            out = {k: v * f for k, v in a.items()}
        elif t == "ANNUAL_AGG":
            f = node.p("factor", 1.0)
            out = {}
            for y in {k[0] for k in a}:
                vals = [a.get((y, m)) for m in range(1, 13)]
                if all(v is not None for v in vals):
                    s = sum(vals) / 12.0 * f
                    out.update({(y, m): s for m in range(1, 13)})
        elif t == "LAG":
            k = int(node.p("months", 1))
            out = {}
            for (y, m) in {kk for kk in a} | {_shift(*kk, -k) for kk in a}:
                src = _shift(y, m, k)
                if src in a:
                    out[(y, m)] = a[src]
        elif t == "SMOOTH":
            w = int(node.p("window", 3))
            out = {}
            for (y, m) in a:
                vals = [a.get(_shift(y, m, i)) for i in range(w)]
                if all(v is not None for v in vals):
                    out[(y, m)] = sum(vals) / w
        elif t in ("DIFF", "LINEAR", "INVERSION"):
            coefs = node.p("coefs") or ((1.0, -1.0) if t == "DIFF" else
                                        tuple(1.0 for _ in ps))
            const = node.p("const", 0.0)
            scale = node.p("scale", 1.0)
            keys = set(ps[0]).intersection(*[set(p) for p in ps[1:]])
            out = {k: scale * (const + sum(c * p[k] for c, p in
                                           zip(coefs, ps))) for k in keys}
        elif t == "SEASONAL_CORRECTION":
            ref = ps[1]
            fy = node.fit_years
            clim = {}
            for m in range(1, 13):
                vals = [v for (y, mm), v in ref.items() if mm == m and
                        (fy in (None, ALL) or y in fy)]
                if vals:
                    clim[m] = sum(vals) / len(vals)
            out = {k: v - clim[k[1]] for k, v in a.items() if k[1] in clim}
        elif t == "FIT_NORMALIZE":
            fy = node.fit_years
            vals = [v for (y, m), v in a.items()
                    if fy in (None, ALL) or y in fy]
            mu = sum(vals) / len(vals) if vals else 0.0
            sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 \
                if vals else 1.0
            sd = sd or 1.0
            out = {k: (v - mu) / sd for k, v in a.items()}
        else:
            raise LineageError("UNKNOWN_TRANSFORM", t)
    memo[name] = out
    return out
