# -*- coding: utf-8 -*-
"""VHS 候选契约最小单元测试 —— 仅使用纯合成数据（SYNTHETIC_EXAMPLE），不读取任何真实数据/真实 Q。
运行：python -B tests/test_vhs_contract.py （需设置 PYTHONDONTWRITEBYTECODE=1，避免生成 __pycache__）
"""
import copy
import json
import os
import sys
import unittest

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
import vhs_contract as vc  # noqa: E402

with open(os.path.join(ROOT, "05_api_contract_example.json"), encoding="utf-8") as fh:
    EXAMPLES = {e["case"]: e["response"] for e in json.load(fh)["examples"]}
BASE = EXAMPLES["A_metadata_only_not_authorized_wgs84"]
DS = (BASE["dataset_id"], BASE["dataset_version"])
REGISTRY = {DS: {BASE["target_station_id"]: BASE}}


class TestExamples(unittest.TestCase):
    def test_all_examples_valid_and_synthetic(self):
        for case, r in EXAMPLES.items():
            self.assertEqual(vc.validate_response(r), [], case)
            self.assertIn("SYNTHETIC", json.dumps(r, ensure_ascii=False), case)

    def test_example_file_is_strict_json(self):
        with open(os.path.join(ROOT, "05_api_contract_example.json"), "rb") as fh:
            raw = fh.read()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "no BOM expected")
        json.loads(raw.decode("utf-8"), parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))


class TestStationErrors(unittest.TestCase):
    def test_missing_station_id(self):
        r = vc.lookup_virtual_station({"dataset_id": DS[0], "dataset_version": DS[1]}, REGISTRY)
        self.assertEqual(r["error"]["code"], "VHS-E001")
        self.assertIsNone(r["prediction"])

    def test_blank_station_id(self):
        r = vc.lookup_virtual_station({"target_station_id": "  ", "dataset_id": DS[0], "dataset_version": DS[1]}, REGISTRY)
        self.assertEqual(r["error"]["code"], "VHS-E001")

    def test_invalid_station_format(self):
        r = vc.lookup_virtual_station({"target_station_id": "../../etc;DROP", "dataset_id": DS[0], "dataset_version": DS[1]}, REGISTRY)
        self.assertEqual(r["error"]["code"], "VHS-E003")

    def test_unknown_station(self):
        r = vc.lookup_virtual_station({"target_station_id": "SYNTHETIC_EXAMPLE_STN_404", "dataset_id": DS[0], "dataset_version": DS[1]}, REGISTRY)
        self.assertEqual(r["error"]["code"], "VHS-E002")
        self.assertEqual(vc.validate_response(r), [])

    def test_unknown_dataset_version(self):
        r = vc.lookup_virtual_station({"target_station_id": BASE["target_station_id"], "dataset_id": DS[0], "dataset_version": "9.9"}, REGISTRY)
        self.assertEqual(r["error"]["code"], "VHS-E004")

    def test_known_station_returns_not_authorized(self):
        r = vc.lookup_virtual_station({"target_station_id": BASE["target_station_id"], "dataset_id": DS[0], "dataset_version": DS[1]}, REGISTRY)
        self.assertNotIn("error", r)
        self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED")
        self.assertIsNone(r["prediction"])


class TestPredictionAuthorization(unittest.TestCase):
    def test_prediction_without_authorization_rejected(self):
        r = copy.deepcopy(BASE)
        r["prediction"] = {"data_class": "SYNTHETIC_DEMO_ONLY", "values": [1.0]}
        codes = [c for c, _ in vc.validate_response(r)]
        self.assertIn("VHS-E010", codes)

    def test_unauthorized_must_say_not_authorized(self):
        r = copy.deepcopy(BASE)
        r["prediction_authorized"] = {"status": "UNKNOWN", "authorization_ref": None}
        self.assertIn("VHS-E011", [c for c, _ in vc.validate_response(r)])

    def test_registry_cannot_smuggle_prediction(self):
        rec = copy.deepcopy(BASE)
        rec["prediction"] = {"data_class": "SYNTHETIC_DEMO_ONLY", "values": [9.0]}
        rec["prediction_authorized"] = {"status": "CONDITIONAL", "authorization_ref": None}
        reg = {DS: {rec["target_station_id"]: rec}}
        r = vc.lookup_virtual_station({"target_station_id": rec["target_station_id"], "dataset_id": DS[0], "dataset_version": DS[1]}, reg)
        self.assertEqual(r["prediction_authorized"]["status"], "NOT_AUTHORIZED")
        self.assertIsNone(r["prediction"])

    def test_s0_policy_rejects_non_synthetic_authorized_prediction(self):
        r = copy.deepcopy(EXAMPLES["D_synthetic_demo_only_prediction"])
        r["dataset_id"] = "SOME_REAL_LOOKING_DATASET"
        self.assertIn("VHS-E010", [c for c, _ in vc.validate_response(r)])
        r2 = copy.deepcopy(EXAMPLES["D_synthetic_demo_only_prediction"])
        r2["prediction"]["data_class"] = "VALIDATED_PRODUCT_FUTURE"
        self.assertIn("VHS-E010", [c for c, _ in vc.validate_response(r2)])


class TestSealedQLeakGuard(unittest.TestCase):
    def test_response_with_observed_q_rejected(self):
        for key in ("qobs", "q_obs", "observed_discharge", "target_q", "sealed_target_q", "q_mean", "runoff_ratio", "fdc_slope"):
            r = copy.deepcopy(BASE)
            r["data_readiness"][key] = [0.0]
            self.assertIn("VHS-E008", [c for c, _ in vc.validate_response(r)], key)

    def test_response_with_skill_metric_rejected(self):
        for key in ("nse", "KGE", "test_nse", "rmse"):
            r = copy.deepcopy(BASE)
            r["warnings_meta"] = {key: 0.5}
            self.assertIn("VHS-E009", [c for c, _ in vc.validate_response(r)], key)

    def test_benign_keys_not_flagged(self):
        r = copy.deepcopy(BASE)
        r["data_readiness"]["quality_flags_summary"] = "UNKNOWN"
        r["data_readiness"]["target_series_access"] = {"role": "SEALED_TARGET_Q", "exposed": False}
        self.assertEqual(vc.validate_response(r), [])

    def test_error_response_with_q_rejected(self):
        e = vc.make_error("VHS-E002", "x")
        e["error"]["qobs"] = 1.0
        self.assertIn("VHS-E008", [c for c, _ in vc.validate_response(e)])

    def test_log_guard(self):
        self.assertTrue(vc.assert_log_safe({"event": "lookup", "station": "SYNTHETIC_EXAMPLE_STN_A001", "status": "NOT_AUTHORIZED"}))
        self.assertTrue(vc.assert_log_safe("lookup SYNTHETIC_EXAMPLE_STN_A001 status=NOT_AUTHORIZED"))
        with self.assertRaises(vc.ContractError) as cm:
            vc.assert_log_safe({"event": "debug", "qobs": 12.3})
        self.assertEqual(cm.exception.code, "VHS-E008")
        with self.assertRaises(vc.ContractError):
            vc.assert_log_safe("debug target qobs=12.3 at day 5")
        with self.assertRaises(vc.ContractError):
            vc.assert_log_safe('{"discharge": 4.5}')
        with self.assertRaises(vc.ContractError) as cm2:
            vc.assert_log_safe({"event": "eval", "nse": 0.7})
        self.assertEqual(cm2.exception.code, "VHS-E009")


class TestCRS(unittest.TestCase):
    def test_missing_crs_rejected(self):
        r = copy.deepcopy(BASE)
        del r["coordinate_reference_system"]
        self.assertIn("VHS-E005", [c for c, _ in vc.validate_response(r)])
        r["coordinate_reference_system"] = None
        self.assertIn("VHS-E005", [c for c, _ in vc.validate_response(r)])
        r["coordinate_reference_system"] = {}
        self.assertIn("VHS-E005", [c for c, _ in vc.validate_response(r)])

    def test_epsg_missing_or_unregistered(self):
        r = copy.deepcopy(BASE)
        r["coordinate_reference_system"].pop("epsg")
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_response(r)])
        r["coordinate_reference_system"]["epsg"] = 99999
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_response(r)])

    def test_units_axis_mismatch(self):
        r = copy.deepcopy(EXAMPLES["B_europe_epsg3035_blocked_admission"])
        r["coordinate_reference_system"]["units"] = "degree"   # 把米制 3035 当度数 —— B1A 曾犯过的错误
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_response(r)])
        r = copy.deepcopy(EXAMPLES["B_europe_epsg3035_blocked_admission"])
        r["coordinate_reference_system"]["coordinate_axis_order_in_payload"] = ["latitude", "longitude"]
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_response(r)])

    def test_degree_range(self):
        r = copy.deepcopy(BASE)
        r["coordinate_reference_system"]["coordinates"] = [4500000.0, 2800000.0]  # 米值塞进度数 CRS
        self.assertIn("VHS-E006", [c for c, _ in vc.validate_response(r)])

    def test_area_of_use_mismatch(self):
        r = copy.deepcopy(EXAMPLES["B_europe_epsg3035_blocked_admission"])
        r["region_scope"] = "CENTRAL_ASIA_SYNTHETIC"   # EPSG:3035 不适用于新疆/中亚
        self.assertIn("VHS-E007", [c for c, _ in vc.validate_response(r)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
