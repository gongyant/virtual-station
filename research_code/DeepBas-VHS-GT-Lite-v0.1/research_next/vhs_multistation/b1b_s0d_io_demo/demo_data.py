# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 纯合成演示数据（SYNTHETIC_DEMO_ONLY / PROPOSED）。

本文件中的站点、坐标、河网、面积、QC 元数据、许可与拓扑认证状态全部为人工虚构，
不对应任何真实水文站，不来自任何真实数据文件，不含任何真实流量或性能指标。
关系（上游/下游/连通）只由有向边定义；节点坐标仅供示意图绘制，程序不用坐标判断关系。
边方向约定：edge["from"] -> edge["to"] 表示沿水流方向（上游 -> 下游）。
"""

DATA_CLASS = "SYNTHETIC_DEMO_ONLY"
DATASET_ID = "SYNTHETIC_EXAMPLE_S0D_DEMO"
DATASET_VERSION = "0.1-synthetic"
REGION_SCOPE = "CENTRAL_ASIA_SYNTHETIC"
SYNTHETIC_WINDOW = ("2020-01-01", "2020-12-31")   # 合成演示允许的日期窗口（任意选定，非真实资料期）
MAX_SPAN_DAYS = 92                                  # 单次合成演示最长天数（任意选定的演示限制）
DEFAULT_DEMO_RANGE = ("2020-01-01", "2020-01-14")

EDGE_KINDS = ("natural", "artificial_transfer")
SNAP_STATUSES = ("CERTIFIED", "UNCERTIFIED", "UNKNOWN")


def _n(nid, lat, lon, label):
    return {"id": nid, "lat": lat, "lon": lon, "label": label}


def _e(eid, src, dst, kind="natural", snap="CERTIFIED", note=""):
    return {"id": eid, "from": src, "to": dst, "kind": kind, "snap_status": snap, "note": note}


# ---------------------------------------------------------------- 主合成图（含多个弱连通分量）
MAIN_GRAPH = {
    "graph_id": "SYNTHETIC_MAIN_GRAPH",
    "data_class": DATA_CLASS,
    "edge_direction": "from -> to = 沿水流方向（上游 -> 下游）",
    "nodes": [
        _n("DEMO_HEAD_1", 41.20, 79.20, "主干源头"),
        _n("DEMO_MID_1", 40.80, 79.60, "主干中游汇合"),
        _n("DEMO_TRIB_2", 41.35, 79.95, "支流源头(snap未认证)"),
        _n("DEMO_TRIB_1", 41.05, 79.85, "支流1"),
        _n("DEMO_TRIB_T", 40.20, 79.70, "直接汇入目标的支流"),
        _n("DEMO_TARGET_A", 40.50, 80.00, "目标断面A"),
        _n("DEMO_DOWN_1", 40.20, 80.40, "目标下游"),
        _n("DEMO_TRIB_DS", 40.65, 80.65, "汇入下游的支流"),
        _n("DEMO_OUTLET", 39.90, 80.80, "合成出口"),
        _n("DEMO_CANAL_SRC", 40.95, 78.80, "人工输水源(邻近水系)"),
        _n("DEMO_CANAL_BASIN_OUT", 40.55, 78.60, "邻近水系出口"),
        _n("DEMO_CTRL_1", 39.60, 78.90, "独立水系X上游"),
        _n("DEMO_CTRL_2", 39.40, 79.30, "独立水系X出口"),
        _n("DEMO_CTRL_NEAR", 40.53, 80.04, "独立水系Y(地理最近)"),
    ],
    "edges": [
        _e("E01", "DEMO_HEAD_1", "DEMO_MID_1"),
        _e("E02", "DEMO_TRIB_2", "DEMO_TRIB_1", snap="UNCERTIFIED", note="SYNTHETIC: 站点 snapping 未认证"),
        _e("E03", "DEMO_TRIB_1", "DEMO_MID_1", note="SYNTHETIC: 支流汇入主干"),
        _e("E04", "DEMO_MID_1", "DEMO_TARGET_A"),
        _e("E05", "DEMO_TARGET_A", "DEMO_DOWN_1"),
        _e("E06", "DEMO_TRIB_DS", "DEMO_DOWN_1", note="SYNTHETIC: 支流在目标下游汇入"),
        _e("E07", "DEMO_DOWN_1", "DEMO_OUTLET"),
        _e("E08", "DEMO_CANAL_SRC", "DEMO_CANAL_BASIN_OUT"),
        _e("E09", "DEMO_CANAL_SRC", "DEMO_MID_1", kind="artificial_transfer",
           note="SYNTHETIC: 人工输水渠，调度未知"),
        _e("E10", "DEMO_CTRL_1", "DEMO_CTRL_2"),
        _e("E11", "DEMO_TRIB_T", "DEMO_TARGET_A", note="SYNTHETIC: 支流直接汇入目标断面"),
    ],
}

# ---------------------------------------------------------------- 环路测试图（故意错误的拓扑）
CYCLE_GRAPH = {
    "graph_id": "SYNTHETIC_CYCLE_TEST_GRAPH",
    "data_class": DATA_CLASS,
    "edge_direction": "from -> to = 沿水流方向（上游 -> 下游）",
    "nodes": [
        _n("DEMO_CYCLE_X", 43.00, 76.00, "环路测试X"),
        _n("DEMO_CYCLE_Y", 43.30, 76.20, "环路测试Y"),
        _n("DEMO_CYCLE_Z", 43.10, 76.50, "环路测试Z"),
        _n("DEMO_CYCLE_W", 43.50, 75.90, "环路入流W"),
    ],
    "edges": [
        _e("C1", "DEMO_CYCLE_Y", "DEMO_CYCLE_X"),
        _e("C2", "DEMO_CYCLE_Z", "DEMO_CYCLE_Y"),
        _e("C3", "DEMO_CYCLE_X", "DEMO_CYCLE_Z", note="SYNTHETIC: 人为制造的环路（X->Z->Y->X）"),
        _e("C4", "DEMO_CYCLE_W", "DEMO_CYCLE_Y"),
    ],
}

# ---------------------------------------------------------------- 准入场景图（孤立节点）
AUDIT_GRAPH = {
    "graph_id": "SYNTHETIC_AUDIT_SCENARIO_GRAPH",
    "data_class": DATA_CLASS,
    "edge_direction": "from -> to = 沿水流方向（上游 -> 下游）",
    "nodes": [
        _n("DEMO_QC_IDEAL", 42.00, 81.00, "QC理想(合成)"),
        _n("DEMO_QC_LICENSE_UNKNOWN", 42.00, 81.30, "许可未知"),
        _n("DEMO_QC_SNAP_UNCERT", 42.00, 81.60, "snap未认证"),
        _n("DEMO_QC_GAPS", 42.30, 81.00, "有缺测"),
        _n("DEMO_QC_MISSING", 42.30, 81.30, "QC缺失"),
        _n("DEMO_QC_UNKNOWN_FIELDS", 42.30, 81.60, "未知字段/缺证据"),
    ],
    "edges": [],
}

GRAPHS = {g["graph_id"]: g for g in (MAIN_GRAPH, CYCLE_GRAPH, AUDIT_GRAPH)}

_QC_COMPLETE = {"completeness_class": "COMPLETE", "qc_flags_reviewed": True,
                "metadata_fields_complete": True, "source": "SYNTHETIC"}


def _st(sid, name, graph_id, basin_id, basin_name, area, role="NETWORK_NODE", qc="DEFAULT",
        license_status="UNKNOWN", topology_certification="CERTIFIED",
        target_q_access="NOT_APPLICABLE_SYNTHETIC", evidence_refs="DEFAULT"):
    g = GRAPHS[graph_id]
    node = [n for n in g["nodes"] if n["id"] == sid][0]
    return {
        "station_id": sid,
        "station_name": "SYNTHETIC " + name,
        "graph_id": graph_id,
        "basin_id": basin_id,
        "basin_name": "SYNTHETIC " + basin_name,
        "coordinates_lat_lon": [node["lat"], node["lon"]],
        "catchment_area_km2": area,
        "role": role,
        "qc": dict(_QC_COMPLETE) if qc == "DEFAULT" else qc,
        "license_status": license_status,
        "topology_certification": topology_certification,
        "target_q_access": target_q_access,
        "evidence_refs": ([{"ref": "S0D_SYNTHETIC_EVIDENCE_" + sid, "level": "PROPOSED"}]
                          if evidence_refs == "DEFAULT" else evidence_refs),
        "data_class": DATA_CLASS,
    }


_M, _C, _A = "SYNTHETIC_MAIN_GRAPH", "SYNTHETIC_CYCLE_TEST_GRAPH", "SYNTHETIC_AUDIT_SCENARIO_GRAPH"

STATION_LIST = [
    _st("DEMO_TARGET_A", "目标断面 A", _M, "SYN_BASIN_MAIN", "主干水系", 1200.0, role="TARGET",
        license_status="UNKNOWN", topology_certification="PATH_OK_SNAP_UNCERTIFIED", target_q_access="SEALED"),
    _st("DEMO_HEAD_1", "主干源头站", _M, "SYN_BASIN_MAIN", "主干水系", 300.0),
    _st("DEMO_MID_1", "主干中游汇合站", _M, "SYN_BASIN_MAIN", "主干水系", 900.0),
    _st("DEMO_TRIB_1", "支流站 1", _M, "SYN_BASIN_MAIN", "主干水系", 250.0),
    _st("DEMO_TRIB_2", "支流源头站 2", _M, "SYN_BASIN_MAIN", "主干水系", 120.0,
        topology_certification="PATH_OK_SNAP_UNCERTIFIED"),
    _st("DEMO_TRIB_T", "直接汇入目标断面的支流站", _M, "SYN_BASIN_MAIN", "主干水系", 180.0),
    _st("DEMO_DOWN_1", "目标下游站", _M, "SYN_BASIN_MAIN", "主干水系", 1600.0),
    _st("DEMO_TRIB_DS", "下游汇入支流站", _M, "SYN_BASIN_MAIN", "主干水系", 200.0),
    _st("DEMO_OUTLET", "合成出口站", _M, "SYN_BASIN_MAIN", "主干水系", 2100.0),
    _st("DEMO_CANAL_SRC", "人工输水源头站", _M, "SYN_BASIN_CANAL", "邻近水系", 400.0,
        topology_certification="NOT_CERTIFIED"),
    _st("DEMO_CANAL_BASIN_OUT", "邻近水系出口站", _M, "SYN_BASIN_CANAL", "邻近水系", 650.0),
    _st("DEMO_CTRL_1", "独立水系 X 上游站", _M, "SYN_BASIN_X", "独立水系 X", 500.0),
    _st("DEMO_CTRL_2", "独立水系 X 出口站", _M, "SYN_BASIN_X", "独立水系 X", 800.0),
    _st("DEMO_CTRL_NEAR", "独立水系 Y 站（地理最近）", _M, "SYN_BASIN_Y", "独立水系 Y", 90.0),
    _st("DEMO_CYCLE_X", "环路测试站 X", _C, "SYN_BASIN_CYCLE", "环路测试水系", 700.0, role="TARGET",
        topology_certification="NOT_CERTIFIED"),
    _st("DEMO_CYCLE_Y", "环路测试站 Y", _C, "SYN_BASIN_CYCLE", "环路测试水系", 500.0),
    _st("DEMO_CYCLE_Z", "环路测试站 Z", _C, "SYN_BASIN_CYCLE", "环路测试水系", 300.0),
    _st("DEMO_CYCLE_W", "环路入流站 W", _C, "SYN_BASIN_CYCLE", "环路测试水系", 150.0),
    _st("DEMO_QC_IDEAL", "QC 理想场景", _A, "SYN_BASIN_QC_1", "准入场景 1", 100.0, role="AUDIT_SCENARIO",
        license_status="PERMITTED", topology_certification="CERTIFIED"),
    _st("DEMO_QC_LICENSE_UNKNOWN", "数据完整但许可未知", _A, "SYN_BASIN_QC_2", "准入场景 2", 100.0,
        role="AUDIT_SCENARIO", license_status="UNKNOWN", topology_certification="CERTIFIED"),
    _st("DEMO_QC_SNAP_UNCERT", "拓扑路径通过但 snapping 未认证", _A, "SYN_BASIN_QC_3", "准入场景 3", 100.0,
        role="AUDIT_SCENARIO", license_status="PERMITTED", topology_certification="PATH_OK_SNAP_UNCERTIFIED"),
    _st("DEMO_QC_GAPS", "有缺测但不影响元数据查询", _A, "SYN_BASIN_QC_4", "准入场景 4", 100.0,
        role="AUDIT_SCENARIO", license_status="PERMITTED",
        qc={"completeness_class": "PARTIAL_GAPS", "qc_flags_reviewed": True,
            "metadata_fields_complete": True, "source": "SYNTHETIC"}),
    _st("DEMO_QC_MISSING", "QC 元数据缺失", _A, "SYN_BASIN_QC_5", "准入场景 5", 100.0,
        role="AUDIT_SCENARIO", license_status="PERMITTED", qc=None),
    _st("DEMO_QC_UNKNOWN_FIELDS", "含未知字段且缺证据", _A, "SYN_BASIN_QC_6", "准入场景 6", 100.0,
        role="AUDIT_SCENARIO", license_status="PERMITTED",
        qc={"completeness_class": "COMPLETE", "qc_flags_reviewed": True, "metadata_fields_complete": True,
            "source": "SYNTHETIC", "vendor_flag_x": "?", "legacy_code": 7},
        evidence_refs=[]),
]

STATIONS = {s["station_id"]: s for s in STATION_LIST}
