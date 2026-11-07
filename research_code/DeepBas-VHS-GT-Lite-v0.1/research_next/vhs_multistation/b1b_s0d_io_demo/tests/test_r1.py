# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D-R1 验收测试（unittest，纯标准库，纯合成数据）。
运行（同时跑旧 42 项 + R1 新增项，日志写到控制台）：
  set PYTHONDONTWRITEBYTECODE=1 && python -B tests/test_r1.py
测试编号与决策对应：R1-D1…R1-D8（interface_decisions.md D1–D8），R1-IN 非法输入，R1-PR 预测拒绝，
R1-REL 关系方向，R1-LOG 日志安全，R1-SEAL 不访问封存目录，R1-OLD 旧目录未修改，R1-ZZ 全局复核。
网络守卫沿用 test_demo（只允许 127.0.0.1）。不读取任何真实数据；不访问 sealed_runoff / quarantine。
"""
import builtins
import copy
import hashlib
import http.client
import io
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_demo as base   # noqa: E402  （安装网络守卫；共享 ALL_RESPONSES / LOG_LINES / H / P）

ROOT, OLD, VM = base.ROOT, base.OLD, base.VM
core, dd, vc, mini_schema, demo_server, demo_cli = base.core, base.dd, base.vc, base.mini_schema, base.demo_server, \
    base.demo_cli
sys.path.insert(0, os.path.join(ROOT, "tools"))
import integrity_snapshot_r1 as isr1   # noqa: E402
import axis_ref                         # noqa: E402

H, P, ALL = base.H, base.P, base.ALL_RESPONSES
with open(os.path.join(ROOT, "schema_draft", "vhs_response_v0.2.draft.schema.json"), encoding="utf-8") as _fh:
    DRAFT = json.load(_fh)
with open(os.path.join(ROOT, "schema_draft", "error_codes_v0.2.draft.json"), encoding="utf-8") as _fh:
    DRAFT_CODES = json.load(_fh)
with open(os.path.join(HERE, "fixtures", "axis_cases.json"), encoding="utf-8") as _fh:
    AXIS = json.load(_fh)
OLD_SHA = {"vhs_contract.py": "38009ed258ca5f63bc9169917f5ab7cbe0310d9e644eeeac7708d576e163595b",
           "vhs_response.schema.json": "4e21e4d1b1c3a13eed05b248bb8dc61680ecf15744db2ec39180905590fa1158"}
LEGACY_CODES = {"VHS-E001": "STATION_ID_MISSING", "VHS-E002": "STATION_NOT_FOUND",
                "VHS-E003": "STATION_ID_INVALID_FORMAT", "VHS-E004": "DATASET_OR_VERSION_MISMATCH",
                "VHS-E005": "CRS_MISSING", "VHS-E006": "CRS_INVALID", "VHS-E007": "CRS_AREA_OF_USE_MISMATCH",
                "VHS-E008": "SEALED_TARGET_Q_LEAK_BLOCKED", "VHS-E009": "FORBIDDEN_SKILL_METRIC_FIELD",
                "VHS-E010": "PREDICTION_NOT_AUTHORIZED_BUT_PRESENT", "VHS-E011": "SCHEMA_VIOLATION",
                "VHS-E012": "UNSUPPORTED_API_VERSION"}
NOT_OFFICIAL = "非 DeepBas 官方协议，未完成正式集成"
HTTP_LOG = []   # (method, path, status, headers, json)


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


class _Srv(unittest.TestCase):
    """每个子类启动一个只绑 127.0.0.1 的线程服务；用 http.client 精确控制请求头。"""

    @classmethod
    def setUpClass(cls):
        cls.srv, cls.th, cls.port = demo_server.start_in_thread(0)

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.th.join(5)

    def call(self, method, path, body=None, raw=None, ctype="application/json", headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        data = raw if raw is not None else (json.dumps(body).encode("utf-8") if body is not None else None)
        hdr = dict(headers or {})
        if data is not None and ctype is not None:
            hdr["Content-Type"] = ctype
        try:
            conn.request(method, path, body=data, headers=hdr)
            r = conn.getresponse()
            status, rh, payload = r.status, dict(r.getheaders()), r.read()
        finally:
            conn.close()
        j = json.loads(payload.decode("utf-8")) if rh.get("Content-Type", "").startswith("application/json") else None
        if j is not None:
            ALL.append(("http-r1:%s %s" % (method, path[:80]), status, j))
            HTTP_LOG.append((method, path, status, rh, j))
        return status, rh, j


# ------------------------------------------------------------------ D1 schema 兼容
class R1_D1_SchemaCompat(unittest.TestCase):
    def test_D1_01_old_contract_files_untouched(self):
        for name, h in OLD_SHA.items():
            self.assertEqual(sha(os.path.join(OLD, name)), h, name)
        self.assertEqual(vc.ERROR_CODES, LEGACY_CODES)
        self.assertEqual(vc.API_VERSION, "vhs-contract-0.1.0-draft")

    def test_D1_02_draft_is_versioned_extension(self):
        self.assertEqual(DRAFT["$id"], "urn:deepbas:vhs:contract:0.2.0-draft-s0d-r1")
        self.assertEqual(DRAFT["x-status"], "DRAFT_PROPOSED_NOT_ACTIVE")
        self.assertIs(DRAFT["x-base-contract"]["modified"], False)
        rel = DRAFT["$defs"]["relation_v02"]["properties"]["relation"]["enum"]
        for x in ("CONNECTED_UPSTREAM", "NONCONNECTED_CONTROL", "CONNECTED_DOWNSTREAM", "SAME_SYSTEM_NOT_UPSTREAM"):
            self.assertIn(x, rel)
        self.assertEqual(DRAFT["$defs"]["relation_old_compatible"]["properties"]["relation"]["enum"],
                         ["CONNECTED_UPSTREAM", "NONCONNECTED_CONTROL"])
        self.assertNotIn("SYNTHETIC", DRAFT["$defs"]["evidence_level"]["enum"])   # 用 data_mode 表达，不混淆
        for k in ("admission_status", "control_status", "river_network_ref", "data_mode", "operation",
                  "interface_status", "certification_status"):
            self.assertIn(k, DRAFT["$defs"]["status_response_v02"]["required"])
        self.assertEqual(sorted(DRAFT_CODES["legacy_codes_retained"]), sorted(LEGACY_CODES))

    def test_D1_03_old_fields_not_broken(self):
        st, r = H("station", {"station_id": "DEMO_TARGET_A"})
        for k in vc.REQUIRED_TOP:
            self.assertIn(k, r)
        self.assertEqual(r["api_version"], vc.API_VERSION)
        for lst in ("upstream_donors", "nonconnected_controls"):
            for d in r[lst]:
                self.assertIn(d["relation"], ("CONNECTED_UPSTREAM", "NONCONNECTED_CONTROL"))
                self.assertIn(d["data_role"], vc.DATA_ROLES)
        st, e = H("station", {"station_id": "DEMO_NOT_EXIST"})
        self.assertEqual((e["error"]["code"], e["error"]["name"]), ("VHS-E002", LEGACY_CODES["VHS-E002"]))
        self.assertEqual(vc.validate_crs(r["coordinate_reference_system"], r["region_scope"]), [])

    def test_D1_04_draft_rejects_known_bad_shapes(self):
        st, demo = H("demo", {"station_id": "DEMO_QC_IDEAL", "start": "2020-01-01", "end": "2020-01-03"})
        self.assertEqual(mini_schema.validate(demo, DRAFT), [])
        bad = copy.deepcopy(demo)   # 旧示例 D 写法：合成 prediction 非空 + PASS
        bad["prediction_authorized"] = {"status": "PASS", "authorization_ref": "SYNTHETIC"}
        bad["science_stage"] = "SYNTHETIC_DEMO_ONLY"
        bad["prediction"] = {"data_class": "SYNTHETIC_DEMO_ONLY", "values": [1.0], "unit": "SYN_UNIT"}
        self.assertEqual(vc.validate_response(bad), [])          # 旧校验器允许（历史行为，记录为差异）
        self.assertNotEqual(mini_schema.validate(bad, DRAFT), [])  # v0.2 草案：废弃
        ok, out = core.finalize(bad, "demo", "T")                 # 原型出口闸门：拒绝
        self.assertFalse(ok)
        self.assertEqual(out["error"]["alias"], "INTERNAL_CONTRACT_VIOLATION")
        st, err = P({"target_station_id": "DEMO_NOT_EXIST"})
        self.assertEqual(mini_schema.validate(err, DRAFT), [])
        bad2 = dict(err, prediction_authorized={"status": "NOT_AUTHORIZED"})
        self.assertNotEqual(mini_schema.validate(bad2, DRAFT), [])
        st, s = H("station", {"station_id": "DEMO_TARGET_A"})
        for k in ("interface_status", "data_mode", "operation", "certification_status"):
            self.assertNotEqual(mini_schema.validate({x: y for x, y in s.items() if x != k}, DRAFT), [], k)
        mixed = copy.deepcopy(s)
        mixed["coordinate_reference_system"].update(epsg=3035, units="metre",
                                                    epsg_authority_axis_order=["northing", "easting"])
        self.assertNotEqual(mini_schema.validate(mixed, DRAFT), [])   # 3035 不得带 lat/lon 轴与 lon_lat


# ------------------------------------------------------------------ D2 prediction 恒 null
class R1_D2_PredictionAlwaysNull(_Srv):
    MODES = [{}, {"mode": "hindcast"}, {"mode": "REALTIME_FORECAST"}, {"mode": "RETROSPECTIVE_RECONSTRUCTION"},
             {"model": "xxx"}, {"model_id": "SYNTHETIC_DEMO_MODEL"}, {"authorized": True},
             {"start": "2020-01-01", "end": "2020-01-31"}]

    def _check(self, src, st, r):
        self.assertIn("prediction", r, src)
        self.assertIsNone(r["prediction"], src)
        if "synthetic_display_data" in r:
            self.assertEqual((st, r["operation"]), (200, "SYNTHETIC_DEMO"), src)
            self.assertFalse(r["synthetic_display_data"]["is_prediction"])

    def test_D2_01_core_all_stations_all_operations_all_modes(self):
        n = 0
        for sid in list(dd.STATIONS) + ["DEMO_NOT_EXIST", "", "../x"]:
            for fn in ("station", "network", "audit"):
                st, r = H(fn, {"station_id": sid})
                self._check(fn + sid, st, r)
                n += 1
            for rng in (("2020-01-01", "2020-01-02"), ("2020-06-01", "2020-08-31"), ("2020-02-01", "2020-01-01")):
                st, r = H("demo", {"station_id": sid, "start": rng[0], "end": rng[1]})
                self._check("demo" + sid, st, r)
                n += 1
            for m in self.MODES:
                st, r = P(dict({"target_station_id": sid}, **m))
                self._check("predict" + sid, st, r)
                self.assertNotIn("synthetic_display_data", r)
                n += 1
        self.assertGreater(n, 300)

    def test_D2_02_http_all_endpoints(self):
        for sid in ("DEMO_TARGET_A", "DEMO_QC_IDEAL", "DEMO_CYCLE_X", "DEMO_NOT_EXIST"):
            for path in ("/api/vhs/stations/%s" % sid, "/api/vhs/stations/%s/network" % sid,
                         "/api/vhs/stations/%s/audit" % sid,
                         "/api/vhs/synthetic-demo?station_id=%s&start=2020-01-01&end=2020-01-05" % sid):
                st, h, j = self.call("GET", path)
                self._check(path, st, j)
            for m in self.MODES:
                st, h, j = self.call("POST", "/api/vhs/predict", dict({"target_station_id": sid}, **m))
                self._check("POST predict " + sid, st, j)
                self.assertIn(st, (403, 404))
        st, h, j = self.call("GET", "/api/vhs/predict")
        self._check("GET predict", st, j)

    def test_D2_03_offline_snapshot_and_cli(self):
        js = read("offline_snapshot.js")
        payload = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
        self.assertEqual(payload["interface_status"], "PROPOSED")   # 证明快照已按 R1 重新生成
        for key, (st, r) in payload["responses"].items():
            self._check(key, st, r)
            self.assertEqual(r["interface_status"], "PROPOSED", key)
            self.assertEqual("synthetic_display_data" in r, key.startswith("demo|") and st == 200, key)
        for args in (["station", "DEMO_TARGET_A"], ["network", "DEMO_TARGET_A"], ["audit", "DEMO_TARGET_A"],
                     ["demo", "DEMO_TARGET_A"], ["predict", "DEMO_TARGET_A", "--mode", "hindcast"],
                     ["predict", "DEMO_NOT_EXIST"]):
            buf = io.StringIO()
            with redirect_stdout(buf):
                demo_cli.main(args)
            self.assertIsNone(json.loads(buf.getvalue())["prediction"], args)


# ------------------------------------------------------------------ D3 四字段分离
class R1_D3_FourFields(_Srv):
    def test_D3_01_operation_per_endpoint(self):
        exp = {"station": "STATION_LOOKUP", "network": "NETWORK_QUERY", "audit": "ADMISSION_AUDIT"}
        for fn, op in exp.items():
            st, r = H(fn, {"station_id": "DEMO_TARGET_A"})
            self.assertEqual((r["operation"], r["data_mode"], r["science_stage"]), (op, "SYNTHETIC", "METADATA_ONLY"))
            st, e = H(fn, {"station_id": "DEMO_NOT_EXIST"})
            self.assertEqual((e["operation"], e["data_mode"]), (op, "SYNTHETIC"))
        st, r = H("demo", {"station_id": "DEMO_TARGET_A", "start": "2020-01-01", "end": "2020-01-02"})
        self.assertEqual((r["operation"], r["science_stage"]), ("SYNTHETIC_DEMO", "METADATA_ONLY"))
        st, r = P({"target_station_id": "DEMO_TARGET_A"})
        self.assertEqual((r["operation"], r["science_stage"]), ("PREDICT_REQUEST", "METADATA_ONLY"))
        st, h, j = self.call("GET", "/api/vhs/nothing")
        self.assertEqual((st, j["operation"]), (404, "UNRESOLVED"))

    def test_D3_02_admission_status_and_alias(self):
        for sid in dd.STATIONS:
            st, a = H("audit", {"station_id": sid})
            self.assertEqual(a["admission_status"]["status"], a["s0d"]["audit"]["science_admission"]["status"])
            self.assertIn(a["admission_status"]["status"], vc.STATUS_VALUES)
            self.assertTrue(a["admission_status"]["rule_basis"].startswith("SYNTHETIC_RULES"))
            self.assertIn("s0d_status", a)
            dep = {d["field"]: d for d in a["deprecations"]}
            self.assertEqual(dep["s0d_status"]["status"], "DEPRECATED_ALIAS")
            self.assertIn("operation", dep["s0d_status"]["replacement"])

    def test_D3_03_enums_match_draft(self):
        self.assertEqual(sorted(set(core.OPERATIONS.values()) | {core.OPERATION_UNRESOLVED}),
                         sorted(DRAFT["$defs"]["operation"]["enum"]))
        self.assertEqual(list(core.DATA_MODES), DRAFT["$defs"]["data_mode"]["enum"])
        self.assertEqual(list(vc.SCIENCE_STAGES), DRAFT["$defs"]["science_stage"]["enum"])
        self.assertIn(core.CURRENT_SCIENCE_STAGE, vc.SCIENCE_STAGES)
        self.assertEqual(core.DATA_MODE, "SYNTHETIC")


# ------------------------------------------------------------------ D4 认证说明
class R1_D4_Certification(unittest.TestCase):
    def test_D4_01_responses(self):
        for sid in ("DEMO_TARGET_A", "DEMO_QC_IDEAL", "DEMO_CYCLE_X"):
            st, r = H("network", {"station_id": sid})
            self.assertEqual(r["certification_status"], "NOT_CERTIFIED")
            self.assertIn(core.CERTIFICATION_NOTE, r["warnings"])
            for lst in ("upstream_donors", "nonconnected_controls", "network_relations"):
                for d in r[lst]:
                    self.assertEqual((d["evidence_level"], d["certification_status"], d["data_mode"]),
                                     ("PROPOSED", "NOT_CERTIFIED", "SYNTHETIC"))
        self.assertIn("不等于数据已获科学认证", core.CERTIFICATION_NOTE)

    def test_D4_02_docs_and_page(self):
        for rel in ("index.html", "README.md", "interface_decisions.md"):
            self.assertIn("不等于数据已获科学认证", read(rel), rel)
        self.assertIn("certification_status=NOT_CERTIFIED", read("index.html"))


# ------------------------------------------------------------------ D5 错误码
class R1_D5_ErrorCodes(unittest.TestCase):
    def test_D5_01_legacy_unchanged_and_draft_codes_not_in_runtime(self):
        self.assertEqual(vc.ERROR_CODES, LEGACY_CODES)
        for rel in (os.path.join(OLD, "vhs_contract.py"), os.path.join(ROOT, "demo_core.py"),
                    os.path.join(ROOT, "demo_server.py")):
            with open(rel, encoding="utf-8") as fh:
                self.assertNotIn("V2-E", fh.read(), rel)
        dc = [c["draft_code"] for c in DRAFT_CODES["codes"]]
        self.assertEqual(len(dc), len(set(dc)))
        self.assertTrue(all(re.match(r"^V2-E\d{3}$", c) for c in dc))
        for c in DRAFT_CODES["codes"]:
            if c["legacy_code"] is not None:
                self.assertIn(c["legacy_code"], LEGACY_CODES)
                self.assertIn(c["legacy_code"], core.ERROR_ALIAS_MAP[c["alias"]])
                self.assertEqual(core.ALIAS_HTTP[c["alias"]], c["http_status"])

    def test_D5_02_alias_map_covers_legacy_mapping(self):
        for alias, codes in core.ERROR_ALIAS_MAP.items():
            self.assertIn(alias, core.ALIAS_HTTP)
            for c in codes:
                self.assertIn(c, LEGACY_CODES)


# ------------------------------------------------------------------ D6 HTTP 语义
class R1_D6_HttpSemantics(_Srv):
    CASES = [  # (method, path, body, raw, ctype, status, alias)
        ("GET", "/api/vhs/stations/DEMO_TARGET_A", None, None, None, 200, None),
        ("GET", "/api/vhs/stations/DEMO_NOT_EXIST", None, None, None, 404, "UNKNOWN_STATION"),
        ("GET", "/api/vhs/stations/DEMO_TARGET_A?dataset_version=9.9", None, None, None, 404, "UNKNOWN_DATASET"),
        ("GET", "/api/vhs/stations/bad%20id", None, None, None, 400, "INVALID_REQUEST"),
        ("GET", "/api/vhs/nothing", None, None, None, 404, "ROUTE_NOT_FOUND"),
        ("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A"}, None, "application/json", 403, None),
        ("POST", "/api/vhs/predict", {"target_station_id": "DEMO_NOT_EXIST"}, None, "application/json", 404,
         "UNKNOWN_STATION"),
        ("POST", "/api/vhs/predict", {"target_station_id": "x" * 65}, None, "application/json", 400,
         "INVALID_REQUEST"),
        ("POST", "/api/vhs/predict", None, b"{oops", "application/json", 400, "INVALID_REQUEST"),
        ("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A", "dataset_id": "OTHER"}, None,
         "application/json", 404, "UNKNOWN_DATASET"),
        ("GET", "/api/vhs/predict", None, None, None, 405, "METHOD_NOT_ALLOWED"),
        ("DELETE", "/api/vhs/stations/DEMO_TARGET_A", None, None, None, 405, "METHOD_NOT_ALLOWED"),
        ("POST", "/api/vhs/stations/DEMO_TARGET_A", {"a": 1}, None, "application/json", 405, "METHOD_NOT_ALLOWED"),
        ("POST", "/api/vhs/predict", None, b"x" * (64 * 1024 + 1), "application/json", 413, "REQUEST_TOO_LARGE"),
        ("GET", "/api/vhs/stations/" + "A" * 2100, None, None, None, 414, "URI_TOO_LONG"),
    ]

    def test_D6_01_status_alias_one_to_one(self):
        for method, path, body, raw, ctype, status, alias in self.CASES:
            st, h, j = self.call(method, path, body, raw, ctype)
            self.assertEqual(st, status, (method, path[:60]))
            self.assertIsNone(j["prediction"])
            self.assertEqual(h.get("X-VHS-Interface-Status"), "PROPOSED")
            if alias is None:
                self.assertNotEqual(j["response_type"], "error")
            else:
                self.assertEqual((j["error"]["alias"], j["error"]["http_status"]), (alias, status))
                self.assertEqual(core.ALIAS_HTTP[alias], status)
                self.assertNotIn("prediction_authorized", j)          # D6：4xx 不声明授权
            if status == 403:
                self.assertEqual(j["prediction_authorized"]["status"], "NOT_AUTHORIZED")
                self.assertIs(j["prediction_authorization_evaluated"], True)

    def test_D6_02_predict_three_outcomes(self):
        st, h, a = self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_NOT_EXIST", "authorized": True})
        st2, h2, b = self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A", "authorized": True})
        st3, h3, c = self.call("POST", "/api/vhs/predict", {"target_station_id": 7})
        self.assertEqual((st, st2, st3), (404, 403, 400))
        self.assertEqual((a["error"]["alias"], b["s0d_status"], c["error"]["alias"]),
                         ("UNKNOWN_STATION", "NOT_AUTHORIZED", "INVALID_REQUEST"))
        for j in (a, b, c):
            self.assertIsNone(j["prediction"])
            self.assertNotIn("values", json.dumps(j.get("synthetic_display_data")) if "synthetic_display_data" in j
                             else "")
        for j in (a, c):
            self.assertNotIn("prediction_authorized", j)
            self.assertIs(j["prediction_authorization_evaluated"], False)
            self.assertIn("不表示存在任何授权", j["prediction_authorization_note"])

    def test_D6_03_every_http_error_status_matches_alias(self):
        seen = 0
        for src, st, r in ALL:
            if src.startswith("http") and r.get("response_type") == "error":
                self.assertEqual(core.ALIAS_HTTP[r["error"]["alias"]], st, src)
                self.assertEqual(r["error"]["http_status"], st, src)
                seen += 1
        self.assertGreater(seen, 10)


# ------------------------------------------------------------------ D7 坐标轴序
def _axis_rec(sid, lat, lon):
    return dict(dd.STATIONS["DEMO_QC_IDEAL"], station_id=sid, coordinates_lat_lon=[lat, lon])


class R1_D7_AxisOrder(unittest.TestCase):
    def test_D7_01_api_axis_fields(self):
        for sid, rec in dd.STATIONS.items():
            st, r = H("station", {"station_id": sid})
            crs = r["coordinate_reference_system"]
            lat, lon = rec["coordinates_lat_lon"]
            self.assertEqual((crs["epsg"], crs["units"], crs["axis_order"]), (4326, "degree", "lat,lon"))
            self.assertEqual(crs["epsg_authority_axis_order"], ["latitude", "longitude"])
            self.assertEqual(crs["coordinate_axis_order_in_payload"], ["latitude", "longitude"])
            self.assertEqual((crs["coordinates"], crs["lon_lat"]), ([lat, lon], [lon, lat]))
            self.assertEqual(core.lat_lon_from_crs(crs), (lat, lon))
            self.assertEqual(r["s0d"]["station"]["crs"]["coordinates"], [lat, lon])
        n = H("network", {"station_id": "DEMO_TARGET_A"})[1]["s0d"]["network"]["graph_for_display"]
        node = {x["id"]: x for x in n["nodes"]}["DEMO_TARGET_A"]
        self.assertEqual([node["lat"], node["lon"]], dd.STATIONS["DEMO_TARGET_A"]["coordinates_lat_lon"])
        self.assertIn("x <- lon", n["svg_mapping"])

    def test_D7_02_east_north_via_api_and_projector(self):
        g = AXIS["axis_graph"]
        crs = {}
        for sid, lat, lon in (("AX_O", 40.0, 80.0), ("AX_E", 40.0, 81.0), ("AX_N", 41.0, 80.0)):
            rec = _axis_rec(sid, lat, lon)
            net = core.analyze_network(g, sid)
            env = core.build_envelope(rec, net, core.audit_station(rec, net), "station", "AXIS")
            crs[sid] = env["coordinate_reference_system"]
        self.assertEqual([crs[k] for k in ("AX_O", "AX_E", "AX_N")], [c["crs"] for c in AXIS["crs_accept"][:3]])
        pts = {k: dict(zip(("lat", "lon"), core.lat_lon_from_crs(v))) for k, v in crs.items()}
        proj = axis_ref.make_projector(list(pts.values()))
        o, e, n = (proj(pts[k]["lat"], pts[k]["lon"]) for k in ("AX_O", "AX_E", "AX_N"))
        self.assertGreater(e[0], o[0])            # 正东 -> x 更大
        self.assertAlmostEqual(e[1], o[1])        # 同纬度 -> 同 y
        self.assertLess(n[1], o[1])               # 正北 -> SVG y 更小（向上）
        self.assertAlmostEqual(n[0], o[0])        # 同经度 -> 同 x
        wrong = axis_ref.make_projector([{"lat": c["coordinates"][1], "lon": c["coordinates"][0]}
                                         for c in crs.values()])   # 若误把 [lat, lon] 当 [lon, lat]
        self.assertNotEqual(wrong(80.0, 40.0)[0] < wrong(81.0, 40.0)[0], e[0] > o[0])

    def test_D7_03_python_reproduces_fixture(self):
        self.assertEqual(axis_ref.DEFAULT_BOX, AXIS["box"])
        for c in AXIS["projector_cases"]:
            p = axis_ref.make_projector(c["points"], AXIS["box"])
            for q, exp in zip(c["points"], c["expected"]):
                got = p(q["lat"], q["lon"])
                self.assertAlmostEqual(got[0], exp[0], places=9)
                self.assertAlmostEqual(got[1], exp[1], places=9)
        for c in AXIS["crs_accept"]:
            self.assertEqual(core.lat_lon_from_crs(c["crs"]), (c["lat"], c["lon"]))
        for c in AXIS["crs_reject"]:
            with self.assertRaises(ValueError) as cm:
                core.lat_lon_from_crs(c["crs"])
            self.assertEqual(str(cm.exception), c["error"], c["name"])

    def test_D7_04_epsg_3035_4326_mix_rejected_by_old_validator(self):
        bad = {"epsg": 3035, "units": "metre", "epsg_authority_axis_order": ["northing", "easting"],
               "coordinate_axis_order_in_payload": ["latitude", "longitude"], "coordinates": [40.5, 80.0]}
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_crs(bad, "EUROPE")])
        bad2 = {"epsg": 4326, "units": "degree", "epsg_authority_axis_order": ["latitude", "longitude"],
                "coordinate_axis_order_in_payload": ["easting", "northing"], "coordinates": [40.5, 80.0]}
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_crs(bad2, "GLOBAL")])
        bad3 = {"epsg": 3035, "units": "degree", "epsg_authority_axis_order": ["latitude", "longitude"],
                "coordinate_axis_order_in_payload": ["latitude", "longitude"], "coordinates": [40.5, 80.0]}
        self.assertTrue(vc.validate_crs(bad3, "EUROPE"))

    def test_D7_05_frontend_uses_pure_function(self):
        g, app, html = read("geo_map.js"), read("app.js"), read("index.html")
        self.assertIn("(lon - minLon) / (maxLon - minLon) * b.width", g)
        self.assertIn("(maxLat - lat) / (maxLat - minLat) * b.height", g)
        self.assertIn("GEO.makeProjector(g.nodes, GEO.DEFAULT_BOX)", app)
        self.assertIn("project(n.lat, n.lon)", app)
        self.assertNotIn("function X(lon)", app)
        self.assertLess(html.index('src="geo_map.js"'), html.index('src="app.js"'))

    def test_D7_06_node_runs_geo_map_on_same_fixture(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node 不可用：本机无法直接执行 geo_map.js；一致性由 box 上的 node 运行记录"
                          "（tests/js/test_geo_map.js）与 D7_03/D7_05 共同证明")
        p = subprocess.run([node, os.path.join(HERE, "js", "test_geo_map.js")], capture_output=True, timeout=60)
        self.assertEqual(p.returncode, 0, p.stdout.decode("utf-8", "replace") + p.stderr.decode("utf-8", "replace"))


# ------------------------------------------------------------------ D8 PROPOSED 标注
class R1_D8_ProposedMarking(unittest.TestCase):
    FILES = ["README.md", "interface_decisions.md", "compat_report.md", "incident_audit.md", "index.html", "app.js",
             "geo_map.js", "demo_core.py", "demo_server.py", "demo_cli.py", "schema_draft/vhs_response_v0.2.draft.schema.json",
             "schema_draft/error_codes_v0.2.draft.json", "tools/gen_io_examples_r1.py"]

    def test_D8_01_every_response(self):
        st, r = H("station", {"station_id": "DEMO_TARGET_A"})
        st2, e = H("station", {"station_id": "DEMO_NOT_EXIST"})
        for x in (r, e):
            self.assertEqual(x["interface_status"], "PROPOSED")
            self.assertTrue(any(NOT_OFFICIAL in w for w in x["warnings"]))

    def test_D8_02_docs_page_never_claim_integration(self):
        for rel in ("README.md", "index.html", "interface_decisions.md"):
            self.assertIn(NOT_OFFICIAL, read(rel), rel)
        for rel in self.FILES:
            text = read(rel)
            for m in re.finditer("完成正式集成", text):
                self.assertEqual(text[m.start() - 1], "未", (rel, text[max(0, m.start() - 20):m.end()]))
            self.assertNotIn("已集成", text, rel)
            self.assertNotIn("已完成集成", text, rel)
            self.assertNotIn("已接入 DeepBas", text, rel)


# ------------------------------------------------------------------ 非法输入
class R1_IN_IllegalInput(_Srv):
    def e(self, st, j, status, reason=None, code=None):
        self.assertEqual(st, status, j.get("error"))
        if reason:
            self.assertEqual(j["error"]["reason_code"], reason)
        if code:
            self.assertEqual(j["error"]["code"], code)
        self.assertIsNone(j["prediction"])
        self.assertNotIn("prediction_authorized", j)

    def test_IN_01_missing_fields(self):
        self.e(*self.call("GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A")[::2], 400, "TIME_RANGE_MISSING")
        self.e(*self.call("GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01")[::2], 400,
               "TIME_RANGE_MISSING")
        self.e(*self.call("GET", "/api/vhs/synthetic-demo?start=2020-01-01&end=2020-01-02")[::2], 400,
               "STATION_ID_MISSING", "VHS-E001")
        self.e(*self.call("POST", "/api/vhs/predict", {})[::2], 400, "STATION_ID_MISSING", "VHS-E001")
        self.e(*self.call("POST", "/api/vhs/predict", {"start": "2020-01-01"})[::2], 400, "STATION_ID_MISSING")

    def test_IN_02_wrong_types(self):
        for b in ({"target_station_id": 123}, {"target_station_id": ["DEMO_TARGET_A"]},
                  {"target_station_id": {"id": "DEMO_TARGET_A"}}, {"target_station_id": True}):
            self.e(*self.call("POST", "/api/vhs/predict", b)[::2], 400, "STATION_ID_INVALID_FORMAT", "VHS-E003")
        self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A", "start": 20200101,
                                                       "end": "2020-01-02"})[::2], 400, "TIME_FORMAT_INVALID")
        self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A", "dataset_id": 5})[::2],
               400, "DATASET_PARAM_INVALID")
        for b in ([1], "x", 5, None):
            self.e(*self.call("POST", "/api/vhs/predict", raw=json.dumps(b).encode())[::2], 400, "BODY_NOT_OBJECT")

    def test_IN_03_overlong_control_traversal(self):
        self.e(*self.call("GET", "/api/vhs/stations/" + "A" * 65)[::2], 400, "STATION_ID_INVALID_FORMAT")
        self.e(*self.call("GET", "/api/vhs/stations/" + "A" * 1500)[::2], 400, "STATION_ID_INVALID_FORMAT")
        self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": "B" * 10000})[::2], 400,
               "STATION_ID_INVALID_FORMAT")
        for enc in ("DEMO%00X", "DEMO%0AX", "DEMO%09X", "DEMO%7FX", "DEMO%0D%0AX-Injected:1", "%E4%B8%AD"):
            self.e(*self.call("GET", "/api/vhs/stations/" + enc)[::2], 400, "STATION_ID_INVALID_FORMAT")
        for b in ("DEMO\u0000X", "DEMO\nX", "\u202eDEMO", " DEMO_TARGET_A"):
            self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": b})[::2], 400,
                   "STATION_ID_INVALID_FORMAT")
        for p in ("/api/vhs/stations/..%2F..%2Fdemo_core.py", "/api/vhs/stations/..%5C..%5Cvhs_contract.py"):
            self.e(*self.call("GET", p)[::2], 400, "STATION_ID_INVALID_FORMAT")
        # ".." 符合旧契约 STATION_ID_RE（允许 "."）；原型不改旧正则（D1），它只作为字典键查找 -> 404，不触碰文件系统
        self.e(*self.call("GET", "/api/vhs/stations/%2e%2e")[::2], 404, "UNKNOWN_STATION", "VHS-E002")
        st, h, j = self.call("GET", "/api/vhs/stations/../../b1b_s0_deepbas_mvp/vhs_contract.py")
        self.assertEqual((st, j["error"]["alias"]), (404, "ROUTE_NOT_FOUND"))
        self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": "../../etc/passwd"})[::2], 400,
               "STATION_ID_INVALID_FORMAT")
        self.e(*self.call("GET", "/api/vhs/stations/" + "A" * 2100)[::2], 414, "URL_TOO_LONG")

    def test_IN_04_body_size_nonjson_ctype(self):
        self.e(*self.call("POST", "/api/vhs/predict", raw=b"{" + b" " * (64 * 1024) + b"}")[::2], 413, "BODY_TOO_LARGE")
        for raw in (b"{not json", b"", b"\xff\xfe\x00", b'{"target_station_id": Infinity}', b"[" * 20000 + b"]" * 20000):
            self.e(*self.call("POST", "/api/vhs/predict", raw=raw)[::2], 400, "JSON_PARSE_ERROR")
        body = {"target_station_id": "DEMO_TARGET_A"}
        for ct in ("text/plain", "application/x-www-form-urlencoded", "application/jsonp", "multipart/form-data"):
            self.e(*self.call("POST", "/api/vhs/predict", body, ctype=ct)[::2], 400, "CONTENT_TYPE_UNSUPPORTED")
        self.e(*self.call("POST", "/api/vhs/predict", body, ctype=None)[::2], 400, "CONTENT_TYPE_UNSUPPORTED")
        st, h, j = self.call("POST", "/api/vhs/predict", body, ctype="application/json; charset=utf-8")
        self.assertEqual(st, 403)
        self.e(*self.call("POST", "/api/vhs/predict",
                          raw=b'{"target_station_id":"DEMO_QC_IDEAL","target_station_id":"DEMO_TARGET_A"}')[::2],
               400, "JSON_DUPLICATE_KEY")
        self.e(*self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A",
                                                       "station_id": "DEMO_QC_IDEAL"})[::2], 400, "STATION_ID_CONFLICT")

    def test_IN_05_unknown_and_duplicate_params(self):
        for q in ("?foo=1", "?qobs=1.5", "?mode=real", "?Dataset_id=x"):
            self.e(*self.call("GET", "/api/vhs/stations/DEMO_TARGET_A" + q)[::2], 400, "UNKNOWN_PARAMETER")
        self.e(*self.call("GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-02"
                                 "&model=x")[::2], 400, "UNKNOWN_PARAMETER")
        self.e(*self.call("POST", "/api/vhs/predict?authorized=true", {"target_station_id": "DEMO_TARGET_A"})[::2],
               400, "UNKNOWN_PARAMETER")
        for q in ("?dataset_id=a&dataset_id=a", "?start=2020-01-01&start=2020-01-02", "?a=1&a=2"):
            self.e(*self.call("GET", "/api/vhs/stations/DEMO_TARGET_A" + q)[::2], 400, "QUERY_INVALID")
        for q in ("?a&&b", "?=x", "?%00=1", "?" + "&".join("k%d=1" % i for i in range(30))):
            st, h, j = self.call("GET", "/api/vhs/stations/DEMO_TARGET_A" + q)
            self.assertEqual((st, j["error"]["alias"]), (400, "INVALID_REQUEST"), q[:40])
            self.assertIn(j["error"]["reason_code"], ("QUERY_INVALID", "UNKNOWN_PARAMETER"))
            self.assertIsNone(j["prediction"])
        self.e(*self.call("GET", "/api/vhs/stations/DEMO_TARGET_A?station_id=DEMO_QC_IDEAL")[::2], 400,
               "STATION_ID_DUPLICATED")

    def test_IN_06_dates(self):
        base_q = "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=%s&end=%s"
        for s, e_, reason in (("2020-02-30", "2020-03-01", "TIME_FORMAT_INVALID"),
                              ("2020-13-01", "2020-12-31", "TIME_FORMAT_INVALID"),
                              ("2020-1-1", "2020-01-02", "TIME_FORMAT_INVALID"),
                              ("abc", "2020-01-02", "TIME_FORMAT_INVALID"),
                              ("2020-01-01T00:00", "2020-01-02", "TIME_FORMAT_INVALID"),
                              ("2020-03-01", "2020-02-01", "TIME_RANGE_START_AFTER_END"),
                              ("2019-12-31", "2020-01-02", "TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW"),
                              ("2020-12-30", "2021-01-01", "TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW"),
                              ("2020-01-01", "2020-04-02", "TIME_RANGE_TOO_LONG")):
            self.e(*self.call("GET", base_q % (s, e_))[::2], 400, reason)
        for s, e_, reason in (("2020-02-30", "2020-03-01", "TIME_FORMAT_INVALID"),
                              ("2020-03-01", "2020-02-01", "TIME_RANGE_START_AFTER_END"),
                              ("2020-01-01", None, "TIME_RANGE_MISSING")):
            b = {"target_station_id": "DEMO_TARGET_A", "start": s}
            if e_:
                b["end"] = e_
            self.e(*self.call("POST", "/api/vhs/predict", b)[::2], 400, reason)


# ------------------------------------------------------------------ 预测拒绝
class R1_PR_PredictRejection(_Srv):
    VARIANTS = [
        {"mode": "hindcast"}, {"mode": "REALTIME_FORECAST"}, {"Mode": "realtime"}, {"MODE": "x"},
        {"model": "xxx"}, {"Model_ID": "GNN"}, {"model-name": "lstm"},
        {"authorized": True}, {"authorized": "true"}, {"authorized": 1}, {"Authorized": True}, {"AUTHORIZED": "yes"},
        {" authorized ": True}, {"authorization": "Bearer x"}, {"authorization_ref": "REF-1"},
        {"prediction_authorized": {"status": "PASS"}}, {"prediction_authorized": "PASS"},
        {"force": True}, {"override": 1}, {"bypass": True}, {"admin": True}, {"token": "abc"},
        {"science_stage": "INDEPENDENTLY_VALIDATED"}, {"data_class": "VALIDATED_PRODUCT_FUTURE"},
        {"allow_real": True}, {"real": True}, {"prediction": {"values": [1, 2]}},
        {"options": {"authorized": True}}, {"meta": {"auth": {"FORCE": True}}}, {"list": [{"mode": "x"}]},
        {"unrelated_extra": "x"}, {"start": "2020-01-01", "end": "2020-02-01"},
        {"dataset_id": dd.DATASET_ID, "dataset_version": dd.DATASET_VERSION},
    ]

    def test_PR_01_all_variants_403(self):
        for sid in ("DEMO_TARGET_A", "DEMO_QC_IDEAL", "DEMO_HEAD_1", "DEMO_CYCLE_X"):
            for v in self.VARIANTS:
                body = dict({"target_station_id": sid}, **v)
                for st, r in (P(body), self.call("POST", "/api/vhs/predict", body)[::2]):
                    self.assertEqual((st, r["s0d_status"], r["prediction_authorized"]["status"]),
                                     (403, "NOT_AUTHORIZED", "NOT_AUTHORIZED"), v)
                    self.assertIsNone(r["prediction"])
                    self.assertNotIn("synthetic_display_data", r)

    def test_PR_02_override_detection_case_and_nested(self):
        st, r = P({"target_station_id": "DEMO_TARGET_A", "AUTHORIZED": True, "Mode": "x", "options": {"Force": 1},
                   "list": [{"model": "m"}], "meta": {"auth": {"BYPASS": True}}})
        self.assertEqual(r["s0d"]["predict"]["override_attempts_ignored"],
                         sorted(["AUTHORIZED", "Mode", "options.Force", "list.*.model", "meta.auth.BYPASS"]))
        st, r = P({"target_station_id": "DEMO_TARGET_A", "nested": {"qobs": {"authorized": True}}})
        self.assertEqual(r["s0d"]["predict"]["override_attempts_hidden_count"], 1)   # 路径含禁用键名 -> 不回显
        self.assertNotIn("qobs", json.dumps(r))

    def test_PR_03_station_variants(self):
        for sid, status in (("DEMO_NOT_EXIST", 404), ("demo_target_a", 404), ("DEMO_TARGET_A ", 400),
                            ("DEMO_TARGET_A/../x", 400), ("", 400), ("DEMO_CTRL_NEAR", 403)):
            for st, r in (P({"target_station_id": sid, "authorized": True}),
                          self.call("POST", "/api/vhs/predict", {"target_station_id": sid, "authorized": True})[::2]):
                self.assertEqual(st, status, sid)
                self.assertIsNone(r["prediction"])
                if status == 403:
                    self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED")
                else:
                    self.assertNotIn("prediction_authorized", r)
        st, r = P({"station_id": "DEMO_QC_IDEAL"})
        self.assertEqual((st, r["target_station_id"]), (403, "DEMO_QC_IDEAL"))


# ------------------------------------------------------------------ 关系方向（扩展）
class R1_REL_Direction(unittest.TestCase):
    def rel(self, net_env):
        out = {}
        for x in net_env["network_relations"]:
            out.setdefault(x["relation"], set()).add(x["station_id"])
        return out

    def test_REL_01_network_relations_consistent(self):
        for sid in ("DEMO_TARGET_A", "DEMO_DOWN_1", "DEMO_HEAD_1", "DEMO_CTRL_1", "DEMO_CYCLE_X"):
            st, r = H("network", {"station_id": sid})
            n, rel = r["s0d"]["network"], self.rel(r)
            if n["connection_status"] != "CYCLE_DETECTED":
                self.assertEqual(rel.get("CONNECTED_UPSTREAM", set()), base.ids(n["upstream_nodes"]), sid)
                self.assertEqual(rel.get("CONNECTED_DOWNSTREAM", set()), base.ids(n["downstream_nodes"]), sid)
            self.assertEqual(rel.get("SAME_SYSTEM_NOT_UPSTREAM", set()), base.ids(n["same_system_not_upstream"]))
            self.assertEqual(rel.get("NONCONNECTED_CONTROL", set()), base.ids(n["nonconnected_control_candidates"]))
            self.assertNotIn(sid, set().union(*rel.values()) if rel else set())
        st, r = H("network", {"station_id": "DEMO_TARGET_A"})
        rel = self.rel(r)
        self.assertEqual(rel["CONNECTED_DOWNSTREAM"], {"DEMO_DOWN_1", "DEMO_OUTLET"})
        self.assertEqual(rel["SAME_SYSTEM_NOT_UPSTREAM"], {"DEMO_TRIB_DS", "DEMO_CANAL_BASIN_OUT"})
        st, c = H("network", {"station_id": "DEMO_CYCLE_X"})
        self.assertTrue({"DEMO_CYCLE_Y", "DEMO_CYCLE_Z"} <= self.rel(c)["IN_CYCLE_TOPOLOGY_INVALID"])

    def test_REL_02_chain_and_branch(self):
        g = {"graph_id": "CHAIN", "nodes": [{"id": x} for x in "ABCDEF"],
             "edges": [{"id": "1", "from": "A", "to": "B", "snap_status": "CERTIFIED"},
                       {"id": "2", "from": "B", "to": "C", "snap_status": "CERTIFIED"},
                       {"id": "3", "from": "C", "to": "D", "snap_status": "CERTIFIED"},
                       {"id": "4", "from": "D", "to": "E", "snap_status": "CERTIFIED"},
                       {"id": "5", "from": "F", "to": "D", "snap_status": "CERTIFIED"}]}
        n = core.analyze_network(g, "E")
        self.assertEqual({u["station_id"]: u["hops"] for u in n["upstream_nodes"]},
                         {"D": 1, "C": 2, "F": 2, "B": 3, "A": 4})
        n = core.analyze_network(g, "C")
        self.assertEqual((base.ids(n["upstream_nodes"]), base.ids(n["downstream_nodes"]),
                          base.ids(n["same_system_not_upstream"])), ({"A", "B"}, {"D", "E"}, {"F"}))
        rel = {x["station_id"]: x["relation"] for x in core.network_relations_v02(n)}
        self.assertEqual(rel, {"A": "CONNECTED_UPSTREAM", "B": "CONNECTED_UPSTREAM", "D": "CONNECTED_DOWNSTREAM",
                               "E": "CONNECTED_DOWNSTREAM", "F": "SAME_SYSTEM_NOT_UPSTREAM"})
        rg = copy.deepcopy(g)
        for e in rg["edges"]:
            e["from"], e["to"] = e["to"], e["from"]
        rn = core.analyze_network(rg, "C")
        self.assertEqual((base.ids(rn["upstream_nodes"]), base.ids(rn["downstream_nodes"])), ({"D", "E"}, {"A", "B"}))
        self.assertEqual(core.check_network_invariants(n), [])


# ------------------------------------------------------------------ 日志安全
SENTINELS = ("987.654321", "0.123456789", "0.55555", "13579.2468", "24680.1357")


class R1_LOG_Safety(_Srv):
    def _assert_clean(self, text, where):
        for s in SENTINELS:
            self.assertNotIn(s, text, where)
        self.assertIsNone(base.RESTRICTED_TEXT.search(text), where)
        self.assertIsNone(vc.FORBIDDEN_LOG_TEXT.search(text), where)

    def test_LOG_01_in_process_server_logs_and_responses(self):
        start = len(base.LOG_LINES)
        inj = {"target_station_id": "DEMO_TARGET_A", "qobs": [987.654321], "nse": 0.123456789, "kge": 0.55555,
               "nested": {"Q_obs": 13579.2468, "discharge": 24680.1357}}
        outs = [self.call("POST", "/api/vhs/predict", inj)[2],
                self.call("POST", "/api/vhs/predict", dict(inj, target_station_id="DEMO_NOT_EXIST"))[2],
                self.call("GET", "/api/vhs/stations/DEMO_TARGET_A?qobs=987.654321&nse=0.123456789")[2],
                self.call("GET", "/api/vhs/synthetic-demo?station_id=DEMO_TARGET_A&start=2020-01-01&end=2020-01-02"
                                 "&kge=0.55555")[2],
                self.call("GET", "/api/vhs/stations/qobs=987.654321")[2],
                self.call("POST", "/api/vhs/predict", raw=b'{"qobs": 987.654321, "target_station_id": ')[2]]
        for j in outs:
            self._assert_clean(json.dumps(j, ensure_ascii=False), "response")
            self.assertEqual(vc.scan_forbidden_fields(j), [])
        for _ in range(100):   # 服务端在发送响应后才写访问日志（线程竞争），等待日志落定，不放松断言
            if len(base.LOG_LINES) - start >= 6:
                break
            time.sleep(0.02)
        new = base.LOG_LINES[start:]
        self.assertGreaterEqual(len(new), 6)
        for line in new:
            self._assert_clean(line, line)
            self.assertTrue(vc.assert_log_safe(line))

    def test_LOG_02_cli_output(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        for args in (["predict", "DEMO_TARGET_A", "--extra", "qobs=987.654321", "--extra", "nse=0.123456789",
                      "--extra", "kge=0.55555"],
                     ["predict", "DEMO_NOT_EXIST", "--extra", "qobs=987.654321"],
                     ["station", "DEMO_TARGET_A"]):
            p = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "demo_cli.py")] + args, cwd=ROOT, env=env,
                               capture_output=True, timeout=60)
            text = p.stdout.decode("utf-8") + p.stderr.decode("utf-8", "replace")
            self._assert_clean(text, args)
            self.assertIsNone(json.loads(p.stdout.decode("utf-8"))["prediction"])

    def test_LOG_03_real_server_process_stderr(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen([sys.executable, "-B", os.path.join(ROOT, "demo_server.py"), "--port", str(port)],
                                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            ok = False
            for _ in range(100):
                try:
                    c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
                    c.request("GET", "/api/vhs/stations/DEMO_TARGET_A")
                    c.getresponse().read()
                    c.close()
                    ok = True
                    break
                except OSError:
                    time.sleep(0.1)
            self.assertTrue(ok, "server subprocess did not start")
            old_port, self.port = self.port, port
            try:
                self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_TARGET_A", "qobs": [987.654321],
                                                       "nse": 0.123456789})
                self.call("GET", "/api/vhs/stations/DEMO_TARGET_A?qobs=13579.2468")
                self.call("POST", "/api/vhs/predict", {"target_station_id": "DEMO_NOT_EXIST", "kge": 0.55555})
            finally:
                self.port = old_port
        finally:
            proc.terminate()
            out, err = proc.communicate(timeout=20)
        text = out.decode("utf-8", "replace") + err.decode("utf-8", "replace")
        self.assertIn('"event": "request"', text)
        self._assert_clean(text, "server stderr")


# ------------------------------------------------------------------ 不访问封存目录
class _FakeEntry:
    def __init__(self, parent, name, kind):
        self.name, self.path, self.kind = name, parent.rstrip("/") + "/" + name, kind

    def is_symlink(self):
        return self.kind == "link"

    def is_junction(self):
        return False

    def is_dir(self, follow_symlinks=True):
        return self.kind == "dir"

    def is_file(self, follow_symlinks=True):
        return self.kind == "file"

    def stat(self, follow_symlinks=True):
        class S:
            st_size, st_mtime_ns = 7, 123
        return S()


class _FakeFS:
    TREE = {"/r": [("a", "dir"), ("sealed_runoff", "dir"), ("Quarantine_old", "dir"), ("x_SEALED", "dir"),
                   ("b.txt", "file"), ("lnk", "link")],
            "/r/a": [("c.txt", "file"), ("quarantine", "dir"), ("deep", "dir")], "/r/a/deep": [("d.txt", "file")],
            "/r/sealed_runoff": [("SECRET_Q.csv", "file")], "/r/Quarantine_old": [("e.txt", "file")],
            "/r/x_SEALED": [("f.txt", "file")], "/r/a/quarantine": [("g.txt", "file")]}

    def __init__(self):
        self.opened = []

    def scandir(self, d):
        # R1 修正（PC 实跑发现）：walk_pruned 内 os.path.abspath 在 Windows 上把 "/r" 变成 "E:\\r"，
        # 这里去掉盘符并统一分隔符后再查假目录树；记录的也是规范化后的键，断言不放宽。
        key = os.path.splitdrive(str(d))[1].replace("\\", "/")
        self.opened.append(key)
        fs = self

        class Ctx:
            def __enter__(self_):
                return iter([_FakeEntry(d, n, k) for n, k in fs.TREE[key]])

            def __exit__(self_, *a):
                return False
        return Ctx()


class R1_SEAL_NoSealedAccess(_Srv):
    def test_SEAL_01_walker_prunes_by_name(self):
        fs = _FakeFS()
        trace = []
        res = isr1.walk_pruned("/r", with_hash=False, scandir=fs.scandir, trace=trace)
        self.assertEqual(sorted(res["files"]), ["a/c.txt", "a/deep/d.txt", "b.txt"])
        self.assertEqual([p["path"] for p in res["pruned_dirs_metadata_only"]],
                         ["Quarantine_old", "a/quarantine", "sealed_runoff", "x_SEALED"])
        self.assertEqual(res["links_not_followed"], ["lnk"])
        for d in fs.opened + trace:
            self.assertIsNone(isr1.FORBIDDEN_DIR_RE.search(d), d)
        with self.assertRaises(ValueError):
            isr1.walk_pruned("/r/sealed_runoff", with_hash=False, scandir=fs.scandir)
        l1 = isr1.level1("/r", scandir=fs.scandir)
        self.assertIn("note", l1["sealed_runoff"])
        self.assertEqual(fs.opened.count("/r/sealed_runoff"), 0)

    def test_SEAL_02_static_scan_new_files(self):
        pat = re.compile(r"(?i)sealed_runoff|quarantine")
        for rel in ("demo_core.py", "demo_server.py", "demo_cli.py", "demo_data.py", "app.js", "geo_map.js",
                    "index.html", "tools/gen_io_examples_r1.py", "tools/build_artifacts.py",
                    "schema_draft/error_codes_v0.2.draft.json"):
            self.assertIsNone(pat.search(read(rel)), rel)
        src = read("tools/integrity_snapshot_r1.py")
        self.assertNotIn("sealed_runoff", src)
        self.assertEqual(src.count('re.compile(r"(?i)sealed|quarantin")'), 1)
        code_lines = [l for l in src.splitlines() if re.search(r"(?i)sealed|quarantin", l)
                      and not l.strip().startswith("#") and "FORBIDDEN_DIR_RE" not in l]
        for l in code_lines:   # 其余出现只能在文档串/说明/异常文本中，不得构造路径
            self.assertNotIn("os.path.join", l)
            self.assertNotIn("scandir(", l)

    def test_SEAL_03_runtime_file_access_guard(self):
        seen = []
        orig_open, orig_scandir, orig_listdir, orig_stat = builtins.open, os.scandir, os.listdir, os.stat
        pat = re.compile(r"(?i)sealed|quarantin")

        def g_open(f, *a, **k):
            seen.append(str(f))
            return orig_open(f, *a, **k)

        def g_scandir(p="."):
            seen.append(str(p))
            return orig_scandir(p)

        def g_listdir(p="."):
            seen.append(str(p))
            return orig_listdir(p)

        def g_stat(p, *a, **k):
            seen.append(str(p))
            return orig_stat(p, *a, **k)
        builtins.open, os.scandir, os.listdir, os.stat = g_open, g_scandir, g_listdir, g_stat
        try:
            for sid in dd.STATIONS:
                for fn in ("station", "network", "audit"):
                    H(fn, {"station_id": sid})
                H("demo", {"station_id": sid, "start": "2020-01-01", "end": "2020-01-03"})
                P({"target_station_id": sid})
            core.offline_snapshot()
            for p in ("/", "/app.js", "/geo_map.js", "/api/vhs/stations/DEMO_TARGET_A", "/../sealed_runoff/x",
                      "/api/vhs/stations/sealed_runoff"):
                self.call("GET", p)
        finally:
            builtins.open, os.scandir, os.listdir, os.stat = orig_open, orig_scandir, orig_listdir, orig_stat
        self.assertEqual([p for p in seen if pat.search(p)], [])
        self.assertEqual(base.EXTERNAL_ATTEMPTS, [])


# ------------------------------------------------------------------ 旧目录未修改
class R1_OLD_FilesUnchanged(unittest.TestCase):
    def test_OLD_01_against_r1_pre_snapshot(self):
        pre_path = os.path.join(ROOT, "integrity", "r1_pre_snapshot.json")
        if not os.path.exists(pre_path):
            self.skipTest("integrity/r1_pre_snapshot.json 只在用户电脑上生成（开发前快照）")
        with open(pre_path, encoding="utf-8") as fh:
            pre = json.load(fh)
        vm = os.path.dirname(ROOT)
        now_l1 = isr1.level1(vm)
        pre_l1 = pre["scopes"]["vhs_multistation_level1"]
        self.assertEqual(sorted(now_l1), sorted(pre_l1))
        for k in now_l1:
            if k != isr1.NEW_DIR_NAME:
                self.assertEqual(now_l1[k], pre_l1[k], k)
        self.assertEqual(sorted(pre["scopes"]["vm_whitelist"]), sorted(isr1.VM_WHITELIST))
        for name in isr1.VM_WHITELIST:
            now = isr1.walk_pruned(os.path.join(vm, name), True)
            cmp_ = isr1._cmp_files(pre["scopes"]["vm_whitelist"][name], now)
            self.assertEqual((cmp_["added"], cmp_["removed"], cmp_["changed"]), ([], [], []), name)
            self.assertTrue(cmp_["pruned_dirs_equal"], name)
            self.assertEqual(now["summary"], pre["scopes"]["vm_whitelist"][name]["summary"], name)
        pr = isr1.PROJECT_ROOT
        self.assertEqual(isr1.level1(pr), pre["scopes"]["project_root_level1"])
        self.assertEqual(isr1.level1(os.path.join(pr, "research_next")), pre["scopes"]["research_next_level1"])

    def test_OLD_02_no_pycache(self):
        self.assertFalse(os.path.exists(os.path.join(OLD, "__pycache__")))
        for d, dirs, files in os.walk(ROOT):
            self.assertNotIn("__pycache__", dirs, d)


# ------------------------------------------------------------------ 全局复核（最后运行）
class R1_ZZ_GlobalChecks(unittest.TestCase):
    def test_ZZ_01_all_responses_old_and_draft(self):
        self.assertGreater(len(ALL), 800)
        for src, st, r in ALL:
            self.assertEqual(vc.validate_response(r), [], src)
            self.assertEqual(mini_schema.validate(r, base.OLD_SCHEMA), [], src)
            self.assertEqual(mini_schema.validate(r, DRAFT), [], src)
            self.assertIsNone(r["prediction"], src)
            self.assertEqual((r["interface_status"], r["data_mode"]), ("PROPOSED", "SYNTHETIC"), src)
            if r.get("response_type") == "error":
                self.assertNotIn("prediction_authorized", r, src)
            else:
                self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED", src)

    def test_ZZ_02_error_reason_codes_in_draft_mapping(self):
        mp = {(c["alias"], c["reason_code"]): c for c in DRAFT_CODES["codes"]}
        seen = set()
        for src, st, r in ALL:
            if r.get("response_type") != "error":
                continue
            e = r["error"]
            key = (e["alias"], e["reason_code"]) if e["alias"] != "INTERNAL_CONTRACT_VIOLATION" else (e["alias"], "*")
            self.assertIn(key, mp, src)
            self.assertEqual((mp[key]["legacy_code"], mp[key]["http_status"]), (e["code"], e["http_status"]), src)
            seen.add(key)
        self.assertGreater(len(seen), 20)

    def test_ZZ_03_no_restricted_and_no_external(self):
        for src, st, r in ALL:
            self.assertEqual(vc.scan_forbidden_fields(r), [], src)
            self.assertIsNone(base.RESTRICTED_TEXT.search(json.dumps(r, ensure_ascii=False)), src)
        for line in base.LOG_LINES:
            self.assertIsNone(base.RESTRICTED_TEXT.search(line), line)
        self.assertEqual(base.EXTERNAL_ATTEMPTS, [])


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite([loader.loadTestsFromModule(base), loader.loadTestsFromModule(sys.modules[__name__])])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("R1_SUMMARY total=%d failures=%d errors=%d skipped=%d passed=%d" % (
        result.testsRun, len(result.failures), len(result.errors), len(result.skipped),
        result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)))
    sys.exit(0 if result.wasSuccessful() else 1)
