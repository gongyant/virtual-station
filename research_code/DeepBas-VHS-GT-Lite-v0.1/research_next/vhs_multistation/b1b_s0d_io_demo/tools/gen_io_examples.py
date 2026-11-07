# -*- coding: utf-8 -*-
"""录制 S0D 输入/输出示例（真实运行输出；SYNTHETIC_DEMO_ONLY；PROPOSED）。
1) 在后台线程启动本地服务（仅 127.0.0.1，空闲端口），用 urllib 访问各接口；
2) 用子进程运行 demo_cli.py 的 5 条命令；
结果写入本目录 io_examples.json 与 io_examples.md。不访问任何外部网络、不读取任何真实数据。
用法：python -B tools/gen_io_examples.py
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

HTTP_CASES = [
    ("F1 合法合成站点", "GET", "/api/vhs/stations/DEMO_TARGET_A", None),
    ("F1 不存在站点 -> UNKNOWN_STATION", "GET", "/api/vhs/stations/DEMO_NOT_EXIST", None),
    ("F1 非法输入 -> INVALID_REQUEST", "GET", "/api/vhs/stations/bad%20id%3B", None),
    ("F1 未登记数据集版本 -> UNKNOWN_DATASET", "GET", "/api/vhs/stations/DEMO_TARGET_A?dataset_version=9.9", None),
    ("F2 上游河网（主干+支流+人工输水+snap 不确定）", "GET", "/api/vhs/stations/DEMO_TARGET_A/network", None),
    ("F2 环路测试图 -> CYCLE_DETECTED", "GET", "/api/vhs/stations/DEMO_CYCLE_X/network", None),
    ("F3 准入：目标 Q 封存 + 许可未知 + snap 未认证", "GET", "/api/vhs/stations/DEMO_TARGET_A/audit", None),
    ("F3 准入：数据完整但许可未知（不能 PASS）", "GET", "/api/vhs/stations/DEMO_QC_LICENSE_UNKNOWN/audit", None),
    ("F3 准入：QC 缺失", "GET", "/api/vhs/stations/DEMO_QC_MISSING/audit", None),
    ("合成演示序列", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-14", None),
    ("合成演示：start>end", "GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-14&end=2020-01-01",
     None),
    ("F4 预测请求（普通）", "POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A"}),
    ("F4 预测请求（试图越权：authorized/mode/model/force）", "POST", "/api/vhs/predict",
     {"target_station_id": "DEMO_TARGET_A", "authorized": True, "mode": "hindcast", "model": "xxx", "force": True,
      "start": "2020-01-01", "end": "2020-01-14"}),
    ("F4 预测请求（换成准入 PASS 的合成站）", "POST", "/api/vhs/predict", {"station_id": "DEMO_QC_IDEAL"}),
    ("F4 预测请求（JSON 解析错误）", "POST", "/api/vhs/predict", "RAW:{not json"),
    ("静态目录穿越尝试", "GET", "/../demo_core.py", None),
]
CLI_CASES = [["station", "DEMO_TARGET_A"], ["network", "DEMO_TARGET_A"], ["audit", "DEMO_TARGET_A"],
             ["demo", "DEMO_TARGET_A", "--start", "2020-01-01", "--end", "2020-01-14"], ["predict", "DEMO_TARGET_A"],
             ["station", "DEMO_NOT_EXIST"]]


def main():
    srv, th, port = demo_server.start_in_thread(0)
    base = "http://127.0.0.1:%d" % port
    http_out = []
    try:
        for title, method, path, body in HTTP_CASES:
            if isinstance(body, str) and body.startswith("RAW:"):
                data = body[4:].encode("utf-8")
            else:
                data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(base + path, data=data, method=method)
            if data is not None:
                req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    status, payload = r.status, r.read()
            except urllib.error.HTTPError as e:
                status, payload = e.code, e.read()
                e.close()
            http_out.append({"scenario": title, "request": {"method": method, "url": path, "body": body},
                             "http_status": status, "response": json.loads(payload.decode("utf-8"))})
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
    doc = {"_notice": "SYNTHETIC_DEMO_ONLY —— 以下为 S0D 原型的真实运行输出（输入输出均为纯合成数据；接口 PROPOSED，"
                      "非 DeepBas 官方协议；不是水文预测）。",
           "generated_at_local": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "machine": platform.node(),
           "python": sys.version.split()[0], "python_executable": sys.executable,
           "server": "demo_server.start_in_thread on 127.0.0.1:<free port>",
           "http_examples": http_out, "cli_examples": cli_out}
    with open(os.path.join(ROOT, "io_examples.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    lines = ["# S0D 输入输出示例摘要（SYNTHETIC_DEMO_ONLY；PROPOSED）", "",
             "由 `tools/gen_io_examples.py` 于 %s 在 %s（Python %s）实际运行生成；完整响应见 `io_examples.json`。"
             % (doc["generated_at_local"], doc["machine"], doc["python"]), "",
             "| 场景 | 请求 | HTTP | s0d_status | error.alias / code | prediction |", "|---|---|---|---|---|---|"]
    for x in http_out:
        r = x["response"]
        err = r.get("error") or {}
        lines.append("| %s | `%s %s` | %d | %s | %s | %s |" % (
            x["scenario"], x["request"]["method"], x["request"]["url"], x["http_status"], r.get("s0d_status"),
            ("%s / %s" % (err.get("alias"), err.get("code"))) if err else "-", json.dumps(r.get("prediction"))))
    lines += ["", "| CLI 命令 | 退出码 | s0d_status | prediction |", "|---|---|---|---|"]
    for c in cli_out:
        lines.append("| `%s` | %d | %s | %s |" % (c["command"], c["exit_code"], c["stdout_json"].get("s0d_status"),
                                                  json.dumps(c["stdout_json"].get("prediction"))))
    with open(os.path.join(ROOT, "io_examples.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("http_examples=%d cli_examples=%d" % (len(http_out), len(cli_out)))


if __name__ == "__main__":
    main()
