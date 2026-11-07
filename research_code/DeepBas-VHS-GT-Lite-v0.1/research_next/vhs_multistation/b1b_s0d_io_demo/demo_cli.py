# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 命令行演示（PROPOSED；SYNTHETIC_DEMO_ONLY；纯标准库）。

  python -B demo_cli.py station DEMO_TARGET_A
  python -B demo_cli.py network DEMO_TARGET_A [--graph synthetic_data/cycle_graph.json]
  python -B demo_cli.py audit   DEMO_TARGET_A
  python -B demo_cli.py demo    DEMO_TARGET_A --start 2020-01-01 --end 2020-01-14
  python -B demo_cli.py predict DEMO_TARGET_A [--mode hindcast --model xxx --extra authorized=true]
  python -B demo_cli.py list
退出码：0 正常；1 错误响应（如 UNKNOWN_STATION / INVALID_REQUEST）；3 NOT_AUTHORIZED（预测被拒绝）。
R1：predict 对不存在站点返回 UNKNOWN_STATION（退出码 1），对存在站点返回 NOT_AUTHORIZED（退出码 3）。
interface_status=PROPOSED：非 DeepBas 官方协议，未完成正式集成。
"""
import argparse
import json
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import demo_core as core  # noqa: E402
import demo_data as dd    # noqa: E402


def _print(obj):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, indent=1) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="VHS S0D 虚拟水文站 I/O 原型（SYNTHETIC_DEMO_ONLY；PROPOSED）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("station", "network", "audit", "demo", "predict"):
        p = sub.add_parser(name)
        p.add_argument("station_id")
        p.add_argument("--dataset-id", default=None)
        p.add_argument("--dataset-version", default=None)
        if name == "network":
            p.add_argument("--graph", default=None, help="自定义合成有向图 JSON（输出原始分析，不是契约信封）")
        if name in ("demo", "predict"):
            p.add_argument("--start", default=dd.DEFAULT_DEMO_RANGE[0] if name == "demo" else None)
            p.add_argument("--end", default=dd.DEFAULT_DEMO_RANGE[1] if name == "demo" else None)
        if name == "predict":
            p.add_argument("--mode", default=None)
            p.add_argument("--model", default=None)
            p.add_argument("--extra", action="append", default=[], help="附加请求字段 key=value（不会改变授权）")
    sub.add_parser("list")
    a = ap.parse_args(argv)
    if a.cmd == "list":
        _print({"data_class": core.DEMO_FLAG, "protocol_status": core.PROTOCOL_STATUS,
                "interface_status": core.INTERFACE_STATUS, "interface_notice": core.INTERFACE_NOTICE,
                "data_mode": core.DATA_MODE,
                "stations": [{"station_id": s["station_id"], "role": s["role"], "station_name": s["station_name"]}
                             for s in dd.STATION_LIST]})
        return 0
    params = {"station_id": a.station_id}
    if a.dataset_id is not None:
        params["dataset_id"] = a.dataset_id
    if a.dataset_version is not None:
        params["dataset_version"] = a.dataset_version
    if a.cmd == "network" and a.graph:
        with open(a.graph, encoding="utf-8") as fh:
            graph = json.load(fh)
        try:
            res = core.analyze_network(graph, a.station_id)
        except core.GraphInputError as exc:
            _print({"data_class": core.DEMO_FLAG, "interface_status": core.INTERFACE_STATUS,
                    "data_mode": core.DATA_MODE,
                    "error": {"alias": "INVALID_REQUEST", "code": "VHS-E011", "detail": str(exc)},
                    "prediction": None})
            return 1
        res["note"] = "自定义合成图的原始 F2 分析输出（非契约信封）；PROPOSED / SYNTHETIC_DEMO_ONLY"
        res["interface_status"], res["data_mode"] = core.INTERFACE_STATUS, core.DATA_MODE
        res["prediction"] = None
        _print(res)
        return 0
    if a.cmd == "predict":
        body = {"target_station_id": a.station_id}
        body.update({k: v for k, v in params.items() if k != "station_id"})
        for k in ("start", "end", "mode", "model"):
            if getattr(a, k) is not None:
                body[k] = getattr(a, k)
        for kv in a.extra:
            k, _, v = kv.partition("=")
            body[k] = v
        status, resp = core.handle_predict(body)
        _print(resp)
        return 3 if resp.get("s0d_status") == "NOT_AUTHORIZED" and resp.get("response_type") != "error" else 1
    if a.cmd == "demo":
        params["start"], params["end"] = a.start, a.end
    status, resp = core.handle(a.cmd, params)
    _print(resp)
    return 0 if resp.get("response_type") != "error" else 1


if __name__ == "__main__":
    sys.exit(main())
