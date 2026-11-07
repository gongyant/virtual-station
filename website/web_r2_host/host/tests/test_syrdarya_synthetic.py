"""
tests/test_syrdarya_synthetic.py -- pure synthetic tests for the Syr Darya
adapter and the research leakage guard. Writes six tiny CSVs to a temp dir
inside W/tmp (v0.5.1: never %TEMP%); never touches the teacher's files.
v0.5.1: the adapter fails closed, so every store is built with a complete
pinned manifest of the synthetic files.
"""
import calendar
import json
import os
import hashlib
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)

import syrdarya_adapter as SA  # noqa: E402
from research import baselines as RB  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print("  %-66s %s %s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else detail))


def pin(d, override=None, name="pin.json", drop=None, extra=None):
    """Write a complete pinned manifest for the synthetic files in d."""
    files = []
    for fn in SA.FILES.values():
        if fn == drop:
            continue
        p = os.path.join(d, fn)
        raw = open(p, "rb").read() if os.path.isfile(p) else b""
        files.append({"file": fn, "bytes": len(raw), "sha256": (
            override or {}).get(fn, hashlib.sha256(raw).hexdigest())})
    if extra:
        files.append({"file": extra, "bytes": 0, "sha256": "0" * 64})
    mp = os.path.join(d, name)
    with open(mp, "w", encoding="utf-8") as f:
        json.dump({"files": files}, f)
    return mp


def w_from(q, year):
    return sum(q * calendar.monthrange(year, m)[1] * 86400 for m in
               range(1, 13)) / 1e6


def build(d):
    hdr = (["年份", "站码", "站名", "年径流W_百万m3"] +
           ["%d月平均" % m for m in range(1, 13)] +
           ["%d月最大" % m for m in range(1, 13)] +
           ["%d月最小" % m for m in range(1, 13)] + ["校验"])
    w = w_from(100.0, 2003)

    def row(code, W, mins):
        return ([2003, code, "S" + code, W] + [100.0] * 12 + [150.0] * 12 +
                mins + ["OK"])
    rows = [row("16037", w, [50.0] * 12),
            row("16039", w / 1000.0, [50.0] * 12),        # unit-scale case
            row("99001", w * 1.30, [float(m) for m in range(1, 13)])]
    with open(os.path.join(d, SA.FILES["discharge"]), "w", encoding="utf-8-sig",
              newline="") as f:
        f.write(",".join(hdr) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")
    up, down = w / 1000.0, w / 1000.0 * 0.9
    dW, P_mm, ET_mm, area = up - down, 100.0, 150.0, 1608.0
    P_vol, ET_vol, Wi = P_mm * area / 1e6, ET_mm * area / 1e6, 0.2
    R = dW - P_vol + ET_vol - Wi
    with open(os.path.join(d, SA.FILES["water_balance"]), "w",
              encoding="utf-8-sig", newline="") as f:
        f.write("year,半宽km,面积km2,W上,W下,dW,P_mm,ET_mm,P_vol,ET_vol,W引水,残余\n")
        f.write(",".join(str(x) for x in [2003, 3, area, up, down, dW, P_mm,
                                          ET_mm, P_vol, ET_vol, Wi, R]) + "\n")
    with open(os.path.join(d, SA.FILES["intakes"]), "w", encoding="utf-8-sig",
              newline="") as f:
        f.write("year,dW,P_vol,ET_vol,残余,W_a60,W_a75,W_a90,W_km3,source,"
                "confidence\n")
        f.write("2003,%s,%s,%s,%s,0.1,0.2,0.3,0.2,synthetic,低\n"
                % (dW, P_vol, ET_vol, R))
    with open(os.path.join(d, SA.FILES["circles"]), "w", encoding="utf-8-sig",
              newline="") as f:
        f.write("year,month,area_A_km2,area_B_km2,area_C_km2,area_D_km2,"
                "area_E_km2,area_F_km2,area_G_km2,n_A,n_B,n_C,n_D,n_E,n_F,n_G\n")
        f.write("2003,7,,0.0,0.5,,,,,,1.0,2.0,,,,\n")
    with open(os.path.join(d, SA.FILES["kzdam"]), "w", encoding="utf-8-sig",
              newline="") as f:
        f.write("ym,KC,KD,KS,KU,n_scene\n2003-07,10,,30,40,4\n")
    with open(os.path.join(d, SA.FILES["meteorology"]), "w", encoding="utf-8",
              newline="") as f:
        f.write("date,p,t,year\n")
        for m in range(1, 13):
            for dd in range(1, calendar.monthrange(2003, m)[1] + 1):
                if (m, dd) == (3, 15):
                    continue                              # one missing day
                f.write("2003-%02d-%02d,1.0,%s,2003\n" % (m, dd, float(m)))


def main():
    tmp = os.path.join(APP, "tmp")
    os.makedirs(tmp, exist_ok=True)
    d = tempfile.mkdtemp(prefix="syr_synth_", dir=tmp)
    try:
        build(d)
        good = pin(d, name="pin_good.json")
        s = SA.SyrDaryaStore(d, pinned_manifest=good)
        check("S01 store loads synthetic files", s.status == "OK", s.status)
        check("S02 ids are namespaced", "SYRDARYA:16037" in
              [st.uid for st in s.stations.values()])
        try:
            SA.parse_uid("LAMAHCE:58")
            ok = False
        except ValueError as e:
            ok = "NAMESPACE_MISMATCH" in str(e)
        check("S03 LAMAHCE:58 rejected (no cross-dataset match)", ok)
        wc = {c["station"]: c for c in s.w_checks}
        check("S04 W from monthly Q consistent -> CONSISTENT",
              wc["SYRDARYA:16037"]["status"] == "CONSISTENT")
        check("S05 W 1000x too small -> W_UNIT_SCALE_SUSPECT",
              wc["SYRDARYA:16039"]["status"] == "W_UNIT_SCALE_SUSPECT")
        check("S06 W +30% -> W_INCONSISTENT, source NOT overwritten",
              wc["SYRDARYA:99001"]["status"] == "W_INCONSISTENT" and
              abs(s.annual_w[("99001", 2003)][0] - w_from(100, 2003) * 1.3)
              < 1e-6)
        mins = [o for o in s.discharge if o.station_uid == "SYRDARYA:99001"
                and o.stat == "min"]
        check("S07 min==month 1..12 flagged SEQUENCE_INDEX_SUSPECT",
              all("SEQUENCE_INDEX_SUSPECT" in o.flags for o in mins))
        check("S08 discharge unit UNKNOWN (no header unit)",
              all(o.unit == "UNKNOWN" for o in s.discharge))
        mm = s.met_monthly(2003)
        check("S09 Feb aggregated over 28 days", mm[1]["days_in_month"] == 28
              and mm[1]["P_sum"] == 28.0)
        check("S10 Jan aggregated over 31 days", mm[0]["P_sum"] == 31.0)
        check("S11 month with a missing day -> no monthly value",
              mm[2]["complete"] is False and mm[2]["P_sum"] is None)
        check("S12 missing met day detected", len(s.met_missing_days) == 1)
        c = {o.site: o for o in s.rs if o.product == "CIRCLE"}
        check("S13 empty circle cell -> NO_OBSERVATION (not 0)",
              c["A"].value is None and c["A"].value_status == "NO_OBSERVATION")
        check("S14 real 0 -> ZERO", c["B"].value == 0 and
              c["B"].value_status == "ZERO")
        check("S15 circle area unit km2 from header", c["C"].unit == "km2")
        kz = [o for o in s.rs if o.product == "KZDAM"]
        check("S16 KZDAM unit UNKNOWN, never km2",
              all(o.unit == "UNKNOWN" for o in kz))
        check("S17 KZDAM empty KD -> NO_OBSERVATION",
              [o for o in kz if o.site == "KD"][0].value_status ==
              "NO_OBSERVATION")
        check("S18 intakes are Q-derived scenarios, not measurements",
              all(i.q_derived and not i.is_measurement for i in s.intakes))
        wb = s.wb_checks[0]
        check("S19 dW / P_vol / ET_vol recomputed and consistent",
              wb["dW_ok"] and wb["P_vol_ok"] and wb["ET_vol_ok"])
        check("S20 residual sign convention detected",
              wb["residual_matches_file_convention"])
        check("S21 discrete years recorded, no interpolation",
              s.discharge_years == [2003])
        # pinned manifest mismatch
        mp = pin(d, override={SA.FILES["kzdam"]: "0" * 64}, name="pin_bad.json")
        s2 = SA.SyrDaryaStore(d, pinned_manifest=mp)
        check("S22 complete pin, wrong kzdam hash -> SOURCE_CHANGED, no data",
              s2.status == "SOURCE_CHANGED" and not s2.discharge and
              not s2.rs)
        inc = os.path.join(d, "pin_incomplete.json")
        with open(inc, "w", encoding="utf-8") as f:
            json.dump({"files": [{"file": SA.FILES["kzdam"],
                                  "sha256": "0" * 64}]}, f)
        s3 = SA.SyrDaryaStore(d, pinned_manifest=inc)
        check("S22b incomplete pin (v0.5 style) -> MANIFEST_INVALID refusal",
              s3.status == "MANIFEST_INVALID" and not s3.discharge)
        s4 = SA.SyrDaryaStore(d)
        check("S22c no pinned manifest -> MANIFEST_MISSING (fail closed)",
              s4.status == "MANIFEST_MISSING" and not s4.discharge)
        s5 = SA.SyrDaryaStore(d, pinned_manifest=good,
                              expected_manifest_sha256="0" * 64)
        check("S22d manifest itself not the frozen one -> MANIFEST_INVALID",
              s5.status == "MANIFEST_INVALID")
        os.remove(os.path.join(d, SA.FILES["kzdam"]))
        s6 = SA.SyrDaryaStore(d, pinned_manifest=good)
        check("S23 missing source file -> SOURCE_MISSING",
              s6.status == "SOURCE_MISSING" and not s6.discharge)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    # ---- leakage guard ------------------------------------------------
    T = "SYRDARYA:16039"
    r = RB.check_leakage(["dW_reach"], T, RB.ZERO_TARGET_Q)
    check("L01 dW forbidden in zero-target-Q task", not r.ok)
    r = RB.check_leakage(["intake_alpha", "wb_residual"], T, RB.ZERO_TARGET_Q)
    check("L02 intake / residual forbidden in zero-target-Q",
          not r.ok and len(r.violations) == 2)
    r = RB.check_leakage(["Q_up_monthly_mean", "P_monthly_sum"], T,
                         RB.ZERO_TARGET_Q)
    check("L03 upstream Q + met allowed in zero-target-Q", r.ok)
    r = RB.check_leakage(["Q_down_monthly_mean"], T,
                         RB.MISSING_RECONSTRUCTION)
    check("L04 target Q in reconstruction -> temporal-split warning",
          r.ok and r.warnings[0]["rule"] == "REQUIRES_TEMPORAL_SPLIT")
    r = RB.check_leakage(["Q_up_monthly_mean"], T, RB.CROSS_SYSTEM,
                         train_dataset="SYRDARYA")
    check("L05 cross-system trained on apply system -> violation", not r.ok)
    r = RB.check_leakage(["Q_up_monthly_mean"], T, RB.CROSS_SYSTEM,
                         train_dataset="LAMAHCE")
    check("L06 cross-system trained on LAMAHCE -> ok", r.ok)
    r = RB.check_leakage(["mystery_feature"], T, RB.ZERO_TARGET_Q)
    check("L07 unknown feature lineage -> violation", not r.ok)
    for name, b in RB.BASELINES.items():
        r = RB.check_leakage(b["features"], b["target"], RB.ZERO_TARGET_Q)
        check("L08 %s passes zero-target-Q leakage guard" % name, r.ok)
    check("L09 KZDAM excluded from SYR-B2 (unit unknown)",
          "kzdam_KC_KU" not in RB.BASELINES["SYR-B2"]["features"])
    out = RB.run_baseline("SYR-B2")
    check("L10 run_baseline never predicts", out["prediction"] is None and
          out["status"] == "NOT_AUTHORIZED")

    n = len(RESULTS)
    p = sum(1 for _, ok in RESULTS if ok)
    print("\n%d/%d synthetic Syr Darya / leakage tests passed" % (p, n))
    with open(os.path.join(APP, "logs", "test_syrdarya_synthetic.json"), "w",
              encoding="utf-8") as f:
        json.dump({"passed": p, "total": n,
                   "tests": [{"test": a, "passed": b} for a, b in RESULTS]},
                  f, ensure_ascii=False, indent=1)
    return 0 if p == n else 1


if __name__ == "__main__":
    raise SystemExit(main())
