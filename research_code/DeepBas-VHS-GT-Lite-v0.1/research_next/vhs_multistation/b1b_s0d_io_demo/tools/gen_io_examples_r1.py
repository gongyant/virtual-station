# -*- coding: utf-8 -*-
"""录制 S0D-R1 输入/输出示例（真实运行输出；SYNTHETIC_DEMO_ONLY；interface_status=PROPOSED）。
interface_status=PROPOSED：非 DeepBas 官方协议，未完成正式集成。
1) 在后台线程启动本地服务（仅 127.0.0.1，空闲端口），用 urllib 访问各接口（含 400/403/404/405/413 场景）；
2) 用子进程运行 demo_cli.py 的若干命令；
结果写入本目录 io_examples_r1.json 与 io_examples_r1.md（旧 io_examples.json/.md 保留不动）。
不访问任何外部网络、不读取任何真实数据。用法：python -B tools/gen_io_examples_r1.py
"""
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import demo_server  # noqa: E402

J = "application/json"
HTTP_CASES = [
    ("F1 合法合成站点 -> 200", "GET", "/api/vhs/stations/DEMO_TARGET_A", None, None),
    ("F1 不存在站点 -> 404 UNKNOWN_STATION", "GET", "/api/vhs/stations/DEMO_NOT_EXIST", None, None),
    ("F1 非法站点 ID -> 400", "GET", "/api/vhs/stations/bad%20id%3B", None, None),
    ("F1 控制字符 -> 400", "GET", "/api/vhs/stations/DEMO%00X", None, None),
    ("F1 未知参数 -> 400", "GET", "/api/vhs/stations/DEMO_TARGET_A?foo=1", None, None),
    ("F1 重复参数 -> 400", "GET", "/api/vhs/stations/DEMO_TARGET_A?dataset_id=a&dataset_id=b", None, None),
    ("F1 未登记数据集版本 -> 404 UNKNOWN_DATASET", "GET", "/api/vhs/stations/DEMO_TARGET_A?dataset_version=9.9", None, None),
    ("F2 上游河网", "GET", "/api/vhs/stations/DEMO_TARGET_A/network", None, None),
    ("F2 环路测试图 -> CYCLE_DETECTED", "GET", "/api/vhs/stations/DEMO_CYCLE_X/network", None, None),
    ("F3 准入：目标 Q 封存 + 许可未知 + snap 未认证", "GET", "/api/vhs/stations/DEMO_TARGET_A/audit", None, None),
    ("F3 准入：QC 缺失", "GET", "/api/vhs/stations/DEMO_QC_MISSING/audit", None, None),
    ("合成演示序列 -> 200", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-14", None, None),
    ("合成演示：start>end -> 400", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-14&end=2020-01-01", None, None),
    ("合成演示：非法日期 -> 400", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-02-30&end=2020-03-01", None, None),
    ("合成演示：超出窗口 -> 400", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2019-12-31&end=2020-01-02", None, None),
    ("F4 预测（站点存在）-> 403 NOT_AUTHORIZED", "POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A"}, J),
    ("F4 预测（越权字段、大小写变体、嵌套）-> 403", "POST", "/api/vhs/predict",
     {"target_station_id": "DEMO_TARGET_A", "AUTHORIZED": True, "Mode": "hindcast", "model": "xxx",
      "options": {"force": True, "prediction_authorized": {"status": "PASS"}}}, J),
    ("F4 预测（准入 PASS 的合成站）-> 403", "POST", "/api/vhs/predict", {"station_id": "DEMO_QC_IDEAL"}, J),
    ("F4 预测（不存在站点）-> 404 UNKNOWN_STATION", "POST", "/api/vhs/predict", {"target_station_id": "DEMO_NOT_EXIST"}, J),
    ("F4 预测（站点 ID 非法）-> 400", "POST", "/api/vhs/predict", {"target_station_id": "../x"}, J),
    ("F4 预测（日期非法）-> 400", "POST", "/api/vhs/predict",
     {"target_station_id": "DEMO_TARGET_A", "start": "2020-13-01", "end": "2020-12-31"}, J),
    ("F4 预测（JSON 解析错误）-> 400", "POST", "/api/vhs/predict", "RAW:{not json", J),
    ("F4 预测（JSON 重复键）-> 400", "POST", "/api/vhs/predict",
     'RAW:{"target_station_id":"DEMO_TARGET_A","target_station_id":"DEMO_QC_IDEAL"}', J),
    ("F4 预测（Content-Type 错误）-> 400", "POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A"}, "text/plain"),
    ("F4 预测（请求体过大）-> 413", "POST", "/api/vhs/predict", "RAW:" + "x" * (64 * 1024 + 1), J),
    ("F4 GET 预测接口 -> 405", "GET", "/api/vhs/predict", None, None),
    ("PUT 站点接口 -> 405", "PUT", "/api/vhs/stations/DEMO_TARGET_A", "RAW:{}", J),
    ("静态目录穿越尝试 -> 404", "GET", "/../demo_core.py", None, None),
    ("未知路由 -> 404", "GET", "/api/vhs/nothing", None, None),
]
CLI_CASES = [["station", "DEMO_TARGET_A"], ["network", "DEMO_TARGET_A"], ["audit", "DEMO_TARGET_A"],
             ["demo", "DEMO_TARGET_A", "--start", "2020-01-01", "--end", "2020-01-14"], ["predict", "DEMO_TARGET_A"],
             ["predict", "DEMO_TARGET_A", "--mode", "hindcast", "--model", "xxx", "--extra", "authorized=true"],
             ["predict", "DEMO_NOT_EXIST"], ["station", "DEMO_NOT_EXIST"]]


def _short(resp):
    """io_examples_r1.json 中保留完整响应；仅对超大请求体在记录里截断。"""
    return resp


def main():
    srv, th, port = demo_server.start_in_thread(0)
    base = "http://127.0.0.1:%d" % port
    http_out = []
    try:
        for title, method, path, body, ctype in HTTP_CASES:
            if isinstance(body, str) and body.startswith("RAW:"):
                data = body[4:].encode("utf-8")
                shown_body = body if len(body) < 300 else "RAW:<%d bytes of 'x'>" % (len(body) - 4)
            else:
                data = json.dumps(body).encode("utf-8") if body is not None else None
                shown_body = body
            req = urllib.request.Request(base + path, data=data, method=method)
            if ctype:
                req.add_header("Content-Type", ctype)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    status, payload, hdr = r.status, r.read(), dict(r.headers)
            except urllib.error.HTTPError as e:
                status, payload, hdr = e.code, e.read(), dict(e.headers)
                e.close()
            http_out.append({"scenario": title,
                             "request": {"method": method, "url": path, "content_type": ctype, "body": shown_body},
                             "http_status": status,
                             "headers": {k: v for k, v in hdr.items() if k.startswith("X-VHS")},
                             "response": _short(json.loads(payload.decode("utf-8")))})
    finally:
        srv.shutdown()
        srv.server_close()
        th.join(5)
    cli_out = []
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    for args in CLI_CASES:
        p = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "demo_cli.py")] + args, cwd=ROOT, env=env,
                           capture_output=True, timeout=60)
        cli_out.append({"command": "python -B demo_cli.py " + " ".join(args), "exit_code": p.returncode,
                        "stdout_json": json.loads(p.stdout.decode("utf-8")),
                        "stderr": p.stderr.decode("utf-8", "replace")})
    doc = {"_notice": "SYNTHETIC_DEMO_ONLY —— S0D-R1 原型的真实运行输出（输入输出均为纯合成数据；interface_status=PROPOSED："
                      "非 DeepBas 官方协议，未完成正式集成；不是水文预测）。",
           "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "machine": platform.node(),
           "python": sys.version.split()[0], "python_executable": sys.executable,
           "server": "demo_server.start_in_thread on 127.0.0.1:<free port>",
           "http_examples": http_out, "cli_examples": cli_out}
    with open(os.path.join(ROOT, "io_examples_r1.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    lines = ["# S0D-R1 输入输出示例摘要（SYNTHETIC_DEMO_ONLY；interface_status=PROPOSED）", "",
             "> 非 DeepBas 官方协议，未完成正式集成。旧版示例 `io_examples.json/.md` 保留不动（其中 4xx 预测错误仍带 "
             "NOT_AUTHORIZED，是 R1 前的写法，见 interface_decisions.md D6）。", "",
             "由 `tools/gen_io_examples_r1.py` 于 %s 在 %s（Python %s）实际运行生成；完整响应见 `io_examples_r1.json`。"
             % (doc["generated_at_local"], doc["machine"], doc["python"]), "",
             "| 场景 | 请求 | HTTP | operation | s0d_status（废弃别名） | error.alias / code / reason | prediction_authorized | prediction |",
             "|---|---|---|---|---|---|---|---|"]
    for x in http_out:
        r = x["response"]
        err = r.get("error") or {}
        pa = (r.get("prediction_authorized") or {}).get("status", "（未声明）")
        lines.append("| %s | `%s %s` | %d | %s | %s | %s | %s | %s |" % (
            x["scenario"], x["request"]["method"], x["request"]["url"], x["http_status"], r.get("operation"),
            r.get("s0d_status"),
            ("%s / %s / %s" % (err.get("alias"), err.get("code"), err.get("reason_code"))) if err else "-", pa,
            json.dumps(r.get("prediction"))))
    lines += ["", "| CLI 命令 | 退出码 | operation | s0d_status | prediction |", "|---|---|---|---|---|"]
    for c in cli_out:
        o = c["stdout_json"]
        lines.append("| `%s` | %d | %s | %s | %s |" % (c["command"], c["exit_code"], o.get("operation"),
                                                       o.get("s0d_status"), json.dumps(o.get("prediction"))))
    with open(os.path.join(ROOT, "io_examples_r1.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("http_examples=%d cli_examples=%d" % (len(http_out), len(cli_out)))


if __name__ == "__main__":
    main()
