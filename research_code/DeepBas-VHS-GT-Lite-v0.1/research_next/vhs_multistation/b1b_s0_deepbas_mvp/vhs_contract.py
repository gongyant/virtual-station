# -*- coding: utf-8 -*-
"""DeepBas-VHS 候选 JSON 契约的最小验证器（仅 Python 标准库）。

状态：PROPOSED（VHS-NEXT-B1B-S0 候选草案，等待 DeepBas 平台组确认；不是已完成的平台集成）。
本模块不读取任何真实数据文件、不读取真实流量、不训练、不评分。
仅用于：
  1) 校验响应 JSON 是否符合候选契约；
  2) 拒绝在响应/日志中出现观测流量（封存目标 Q）及其衍生统计/技能指标字段；
  3) 在未授权预测时强制 prediction=null 且状态 NOT_AUTHORIZED；
  4) 强制坐标参考系显式声明（EPSG、轴顺序、单位）。
"""
import json
import re

API_VERSION = "vhs-contract-0.1.0-draft"
STATUS_VALUES = ("PASS", "CONDITIONAL", "BLOCKED", "UNKNOWN", "NOT_AUTHORIZED")
SCIENCE_STAGES = ("METADATA_ONLY", "ADMISSION_REVIEW", "PREDICTION_PROTOCOL_FROZEN",
                  "INDEPENDENTLY_VALIDATED", "SYNTHETIC_DEMO_ONLY")
DATA_ROLES = ("OPEN_METADATA", "OPEN_FORCING", "SEALED_TARGET_Q",
              "AUTHORIZED_DONOR_Q_FUTURE", "QUARANTINE", "UNKNOWN")
SYNTHETIC_PREFIX = "SYNTHETIC_EXAMPLE"

ERROR_CODES = {
    "VHS-E001": "STATION_ID_MISSING",
    "VHS-E002": "STATION_NOT_FOUND",
    "VHS-E003": "STATION_ID_INVALID_FORMAT",
    "VHS-E004": "DATASET_OR_VERSION_MISMATCH",
    "VHS-E005": "CRS_MISSING",
    "VHS-E006": "CRS_INVALID",
    "VHS-E007": "CRS_AREA_OF_USE_MISMATCH",
    "VHS-E008": "SEALED_TARGET_Q_LEAK_BLOCKED",
    "VHS-E009": "FORBIDDEN_SKILL_METRIC_FIELD",
    "VHS-E010": "PREDICTION_NOT_AUTHORIZED_BUT_PRESENT",
    "VHS-E011": "SCHEMA_VIOLATION",
    "VHS-E012": "UNSUPPORTED_API_VERSION",
}

# 已知 CRS 的最小登记（只列契约示例所需；未登记的 EPSG 一律 CRS_INVALID，需平台组扩充）
KNOWN_CRS = {
    4326: {"units": "degree", "authority_axis_order": ["latitude", "longitude"],
           "area_scope": "GLOBAL"},
    3035: {"units": "metre", "authority_axis_order": ["northing", "easting"],
           "area_scope": "EUROPE"},
    2056: {"units": "metre", "authority_axis_order": ["easting", "northing"],
           "area_scope": "SWITZERLAND"},
}
AXIS_NAMES = ("latitude", "longitude", "easting", "northing")

# 观测流量 / 封存目标 Q / 由 Q 派生的统计与技能指标：响应与日志中一律禁止出现的键名
FORBIDDEN_Q_KEY_PATTERNS = [
    r"^q$", r"^qobs.*", r"^q_obs.*", r"^obs(erved)?_?(q($|_)|discharge|flow|runoff|streamflow).*",
    r".*target_?q($|_).*", r".*sealed_?(target_)?q($|_).*", r"^(q|discharge|runoff|streamflow)_(mean|std|var|min|max|median|p\d+|quantile.*|cv)$",
    r".*(flow_duration|fdc).*", r".*runoff_ratio.*", r".*baseflow_index.*",
    r"^(mean|max|min|std|var)_(q|discharge|runoff|streamflow)$",
    r"^q_?(mean|max|min|std|var|peak|5|95)$", r"^hydro(logical)?_signature.*",
]
FORBIDDEN_METRIC_KEY_PATTERNS = [r"^nse.*", r".*_nse$", r"^kge.*", r".*_kge$", r"^rmse.*", r"^mse$",
                                 r"^r2$", r"^pbias.*", r"^skill.*", r"^correlation.*", r"^pearson.*"]
# 日志文本中禁止出现的 Q 赋值样式，例如 "qobs=12.3"、"\"discharge\": 4.5"
FORBIDDEN_LOG_TEXT = re.compile(
    r"(?i)\b(qobs|q_obs|observed_q|target_q|discharge|streamflow|runoff)\b\"?\s*[:=]\s*-?\d")

_Q_RES = [re.compile(p, re.I) for p in FORBIDDEN_Q_KEY_PATTERNS]
_M_RES = [re.compile(p, re.I) for p in FORBIDDEN_METRIC_KEY_PATTERNS]


class ContractError(Exception):
    def __init__(self, code, detail):
        super().__init__("%s %s: %s" % (code, ERROR_CODES.get(code, "?"), detail))
        self.code = code
        self.detail = detail


def _walk_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = "%s.%s" % (path, k) if path else str(k)
            yield str(k), p
            yield from _walk_keys(v, p)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk_keys(v, "%s[%d]" % (path, i))


def scan_forbidden_fields(obj):
    """返回 [(code, path)]：封存目标 Q / 派生统计 / 技能指标键名。"""
    hits = []
    for key, path in _walk_keys(obj):
        if any(r.match(key) for r in _Q_RES):
            hits.append(("VHS-E008", path))
        elif any(r.match(key) for r in _M_RES):
            hits.append(("VHS-E009", path))
    return hits


def assert_log_safe(record):
    """日志防泄漏：record 可以是 dict 或 str。发现禁止字段/赋值样式即抛 ContractError。"""
    if isinstance(record, dict):
        hits = scan_forbidden_fields(record)
        if hits:
            raise ContractError(hits[0][0], "log field %s" % hits[0][1])
        text = json.dumps(record, ensure_ascii=False)
    else:
        text = str(record)
    if FORBIDDEN_LOG_TEXT.search(text):
        raise ContractError("VHS-E008", "log text contains discharge-like assignment")
    return True


def validate_crs(crs, region_scope):
    errs = []
    if crs is None or not isinstance(crs, dict) or not crs:
        return [("VHS-E005", "coordinate_reference_system missing")]
    epsg = crs.get("epsg")
    if not isinstance(epsg, int) or epsg not in KNOWN_CRS:
        return [("VHS-E006", "epsg missing/unregistered: %r" % (epsg,))]
    ref = KNOWN_CRS[epsg]
    order = crs.get("coordinate_axis_order_in_payload")
    if (not isinstance(order, list) or len(order) != 2 or any(a not in AXIS_NAMES for a in order)):
        errs.append(("VHS-E006", "coordinate_axis_order_in_payload must name 2 axes"))
    if crs.get("units") != ref["units"]:
        errs.append(("VHS-E006", "units %r inconsistent with EPSG:%d (%s)" % (crs.get("units"), epsg, ref["units"])))
    if crs.get("epsg_authority_axis_order") != ref["authority_axis_order"]:
        errs.append(("VHS-E006", "epsg_authority_axis_order must be %r" % ref["authority_axis_order"]))
    if ref["units"] == "degree" and isinstance(order, list) and set(order) - {"latitude", "longitude"}:
        errs.append(("VHS-E006", "degree CRS cannot use easting/northing axes"))
    if ref["units"] == "metre" and isinstance(order, list) and set(order) - {"easting", "northing"}:
        errs.append(("VHS-E006", "projected CRS cannot use latitude/longitude axes"))
    coords = crs.get("coordinates")
    if not isinstance(coords, list) or len(coords) != 2 or not all(isinstance(c, (int, float)) for c in coords):
        errs.append(("VHS-E006", "coordinates must be 2 numbers in declared axis order"))
    elif ref["units"] == "degree" and isinstance(order, list) and len(order) == 2:
        for name, val in zip(order, coords):
            lim = 90 if name == "latitude" else 180
            if abs(val) > lim:
                errs.append(("VHS-E006", "%s=%r out of degree range" % (name, val)))
    if ref["area_scope"] not in ("GLOBAL", region_scope):
        errs.append(("VHS-E007", "EPSG:%d area scope %s != region_scope %s" % (epsg, ref["area_scope"], region_scope)))
    return errs


REQUIRED_TOP = ["api_version", "dataset_id", "dataset_version", "target_station_id",
                "region_scope", "coordinate_reference_system", "catchment_area_km2",
                "topology_status", "upstream_donors", "nonconnected_controls",
                "data_readiness", "license_status", "science_stage",
                "prediction_authorized", "prediction", "evidence_refs", "warnings"]


def _status_ok(v):
    return isinstance(v, dict) and v.get("status") in STATUS_VALUES


def validate_response(resp, policy="S0"):
    """返回错误列表 [(code, message)]；空列表表示通过。policy='S0' 表示本轮（无真实预测授权）。"""
    errs = []
    if not isinstance(resp, dict):
        return [("VHS-E011", "response must be an object")]
    if resp.get("response_type") == "error":
        e = resp.get("error") or {}
        if e.get("code") not in ERROR_CODES:
            errs.append(("VHS-E011", "error.code not registered"))
        if resp.get("prediction", None) is not None:
            errs.append(("VHS-E010", "error response must not carry prediction"))
        errs += [(c, "forbidden field at " + p) for c, p in scan_forbidden_fields(resp)]
        return errs
    for k in REQUIRED_TOP:
        if k not in resp:
            errs.append(("VHS-E005" if k == "coordinate_reference_system" else "VHS-E011", "missing field: " + k))
    if errs:
        return errs
    if resp["api_version"] != API_VERSION:
        errs.append(("VHS-E012", "api_version %r" % resp["api_version"]))
    sid = resp["target_station_id"]
    if not isinstance(sid, str) or not sid.strip():
        errs.append(("VHS-E001", "target_station_id empty"))
    errs += validate_crs(resp["coordinate_reference_system"], resp["region_scope"])
    area = resp["catchment_area_km2"]
    if not (isinstance(area, dict) and area.get("status") in STATUS_VALUES and "value" in area and "source" in area):
        errs.append(("VHS-E011", "catchment_area_km2 must be {value,status,source}"))
    for k in ("topology_status", "data_readiness", "license_status"):
        if not _status_ok(resp[k]):
            errs.append(("VHS-E011", "%s.status must be one of %s" % (k, STATUS_VALUES)))
    if resp["science_stage"] not in SCIENCE_STAGES:
        errs.append(("VHS-E011", "science_stage invalid"))
    for lst in ("upstream_donors", "nonconnected_controls"):
        if not isinstance(resp[lst], list):
            errs.append(("VHS-E011", lst + " must be a list"))
            continue
        for i, d in enumerate(resp[lst]):
            if not (isinstance(d, dict) and d.get("station_id") and _status_ok(d.get("relation_status"))
                    and isinstance(d.get("evidence_level"), str)):
                errs.append(("VHS-E011", "%s[%d] needs station_id, relation_status.status, evidence_level" % (lst, i)))
            if isinstance(d, dict) and d.get("data_role") not in DATA_ROLES:
                errs.append(("VHS-E011", "%s[%d].data_role invalid" % (lst, i)))
    if not isinstance(resp["evidence_refs"], list) or not isinstance(resp["warnings"], list):
        errs.append(("VHS-E011", "evidence_refs/warnings must be lists"))
    # 预测授权规则
    auth = resp["prediction_authorized"]
    pred = resp["prediction"]
    if not isinstance(auth, dict) or auth.get("status") not in STATUS_VALUES:
        errs.append(("VHS-E011", "prediction_authorized must be {status, authorization_ref}"))
    else:
        if auth["status"] != "PASS":
            if pred is not None:
                errs.append(("VHS-E010", "prediction must be null unless prediction_authorized.status == PASS"))
            if auth["status"] != "NOT_AUTHORIZED":
                errs.append(("VHS-E011", "unauthorized prediction must report NOT_AUTHORIZED"))
        elif policy == "S0":
            synthetic = (str(resp["dataset_id"]).startswith(SYNTHETIC_PREFIX)
                         and resp["science_stage"] == "SYNTHETIC_DEMO_ONLY"
                         and isinstance(pred, dict) and pred.get("data_class") == "SYNTHETIC_DEMO_ONLY")
            if not synthetic:
                errs.append(("VHS-E010", "S0 policy: only SYNTHETIC_DEMO_ONLY predictions may be non-null"))
    errs += [(c, "forbidden field at " + p) for c, p in scan_forbidden_fields(resp)]
    return errs


def make_error(code, detail, request_id="SYNTHETIC_EXAMPLE_REQ"):
    return {"api_version": API_VERSION, "response_type": "error", "request_id": request_id,
            "error": {"code": code, "name": ERROR_CODES[code], "detail": detail},
            "prediction": None}


STATION_ID_RE = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")


def lookup_virtual_station(request, registry):
    """合成参考实现：F1/F2 元数据查询。registry 为纯合成字典；绝不访问真实数据。"""
    sid = request.get("target_station_id")
    if sid is None or (isinstance(sid, str) and not sid.strip()):
        return make_error("VHS-E001", "target_station_id is required")
    if not isinstance(sid, str) or not STATION_ID_RE.match(sid):
        return make_error("VHS-E003", "target_station_id has invalid format")
    ds = (request.get("dataset_id"), request.get("dataset_version"))
    rec = registry.get(ds, {}).get(sid)
    if registry.get(ds) is None:
        return make_error("VHS-E004", "unknown dataset/version %r" % (ds,))
    if rec is None:
        return make_error("VHS-E002", "station %s not in %s %s" % (sid, ds[0], ds[1]))
    resp = json.loads(json.dumps(rec))  # 深拷贝
    if resp.get("prediction_authorized", {}).get("status") != "PASS":
        resp["prediction_authorized"] = {"status": "NOT_AUTHORIZED",
                                         "authorization_ref": None,
                                         "reason": "no independent prediction authorization for this station"}
        resp["prediction"] = None
    errs = validate_response(resp)
    if errs:
        return make_error(errs[0][0], errs[0][1])
    return resp
