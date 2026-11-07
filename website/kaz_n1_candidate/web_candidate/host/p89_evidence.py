# -*- coding: utf-8 -*-
"""Read-only P8–P9C sealed-evidence API for portable handoff host.
Serves JSON summaries from package-relative results/; never trains or predicts.
"""
from __future__ import annotations
import csv
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent

def _find_h_root(start: pathlib.Path) -> pathlib.Path:
    cur = start
    for _ in range(8):
        if (cur / "results" / "p8" / "P8_FINAL_STATUS.json").is_file():
            return cur
        if (cur / "HANDOFF_ACCEPTANCE.json").is_file() and (cur / "results").is_dir():
            return cur
        cur = cur.parent
    # fallback: host -> web_candidate -> kaz_n1_candidate -> website -> H
    return start.parents[4]

H_ROOT = _find_h_root(HERE)
RESULTS = H_ROOT / "results"
DEMO = H_ROOT / "demo_data" / "p8_p9_web"


def _load_json(p: pathlib.Path):
    return json.loads(p.read_text(encoding="utf-8-sig"))


def _csv_rows(p: pathlib.Path, limit=None):
    with p.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if limit is not None:
        rows = rows[:limit]
    return rows


def _env():
    return {
        "display_scope": "SEALED_RESEARCH_EVIDENCE_READONLY",
        "production_display_permission": "NOT_GRANTED",
        "model_execution": "NOT_AUTHORIZED",
        "future_forecast": False,
        "formal_PUB": False,
        "new_validated_VHS": 0,
        "note_zh": "历史拟合/重建展示；非未来水位流量预报；非正式哈国PUB验证。",
    }


class P89Evidence:
    def handle(self, path: str, q: dict):
        leaf = path.rstrip("/").rsplit("/", 1)[-1]
        if leaf in ("execute", "predict", "train", "export", "download") or any(
            k in q for k in ("Qobs", "qobs", "format", "file", "path")
        ):
            return 403, {**_env(), "status": "OPERATION_NOT_AUTHORIZED"}

        if leaf in ("catalog", "index"):
            return 200, {
                **_env(),
                "modules": ["p8", "p9a", "p9b", "p9c"],
                "routes": {
                    "p8": "/api/v6/p89/p8",
                    "p9a": "/api/v6/p89/p9a",
                    "p9b": "/api/v6/p89/p9b",
                    "p9c": "/api/v6/p89/p9c",
                    "withdrawn": "/api/v6/p89/withdrawn",
                },
            }

        if leaf == "p8":
            st = _load_json(RESULTS / "p8" / "P8_FINAL_STATUS.json")
            basins = _csv_rows(RESULTS / "p8" / "P8_EIGHT_BASIN_SUMMARY.csv")
            orders = _csv_rows(RESULTS / "p8" / "P8_CLASSICAL_VS_STRAHLER.csv", limit=40)
            return 200, {
                **_env(),
                "task": "P8",
                "national_length_km": st.get("national_length_km"),
                "national_reaches": st.get("national_reaches"),
                "unassigned_length_km": st.get("unassigned_length_km"),
                "gauge_catalog": st.get("gauge_catalog"),
                "basins": basins,
                "order_sample": orders,
                "ORD_CLAS_ORD_STRA_note_zh": "河网等级同时报告 ORD_CLAS（经典分级）与 ORD_STRA（Strahler）；页面表格保留原始字段名。",
                "status": st,
            }

        if leaf == "p9a":
            st = _load_json(RESULTS / "p9a" / "P9A_FINAL_STATUS.json")
            orders = _csv_rows(RESULTS / "p9a" / "P9A_ORDER_1_TO_7.csv")
            chain = _csv_rows(RESULTS / "p9a" / "P9A_UPSTREAM_CHAIN_LENGTH.csv", limit=30)
            return 200, {
                **_env(),
                "task": "P9A",
                "QazSu_records": st.get("QazSu_records"),
                "provisional_gauges": st.get("provisional_gauges"),
                "topology_geometry_qualified": st.get("topology_geometry_qualified"),
                "official_gauges_identity_certified": st.get("official_gauges_identity_certified"),
                "pilot_basin_name": st.get("pilot_basin_name"),
                "not_certified_note_zh": "237为QazSu临时几何吸附；519为几何拓扑合格候选池，均非认证站；正式已验证新增VHS=0。",
                "order_1_to_7": orders,
                "chain_length_sample": chain,
                "status": st,
            }

        if leaf == "p9b":
            st = _load_json(RESULTS / "p9b" / "P9B_FINAL_STATUS.json")
            # main 20 + alternate 10 engineering candidates
            alt = _csv_rows(RESULTS / "p9b" / "P9B_ALTERNATE_TRIBUTARY_CANDIDATES.csv", limit=20)
            catch = _csv_rows(RESULTS / "p9b" / "P9B_CATCHMENT_DELINEATION_STATUS.csv", limit=40)
            return 200, {
                **_env(),
                "task": "P9B",
                "basin": "Balkhash-Alakol",
                "original_engineering_candidates": st.get("original_engineering_candidates"),
                "alternate_engineering_candidates": st.get("alternate_engineering_candidates"),
                "outlet_proxy_records": st.get("outlet_proxy_records"),
                "formal_VHS": st.get("formal_VHS"),
                "P10_status": st.get("P10_status"),
                "alternate_sample": alt,
                "catchment_sample": catch,
                "status": st,
            }

        if leaf == "p9c":
            st = _load_json(RESULTS / "p9c" / "P9C_FINAL_STATUS.json")
            metrics = _csv_rows(RESULTS / "p9c" / "e2_valid" / "E2_TEMPORAL_METRICS.csv")
            catch = _csv_rows(RESULTS / "p9c" / "P9C_CATCHMENT_VALIDATION.csv", limit=20)
            # keep only RAW ALL / year rows for display clarity
            return 200, {
                **_env(),
                "task": "P9C",
                "estimand_zh": "E2已知站历史月流量重建（目标月ERA5-Land已观测气象）；非未来预报；非正式PUB。",
                "numeric_complete_station_months": st.get("numeric_complete_station_months"),
                "new_WB_target_stations": st.get("new_WB_target_stations"),
                "E2_C0_NSE": st.get("E2_C0_NSE"),
                "E2_C0_KGE": st.get("E2_C0_KGE"),
                "E2_C0PT_NSE": st.get("E2_C0PT_NSE"),
                "E2_C0PT_KGE": st.get("E2_C0PT_KGE"),
                "E2_C0PT_MSE_skill": st.get("E2_C0PT_MSE_skill"),
                "Tauturgen_note_zh": "Tauturgen D8汇水约594.923 km2（相对来源面积约-3.11%）；驱动期2000–2015 ERA5-Land。",
                "metrics": metrics,
                "catchment_sample": catch,
                "status": st,
                "rejected_schema_models": st.get("rejected_schema_models"),
                "rejected_schema_predictions": st.get("rejected_schema_predictions"),
            }

        if leaf == "withdrawn":
            return 200, {
                **_env(),
                "status": "WITHDRAWN",
                "title_zh": "已撤回：P9C CSV错列错误结果",
                "body_zh": (
                    "早期 exploratory 因午夜时间/列对齐错误产生无效成绩"
                    "（含“655站月/40站年/120预测”等口径），不得作为正式结果。"
                    "正式有效结果见 /api/v6/p89/p9c 与 results/p9c/e2_valid。"
                ),
                "location": "results/p9c/e2_REJECTED_WITHDRAWN/",
            }

        return 404, {**_env(), "status": "NOT_FOUND"}
