"""
tests/test_http_boundaries.py  --  VHS v0.5.1 security suite (Codex P0-01, P1-06)

All file-system probes use a SYNTHETIC fixture under W/tests/_fixtures/
static_case: a fake static root plus canary files OUTSIDE it. Real project
files (server.py, teacher CSVs) are never used as targets.

1. reproduce the v0.5 defect (E:../ drive-relative escape) against the
   synthetic fixture via tests/_v05_static_probe.py;
2. the same and ~30 more hostile paths against an in-process v0.5.1 server
   (raw sockets, so nothing is normalised by a client library);
3. junction / symlink escape (SKIP if the OS refuses to create one);
4. Host / Origin / Sec-Fetch-Site / CORS / bind policy;
5. permission domains.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, APP)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import server as S  # noqa: E402
import http_policy  # noqa: E402
from static_guard import StaticGuard, StaticRefused  # noqa: E402

V05 = os.path.join(os.path.dirname(APP), "v0.5_syrdarya_integration")
FIX = os.path.join(HERE, "_fixtures", "static_case")
ST = os.path.join(FIX, "static")
MARK = "CANARY_OUTSIDE_STATIC_7f3a"
T = Suite("test_http_boundaries")


def build_fixture():
    if os.path.isdir(FIX):
        remove_links()
        shutil.rmtree(FIX)
    os.makedirs(ST)
    os.makedirs(os.path.join(FIX, "outside_dir"))
    for n, body in (("index.html", "<html>fixture</html>"),
                    ("app.js", "console.log('fixture');"),
                    ("style.css", "body{}")):
        with open(os.path.join(ST, n), "w", encoding="utf-8") as f:
            f.write(body)
    for n in ("canary_outside.js", "canary_outside.txt",
              os.path.join("outside_dir", "canary_junction.js")):
        with open(os.path.join(FIX, n), "w", encoding="utf-8") as f:
            f.write("/* %s */" % MARK)


def make_dir_link():
    """static/jdir -> ../outside_dir via symlink, else NTFS junction."""
    link = os.path.join(ST, "jdir")
    target = os.path.join(FIX, "outside_dir")
    try:
        os.symlink(target, link, target_is_directory=True)
        return "symlink"
    except (OSError, NotImplementedError, AttributeError):
        pass
    try:
        import _winapi
        _winapi.CreateJunction(target, link)
        return "junction"
    except Exception:                           # noqa: BLE001
        return None


def make_file_link():
    link = os.path.join(ST, "link.js")
    try:
        os.symlink(os.path.join(FIX, "canary_outside.js"), link)
        return True
    except (OSError, NotImplementedError):
        return False


def remove_links():
    for n in ("jdir", "link.js"):
        p = os.path.join(ST, n)
        if os.path.islink(p) or os.path.isfile(p):
            os.remove(p)
        elif os.path.isdir(p):
            os.rmdir(p)                 # removes the junction, not the target


def raw(port, target, headers=None, method="GET", version="HTTP/1.1",
        host=True):
    h = {"Host": "127.0.0.1:%d" % port}
    if not host:
        h = {}
    h.update(headers or {})
    req = "%s %s %s\r\n" % (method, target, version) + "".join(
        "%s: %s\r\n" % kv for kv in h.items()) + "Connection: close\r\n"
    if method == "POST":
        req += "Content-Length: 2\r\n\r\n{}"
    else:
        req += "\r\n"
    s = socket.create_connection(("127.0.0.1", port), 10)
    s.sendall(req.encode("latin-1"))
    buf = b""
    while True:
        c = s.recv(65536)
        if not c:
            break
        buf += c
    s.close()
    head, _, body = buf.partition(b"\r\n\r\n")
    lines = head.decode("latin-1").split("\r\n")
    try:
        status = int(lines[0].split()[1])
    except (IndexError, ValueError):
        status = 0
    hd = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            hd.setdefault(k.strip().lower(), []).append(v.strip())
    return status, hd, body


def main():
    build_fixture()
    drive = os.path.splitdrive(APP)[0] or "E:"
    dl = make_dir_link()
    fl = make_file_link()
    probes = [
        drive + "../canary_outside.js",            # the v0.5 P0 defect
        drive.lower() + "../canary_outside.js",
        drive + "..\\canary_outside.js",
        drive + "canary_outside.js",
        "C:../canary_outside.js",
        "../canary_outside.js",
        "..\\canary_outside.js",
        "..%2fcanary_outside.js",
        "..%5ccanary_outside.js",
        "%2e%2e/canary_outside.js",
        "%2e%2e%2fcanary_outside.js",
        "%252e%252e%252fcanary_outside.js",
        "..%c0%afcanary_outside.js",
        "app.js/../../canary_outside.js",
        "./../canary_outside.js",
        "/" + FIX.replace("\\", "/") + "/canary_outside.js",
        FIX.replace("\\", "/") + "/canary_outside.js",
        FIX + "\\canary_outside.js",
        "//127.0.0.1/share/canary_outside.js",
        "\\\\127.0.0.1\\share\\canary_outside.js",
        "app.js%00.txt",
        "app.js::$DATA",
        "app.js.",
        "app.js%20",
        "APP.JS",
        "CON.js", "nul.js", "COM1.js", "lpt9.css", "aux.html",
        "con/app.js",
        "jdir/canary_junction.js",
        "link.js",
        "../canary_outside.txt",
        "index.html.bak",
    ]
    pf = os.path.join(APP, "tmp", "static_probes.json")
    os.makedirs(os.path.dirname(pf), exist_ok=True)
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(probes, f)

    # ---- 1. reproduce the v0.5 defect (synthetic fixture only) ---------
    v05 = None
    if os.path.isfile(os.path.join(V05, "server.py")):
        e = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                 TEMP=os.path.join(APP, "tmp"), TMP=os.path.join(APP, "tmp"))
        r = subprocess.run([sys.executable, "-B",
                            os.path.join(HERE, "_v05_static_probe.py"), V05,
                            ST, pf], capture_output=True, text=True,
                           encoding="utf-8", env=e, cwd=os.path.join(APP,
                                                                     "tmp"))
        try:
            v05 = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:                       # noqa: BLE001
            T.check("R00", "v0.5 probe child ran", False, r.stderr[-400:])
    if v05:
        res = {x["rel"]: x for x in v05["results"]}
        d0 = res[probes[0]]
        T.check("R01", "v0.5 defect reproduced: %s -> 200 + canary"
                % probes[0], d0["status"] == 200 and d0["canary"], d0)
        leaked = [x["rel"] for x in v05["results"] if x["canary"]]
        T.check("R02", "v0.5 leaks canary for drive-relative / link probes",
                len(leaked) >= 1, leaked)
        T.check("R03", "v0.5 probe made no write attempt in v0.5 tree",
                v05["v05_write_attempts"] == [], v05["v05_write_attempts"])
        with open(os.path.join(APP, "logs", "v05_static_defect_repro.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"fixture": FIX, "dir_link": dl, "file_link": fl,
                       "v05_results": v05["results"], "v05_leaked": leaked},
                      f, ensure_ascii=False, indent=1)
    else:
        T.skip("R01", "v0.5 defect reproduction", "v0.5 server.py not found")

    # ---- 2. v0.5.1 in-process server on the fixture ------------------
    S.GUARD = StaticGuard(ST)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    port = srv.server_address[1]
    S.PORT = port
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    results = []
    try:
        st, hd, body = raw(port, "/static/app.js")
        T.check("S00", "positive control /static/app.js -> 200",
                st == 200 and b"fixture" in body, st)
        st, hd, body = raw(port, "/")
        T.check("S00b", "positive control / -> 200 index", st == 200, st)
        n_ok = 0
        for i, p in enumerate(probes):
            st, hd, body = raw(port, "/static/" + p.replace(" ", "%20"))
            leak = MARK.encode() in body
            results.append({"rel": p, "status": st, "canary": leak})
            ok = st in (400, 403, 404) and not leak
            n_ok += ok
            T.check("S%02d" % (i + 1), "v0.5.1 refuses %s" % p[:50], ok,
                    "status=%s canary=%s" % (st, leak))
        T.check("S90", "no hostile probe returned canary bytes",
                not any(r["canary"] for r in results))
        if v05:
            T.check("S91", "same drive-relative probe: v0.5 200 -> v0.5.1 "
                    "400", results[0]["status"] == 400 and
                    res[probes[0]]["status"] == 200, results[0])
        # unit level, realpath layer alone (whitelist off)
        g2 = StaticGuard(ST, use_whitelist=False)
        if dl:
            try:
                g2.resolve("jdir/canary_junction.js")
                T.check("J01", "%s escape refused by realpath layer" % dl,
                        False, "resolved")
            except StaticRefused as e:
                T.check("J01", "%s escape refused by realpath layer (%s)"
                        % (dl, e.code), e.code == "OUTSIDE_STATIC_ROOT",
                        e.code)
        else:
            T.skip("J01", "directory junction/symlink escape",
                   "OS refused to create a symlink or junction")
        if fl:
            try:
                g2.resolve("link.js")
                T.check("J02", "file symlink escape refused", False,
                        "resolved")
            except StaticRefused as e:
                T.check("J02", "file symlink escape refused (%s)" % e.code,
                        e.code == "OUTSIDE_STATIC_ROOT", e.code)
        else:
            T.skip("J02", "file symlink escape",
                   "os.symlink not permitted (needs admin/developer mode)")
        T.check("J03", "whitelist = top-level regular files only",
                sorted(S.GUARD.whitelist) == ["app.js", "index.html",
                                              "style.css"],
                sorted(S.GUARD.whitelist))

        # ---- 4. Host / Origin / CORS -----------------------------------
        same = "http://127.0.0.1:%d" % port
        api = "/api/vhs/permissions"
        allh = []

        def rq(tid, title, target, expect, **kw):
            st, hd, body = raw(port, target, **kw)
            allh.append(hd)
            T.check(tid, title, st == expect, "status=%s body=%s"
                    % (st, body[:120]))
            return st, hd, body
        rq("H01", "Host evil.example -> 403", api, 403,
           headers={"Host": "evil.example:%d" % port}, host=False)
        rq("H02", "Host 127.0.0.1 without port -> 403", api, 403,
           headers={"Host": "127.0.0.1"}, host=False)
        rq("H03", "Host rebinding name attacker.test -> 403", api, 403,
           headers={"Host": "attacker.test"}, host=False)
        rq("H04", "missing Host (HTTP/1.0) -> 403", api, 403, host=False,
           version="HTTP/1.0")
        rq("H05", "Host localhost:port -> 200", api, 200,
           headers={"Host": "localhost:%d" % port}, host=False)
        rq("O01", "Origin https://evil.example GET api -> 403", api, 403,
           headers={"Origin": "https://evil.example"})
        rq("O02", "Origin null -> 403", api, 403, headers={"Origin": "null"})
        rq("O03", "Origin same port other scheme https -> 403", api, 403,
           headers={"Origin": "https://127.0.0.1:%d" % port})
        rq("O04", "Origin other local port -> 403", api, 403,
           headers={"Origin": "http://127.0.0.1:8773"})
        st, hd, _ = rq("O05", "same Origin -> 200", api, 200,
                       headers={"Origin": same})
        T.check("O06", "same Origin echoed (never *), Vary: Origin",
                hd.get("access-control-allow-origin") == [same] and
                "Origin" in hd.get("vary", []), hd)
        st, hd, _ = rq("O07", "no Origin -> 200", api, 200)
        T.check("O08", "no Origin -> no ACAO header",
                "access-control-allow-origin" not in hd, hd)
        rq("O09", "OPTIONS preflight from evil origin -> 403", api, 403,
           method="OPTIONS", headers={"Origin": "https://evil.example"})
        st, hd, _ = rq("O10", "OPTIONS same origin -> 204", api, 204,
                       method="OPTIONS", headers={"Origin": same})
        rq("O11", "POST predict evil Origin refused before route -> 403",
           "/api/vhs/datasets/SYRDARYA/predict", 403, method="POST",
           headers={"Origin": "https://evil.example"})
        st, hd, body = rq("O12", "POST predict same origin -> 403",
                          "/api/vhs/datasets/SYRDARYA/predict", 403,
                          method="POST", headers={"Origin": same})
        try:
            b = json.loads(body)
        except ValueError:
            b = {}
        T.check("O13", "predict body prediction=null, NOT_AUTHORIZED",
                b.get("prediction", "x") is None and
                b.get("status") == "NOT_AUTHORIZED", b)
        rq("O14", "Sec-Fetch-Site cross-site fetch of api -> 403", api, 403,
           headers={"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"})
        rq("O15", "Sec-Fetch-Site same-site (other port) api -> 403", api,
           403, headers={"Sec-Fetch-Site": "same-site"})
        rq("O16", "cross-site top-level navigation to / allowed", "/", 200,
           headers={"Sec-Fetch-Site": "cross-site",
                    "Sec-Fetch-Mode": "navigate"})
        rq("O17", "cross-site navigation to static js refused",
           "/static/app.js", 403, headers={"Sec-Fetch-Site": "cross-site",
                                           "Sec-Fetch-Mode": "navigate"})
        rq("O18", "Sec-Fetch-Site same-origin -> 200", api, 200,
           headers={"Sec-Fetch-Site": "same-origin"})
        rq("O19", "unsupported method PUT -> 501/405", api, 501,
           method="PUT")
        T.check("O20", "no response ever carried ACAO '*'",
                not any("*" in h.get("access-control-allow-origin", [])
                        for h in allh))
        st, hd, _ = raw(port, api)
        T.check("O21", "security headers nosniff / DENY / CSP present",
                hd.get("x-content-type-options") == ["nosniff"] and
                hd.get("x-frame-options") == ["DENY"] and
                "frame-ancestors 'none'" in hd.get(
                    "content-security-policy", [""])[0], hd)
        st, hd, body = raw(port, "/api/vhs/permissions")
        perm = json.loads(body)["permissions"]
        T.check("P01", "permission domains: display AUTHORIZED, others not",
                {k: v["status"] for k, v in perm.items()} == {
                    "HISTORICAL_OBSERVATION_DISPLAY": "AUTHORIZED",
                    "FUTURE_MODEL_INPUT": "NOT_AUTHORIZED",
                    "PREDICTION": "NOT_AUTHORIZED",
                    "DATA_EXPORT": "NOT_AUTHORIZED"}, perm)
        st, hd, body = raw(port, "/api/vhs/stations?limit=abc")
        T.check("Q01", "malformed limit -> 400 (not 500)", st == 400, st)
        class _Stub:
            stations = {58: object()}
            def network(self, sid, depth):
                return {"station": sid, "depth": depth, "nodes": []}
        S.STORE = _Stub()
        st, hd, body = raw(port, "/api/vhs/stations/58/network?depth=x")
        T.check("Q02", "malformed depth -> 400 (not 500)", st == 400, st)
        S.STORE = None
    finally:
        srv.shutdown()
        srv.server_close()

    # ---- bind refusal + v0.5 source evidence ------------------------------
    r = subprocess.run([sys.executable, "-B", os.path.join(APP, "server.py"),
                        "--host", "0.0.0.0", "--port", "1"],
                       capture_output=True, text=True, encoding="utf-8",
                       timeout=60, env=dict(os.environ,
                                            PYTHONDONTWRITEBYTECODE="1"))
    T.check("B01", "--host 0.0.0.0 refused before any data is loaded",
            r.returncode != 0 and "refusing to bind" in (r.stderr + r.stdout),
            (r.stderr + r.stdout)[-200:])
    with open(os.path.join(APP, "server.py"), encoding="utf-8") as f:
        new_src = f.read()
    T.check("B02", "v0.5.1 server.py contains no ACAO '*'",
            '"Access-Control-Allow-Origin", "*"' not in new_src)
    if os.path.isfile(os.path.join(V05, "server.py")):
        with open(os.path.join(V05, "server.py"), encoding="utf-8") as f:
            T.check("B03", "evidence: v0.5 server.py did send ACAO '*'",
                    '"Access-Control-Allow-Origin", "*"' in f.read())
    remove_links()
    T.check("Z01", "fixture links removed after test",
            not os.path.lexists(os.path.join(ST, "jdir")) and
            not os.path.lexists(os.path.join(ST, "link.js")))
    os.remove(pf)
    return T.save({"dir_link_kind": dl, "file_symlink": fl,
                   "v051_results": results})


if __name__ == "__main__":
    raise SystemExit(main())
