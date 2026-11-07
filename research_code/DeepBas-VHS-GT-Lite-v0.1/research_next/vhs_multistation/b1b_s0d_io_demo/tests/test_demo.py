# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 自动测试（unittest，纯标准库，纯合成数据）。
运行：set PYTHONDONTWRITEBYTECODE=1 && python -B tests/test_demo.py
覆盖任务书第五节 1–17 项 + HTTP 集成测试。不读取任何真实数据；网络访问被运行期拦截，只允许 127.0.0.1。
R1 修改（逐项原因见 interface_decisions.md §4「被修改的旧测试」）：
  M1 T11.test_rejected_even_when_invalid —— D6：无效/不存在站点的预测请求改为 400/404，且不再声明 prediction_authorized；
  M2 T13.test_demo_markers —— D3：science_stage 不再承载操作类型（demo 也为 METADATA_ONLY，operation=SYNTHETIC_DEMO）；
  M3 THTTP.test_predict_http —— D6：JSON 解析错误的 400 响应不再声明 prediction_authorized；
  M4 T16.PRODUCT —— 新增 geo_map.js、tools/gen_io_examples_r1.py 纳入静态扫描（只增不减）。
所有安全断言（prediction 恒 null、无 Q/指标字段、只连 127.0.0.1、旧文件不变）均保留，未放宽。
"""
import copy
import io
import json
import logging
import math
import os
import re
import socket
import sys
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stdout

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VM = os.path.dirname(ROOT)
OLD = os.path.join(VM, "b1b_s0_deepbas_mvp")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

# ---------------- 运行期网络守卫：只允许连接 127.0.0.1（在导入被测模块之前安装）
EXTERNAL_ATTEMPTS = []
INTENTIONAL_PROBES = []
_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_getaddrinfo = socket.getaddrinfo
_orig_create_connection = socket.create_connection
_PROBE = {"on": False}


def _host_ok(addr):
    host = addr[0] if isinstance(addr, tuple) else addr
    return host in ("127.0.0.1",)


def _guard_connect(self, addr):
    if not _host_ok(addr):
        (INTENTIONAL_PROBES if _PROBE["on"] else EXTERNAL_ATTEMPTS).append(repr(addr))
        raise PermissionError("S0D test guard: non-127.0.0.1 connection refused: %r" % (addr,))
    return _orig_connect(self, addr)


def _guard_connect_ex(self, addr):
    if not _host_ok(addr):
        (INTENTIONAL_PROBES if _PROBE["on"] else EXTERNAL_ATTEMPTS).append(repr(addr))
        raise PermissionError("S0D test guard")
    return _orig_connect_ex(self, addr)


def _guard_getaddrinfo(host, *a, **k):
    if host not in ("127.0.0.1", None):
        (INTENTIONAL_PROBES if _PROBE["on"] else EXTERNAL_ATTEMPTS).append("getaddrinfo:%r" % (host,))
        raise PermissionError("S0D test guard: name resolution refused: %r" % (host,))
    return _orig_getaddrinfo(host, *a, **k)


socket.socket.connect = _guard_connect
socket.socket.connect_ex = _guard_connect_ex
socket.getaddrinfo = _guard_getaddrinfo

import demo_cli          # noqa: E402
import demo_core as core  # noqa: E402
import demo_data as dd    # noqa: E402
import demo_server        # noqa: E402
import integrity_snapshot as isnap  # noqa: E402
import mini_schema        # noqa: E402
vc = core.vc

with open(os.path.join(OLD, "vhs_response.schema.json"), encoding="utf-8") as _fh:
    OLD_SCHEMA = json.load(_fh)

LOG_LINES = []


class _Cap(logging.Handler):
    def emit(self, record):
        LOG_LINES.append(record.getMessage())


logging.getLogger("vhs_s0d").addHandler(_Cap())
logging.getLogger("vhs_s0d").setLevel(logging.INFO)

ALL_RESPONSES = []   # (来源, http_status, response) —— 供第 12/14/15 项遍历
RESTRICTED_TEXT = re.compile(r"(?i)\b(nse|kge|rmse|qobs|q_obs|observed_q|target_q)\b")


def H(fn, params):
    st, r = core.handle(fn, params)
    ALL_RESPONSES.append(("core:%s" % fn, st, r))
    return st, r


def P(body):
    st, r = core.handle_predict(body)
    ALL_RESPONSES.append(("core:predict", st, r))
    return st, r


def net_of(sid):
    return H("network", {"station_id": sid})[1]["s0d"]["network"]


def ids(lst):
    return {x["station_id"] for x in lst}


class T01_LegalStation(unittest.TestCase):
    def test_station_target_a(self):
        st, r = H("station", {"station_id": "DEMO_TARGET_A"})
        self.assertEqual(st, 200)
        self.assertEqual(r["target_station_id"], "DEMO_TARGET_A")
        crs = r["coordinate_reference_system"]
        self.assertEqual((crs["epsg"], crs["units"]), (4326, "degree"))
        self.assertEqual(crs["coordinate_axis_order_in_payload"], ["latitude", "longitude"])
        s = r["s0d"]["station"]
        for k in ("crs", "basin", "data_source", "admission"):
            self.assertIn(k, s)
        self.assertEqual(s["admission"]["status"], "BLOCKED")
        self.assertTrue(s["admission"]["blocking_reasons"])
        self.assertFalse(s["data_source"]["real_data_used"])
        self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED")
        self.assertIsNone(r["prediction"])

    def test_dataset_explicit_ok(self):
        st, r = H("station", {"station_id": "DEMO_TARGET_A", "dataset_id": dd.DATASET_ID,
                              "dataset_version": dd.DATASET_VERSION})
        self.assertEqual(st, 200)


class T02_UnknownStation(unittest.TestCase):
    def test_unknown_station_all_functions(self):
        for fn in ("station", "network", "audit"):
            st, r = H(fn, {"station_id": "DEMO_NOT_EXIST"})
            self.assertEqual((st, r["error"]["alias"], r["error"]["code"]), (404, "UNKNOWN_STATION", "VHS-E002"))
            self.assertIsNone(r["prediction"])
        st, r = H("demo", {"station_id": "DEMO_NOT_EXIST", "start": "2020-01-01", "end": "2020-01-02"})
        self.assertEqual(r["error"]["alias"], "UNKNOWN_STATION")


class T03_MissingOrInvalidInput(unittest.TestCase):
    def test_missing_station(self):
        for params in ({}, {"station_id": ""}, {"station_id": "   "}):
            st, r = H("station", params)
            self.assertEqual((st, r["error"]["alias"], r["error"]["code"]), (400, "INVALID_REQUEST", "VHS-E001"))

    def test_invalid_format(self):
        for bad in ("../../etc", "a b", "x" * 65, "DEMO;DROP"):
            st, r = H("station", {"station_id": bad})
            self.assertEqual((r["error"]["alias"], r["error"]["code"]), ("INVALID_REQUEST", "VHS-E003"), bad)

    def test_unknown_param_and_dataset(self):
        st, r = H("station", {"station_id": "DEMO_TARGET_A", "mode": "real"})
        self.assertEqual((r["error"]["alias"], r["error"]["reason_code"]), ("INVALID_REQUEST", "UNKNOWN_PARAMETER"))
        st, r = H("station", {"station_id": "DEMO_TARGET_A", "dataset_version": "9.9"})
        self.assertEqual((st, r["error"]["alias"], r["error"]["code"]), (404, "UNKNOWN_DATASET", "VHS-E004"))

    def test_demo_missing_dates(self):
        st, r = H("demo", {"station_id": "DEMO_TARGET_A"})
        self.assertEqual(r["error"]["reason_code"], "TIME_RANGE_MISSING")


class T04_TimeRange(unittest.TestCase):
    CASES = [("2020-01-10", "2020-01-01", "TIME_RANGE_START_AFTER_END"),
             ("2020/01/01", "2020-01-05", "TIME_FORMAT_INVALID"),
             ("2020-02-30", "2020-03-01", "TIME_FORMAT_INVALID"),
             ("20200101", "2020-01-05", "TIME_FORMAT_INVALID"),
             ("2019-12-31", "2020-01-05", "TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW"),
             ("2020-12-01", "2021-01-02", "TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW"),
             ("2020-01-01", "2020-06-30", "TIME_RANGE_TOO_LONG")]

    def test_bad_ranges(self):
        for s, e, code in self.CASES:
            st, r = H("demo", {"station_id": "DEMO_TARGET_A", "start": s, "end": e})
            self.assertEqual((st, r["error"]["alias"], r["error"]["code"], r["error"]["reason_code"]),
                             (400, "INVALID_REQUEST", "VHS-E011", code), (s, e))

    def test_boundary_ok(self):
        st, r = H("demo", {"station_id": "DEMO_TARGET_A", "start": "2020-01-01", "end": "2020-04-01"})
        self.assertEqual(st, 200)
        self.assertEqual(len(r["synthetic_display_data"]["values"]), 92)


class T05_DirectedPathSearch(unittest.TestCase):
    def test_upstream_set_and_paths(self):
        n = net_of("DEMO_TARGET_A")
        self.assertEqual(ids(n["upstream_nodes"]), {"DEMO_MID_1", "DEMO_HEAD_1", "DEMO_TRIB_1", "DEMO_TRIB_2",
                                                    "DEMO_TRIB_T", "DEMO_CANAL_SRC"})
        up = {u["station_id"]: u for u in n["upstream_nodes"]}
        self.assertEqual(up["DEMO_TRIB_2"]["path_edge_ids"], ["E02", "E03", "E04"])
        self.assertEqual(up["DEMO_TRIB_2"]["path_nodes"],
                         ["DEMO_TRIB_2", "DEMO_TRIB_1", "DEMO_MID_1", "DEMO_TARGET_A"])
        self.assertEqual(up["DEMO_TRIB_2"]["relation_status"]["status"], "CONDITIONAL")
        self.assertEqual(up["DEMO_CANAL_SRC"]["relation_status"]["status"], "CONDITIONAL")
        self.assertIn("ARTIFICIAL_TRANSFER", up["DEMO_CANAL_SRC"]["path_flags"])
        self.assertEqual(up["DEMO_HEAD_1"]["relation_status"]["status"], "PASS")
        for u in n["upstream_nodes"]:   # 每条路径边首尾相接、沿流向终止于目标
            es = u["path_edges"]
            self.assertEqual(es[0]["from"], u["station_id"])
            self.assertEqual(es[-1]["to"], "DEMO_TARGET_A")
            for a, b in zip(es, es[1:]):
                self.assertEqual(a["to"], b["from"])
        self.assertEqual(n["connection_status"], "HAS_UPSTREAM")
        self.assertEqual(core.check_network_invariants(n), [])
        self.assertFalse(n["method"]["uses_coordinates_for_relations"])

    def test_direction_cannot_be_reversed(self):
        n = net_of("DEMO_TARGET_A")
        self.assertEqual(ids(n["downstream_nodes"]), {"DEMO_DOWN_1", "DEMO_OUTLET"})
        self.assertFalse(ids(n["downstream_nodes"]) & ids(n["upstream_nodes"]))
        down = net_of("DEMO_DOWN_1")
        self.assertIn("DEMO_TARGET_A", ids(down["upstream_nodes"]))
        self.assertIn("DEMO_TRIB_DS", ids(down["upstream_nodes"]))
        self.assertEqual(net_of("DEMO_HEAD_1")["upstream_nodes"], [])
        g = copy.deepcopy(dd.MAIN_GRAPH)   # 反转所有边：原上游必须全部变为下游
        for e in g["edges"]:
            e["from"], e["to"] = e["to"], e["from"]
        rev = core.analyze_network(g, "DEMO_TARGET_A")
        self.assertEqual(ids(rev["upstream_nodes"]), {"DEMO_DOWN_1", "DEMO_OUTLET"})
        self.assertEqual(ids(rev["downstream_nodes"]), ids(n["upstream_nodes"]))

    def test_not_fixed_json_custom_graph(self):
        g = {"graph_id": "T", "nodes": [{"id": i} for i in ("A", "B", "C", "D")],
             "edges": [{"id": "1", "from": "A", "to": "B", "snap_status": "CERTIFIED"},
                       {"id": "2", "from": "B", "to": "C", "snap_status": "CERTIFIED"},
                       {"id": "3", "from": "D", "to": "C", "snap_status": "CERTIFIED"}]}
        self.assertEqual(ids(core.analyze_network(g, "C")["upstream_nodes"]), {"A", "B", "D"})
        self.assertEqual(ids(core.analyze_network(g, "B")["upstream_nodes"]), {"A"})
        self.assertEqual(ids(core.analyze_network(g, "B")["same_system_not_upstream"]), {"D"})


class T06_NonconnectedControls(unittest.TestCase):
    def test_controls_only_from_other_components(self):
        n = net_of("DEMO_TARGET_A")
        self.assertEqual(ids(n["nonconnected_control_candidates"]), {"DEMO_CTRL_1", "DEMO_CTRL_2", "DEMO_CTRL_NEAR"})
        self.assertFalse(ids(n["nonconnected_control_candidates"]) & ids(n["upstream_nodes"]))

    def test_geographic_nearest_is_not_upstream(self):
        tgt = dd.STATIONS["DEMO_TARGET_A"]["coordinates_lat_lon"]
        dist = {s: math.hypot(v["coordinates_lat_lon"][0] - tgt[0], v["coordinates_lat_lon"][1] - tgt[1])
                for s, v in dd.STATIONS.items() if s != "DEMO_TARGET_A" and v["graph_id"] == "SYNTHETIC_MAIN_GRAPH"}
        nearest = min(dist, key=dist.get)
        self.assertEqual(nearest, "DEMO_CTRL_NEAR")
        n = net_of("DEMO_TARGET_A")
        self.assertNotIn(nearest, ids(n["upstream_nodes"]))
        self.assertIn(nearest, ids(n["nonconnected_control_candidates"]))

    def test_adding_edge_changes_relation(self):
        g = copy.deepcopy(dd.MAIN_GRAPH)
        g["edges"].append({"id": "X1", "from": "DEMO_CTRL_NEAR", "to": "DEMO_TARGET_A", "kind": "natural",
                           "snap_status": "CERTIFIED"})
        n = core.analyze_network(g, "DEMO_TARGET_A")
        self.assertIn("DEMO_CTRL_NEAR", ids(n["upstream_nodes"]))
        self.assertNotIn("DEMO_CTRL_NEAR", ids(n["nonconnected_control_candidates"]))


class T07_TributaryClassification(unittest.TestCase):
    def test_tributaries(self):
        n = net_of("DEMO_TARGET_A")
        up, ctrl = ids(n["upstream_nodes"]), ids(n["nonconnected_control_candidates"])
        same = ids(n["same_system_not_upstream"])
        for t in ("DEMO_TRIB_T", "DEMO_TRIB_1", "DEMO_TRIB_2"):
            self.assertIn(t, up)
            self.assertNotIn(t, ctrl)
            self.assertNotIn(t, same)
        self.assertIn("DEMO_TRIB_DS", same)          # 下游汇入的支流：同水系，非上游、非对照
        self.assertNotIn("DEMO_TRIB_DS", ctrl)
        self.assertIn("DEMO_CANAL_BASIN_OUT", same)  # 经人工输水相连：不可当独立对照
        self.assertNotIn("DEMO_CANAL_BASIN_OUT", ctrl)
        self.assertEqual(n["display_roles"]["DEMO_TRIB_T"], "UPSTREAM_PASS")


class T08_CycleHandling(unittest.TestCase):
    def test_cycle_graph(self):
        n = net_of("DEMO_CYCLE_X")
        self.assertEqual(n["connection_status"], "CYCLE_DETECTED")
        self.assertEqual(n["topology"]["status"], "BLOCKED")
        self.assertTrue(n["cycles"])
        self.assertEqual(set(n["cycles"][0]), {"DEMO_CYCLE_X", "DEMO_CYCLE_Y", "DEMO_CYCLE_Z"})
        self.assertIn("DEMO_CYCLE_W", ids(n["upstream_nodes"]))
        self.assertTrue(all(u["relation_status"]["status"] == "BLOCKED" for u in n["upstream_nodes"]))
        st, a = H("audit", {"station_id": "DEMO_CYCLE_X"})
        self.assertEqual(a["s0d"]["audit"]["science_admission"]["status"], "BLOCKED")

    def test_self_loop_and_bad_graph(self):
        g = {"nodes": [{"id": "A"}, {"id": "B"}], "edges": [{"id": "s", "from": "A", "to": "A"},
                                                             {"id": "t", "from": "A", "to": "B"}]}
        self.assertEqual(core.analyze_network(g, "B")["connection_status"], "CYCLE_DETECTED")
        with self.assertRaises(core.GraphInputError):
            core.analyze_network({"nodes": [{"id": "A"}], "edges": [{"id": "e", "from": "A", "to": "Z"}]}, "A")
        with self.assertRaises(core.GraphInputError):
            core.analyze_network({"nodes": [{"id": "A"}, {"id": "A"}], "edges": []}, "A")
        self.assertEqual(core.analyze_network(g, "Q")["connection_status"], "NOT_IN_NETWORK")

    def test_cli_custom_cycle_graph(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = demo_cli.main(["network", "DEMO_CYCLE_X", "--graph",
                                os.path.join(ROOT, "synthetic_data", "cycle_graph.json")])
        out = json.loads(buf.getvalue())
        self.assertEqual((rc, out["connection_status"], out["prediction"]), (0, "CYCLE_DETECTED", None))


class T09_T10_Audit(unittest.TestCase):
    def aud(self, sid):
        return H("audit", {"station_id": sid})[1]["s0d"]["audit"]

    def test_missing_qc(self):
        a = self.aud("DEMO_QC_MISSING")
        self.assertEqual((a["metadata_display"]["status"], a["science_admission"]["status"]), ("CONDITIONAL", "UNKNOWN"))
        st, r = H("station", {"station_id": "DEMO_QC_MISSING"})
        self.assertEqual(st, 200)

    def test_license_unknown_never_pass(self):
        a = self.aud("DEMO_QC_LICENSE_UNKNOWN")
        self.assertEqual(a["science_admission"]["status"], "UNKNOWN")
        for sid, rec in dd.STATIONS.items():
            if rec["license_status"] != "PERMITTED":
                self.assertNotEqual(self.aud(sid)["science_admission"]["status"], "PASS", sid)

    def test_other_rule_scenarios(self):
        self.assertEqual(self.aud("DEMO_QC_SNAP_UNCERT")["science_admission"]["status"], "CONDITIONAL")
        g = self.aud("DEMO_QC_GAPS")
        self.assertEqual((g["metadata_display"]["status"], g["science_admission"]["status"]), ("PASS", "CONDITIONAL"))
        t = self.aud("DEMO_TARGET_A")
        self.assertEqual(t["science_admission"]["status"], "BLOCKED")
        self.assertTrue(any(x.startswith("R06_TARGET_Q_ACCESS") for x in t["science_admission"]["reasons"]))
        u = self.aud("DEMO_QC_UNKNOWN_FIELDS")
        self.assertEqual(u["science_admission"]["status"], "UNKNOWN")
        r7 = [x for x in u["rules"] if x["rule_id"] == "R07_UNKNOWN_QC_FIELDS"][0]
        self.assertEqual(r7["unknown_field_names"], ["legacy_code", "vendor_flag_x"])
        ideal = self.aud("DEMO_QC_IDEAL")
        self.assertEqual(ideal["science_admission"]["status"], "PASS")
        self.assertEqual(ideal["prediction_authorization"]["status"], "NOT_AUTHORIZED")
        self.assertTrue(all("SYNTHETIC" in x["label"] for x in ideal["rules"]))

    def test_unregistered_value_is_unknown(self):
        rec = dict(dd.STATIONS["DEMO_QC_IDEAL"], license_status="MAYBE")
        a = core.audit_station(rec, core.analyze_network(dd.AUDIT_GRAPH, "DEMO_QC_IDEAL"))
        self.assertEqual(a["science_admission"]["status"], "UNKNOWN")


class T11_PredictRejected(unittest.TestCase):
    BODIES = [{"target_station_id": "DEMO_TARGET_A"},
              {"target_station_id": "DEMO_TARGET_A", "mode": "hindcast"},
              {"target_station_id": "DEMO_TARGET_A", "mode": "REALTIME_FORECAST", "model": "xxx"},
              {"target_station_id": "DEMO_TARGET_A", "authorized": True, "force": True, "override": "yes"},
              {"station_id": "DEMO_QC_IDEAL", "start": "2020-01-01", "end": "2020-01-10"},
              {"target_station_id": "DEMO_HEAD_1", "model_id": "SYNTHETIC_DEMO_MODEL", "token": "x", "admin": 1},
              {"target_station_id": "DEMO_TARGET_A", "prediction_authorized": {"status": "PASS"},
               "science_stage": "INDEPENDENTLY_VALIDATED", "data_class": "VALIDATED_PRODUCT_FUTURE"},
              {"target_station_id": "DEMO_TARGET_A", "prediction": {"values": [1, 2]}, "qobs": [1.0],
               "nse": 0.9, "unrelated": {"deep": [1, 2, 3]}}]

    def test_all_rejected(self):
        for b in self.BODIES:
            st, r = P(b)
            self.assertEqual(st, 403, b)
            self.assertEqual(r["s0d_status"], "NOT_AUTHORIZED")
            self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED")
            self.assertIsNone(r["prediction"])
            self.assertNotIn("synthetic_display_data", r)
        st, r = P(self.BODIES[3])
        self.assertEqual(r["s0d"]["predict"]["override_attempts_ignored"], ["authorized", "force", "override"])
        st, r = P(self.BODIES[-1])
        self.assertEqual(r["s0d"]["predict"]["received_field_hidden_count"], 2)   # qobs、nse 键名不回显

    def test_rejected_even_when_invalid(self):
        # R1/D6（M1）：错误类型与 HTTP 状态一一对应；错误响应不声明 prediction_authorized，prediction 仍为 null
        cases = [({"target_station_id": "DEMO_NOT_EXIST", "authorized": True}, 404, "UNKNOWN_STATION"),
                 ({}, 400, "INVALID_REQUEST"), ([1, 2], 400, "INVALID_REQUEST"), ("x", 400, "INVALID_REQUEST"),
                 ({"target_station_id": "../x"}, 400, "INVALID_REQUEST")]
        for b, code, alias in cases:
            st, r = P(b)
            self.assertEqual((st, r["response_type"], r["error"]["alias"], r["s0d_status"]),
                             (code, "error", alias, alias), b)
            self.assertNotIn("prediction_authorized", r, b)
            self.assertIs(r["prediction_authorization_evaluated"], False)
            self.assertIsNone(r["prediction"])

    def test_cli_predict(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = demo_cli.main(["predict", "DEMO_TARGET_A", "--mode", "hindcast", "--model", "xxx",
                                "--extra", "authorized=true", "--extra", "force=1"])
        out = json.loads(buf.getvalue())
        self.assertEqual((rc, out["s0d_status"], out["prediction"]), (3, "NOT_AUTHORIZED", None))


class T13_SyntheticMarkers(unittest.TestCase):
    def test_demo_markers(self):
        st, r = H("demo", {"station_id": "DEMO_TARGET_A", "start": "2020-01-01", "end": "2020-01-14"})
        sdd = r["synthetic_display_data"]
        self.assertEqual(sdd["data_class"], "SYNTHETIC_DEMO_ONLY")
        self.assertIn("SYNTHETIC_DEMO_ONLY", sdd["banner"])
        self.assertEqual(sdd["unit"], "SYN_UNIT")
        self.assertFalse(sdd["is_prediction"])
        self.assertEqual(len(sdd["values"]), 14)
        self.assertIsNone(r["prediction"])
        self.assertEqual((r["science_stage"], r["operation"], r["data_mode"]),    # R1/D3（M2）
                         ("METADATA_ONLY", "SYNTHETIC_DEMO", "SYNTHETIC"))
        st2, r2 = H("demo", {"station_id": "DEMO_TARGET_A", "start": "2020-01-05", "end": "2020-01-14"})
        self.assertEqual(r2["synthetic_display_data"]["values"], sdd["values"][4:])   # 确定性、与起点无关

    def test_every_response_marked(self):
        for src, st, r in ALL_RESPONSES:
            self.assertEqual(r.get("data_class"), "SYNTHETIC_DEMO_ONLY", src)
            self.assertEqual(r.get("protocol_status"), "PROPOSED_NOT_DEEPBAS_OFFICIAL", src)

    def test_offline_snapshot_marked(self):
        with open(os.path.join(ROOT, "offline_snapshot.js"), encoding="utf-8") as fh:
            js = fh.read()
        self.assertTrue(js.startswith("/* SYNTHETIC_DEMO_ONLY"))
        payload = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
        self.assertEqual(payload["data_class"], "SYNTHETIC_DEMO_ONLY")
        for key, (st, r) in payload["responses"].items():
            self.assertIsNone(r["prediction"], key)


class T16_StaticScan(unittest.TestCase):
    PRODUCT = ["demo_core.py", "demo_data.py", "demo_server.py", "demo_cli.py", "index.html", "app.js",
               "offline_snapshot.js", "tools/build_artifacts.py", "tools/gen_io_examples.py",
               "geo_map.js", "tools/gen_io_examples_r1.py"]   # R1（M4）：只增不减
    BANNED = [re.compile(p, re.I) for p in (r"sealed_runoff", r"quarantine", r"https?://(?!127\.0\.0\.1)",
                                             r"0\.0\.0\.0", r"\burlopen\(", r"\bhttp\.client\b", r"\brequests\b",
                                             r"//cdn", r"fonts\.googleapis", r"\bimport\s+socket\b")]
    ALLOWED_LITERALS = ['"http://www.w3.org/2000/svg"']   # SVG XML 命名空间标识，不是网络请求

    def test_product_code_clean(self):
        for rel in self.PRODUCT:
            p = os.path.join(ROOT, rel)
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as fh:
                text = fh.read()
            for lit in self.ALLOWED_LITERALS:
                text = text.replace(lit, '""')
            for rx in self.BANNED:
                if rel in ("tools/gen_io_examples.py", "tools/gen_io_examples_r1.py") and \
                        rx.pattern.startswith(r"\burlopen"):
                    continue   # 该工具用 urllib 访问本机 127.0.0.1 服务录制示例（见下一断言）
                self.assertIsNone(rx.search(text), "%s matched %s" % (rel, rx.pattern))
        for tool in ("gen_io_examples.py", "gen_io_examples_r1.py"):
            with open(os.path.join(ROOT, "tools", tool), encoding="utf-8") as fh:
                g = fh.read()
            self.assertNotIn("0.0.0.0", g)
            self.assertEqual(set(re.findall(r"https?://([^/:\"']+)", g)), {"127.0.0.1"})

    def test_snapshot_tool_only_prunes(self):
        with open(os.path.join(ROOT, "tools", "integrity_snapshot.py"), encoding="utf-8") as fh:
            lines = [l for l in fh if "sealed_runoff" in l]
        self.assertEqual(len(lines), 1)
        self.assertIn("PRUNE_DIR_NAMES", lines[0])

    def test_html_no_external_refs(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        for m in re.finditer(r"""(?:src|href)\s*=\s*["']([^"']+)""", html):
            self.assertNotIn("//", m.group(1))
        self.assertNotIn("<link", html.lower())
        self.assertNotIn("@import", html)

    def test_runtime_guard_blocks_external(self):
        _PROBE["on"] = True
        try:
            s = socket.socket()
            with self.assertRaises(PermissionError):
                s.connect(("203.0.113.1", 80))   # TEST-NET-3，守卫在系统调用前拒绝
            s.close()
            with self.assertRaises(PermissionError):
                socket.getaddrinfo("example.invalid", 80)
        finally:
            _PROBE["on"] = False
        self.assertEqual(len(INTENTIONAL_PROBES), 2)


class T17_OldFilesUnchanged(unittest.TestCase):
    def test_against_baseline(self):
        with open(os.path.join(ROOT, "integrity", "baseline_pre.json"), encoding="utf-8") as fh:
            base = json.load(fh)
        now = isnap.snapshot(VM)
        cmp_ = isnap.compare(base, now)
        self.assertEqual(cmp_["added"], [])
        self.assertEqual(cmp_["removed"], [])
        self.assertEqual(cmp_["changed"], [])
        self.assertTrue(cmp_["pruned_dirs_equal"])
        self.assertEqual(now["summary"]["list_sha256"], base["summary"]["list_sha256"])
        old_files = [k for k in now["files"] if k.startswith("b1b_s0_deepbas_mvp/")]
        self.assertEqual(len(old_files), 12)
        self.assertFalse(os.path.exists(os.path.join(OLD, "__pycache__")))


class THTTP_Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv, cls.th, cls.port = demo_server.start_in_thread(0)
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.th.join(5)

    def req(self, path, method="GET", body=None, headers=None, raw=None):
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        r = urllib.request.Request(self.base + path, data=data, method=method, headers=headers or {})
        if data is not None and "Content-Type" not in (headers or {}):
            r.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(r, timeout=10) as resp:
                status, hdrs, payload = resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            status, hdrs, payload = e.code, dict(e.headers), e.read()
            e.close()
        ctype = hdrs.get("Content-Type", "")
        if ctype.startswith("application/json"):
            j = json.loads(payload.decode("utf-8"))
            ALL_RESPONSES.append(("http:%s %s" % (method, path), status, j))
            return status, hdrs, j
        return status, hdrs, payload

    def test_bound_loopback_only(self):
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")
        self.assertEqual(demo_server.BIND_HOST, "127.0.0.1")

    def test_static_and_traversal(self):
        st, h, body = self.req("/")
        self.assertEqual(st, 200)
        self.assertIn("text/html", h["Content-Type"])
        self.assertIn(b"SYNTHETIC_DEMO_ONLY", body)
        self.assertIn("default-src 'none'", h["Content-Security-Policy"])
        for p in ("/app.js", "/offline_snapshot.js", "/index.html"):
            self.assertEqual(self.req(p)[0], 200, p)
        for p in ("/../demo_core.py", "/%2e%2e/%2e%2e/demo_core.py", "/demo_core.py", "/index.html/../demo_server.py",
                  "/..%5c..%5cvhs_contract.py", "/integrity/baseline_pre.json", "/tests/test_demo.py",
                  "//etc/passwd", "/C:/Windows/win.ini"):
            st, h, j = self.req(p)
            self.assertEqual(st, 404, p)
            self.assertEqual(j["error"]["alias"], "ROUTE_NOT_FOUND")
        st, h, j = self.req("/api/vhs/stations/..%2F..%2Fdemo_core.py")
        self.assertEqual((st, j["error"]["code"]), (400, "VHS-E003"))

    def test_endpoints(self):
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A")
        self.assertEqual((st, j["target_station_id"], h["X-VHS-Protocol-Status"]),
                         (200, "DEMO_TARGET_A", "PROPOSED_NOT_DEEPBAS_OFFICIAL"))
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A/network")
        self.assertEqual(ids(j["s0d"]["network"]["upstream_nodes"]),
                         {"DEMO_MID_1", "DEMO_HEAD_1", "DEMO_TRIB_1", "DEMO_TRIB_2", "DEMO_TRIB_T", "DEMO_CANAL_SRC"})
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A/audit")
        self.assertEqual(j["s0d"]["audit"]["science_admission"]["status"], "BLOCKED")
        st, h, j = self.req("/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-14")
        self.assertEqual((st, j["synthetic_display_data"]["data_class"], j["prediction"]), (200, "SYNTHETIC_DEMO_ONLY", None))
        st, h, j = self.req("/api/vhs/stations/DEMO_NOT_EXIST")
        self.assertEqual((st, j["error"]["alias"]), (404, "UNKNOWN_STATION"))
        st, h, j = self.req("/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-09&end=2020-01-01")
        self.assertEqual((st, j["error"]["reason_code"]), (400, "TIME_RANGE_START_AFTER_END"))
        st, h, j = self.req("/api/vhs/synthetic-demo?station_id=A&station_id=B&start=2020-01-01&end=2020-01-02")
        self.assertEqual(j["error"]["reason_code"], "QUERY_INVALID")
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A?qobs=12.5")
        self.assertEqual(j["error"]["reason_code"], "UNKNOWN_PARAMETER")
        self.assertNotIn("qobs", json.dumps(j))
        st, h, j = self.req("/api/vhs/nothing")
        self.assertEqual(st, 404)

    def test_predict_http(self):
        for b in T11_PredictRejected.BODIES:
            st, h, j = self.req("/api/vhs/predict", "POST", b)
            self.assertEqual((st, j["s0d_status"], j["prediction"]), (403, "NOT_AUTHORIZED", None))
        st, h, j = self.req("/api/vhs/predict", "POST", raw=b"{not json")
        self.assertEqual((st, j["error"]["alias"], j["prediction"]), (400, "INVALID_REQUEST", None))   # R1/D6（M3）
        self.assertNotIn("prediction_authorized", j)
        st, h, j = self.req("/api/vhs/predict", "POST", raw=b'{"target_station_id": NaN}')
        self.assertEqual(j["error"]["reason_code"], "JSON_PARSE_ERROR")
        st, h, j = self.req("/api/vhs/predict", "POST", raw=b"x" * (demo_server.MAX_BODY_BYTES + 1))
        self.assertEqual((st, j["error"]["alias"]), (413, "REQUEST_TOO_LARGE"))
        st, h, j = self.req("/api/vhs/predict")
        self.assertEqual((st, j["error"]["alias"], j["prediction"]), (405, "METHOD_NOT_ALLOWED", None))
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A", "PUT", raw=b"{}")
        self.assertEqual(st, 405)
        st, h, j = self.req("/api/vhs/stations/DEMO_TARGET_A", "POST", {"a": 1})
        self.assertEqual(st, 405)


class TZZ_GlobalChecks(unittest.TestCase):
    """最后运行：遍历本次测试产生的全部响应（core + HTTP）。"""

    @classmethod
    def setUpClass(cls):
        for sid in dd.STATIONS:   # 补全：所有站点 × 所有功能
            for fn in ("station", "network", "audit"):
                H(fn, {"station_id": sid})
            H("demo", {"station_id": sid, "start": "2020-03-01", "end": "2020-03-07"})
            P({"target_station_id": sid, "mode": "hindcast"})

    def test_12_prediction_always_null(self):
        self.assertGreater(len(ALL_RESPONSES), 150)
        for src, st, r in ALL_RESPONSES:
            self.assertIn("prediction", r, src)
            self.assertIsNone(r["prediction"], src)
            if "prediction_authorized" in r:
                self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED", src)

    def test_14_old_contract_and_schema(self):
        for src, st, r in ALL_RESPONSES:
            self.assertEqual(vc.validate_response(r), [], src)
            self.assertEqual(mini_schema.validate(r, OLD_SCHEMA), [], src)
        self.assertEqual(core.OLD_CONTRACT_SHA256,
                         "38009ed258ca5f63bc9169917f5ab7cbe0310d9e644eeeac7708d576e163595b")

    def test_15_no_restricted_fields_in_responses_or_logs(self):
        for src, st, r in ALL_RESPONSES:
            self.assertEqual(vc.scan_forbidden_fields(r), [], src)
            self.assertIsNone(RESTRICTED_TEXT.search(json.dumps(r, ensure_ascii=False)), src)
        self.assertTrue(LOG_LINES)
        for line in LOG_LINES:
            self.assertTrue(vc.assert_log_safe(line))
            self.assertIsNone(RESTRICTED_TEXT.search(line), line)
        self.assertFalse(core.safe_log({"event": "x", "qobs": 1.0}))
        self.assertFalse(core.safe_log("debug nse 0.8"))
        self.assertIn('{"event": "log_record_blocked", "code": "VHS-E008"}', LOG_LINES)

    def test_16_no_external_connection_attempted(self):
        self.assertEqual(EXTERNAL_ATTEMPTS, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
