"""
tests/test_v06_ui.py -- VHS v0.6 real-browser suite (Chrome over CDP)

Drives the installed Chrome headless against a PRIVATE v0.6 server:
  * five first-level entries + hash routing + browser back/forward;
  * dataset switch keeps the two research areas separate;
  * results layer shows the observed hydrograph and the explicit empty state;
  * model config saves a real JSON through the UI, run button shows the 403;
  * layer map click opens a station summary with jump links;
  * no horizontal overflow at 800 px; no page errors.

Uses tools/cdp.py (stdlib websocket). Nothing is installed; loopback only.
"""
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(APP, "tools"))
sys.dont_write_bytecode = True

from _harness import Suite  # noqa: E402
import _server  # noqa: E402
import cdp  # noqa: E402

CHROME = os.environ.get("VHS_CHROME", r"C:\Users\Administrator\AppData\Local"
                        r"\Google\Chrome\Application\chrome.exe")
SHOTS = os.path.join(APP, "screenshots")
T = Suite("test_v06_ui")


def ready(b, extra="true", timeout=25):
    return b.wait("(()=>{const v=document.getElementById('view');"
                  "if(!v||v.querySelector('.loading'))return false;"
                  "return v.textContent.length>40 && (%s)})()" % extra, timeout)


def text(b, sel):
    return b.eval("(()=>{const x=document.querySelector(%s);"
                  "return x?x.textContent:null})()" % json.dumps(sel))


def go(b, base, hash_, extra="true"):
    b.goto(base + "/" + hash_, "document.readyState==='complete'")
    return ready(b, extra)


def no_overflow(b):
    return b.eval("(()=>{const d=document.documentElement;"
                  "return {sw:d.scrollWidth,cw:d.clientWidth}})()")


def main():
    if not os.path.isfile(CHROME):
        T.skip("B00", "browser suite", "Chrome not found at %s" % CHROME)
        return T.save()
    os.makedirs(SHOTS, exist_ok=True)
    prof = os.path.join(APP, "tmp", "chrome_v06_%d" % os.getpid())
    if os.path.isdir(prof):
        shutil.rmtree(prof, ignore_errors=True)
    proc, base, port = _server.start()
    b = None
    try:
        b = cdp.Browser(CHROME, prof, _server.free_port(19300))
        b.viewport(1440, 900)
        b.goto(base + "/#/overview?dataset=SYRDARYA",
               "document.readyState==='complete'")
        ok = ready(b)
        T.check("B01", "overview renders with five primary nav entries",
                ok and b.eval("document.querySelectorAll('#nav a').length") == 5 and
                "v0.6" in (b.eval("document.getElementById('verBadge').textContent") or ""))
        T.check("B02", "overview hydrograph drawn from real observations",
                b.eval("document.querySelectorAll('#view svg path.obs').length") >= 2 and
                "模拟结果尚未生成" in (text(b, "#view") or ""))
        T.check("B03", "overview shows fixed reach separately from browsed station",
                "固定研究河段" in (text(b, "#view") or "") and
                "当前浏览测站" in (text(b, "#view") or ""))
        b.screenshot(os.path.join(SHOTS, "v06_ui_01_overview.png"))

        # ---- dataset switch: Syr Darya -> LamaH-CE ---------------------
        b.eval("document.querySelector('#dsSwitch button[data-ds=LAMAHCE]').click()")
        ok = b.wait("(()=>{return location.hash.indexOf('LAMAHCE')>=0 && "
                    "document.getElementById('view') && "
                    "!document.getElementById('view').querySelector('.loading')})()")
        time.sleep(0.5)
        T.check("B04", "dataset switch re-renders LamaH-CE overview",
                ok and "LamaH-CE" in (text(b, "#view") or "") and
                "882" in (text(b, "#view") or ""))
        b.screenshot(os.path.join(SHOTS, "v06_ui_02_overview_lamah.png"))

        # ---- layers: real points + click -> station summary ------------
        ok = go(b, base, "#/layers?dataset=LAMAHCE",
                "document.querySelectorAll('#view circle.mapdot').length>800")
        n_dots = b.eval("document.querySelectorAll('#view circle.mapdot').length")
        T.check("B05", "layer map draws 882 real projected station dots",
                ok and n_dots == 882, n_dots)
        b.eval("(()=>{const d=document.querySelectorAll('#view circle.mapdot')[10];"
               "d.dispatchEvent(new MouseEvent('click',{bubbles:true}));return true})()")
        ok = b.wait("(()=>{const s=document.getElementById('stSummary');"
                    "return !!(s && s.textContent.indexOf('结果层')>=0 && "
                    "s.querySelector('a.btn.primary'))})()", 20)
        summary = text(b, "#stSummary") or ""
        n_links = b.eval("document.querySelectorAll('#stSummary a.btn').length") or 0
        T.check("B06", "map click opens station summary with data/results links",
                ok and "LAMAHCE:" in summary and "面积" in summary and n_links >= 2,
                (summary[:70], n_links))
        b.screenshot(os.path.join(SHOTS, "v06_ui_03_layer_station_summary.png"))

        # ---- results: station / evaluation / spatial / report ----------
        ok = go(b, base, "#/results?dataset=SYRDARYA&station=SYRDARYA:16037",
                "document.querySelectorAll('#view svg path.obs').length>=2")
        T.check("B07", "results station: big observed hydrograph + empty Qsim",
                ok and "Qsim 模拟（未生成）" in (text(b, "#view") or "") and
                "N/A" in (text(b, "#view") or ""))
        b.screenshot(os.path.join(SHOTS, "v06_ui_04_results_station.png"))

        ok = go(b, base, "#/results/evaluation?dataset=SYRDARYA")
        ev = text(b, "#view") or ""
        T.check("B08", "evaluation page: five N/A metrics + NOT_EVALUATED",
                ok and ev.count("N/A") >= 5 and "NOT_EVALUATED" in ev and
                "无共同样本" in ev)
        b.screenshot(os.path.join(SHOTS, "v06_ui_05_results_evaluation.png"))

        ok = go(b, base, "#/results/spatial?dataset=SYRDARYA")
        T.check("B09", "spatial results: empty prediction layer + contract",
                ok and "PREDICTION_LAYER_NOT_AVAILABLE" in (text(b, "#view") or "") and
                "qsim" in (text(b, "#view") or ""))

        ok = go(b, base, "#/results/report?dataset=SYRDARYA&station=SYRDARYA:16037",
                "document.querySelectorAll('#view .report h2').length>=5")
        rp = text(b, "#view") or ""
        T.check("B10", "report page renders sections, tables and not-executed marks",
                ok and "未执行" in rp and "模拟序列：未生成" in rp and
                len(rp) > 1400 and
                b.eval("document.querySelectorAll('#view .report table').length") >= 1,
                len(rp))
        b.screenshot(os.path.join(SHOTS, "v06_ui_06_results_report.png"))

        # ---- data layer: history, alpha switch, quality filter ---------
        ok = go(b, base, "#/data/history?dataset=SYRDARYA&station=SYRDARYA:16037&year=2010",
                "document.querySelectorAll('#view table tbody tr').length>=12")
        T.check("B11", "data layer: monthly statistics table (12 rows)",
                ok and b.eval("document.querySelectorAll('#view table tbody tr').length") >= 12)
        wb_text = None
        ok = go(b, base, "#/data/history?dataset=SYRDARYA&year=2010&tab=wb&alpha=0.6")
        wb_text = text(b, "#view") or ""
        b.eval("(()=>{const s=document.getElementById('alSel');"
               "s.value='0.90';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
        time.sleep(0.8)
        wb_text2 = text(b, "#view") or ""
        T.check("B12", "water balance alpha switch updates scenario residual",
                "固定源记录" in wb_text and wb_text2 != wb_text and
                "0.90" in (b.eval("document.getElementById('alSel').value") or "0.90"))
        b.screenshot(os.path.join(SHOTS, "v06_ui_07_water_balance.png"))

        ok = go(b, base, "#/data/quality?dataset=SYRDARYA",
                "document.querySelectorAll('#view table tbody tr').length>=20")
        b.eval("(()=>{const s=document.getElementById('qcSev');"
               "s.value='INFO';s.dispatchEvent(new Event('change',{bubbles:true}));return true})()")
        time.sleep(0.9)
        cnt = b.eval("(()=>{const t=document.querySelectorAll('#view table')[0];"
                     "let rows=0,errs=0;t.querySelectorAll('tbody tr').forEach(r=>{rows++;"
                     "if(r.textContent.indexOf('ERROR')>=0)errs++});return {rows:rows,errs:errs}})()")
        T.check("B13", "quality page: severity filter keeps only INFO rows",
                (cnt or {}).get("rows", 0) >= 10 and (cnt or {}).get("errs", 1) == 0, cnt)
        b.screenshot(os.path.join(SHOTS, "v06_ui_08_data_quality.png"))

        # ---- model layer: config save through the UI -------------------
        ok = go(b, base, "#/model?dataset=SYRDARYA",
                "document.querySelectorAll('#view .card').length>=5")
        T.check("B14", "model architecture: 3 baselines + roadmap not implemented",
                ok and "DEFINED_ONLY" in (text(b, "#view") or "") and
                "NOT_IMPLEMENTED" in (text(b, "#view") or ""))
        b.screenshot(os.path.join(SHOTS, "v06_ui_09_model_architecture.png"))

        ok = go(b, base, "#/model/config?dataset=SYRDARYA&model=SYR-B1",
                "!!document.getElementById('cfgPreview')")
        b.eval("(()=>{const el=document.getElementById('cfgLag');el.value='5';"
               "el.dispatchEvent(new Event('input',{bubbles:true}));return true})()")
        time.sleep(0.3)
        prev = text(b, "#cfgPreview") or ""
        T.check("B15", "config editor: form changes flow into the JSON preview",
                ok and '"lag_months": 5' in prev)
        b.eval("document.getElementById('cfgSave').click()")
        ok = b.wait("(()=>{const m=document.getElementById('cfgMsg');"
                    "return m && m.textContent.indexOf('配置已保存')>=0})()", 25)
        T.check("B16", "config save through the UI writes a real JSON (not executed)",
                ok and "executed=false" in (text(b, "#cfgMsg") or ""),
                (text(b, "#cfgMsg") or "")[:90])
        b.screenshot(os.path.join(SHOTS, "v06_ui_10_model_config_saved.png"))

        ok = go(b, base, "#/model/run?dataset=SYRDARYA",
                "!!document.getElementById('runBtn')")
        b.eval("document.getElementById('runBtn').click()")
        ok = b.wait("(()=>{const m=document.getElementById('runMsg');"
                    "return m && m.textContent.indexOf('403')>=0})()", 25)
        T.check("B17", "run button surfaces the backend 403 refusal",
                ok and "NOT_AUTHORIZED" in (text(b, "#runMsg") or ""))
        b.screenshot(os.path.join(SHOTS, "v06_ui_11_model_run_403.png"))

        # ---- browser back / forward -----------------------------------
        go(b, base, "#/overview?dataset=SYRDARYA", "document.querySelectorAll('#nav a.on').length===1")
        go(b, base, "#/results?dataset=SYRDARYA&station=SYRDARYA:16037",
           "document.querySelectorAll('#view svg path.obs').length>=2")
        b.eval("history.back()")
        ok1 = b.wait("location.hash.indexOf('/overview')>=0 && "
                     "document.querySelectorAll('#nav a.on')[0].textContent.indexOf('研究概览')>=0", 20)
        b.eval("history.forward()")
        ok2 = b.wait("location.hash.indexOf('/results')>=0 && "
                     "document.querySelectorAll('#view svg path.obs').length>=2", 20)
        T.check("B18", "browser back/forward keeps the layer and content in sync",
                ok1 and ok2, (ok1, ok2))

        # ---- 800 px responsive ----------------------------------------
        b.viewport(800, 900)
        bad = []
        for path in ["#/overview?dataset=SYRDARYA", "#/layers?dataset=LAMAHCE",
                     "#/data/quality?dataset=SYRDARYA",
                     "#/model/config?dataset=SYRDARYA&model=SYR-B1",
                     "#/results?dataset=SYRDARYA&station=SYRDARYA:16037",
                     "#/results/report?dataset=SYRDARYA&station=SYRDARYA:16037"]:
            go(b, base, path)
            s = no_overflow(b)
            if s["sw"] > s["cw"] + 1:
                bad.append((path, s))
        T.check("B19", "no horizontal overflow at 800 px on six key pages",
                bad == [], bad[:2])
        b.screenshot(os.path.join(SHOTS, "v06_ui_12_results_800px.png"))
        b.viewport(1440, 900)

        errs = b.errors()
        T.check("B20", "no uncaught page errors across the whole run",
                len(errs) == 0, errs[:3])
    finally:
        if b:
            b.close()
        _server.stop(proc)
    return T.save()


if __name__ == "__main__":
    raise SystemExit(main())
