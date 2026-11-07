"""tests/test_research_ready.py -- validates research/prepare_baseline.py output
(real data on the user's PC; outputs contain ids / counts / flags only)."""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import syrdarya_adapter as SA  # noqa: E402
from research import prepare_baseline as PB  # noqa: E402
from research import baselines as RB  # noqa: E402

T = Suite("test_research_ready")


def main():
    s = SA.SyrDaryaStore(None, pinned_manifest=os.path.join(
        APP, "manifest", "source_manifest.json"),
        expected_manifest_sha256=SA.PINNED_MANIFEST_SHA256)
    T.check("RR01", "real store loads under frozen pin", s.status == "OK",
            s.status)
    man, support, bad = PB.build(s)
    T.check("RR02", "self-check: no decimal value in any CSV output",
            not bad and man["self_check_no_decimal_values_in_csv"], bad[:5])
    names = {f["file"] for f in man["files"]}
    T.check("RR03", "all 7 outputs + manifest written", names == {
        "qc_station_year.csv", "reach_month_status.csv",
        "continuous_intervals.json", "samples.csv", "common_support.json",
        "target_q_blocks.json", "task_eligibility.json"} and os.path.isfile(
            os.path.join(PB.OUT, "manifest.json")), names)
    with open(os.path.join(PB.OUT, "qc_station_year.csv"),
              encoding="utf-8") as f:
        qc = list(csv.DictReader(f))
    T.check("RR04", "qc_station_year has 366 rows, categories as review",
            len(qc) == 366 and sum(r["qc_category"] == "CONSISTENT"
                                   for r in qc) == 259)
    with open(os.path.join(PB.OUT, "reach_month_status.csv"),
              encoding="utf-8") as f:
        rm = list(csv.DictReader(f))
    T.check("RR05", "reach_month_status = years x 12 x 2 stations",
            len(rm) == len(s.discharge_years) * 24)
    with open(os.path.join(PB.OUT, "common_support.json"),
              encoding="utf-8") as f:
        cs = json.load(f)["baselines"]
    T.check("RR06", "common support nested: B2 subset-of B1 subset-of B0",
            set(cs["SYR-B2"]["sample_ids"]) <= set(cs["SYR-B1"]["sample_ids"])
            <= set(cs["SYR-B0"]["sample_ids"]),
            {k: v["n_samples"] for k, v in cs.items()})
    with open(os.path.join(PB.OUT, "task_eligibility.json"),
              encoding="utf-8") as f:
        te = json.load(f)
    T.check("RR07", "B0-B2 lineage-ok for zero-target-Q; status "
            "NOT_EXECUTED", all(te["baselines"][b][RB.ZERO_TARGET_Q]
                                ["lineage_ok"] for b in RB.BASELINES) and
            all(v["status"] == "LINEAGE_CHECK_ONLY_NOT_EXECUTED"
                for b in te["baselines"].values() for v in b.values()))
    with open(os.path.join(PB.OUT, "target_q_blocks.json"),
              encoding="utf-8") as f:
        tb = {x["feature"] for x in json.load(f)["blocked_features"]}
    T.check("RR08", "target-Q blocks include dW / intake / residual",
            {"dW_reach", "intake_alpha", "wb_residual"} <= tb, tb)
    raw = ""
    for n in names:
        with open(os.path.join(PB.OUT, n), encoding="utf-8") as f:
            raw += f.read()
    T.check("RR09", "no float literal anywhere in outputs (ids/counts only)",
            not re.search(r"(?<![\w-])-?\d+\.\d{2,}", raw))
    T.check("RR10", "manifest records snapshot id",
            man["snapshot"] == s.snapshot.snapshot_id)
    return T.save()


if __name__ == "__main__":
    raise SystemExit(main())
