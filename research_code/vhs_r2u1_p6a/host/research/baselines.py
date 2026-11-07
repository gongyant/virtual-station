"""
research/baselines.py  --  Syr Darya baseline interfaces (NO execution)
======================================================================

Defines SYR-B0 / SYR-B1 / SYR-B2, the three experimental task types, a
feature-lineage catalogue, a data-availability clock and an automatic
Q-derived leakage guard.

v0.5.1: the catalogue is a recursive feature DAG (research/feature_dag.py).
``check_leakage`` follows every ancestor (renamed / multi-level / unit
converted / aggregated / lagged / smoothed / fitted features inherit the
lineage of their parents), rejects unknown tasks and unknown features, and
in CROSS_SYSTEM_GENERALIZATION refuses target Q as an application-time
input (Codex P1-01 counter-examples).

Nothing here trains, scores, tunes or predicts. ``run_baseline`` always
returns MODEL_EXECUTION = NOT_AUTHORIZED with prediction = None.
"""

from dataclasses import dataclass, field
from typing import List

from research import feature_dag as FD

MODEL_EXECUTION = "NOT_AUTHORIZED"

# --- task types (kept strictly apart) --------------------------------------
MISSING_RECONSTRUCTION = FD.MISSING_RECONSTRUCTION   # target has Q in other periods
ZERO_TARGET_Q = FD.ZERO_TARGET_Q                     # target Q never available
CROSS_SYSTEM = FD.CROSS_SYSTEM                       # train elsewhere, apply here
TASKS = {
    MISSING_RECONSTRUCTION:
        "站点缺测重建：目标站在其他时段有 Q，可用于校准；必须按时间切分，"
        "评估期的目标 Q 不得进入特征、预处理参数或模型选择。",
    ZERO_TARGET_Q:
        "无目标站 Q 校准：目标站 Q 在任何时段都不可用；任何谱系（递归）包含目标站 Q "
        "的特征（含 dW、反演引水、残余、滞后/平滑/季节校正）一律禁止；仅最终评分可读留出标签。",
    CROSS_SYSTEM:
        "跨独立水文系统泛化：在另一水文系统（如 LAMAHCE）训练，应用到本系统；"
        "训练集不得包含应用系统的 Q，应用期输入不得含目标站 Q。",
}


def q(uid):
    return "Q:" + uid


UP = "SYRDARYA:16037"
DOWN = "SYRDARYA:16039"


def build_catalog():
    g = FD.FeatureGraph()
    g.add_source(q(UP), "SYRDARYA", "OBSERVED_Q", q_station=UP)
    g.add_source(q(DOWN), "SYRDARYA", "OBSERVED_Q", q_station=DOWN)
    g.add_source("MET:P", "SYRDARYA", "UNKNOWN",
                 note="met p; production chain (station / reanalysis) unknown")
    g.add_source("MET:T", "SYRDARYA", "UNKNOWN", note="met t")
    g.add_source("ET:SOURCE", "SYRDARYA", "UNKNOWN",
                 note="ET_mm in water-balance file; algorithm not in source")
    g.add_source("RS:CIRCLE", "SYRDARYA", "REMOTE_SENSING", unit="km2")
    g.add_source("RS:KZDAM", "SYRDARYA", "REMOTE_SENSING")
    g.add_source("PARAM:alpha", "SYRDARYA", "SCENARIO_PARAM", unit="1")
    g.add("Q_up_monthly_mean", "SELECT", q(UP), "SYRDARYA",
          note="anchor upstream discharge")
    g.add("Q_down_monthly_mean", "SELECT", q(DOWN), "SYRDARYA",
          note="target discharge in the 16037->16039 case")
    g.add("W_up_annual", "ANNUAL_AGG", "Q_up_monthly_mean", "SYRDARYA",
          unit="10^6 m3", factor=31.536)
    g.add("W_down_annual", "ANNUAL_AGG", "Q_down_monthly_mean", "SYRDARYA",
          unit="10^6 m3", factor=31.536)
    g.add("dW_reach", "DIFF", ("W_up_annual", "W_down_annual"), "SYRDARYA",
          note="upstream minus downstream volume")
    g.add("P_daily", "SELECT", "MET:P", "SYRDARYA")
    g.add("T_daily", "SELECT", "MET:T", "SYRDARYA")
    g.add("P_monthly_sum", "MONTHLY_AGG", "P_daily", "SYRDARYA")
    g.add("P_vol", "UNIT_CONVERT", "P_monthly_sum", "SYRDARYA")
    g.add("ET_vol", "UNIT_CONVERT", "ET:SOURCE", "SYRDARYA")
    g.add("intake_alpha", "INVERSION",
          ("dW_reach", "P_vol", "ET_vol", "PARAM:alpha"), "SYRDARYA",
          note="inverted intake scenario alpha*(dW-P_vol+ET_vol)")
    g.add("wb_residual", "LINEAR",
          ("dW_reach", "P_vol", "ET_vol", "intake_alpha"), "SYRDARYA",
          coefs=(1.0, -1.0, 1.0, -1.0))
    g.add("circle_area_A_G", "SELECT", "RS:CIRCLE", "SYRDARYA", unit="km2",
          note="remote sensing; independence of production chain unverified")
    g.add("kzdam_KC_KU", "SELECT", "RS:KZDAM", "SYRDARYA",
          note="unit unknown; excluded from B2 until unit is traced")
    return g


GRAPH = build_catalog()
CATALOG = {k: v for k, v in GRAPH.nodes.items() if v.transform != "SOURCE"}

BASELINES = {
    "SYR-B0": {"title": "锚点流量基线", "features": ["Q_up_monthly_mean"],
               "target": DOWN},
    "SYR-B1": {"title": "锚点流量 + 气象",
               "features": ["Q_up_monthly_mean", "P_monthly_sum", "T_daily"],
               "target": DOWN},
    "SYR-B2": {"title": "锚点流量 + 气象 + 独立遥感",
               "features": ["Q_up_monthly_mean", "P_monthly_sum", "T_daily",
                            "circle_area_A_G"],
               "target": DOWN},
}


@dataclass
class LeakageReport:
    task: str
    target: str
    ok: bool
    violations: List[dict] = field(default_factory=list)
    warnings: List[dict] = field(default_factory=list)


def check_leakage(feature_names, target_uid, task, train_dataset=None,
                  apply_dataset="SYRDARYA", catalog=None):
    """Return a LeakageReport for inference-input use of ``feature_names``.

    ``catalog`` may be a FD.FeatureGraph (defaults to GRAPH). Lineage is
    recursive. Unknown task / feature / cycle are violations.
    """
    g = catalog if isinstance(catalog, FD.FeatureGraph) else GRAPH
    rep = LeakageReport(task, target_uid, True)
    if task not in TASKS:
        rep.violations.append({"feature": "*", "rule": "UNKNOWN_TASK",
                               "allowed": list(TASKS)})
        rep.ok = False
        return rep
    for name in feature_names:
        try:
            lin = g.lineage(name)
        except FD.LineageError as exc:
            rule = ("UNKNOWN_FEATURE_LINEAGE" if exc.code == "UNKNOWN_FEATURE"
                    else exc.code)
            rep.violations.append({"feature": name, "rule": rule,
                                   "detail": str(exc.detail)})
            continue
        uses_target = target_uid in lin["q_stations"]
        info = {"lineage": lin["sources"],
                "chains": lin["transform_chains"]}
        if task == ZERO_TARGET_Q and uses_target:
            rep.violations.append(dict(info, feature=name,
                                       rule="TARGET_Q_DERIVED_FORBIDDEN"))
        elif task == MISSING_RECONSTRUCTION and uses_target:
            rep.warnings.append(dict(info, feature=name,
                                     rule="REQUIRES_TEMPORAL_SPLIT"))
        elif task == CROSS_SYSTEM:
            if uses_target:
                rep.violations.append(dict(info, feature=name,
                                           rule="TARGET_Q_IN_INFERENCE_INPUT"))
            elif lin["q_stations"] and train_dataset == apply_dataset:
                rep.violations.append(dict(info, feature=name,
                                           rule="TRAIN_ON_APPLY_SYSTEM_Q"))
        node = g.nodes[name]
        if node.unit == "UNKNOWN" and name.startswith("kzdam"):
            rep.warnings.append({"feature": name, "rule": "UNIT_UNKNOWN"})
    if task == CROSS_SYSTEM and train_dataset in (None, apply_dataset):
        rep.violations.append({"feature": "*",
                               "rule": "CROSS_SYSTEM_REQUIRES_OTHER_TRAIN_SYSTEM"})
    rep.ok = not rep.violations
    return rep


def availability_clock(store, year, month):
    """What inputs exist for a given month (no values, only availability)."""
    disc = {}
    for code in (UP.split(":")[1], DOWN.split(":")[1]):
        obs = [o for o in store.discharge
               if o.station_uid.endswith(":" + code) and o.year == year and
               o.month == month and o.stat == "mean"]
        if not obs:
            disc[code] = "NO_RECORD_YEAR"
        elif obs[0].value is None:
            disc[code] = "MISSING"
        elif obs[0].flags:
            disc[code] = "SUSPECT"
        else:
            disc[code] = "AVAILABLE"
    mm = store.met_monthly(year)[month - 1] if \
        store.met_range[0][:4] <= "%04d" % year <= store.met_range[1][:4] \
        else None
    circles = [o for o in store.rs if o.product == "CIRCLE" and
               o.year == year and o.month == month and o.value is not None]
    kz = [o for o in store.rs if o.product == "KZDAM" and o.year == year and
          o.month == month and o.value is not None]
    return {
        "year": year, "month": month,
        "discharge_mean": disc,
        "meteorology": ("COMPLETE" if mm and mm["complete"] else
                        ("PARTIAL" if mm else "OUT_OF_RANGE")),
        "circles_observed": sorted({o.site for o in circles}),
        "kzdam_observed": sorted({o.site for o in kz}),
    }


def run_baseline(name, *args, **kwargs):
    if name not in BASELINES:
        return {"status": "UNKNOWN_BASELINE", "prediction": None}
    return {"status": MODEL_EXECUTION, "baseline": name, "prediction": None,
            "reason": "MODEL_EXECUTION = NOT_AUTHORIZED; only interfaces, "
                      "availability and leakage checks exist in v0.5.1."}


def feature_table():
    out = []
    for name in CATALOG:
        lin = GRAPH.lineage(name)
        out.append({"feature": name, "sources": lin["sources"],
                    "transform_chains": lin["transform_chains"],
                    "target_q_derived": DOWN in lin["q_stations"],
                    "zero_target_q_input": "BLOCKED: 谱系含目标站 Q"
                    if DOWN in lin["q_stations"] else "NOT_BLOCKED_BY_LINEAGE"})
    return out


def summary():
    out = []
    for name, b in BASELINES.items():
        reps = {t: check_leakage(b["features"], b["target"], t,
                                 train_dataset="LAMAHCE"
                                 if t == CROSS_SYSTEM else None).__dict__
                for t in TASKS}
        out.append({"baseline": name, "title": b["title"],
                    "features": b["features"], "target": b["target"],
                    "leakage": reps, "execution": MODEL_EXECUTION,
                    "prediction": None})
    return {"tasks": TASKS, "baselines": out, "features": feature_table(),
            "lineage_check": "RECURSIVE_DAG (v0.5.1)",
            "badge_meaning": "目录谱系检查通过 ≠ 已执行实验；未运行任何模型",
            "independence_note": FD.NOT_CERTIFIED_NOTE,
            "model_execution": MODEL_EXECUTION}
