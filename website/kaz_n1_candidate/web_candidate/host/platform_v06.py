"""
platform_v06.py  --  VHS v0.6 four-layer research platform API
=============================================================

Four layers, one research narrative:

    research overview -> spatial layers -> data layer -> model layer
        -> results layer (station series / evaluation / spatial / report)

This module NEVER produces a simulated value.  Every response that belongs to
the results layer carries qsim = null, prediction = null and
evaluation.status = NOT_EVALUATED unless a real, authorized model run exists
(none does).  The two spatial states are kept apart:

* GIS_DISPLAY_READY        real spatial data loaded and safe to draw
* HYDROLOGICALLY_CERTIFIED physical relation verified

A drawn river does not certify a hydrological connection.  Unverified U/T/W
relations stay GRAPH_TENTATIVE / UNKNOWN.

Dataset separation is absolute: every identifier is namespaced
(SYRDARYA:16037 / LAMAHCE:58) and no numeric id is ever matched across
datasets.
"""

import hashlib
import json
import os
import re
import time

import http_policy
import syrdarya_adapter as SA
from research import baselines as RB

APP = os.path.dirname(os.path.abspath(__file__))
PLATFORM_VERSION = "0.6.0"
PLATFORM_BUILD = "v0.6.0-four-layer-20261024"
RULES_VERSION = "VHS-4L-0.6.0"
CONFIG_DIR = os.path.join(APP, "var", "model_configs")
MAX_BODY = 1 << 18
CFG_NAME = re.compile(r"^[A-Za-z0-9_-]{1,48}")

DATASETS = {
    "SYRDARYA": {
        "id": "SYRDARYA", "title": "Syr Darya 锡尔河下游",
        "short": "Syr Darya", "namespace": "SYRDARYA",
        "crs": "GIS_PENDING",
        "authorization": "TEACHER_CSV_READ_ONLY_LOCAL_DISPLAY",
        "task": "河段水量平衡与缺测重建基线（老师提供的 16037 -> 16039 案例）",
    },
    "LAMAHCE": {
        "id": "LAMAHCE", "title": "LamaH-CE 欧洲河网",
        "short": "LamaH-CE", "namespace": "LAMAHCE",
        "crs": "EPSG:3035",
        "authorization": "OPEN_METADATA_ONLY",
        "task": "大规模站网拓扑与 U/T/W 供数关系筛查（仅开放元数据）",
    },
}

DISPLAY_STATUS_ZH = {
    "GIS_DISPLAY_READY": "真实空间数据已加载，可用于地图展示",
    "SYNTHETIC_PREVIEW_ONLY": "合成预览（非真实地理），仅供接口演示",
    "GIS_DISPLAY_NOT_AVAILABLE": "无经许可的真实空间数据，不绘制",
}
HYDRO_STATUS_ZH = {
    "HYDROLOGICALLY_CERTIFIED": "水文物理关系已认证",
    "GRAPH_TENTATIVE": "图级暂定关系（未认证）",
    "UNKNOWN": "物理关系未知",
    "NOT_APPLICABLE": "不适用",
}
MODEL_STATUS_ZH = {
    "IMPLEMENTED": "已实现",
    "DEFINED_ONLY": "仅定义（接口）",
    "NOT_TRAINED": "未训练",
    "TRAINED": "已完成训练",
    "VALIDATED": "已验证",
    "NOT_IMPLEMENTED": "未实现",
}

METRICS = ("NSE", "KGE", "RMSE", "MAE", "PBIAS")
RESULTS_NOTICE = ("模拟结果尚未生成：MODEL_EXECUTION = NOT_AUTHORIZED；"
                  "prediction = null；不填充任何模拟曲线或不确定性区间")

FUTURE_ARCHITECTURES = [
    {"id": "SYR-LIN", "name": "线性回归", "family": "LINEAR",
     "status": "NOT_IMPLEMENTED", "note": "预留：单变量 / 多变量线性基线"},
    {"id": "SYR-RIDGE", "name": "岭回归 Ridge", "family": "LINEAR",
     "status": "NOT_IMPLEMENTED", "note": "预留：加入 L2 正则化与正则系数配置"},
    {"id": "SYR-AR", "name": "简单时间序列（AR / ARIMA）", "family": "TS",
     "status": "NOT_IMPLEMENTED", "note": "预留：滞后阶数与平稳性检验"},
    {"id": "SYR-LSTM", "name": "LSTM", "family": "RNN",
     "status": "NOT_IMPLEMENTED", "note": "预留：序列长度、隐藏层、dropout"},
    {"id": "SYR-GRU", "name": "GRU", "family": "RNN",
     "status": "NOT_IMPLEMENTED", "note": "预留：与 LSTM 对照"},
    {"id": "SYR-TRF", "name": "Transformer", "family": "ATTENTION",
     "status": "NOT_IMPLEMENTED", "note": "预留：注意力头数、位置编码"},
    {"id": "SYR-GNN", "name": "图神经网络（河网 GNN）", "family": "GRAPH",
     "status": "NOT_IMPLEMENTED", "note": "预留：依赖经认证的河网拓扑，当前 GEOMETRY_VERIFIED = 0"},
    {"id": "SYR-PB", "name": "水文物理约束模型", "family": "HYBRID",
     "status": "NOT_IMPLEMENTED", "note": "预留：水量平衡约束、非负性、质量守恒"},
]


class PError(Exception):
    def __init__(self, status, code, message, **extra):
        super().__init__(message)
        self.status, self.code, self.message, self.extra = (
            status, code, message, extra)


def _err(e):
    body = {"error": e.code, "message": e.message, "status": e.status,
            "prediction": None, "platform_version": PLATFORM_VERSION}
    body.update(e.extra)
    return e.status, body


def _one(qs, name, required=False):
    v = qs.get(name)
    if v is None or v == [""]:
        if required:
            raise PError(400, "MISSING_PARAM",
                         "query parameter '%s' is required" % name)
        return None
    if len(v) > 1:
        raise PError(400, "BAD_PARAM", "parameter '%s' given twice" % name)
    return v[0]


def _int(qs, name, lo, hi, required=False):
    v = _one(qs, name, required)
    if v is None:
        return None
    try:
        iv = int(v)
    except ValueError:
        raise PError(400, "BAD_PARAM", "'%s' must be an integer" % name)
    if not lo <= iv <= hi:
        raise PError(400, "OUT_OF_RANGE",
                     "'%s' must be in [%d, %d]" % (name, lo, hi))
    return iv


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class PlatformApi:
    """Four-layer read-only API.  Never executes a model."""

    def __init__(self, store, syr, syr_api):
        self.store = store
        self.syr = syr
        self.syr_api = syr_api

    # -- envelope --------------------------------------------------------
    def env(self, dataset=None, **body):
        base = {
            "platform": "VHS v%s four-layer research platform" % PLATFORM_VERSION,
            "platform_version": PLATFORM_VERSION,
            "platform_build": PLATFORM_BUILD,
            "rules_version": RULES_VERSION,
            "generated_at": _now(),
            "dataset": dataset,
            "model_execution": RB.MODEL_EXECUTION,
            "prediction": None,
            "permissions": {k: v["status"] for k, v in
                            http_policy.PERMISSIONS.items()},
            "privilege_note": "展示历史观测不等于允许模型输入或预测",
        }
        if dataset == "SYRDARYA" and self.syr.snapshot is not None:
            base["snapshot"] = {
                "snapshot_id": self.syr.snapshot.snapshot_id,
                "loaded_at": self.syr.snapshot.loaded_at,
                "source_status": "VERIFIED_AT_LOAD",
            }
        elif dataset == "LAMAHCE":
            base["snapshot"] = {
                "snapshot_id": "lamah-metadata-%s" % (
                    self.store.manifest_sha or "unknown"),
                "loaded_at": self.store.loaded_at,
                "source_status": "STATIC_METADATA_ONLY",
            }
        base.update(body)
        return base

    def _ds(self, qs, default="SYRDARYA"):
        raw = (_one(qs, "dataset") or default).upper()
        if raw not in DATASETS:
            raise PError(400, "DATASET_NOT_FOUND",
                         "dataset must be SYRDARYA or LAMAHCE")
        return raw

    def _syr_station(self, raw):
        if not raw:
            raise PError(400, "MISSING_PARAM",
                         "query parameter 'station' is required")
        try:
            code = SA.parse_uid(raw)
        except ValueError as exc:
            raise PError(400, "BAD_STATION", str(exc).split(":")[0])
        if code not in self.syr.stations:
            raise PError(404, "STATION_NOT_FOUND",
                         "%s has no record in the teacher discharge file"
                         % SA.uid(code))
        return code

    # -- dispatch --------------------------------------------------------
    def handle(self, path, qs):
        try:
            return self._route(path.rstrip("/"), qs)
        except PError as e:
            return _err(e)

    def _route(self, path, qs):
        parts = [p for p in path.split("/") if p][2:]
        if not parts:
            return 200, self.env(None, routes=self.route_index())
        head = parts[0]
        if head == "overview":
            return 200, self.overview(qs)
        if head == "layers":
            if len(parts) > 1 and parts[1] == "features":
                return 200, self.layer_features(qs)
            return 200, self.layers(qs)
        if head == "data":
            sub = parts[1] if len(parts) > 1 else "catalog"
            return 200, self._data_route(sub, qs)
        if head == "model":
            sub = parts[1] if len(parts) > 1 else "registry"
            return 200, self._model_route(sub, qs)
        if head == "results":
            sub = parts[1] if len(parts) > 1 else "station"
            return self._results_route(sub, qs)
        if head == "evidence":
            return 200, self.evidence(qs)
        raise PError(404, "NOT_FOUND", "no v0.6 route %s" % path[:120])

    def route_index(self):
        return [
            {"path": "/api/v6/overview", "layer": "overview"},
            {"path": "/api/v6/layers", "layer": "layers"},
            {"path": "/api/v6/layers/features", "layer": "layers"},
            {"path": "/api/v6/data/catalog", "layer": "data"},
            {"path": "/api/v6/data/coverage", "layer": "data"},
            {"path": "/api/v6/data/remote-sensing", "layer": "data"},
            {"path": "/api/v6/data/yearbooks", "layer": "data"},
            {"path": "/api/v6/data/literature", "layer": "data"},
            {"path": "/api/v6/model/registry", "layer": "model"},
            {"path": "/api/v6/model/config", "layer": "model"},
            {"path": "/api/v6/model/configs", "layer": "model"},
            {"path": "/api/v6/model/workflow", "layer": "model"},
            {"path": "/api/v6/model/execute", "layer": "model"},
            {"path": "/api/v6/results/station", "layer": "results"},
            {"path": "/api/v6/results/evaluation", "layer": "results"},
            {"path": "/api/v6/results/spatial", "layer": "results"},
            {"path": "/api/v6/results/report", "layer": "results"},
            {"path": "/api/v6/evidence", "layer": "evidence"},
        ]

    # =================================================================
    # 0. overview
    # =================================================================
    def overview(self, qs):
        ds = self._ds(qs)
        station = _one(qs, "station")
        if ds == "SYRDARYA":
            body = self._overview_syr(station)
        else:
            body = self._overview_lamah(station)
        return self.env(ds, **body)

    def _overview_syr(self, station):
        code = self._syr_station(station) if station else SA.REACH_DOWN
        st = self.syr.stations[code]
        pts = self._monthly_axis(code)
        observed = [p for p in pts if p["status"] == "OBSERVED"]
        qc = self._qc_counts()
        return {
            "research": {
                "title": "Syr Darya 锡尔河下游 · 河段水量平衡与缺测重建",
                "task": DATASETS["SYRDARYA"]["task"],
                "case_reach": {
                    "id": SA.REACH_ID,
                    "upstream": SA.uid(SA.REACH_UP),
                    "downstream": SA.uid(SA.REACH_DOWN),
                    "label": "16037 -> 16039 · 268 km（老师提供的案例河段）",
                    "role": "固定研究河段（与当前浏览测站分开显示）",
                    "hydrologic_status": "GRAPH_TENTATIVE",
                },
                "task_types": list(RB.TASKS.values())[:3],
            },
            "browse": {
                "station": SA.uid(code),
                "name": st.name,
                "role": "当前浏览测站（不改变固定研究河段）",
                "years": st.years,
                "n_years": len(st.years),
                "coordinate_status": "GIS_PENDING",
            },
            "spatial": {
                "dataset_crs": "GIS_PENDING",
                "display_ready_layers": 0,
                "note": "Syr Darya 无经核验的 GIS 坐标，不绘制站点/河流/DEM；"
                        "仅以图层树状态说明接口就绪度",
                "origin": "TEACHER_CSV_ONLY",
            },
            "hydrograph": {
                "kind": "OBSERVED_ONLY",
                "station": SA.uid(code),
                "unit": "UNKNOWN",
                "unit_status": "UNKNOWN_IN_SOURCE_HEADER；与年径流交叉核对支持 "
                               "m3/s（推断，未确认）",
                "points": pts,
                "n_points": len(pts),
                "n_observed": len(observed),
                "n_missing_cell": sum(1 for p in pts
                                      if p["status"] == "MISSING"),
                "n_no_record_year": sum(1 for p in pts
                                        if p["status"] == "NO_RECORD_YEAR"),
                "qsim": None,
                "qsim_status": "NOT_GENERATED",
                "notice": RESULTS_NOTICE,
            },
            "model": {
                "model_execution": RB.MODEL_EXECUTION,
                "registered_models": 3,
                "implemented_models": 0,
                "trained_models": 0,
                "evaluated_models": 0,
                "evaluation_status": "NOT_EVALUATED",
                "qsim_available": False,
                "last_run": None,
                "notice": "仅存在 SYR-B0/B1/B2 接口定义与谱系检查，未训练、未评估",
            },
            "data_summary": {
                "discharge_years": self.syr.discharge_years,
                "n_stations": len(self.syr.stations),
                "met_range": list(self.syr.met_range),
                "circle_months": len({"%04d-%02d" % (o.year, o.month)
                                      for o in self.syr.rs
                                      if o.product == "CIRCLE" and
                                      o.value is not None}),
                "kzdam_months": len(self.syr.kz_months),
                "water_balance_years": sorted({b.year for b in self.syr.wb}),
                "qc": qc,
            },
            "entries": self._entries(),
        }

    def _overview_lamah(self, station):
        sid = None
        if station:
            raw = str(station).split(":")[-1]
            if raw.isdigit() and int(raw) in self.store.stations:
                sid = int(raw)
            else:
                raise PError(404, "STATION_NOT_FOUND",
                             "station %s is not in the authorized LamaH-CE "
                             "metadata" % station)
        st = self.store.stations.get(sid) if sid else None
        counts = self.store.meta()["counts"]
        return {
            "research": {
                "title": "LamaH-CE 欧洲河网 · 站网拓扑与供数关系筛查",
                "task": DATASETS["LAMAHCE"]["task"],
                "case_reach": {
                    "id": "LAMAHCE:TOPOLOGY",
                    "label": "全站网 U / T / W 关系（图级）",
                    "role": "固定研究任务；无老师指定河段",
                    "hydrologic_status": "GRAPH_TENTATIVE",
                },
                "task_types": ["拓扑筛查", "供数站候选", "跨系统泛化（未授权）"],
            },
            "browse": {
                "station": "LAMAHCE:%d" % sid if sid else None,
                "name": st.get("name") if st else None,
                "role": "当前浏览测站",
                "years": None,
                "n_years": None,
                "coordinate_status": "EPSG:3035 (PROJECTED_METRE)",
            },
            "spatial": {
                "dataset_crs": "EPSG:3035",
                "display_ready_layers": 1,
                "note": "仅 882 个投影站点坐标可绘制；河网/DEM/行政边界图层未暂存",
                "origin": "OPEN_METADATA_STATION_POINTS",
            },
            "hydrograph": {
                "kind": "NOT_AVAILABLE",
                "station": "LAMAHCE:%d" % sid if sid else None,
                "unit": "UNKNOWN",
                "unit_status": "LamaH-CE 径流序列在 sealed_runoff，未授权读取",
                "points": [],
                "n_points": 0, "n_observed": 0, "n_missing_cell": 0,
                "n_no_record_year": 0,
                "qsim": None, "qsim_status": "NOT_GENERATED",
                "notice": "本站网无经授权的水文序列可展示（仅开放元数据）",
            },
            "model": {
                "model_execution": RB.MODEL_EXECUTION,
                "registered_models": 3,
                "implemented_models": 0,
                "trained_models": 0,
                "evaluated_models": 0,
                "evaluation_status": "NOT_EVALUATED",
                "qsim_available": False,
                "last_run": None,
                "notice": "LamaH-CE 侧可作为跨系统训练集候选，但训练未授权",
            },
            "data_summary": {
                "stations_total": counts["stations_total"],
                "stations_in_graph": counts["stations_in_graph"],
                "directed_edges": counts["directed_edges"],
                "targets_with_candidates": counts["targets_with_candidates"],
                "geometry_verified": 0,
                "qc": {"note": "审计口径见 /api/vhs/meta 与站点详情页"},
            },
            "entries": self._entries(),
        }

    def _entries(self):
        return [
            {"key": "overview", "title": "研究概览",
             "sub": "研究区域 · 任务 · 核心过程线", "href": "#/overview"},
            {"key": "layers", "title": "空间图层",
             "sub": "河网 · DEM · 水文站 · 气象站 · 行政区", "href": "#/layers"},
            {"key": "data", "title": "数据层",
             "sub": "站点历史 · 遥感 · 统计年鉴 · 文献 · 质量证据",
             "href": "#/data"},
            {"key": "model", "title": "模型层",
             "sub": "架构 · 参数配置 · 运行方式", "href": "#/model"},
            {"key": "results", "title": "结果层",
             "sub": "站点结果 · 模型评估 · 空间结果 · 报告", "href": "#/results"},
        ]

    def _qc_counts(self):
        w = {}
        for c in self.syr.w_checks:
            w[c["status"]] = w.get(c["status"], 0) + 1
        flags = {}
        for f in self.syr.flags:
            flags[f.code] = flags.get(f.code, 0) + 1
        return {"w_check_status": w, "flag_counts": flags,
                "flags_total": len(self.syr.flags)}

    # =================================================================
    # 1. spatial layers
    # =================================================================
    def layers(self, qs):
        ds = self._ds(qs)
        if ds == "LAMAHCE":
            groups = self._lamah_layer_groups()
        else:
            groups = self._syr_layer_groups()
        summary = {
            "layers_total": sum(len(g["layers"]) for g in groups),
            "display_ready": sum(1 for g in groups for l in g["layers"]
                                 if l["display_status"] == "GIS_DISPLAY_READY"),
            "hydrologically_certified": sum(
                1 for g in groups for l in g["layers"]
                if l["hydrologic_status"] == "HYDROLOGICALLY_CERTIFIED"),
            "tentative": sum(1 for g in groups for l in g["layers"]
                             if l["hydrologic_status"] == "GRAPH_TENTATIVE"),
            "not_available": sum(1 for g in groups for l in g["layers"]
                                 if l["display_status"] ==
                                 "GIS_DISPLAY_NOT_AVAILABLE"),
        }
        return self.env(
            ds,
            crs=("EPSG:3035" if ds == "LAMAHCE" else "GIS_PENDING"),
            groups=groups, summary=summary,
            display_status_legend=DISPLAY_STATUS_ZH,
            hydrologic_status_legend=HYDRO_STATUS_ZH,
            rule_note=("GIS_DISPLAY_READY 只表示真实空间数据可绘制；"
                       "HYDROLOGICALLY_CERTIFIED 表示水文物理关系已审核。"
                       "两者不可混为一谈：画出一条河不等于认证了上下游关系。"),
            synthetic_preview={
                "available": True,
                "endpoint": "/api/vhs/gis/synthetic",
                "label": "SYNTHETIC_PREVIEW_ONLY",
                "note": "河网/DEM 等合成预览仅用于接口演示，与真实地图彻底分开；"
                        "不得作为研究成果引用",
            },
            authorization_required=self._gis_authorization_list(),
        )

    def _layer(self, lid, title, group, geometry, display, hydro, source,
               evidence, notes, features=None, crs=None):
        return {
            "id": lid, "title": title, "group": group,
            "geometry": geometry,
            "display_status": display,
            "display_status_zh": DISPLAY_STATUS_ZH[display],
            "hydrologic_status": hydro,
            "hydrologic_status_zh": HYDRO_STATUS_ZH[hydro],
            "source": source, "evidence": evidence, "notes": notes,
            "feature_count": features,
            "crs": crs,
        }

    def _lamah_layer_groups(self):
        meta = self.store.meta()["counts"]
        n_pts = meta["stations_total"]
        groups = [
            {"key": "river_network", "title": "河网", "icon": "river",
             "description": "河道中心线、干支流关系、工程对象、U/T/W 关系与拓扑来源证据",
             "layers": [
                 self._layer("ln_river_centerline", "河道中心线",
                             "river_network", "MultiLineString",
                             "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "RiverATLAS（input/c1/...）",
                             "NOT_STAGED：图层未暂存，未读取任何 GIS 字节",
                             "接口已就绪；暂存后需校验 CRS/几何/要素数/包围盒",
                             crs="EXPECTED EPSG:3035"),
                 self._layer("ln_tributary_relation", "干支流关系",
                             "river_network", "Topology",
                             "GIS_DISPLAY_NOT_AVAILABLE", "GRAPH_TENTATIVE",
                             "Gauge_hierarchy（属性拓扑）",
                             "图级有向边来自站点层级表，非几何认证",
                             "可绘制拓扑图（非地图）；河段几何关系 UNKNOWN",
                             features=meta["directed_edges"]),
                 self._layer("ln_engineering", "水库 / 引水渠 / 灌溉渠道",
                             "river_network", "Point/LineString",
                             "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "Impact 图层（未暂存）", "NOT_STAGED",
                             "无经许可的工程对象几何；不编造位置"),
                 self._layer("ln_utw", "上游 U / 目标 T / 候选 W 关系",
                             "river_network", "Relation",
                             "GIS_DISPLAY_NOT_AVAILABLE", "GRAPH_TENTATIVE",
                             "站点审计 + 匹配诊断",
                             "关系证据在 /api/vhs/stations/{id}/utw，仅供属性展示",
                             "地图层不可绘制；关系一律标 GRAPH_TENTATIVE"),
                 self._layer("ln_topology_evidence", "河段拓扑与空间来源证据",
                             "river_network", "Table",
                             "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "GIS 检查报告（Stage A）",
                             "图层来源与哈希见 /api/vhs/gis/layers（全部 NOT_STAGED）",
                             "画出来之前先给出证据链", features=0),
             ]},
            {"key": "dem", "title": "DEM", "icon": "dem",
             "description": "高程、坡度、地形阴影与断面高程信息",
             "layers": [
                 self._layer("dem_elevation", "DEM 高程", "dem", "Raster",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "未提供 / 未授权", "NOT_STAGED", "不编造 DEM 栅格"),
                 self._layer("dem_slope", "坡度", "dem", "Raster",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "由 DEM 派生（待 DEM 就位）", "NOT_STAGED",
                             "坡度必须由真实 DEM 派生，不做合成"),
                 self._layer("dem_hillshade", "地形阴影", "dem", "Raster",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "由 DEM 派生（待 DEM 就位）", "NOT_STAGED",
                             "仅可视化用途，不参与科研判定"),
                 self._layer("dem_section", "研究断面高程", "dem", "Profile",
                             "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "断面与站点高程（elev_m 属性可用）", "NOT_STAGED",
                             "站点属性表有 elev_m；断面几何未授权"),
             ]},
            {"key": "hydro_stations", "title": "水文站点", "icon": "gauge",
             "description": "站点位置、编号、流域面积、观测时间范围与角色分类",
             "layers": [
                 self._layer("hs_gauges", "水文站位置", "hydro_stations",
                             "Point", "GIS_DISPLAY_READY", "GRAPH_TENTATIVE",
                             "开放元数据 Gauges（%d 站）" % n_pts,
                             "坐标 EPSG:3035 投影米；属性来自开放元数据",
                             "可绘制真实点位；上下游关系仍为图级暂定",
                             features=n_pts, crs="EPSG:3035"),
                 self._layer("hs_attributes", "站点属性（名称/编号/面积/时段）",
                             "hydro_stations", "Table",
                             "GIS_DISPLAY_READY", "NOT_APPLICABLE",
                             "开放元数据属性表", "属性可查，独立于地图绘制",
                             "面积、观测起止、河段号等可用于筛选",
                             features=n_pts, crs="n/a"),
                 self._layer("hs_roles", "实测站 / 目标站 / 其他测站分类",
                             "hydro_stations", "Attribute",
                             "GIS_DISPLAY_READY", "GRAPH_TENTATIVE",
                             "站点审计（audit_state / candidate_status）",
                             "角色分类来自图级审计，非物理认证",
                             "颜色区分角色；认证状态见站点点选面板",
                             features=n_pts),
             ]},
            {"key": "met_stations", "title": "气象站点", "icon": "met",
             "description": "气象站位置、覆盖范围、降水与气温观测",
             "layers": [
                 self._layer("ms_positions", "气象站位置", "met_stations",
                             "Point", "GIS_DISPLAY_NOT_AVAILABLE",
                             "NOT_APPLICABLE", "未提供 / 未授权", "NOT_STAGED",
                             "不编造气象站坐标"),
                 self._layer("ms_coverage", "站点数据覆盖范围", "met_stations",
                             "Polygon", "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "未提供 / 未授权", "NOT_STAGED",
                             "覆盖范围需真实台站元数据"),
                 self._layer("ms_obs", "降水 / 气温观测", "met_stations",
                             "TimeSeries", "GIS_DISPLAY_NOT_AVAILABLE",
                             "NOT_APPLICABLE", "LamaH-CE 气象数据未授权读取",
                             "NOT_AVAILABLE", "仅面积/位置图层缺失，序列亦不可用"),
                 self._layer("ms_relation", "气象站与研究流域空间关系",
                             "met_stations", "Relation",
                             "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                             "需流域边界与台站坐标", "NOT_STAGED",
                             "缺一不可，不做推断"),
             ]},
            {"key": "admin", "title": "行政区域", "icon": "admin",
             "description": "国家、省州边界与研究区域定位",
             "layers": [
                 self._layer("ad_country", "国家边界", "admin", "Polygon",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "未提供 / 未授权", "NOT_STAGED", "不编造边界"),
                 self._layer("ad_state", "省州 / 地区边界", "admin", "Polygon",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "未提供 / 未授权", "NOT_STAGED",
                             "站点属性含 fedstate，可用于筛选而不画边界"),
                 self._layer("ad_region", "研究区域定位", "admin", "Polygon",
                             "GIS_DISPLAY_NOT_AVAILABLE", "NOT_APPLICABLE",
                             "未提供 / 未授权", "NOT_STAGED",
                             "需授权后才能绘制研究区范围"),
             ]},
        ]
        return groups

    def _syr_layer_groups(self):
        note = "Syr Darya 缺少经核验的 GIS 地理信息；不得套用欧洲 EPSG:3035"
        spec = [
            ("river_network", "河网",
             "河道中心线、干支流关系、工程对象（水库/引水渠/灌溉渠道）、U/T/W 与拓扑证据",
             [("sr_reach268", "268 km 研究河段（16037->16039）", "LineString"),
              ("sr_centerlines", "河道中心线", "MultiLineString"),
              ("sr_tributary", "干支流关系", "Topology"),
              ("sr_engineering", "水库 / 引水渠 / 灌溉渠道", "Point/LineString")]),
            ("dem", "DEM", "高程、坡度、阴影与断面高程",
             [("sr_dem", "DEM 高程", "Raster"),
              ("sr_slope", "坡度", "Raster"),
              ("sr_section", "断面高程", "Profile")]),
            ("hydro_stations", "水文站点",
             "站点位置、编号、流域面积、观测时段与角色",
             [("sr_gauges", "水文站位置", "Point"),
              ("sr_attributes", "站点属性", "Table")]),
            ("met_stations", "气象站点",
             "气象站位置、覆盖范围、降水与气温",
             [("sr_met_pos", "气象站位置", "Point"),
              ("sr_met_cov", "覆盖范围", "Polygon")]),
            ("admin", "行政区域", "国家、省州边界与研究区域定位",
             [("sr_admin", "国家 / 省州边界", "Polygon")]),
        ]
        groups = []
        for key, title, desc, layers in spec:
            groups.append({
                "key": key, "title": title, "icon": key,
                "description": desc,
                "layers": [self._layer(lid, ltitle, key, geom,
                                       "GIS_DISPLAY_NOT_AVAILABLE", "UNKNOWN",
                                       "GIS_PENDING（未授权/未核验）",
                                       "NOT_AVAILABLE：不绘制任何推断几何",
                                       note)
                           for lid, ltitle, geom in layers],
            })
        for g in groups:
            for l in g["layers"]:
                if l["id"] == "sr_attributes":
                    l["hydrologic_status"] = "NOT_APPLICABLE"
                    l["hydrologic_status_zh"] = HYDRO_STATUS_ZH["NOT_APPLICABLE"]
                    l["notes"] = ("站点属性（名称/年数/QC）可在数据层查询；"
                                  "无坐标，故不进入地图")
        return groups

    def _gis_authorization_list(self):
        return [
            {"item": "03_原始数据/vectors/*",
             "need": "CRS(.prj)、几何类型、要素数、包围盒",
             "purpose": "河网 / 行政边界 / 研究区图层"},
            {"item": "经核验的水文站坐标文件",
             "need": "与 SYRDARYA:<code> 的关联字段、坐标系、来源",
             "purpose": "Syr Darya 站点位置"},
            {"item": "reach268 河段线",
             "need": "起止点与 16037/16039 一致、长度约 268 km",
             "purpose": "研究河段几何"},
            {"item": "circles A-G 圆心/半径",
             "need": "坐标系与 area_*_km2 一致性", "purpose": "遥感水面范围图层"},
            {"item": "DEM 栅格", "need": "分辨率、垂直基准、覆盖范围",
             "purpose": "高程/坡度/阴影"},
            {"item": "气象站坐标与覆盖", "need": "台站编号、观测要素、时段",
             "purpose": "气象站点层"},
        ]

    def layer_features(self, qs):
        ds = self._ds(qs)
        layer = _one(qs, "layer", required=True)
        if ds == "LAMAHCE" and layer == "hs_gauges":
            mp = self.store.map_points()
            feats = []
            for p in mp["points"]:
                feats.append({
                    "type": "Feature",
                    "geometry": {"type": "Point",
                                 "coordinates": [p["x"], p["y"]]},
                    "properties": {
                        "id": p["id"], "uid": "LAMAHCE:%d" % p["id"],
                        "name": p.get("name"), "river": p.get("river"),
                        "audit_state": p.get("state"),
                        "candidate_status": p.get("candidate_status"),
                        "role": ("TARGET" if p.get("candidate_status") in
                                 ("HAS_CANDIDATES", "GRAPH_TENTATIVE")
                                 else "OBSERVED_GAUGE"),
                    },
                })
            return self.env(
                ds, layer=layer,
                collection={"type": "FeatureCollection",
                            "crs": {"type": "name",
                                    "properties": {"name": "EPSG:3035"}},
                            "features": feats},
                bounds=mp["bounds"], n_features=len(feats),
                display_status="GIS_DISPLAY_READY",
                hydrologic_status="GRAPH_TENTATIVE",
                note="仅投影站点点位；无底图、无河段几何、无边界多边形")
        return self.env(ds, layer=layer,
                        collection={"type": "FeatureCollection",
                                    "features": []},
                        n_features=0,
                        display_status="GIS_DISPLAY_NOT_AVAILABLE",
                        hydrologic_status="UNKNOWN",
                        reason="no authorized real geometry for this layer; "
                               "nothing is invented",
                        note="该图层无经许可的真实空间数据，返回空集合而不是假几何")

    # =================================================================
    # 2. data layer
    # =================================================================
    def _data_route(self, sub, qs):
        ds = self._ds(qs)
        if sub == "catalog":
            return self._data_catalog(ds)
        if sub == "coverage":
            return self._coverage(ds, qs)
        if sub == "remote-sensing":
            return self._remote_sensing(ds, qs)
        if sub == "yearbooks":
            return self.env(ds, **self._yearbooks(ds))
        if sub == "literature":
            return self.env(ds, **self._literature(ds))
        raise PError(404, "NOT_FOUND", "no data route %s" % sub)

    def _data_catalog(self, ds):
        if ds == "SYRDARYA":
            syr = self.syr
            n_cells = len(syr.discharge)
            n_obs = sum(1 for o in syr.discharge if o.value is not None)
            modules = [
                {"id": "station_history", "title": "站点历史数据",
                 "status": "AVAILABLE",
                 "records": {"station_years": len(syr.w_checks),
                             "discharge_cells": n_cells,
                             "observed_cells": n_obs,
                             "stations": len(syr.stations),
                             "years": syr.discharge_years},
                 "kinds": ["月平均 Q", "月最大 Q", "月最小 Q", "年径流 W"],
                 "origin": "TEACHER_CSV（原始值，未覆盖）",
                 "derived": ["W_from_Q（由 Q 派生，标注 DERIVED）"],
                 "missing_policy": "缺测显示 NO_RECORD_YEAR / DATA_NOT_FOUND / "
                                   "MISSING，不插值、不补零",
                 "href": "#/data/history"},
                {"id": "remote_sensing", "title": "遥感数据",
                 "status": "AVAILABLE",
                 "records": {"circle_sites": 7, "kzdam_sites": 4,
                             "circle_months": len({(o.year, o.month)
                                                   for o in syr.rs
                                                   if o.product == "CIRCLE"}),
                             "kzdam_months": len(syr.kz_months),
                             "products": ["CIRCLE A-G 水面面积",
                                          "KZDAM KC/KD/KS/KU"]},
                 "origin": "TEACHER_CSV", "derived": [],
                 "missing_policy": "NO_OBSERVATION 不等于 0；零面积单列 ZERO",
                 "href": "#/data/remote"},
                {"id": "yearbook", "title": "统计年鉴",
                 "status": "INTERFACE_ONLY",
                 "records": {"entries": 0, "read": "NOT_READ"},
                 "origin": "未读取（需授权）", "derived": [],
                 "missing_policy": "未授权 -> 目录为空且明确标注，不代表“无年鉴”",
                 "href": "#/data/yearbook"},
                {"id": "literature", "title": "文献材料",
                 "status": "INTERFACE_ONLY",
                 "records": {"entries": 0, "verified": 0},
                 "origin": "未读取文献库（不生成不可核实条目）", "derived": [],
                 "missing_policy": "仅登记可核实来源；空目录 = 未登记",
                 "href": "#/data/literature"},
            ]
        else:
            m = self.store.meta()["counts"]
            modules = [
                {"id": "station_history", "title": "站点历史数据",
                 "status": "METADATA_ONLY",
                 "records": {"stations": m["stations_total"],
                             "directed_edges": m["directed_edges"],
                             "discharge_series": 0},
                 "kinds": ["站点属性与观测起止", "审计状态"],
                 "origin": "OPEN_METADATA", "derived": [],
                 "missing_policy": "径流序列位于 sealed_runoff，未授权读取",
                 "href": "#/data/history"},
                {"id": "remote_sensing", "title": "遥感数据",
                 "status": "NOT_AVAILABLE", "records": {},
                 "origin": "未授权", "derived": [],
                 "missing_policy": "不展示未授权产品", "href": "#/data/remote"},
                {"id": "yearbook", "title": "统计年鉴",
                 "status": "NOT_AVAILABLE", "records": {},
                 "origin": "未授权", "derived": [],
                 "missing_policy": "不读取", "href": "#/data/yearbook"},
                {"id": "literature", "title": "文献材料",
                 "status": "INTERFACE_ONLY", "records": {"entries": 0},
                 "origin": "未读取", "derived": [],
                 "missing_policy": "仅登记可核实来源", "href": "#/data/literature"},
            ]
        return self.env(ds, dataset_info=DATASETS[ds], modules=modules,
                        quality_page={"href": "#/data/quality",
                                      "title": "数据质量与科研证据（二级页面）"})

    def _coverage(self, ds, qs):
        if ds != "SYRDARYA":
            return self.env(ds, available=False,
                            reason="该数据集仅开放元数据，无时间序列可做覆盖矩阵",
                            matrix=None)
        syr = self.syr
        years = syr.discharge_years
        cols = [{"year": y, "label": str(y)} for y in years]
        station_rows = []
        for code, st in sorted(syr.stations.items(),
                               key=lambda kv: int(kv[0])):
            cells = []
            for y in years:
                present = sum(1 for o in syr.discharge
                              if o.station_uid == SA.uid(code) and
                              o.year == y and o.stat == "mean" and
                              o.value is not None)
                suspect = sum(1 for o in syr.discharge
                              if o.station_uid == SA.uid(code) and
                              o.year == y and o.stat == "mean" and
                              "SEQUENCE_INDEX_SUSPECT" in o.flags)
                if y not in st.years:
                    status = "NO_RECORD_YEAR"
                elif present == 0:
                    status = "MISSING"
                elif suspect:
                    status = "SUSPECT"
                elif present < 12:
                    status = "PARTIAL"
                else:
                    status = "OBSERVED"
                cells.append({"year": y, "present": present,
                              "total": 12, "status": status,
                              "suspect": suspect})
            station_rows.append({"key": SA.uid(code),
                                 "label": SA.uid(code),
                                 "name": st.name, "role": "OBSERVED_GAUGE",
                                 "cells": cells})
        var_rows = []
        var_rows.append(self._coverage_row(
            "met", "气象 P/T（逐日）", "OBSERVED", years,
            lambda y: syr.met_monthly(y) if
            int(syr.met_range[0][:4]) <= y <= int(syr.met_range[1][:4])
            else None))
        var_rows.append(self._coverage_row(
            "circle", "遥感圆区 A-G（水面面积）", "REMOTE_SENSING", years,
            lambda y: [{"year": y, "month": m,
                        "complete": any(o.value is not None for o in syr.rs
                                        if o.product == "CIRCLE" and
                                        o.year == y and o.month == m)}
                       for m in range(1, 13)]))
        var_rows.append(self._coverage_row(
            "kzdam", "KZDAM KC/KD/KS/KU", "REMOTE_SENSING", years,
            lambda y: [{"year": y, "month": m,
                        "complete": any(o.value is not None for o in syr.rs
                                        if o.product == "KZDAM" and
                                        o.year == y and o.month == m)}
                       for m in range(1, 13)]))
        wb_years = {b.year for b in syr.wb}
        var_rows.append(self._coverage_row(
            "water_balance", "水量平衡（源文件）", "OBSERVED", years,
            lambda y: ([{"year": y, "month": m, "complete": True}
                        for m in range(1, 13)] if y in wb_years else None)))
        return self.env(
            ds, available=True, years=cols, station_rows=station_rows,
            variable_rows=var_rows,
            legend={"OBSERVED": "记录完整/可用", "PARTIAL": "部分月份缺测",
                    "MISSING": "该年有记录行但值缺测",
                    "NO_RECORD_YEAR": "该年无记录行（不插值）",
                    "SUSPECT": "序列序号占位嫌疑（保留原值，不绘制）"},
            note_zh="矩阵与矩阵之间的分母不同：流量按站-年 x 12 月，"
                    "气象按逐日完整月，遥感按有观测的月份。"
                    "不得把不同分母混为一个“完整率”。",
            met_note={"missing_days": len(syr.met_missing_days),
                      "range": list(syr.met_range)})

    def _coverage_row(self, key, label, kind, years, month_fn):
        cells = []
        for y in years:
            mm = month_fn(y)
            if mm is None:
                cells.append({"year": y, "present": 0, "total": 12,
                              "status": "OUT_OF_RANGE"})
                continue
            present = sum(1 for x in mm if x.get("complete"))
            status = ("OBSERVED" if present == 12 else
                      ("PARTIAL" if present else "MISSING"))
            cells.append({"year": y, "present": present, "total": 12,
                          "status": status})
        return {"key": key, "label": label, "kind": kind, "cells": cells}

    def _remote_sensing(self, ds, qs):
        if ds != "SYRDARYA":
            return self.env(ds, available=False, products=[],
                            reason="遥感产品仅 Syr Darya 授权使用")
        year = _int(qs, "year", 1900, 2100, required=True)
        syr = self.syr
        circles = []
        for site in "ABCDEFG":
            obs = [o for o in syr.rs if o.product == "CIRCLE" and
                   o.site == site and o.year == year]
            vals = [o.month for o in obs if o.value is not None]
            circles.append({
                "site": site, "months_with_value": len(vals),
                "months_total": 12,
                "first": min(vals) if vals else None,
                "last": max(vals) if vals else None,
                "values_km2": [{"month": o.month, "value": o.value,
                                "status": o.value_status,
                                "n_images": o.n_images} for o in obs],
                "missing_months": [m for m in range(1, 13)
                                   if m not in set(vals)],
            })
        kz = [o for o in syr.rs if o.product == "KZDAM" and o.year == year]
        return self.env(
            ds, year=year, kind="REMOTE_SENSING",
            products=[{"id": "CIRCLE", "title": "圆区 A-G 水面面积",
                       "unit": "km2", "source": "circle_water_monthly.csv",
                       "spatial_extent": "圆区 A-G（圆心/半径未授权，无法绘制）",
                       "overlap": {"discharge": True, "meteorology": True}},
                      {"id": "KZDAM", "title": "KZDAM KC/KD/KS/KU",
                       "unit": "UNKNOWN", "source": "kzdam_monthly.csv",
                       "spatial_extent": "KZ 大坝区（范围未授权）",
                       "overlap": {"discharge": True, "meteorology": True}}],
            circles=circles,
            kzdam={"months_present": len({o.month for o in kz}),
                   "rows": [{"month": o.month, "site": o.site,
                             "value": o.value, "status": o.value_status}
                            for o in kz]},
            missing_policy="NO_OBSERVATION 不是 0；ZERO 单独标记；"
                           "缺测不参与任何聚合",
            overlap_note="遥感月份与流量/气象年份重叠情况见 coverage 矩阵")

    def _yearbooks(self, ds):
        return {
            "status": "INTERFACE_ONLY",
            "availability": "NOT_READ",
            "entries": [],
            "reason": ("本轮未读取任何年鉴文件；目录条目仅在上级目录列表中出现过"
                       "名称，未打开内容。没有授权就不登记任何年份/表号。"),
            "required_fields": ["volume_name", "year", "institution", "region",
                                "related_stations", "table_ref",
                                "checksum", "access_scope"],
            "ingestion_contract": {
                "endpoint": "/api/v6/data/yearbooks",
                "mode": "READ_ONLY + SHA256 + 人工核验后才登记",
                "forbidden": "不得以估算值填充缺失年鉴数据",
            },
            "authorization_needed": {
                "path": r"D:\VHS_交接包_2026-10-19\VHS\03_原始数据\yearbook",
                "ask": "列出文件清单 + 授权只读打开 + 允许登记元数据",
            },
        }

    def _literature(self, ds):
        return {
            "status": "INTERFACE_ONLY",
            "availability": "NOT_REGISTERED",
            "entries": [],
            "verified_entries": 0,
            "policy": ("只登记可核实来源（DOI / 报告编号 / 文件 SHA-256）。"
                       "本轮未核验任何文献，因此目录如实为空；不生成论文信息。"),
            "required_fields": ["title", "authors", "year", "topic",
                                "doi_or_source", "relation_to_data_or_model",
                                "verification_status"],
            "example_relation": ("示例关系字段：用于解释 ET 反演方法 / "
                                 "用于解释 KZDAM 单位 / 用于对比 LamaH-CE 数据集"),
            "registered_scope": {"datasets": ["SYRDARYA", "LAMAHCE"],
                                 "topics": ["数据集", "方法", "研究区"]},
        }

    # =================================================================
    # 3. model layer
    # =================================================================
    def _model_route(self, sub, qs):
        ds = self._ds(qs)
        if sub == "registry":
            return self._model_registry(ds)
        if sub == "config":
            return self._model_config(ds, qs)
        if sub == "configs":
            return self._saved_configs(ds)
        if sub == "workflow":
            return self._model_workflow(ds, qs)
        if sub in ("execute", "predict"):
            raise PError(403, "NOT_AUTHORIZED",
                         "MODEL_EXECUTION = NOT_AUTHORIZED; prediction = null",
                         model_execution=RB.MODEL_EXECUTION)
        raise PError(404, "NOT_FOUND", "no model route %s" % sub)

    def _model_registry(self, ds):
        summary = RB.summary()
        cards = []
        for b in summary["baselines"]:
            cards.append({
                "id": b["baseline"], "name": b["title"],
                "family": "BASELINE（基线）",
                "status": "DEFINED_ONLY",
                "status_zh": MODEL_STATUS_ZH["DEFINED_ONLY"],
                "implemented": False, "trained": False, "evaluated": False,
                "inputs": b["features"], "output": b["target"],
                "leakage": {t: {"ok": r["ok"],
                                "violations": r["violations"],
                                "warnings": r["warnings"]}
                            for t, r in b["leakage"].items()},
                "execution": b["execution"], "prediction": None,
                "note": "接口与谱系检查已就绪；未训练、未评估、未运行",
            })
        return self.env(
            ds, model_execution=RB.MODEL_EXECUTION, registry=cards,
            roadmap=FUTURE_ARCHITECTURES, status_legend=MODEL_STATUS_ZH,
            badge_meaning="“谱系检查通过”不等于“已执行实验”；本轮未训练任何模型",
            independence_note=summary["independence_note"],
            tasks=summary["tasks"],
            feature_catalog=summary["features"][:40],
            qsim_available=False, prediction=None)

    def _model_config(self, ds, qs):
        model = (_one(qs, "model") or "SYR-B1").upper()
        base = self._registry_card(model)
        if base is None:
            raise PError(404, "MODEL_NOT_FOUND", model)
        years = self.syr.discharge_years if ds == "SYRDARYA" else []
        return self.env(
            ds, schema_version="vhs-model-config/0.6",
            model=model, model_name=base["name"],
            status=base["status"], status_zh=base["status_zh"],
            config={
                "model": model, "dataset": ds,
                "target": base["output"], "inputs": list(base["inputs"]),
                "output": base["output"], "time_scale": "MONTH",
                "lag_months": 0,
                "train_years": years[:max(1, len(years) - 3)] if years else [],
                "test_years": years[-3:] if years else [],
                "regularization": None, "random_seed": None,
                "data_version": SA.RULES_VERSION,
                "feature_version": "v0.6-RECURSIVE_DAG",
                "task": (RB.ZERO_TARGET_Q if ds == "SYRDARYA"
                         else RB.CROSS_SYSTEM),
                "notes": "",
            },
            editable=("输入变量、时间尺度、滞后、训练/测试年份、正则系数、"
                      "随机种子、数据与特征版本；保存为 JSON 以便复现"),
            leakage_preview=self._leakage_preview(base, ds),
            save_endpoint="/api/v6/model/configs",
            execution=RB.MODEL_EXECUTION)

    def _registry_card(self, model):
        summary = RB.summary()
        for b in summary["baselines"]:
            if b["baseline"] == model:
                return {"name": b["title"], "status": "DEFINED_ONLY",
                        "status_zh": MODEL_STATUS_ZH["DEFINED_ONLY"],
                        "inputs": b["features"], "output": b["target"]}
        return None

    def _leakage_preview(self, base, ds):
        out = {}
        for task in RB.TASKS:
            rep = RB.check_leakage(base["inputs"], base["output"], task,
                                   train_dataset="LAMAHCE"
                                   if task == RB.CROSS_SYSTEM else None)
            out[task] = {"ok": rep.ok, "violations": rep.violations,
                         "warnings": rep.warnings}
        return out

    def _saved_configs(self, ds):
        items = []
        if os.path.isdir(CONFIG_DIR):
            for name in sorted(os.listdir(CONFIG_DIR)):
                if not name.endswith(".json"):
                    continue
                p = os.path.join(CONFIG_DIR, name)
                with open(p, "rb") as f:
                    raw = f.read()
                items.append({"file": name,
                              "sha256": hashlib.sha256(raw).hexdigest(),
                              "bytes": len(raw),
                              "config": json.loads(raw.decode("utf-8"))})
        return self.env(ds, configs=items, count=len(items),
                        note="仅保存配置 JSON；不执行、不评分、不写入任何观测值")

    def save_config(self, body):
        """POST /api/v6/model/configs -- validate and store a config JSON."""
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            raise PError(400, "BAD_BODY", "body must be JSON")
        cfg = payload.get("config") if isinstance(payload, dict) else None
        if not isinstance(cfg, dict):
            raise PError(400, "BAD_BODY", "body must be {config: {...}}")
        allow = {"model", "dataset", "target", "inputs", "output",
                 "time_scale", "lag_months", "train_years", "test_years",
                 "regularization", "random_seed", "data_version",
                 "feature_version", "task", "notes"}
        unknown = [k for k in cfg if k not in allow]
        if unknown:
            raise PError(400, "UNKNOWN_FIELD",
                         "unknown config fields: %s" % ", ".join(sorted(unknown)))
        ds = str(cfg.get("dataset") or "").upper()
        if ds not in DATASETS:
            raise PError(400, "BAD_DATASET", "dataset must be SYRDARYA|LAMAHCE")
        model = str(cfg.get("model") or "").upper()
        card = self._registry_card(model)
        if card is None:
            raise PError(400, "UNKNOWN_MODEL", "model must be SYR-B0/B1/B2")
        inputs = cfg.get("inputs")
        if not isinstance(inputs, list) or not all(isinstance(x, str)
                                                   for x in inputs):
            raise PError(400, "BAD_INPUTS", "inputs must be a list of strings")
        known = {f["feature"] for f in RB.summary()["features"]}
        bad = [x for x in inputs if x not in known]
        if bad:
            raise PError(400, "UNKNOWN_FEATURE",
                         "unknown features: %s" % ", ".join(bad))
        task = cfg.get("task")
        if task not in RB.TASKS:
            raise PError(400, "BAD_TASK",
                         "task must be one of %s" % list(RB.TASKS))
        rep = RB.check_leakage(inputs, card["output"], task,
                               train_dataset="LAMAHCE"
                               if task == RB.CROSS_SYSTEM else None)
        if not rep.ok:
            raise PError(400, "LEAKAGE_VIOLATION",
                         "feature lineage violates the task rule",
                         violations=rep.violations)
        for key in ("train_years", "test_years"):
            ys = cfg.get(key) or []
            if not isinstance(ys, list) or not all(isinstance(y, int)
                                                   for y in ys):
                raise PError(400, "BAD_YEARS",
                             "%s must be a list of integers" % key)
        if set(cfg.get("train_years") or []) & set(cfg.get("test_years") or []):
            raise PError(400, "TRAIN_TEST_OVERLAP",
                         "train_years and test_years overlap")
        digest = hashlib.sha256(
            json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:10]
        name = "%s-%s-%s.json" % (ds, model, digest)
        if not CFG_NAME.match(name.replace(".json", "")):
            raise PError(400, "BAD_NAME", "unexpected config name")
        os.makedirs(CONFIG_DIR, exist_ok=True)
        text = json.dumps(cfg, ensure_ascii=False, indent=1, sort_keys=True)
        p = os.path.join(CONFIG_DIR, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return {"saved": True, "file": name,
                "path": os.path.join("var", "model_configs", name),
                "sha256": _sha256_text(text),
                "leakage": {"ok": rep.ok, "warnings": rep.warnings},
                "executed": False,
                "note": "配置已保存；模型仍未执行（NOT_AUTHORIZED）"}

    def _model_workflow(self, ds, qs):
        station = _one(qs, "station")
        code = None
        if ds == "SYRDARYA":
            code = self._syr_station(station) if station else SA.REACH_DOWN
        years = self.syr.discharge_years if ds == "SYRDARYA" else []
        steps = [
            {"n": 1, "key": "select_region", "title": "选择研究区",
             "status": "READY", "value": DATASETS[ds]["title"],
             "detail": "数据集独立管理：标识、CRS、图层目录与站码命名空间均隔离"},
            {"n": 2, "key": "select_target", "title": "选择目标",
             "status": "READY" if code else "CONDITIONAL",
             "value": SA.uid(code) if code else "LAMAHCE 站网（无固定目标）",
             "detail": "固定研究河段 16037->16039 与浏览测站分开"},
            {"n": 3, "key": "select_model", "title": "选择模型",
             "status": "READY", "value": "SYR-B0 / SYR-B1 / SYR-B2",
             "detail": "仅接口定义；无已实现模型"},
            {"n": 4, "key": "data_eligibility", "title": "查看数据资格",
             "status": "CONDITIONAL", "value": "部分可用",
             "detail": "离散年份 %d 个（%s）；序号码占位单元格需排除；"
                       "目标站 Q 派生特征受限"
                       % (len(years), ", ".join(map(str, years))),
             "blockers": ["年份不连续，不能按连续序列直接训练",
                          "SEQUENCE_INDEX_SUSPECT 单元格需剔除",
                          "单位 UNKNOWN（Q 按 m3/s 假设仅用于一致性核对）"]},
            {"n": 5, "key": "configure", "title": "配置参数",
             "status": "READY", "value": "可编辑并保存 JSON",
             "detail": "输入/输出、时间尺度、滞后、训练与测试年份、正则、"
                       "种子、版本"},
            {"n": 6, "key": "validate", "title": "验证实验条件",
             "status": "READY", "value": "递归谱系检查 + 时间切分检查",
             "detail": "泄漏规则按任务类型判定；通过不等于已执行实验"},
            {"n": 7, "key": "run", "title": "运行",
             "status": "BLOCKED", "value": "MODEL_EXECUTION = NOT_AUTHORIZED",
             "detail": "后端 403 拒绝；仅改前端按钮不能解除"},
            {"n": 8, "key": "results", "title": "查看结果",
             "status": "NOT_EVALUATED", "value": "无结果",
             "detail": "未运行 -> 无 Qsim、无指标、无空间预测"},
        ]
        return self.env(ds, steps=steps,
                        model_execution=RB.MODEL_EXECUTION, prediction=None,
                        endpoint_execute="/api/v6/model/execute",
                        api_guard="POST /api/v6/model/execute 始终 403",
                        eligibility_source="/api/vhs/datasets/SYRDARYA/availability")

    # =================================================================
    # 4. results layer
    # =================================================================
    def _results_route(self, sub, qs):
        ds = self._ds(qs)
        if sub == "station":
            return 200, self._results_station(ds, qs)
        if sub == "evaluation":
            return 200, self._results_evaluation(ds, qs)
        if sub == "spatial":
            return 200, self._results_spatial(ds, qs)
        if sub == "report":
            return 200, self._results_report(ds, qs)
        raise PError(404, "NOT_FOUND", "no results route %s" % sub)

    def _monthly_axis(self, code):
        st = self.syr.stations[code]
        vals = {}
        for o in self.syr.discharge:
            if o.station_uid == SA.uid(code) and o.stat == "mean":
                vals[(o.year, o.month)] = o
        years = st.years
        pts = []
        for y in range(min(years), max(years) + 1):
            for m in range(1, 13):
                o = vals.get((y, m))
                if o is None:
                    status = ("NO_RECORD_YEAR" if y not in years
                              else "MISSING")
                    pts.append({"year": y, "month": m,
                                "t": "%04d-%02d" % (y, m), "value": None,
                                "flags": [], "status": status})
                elif o.value is None:
                    pts.append({"year": y, "month": m,
                                "t": "%04d-%02d" % (y, m), "value": None,
                                "flags": list(o.flags), "status": "MISSING"})
                else:
                    pts.append({"year": y, "month": m,
                                "t": "%04d-%02d" % (y, m), "value": o.value,
                                "flags": list(o.flags),
                                "status": ("SUSPECT" if o.flags
                                           else "OBSERVED")})
        return pts

    def _results_station(self, ds, qs):
        station = _one(qs, "station")
        if ds != "SYRDARYA":
            sid = None
            if station:
                raw = str(station).split(":")[-1]
                if raw.isdigit() and int(raw) in self.store.stations:
                    sid = int(raw)
            return self.env(
                ds, station=("LAMAHCE:%d" % sid if sid else None),
                status="NO_AUTHORIZED_SERIES", observations=[],
                qobs={"n_defined": 0, "n_missing": 0},
                qsim=None, qsim_status="NOT_GENERATED",
                prediction_interval=None, model_run=None,
                evaluation={"status": "NOT_EVALUATED", "metrics": {}},
                notice="LamaH-CE 仅开放元数据，径流序列位于 sealed_runoff，"
                       "未授权读取")
        code = self._syr_station(station) if station else SA.REACH_DOWN
        st = self.syr.stations[code]
        pts = self._monthly_axis(code)
        annual = [c for c in self.syr.w_checks
                  if c["station"] == SA.uid(code)]
        return self.env(
            ds, station=SA.uid(code), name=st.name,
            role=("CASE_REACH_DOWNSTREAM" if code == SA.REACH_DOWN else
                  ("CASE_REACH_UPSTREAM" if code == SA.REACH_UP else
                   "OBSERVED_GAUGE")),
            years=st.years, time_scale="MONTH", unit="UNKNOWN",
            unit_status="UNKNOWN_IN_SOURCE_HEADER；年径流交叉核对支持 "
                        "m3/s（推断，未确认）",
            observations=pts,
            qobs={"n_defined": sum(1 for p in pts if p["value"] is not None),
                  "n_missing": sum(1 for p in pts if p["value"] is None),
                  "n_suspect": sum(1 for p in pts
                                   if p["status"] == "SUSPECT")},
            missing_codes={"NO_RECORD_YEAR": "该年无记录行（不插值）",
                           "MISSING": "该年有行但值缺测",
                           "SUSPECT": "序号码占位嫌疑，保留原值但不绘制"},
            qsim=None, qsim_status="NOT_GENERATED",
            prediction_interval=None, model_run=None,
            evaluation={"status": "NOT_EVALUATED",
                        "metrics": {k: None for k in METRICS},
                        "n_samples": None},
            notice=RESULTS_NOTICE,
            annual=[{"year": c["year"], "W_source": c["W_source"],
                     "W_from_Q": c.get("W_from_Q"),
                     "rel_diff": c.get("rel_diff"),
                     "status": c.get("status")} for c in annual])

    def _results_evaluation(self, ds, qs):
        station = _one(qs, "station")
        code = None
        if ds == "SYRDARYA":
            code = self._syr_station(station) if station else SA.REACH_DOWN
        return self.env(
            ds, station=SA.uid(code) if code else None,
            status="NOT_EVALUATED", status_zh="未评估（无模型运行）",
            metrics=[{"key": k, "value": None, "status": "NOT_EVALUATED",
                      "unit": {"NSE": "-", "KGE": "-", "RMSE": "UNKNOWN",
                               "MAE": "UNKNOWN", "PBIAS": "%"}[k]}
                     for k in METRICS],
            n_samples=None,
            provenance_requirements={
                "model_version": None,
                "dataset_version": SA.RULES_VERSION,
                "period": None,
                "common_sample_ids": None,
                "snapshot_id": (self.syr.snapshot.snapshot_id
                                if self.syr.snapshot else None),
            },
            required_for_each_metric=["model_version", "dataset_version",
                                      "period", "common_sample_ids"],
            empty_state=("所有指标为 N/A：没有模型运行，就没有共同样本，"
                         "也不可能计算 NSE/KGE/RMSE/MAE/PBIAS"),
            planned_views=["观测-模拟散点", "残差图", "逐年误差",
                           "高流量/低流量分段评估", "多模型对比"],
            prediction=None)

    def _results_spatial(self, ds, qs):
        base_layers = []
        if ds == "LAMAHCE":
            base_layers = [{"id": "hs_gauges", "title": "水文站点位置",
                            "available": True,
                            "note": "真实投影点位（EPSG:3035）"}]
        return self.env(
            ds, status="PREDICTION_LAYER_NOT_AVAILABLE",
            status_zh="空间模拟结果尚未生成",
            base_layers=base_layers, prediction_layers=[],
            planned_layers=[
                {"id": "sp_reach_q", "title": "河流断面模拟流量",
                 "status": "NOT_AVAILABLE",
                 "requires": "模型运行 + 经认证的河段几何"},
                {"id": "sp_reach_class", "title": "不同河段空间预测结果",
                 "status": "NOT_AVAILABLE", "requires": "模型运行 + 河段分区"},
                {"id": "sp_error", "title": "误差空间分布",
                 "status": "NOT_AVAILABLE", "requires": "观测-模拟配对样本"},
                {"id": "sp_uncertainty", "title": "预测不确定性分布",
                 "status": "NOT_AVAILABLE", "requires": "概率模型输出"},
                {"id": "sp_coverage", "title": "模型可用/不可用区域",
                 "status": "NOT_AVAILABLE", "requires": "模型适用域判定"},
            ],
            contract={
                "geometry": "reach / station point",
                "crs": ("EPSG:3035" if ds == "LAMAHCE" else "GIS_PENDING"),
                "properties": ["reach_id", "station_uid", "period",
                               "qsim", "qsim_status", "model_version",
                               "dataset_version", "uncertainty"],
                "prohibited": "无模型运行不得写入任何 qsim 数值",
            },
            notice="真实模拟结果尚未产生，只展示合法空间数据与状态，"
                   "不编造预测分布")

    def _results_report(self, ds, qs):
        station = _one(qs, "station")
        fmt = (_one(qs, "format") or "json").lower()
        rpt = (self._report_syr(station) if ds == "SYRDARYA"
               else self._report_lamah(station))
        if fmt in ("md", "markdown", "text"):
            return self.env(ds, station=rpt.get("station"),
                            format="markdown", markdown=rpt["markdown"])
        return self.env(ds, **rpt)

    def _report_syr(self, station):
        code = self._syr_station(station) if station else SA.REACH_DOWN
        st = self.syr.stations[code]
        pts = self._monthly_axis(code)
        n_obs = sum(1 for p in pts if p["value"] is not None)
        n_miss = sum(1 for p in pts if p["value"] is None)
        qc = self._qc_counts()
        files = []
        for rec in self.syr.provenance():
            files.append({"file": rec["file"],
                          "sha256": rec["sha256"],
                          "bytes": rec.get("bytes"),
                          "records": rec.get("records")})
        snap = self.syr.snapshot
        md = []
        md.append("# VHS v%s 科研报告（Syr Darya）" % PLATFORM_VERSION)
        md.append("")
        md.append("生成时间：%s　规则版本：%s" % (_now(), RULES_VERSION))
        md.append("")
        md.append("## 1. 研究区域与目标测站")
        md.append("")
        md.append("- 研究区域：%s（%s）" % (DATASETS["SYRDARYA"]["title"],
                                          DATASETS["SYRDARYA"]["id"]))
        md.append("- 固定研究河段：16037 -> 16039 · 268 km（老师提供的案例）")
        md.append("- 本报告测站：%s %s" % (SA.uid(code), st.name or ""))
        md.append("- 测站观测年份：%s" % ", ".join(map(str, st.years)))
        md.append("")
        md.append("## 2. 数据来源（只读，哈希固定）")
        md.append("")
        for f in files:
            md.append("- %s　SHA-256 %s...　%d 字节　%d 行"
                      % (f["file"], (f["sha256"] or "NA")[:16],
                         f["bytes"] or 0, f["records"] or 0))
        md.append("")
        md.append("- 快照：%s（%s）" % (snap.snapshot_id if snap else "None",
                                     snap.loaded_at if snap else "n/a"))
        md.append("- 许可：老师提供、只读、本地展示；批量导出未授权")
        md.append("")
        md.append("## 3. 模型名称与架构")
        md.append("")
        md.append("- SYR-B0 锚点流量基线 / SYR-B1 +气象 / SYR-B2 +独立遥感")
        md.append("- 状态：仅接口定义（DEFINED_ONLY），未实现、未训练、未评估")
        md.append("")
        md.append("## 4. 参数配置")
        md.append("")
        md.append("- 参数配置可在模型层编辑并保存为 JSON；"
                  "本轮未产生任何训练配置运行")
        md.append("")
        md.append("## 5. 训练与评价区间")
        md.append("")
        md.append("- 训练区间：未定义（无运行）")
        md.append("- 评价区间：未定义（无运行）")
        md.append("")
        md.append("## 6. 观测与模拟过程线")
        md.append("")
        md.append("- 观测序列：%d 个月有值，%d 个月缺测/无记录（不插值）"
                  % (n_obs, n_miss))
        md.append("- 模拟序列：未生成（Qsim = null）")
        md.append("- 时间尺度：月；单位：源表未标注 UNKNOWN"
                  "（年径流核对支持 m3/s，推断）")
        md.append("")
        md.append("## 7. 评估指标")
        md.append("")
        md.append("| 指标 | 值 | 状态 |")
        md.append("| --- | --- | --- |")
        for k in METRICS:
            md.append("| %s | N/A | NOT_EVALUATED |" % k)
        md.append("")
        md.append("- 评价样本数：无（无共同样本）")
        md.append("")
        md.append("## 8. 误差与不确定性")
        md.append("")
        md.append("- 未运行 -> 无残差、无预测区间、无空间误差分布")
        md.append("")
        md.append("## 9. 数据质量摘要（真实统计）")
        md.append("")
        md.append("- 年径流一致性：%s"
                  % json.dumps(qc["w_check_status"], ensure_ascii=False))
        md.append("- QC 标记总数：%d" % qc["flags_total"])
        md.append("- 缺测率：见数据层覆盖矩阵（分母按站-年 x 12 月）")
        md.append("")
        md.append("## 10. 科研限制与解释")
        md.append("")
        md.append("- MODEL_EXECUTION = NOT_AUTHORIZED；prediction = null")
        md.append("- 历史观测展示不等于模型输入授权；不得据此训练或推断")
        md.append("- 单位未确认、年份离散、序号占位单元格需剔除")
        md.append("- 引水情景为反演低置信度值，不是实测取水")
        md.append("")
        md.append("## 11. 版本与哈希")
        md.append("")
        md.append("- 应用：VHS v%s（%s）" % (PLATFORM_VERSION, PLATFORM_BUILD))
        md.append("- 规则：%s / 数据集规则 %s"
                  % (RULES_VERSION, SA.RULES_VERSION))
        md.append("- 快照：%s" % (snap.snapshot_id if snap else "None"))
        return {"station": SA.uid(code), "name": st.name,
                "markdown": "\n".join(md),
                "sections": {
                    "research_area": DATASETS["SYRDARYA"]["title"],
                    "case_reach": "16037 -> 16039 · 268 km",
                    "station": SA.uid(code),
                    "data_sources": files,
                    "snapshot_id": snap.snapshot_id if snap else None,
                    "model": {"execution": RB.MODEL_EXECUTION,
                              "status": "DEFINED_ONLY", "prediction": None},
                    "periods": {"train": None, "test": None},
                    "observations": {"n_defined": n_obs, "n_missing": n_miss},
                    "simulation": None,
                    "metrics": {k: None for k in METRICS},
                    "qsim": None,
                },
                "executed_sections": ["research_area", "data_sources",
                                      "quality", "versions"],
                "not_executed_sections": ["training", "evaluation",
                                          "simulation", "uncertainty"]}

    def _report_lamah(self, station):
        sid = None
        if station:
            raw = str(station).split(":")[-1]
            if raw.isdigit() and int(raw) in self.store.stations:
                sid = int(raw)
        meta = self.store.meta()
        md = ["# VHS v%s 科研报告（LamaH-CE）" % PLATFORM_VERSION, "",
              "生成时间：%s　规则版本：%s" % (_now(), RULES_VERSION), "",
              "## 1. 研究区域与目标测站", "",
              "- 研究区域：%s（LAMAHCE）" % DATASETS["LAMAHCE"]["title"],
              "- 测站：%s" % (("LAMAHCE:%d" % sid) if sid else "未选择"), "",
              "## 2. 数据来源", "",
              "- 开放元数据：%d 站，有向边 %d 条"
              % (meta["counts"]["stations_total"],
                 meta["counts"]["directed_edges"]),
              "- 径流序列：sealed_runoff，未授权读取", "",
              "## 3. 模型名称与架构", "",
              "- 跨系统泛化（CROSS_SYSTEM）仅作为任务定义存在；未训练", "",
              "## 4-8. 训练 / 评价 / 过程线 / 指标 / 误差", "",
              "- 全部未执行（NOT_AUTHORIZED），无模拟值、无指标、无不确定性", "",
              "## 9. 科研限制", "",
              "- GEOMETRY_VERIFIED = 0；CONTROL_CERTIFIED = 0；"
              "FULLY_ADMITTED = 0", ""]
        return {"station": ("LAMAHCE:%d" % sid) if sid else None,
                "markdown": "\n".join(md),
                "sections": {"research_area": DATASETS["LAMAHCE"]["title"],
                             "station": ("LAMAHCE:%d" % sid) if sid else None,
                             "model": {"execution": RB.MODEL_EXECUTION,
                                       "prediction": None},
                             "simulation": None,
                             "metrics": {k: None for k in METRICS}},
                "executed_sections": ["research_area", "data_sources",
                                      "versions"],
                "not_executed_sections": ["training", "evaluation",
                                          "simulation", "uncertainty"]}

    # =================================================================
    # 5. evidence (second-level page)
    # =================================================================
    def evidence(self, qs):
        ds = self._ds(qs)
        page = _int(qs, "page", 0, 10 ** 6) or 0
        size = _int(qs, "size", 1, 200) or 50
        code = _one(qs, "code")
        sev = _one(qs, "severity")
        if ds != "SYRDARYA":
            return self.env(ds, flags=[], total=0, files=[], snapshot=None,
                            units=[], note="该数据集无 QC 标记表")
        flags = self.syr.flags
        if code:
            flags = [f for f in flags if f.code == code]
        if sev:
            flags = [f for f in flags if f.severity == sev]
        counts = {}
        for f in self.syr.flags:
            counts[f.code] = counts.get(f.code, 0) + 1
        severities = {}
        for f in self.syr.flags:
            severities[f.severity] = severities.get(f.severity, 0) + 1
        files = [{"file": r["file"], "sha256": r["sha256"],
                  "bytes": r.get("bytes"), "records": r.get("records"),
                  "encoding": r.get("encoding"),
                  "line_endings": r.get("line_endings"),
                  "status": r.get("status"), "access": r.get("access"),
                  "license": r.get("license")}
                 for r in self.syr.provenance()]
        snap = self.syr.snapshot
        return self.env(
            ds, total=len(flags), page=page, size=size,
            flags=[{"code": f.code, "severity": f.severity,
                    "scope": f.scope, "message": f.message,
                    "source_file": f.source_file,
                    "rule_version": f.rule_version}
                   for f in flags[page * size:(page + 1) * size]],
            flag_counts=counts, severity_counts=severities, files=files,
            snapshot=({"snapshot_id": snap.snapshot_id,
                       "loaded_at": snap.loaded_at,
                       "source_status": "VERIFIED_AT_LOAD"}
                      if snap else None),
            units=[{"field": "monthly mean/max/min Q", "unit": "UNKNOWN"},
                   {"field": "met p", "unit": "UNKNOWN"},
                   {"field": "met t", "unit": "UNKNOWN"},
                   {"field": "kzdam KC/KD/KS/KU", "unit": "UNKNOWN"},
                   {"field": "circle area_X_km2", "unit": "km2"},
                   {"field": "water balance W/dW/residual", "unit": "UNKNOWN"}],
            note="QC 错误完整列表、字段说明与文件 SHA-256 只在二级页面展示，"
                 "首页不铺开")

    # -- POST ------------------------------------------------------------
    def handle_post(self, path, body):
        try:
            p = path.rstrip("/")
            if p == "/api/v6/model/configs":
                return 200, {"status": "OK", **self.save_config(body)}
            if p in ("/api/v6/model/execute", "/api/v6/model/predict"):
                raise PError(403, "NOT_AUTHORIZED",
                             "MODEL_EXECUTION = NOT_AUTHORIZED; "
                             "prediction = null",
                             model_execution=RB.MODEL_EXECUTION)
            raise PError(404, "NOT_FOUND", "no POST route %s" % p)
        except PError as e:
            return _err(e)
