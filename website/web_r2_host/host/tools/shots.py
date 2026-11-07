"""
tools/shots.py -- drive the already-installed Chrome (headless) over CDP,
check every v0.6 route for JS errors and horizontal overflow, and save
real screenshots.  Nothing is installed or downloaded; loopback only.

    python -B tools/shots.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import cdp  # noqa: E402

CHROME = os.environ.get("VHS_CHROME", r"C:\Users\Administrator\AppData\Local"
                        r"\Google\Chrome\Application\chrome.exe")
SHOTS = os.path.join(APP, "screenshots")
LOGS = os.path.join(APP, "logs")
ROUTES = [
    ("01_overview_syrdarya", "/#/overview?dataset=SYRDARYA"),
    ("02_overview_lamahce", "/#/overview?dataset=LAMAHCE"),
    ("03_layers_syrdarya", "/#/layers?dataset=SYRDARYA"),
    ("04_layers_lamahce_map", "/#/layers?dataset=LAMAHCE"),
    ("05_data_catalog", "/#/data?dataset=SYRDARYA"),
    ("06_data_history_flow", "/#/data/history?dataset=SYRDARYA&station=SYRDARYA:16037&year=2010"),
    ("07_data_history_wb", "/#/data/history?dataset=SYRDARYA&year=2010&tab=wb&alpha=0.75&width=3.0"),
    ("08_data_remote", "/#/data/remote?dataset=SYRDARYA&year=2010"),
    ("09_data_quality", "/#/data/quality?dataset=SYRDARYA"),
    ("10_data_yearbook", "/#/data/yearbook?dataset=SYRDARYA"),
    ("11_model_architecture", "/#/model?dataset=SYRDARYA"),
    ("12_model_config", "/#/model/config?dataset=SYRDARYA&model=SYR-B1"),
    ("13_model_workflow", "/#/model/run?dataset=SYRDARYA"),
    ("14_results_station", "/#/results?dataset=SYRDARYA&station=SYRDARYA:16037"),
    ("15_results_evaluation", "/#/results/evaluation?dataset=SYRDARYA"),
    ("16_results_spatial", "/#/results/spatial?dataset=SYRDARYA"),
    ("17_results_report", "/#/results/report?dataset=SYRDARYA&station=SYRDARYA:16037"),
    ("18_results_lamahce", "/#/results?dataset=LAMAHCE&station=LAMAHCE:58"),
    ("19_layers_800px", "/#/layers?dataset=LAMAHCE"),
    ("20_results_report_800px", "/#/results/report?dataset=SYRDARYA&station=SYRDARYA:16037"),
]


def free_port(start=18790):
    for p in range(start, start + 200):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise RuntimeError("no free port")


def start_server(port):
    os.makedirs(LOGS, exist_ok=True)
    log = open(os.path.join(LOGS, "ui_server.log"), "w", encoding="utf-8")
    env = dict(os.environ)
    env["TEMP"] = env["TMP"] = os.path.join(APP, "tmp")
    os.makedirs(env["TEMP"], exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-B",
                             os.path.join(APP, "server.py"), "--port", str(port)],
                            cwd=APP, stdout=log, stderr=subprocess.STDOUT, env=env)
    base = "http://127.0.0.1:%d" % port
    for _ in range(240):
        if proc.poll() is not None:
            raise RuntimeError("server exited rc=%s" % proc.returncode)
        try:
            with urllib.request.urlopen(base + "/api/vhs/health", timeout=2) as r:
                json.loads(r.read())
                return proc, base
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("server did not start")


def main():
    if not os.path.isfile(CHROME):
        print(json.dumps({"error": "chrome not found", "path": CHROME}))
        return 1
    os.makedirs(SHOTS, exist_ok=True)
    port = free_port()
    srv, base = start_server(port)
    prof = os.path.join(APP, "tmp", "shots_profile_%d" % os.getpid())
    if os.path.isdir(prof):
        shutil.rmtree(prof, ignore_errors=True)
    b = None
    out = {"base": base, "chrome": CHROME, "routes": [], "errors": []}
    try:
        b = cdp.Browser(CHROME, prof, free_port(19500))
        b.viewport(1440, 900)
        for name, path in ROUTES:
            before = len(b.events)
            b.goto(base + path, "document.readyState==='complete'")
            ok = b.wait("(()=>{const v=document.getElementById('view');"
                        "return v && !v.querySelector('.loading') && (v.textContent.length>40)})()", 25)
            time.sleep(0.45)
            sz = {"sw": b.eval("document.documentElement.scrollWidth"),
                  "cw": b.eval("document.documentElement.clientWidth")}
            errs = []
            for m in b.events[before:]:
                if m.get("method") == "Runtime.exceptionThrown":
                    errs.append(m["params"]["exceptionDetails"].get("text", "exception"))
                if m.get("method") == "Runtime.consoleAPICalled" and \
                        m["params"].get("type") == "error":
                    errs.append("console.error: " + " ".join(
                        str(a.get("value", a.get("description", "")))
                        for a in m["params"]["args"]))
            if "800px" in name:
                b.viewport(800, 900)
                b.goto(base + path, "document.readyState==='complete'")
                b.wait("(()=>{const v=document.getElementById('view');"
                       "return v && !v.querySelector('.loading')})()", 25)
                time.sleep(0.4)
                sz = {"sw": b.eval("document.documentElement.scrollWidth"),
                      "cw": b.eval("document.documentElement.clientWidth")}
            shot = os.path.join(SHOTS, "v06_" + name + ".png")
            b.screenshot(shot)
            out["routes"].append({"name": name, "path": path, "rendered": ok,
                                  "overflow": sz["sw"] > sz["cw"] + 1,
                                  "scrollWidth": sz["sw"], "clientWidth": sz["cw"],
                                  "errors": errs, "shot": os.path.basename(shot)})
            if errs:
                out["errors"].append({"name": name, "errors": errs})
            print("%-28s rendered=%-5s overflow=%-5s errors=%d" %
                  (name, ok, sz["sw"] > sz["cw"] + 1, len(errs)))
            b.viewport(1440, 900)
    finally:
        if b:
            b.close()
        srv.kill()
    with open(os.path.join(LOGS, "ui_smoke.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("errors:", len(out["errors"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
