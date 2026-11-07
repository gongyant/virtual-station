"""
server.py  --  VHS v0.5.1 interactive workbench HTTP service (stdlib only)

Start:
    python server.py --port 8774

Endpoints
---------
GET  /                                        three-panel workbench UI
GET  /static/<file>                           UI assets (strict whitelist)
GET  /api/vhs/health                          liveness + app/build/dataset version
GET  /api/vhs/permissions                     permission domains (v0.5.1)
GET  /api/vhs/meta                            counts + authorization + regions
GET  /api/vhs/stations?q=&limit=&region=&targets_only=
GET  /api/vhs/stations/{id}
GET  /api/vhs/stations/{id}/network?depth=
GET  /api/vhs/stations/{id}/audit
GET  /api/vhs/stations/{id}/candidates
GET  /api/vhs/stations/{id}/served-targets
GET  /api/vhs/stations/{id}/utw?w=           U-T-W linkage
GET  /api/vhs/map                             projected station positions
GET  /api/vhs/export?what=&format=            LamaH-CE open station metadata only
GET  /api/vhs/model-status                     prediction gate info (no run)
GET|POST /api/vhs/predict                      always 403 NOT_AUTHORIZED
GET  /api/vhs/datasets/...                     dataset routes (syr_api.py)

v0.5.1 security (Codex P0-01 / P1-06): static files are resolved through
static_guard.StaticGuard (grammar + realpath/commonpath + whitelist); Host
and Origin are checked on every request (http_policy); CORS never answers
'*'; loopback binding only.

No network access, no model execution.
"""

import argparse
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import p89_evidence  # noqa: E402

from vhs_core import VHSStore, APP_VERSION, BUILD_ID  # noqa: E402
import syrdarya_adapter  # noqa: E402
from syr_api import SyrApi  # noqa: E402
import http_policy  # noqa: E402
from static_guard import StaticGuard, StaticRefused  # noqa: E402
import platform_v06  # noqa: E402
from r2_public import R2HostGateway

SANDBOX = os.environ.get(
    "VHS_SANDBOX", os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
STATIC = os.path.join(HERE, "static")
LOGDIR = os.path.join(HERE, "logs")
os.makedirs(LOGDIR, exist_ok=True)
SYR_MANIFEST = os.path.join(HERE, "manifest", "source_manifest.json")

STORE = None
SYR = None
SYR_API = None
GUARD = None
PLAT = None
PORT = None
R2_PUBLIC = None
R2_CANDIDATE = False
ACCESS_LOG = os.path.join(LOGDIR, "access.log")

ROUTE_STATION = re.compile(r"^/api/vhs/stations/(\d+)(?:/([a-z\-]+))?$")


class BadParam(Exception):
    pass


def _qint(qs, name, default, lo, hi):
    """Integer query parameter; malformed -> 400 instead of 500 (P2)."""
    raw = (qs.get(name) or [None])[0]
    if raw is None or raw == "":
        return default
    try:
        v = int(raw)
    except ValueError:
        raise BadParam("'%s' must be an integer" % name)
    return max(lo, min(v, hi))


def log_access(method, path, status, ms, note=""):
    line = "%s\t%s\t%s\t%d\t%.1fms\t%s\n" % (
        time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
        method, path[:300], status, ms, note)
    with open(ACCESS_LOG, "a", encoding="utf-8") as f:
        f.write(line)


class Handler(BaseHTTPRequestHandler):
    server_version = "VHS/%s" % APP_VERSION
    protocol_version = "HTTP/1.1"

    def _port(self):
        return PORT or self.server.server_address[1]

    def _send(self, status, body, ctype="application/json; charset=utf-8",
              extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, indent=1)
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in http_policy.cors_headers(self.headers,
                                             self._port()).items():
            self.send_header(k, v)
        for k, v in http_policy.SECURITY_HEADERS.items():
            self.send_header(k, v)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, obj):
        self._send(status, obj)

    def _err(self, status, code, message, **kw):
        payload = {"error": code, "message": message, "status": status,
                   "prediction": None}
        payload.update(kw)
        self._json(status, payload)

    def log_message(self, fmt, *args):
        pass

    def _gate(self, method, path):
        """Host / Origin / Sec-Fetch policy. Returns status if refused."""
        bad = http_policy.check_request(method, path, self.headers,
                                        self._port())
        if bad:
            st, code, msg = bad
            self._err(st, code, msg)
            return st
        return None

    def do_OPTIONS(self):
        t0 = time.time()
        st = self._gate("OPTIONS", urlparse(self.path).path)
        if st is None:
            st = 204
            self.send_response(204)
            for k, v in http_policy.cors_headers(self.headers,
                                                 self._port()).items():
                self.send_header(k, v)
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", "0")
            self.end_headers()
        log_access("OPTIONS", self.path, st, (time.time() - t0) * 1000)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        t0 = time.time()
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)
        try:
            status = self._gate("GET", path)
            if status is None:
                status = self._dispatch(path, qs)
        except BrokenPipeError:
            return
        except BadParam as exc:
            status = 400
            self._err(400, "BAD_PARAM", str(exc))
        except Exception as exc:                     # noqa: BLE001
            status = 500
            self._err(500, "INTERNAL", type(exc).__name__)
        log_access("GET", self.path, status, (time.time() - t0) * 1000)

    def do_POST(self):
        t0 = time.time()
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = b""
        if 0 < length <= 1 << 20:
            body = self.rfile.read(length)
        p = parsed.path.rstrip("/")
        status = self._gate("POST", p)
        if status is not None:
            pass
        elif p.startswith(("/api/v6/candidate-public/","/api/v6/public/","/api/v6/candidate-kaz/","/api/v6/public-kaz/")):
            self._json(403, {"status":"MODEL_EXECUTION_NOT_AUTHORIZED","prediction":None})
            status = 403
        elif p.startswith("/api/v6/"):
            st, obj = PLAT.handle_post(p, body)
            self._json(st, obj)
            status = st
        elif p == "/api/vhs/predict":
            self._json(403, STORE.predict())
            status = 403
        elif p.startswith("/api/vhs/datasets/") and p.endswith("/predict"):
            self._json(403, {"status": "NOT_AUTHORIZED", "prediction": None,
                             "model_execution": "NOT_AUTHORIZED",
                             "permission": http_policy.PERMISSIONS[
                                 "PREDICTION"]})
            status = 403
        else:
            self._err(404, "NOT_FOUND", "no POST route for %s" % parsed.path)
            status = 404
        log_access("POST", self.path, status, (time.time() - t0) * 1000)

    def _dispatch(self, path, qs):
        if path in ("/", "/index.html"):
            return self._serve_static("index.html")
        if path.startswith("/static/"):
            return self._serve_static(path[len("/static/"):])
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
            return 204

        if R2_PUBLIC is not None:
            public_result = R2_PUBLIC.handle(path, qs)
            if public_result is not None:
                st, body = public_result
                self._json(st, body)
                return st
        if path.startswith("/api/v6/p89/") or path == "/api/v6/p89":
            leaf = path.rstrip("/").split("/")[-1]
            if leaf == "p89":
                leaf = "catalog"
            qmap = {k: (v[0] if isinstance(v, list) else v) for k, v in qs.items()}
            code, obj = p89_evidence.P89Evidence().handle(leaf, qmap)
            return self._json(code, obj)
        if path.startswith("/api/v6/") and (qs.get("dataset") or ["SYRDARYA"])[0] == "SYRDARYA" and SYR.status != "OK" and not path.endswith("/execute"):
            self._json(403, {"status":"TEACHER_SOURCE_NOT_MOUNTED_IN_CANDIDATE","prediction":None,"qsim":None,"note":"Original teacher module is retained. Candidate does not read teacher Q."})
            return 403
        if path == "/api/v6" or path.startswith("/api/v6/"):
            status, body = PLAT.handle(path, qs)
            self._json(status, body)
            return status

        if path == "/api/vhs/health":
            h = STORE.health()
            h["uptime_s"] = round(time.time() - START_TS, 1)
            h["datasets"] = {"LAMAHCE": "OK", "SYRDARYA": SYR.status}
            h["syrdarya_rules_version"] = syrdarya_adapter.RULES_VERSION
            h["syrdarya_snapshot"] = SYR.snapshot_public()
            h["data_mode_by_dataset"] = {
                "LAMAHCE": h.get("data_mode"),
                "SYRDARYA": "TEACHER_CSV_READ_ONLY_LOCAL_DISPLAY"}
            h["permissions"] = {k: v["status"] for k, v in
                                http_policy.PERMISSIONS.items()}
            h["platform_version"] = platform_v06.PLATFORM_VERSION
            h["platform_build"] = platform_v06.PLATFORM_BUILD
            h["four_layer"] = ["overview", "layers", "data", "model",
                               "results"]
            h["r2_candidate"] = {"host_root":HERE,"server_pid":os.getpid(),"candidate_local":R2_CANDIDATE,"public_module":"MOUNTED","production_display_permission":"NOT_GRANTED","teacher_source_mounted":SYR.status == "OK"}
            h["datasets"]["LAMAH_CE_PUBLIC_V1"] = "FROZEN_PUBLIC_RESULTS"
            h["datasets"]["KAZAKHSTAN_PUBLIC_NETWORK"] = "OFFICIAL_BASELINE_PARTIAL_GEOMETRY_NO_KAZ_PREDICTIONS"
            h["model_execution"] = "NOT_AUTHORIZED"
            h["prediction"] = None
            self._json(200, h)
            return 200

        if path == "/api/vhs/permissions":
            self._json(200, {"permissions": http_policy.PERMISSIONS,
                             "bind": "127.0.0.1 only",
                             "cors": "same-origin only; never '*'"})
            return 200

        if path == "/api/vhs/datasets" or path.startswith("/api/vhs/datasets/"):
            status, body = SYR_API.handle(path.rstrip("/"), qs)
            self._json(status, body)
            return status

        if path == "/api/vhs/meta":
            self._json(200, STORE.meta())
            return 200

        if path == "/api/vhs/map":
            self._json(200, STORE.map_points())
            return 200

        if path == "/api/vhs/model-status":
            self._json(200, STORE.predict())
            return 200

        if path == "/api/vhs/gis/status":
            self._json(200, STORE.gis_status())
            return 200

        if path == "/api/vhs/gis/layers":
            self._json(200, STORE.gis_layers())
            return 200

        if path == "/api/vhs/pilot":
            self._json(200, STORE.pilot())
            return 200

        if path == "/api/vhs/gis/synthetic":
            import synthetic_gis
            self._json(200, synthetic_gis.build())
            return 200

        if path == "/api/vhs/predict":
            self._json(403, STORE.predict())
            return 403

        if path == "/api/vhs/export":
            return self._export(qs)

        if path == "/api/vhs/stations":
            q = (qs.get("q") or [""])[0]
            limit = _qint(qs, "limit", 25, 0, 200)
            region = (qs.get("region") or [None])[0]
            targets_only = (qs.get("targets_only") or ["0"])[0] in (
                "1", "true", "True")
            self._json(200, {
                "query": q, "region": region, "targets_only": targets_only,
                "results": STORE.search(q, limit, region, targets_only)})
            return 200

        if path == "/api/vhs/regions":
            self._json(200, {"regions": STORE.all_regions})
            return 200

        m = ROUTE_STATION.match(path)
        if m:
            sid = int(m.group(1))
            sub = m.group(2)
            if sid not in STORE.stations:
                self._err(404, "STATION_NOT_FOUND",
                          "station %d is not in the authorized metadata "
                          "(882 stations)" % sid)
                return 404
            if sub is None:
                self._json(200, STORE.station_public(sid))
                return 200
            if sub == "network":
                depth = _qint(qs, "depth", 4, 0, 30)
                self._json(200, STORE.network(sid, depth))
                return 200
            if sub == "audit":
                self._json(200, STORE.audit(sid))
                return 200
            if sub == "candidates":
                self._json(200, STORE.candidates(sid))
                return 200
            if sub == "served-targets":
                self._json(200, STORE.served_targets(sid))
                return 200
            if sub == "utw":
                w = (qs.get("w") or [None])[0]
                w_id = int(w) if w and w.isdigit() else None
                self._json(200, STORE.utw_linkage(sid, w_id))
                return 200
            self._err(404, "UNKNOWN_SUBRESOURCE", sub)
            return 404

        self._err(404, "NOT_FOUND", "no route for %s" % path[:200])
        return 404

    def _serve_static(self, rel):
        try:
            full, ctype = GUARD.resolve(rel)
        except StaticRefused as exc:
            self._err(exc.status, exc.code, "static request refused")
            return exc.status
        with open(full, "rb") as f:
            self._send(200, f.read(), ctype)
        return 200

    def _export(self, qs):
        what = (qs.get("what") or ["stations"])[0]
        fmt = (qs.get("format") or ["csv"])[0].lower()
        if what not in ("stations", "candidates"):
            self._err(400, "BAD_EXPORT", what)
            return 400
        rows, cols = STORE.export_table(what)
        if fmt == "json":
            self._json(200, {"what": what, "n": len(rows),
                             "columns": cols, "rows": rows})
            return 200
        import csv
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
        self._send(200, buf.getvalue(),
                   "text/csv; charset=utf-8",
                   {"Content-Disposition":
                    'attachment; filename="vhs_%s.csv"' % what})
        return 200


START_TS = time.time()


def main():
    global STORE, SYR, SYR_API, GUARD, PORT, PLAT, R2_PUBLIC, R2_CANDIDATE
    ap = argparse.ArgumentParser(description="VHS v0.6 four-layer local service")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8795)
    ap.add_argument("--candidate-public-preview", action="store_true", help="local candidate namespace only, NOT production display approval")
    ap.add_argument("--sandbox", default=os.environ.get("VHS_SANDBOX",""))
    ap.add_argument("--syr-source", default=None,
                    help="read-only directory with the six Syr Darya CSVs")
    args = ap.parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("refusing to bind %s: v0.5.1 serves teacher-provided "
                         "data on 127.0.0.1 only" % args.host)
    if args.syr_source:
        raise SystemExit("WEB-S1 does not mount teacher sources")
    if args.port in (8772,8773,8774,8775,8791,8792,8793,8794):
        raise SystemExit("original production ports are protected in the R2 candidate")
    R2_CANDIDATE = args.candidate_public_preview
    R2_PUBLIC = R2HostGateway(candidate_local=R2_CANDIDATE)
    PORT = args.port
    GUARD = StaticGuard(STATIC)
    STORE = VHSStore(args.sandbox)
    print("[vhs v%s] loaded %s" % (APP_VERSION, json.dumps(STORE.loaded_at)))
    SYR = syrdarya_adapter.SyrDaryaStore(
        args.syr_source or os.path.join(HERE,"tmp","NO_TEACHER_SOURCE_MOUNTED"), pinned_manifest=SYR_MANIFEST,
        expected_manifest_sha256=syrdarya_adapter.PINNED_MANIFEST_SHA256)
    SYR_API = SyrApi(SYR, STORE)
    PLAT = platform_v06.PlatformApi(STORE, SYR, SYR_API)
    print("[vhs v%s] SYRDARYA status=%s stations=%d flags=%d snapshot=%s"
          % (APP_VERSION, SYR.status, len(SYR.stations), len(SYR.flags),
             SYR.snapshot.snapshot_id if SYR.snapshot else None))
    print("[vhs v%s] static whitelist %s" % (APP_VERSION,
                                             sorted(GUARD.whitelist)))
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("[vhs v%s] build %s" % (APP_VERSION, BUILD_ID))
    print("[vhs v%s] serving %s" % (APP_VERSION, url))
    print("[vhs v%s] API root %sapi/vhs/" % (APP_VERSION, url))
    sys.stdout.flush()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n[vhs] stopped")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
