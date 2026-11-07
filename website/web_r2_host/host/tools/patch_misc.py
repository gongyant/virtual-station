"""Apply small v0.5.1 patches: vhs_core version and the inherited tests."""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class F:
    def __init__(self, rel):
        self.p = os.path.join(W, rel)
        assert os.path.commonpath([os.path.realpath(self.p), W]) == W
        raw = open(self.p, "rb").read()
        self.nl = "\r\n" if b"\r\n" in raw else "\n"
        self.s = raw.decode("utf-8").replace("\r\n", "\n")

    def rep(self, old, new, count=1):
        n = self.s.count(old)
        if n != count:
            sys.exit("%s: patch failed (%d matches): %r" % (self.p, n,
                                                           old[:70]))
        self.s = self.s.replace(old, new)

    def save(self):
        open(self.p, "w", encoding="utf-8", newline=self.nl).write(self.s)
        print("patched", os.path.relpath(self.p, W))


c = F("vhs_core.py")
c.rep('APP_VERSION = "0.5.0"\nBUILD_ID = "v0.5-20261022-syrdarya"',
      'APP_VERSION = "0.5.1"\nBUILD_ID = "v0.5.1-20261022-codex-fixes"')
c.save()

t = F(os.path.join("tests", "test_lamahce_regression.py"))
t.rep('"T02 health carries app_version 0.5.0"',
      '"T02 health carries app_version 0.5.1"')
t.rep('h.get("app_version") == "0.5.0", h.get("app_version")',
      'h.get("app_version") == "0.5.1", h.get("app_version")')
t.rep('"T11 meta: app_version 0.5.0 + regions list present"',
      '"T11 meta: app_version 0.5.1 + regions list present"')
t.rep('m.get("app_version") == "0.5.0" and',
      'm.get("app_version") == "0.5.1" and')
t.rep('"T70 health carries gis_mode + app_version 0.5.0"',
      '"T70 health carries gis_mode + app_version 0.5.1"')
t.rep('h2.get("app_version") == "0.5.0" and',
      'h2.get("app_version") == "0.5.1" and')
t.save()

a = F(os.path.join("tests", "test_syrdarya_api.py"))
a.rep('"H01 health app_version 0.5.0, both datasets OK"',
      '"H01 health app_version 0.5.1, both datasets OK"')
a.rep('h.get("app_version") == "0.5.0" and',
      'h.get("app_version") == "0.5.1" and')
a.save()

s = F(os.path.join("tests", "test_syrdarya_synthetic.py"))
s.rep('''adapter and the research leakage guard. Writes six tiny CSVs to a temp dir;
never touches the teacher's files.''', '''adapter and the research leakage guard. Writes six tiny CSVs to a temp dir
inside W/tmp (v0.5.1: never %TEMP%); never touches the teacher's files.
v0.5.1: the adapter fails closed, so every store is built with a complete
pinned manifest of the synthetic files.''')
s.rep('''import shutil
import sys
import tempfile
''', '''import hashlib
import shutil
import sys
import tempfile
''')
s.rep('''def w_from(q, year):''', '''def pin(d, override=None, name="pin.json", drop=None, extra=None):
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


def w_from(q, year):''')
s.rep('''    d = tempfile.mkdtemp(prefix="syr_synth_")
    try:
        build(d)
        s = SA.SyrDaryaStore(d)
''', '''    tmp = os.path.join(APP, "tmp")
    os.makedirs(tmp, exist_ok=True)
    d = tempfile.mkdtemp(prefix="syr_synth_", dir=tmp)
    try:
        build(d)
        good = pin(d, name="pin_good.json")
        s = SA.SyrDaryaStore(d, pinned_manifest=good)
''')
s.rep('''        mp = os.path.join(d, "pin.json")
        with open(mp, "w", encoding="utf-8") as f:
            json.dump({"files": [{"file": SA.FILES["kzdam"],
                                  "sha256": "0" * 64}]}, f)
        s2 = SA.SyrDaryaStore(d, pinned_manifest=mp)
        check("S22 changed source file -> SOURCE_CHANGED refusal",
              s2.status == "SOURCE_CHANGED")
        os.remove(os.path.join(d, SA.FILES["kzdam"]))
        check("S23 missing source file -> SOURCE_MISSING",
              SA.SyrDaryaStore(d).status == "SOURCE_MISSING")
''', '''        mp = pin(d, override={SA.FILES["kzdam"]: "0" * 64}, name="pin_bad.json")
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
''')
s.save()
