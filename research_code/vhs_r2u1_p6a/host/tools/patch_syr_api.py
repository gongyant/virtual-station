"""Apply the v0.5.1 changes to W/syr_api.py (exact-match patches)."""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(W, "syr_api.py")
NL = "\r\n" if b"\r\n" in open(P, "rb").read() else "\n"
s = open(P, encoding="utf-8").read()
if "ScienceViews" in s:
    sys.exit("already patched")


def rep(old, new, count=1):
    global s
    n = s.count(old)
    if n != count:
        sys.exit("patch failed (%d matches): %r" % (n, old[:80]))
    s = s.replace(old, new)


rep('''is no bulk-export route for the teacher's CSVs.
"""

from dataclasses import asdict

import syrdarya_adapter as SA
from research import baselines as RB
''', '''is no bulk-export route for the teacher's CSVs.

v0.5.1: every response carries the immutable snapshot id / load time;
new routes provenance, provenance-recheck (hash comparison only) and
science (QC closure, run vs cell counts, dual denominators, balance-W
formula, alpha residuals, units, target-Q labels). Data export, future model
input and prediction remain NOT_AUTHORIZED (http_policy.PERMISSIONS).
"""

from dataclasses import asdict

import http_policy
import syrdarya_adapter as SA
from research import baselines as RB
from science_views import ScienceViews, TARGET_Q_NOTICE, dual_pct
''')
rep('''    def __init__(self, store, lamah_store=None):
        self.s = store
        self.lamah = lamah_store
''', '''    def __init__(self, store, lamah_store=None):
        self.s = store
        self.lamah = lamah_store
        self.sci = ScienceViews(store)
''')
rep('''                               for p in prov]}
        base.update(body)
        return 200, base
''', '''                               for p in prov]}
        snap = self.s.snapshot
        base["snapshot"] = {
            "snapshot_id": snap.snapshot_id if snap else None,
            "loaded_at": snap.loaded_at if snap else None,
            "source_status": "VERIFIED_AT_LOAD" if snap else self.s.status,
            "policy": snap.policy if snap else None}
        base.update(body)
        return 200, base
''')
rep('''                         "reason": "historical observation display is not a "
                                   "model-input authorisation"}
        if self.s.status != "OK":
            raise ApiError(503, self.s.status,
                           "source files missing or changed; refusing to "
                           "serve values", files=[
                               {k: v for k, v in r.items() if k != "path"}
                               for r in self.s.files.values()])
''', '''                         "reason": "historical observation display is not a "
                                   "model-input authorisation",
                         "permissions": {k: v["status"] for k, v in
                                         http_policy.PERMISSIONS.items()}}
        if self.s.status != "OK":
            raise ApiError(503, self.s.status,
                           "source files missing or changed, or pinned "
                           "manifest invalid; refusing to serve values",
                           files=[{k: v for k, v in r.items() if k != "path"}
                                  for r in self.s.files.values()],
                           refusal=self.s.refusal)
''')
rep('''                  "availability": self.availability, "gis": self.gis}
''', '''                  "availability": self.availability, "gis": self.gis,
                  "provenance": self.provenance,
                  "provenance-recheck": self.provenance_recheck,
                  "science": self.science}
''')
rep('''        if view == "annual":
            rows = [c for c in self.s.w_checks if c["station"] == SA.uid(code)]
            return self.env(["discharge"], station=SA.uid(code),
                            view="annual", years=rows,
                            unit_W="10^6 m3 (source header)",
                            W_from_Q_note="Σ Q_month·days·86400/1e6 under the "
                                          "hypothesis Q is m3/s",
                            tolerance=SA.W_REL_TOL)
''', '''        if view == "annual":
            rows = []
            for c in self.s.w_checks:
                if c["station"] != SA.uid(code):
                    continue
                r = dict(c)
                r["dual_pct"] = dual_pct(c.get("W_from_Q"), c.get("W_source"))
                r["source_value_overwritten"] = False
                rows.append(r)
            return self.env(["discharge"], station=SA.uid(code),
                            view="annual", years=rows,
                            unit_W="10^6 m3 (source header)",
                            W_from_Q_note="Σ Q_month·days·86400/1e6 under the "
                                          "hypothesis Q is m3/s",
                            rel_diff_definition="rel_diff = (W_Q − W_源)/W_源"
                                                "（分母为源 W）",
                            tolerance=SA.W_REL_TOL,
                            target_q_notice="W_from_Q 由该站 Q 派生；该站作目标站时"
                                            + TARGET_Q_NOTICE)
''')
rep('''                        unit="UNKNOWN", unit_status="UNKNOWN_IN_SOURCE_HEADER;"
                        " annual-volume cross-check supports m3/s",
''', '''                        unit="UNKNOWN", unit_status="UNKNOWN_IN_SOURCE_HEADER;"
                        " annual-volume cross-check supports m3/s",
                        statistics_basis={
                            "mean": "源表“N月平均”原值", "max": "源表“N月最大”原值",
                            "min": "源表“N月最小”原值",
                            "suspect": "连续≥3月等于月序号→SUSPECT，保留原值，不绘制"},
''')
rep('''                        selected_scenario=sel[0] if sel else None,
                        disclaimer="引水量为由 16037/16039 上下游 Q 反演的低置信度"
                                   "情景，不是实测取水量；残余按源文件公式 "
                                   "dW − P_vol + ET_vol − W引水 给出，与标准水量"
                                   "平衡符号相反，待老师确认。",
''', '''                        selected_scenario=sel[0] if sel else None,
                        residuals=self.sci.alpha_view(year, width, alpha),
                        balance_w_formula=self.sci.build()[
                            "water_balance_w_formula"]["formula_in_use"],
                        disclaimer="引水量为由 16037/16039 上下游 Q 反演的低置信度"
                                   "情景，不是实测取水量；源残余按源文件公式 "
                                   "dW − P_vol + ET_vol − W引水 给出（对应源文件"
                                   "取水），与所选 α 情景残余分列；源文件未给出控制体"
                                   "定义，不判定其符号对错，待老师确认。",
                        target_q_notice=TARGET_Q_NOTICE,
''')
rep('''                        permissions={"display": "LOCAL_READ_ONLY",
                                     "bulk_export": "DISABLED",
                                     "model_execution": RB.MODEL_EXECUTION,
                                     "prediction": None})
''', '''                        flags_offset=offset, flags_limit=limit,
                        permissions={"display": "LOCAL_READ_ONLY",
                                     "bulk_export": "DISABLED",
                                     "model_execution": RB.MODEL_EXECUTION,
                                     "prediction": None,
                                     "domains": {k: v["status"] for k, v in
                                                 http_policy.PERMISSIONS
                                                 .items()}})
''')
rep('''    def research(self, qs):
        return self.env(list(SA.FILES), **RB.summary())
''', '''    def research(self, qs):
        return self.env(list(SA.FILES), **RB.summary())

    def provenance(self, qs):
        return self.env(list(SA.FILES), **self.s.snapshot.info())

    def provenance_recheck(self, qs):
        return self.env(list(SA.FILES), recheck=self.s.snapshot.recheck(),
                        semantics=self.s.snapshot.info()["semantics"])

    def science(self, qs):
        return self.env(list(SA.FILES), **self.sci.build())
''')
open(P, "w", encoding="utf-8", newline=NL).write(s)
print("patched", P)
