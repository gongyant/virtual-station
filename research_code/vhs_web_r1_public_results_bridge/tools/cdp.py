"""
tools/cdp.py -- minimal Chrome DevTools Protocol client (stdlib only).

Used by tests/test_browser_cdp.py to drive an ALREADY INSTALLED Chrome in
headless mode with a throw-away profile directory inside W/tmp. Nothing is
installed or downloaded. Only connects to 127.0.0.1.
"""
import base64
import json
import os
import socket
import struct
import subprocess
import time
import urllib.request


class WebSocket:
    def __init__(self, url, timeout=30):
        assert url.startswith("ws://127.0.0.1:") or url.startswith(
            "ws://localhost:"), url
        hostport, path = url[5:].split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        req = ("GET /%s HTTP/1.1\r\nHost: %s\r\nUpgrade: websocket\r\n"
               "Connection: Upgrade\r\nSec-WebSocket-Key: %s\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n" % (path, hostport, key))
        self.sock.sendall(req.encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("handshake failed")
            buf += chunk
        head, self.rest = buf.split(b"\r\n\r\n", 1)
        if b" 101 " not in head.split(b"\r\n")[0]:
            raise ConnectionError(head[:200])

    def send(self, text):
        data = text.encode("utf-8")
        hdr = bytearray([0x81])
        n = len(data)
        if n < 126:
            hdr.append(0x80 | n)
        elif n < 65536:
            hdr.append(0x80 | 126)
            hdr += struct.pack(">H", n)
        else:
            hdr.append(0x80 | 127)
            hdr += struct.pack(">Q", n)
        mask = os.urandom(4)
        hdr += mask
        self.sock.sendall(bytes(hdr) + bytes(b ^ mask[i % 4]
                                             for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.rest) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise ConnectionError("closed")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def recv(self):
        msg = b""
        while True:
            b1, b2 = self._read(2)
            op, n = b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            if b2 & 0x80:
                mask = self._read(4)
                payload = bytes(b ^ mask[i % 4]
                                for i, b in enumerate(self._read(n)))
            else:
                payload = self._read(n)
            if op == 0x9:                       # ping -> ignore
                continue
            if op == 0x8:
                raise ConnectionError("ws closed")
            msg += payload
            if b1 & 0x80:
                return msg.decode("utf-8")

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Browser:
    def __init__(self, chrome, profile_dir, port, width=1366, height=768):
        self.port = port
        self.proc = subprocess.Popen(
            [chrome, "--headless=new", "--remote-debugging-port=%d" % port,
             "--remote-debugging-address=127.0.0.1",
             "--user-data-dir=%s" % profile_dir, "--no-first-run",
             "--no-default-browser-check", "--disable-extensions",
             "--disable-background-networking", "--disable-sync",
             "--disable-component-update", "--metrics-recording-only",
             "--disable-default-apps", "--mute-audio",
             "--window-size=%d,%d" % (width, height), "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        base = "http://127.0.0.1:%d" % port
        for _ in range(100):
            try:
                with urllib.request.urlopen(base + "/json/list",
                                            timeout=1) as r:
                    tabs = json.loads(r.read())
                pages = [t for t in tabs if t.get("type") == "page"]
                if pages:
                    self.ws = WebSocket(pages[0]["webSocketDebuggerUrl"])
                    break
            except Exception:                   # noqa: BLE001
                time.sleep(0.2)
        else:
            self.proc.kill()
            raise RuntimeError("chrome devtools not reachable")
        self.mid = 0
        self.events = []
        self.call("Page.enable")
        self.call("Runtime.enable")

    def call(self, method, **params):
        self.mid += 1
        my = self.mid
        self.ws.send(json.dumps({"id": my, "method": method,
                                 "params": params}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get("id") == my:
                if "error" in m:
                    raise RuntimeError("%s: %s" % (method, m["error"]))
                return m.get("result", {})
            self.events.append(m)

    def eval(self, expr, await_promise=True, cmdline=False):
        r = self.call("Runtime.evaluate", expression=expr,
                      awaitPromise=await_promise, returnByValue=True,
                      includeCommandLineAPI=cmdline)
        if "exceptionDetails" in r:
            raise RuntimeError("JS error: %s" % json.dumps(
                r["exceptionDetails"])[:500])
        return r.get("result", {}).get("value")

    def wait(self, expr, timeout=15.0, step=0.15):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.eval(expr):
                    return True
            except RuntimeError:
                pass
            time.sleep(step)
        return False

    def viewport(self, w, h):
        self.call("Emulation.setDeviceMetricsOverride", width=w, height=h,
                  deviceScaleFactor=1, mobile=False)

    def goto(self, url, wait_expr="document.readyState==='complete'"):
        self.call("Page.navigate", url=url)
        return self.wait(wait_expr)

    def screenshot(self, path, full=False):
        kw = {"format": "png"}
        if full:
            kw["captureBeyondViewport"] = True
        data = self.call("Page.captureScreenshot", **kw)["data"]
        with open(path, "wb") as f:
            f.write(base64.b64decode(data))
        return os.path.getsize(path)

    def errors(self):
        out = []
        for m in self.events:
            if m.get("method") == "Runtime.exceptionThrown":
                out.append(m["params"]["exceptionDetails"].get("text"))
            if m.get("method") == "Runtime.consoleAPICalled" and \
                    m["params"].get("type") in ("error", "warning"):
                out.append(" ".join(str(a.get("value", a.get(
                    "description", ""))) for a in m["params"]["args"]))
        return out

    def close(self):
        try:
            self.call("Browser.close")
        except Exception:                       # noqa: BLE001
            pass
        self.ws.close()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
