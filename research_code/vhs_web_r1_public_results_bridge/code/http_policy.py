"""
http_policy.py  --  VHS v0.5.1 request boundary (fixes Codex P1-06)

* Host header must be exactly 127.0.0.1:<port> or localhost:<port>
  (defends against DNS rebinding); missing Host is refused.
* Origin, when present, must be the same origin
  (http://127.0.0.1:<port> or http://localhost:<port>); ``null`` and any
  other origin are refused for every method.
* Sec-Fetch-Site (sent by modern browsers even when Origin is absent) must be
  same-origin or none; a cross-site top-level navigation is tolerated only
  for the HTML entry page.
* CORS: ``Access-Control-Allow-Origin`` is never ``*``. It is echoed only
  for an allowed same origin (with Vary: Origin); otherwise omitted.
* Permission domains are explicit. Only historical observation display is
  authorised (within the existing teacher licence: local, read-only,
  per station/year/month). Future model input, prediction and data export
  are NOT_AUTHORIZED.
"""

PERMISSIONS = {
    "HISTORICAL_OBSERVATION_DISPLAY": {
        "status": "AUTHORIZED",
        "scope": "local loopback display of teacher-provided historical "
                 "observations, read-only, per station/year/month; within the "
                 "existing licence; no bulk route",
    },
    "FUTURE_MODEL_INPUT": {
        "status": "NOT_AUTHORIZED",
        "scope": "using any Syr Darya value as a model input / training "
                 "label / preprocessing parameter",
    },
    "PREDICTION": {"status": "NOT_AUTHORIZED",
                   "scope": "any model execution or prediction output"},
    "DATA_EXPORT": {"status": "NOT_AUTHORIZED",
                    "scope": "bulk or file export of Syr Darya data or "
                             "derived research products over HTTP"},
}

ENTRY_PAGES = ("/", "/index.html")


def allowed_hosts(port):
    return {"127.0.0.1:%d" % port, "localhost:%d" % port}


def allowed_origins(port):
    return {"http://127.0.0.1:%d" % port, "http://localhost:%d" % port}


def check_request(method, path, headers, port):
    """Return None if allowed, else (status, code, message)."""
    host = headers.get("Host")
    if not host or host.strip().lower() not in allowed_hosts(port):
        return (403, "HOST_NOT_ALLOWED",
                "Host header must be 127.0.0.1:%d or localhost:%d"
                % (port, port))
    origin = headers.get("Origin")
    if origin is not None and origin.strip().lower() not in \
            allowed_origins(port):
        return (403, "ORIGIN_NOT_ALLOWED",
                "cross-origin requests are refused (same-origin only)")
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if site and site not in ("same-origin", "none"):
        mode = (headers.get("Sec-Fetch-Mode") or "").strip().lower()
        if not (method == "GET" and mode == "navigate" and
                path in ENTRY_PAGES):
            return (403, "CROSS_SITE_REFUSED",
                    "Sec-Fetch-Site=%s is refused" % site)
    if method not in ("GET", "HEAD", "POST", "OPTIONS"):
        return (405, "METHOD_NOT_ALLOWED", method)
    return None


def cors_headers(headers, port):
    """Headers to add to a response: same-origin echo only, never '*'."""
    origin = headers.get("Origin")
    if origin and origin.strip().lower() in allowed_origins(port):
        return {"Access-Control-Allow-Origin": origin.strip(),
                "Vary": "Origin"}
    return {}


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
        "form-action 'none'"),
}
