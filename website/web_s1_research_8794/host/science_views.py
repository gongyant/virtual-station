"""
science_views.py  --  VHS v0.5.1 research-display correctness (Codex P1-03..05)

All numbers are recomputed from the in-memory verified snapshot at first use
and cached (the snapshot is immutable). Nothing is hard-coded: the review's
values (366 / 259-80-7-18-2 / 391 runs / 2671 cells / 2831 equal-month /
20.31 % and -16.88 %) are only used by the tests as an external comparison.

Outputs contain identifiers, counts, flags and a few clearly labelled
diagnostics; no raw monthly Q series is returned here.
"""
import calendar

import syrdarya_adapter as SA
from research import baselines as RB

TARGET_Q_NOTICE = "不可用于严格零目标 Q 模型输入（TARGET_Q_DERIVED：谱系含目标站 Q）"
CATEGORIES = ["CONSISTENT", "W_INCONSISTENT", "W_MISSING_IN_SOURCE",
              "NOT_CHECKABLE_MISSING_MONTHS", "W_UNIT_SCALE_SUSPECT"]
CLASSIFICATION_RULE = (
    "按顺序互斥判定：①12 个月均有缺→NOT_CHECKABLE_MISSING_MONTHS；②源 W 空→"
    "W_MISSING_IN_SOURCE（源 W=0→W_ZERO）；③|W_Q−W_源|/W_源 ≤5%→CONSISTENT；"
    "④W_Q/W_源 在 900–1100→W_UNIT_SCALE_SUSPECT；⑤其余→W_INCONSISTENT。"
    "W_Q=Σ Q_m·该月实际天数·86400/1e6（假设 Q 为 m³/s，单位 10⁶ m³）。")


def dual_pct(w_q, w_s):
    """Both denominators, each explicitly labelled (Codex Q2)."""
    if w_q is None or w_s in (None, 0):
        return None
    return {
        "W_from_Q": w_q, "W_source": w_s, "abs_diff_WQ_minus_Wsource": w_q - w_s,
        "pct_denominator_W_source": (w_q - w_s) / w_s * 100.0,
        "pct_denominator_W_source_label":
            "(W_Q − W_源)/W_源：以源 W 为分母，月积分相对源值的偏差",
        "pct_denominator_W_from_Q": (w_s - w_q) / w_q * 100.0,
        "pct_denominator_W_from_Q_label":
            "(W_源 − W_Q)/W_Q：以月积分为分母，源值相对月积分的偏差",
    }


class ScienceViews:
    def __init__(self, store):
        self.s = store
        self._cache = None

    def build(self):
        if self._cache is None:
            s = self.s
            self._cache = {
                "snapshot_id": s.snapshot.snapshot_id if s.snapshot else None,
                "qc_classification": self.qc_classification(),
                "sequence_index": self.sequence_index(),
                "case_16037_2008": self.case(SA.REACH_UP, 2008),
                "annual_w_policy": {
                    "source_value_overwritten": False,
                    "display": "源 W 与 Q 积分 W 并列显示；任何情况下都不改写源值"},
                "water_balance_w_formula": self.wb_formula(),
                "units": self.units(),
                "target_q_derived": self.target_q_labels(),
            }
        return self._cache

    # 1 -----------------------------------------------------------------
    def qc_classification(self):
        s = self.s
        rows = [{"station": c["station"], "year": c["year"],
                 "category": c["status"]} for c in s.w_checks]
        counts = {k: 0 for k in CATEGORIES}
        other = {}
        for r in rows:
            if r["category"] in counts:
                counts[r["category"]] += 1
            else:
                other[r["category"]] = other.get(r["category"], 0) + 1
        n_rec = s.files["discharge"].get("records")
        return {"rule": CLASSIFICATION_RULE, "tolerance": SA.W_REL_TOL,
                "counts": counts, "other_categories": other,
                "n_station_years": len(rows), "n_discharge_records": n_rec,
                "closed": sum(counts.values()) == len(rows) == n_rec and
                not other,
                "rows": rows}

    # 2/3 ---------------------------------------------------------------
    def sequence_index(self):
        s = self.s
        runs = s.seq_runs
        cells = {}
        affected = {}
        for r in runs:
            cells[r["stat"]] = cells.get(r["stat"], 0) + len(r["months"])
            affected.setdefault(r["stat"], set()).add((r["station"],
                                                       r["year"]))
        eq = {}
        for o in s.discharge:
            if o.value is not None and abs(o.value - o.month) < SA.FLOAT_TOL:
                eq[o.stat] = eq.get(o.stat, 0) + 1
        n_cells = sum(cells.values())
        n_eq = sum(eq.values())
        wcat = {(c["station"], c["year"]): c["status"] for c in s.w_checks}
        scope = {}
        for st in ("mean", "max", "min"):
            sy = sorted(affected.get(st, set()))
            cats = {}
            for k in sy:
                cats[wcat.get(k)] = cats.get(wcat.get(k), 0) + 1
            scope[st] = {
                "runs": sum(1 for r in runs if r["stat"] == st),
                "flagged_cells": cells.get(st, 0),
                "equal_month_cells": eq.get(st, 0),
                "station_years": len(sy),
                "station_year_list": ["%s/%d" % k for k in sy],
                "w_category_of_affected_station_years": cats}
        return {
            "rule": "同一站-年-统计量内，连续 ≥%d 个月数值恰等于月序号 → "
                    "SEQUENCE_INDEX_SUSPECT（保留原值，默认不绘制，不判定为确认缺失）"
                    % SA.SEQ_RUN_MIN,
            "runs_total": len(runs),
            "flagged_cells_total": n_cells,
            "equal_month_cells_total": n_eq,
            "equal_month_not_in_run": n_eq - n_cells,
            "by_stat": scope,
            "semantics": "run = 一段连续疑似序号；cell = 被标记的单元格；二者不可混用",
            "runs": runs,
        }

    # 4/5 ---------------------------------------------------------------
    def case(self, code, year):
        c = [x for x in self.s.w_checks if x["station"] == SA.uid(code) and
             x["year"] == year]
        if not c:
            return None
        c = c[0]
        out = {"station": c["station"], "year": year,
               "category": c["status"],
               "W_source_unit": "10^6 m3 (source header)",
               "W_from_Q_hypothesis": "Q in m3/s; actual days per month",
               "source_value_overwritten": False,
               "target_q_notice": TARGET_Q_NOTICE + "（若该站作为目标站）"}
        out.update(dual_pct(c.get("W_from_Q"), c.get("W_source")) or {})
        return out

    # 6 -----------------------------------------------------------------
    def _monthly_means(self, code, year):
        v = {o.month: o.value for o in self.s.discharge
             if o.station_uid == SA.uid(code) and o.year == year and
             o.stat == "mean"}
        vals = [v.get(m) for m in range(1, 13)]
        return None if any(x is None for x in vals) else vals

    def wb_formula(self):
        cands = {
            "EQUAL_MONTH_FIXED_365":
                ("W = (Σ_{m=1..12} Q_m / 12) × 365 × 86400 / 1e9",
                 lambda q, y: sum(q) / 12 * 365 * 86400 / 1e9),
            "EQUAL_MONTH_DAYS_IN_YEAR":
                ("W = (Σ Q_m / 12) × (365 或 366) × 86400 / 1e9",
                 lambda q, y: sum(q) / 12 * (366 if calendar.isleap(y)
                                             else 365) * 86400 / 1e9),
            "ACTUAL_MONTH_DAYS":
                ("W = Σ Q_m × 该月实际天数 × 86400 / 1e9",
                 lambda q, y: sum(v * calendar.monthrange(y, m + 1)[1]
                                  for m, v in enumerate(q)) * 86400 / 1e9),
            "MONTH_30_DAYS":
                ("W = Σ Q_m × 30 × 86400 / 1e9",
                 lambda q, y: sum(q) * 30 * 86400 / 1e9),
        }
        years = sorted({b.year for b in self.s.wb})
        worst = {k: 0.0 for k in cands}
        n = 0
        for y in years:
            b = [x for x in self.s.wb if x.year == y][0]
            for code, wv in ((SA.REACH_UP, b.W_up), (SA.REACH_DOWN, b.W_down)):
                q = self._monthly_means(code, y)
                if q is None or wv is None:
                    continue
                n += 1
                for k, (_, f) in cands.items():
                    rel = abs(f(q, y) - wv) / max(abs(wv), 1e-12)
                    worst[k] = max(worst[k], rel)
        tol = 1e-6
        detected = [k for k in cands if worst[k] <= tol]
        return {
            "comparisons": n, "years": years, "tolerance_rel": tol,
            "candidates": {k: {"formula": cands[k][0],
                               "max_rel_error": worst[k]} for k in cands},
            "detected": detected,
            "formula_in_use": cands[detected[0]][0] if len(detected) == 1
            else ("UNDETERMINED" if not detected else
                  " / ".join(cands[k][0] for k in detected)),
            "note": "由水量平衡文件 W上/W下 与 16037/16039 月均 Q 逐年逐站复算比对得到的数值事实；"
                    "单位按 Q=m³/s 假设得 km³，体积列单位仍为 UNKNOWN；"
                    "不同于流量文件源 W（10⁶ m³）的年度口径。",
            "target_q_notice": "W下 及由其派生的 dW/引水/残余：" + TARGET_Q_NOTICE,
        }

    # 7 -----------------------------------------------------------------
    def alpha_view(self, year, width, alpha):
        b = [x for x in self.s.wb if x.year == year and
             abs(x.half_width_km - width) < 1e-9]
        if not b:
            return None
        b = b[0]
        scen = {round(i.alpha, 2): i.value for i in self.s.intakes
                if i.year == year}
        # the source W_intake is rounded (e.g. 2.304 vs scenario 2.30422):
        # match the scenario within 0.1 % relative, closest one wins
        near = sorted((abs(v - b.W_intake) / max(abs(b.W_intake), 1e-12), a)
                      for a, v in scen.items() if v is not None and
                      b.W_intake is not None)
        src_alpha = [a for r, a in near if r <= 1e-3][:1]
        sel = scen.get(round(alpha, 2))

        def fc(i):
            return None if None in (b.dW, b.P_vol, b.ET_vol, i) else \
                b.dW - b.P_vol + b.ET_vol - i

        def cv(i):
            return None if None in (b.dW, b.P_vol, b.ET_vol, i) else \
                b.dW + b.P_vol - b.ET_vol - i
        return {
            "fixed_source_record": {
                "label": "固定源记录（对应源文件取水 W引水，不随 α 切换）",
                "W_intake_source": b.W_intake,
                "source_alpha_detected": src_alpha[0] if len(src_alpha) == 1
                else (src_alpha or "UNDETERMINED"),
                "residual_file_value": b.residual_file,
                "residual_file_formula": "源文件：残余 = dW − P_vol + ET_vol − W引水",
                "residual_control_volume_diagnostic": cv(b.W_intake),
            },
            "selected_scenario": {
                "label": "所选 α 情景（同单位假设下的情景代数，非实测）",
                "alpha": alpha, "W_intake_alpha": sel,
                "residual_file_formula_with_selected_intake": fc(sel),
                "residual_control_volume_diagnostic": cv(sel),
            },
            "all_alphas": [{"alpha": a, "W_intake": v,
                            "residual_file_formula": fc(v),
                            "residual_control_volume_diagnostic": cv(v)}
                           for a, v in sorted(scen.items())],
            "control_volume_definition":
                "ΔS = W_up − W_down + P − ET − I + J；诊断 R = dW + P_vol − ET_vol − I"
                "（假设 J=0、ΔS 未知；缓冲区面积≠已验证增量汇水区）",
            "units": "UNKNOWN（数值支持 km³ 假设，未确认）",
            "target_q_notice": TARGET_Q_NOTICE,
        }

    # 8 -----------------------------------------------------------------
    def units(self):
        s = self.s
        out = {
            "discharge_Q": sorted({o.unit for o in s.discharge}),
            "meteorology_P_T": sorted({o.unit for o in s.met}),
            "kzdam": sorted({o.unit for o in s.rs if o.product == "KZDAM"}),
            "circle_area": sorted({o.unit for o in s.rs
                                   if o.product == "CIRCLE"}),
            "intake_scenarios": sorted({i.unit for i in s.intakes}),
            "water_balance": dict(s.wb[0].units) if s.wb else {},
        }
        unknown_required = ["discharge_Q", "meteorology_P_T", "kzdam",
                            "intake_scenarios"]
        out["unconfirmed_kept_unknown"] = all(
            out[k] == ["UNKNOWN"] for k in unknown_required) and all(
            out["water_balance"].get(k) == "UNKNOWN" for k in
            ("W_up", "W_down", "dW", "P_vol", "ET_vol", "W_intake",
             "residual"))
        return out

    # 9 -----------------------------------------------------------------
    def target_q_labels(self):
        rows = []
        for f in RB.feature_table():
            if f["target_q_derived"]:
                rows.append({"diagnostic": f["feature"],
                             "eligibility": TARGET_Q_NOTICE,
                             "transform_chains": f["transform_chains"]})
        extra = ["annual W_from_Q of 16039 (target)", "W_down (water balance)",
                 "residual_file / residual_control_volume_diagnostic",
                 "selected α intake scenario"]
        return {"notice": TARGET_Q_NOTICE, "features": rows,
                "also_labelled_in_api": extra}
