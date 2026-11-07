"""
research/prepare_baseline.py  --  VHS v0.5.1 research-ready validator

Builds a research-READY description of the Syr Darya case WITHOUT exporting
any observed value: outputs carry only identifiers, counts, statuses and
flags (W/research_ready). No model is trained, scored or run.

    python -B research/prepare_baseline.py            (on the user's PC)

Outputs (all in W/research_ready):
  qc_station_year.csv        station, year, QC category, sequence flag, months
  reach_month_status.csv     16037/16039 per year-month: mean/max/min status
  continuous_intervals.json  runs of consecutive usable months per station
  samples.csv                candidate sample ids + availability mask
  common_support.json        per baseline: months where ALL inputs + label ok
  target_q_blocks.json       features whose lineage contains target Q, per task
  task_eligibility.json      lineage check per baseline x task (NOT executed)
  manifest.json              snapshot id, sha256 of every output, self-check
"""
import csv
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
sys.dont_write_bytecode = True

import syrdarya_adapter as SA  # noqa: E402
from research import baselines as RB  # noqa: E402

OUT = os.path.join(APP, "research_ready")
UP, DOWN = SA.uid(SA.REACH_UP), SA.uid(SA.REACH_DOWN)
SAFE_CELL = re.compile(r"^[A-Za-z0-9_:\-./ ]*$")


def _write_csv(name, header, rows):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)
    return p


def _write_json(name, obj):
    p = os.path.join(OUT, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    return p


def status_of(o):
    if o is None:
        return "ABSENT"
    if o.value is None:
        return "MISSING"
    if "SEQUENCE_INDEX_SUSPECT" in o.flags:
        return "SUSPECT"
    return "OBSERVED"


def build(store):
    assert store.status == "OK", store.status
    os.makedirs(OUT, exist_ok=True)
    files = []
    # 1 station-year QC ----------------------------------------------------
    rows = [(c["station"], c["year"], c["status"],
             "Y" if c.get("sequence_suspect") else "N", c["months_present"])
            for c in sorted(store.w_checks, key=lambda c: (c["station"],
                                                           c["year"]))]
    files.append(_write_csv("qc_station_year.csv", ["station", "year",
                            "qc_category", "sequence_suspect",
                            "mean_months_present"], rows))
    # 2 reach month status -------------------------------------------------
    idx = {(o.station_uid, o.year, o.month, o.stat): o
           for o in store.discharge if o.station_uid in (UP, DOWN)}
    years = store.discharge_years
    st_rows = []
    for y in years:
        for m in range(1, 13):
            for s in (UP, DOWN):
                st_rows.append((y, m, s) + tuple(
                    status_of(idx.get((s, y, m, k))) for k in
                    ("mean", "max", "min")))
    files.append(_write_csv("reach_month_status.csv",
                            ["year", "month", "station", "mean_status",
                             "max_status", "min_status"], st_rows))
    # 3 continuous intervals (calendar-consecutive OBSERVED mean months) ---
    ivs = {}
    for s in (UP, DOWN):
        runs, cur = [], []
        for y in range(min(years), max(years) + 1):
            for m in range(1, 13):
                ok = status_of(idx.get((s, y, m, "mean"))) == "OBSERVED"
                if ok:
                    cur.append("%04d-%02d" % (y, m))
                elif cur:
                    runs.append(cur)
                    cur = []
        if cur:
            runs.append(cur)
        ivs[s] = [{"start": r[0], "end": r[-1], "months": len(r)}
                  for r in runs]
    files.append(_write_json("continuous_intervals.json", {
        "definition": "calendar-consecutive months whose monthly mean is "
                      "OBSERVED (not missing, not SEQUENCE_INDEX_SUSPECT); "
                      "discharge exists only for discrete years, gaps are "
                      "never interpolated", "discharge_years": years,
        "intervals": ivs}))
    # 4 availability masks + samples --------------------------------------
    y0, y1 = int(store.met_range[0][:4]), int(store.met_range[1][:4])
    met_ok = {}
    for y in range(y0, y1 + 1):
        for mm in store.met_monthly(y):
            met_ok[(y, mm["month"])] = bool(mm.get("complete"))
    circ = {(o.year, o.month) for o in store.rs
            if o.product == "CIRCLE" and o.value is not None}
    feat_avail = {
        "Q_up_monthly_mean": lambda y, m: status_of(
            idx.get((UP, y, m, "mean"))) == "OBSERVED",
        "P_monthly_sum": lambda y, m: met_ok.get((y, m), False),
        "T_daily": lambda y, m: met_ok.get((y, m), False),
        "circle_area_A_G": lambda y, m: (y, m) in circ,
    }
    samples, support = [], {b: [] for b in RB.BASELINES}
    for y in years:
        for m in range(1, 13):
            sid = "%s:%04d-%02d" % (DOWN, y, m)
            lab = status_of(idx.get((DOWN, y, m, "mean"))) == "OBSERVED"
            av = {f: fn(y, m) for f, fn in feat_avail.items()}
            elig = {}
            for b, spec in RB.BASELINES.items():
                e = lab and all(av[f] for f in spec["features"])
                elig[b] = e
                if e:
                    support[b].append(sid)
            samples.append((sid, y, m, "Y" if lab else "N") + tuple(
                "Y" if av[f] else "N" for f in feat_avail) + tuple(
                "Y" if elig[b] else "N" for b in RB.BASELINES))
    files.append(_write_csv("samples.csv", ["sample_id", "year", "month",
                            "label_16039_observed"] +
                            ["avail_" + f for f in feat_avail] +
                            ["support_" + b for b in RB.BASELINES], samples))
    files.append(_write_json("common_support.json", {
        "definition": "a sample is in a baseline's common support iff the "
                      "16039 label and every input feature are available "
                      "for that month (availability only; no value used)",
        "baselines": {b: {"features": RB.BASELINES[b]["features"],
                          "n_samples": len(v), "sample_ids": v}
                      for b, v in support.items()},
        "n_candidate_months": len(samples)}))
    # 5 target-Q blocks -----------------------------------------------------
    blocks = []
    for f in RB.feature_table():
        if f["target_q_derived"]:
            blocks.append({"feature": f["feature"],
                           "chains": f["transform_chains"],
                           RB.ZERO_TARGET_Q: "FORBIDDEN_ANY_ROLE_EXCEPT_FINAL_SCORING",
                           RB.CROSS_SYSTEM: "FORBIDDEN_AS_INFERENCE_INPUT",
                           RB.MISSING_RECONSTRUCTION:
                               "ALLOWED_ONLY_WITH_TEMPORAL_SPLIT"})
    files.append(_write_json("target_q_blocks.json", {
        "target": DOWN, "blocked_features": blocks}))
    # 6 task eligibility ----------------------------------------------------
    elig = {}
    for b, spec in RB.BASELINES.items():
        elig[b] = {}
        for t in RB.TASKS:
            kw = {"train_dataset": "LAMAHCE"} if t == RB.CROSS_SYSTEM else {}
            r = RB.check_leakage(spec["features"], spec["target"], t, **kw)
            elig[b][t] = {"lineage_ok": r.ok,
                          "violations": [v["rule"] for v in r.violations],
                          "warnings": [w["rule"] for w in r.warnings],
                          "status": "LINEAGE_CHECK_ONLY_NOT_EXECUTED"}
    files.append(_write_json("task_eligibility.json", {
        "note": "目录谱系检查通过 ≠ 已执行实验；未训练、未评分、未推理任何模型",
        "independence_note": RB.FD.NOT_CERTIFIED_NOTE if hasattr(RB, "FD")
        else None, "model_execution": RB.MODEL_EXECUTION, "baselines": elig}))
    # self-check: CSV outputs contain no observed numeric value -----------
    bad = []
    for p in files:
        if p.endswith(".csv"):
            with open(p, encoding="utf-8", newline="") as f:
                for r in csv.reader(f):
                    bad += [c for c in r if not SAFE_CELL.match(c) or
                            re.search(r"\d\.\d", c)]
    man = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "snapshot": store.snapshot.info()["snapshot_id"],
           "manifest_sha256": store.snapshot.manifest_sha256,
           "contains_observed_values": False,
           "self_check_no_decimal_values_in_csv": not bad,
           "files": [{"file": os.path.basename(p), "sha256": hashlib.sha256(
               open(p, "rb").read()).hexdigest(), "bytes": os.path.getsize(p)}
               for p in files]}
    _write_json("manifest.json", man)
    return man, support, bad


def main():
    s = SA.SyrDaryaStore(None, pinned_manifest=os.path.join(
        APP, "manifest", "source_manifest.json"),
        expected_manifest_sha256=SA.PINNED_MANIFEST_SHA256)
    if s.status != "OK":
        print("refused:", s.status)
        return 2
    man, support, bad = build(s)
    print("research_ready: %d files, snapshot %s, support %s, self-check %s"
          % (len(man["files"]), man["snapshot"],
             {b: len(v) for b, v in support.items()},
             "OK" if not bad else "FAIL"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
