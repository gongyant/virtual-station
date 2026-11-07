# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 本地演示 HTTP 服务（标准库 http.server；仅绑定 127.0.0.1）。

PROPOSED 本地原型接口，非 DeepBas 官方协议；全部数据为 SYNTHETIC_DEMO_ONLY。
  GET  /                                   -> index.html
  GET  /api/vhs/stations/{station_id}            F1 站点信息
  GET  /api/vhs/stations/{station_id}/network    F2 上游河网关系
  GET  /api/vhs/stations/{station_id}/audit      F3 数据质量与科学准入
  GET  /api/vhs/synthetic-demo?station_id=&start=&end=   合成演示序列（synthetic_display_data）
  POST /api/vhs/predict                          F4 恒 NOT_AUTHORIZED，prediction=null
用法：python -B demo_server.py [--port 8765]
"""
import argparse
import json
import logging
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import demo_core as core  # noqa: E402

BIND_HOST = "127.0.0.1"          # 固定，不提供修改入口
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 64 * 1024
DRAIN_LIMIT_BYTES = 1024 * 1024
MAX_URL_CHARS = 2048
STATIC_WHITELIST = {             # URL 路径 -> (本目录内文件名, Content-Type)；只服务这些文件
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/offline_snapshot.js": ("offline_snapshot.js", "application/javascript; charset=utf-8"),
}
STATION_ROUTE = re.compile(r"^/api/vhs/stations/([^/]{1,200})(/network|/audit)?$")
CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
       "connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class LocalOnlyServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, port, handler):
        super().__init__((BIND_HOST, port), handler)
        if self.server_address[0] != BIND_HOST:
            self.server_close()
            raise RuntimeError("refusing to bind anything other than 127.0.0.1")


class Handler(BaseHTTPRequestHandler):
    server_version = "VHS-S0D-Demo/0.1"
    sys_version = ""
    protocol_version = "HTTP/1.1"
    timeout = 15

    # 原始访问日志可能含查询串原文，禁用；改为经过滤的结构化日志
    def log_message(self, fmt, *args):
        return

    def _log(self, route, status, function="-", sid="-", s0d_status="-"):
        core.safe_log({"event": "request", "method": self.command, "route": route, "http_status": status,
                       "function": function, "station_id": sid, "s0d_status": s0d_status})

    def _send(self, status, body, ctype, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-VHS-Protocol-Status", core.PROTOCOL_STATUS)
        self.send_header("X-VHS-Data-Class", core.DEMO_FLAG)
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status, resp, route, function="-", sid="-"):
        if resp.get("prediction", None) is not None:   # 纵深防御：服务层再查一次
            resp = core.error_response(core.RequestError("INTERNAL_CONTRACT_VIOLATION", "VHS-E011",
                                                         "PREDICTION_NOT_NULL", "blocked", 500),
                                       function, "S0D-BLOCKED")[0]
            status = 500
        body = json.dumps(resp, ensure_ascii=False, indent=1).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8")
        self._log(route, status, function, sid if core.SAFE_NAME_RE.match(str(sid)) else "<invalid>",
                  resp.get("s0d_status", "-"))

    def _err(self, alias, code, reason, detail, status, route, function="-", predict=False):
        resp, _ = core.error_response(core.RequestError(alias, code, reason, detail, status), function,
                                      core.request_id(function, route), predict=predict)
        self._json(status, resp, route, function)

    def _parse_query(self, query, route):
        try:
            q = parse_qs(query, keep_blank_values=True, strict_parsing=bool(query), max_num_fields=20)
        except ValueError:
            return None
        if any(len(v) != 1 for v in q.values()):
            return None
        return {k: v[0] for k, v in q.items()}

    def do_GET(self):
        if len(self.path) > MAX_URL_CHARS:
            return self._err("INVALID_REQUEST", "VHS-E011", "URL_TOO_LONG", "url too long", 414, "<long>")
        parts = urlsplit(self.path)
        path = parts.path
        if path in STATIC_WHITELIST:
            fname, ctype = STATIC_WHITELIST[path]
            fpath = os.path.join(HERE, fname)
            try:
                with open(fpath, "rb") as fh:
                    body = fh.read()
            except OSError:
                return self._err("ROUTE_NOT_FOUND", "VHS-E011", "STATIC_FILE_MISSING", "static file missing",
                                 404, path)
            self._send(200, body, ctype)
            return self._log(path, 200, "static")
        if not path.startswith("/api/"):
            # 非白名单静态路径（含 ../、%2e%2e、反斜杠等）一律 404，不触碰文件系统
            return self._err("ROUTE_NOT_FOUND", "VHS-E011", "ROUTE_NOT_FOUND", "not found", 404, "<static-denied>")
        params = self._parse_query(parts.query, path)
        if params is None:
            return self._err("INVALID_REQUEST", "VHS-E011", "QUERY_INVALID", "malformed or duplicated query", 400,
                             path)
        m = STATION_ROUTE.match(path)
        if m:
            sid = unquote(m.group(1))
            function = {None: "station", "/network": "network", "/audit": "audit"}[m.group(2)]
            if "station_id" in params:
                return self._err("INVALID_REQUEST", "VHS-E011", "STATION_ID_DUPLICATED",
                                 "station_id must be given in the path only", 400, path, function)
            params["station_id"] = sid
            status, resp = core.handle(function, params)
            return self._json(status, resp, "/api/vhs/stations/{id}" + (m.group(2) or ""), function, sid)
        if path == "/api/vhs/synthetic-demo":
            status, resp = core.handle("demo", params)
            return self._json(status, resp, path, "demo", params.get("station_id", "-"))
        if path == "/api/vhs/predict":
            return self._err("METHOD_NOT_ALLOWED", "VHS-E011", "USE_POST", "use POST", 405, path, "predict",
                             predict=True)
        return self._err("ROUTE_NOT_FOUND", "VHS-E011", "ROUTE_NOT_FOUND", "not found", 404, "<api-unknown>")

    def do_POST(self):
        path = urlsplit(self.path).path
        if path != "/api/vhs/predict":
            self.close_connection = True
            return self._err("METHOD_NOT_ALLOWED", "VHS-E011", "POST_NOT_ALLOWED", "POST only for /api/vhs/predict",
                             405, "<post-denied>")
        if self.headers.get("Transfer-Encoding"):
            self.close_connection = True
            return self._err("INVALID_REQUEST", "VHS-E011", "CHUNKED_NOT_SUPPORTED", "Content-Length required",
                             411, path, "predict", predict=True)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            return self._err("INVALID_REQUEST", "VHS-E011", "CONTENT_LENGTH_INVALID", "bad Content-Length", 400,
                             path, "predict", predict=True)
        if length > MAX_BODY_BYTES:
            self.close_connection = True
            if length <= DRAIN_LIMIT_BYTES:     # 读掉并丢弃，避免客户端因连接被重置而收不到 413
                remaining = length
                while remaining > 0:
                    chunk = self.rfile.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            return self._err("REQUEST_TOO_LARGE", "VHS-E011", "BODY_TOO_LARGE",
                             "body larger than %d bytes" % MAX_BODY_BYTES, 413, path, "predict", predict=True)
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode("utf-8"),
                              parse_constant=lambda c: (_ for _ in ()).throw(ValueError("non-finite")))
        except (UnicodeDecodeError, ValueError):
            return self._err("INVALID_REQUEST", "VHS-E011", "JSON_PARSE_ERROR", "request body is not valid JSON",
                             400, path, "predict", predict=True)
        status, resp = core.handle_predict(body)
        sid = body.get("target_station_id", body.get("station_id", "-")) if isinstance(body, dict) else "-"
        return self._json(status, resp, path, "predict", sid)

    def _method_not_allowed(self):
        self.close_connection = True
        self._err("METHOD_NOT_ALLOWED", "VHS-E011", "METHOD_NOT_ALLOWED", "method not allowed", 405, "<method>")

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _method_not_allowed


def make_server(port=DEFAULT_PORT):
    return LocalOnlyServer(port, Handler)


def start_in_thread(port=0):
    """测试用：在后台线程启动，返回 (server, thread, port)。"""
    srv = make_server(port)
    t = threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True)
    t.start()
    return srv, t, srv.server_address[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="VHS S0D 本地演示服务（仅 127.0.0.1；SYNTHETIC_DEMO_ONLY；PROPOSED）")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help="端口，默认 %d" % DEFAULT_PORT)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    srv = make_server(a.port)
    core.safe_log({"event": "server_start", "url": "http://127.0.0.1:%d/" % srv.server_address[1],
                   "data_class": core.DEMO_FLAG, "protocol_status": core.PROTOCOL_STATUS})
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        core.safe_log({"event": "server_stop"})


if __name__ == "__main__":
    main()
