"""
Child process: reproduce the v0.5 static path check on a SYNTHETIC static dir.

Loads v0.5 server.py read-only (no bytecode, any write into the v0.5 tree is
refused by an open() guard), points its STATIC at the synthetic fixture and
calls Handler._serve_static with a fake request object, so neither port 8773
nor v0.5/logs/access.log is touched.
argv: <v05_dir> <static_dir> <probes.json>  -> prints JSON results.
"""
import builtins
import importlib.util
import json
import os
import sys

sys.dont_write_bytecode = True
V05, STATIC, PROBES = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path = [V05] + [p for p in sys.path if os.path.abspath(p or ".") !=
                    os.path.dirname(os.path.abspath(__file__))]
V05N = os.path.normcase(os.path.realpath(V05))
_open = builtins.open
WRITE_ATTEMPTS = []


def guarded_open(file, mode="r", *a, **kw):
    try:
        p = os.path.normcase(os.path.realpath(os.fspath(file)))
    except TypeError:
        p = ""
    if p.startswith(V05N) and any(c in mode for c in "wax+"):
        WRITE_ATTEMPTS.append(p)
        raise PermissionError("v0.5 tree is read-only in this probe")
    return _open(file, mode, *a, **kw)


builtins.open = guarded_open
_mk = os.makedirs
os.makedirs = lambda p, *a, **k: None if os.path.isdir(p) else \
    WRITE_ATTEMPTS.append(p)
spec = importlib.util.spec_from_file_location("v05_server",
                                              os.path.join(V05, "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
os.makedirs = _mk
mod.STATIC = STATIC
mod.log_access = lambda *a, **k: None


class Fake:
    def __init__(self):
        self.status, self.body = None, b""

    def _err(self, status, code, message, **kw):
        self.status, self.body = status, code.encode()

    def _json(self, status, obj):
        self.status, self.body = status, json.dumps(obj).encode()

    def _send(self, status, body, ctype="", extra=None):
        self.status = status
        self.body = body if isinstance(body, bytes) else str(body).encode()


out = []
with _open(PROBES, encoding="utf-8") as f:
    probes = json.load(f)
for rel in probes:
    fk = Fake()
    try:
        st = mod.Handler._serve_static(fk, rel)
    except Exception as exc:                    # noqa: BLE001
        st, fk.body = "EXC:" + type(exc).__name__, b""
    out.append({"rel": rel, "status": st,
                "canary": b"CANARY_" in fk.body})
print(json.dumps({"results": out, "v05_write_attempts": WRITE_ATTEMPTS}))
