"""
tests/test_feature_lineage.py -- VHS v0.5.1 recursive lineage + leakage +
counterfactual-invariance tests. PURE SYNTHETIC: no teacher file is read.

The 12 leakage cases (L01-L12) are INFERRED from REVIEW_REPORT.md (P1-01,
Q7) and NEXT_ROUND_TASKBOOK.md (test_feature_lineage list); no explicit
"12 cases" list attributed to a Claude review exists in the readable files.
L13-L16 are extra cases; N01-N06 are negative controls (must NOT be blocked);
CF-* are counterfactual target-Q deletion / permutation / scaling tests with a
deterministic synthetic linear "model" (closed-form least squares on
synthetic numbers; not a real model, nothing is trained on real data).

A pass does not certify that external remote sensing or pretrained models
are scientifically independent of the target Q.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

from _harness import Suite  # noqa: E402
from research import feature_dag as FD  # noqa: E402
from research import baselines as RB  # noqa: E402

S = Suite("test_feature_lineage")
T, U = "SYN:T", "SYN:U"
TRAIN = tuple(range(2003, 2011))
EVAL = (2014, 2015, 2016, 2017)
YEARS = TRAIN + EVAL


def graph():
    g = FD.FeatureGraph()
    g.add_source("Q:SYN:T", "SYN", "OBSERVED_Q", q_station=T)
    g.add_source("Q:SYN:U", "SYN", "OBSERVED_Q", q_station=U)
    g.add_source("MET:P", "SYN", "MET", unit="mm")
    g.add_source("Q:OTHER:D", "OTHER", "OBSERVED_Q", q_station="OTHER:D")
    g.add_source("Q:OTHER:UD", "OTHER", "OBSERVED_Q", q_station="OTHER:UD")
    g.add_source("PARAM:alpha", "SYN", "SCENARIO_PARAM", unit="1")
    g.add("QT", "SELECT", "Q:SYN:T")
    g.add("QU_in", "SELECT", "Q:SYN:U")
    g.add("P_in", "SELECT", "MET:P")
    g.add("QUD_in", "SELECT", "Q:OTHER:UD")
    g.add("QD_label", "SELECT", "Q:OTHER:D")
    g.add("QT_renamed", "RENAME", "QT")
    g.add("dW_T", "DIFF", ("QU_in", "QT"))
    g.add("dW_D", "DIFF", ("QUD_in", "QD_label"))
    g.add("renamed_dW", "RENAME", "dW_T")
    g.add("intake_alpha", "INVERSION", ("dW_T", "P_in", "PARAM:alpha"),
          coefs=(0.75, -0.75, 0.0))
    g.add("residual", "LINEAR", ("dW_T", "P_in", "intake_alpha"),
          coefs=(1.0, -1.0, -1.0))
    g.add("renamed_residual", "RENAME", "residual")
    g.add("QT_m3", "UNIT_CONVERT", "QT", factor=86400.0)
    g.add("WT_annual", "ANNUAL_AGG", "QT", factor=31.536)
    g.add("QT_lag1", "LAG", "QT", months=1)
    g.add("QT_lag12", "LAG", "QT", months=12)
    g.add("QT_smooth", "SMOOTH", "QT", window=3)
    g.add("QU_seasonal_by_T_train", "SEASONAL_CORRECTION", ("QU_in", "QT"),
          fit_years=TRAIN)
    g.add("QT_norm_all", "FIT_NORMALIZE", "QT", fit_years=FD.ALL)
    g.add("QT_norm_train", "FIT_NORMALIZE", "QT", fit_years=TRAIN)
    return g


def U_(f, r, y=FD.ALL):
    return FD.Usage(f, r, y)


ZERO = FD.TaskSpec(FD.ZERO_TARGET_Q, T, "SYN")
MREC = FD.TaskSpec(FD.MISSING_RECONSTRUCTION, T, "SYN", None, TRAIN, EVAL)
CROSS = FD.TaskSpec(FD.CROSS_SYSTEM, T, "SYN", "OTHER")
INP, LAB, PRE, SEL, SCO = (FD.INFERENCE_INPUT, FD.TRAINING_LABEL,
                           FD.PREPROCESSING_PARAM, FD.MODEL_SELECTION,
                           FD.FINAL_SCORING)


def rules(rep):
    return [v.get("rule") for v in rep.violations]


def leak_tests():
    g = graph()
    cases = [
        ("L01", "同名/直接目标 Q 作推理输入 (ZERO)", ZERO, [U_("QT", INP)],
         "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L02", "换名 renamed_dW (Codex 反例, ZERO)", ZERO,
         [U_("renamed_dW", INP)], "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L03", "多层派生 dW→引水→残余→换名 (ZERO)", ZERO,
         [U_("renamed_residual", INP)], "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L04", "单位换算 Q→m3 (ZERO)", ZERO, [U_("QT_m3", INP)],
         "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L05", "年度聚合 W_target (ZERO)", ZERO, [U_("WT_annual", INP)],
         "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L06", "滞后 1 月目标 Q 用于评价年 (MISSING_RECON)", MREC,
         [U_("QT_lag1", INP, EVAL)], "EVAL_LABEL_LEAKAGE_INFERENCE_INPUT"),
        ("L07", "平滑目标 Q (ZERO)", ZERO, [U_("QT_smooth", INP)],
         "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L08", "用目标 Q 拟合的季节校正参数 (ZERO, 预处理参数)", ZERO,
         [U_("QU_seasonal_by_T_train", PRE)],
         "TARGET_Q_IN_PREPROCESSING_PARAM"),
        ("L10", "未知任务 TYPO_TASK", FD.TaskSpec("TYPO_TASK", T, "SYN"),
         [U_("QU_in", INP)], "UNKNOWN_TASK"),
        ("L11", "CROSS_SYSTEM 训练域 OTHER, 应用期输入目标 Q", CROSS,
         [U_("QT", INP)], "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L12", "α 反演引水 (SCENARIO+TARGET_DERIVED) 作输入 (ZERO)", ZERO,
         [U_("intake_alpha", INP)], "TARGET_Q_IN_INFERENCE_INPUT"),
        ("L13", "评价年标签用于模型选择 (MISSING_RECON)", MREC,
         [U_("QT", SEL, EVAL)], "EVAL_LABEL_LEAKAGE_MODEL_SELECTION"),
        ("L14", "全年份拟合的归一化参数 (MISSING_RECON)", MREC,
         [U_("QT_norm_all", PRE, TRAIN)],
         "EVAL_LABEL_LEAKAGE_PREPROCESSING_PARAM"),
        ("L15", "未知特征", ZERO, [U_("mystery", INP)], "UNKNOWN_FEATURE"),
        ("L16", "未知角色", ZERO, [U_("QU_in", "SOMETHING")], "UNKNOWN_ROLE"),
        ("L17", "ZERO 中目标 Q 作训练标签", ZERO, [U_("QT", LAB)],
         "TARGET_Q_IN_TRAINING_LABEL"),
    ]
    for tid, title, spec, us, want in cases:
        rep = FD.check_plan(g, spec, us)
        S.check(tid, title + " -> " + want, (not rep.ok) and want in rules(rep),
                rules(rep))
    # L09 cycle
    g2 = graph()
    g2.add("A", "RENAME", "B")
    g2.add("B", "RENAME", "A")
    g2.add("C", "RENAME", "A")
    rep = FD.check_plan(g2, ZERO, [U_("C", INP)])
    S.check("L09", "循环依赖 A<->B 被检测并拒绝",
            not rep.ok and "CYCLE_DETECTED" in rules(rep), rules(rep))
    cyc = [p for p in g2.problems() if p["code"] == "CYCLE_DETECTED"]
    S.check("L09b", "problems() 报告循环路径",
            cyc and set(cyc[0]["cycle"]) >= {"A", "B"}, cyc)
    # lineage completeness
    lin = g.lineage("renamed_residual")
    S.check("D01", "多层派生保留全部变换链并递归到源",
            "Q:SYN:T" in lin["sources"] and "Q:SYN:U" in lin["sources"] and
            any("renamed_residual[RENAME]" in c and "residual[LINEAR]" in c and
                "dW_T[DIFF]" in c and "Q:SYN:T[SOURCE]" in c
                for c in lin["transform_chains"]) and
            any("intake_alpha[INVERSION]" in c
                for c in lin["transform_chains"]), lin)
    acc = g.q_access("QT_lag12", {2014})
    S.check("D02", "LAG12 在 2014 使用时读取 2013 年目标 Q",
            acc.get(T) == {2013}, acc)
    acc = g.q_access("QU_seasonal_by_T_train", set(EVAL))
    S.check("D03", "季节校正参数的目标 Q 读取年份=拟合年份",
            acc.get(T) == set(TRAIN) and acc.get(U) == set(EVAL), acc)
    try:
        g.add("bad", "MAGIC", "QT")
        ok = False
    except FD.LineageError as e:
        ok = e.code == "UNKNOWN_TRANSFORM"
    S.check("D04", "未知变换被拒绝", ok)
    try:
        g.add("QT", "SELECT", "Q:SYN:T")
        ok = False
    except FD.LineageError as e:
        ok = e.code == "DUPLICATE_NODE"
    S.check("D05", "重复节点被拒绝", ok)
    # negative controls
    neg = [
        ("N01", "ZERO: 上游 Q + 气象作输入允许", ZERO,
         [U_("QU_in", INP), U_("P_in", INP)]),
        ("N02", "ZERO: 最终评分读取留出目标标签合法", ZERO,
         [U_("QU_in", INP), U_("QT", SCO)]),
        ("N03", "MISSING_RECON: 训练年目标 Q 作训练标签允许", MREC,
         [U_("QT", LAB, TRAIN), U_("QU_in", INP, YEARS)]),
        ("N04", "MISSING_RECON: 评价年目标 Q 仅用于最终评分合法", MREC,
         [U_("QU_in", INP, EVAL), U_("QT", SCO, EVAL)]),
        ("N05", "CROSS: 他系统标签训练+锚点上游输入允许", CROSS,
         [U_("QD_label", LAB), U_("QUD_in", INP), U_("QU_in", INP),
          U_("QT", SCO)]),
        ("N06", "MISSING_RECON: 仅训练年拟合的季节校正用于评价年允许", MREC,
         [U_("QU_seasonal_by_T_train", INP, EVAL)]),
    ]
    for tid, title, spec, us in neg:
        rep = FD.check_plan(g, spec, us)
        S.check(tid, title, rep.ok, rep.violations)
    rep = FD.check_plan(g, ZERO, [U_("QT", SCO)])
    S.check("N07", "评分模块使用留出标签被记录为合法而非输入泄漏",
            rep.ok and rep.legal_label_use and
            rep.legal_label_use[0]["rule"] == "HELD_OUT_LABEL_IN_SCORING_ONLY",
            rep.__dict__)
    S.check("N08", "报告附带“不等于独立性认证”声明",
            "不代表" in rep.note)
    # production catalogue (Codex P1-01 counter-examples)
    g3 = RB.build_catalog()
    g3.add("renamed_dW", "RENAME", "dW_reach")
    r = RB.check_leakage(["renamed_dW"], RB.DOWN, RB.ZERO_TARGET_Q,
                         catalog=g3)
    S.check("P01", "产品目录: renamed_dW (lineage dW_reach) 在 ZERO 中被拒",
            not r.ok, r.__dict__)
    r = RB.check_leakage(["Q_up_monthly_mean"], RB.DOWN, "TYPO_TASK")
    S.check("P02", "产品目录: TYPO_TASK 被拒", not r.ok and
            r.violations[0]["rule"] == "UNKNOWN_TASK")
    r = RB.check_leakage(["Q_down_monthly_mean"], RB.DOWN, RB.CROSS_SYSTEM,
                         train_dataset="LAMAHCE")
    S.check("P03", "产品目录: CROSS(LAMAHCE) 应用期 Q_down 输入被拒",
            not r.ok and "TARGET_Q_IN_INFERENCE_INPUT" in
            [v["rule"] for v in r.violations])
    for name, b in RB.BASELINES.items():
        r = RB.check_leakage(b["features"], b["target"], RB.ZERO_TARGET_Q)
        S.check("P04-" + name[-2:], "%s 特征集在 ZERO 中谱系检查通过" % name, r.ok,
                r.violations)
    S.check("P05", "run_baseline 仍为 NOT_AUTHORIZED / prediction=None",
            RB.run_baseline("SYR-B1")["prediction"] is None and
            RB.run_baseline("SYR-B1")["status"] == "NOT_AUTHORIZED")


# ---------------------------------------------------------------------------
# counterfactual invariance with a deterministic synthetic linear model
# ---------------------------------------------------------------------------
def synth():
    d = {k: {} for k in ("Q:SYN:T", "Q:SYN:U", "MET:P", "Q:OTHER:D",
                         "Q:OTHER:UD", "PARAM:alpha")}
    for y in YEARS:
        for m in range(1, 13):
            qu = 100.0 + 10 * m + (y - 2000)
            p = 5.0 + (m * 7 % 11)
            d["Q:SYN:U"][(y, m)] = qu
            d["MET:P"][(y, m)] = p
            d["Q:SYN:T"][(y, m)] = 0.8 * qu + 2.0 * p + ((y * m) % 5)
            qud = 80.0 + 12 * m + 0.5 * (y - 2000)
            d["Q:OTHER:UD"][(y, m)] = qud
            d["Q:OTHER:D"][(y, m)] = 0.7 * qud + 1.5 * p + ((y + m) % 3)
            d["PARAM:alpha"][(y, m)] = 1.0
    return d


def variants(d, years):
    """Target-Q counterfactuals restricted to ``years``."""
    keys = sorted(k for k in d["Q:SYN:T"] if k[0] in years)
    out = {}
    dele = {k: dict(v) for k, v in d.items()}
    for k in keys:
        del dele["Q:SYN:T"][k]
    out["delete"] = dele
    perm = {k: dict(v) for k, v in d.items()}
    vals = [d["Q:SYN:T"][k] for k in keys][::-1]
    for k, v in zip(keys, vals):
        perm["Q:SYN:T"][k] = v
    out["permute"] = perm
    sc = {k: dict(v) for k, v in d.items()}
    for k in keys:
        sc["Q:SYN:T"][k] = d["Q:SYN:T"][k] * 1000.0 + 7.0
    out["scale"] = sc
    return out


def ols(X, y):
    """Closed-form least squares with intercept (Gauss-Jordan)."""
    A = [[1.0] + list(r) for r in X]
    k = len(A[0])
    M = [[sum(a[i] * a[j] for a in A) for j in range(k)] +
         [sum(a[i] * t for a, t in zip(A, y))] for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        pv = M[c][c]
        M[c] = [v / pv for v in M[c]]
        for r in range(k):
            if r != c:
                f = M[r][c]
                M[r] = [a - f * b for a, b in zip(M[r], M[c])]
    return tuple(round(M[i][k], 9) for i in range(k))


def design(g, feats, data, years):
    cols = [FD.evaluate(g, f, data) for f in feats]
    keys = sorted(k for k in cols[0] if k[0] in years and
                  all(k in c for c in cols))
    return keys, [tuple(c[k] for c in cols) for k in keys]


def predict(beta, X):
    return tuple(round(beta[0] + sum(b * x for b, x in zip(beta[1:], r)), 6)
                 for r in X)


def pipeline_zero(d, extra_t=(), extra_d=()):
    g = graph()
    fT = ["QU_in", "P_in"] + list(extra_t)
    fD = ["QUD_in", "P_in"] + list(extra_d)
    kD, XD = design(g, fD, d, YEARS)
    lab = FD.evaluate(g, "QD_label", d)
    kD2 = [k for k in kD if k in lab]
    XD2 = [x for k, x in zip(kD, XD) if k in lab]
    beta = ols(XD2, [lab[k] for k in kD2])
    kT, XT = design(g, fT, d, YEARS)
    preds = predict(beta, XT)
    qt = FD.evaluate(g, "QT", d)
    sc = [abs(p - qt[k]) for k, p in zip(kT, preds) if k in qt]
    score = round(sum(sc) / len(sc), 6) if sc else None
    return {"inputs": tuple(XT), "params": beta, "samples": tuple(kT),
            "preds": preds, "score": score}


def pipeline_mrec(d, extra=(), label_norm_all=False):
    g = graph()
    f = ["QU_in", "P_in"] + list(extra)
    k, X = design(g, f, d, YEARS)
    lab = FD.evaluate(g, "QT", d)
    if label_norm_all:     # LEAKY: normalisation fitted on ALL years
        vals = [v for kk, v in lab.items()]
        mu = sum(vals) / len(vals)
    else:                  # legal: fitted on training years only
        vals = [v for kk, v in lab.items() if kk[0] in TRAIN]
        mu = sum(vals) / len(vals)
    tr = [(kk, x) for kk, x in zip(k, X) if kk[0] in TRAIN and kk in lab]
    beta = ols([x for _, x in tr], [lab[kk] - mu for kk, _ in tr])
    ev = [(kk, x) for kk, x in zip(k, X) if kk[0] in EVAL]
    preds = tuple(round(p + mu, 6) for p in predict(beta, [x for _, x in ev]))
    return {"inputs": tuple(x for _, x in ev), "params": beta + (round(mu, 9),),
            "samples": tuple(kk for kk, _ in ev), "preds": preds}


def same(a, b, keys=("inputs", "params", "samples", "preds")):
    return all(a[k] == b[k] for k in keys)


def cf_tests():
    d = synth()
    g = graph()
    # ---- strict zero-target-Q -----------------------------------------
    base = pipeline_zero(d)
    rep = FD.check_plan(g, ZERO, [U_("QU_in", INP), U_("P_in", INP),
                                  U_("QD_label", LAB), U_("QT", SCO)])
    S.check("CF-Z0", "ZERO 合法管线通过谱系检查（评分读留出标签合法）",
            rep.ok and rep.legal_label_use, rep.violations)
    for name, dv in variants(d, YEARS).items():
        r = pipeline_zero(dv)
        S.check("CF-Z-" + name, "ZERO 目标 Q %s: 输入/参数/样本/推理完全不变" % name,
                same(base, r), {k: (base[k] == r[k]) for k in base})
    r = pipeline_zero(variants(d, YEARS)["scale"])
    S.check("CF-Z-score", "ZERO 评分随标签改变（评分合法使用留出标签）",
            r["score"] != base["score"], (r["score"], base["score"]))
    leaky = pipeline_zero(d, ("dW_T",), ("dW_D",))
    lv = pipeline_zero(variants(d, YEARS)["scale"], ("dW_T",), ("dW_D",))
    S.check("CF-Z-ctl", "阳性对照: 加入 dW_T 后推理随目标 Q 改变（测试有检出力）",
            leaky["preds"] != lv["preds"])
    rep = FD.check_plan(g, ZERO, [U_("dW_T", INP)])
    S.check("CF-Z-ctl2", "阳性对照同时被谱系检查拒绝", not rep.ok)
    # ---- missing reconstruction ---------------------------------------
    base = pipeline_mrec(d)
    rep = FD.check_plan(g, MREC, [U_("QU_in", INP, YEARS),
                                  U_("P_in", INP, YEARS),
                                  U_("QT", LAB, TRAIN), U_("QT", SCO, EVAL)])
    S.check("CF-M0", "MISSING_RECON 合法管线通过（训练年目标 Q 允许）", rep.ok,
            rep.violations)
    for name, dv in variants(d, set(EVAL)).items():
        r = pipeline_mrec(dv)
        S.check("CF-M-" + name,
                "MISSING_RECON 评价年目标 Q %s: 输入/参数/样本/推理不变" % name,
                same(base, r), {k: (base[k] == r[k]) for k in base})
    r = pipeline_mrec(variants(d, set(TRAIN))["scale"])
    S.check("CF-M-train", "训练年目标 Q 改变 → 参数改变（合法使用，非泄漏）",
            r["params"] != base["params"])
    lag = pipeline_mrec(d, ("QT_lag1",))
    lagv = pipeline_mrec(variants(d, set(EVAL))["scale"], ("QT_lag1",))
    rep = FD.check_plan(g, MREC, [U_("QT_lag1", INP, EVAL)])
    S.check("CF-M-ctl-lag",
            "阳性对照: 评价年 lag1 目标 Q 使推理随评价标签改变，且被谱系拒绝",
            lag["preds"] != lagv["preds"] and not rep.ok)
    n1 = pipeline_mrec(d, label_norm_all=True)
    n2 = pipeline_mrec(variants(d, set(EVAL))["scale"], label_norm_all=True)
    rep = FD.check_plan(g, MREC, [U_("QT_norm_all", PRE, TRAIN)])
    S.check("CF-M-ctl-norm",
            "阳性对照: 全年份标签归一化使参数随评价标签改变，且被谱系拒绝",
            n1["params"] != n2["params"] and not rep.ok)
    rep = FD.check_plan(g, MREC, [U_("QT_norm_train", PRE, TRAIN)])
    S.check("CF-M-norm-train", "仅训练年拟合的归一化参数允许", rep.ok,
            rep.violations)


if __name__ == "__main__":
    leak_tests()
    cf_tests()
    sys.exit(S.save({"twelve_cases_source":
                     "INFERRED from REVIEW_REPORT.md P1-01/Q7 and "
                     "NEXT_ROUND_TASKBOOK.md; no explicit 12-item list found",
                     "independence_note": FD.NOT_CERTIFIED_NOTE}))
