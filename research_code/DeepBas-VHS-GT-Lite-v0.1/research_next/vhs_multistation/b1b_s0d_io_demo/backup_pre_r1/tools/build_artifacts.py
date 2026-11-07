# -*- coding: utf-8 -*-
"""生成 S0D 合成数据导出（synthetic_data/*.json）与离线预览快照（offline_snapshot.js）。
全部内容由 demo_data.py / demo_core.py 计算得到，SYNTHETIC_DEMO_ONLY；只写入本目录。
用法：python -B tools/build_artifacts.py
"""
import json
import os
import sys

sys.dont_write_bytecode = True
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import demo_core as core  # noqa: E402
import demo_data as dd    # noqa: E402

NOTICE = ("SYNTHETIC_DEMO_ONLY —— 由 demo_data.py 生成的纯合成数据（VHS-NEXT-B1B-S0D, PROPOSED）；"
          "不对应任何真实站点、河网或流量，不得作为科研结果。")


def _write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print("wrote", rel, len(text.encode("utf-8")))


def main():
    for name, g in (("main_graph.json", dd.MAIN_GRAPH), ("cycle_graph.json", dd.CYCLE_GRAPH),
                    ("audit_graph.json", dd.AUDIT_GRAPH)):
        _write(os.path.join("synthetic_data", name),
               json.dumps(dict({"_notice": NOTICE}, **g), ensure_ascii=False, indent=1) + "\n")
    _write(os.path.join("synthetic_data", "stations.json"),
           json.dumps({"_notice": NOTICE, "dataset_id": dd.DATASET_ID, "dataset_version": dd.DATASET_VERSION,
                       "region_scope": dd.REGION_SCOPE, "stations": dd.STATION_LIST},
                      ensure_ascii=False, indent=1) + "\n")
    snap = core.offline_snapshot()
    js = ("/* " + NOTICE + " 离线预览快照：由 tools/build_artifacts.py 调用 demo_core 生成；"
          "页面无法连接 127.0.0.1 服务时使用。 */\n"
          "window.VHS_OFFLINE_SNAPSHOT = " + json.dumps(snap, ensure_ascii=False, separators=(",", ":")) + ";\n")
    _write("offline_snapshot.js", js)


if __name__ == "__main__":
    main()
