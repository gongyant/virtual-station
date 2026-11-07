"""Pure, synthetic-testable QC. Never uses another station or predictions."""
import calendar
import math

VERSION = "VHS-SCI-S1-QC-2.0.0"
RULES = {
    "version": VERSION, "w_relative_tolerance": 0.05,
    "candidate_w_main_relative_tolerance": 0.10,
    "candidate_w_sensitivity_tolerances": [0.05, 0.20],
    "within_station_scale_log10_threshold": 2.5,
    "within_station_scale_min_other_years": 3,
    "suspect_placeholder_tokens": [-999, 9999],
    "sequence_min_run": 3, "repeat_min_run": 3, "absolute_tolerance": 1e-6,
    "w_scale_ratio_range": [900, 1100],
    "meteorology_required_daily_fraction": 1.0,
    "remote_sensing_min_image_count": 1,
    "year_complete_months": 12,
    "intrinsic_grade_A": "finite nonnegative mean; no own suspicion or unresolved credible extrema conflict",
    "intrinsic_grade_B": "finite nonnegative but own repeat/sequence or one-sided extrema suspicion",
    "intrinsic_grade_C": "structural invalidity or credible two-sided MEAN_CONFLICT",
    "admission_tier_A": "intrinsic mean A; auxiliaries A; annual W consistent at 10 percent",
    "admission_tier_B": "intrinsic mean A; only extrema suspect/missing/swapped or W missing/untestable",
    "admission_tier_C": "intrinsic mean suspect/invalid, own token/scale suspect, or unresolved W inconsistency",
    "strict": "admission tier A at main W threshold",
    "claude_core": "admission tier A or B at main W threshold",
    "mean_first": "intrinsic mean A; extrema/W admission tier kept separately",
    "stress": "all finite nonnegative, unique structurally valid means including quarantined C; not missing/invalid",
    "unit_gate": "all counts conditional on source units; no conversion of Q",
    "forbidden_selection": ["upstream/downstream Q agreement", "model residual or prediction error"],
}
SCHEMES = ("strict", "claude_core", "mean_first", "stress")


def number(raw):
    if raw is None or str(raw).strip() == "":
        return None, "BLANK"
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None, "NONNUMERIC"
    return v, ("FINITE" if math.isfinite(v) else "NONFINITE")


def suspicious_runs(values, predicate, minimum):
    found, run = set(), []
    for i, v in enumerate(values):
        if predicate(i, v, run):
            run.append(i)
        else:
            if len(run) >= minimum:
                found.update(run)
            run = [i] if v is not None and math.isfinite(v) else []
            # Sequence runs must start on a matching value.
            if run and not predicate(i, v, []):
                run = []
    if len(run) >= minimum:
        found.update(run)
    return found


def variable(raw_values, record_exists=True, duplicate=False):
    """12 independent variable grades; nonempty is distinct from numeric."""
    if len(raw_values) != 12:
        raise ValueError("exactly 12 months required")
    parsed = [number(v) for v in raw_values]
    vals = [v for v, _ in parsed]
    seq = suspicious_runs(vals, lambda i, v, r: v is not None and
                          math.isfinite(v) and abs(v - (i + 1)) <= 1e-6, 3)
    repeat = suspicious_runs(vals, lambda i, v, r: v is not None and
                             math.isfinite(v) and (not r or
                             abs(v - vals[r[-1]]) <= 1e-6), 3)
    out = []
    for i, ((v, state), raw) in enumerate(zip(parsed, raw_values)):
        flags = []
        nonempty = raw is not None and str(raw).strip() != ""
        if not record_exists:
            flags.append("NO_RECORD_YEAR")
        elif state != "FINITE":
            flags.append(state)
        if duplicate:
            flags.append("DUPLICATE_STATION_YEAR")
        if v is not None and math.isfinite(v) and v < 0:
            flags.append("NEGATIVE")
        invalid = not record_exists or duplicate or state != "FINITE" or v < 0
        if i in seq:
            flags.append("SEQUENCE_INDEX_SUSPECT")
        if i in repeat:
            flags.append("REPEATED_VALUE_SUSPECT")
        grade = "C" if invalid else ("B" if i in seq or i in repeat else "A")
        out.append({"record_exists": record_exists, "raw_nonempty": nonempty,
                    "numeric_finite": state == "FINITE", "grade": grade,
                    "flags": flags, "value": v})
    return out


def annual_w(year, mean, raw_w, tolerance=0.05):
    w, ws = number(raw_w)
    if any(o["value"] is None or not math.isfinite(o["value"]) for o in mean):
        return "NOT_CHECKABLE_MISSING_MONTHS"
    if any(o["value"] < 0 for o in mean):
        return "NOT_CHECKABLE_INVALID_MEAN"
    if ws == "BLANK":
        return "W_MISSING_IN_SOURCE"
    if ws != "FINITE" or w < 0:
        return "W_INVALID"
    wq = sum(o["value"] * calendar.monthrange(year, m)[1] * 86400
             for m, o in enumerate(mean, 1)) / 1e6
    if w == 0:
        return "W_ZERO"
    if abs((wq - w) / w) <= tolerance:
        return "CONSISTENT"
    if 900 <= wq / w <= 1100:
        return "W_UNIT_SCALE_SUSPECT"
    return "W_INCONSISTENT"


def station_year(year, raw=None, duplicate=False, scale_suspect=False):
    exists = raw is not None
    raw = raw or {"mean": [None] * 12, "max": [None] * 12,
                  "min": [None] * 12, "W": None}
    variables = {k: variable(raw[k], exists, duplicate) for k in ("mean", "max", "min")}
    # Extrema suspects do not contaminate mean. With contradictory credible
    # extrema the cause is unknown: mark suspicion, never correct a value.
    for i in range(12):
        mn, me, mx = (variables[k][i] for k in ("min", "mean", "max"))
        if me["grade"] == "C":
            continue
        if mn["grade"] == mx["grade"] == "A":
            if mn["value"] > mx["value"] and mx["value"] <= me["value"] <= mn["value"]:
                for ob in (mn, mx):
                    ob["grade"] = "B"; ob["flags"].append("MINMAX_SWAPPED")
                me["flags"].append("AUX_MINMAX_SWAPPED")
                continue
            if not min(mn["value"], mx["value"]) - 1e-6 <= me["value"] <= max(mn["value"], mx["value"]) + 1e-6:
                me["grade"] = "C"; me["flags"].append("MEAN_CONFLICT")
                continue
        for ob, bad, flag in ((mn, mn["grade"] == "A" and mn["value"] > me["value"] + 1e-6,
                               "MIN_GT_MEAN"),
                              (mx, mx["grade"] == "A" and mx["value"] < me["value"] - 1e-6,
                               "MAX_LT_MEAN")):
            if bad:
                me["flags"].append(flag)
                ob["flags"].append(flag)
                me["grade"] = ob["grade"] = "B"
    w_status = annual_w(year, variables["mean"], raw["W"]) if exists else "NO_RECORD_YEAR"
    w_statuses = {f"w{int(t * 100)}": annual_w(year, variables["mean"], raw["W"], t)
                  if exists else "NO_RECORD_YEAR" for t in (0.05, 0.10, 0.20)}
    for i, me in enumerate(variables["mean"]):
        if scale_suspect:
            me["flags"].append("WITHIN_STATION_SCALE_SUSPECT")
        if me["value"] in RULES["suspect_placeholder_tokens"]:
            me["flags"].append("TYPICAL_TOKEN_SUSPECT")
        tiers, reasons = {}, {}
        for name, ws in w_statuses.items():
            flags = []
            if me["grade"] != "A" or scale_suspect or "TYPICAL_TOKEN_SUSPECT" in me["flags"]:
                tier = "C"; flags.append("MEAN_INTRINSIC_INVALID_OR_SUSPECT")
            elif ws in ("W_INCONSISTENT", "W_UNIT_SCALE_SUSPECT", "W_INVALID", "W_ZERO"):
                tier = "C"; flags.append("ANNUAL_W_UNRESOLVED")
            elif ws != "CONSISTENT" or any(variables[k][i]["grade"] != "A" for k in ("min", "max")):
                tier = "B"; flags.append("AUXILIARY_EXTREMA_OR_W_UNCERTAIN")
            else:
                tier = "A"
            tiers[name], reasons[name] = tier, flags
        me["admission_tiers"], me["admission_reasons"] = tiers, reasons
        stress_ok = exists and not duplicate and me["value"] is not None and math.isfinite(me["value"]) and me["value"] >= 0
        me["usable"] = {
            "strict": tiers["w10"] == "A",
            "claude_core": tiers["w10"] in ("A", "B"),
            "mean_first": me["grade"] == "A" and not scale_suspect and "TYPICAL_TOKEN_SUSPECT" not in me["flags"],
            "stress": stress_ok,
        }
    return {"variables": variables, "W_status": w_status, "candidate_W_statuses": w_statuses}


def public_month(qc, month):
    """Explicit whitelist: no raw observations or derived Q/W leave memory."""
    i = month - 1
    out = {"record_exists": qc["variables"]["mean"][i]["record_exists"],
           "raw_nonempty": qc["variables"]["mean"][i]["raw_nonempty"],
           "W_status": qc["W_status"]}
    for k in ("mean", "max", "min"):
        ob = qc["variables"][k][i]
        out[k + "_grade"] = ob["grade"]
        out[k + "_flags"] = "|".join(ob["flags"])
    for scheme in SCHEMES:
        out[scheme + "_usable"] = qc["variables"]["mean"][i]["usable"][scheme]
    me = qc["variables"]["mean"][i]
    out["admission_tier"] = me["admission_tiers"]["w10"]
    out["admission_flags"] = "|".join(me["admission_reasons"]["w10"])
    for name in ("w5", "w10", "w20"):
        out["admission_tier_" + name] = me["admission_tiers"][name]
        out["candidate_W_status_" + name] = qc["candidate_W_statuses"][name]
        out["core_" + name + "_usable"] = me["admission_tiers"][name] in ("A", "B")
    return out
