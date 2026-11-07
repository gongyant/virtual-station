"""
Child process: answer a list of GET paths with the UNMODIFIED v0.5 code,
in-process (no HTTP, port 8773 untouched, v0.5 access.log untouched).
Every write attempt is refused unless it targets <W>/tmp.
argv: <v05_dir> <W> <paths.json> <out.json>
"""
import builtins
import importlib.util
import json
import os
import sys
from urllib.parse import parse_qs, urlparse

sys.dont_write_bytecode = True
V05, W, PATHS, OUT = sys.argv[1:5]
TMP = os.path.normcase(os.path.realpath(os.path.join(W, "tmp")))
sys.path = [V05] + [p for p in sys.path if os.path.abspath(p or ".") !=
                    os.path.dirname(os.path.abspath(__file__))]
_open = builtins.open
REFUSED = []


def guarded_open(file, mode="r", *a, **kw):
    if any(c in mode for c in "wax+"):
        try:
            p = os.path.normcase(os.path.realpath(os.fspath(file)))
        except TypeError:
            p = ""
        if not p.startswith(TMP + os.sep):
            REFUSED.append(p)
            raise PermissionError("write refused in v0.5 query child")
    return _open(file, mode, *a, **kw)


builtins.open = guarded_open
_mk = os.makedirs
os.makedirs = lambda p, *a, **k: None if os.path.isdir(p) else \
    REFUSED.append(p)
spec = importlib.util.spec_from_file_location("v05_server",
                                              os.path.join(V05, "server.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
os.makedirs = _mk
mod.log_access = lambda *a, **k: None
mod.STORE = mod.VHSStore(mod.SANDBOX)
mod.SYR = mod.syrdarya_adapter.SyrDaryaStore(None,
                                             pinned_manifest=mod.SYR_MANIFEST)
mod.SYR_API = mod.SyrApi(mod.SYR, mod.STORE)


class Cap:
    pass


def run(path):
    fk = mod.Handler.__new__(mod.Handler)
    cap = Cap()
    cap.status, cap.body = None, None

    def _json(status, obj):
        cap.status, cap.body = status, json.loads(json.dumps(obj))

    def _send(status, body, ctype="", extra=None):
        cap.status = status
        if isinstance(body, (dict, list)):
            cap.body = json.loads(json.dumps(body))
        else:
            b = body.encode() if isinstance(body, str) else body
            cap.body = {"__bytes_len__": len(b)}
    fk._json, fk._send = _json, _send
    fk.command, fk.headers = "GET", {}
    p = urlparse(path)
    try:
        mod.Handler._dispatch(fk, p.path, parse_qs(p.query))
    except Exception as exc:                    # noqa: BLE001
        cap.status, cap.body = "EXC", type(exc).__name__
    return {"status": cap.status, "body": cap.body}


with _open(PATHS, encoding="utf-8") as f:
    paths = json.load(f)
res = {p: run(p) for p in paths}
with _open(OUT, "w", encoding="utf-8") as f:
    json.dump({"results": res, "refused_writes": REFUSED,
               "syr_status": mod.SYR.status}, f, ensure_ascii=False)
print(json.dumps({"n": len(res), "refused_writes": len(REFUSED)}))
