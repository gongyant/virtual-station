"""Start / stop a private v0.6 server for a test run (never touches 8772-8775)."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
RESERVED_PORTS = {8772, 8773, 8774, 8775}   # v0.4 / v0.5 / v0.5.1: never used


def free_port(start=18780):
    for p in range(start, start + 200):
        if p in RESERVED_PORTS:
            continue
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


def env():
    e = dict(os.environ)
    tmp = os.path.join(APP, "tmp")
    os.makedirs(tmp, exist_ok=True)
    e["TEMP"] = e["TMP"] = tmp
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def start(port=None, timeout=180):
    port = port or free_port()
    assert port not in RESERVED_PORTS
    log = open(os.path.join(APP, "logs", "test_server_%d.log" % port), "w",
               encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-B", os.path.join(APP,
                             "server.py"), "--port", str(port)],
                            cwd=APP, stdout=log, stderr=subprocess.STDOUT,
                            env=env())
    base = "http://127.0.0.1:%d" % port
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            raise RuntimeError("server exited rc=%s" % proc.returncode)
        try:
            with urllib.request.urlopen(base + "/api/vhs/health",
                                        timeout=2) as r:
                json.loads(r.read())
                return proc, base, port
        except Exception:                       # noqa: BLE001
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("server did not come up")


def stop(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def get(base, path, method="GET", headers=None, data=None):
    req = urllib.request.Request(base + path, method=method, data=data,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            st, hd = r.status, dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        st, hd = e.code, dict(e.headers)
    try:
        body = json.loads(raw.decode("utf-8"))
    except Exception:                           # noqa: BLE001
        body = raw
    return st, body, hd
