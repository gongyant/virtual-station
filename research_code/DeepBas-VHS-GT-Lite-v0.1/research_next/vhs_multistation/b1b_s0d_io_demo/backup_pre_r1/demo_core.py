# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 虚拟水文站输入/输出功能原型 —— 核心逻辑（纯标准库，纯合成数据）。

状态：PROPOSED 本地原型，非 DeepBas 官方协议；所有数值为 SYNTHETIC_DEMO_ONLY。
复用：通过 sys.path 只读 import B1B-S0 的 vhs_contract.py（API_VERSION、ERROR_CODES、
      STATION_ID_RE、validate_response、make_error、scan_forbidden_fields、assert_log_safe），
      不修改旧文件；所有对外响应在返回前都经旧 validate_response 校验。
功能：F1 站点信息；F2 有向河网上游搜索；F3 合成准入规则；F4 预测权限控制（恒 NOT_AUTHORIZED）；
      合成演示序列放在 synthetic_display_data（永不放入 prediction）。
本模块不读取任何数据文件，不访问网络，不含任何真实流量。
"""
import datetime
import hashlib
import json
import logging
import math
import os
import random
import re
import sys
from collections import deque

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OLD_DIR = os.path.normpath(os.path.join(HERE, os.pardir, "b1b_s0_deepbas_mvp"))
if OLD_DIR not in sys.path:
    sys.path.insert(0, OLD_DIR)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import vhs_contract as vc  # noqa: E402  (B1B-S0 旧契约，只读复用)
import demo_data as dd     # noqa: E402

with open(os.path.join(OLD_DIR, "vhs_contract.py"), "rb") as _fh:
    OLD_CONTRACT_SHA256 = hashlib.sha256(_fh.read()).hexdigest()

STAGE = "VHS-NEXT-B1B-S0D"
PROTOCOL_STATUS = "PROPOSED_NOT_DEEPBAS_OFFICIAL"
PROTOCOL_NOTE = "PROPOSED：S0D 本地原型接口提议，非 DeepBas 官方协议，未与平台组确认"
DEMO_FLAG = "SYNTHETIC_DEMO_ONLY"
STATUS_ORDER = {"PASS": 0, "CONDITIONAL": 1, "UNKNOWN": 2, "BLOCKED": 3}
MAX_GRAPH_NODES = 500
MAX_GRAPH_EDGES = 2000
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,40}$")
RESTRICTED_LOG_WORDS = re.compile(r"(?i)\b(nse|kge|rmse|qobs|q_obs)\b")
OVERRIDE_KEYS = ("authorized", "authorization", "authorization_ref", "mode", "model", "model_id", "model_name",
                 "force", "override", "bypass", "admin", "token", "prediction", "prediction_authorized",
                 "science_stage", "data_class", "allow_real", "real")

# 新增别名 -> 旧错误码（向后兼容：响应中 error.code 一律为旧码，别名放在 error.alias）
ERROR_ALIAS_MAP = {
    "INVALID_REQUEST": ("VHS-E001", "VHS-E003", "VHS-E011"),
    "UNKNOWN_STATION": ("VHS-E002",),
    "UNKNOWN_DATASET": ("VHS-E004",),
    "ROUTE_NOT_FOUND": ("VHS-E011",),
    "METHOD_NOT_ALLOWED": ("VHS-E011",),
    "REQUEST_TOO_LARGE": ("VHS-E011",),
    "INTERNAL_CONTRACT_VIOLATION": ("VHS-E011",),
}

LOG = logging.getLogger("vhs_s0d")


def safe_log(record, level=logging.INFO):
    """经过滤的日志：复用旧 assert_log_safe，并额外拦截 NSE/KGE 等词；不合规记录整体替换为占位。"""
    try:
        vc.assert_log_safe(record)
        text = json.dumps(record, ensure_ascii=False, sort_keys=True) if isinstance(record, dict) else str(record)
        if RESTRICTED_LOG_WORDS.search(text):
            raise vc.ContractError("VHS-E009", "restricted word in log text")
    except vc.ContractError as exc:
        LOG.warning(json.dumps({"event": "log_record_blocked", "code": exc.code}))
        return False
    LOG.log(level, text)
    return True


def worst(statuses):
    vals = [s for s in statuses if s in STATUS_ORDER]
    if not vals:
        return "UNKNOWN"
    return max(vals, key=lambda s: STATUS_ORDER[s])


def safe_field_names(keys):
    """只回显安全的字段名（不回显值；命中旧契约禁用键模式的名字只计数）。"""
    shown, hidden = [], 0
    for k in keys:
        k = str(k)
        if SAFE_NAME_RE.match(k) and not vc.scan_forbidden_fields({k: None}):
            shown.append(k)
        else:
            hidden += 1
    return sorted(shown), hidden


def request_id(function, params):
    raw = json.dumps([function, params], sort_keys=True, ensure_ascii=True, default=str)
    return "S0D-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


class RequestError(Exception):
    def __init__(self, alias, old_code, reason_code, detail, http_status=400):
        super().__init__(detail)
        assert old_code in vc.ERROR_CODES and old_code in ERROR_ALIAS_MAP[alias]
        self.alias, self.old_code, self.reason_code = alias, old_code, reason_code
        self.detail, self.http_status = detail, http_status


class GraphInputError(Exception):
    pass


def common_meta(function):
    return {"protocol_status": PROTOCOL_STATUS, "protocol_note": PROTOCOL_NOTE, "data_class": DEMO_FLAG,
            "stage": STAGE, "function": function,
            "contract_ref": {"module": "b1b_s0_deepbas_mvp/vhs_contract.py", "api_version": vc.API_VERSION,
                             "sha256": OLD_CONTRACT_SHA256}}


def error_response(err, function, rid, predict=False):
    resp = vc.make_error(err.old_code, err.detail, rid)
    resp["error"]["alias"] = err.alias
    resp["error"]["reason_code"] = err.reason_code
    resp.update(common_meta(function))
    resp["s0d_status"] = err.alias
    if predict:
        resp["s0d_status"] = "NOT_AUTHORIZED"
        resp["prediction_authorized"] = {"status": "NOT_AUTHORIZED", "authorization_ref": None,
                                         "reason": "S0D 阶段任何预测请求均不授权（请求本身也未通过输入校验）"}
    resp["prediction"] = None
    return finalize(resp, function, rid)[1], err.http_status


def finalize(resp, function, rid):
    """出口闸门：prediction 强制为 null + 旧 validate_response 校验；不合规则替换为内部错误。"""
    problems = []
    if resp.get("prediction", "MISSING") is not None:
        problems.append(("VHS-E010", "S0D policy: prediction must be null"))
    problems += vc.validate_response(resp)
    if problems:
        safe_log({"event": "contract_violation_blocked", "function": function, "code": problems[0][0]},
                 logging.ERROR)
        bad = vc.make_error("VHS-E011", "internal response failed contract validation", rid)
        bad["error"]["alias"] = "INTERNAL_CONTRACT_VIOLATION"
        bad["error"]["reason_code"] = problems[0][0]
        bad.update(common_meta(function))
        bad["s0d_status"] = "INTERNAL_CONTRACT_VIOLATION"
        return False, bad
    return True, resp


# ------------------------------------------------------------------ 输入校验
def check_station_id(sid):
    if sid is None or (isinstance(sid, str) and not sid.strip()):
        raise RequestError("INVALID_REQUEST", "VHS-E001", "STATION_ID_MISSING", "station_id is required", 400)
    if not isinstance(sid, str) or not vc.STATION_ID_RE.match(sid):
        raise RequestError("INVALID_REQUEST", "VHS-E003", "STATION_ID_INVALID_FORMAT",
                           "station_id has invalid format (allowed: A-Z a-z 0-9 _ . : -, length 1-64)", 400)
    return sid


def check_dataset(ds_id, ds_ver):
    ds_id = dd.DATASET_ID if ds_id in (None, "") else ds_id
    ds_ver = dd.DATASET_VERSION if ds_ver in (None, "") else ds_ver
    if ds_id != dd.DATASET_ID or ds_ver != dd.DATASET_VERSION:
        raise RequestError("UNKNOWN_DATASET", "VHS-E004", "DATASET_OR_VERSION_UNKNOWN",
                           "only %s %s is registered in this synthetic demo" % (dd.DATASET_ID, dd.DATASET_VERSION),
                           404)
    return ds_id, ds_ver


def get_station(sid):
    rec = dd.STATIONS.get(sid)
    if rec is None:
        raise RequestError("UNKNOWN_STATION", "VHS-E002", "UNKNOWN_STATION",
                           "station %s not in %s %s" % (sid, dd.DATASET_ID, dd.DATASET_VERSION), 404)
    return rec


def check_params(params, allowed):
    unknown = [k for k in params if k not in allowed]
    if unknown:
        shown, hidden = safe_field_names(unknown)
        raise RequestError("INVALID_REQUEST", "VHS-E011", "UNKNOWN_PARAMETER",
                           "unknown parameter(s): %s%s" % (", ".join(shown) or "-",
                                                            " (+%d hidden)" % hidden if hidden else ""), 400)


def parse_time_range(start, end):
    if start in (None, "") or end in (None, ""):
        raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_RANGE_MISSING", "start and end are required", 400)
    out = []
    for name, val in (("start", start), ("end", end)):
        if not isinstance(val, str) or not DATE_RE.match(val):
            raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_FORMAT_INVALID",
                               "%s must be YYYY-MM-DD" % name, 400)
        try:
            out.append(datetime.date.fromisoformat(val))
        except ValueError:
            raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_FORMAT_INVALID",
                               "%s is not a valid calendar date" % name, 400)
    s, e = out
    if s > e:
        raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_RANGE_START_AFTER_END", "start must be <= end", 400)
    lo, hi = (datetime.date.fromisoformat(x) for x in dd.SYNTHETIC_WINDOW)
    if s < lo or e > hi:
        raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_RANGE_OUTSIDE_SYNTHETIC_WINDOW",
                           "range must lie within synthetic window %s..%s" % dd.SYNTHETIC_WINDOW, 400)
    if (e - s).days + 1 > dd.MAX_SPAN_DAYS:
        raise RequestError("INVALID_REQUEST", "VHS-E011", "TIME_RANGE_TOO_LONG",
                           "range longer than %d days" % dd.MAX_SPAN_DAYS, 400)
    return s, e


# ------------------------------------------------------------------ F2 有向图分析
def normalize_graph(graph):
    if not isinstance(graph, dict):
        raise GraphInputError("graph must be an object")
    raw_nodes, raw_edges = graph.get("nodes"), graph.get("edges")
    if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
        raise GraphInputError("graph.nodes and graph.edges must be lists")
    if len(raw_nodes) > MAX_GRAPH_NODES or len(raw_edges) > MAX_GRAPH_EDGES:
        raise GraphInputError("graph too large")
    nodes = {}
    for n in raw_nodes:
        nid = n.get("id") if isinstance(n, dict) else None
        if not isinstance(nid, str) or not vc.STATION_ID_RE.match(nid):
            raise GraphInputError("invalid node id")
        if nid in nodes:
            raise GraphInputError("duplicate node id %s" % nid)
        nodes[nid] = n
    edges, seen = [], set()
    for i, e in enumerate(raw_edges):
        if not isinstance(e, dict):
            raise GraphInputError("edge %d must be an object" % i)
        eid = e.get("id") or "EDGE_%d" % i
        if eid in seen:
            raise GraphInputError("duplicate edge id %s" % eid)
        seen.add(eid)
        src, dst = e.get("from"), e.get("to")
        if src not in nodes or dst not in nodes:
            raise GraphInputError("edge %s references unknown node" % eid)
        kind = e.get("kind", "natural")
        snap = e.get("snap_status", "UNKNOWN")
        if kind not in dd.EDGE_KINDS or snap not in dd.SNAP_STATUSES:
            raise GraphInputError("edge %s has invalid kind/snap_status" % eid)
        edges.append({"id": eid, "from": src, "to": dst, "kind": kind, "snap_status": snap,
                      "note": e.get("note", "")})
    return nodes, edges


def edge_flags(e):
    flags = []
    if e["kind"] != "natural":
        flags.append("ARTIFICIAL_TRANSFER")
    if e["snap_status"] != "CERTIFIED":
        flags.append("SNAP_" + e["snap_status"])
    return flags


def find_cycles(nodes, edges, restrict=None):
    """迭代式三色 DFS；返回检测到的环（节点序列，首尾相同）。自环同样报告。"""
    allowed = set(nodes) if restrict is None else set(restrict)
    fwd = {n: [] for n in allowed}
    for e in edges:
        if e["from"] in allowed and e["to"] in allowed:
            fwd[e["from"]].append(e["to"])
    for n in fwd:
        fwd[n].sort()
    color = {n: 0 for n in allowed}  # 0 白 1 灰 2 黑
    cycles, keys = [], set()
    for root in sorted(allowed):
        if color[root]:
            continue
        stack = [(root, iter(fwd[root]))]
        path = [root]
        color[root] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                color[node] = 2
                stack.pop()
                path.pop()
            elif color[nxt] == 1:
                cyc = path[path.index(nxt):] + [nxt]
                key = frozenset(cyc)
                if key not in keys:
                    keys.add(key)
                    cycles.append(cyc)
            elif color[nxt] == 0:
                color[nxt] = 1
                path.append(nxt)
                stack.append((nxt, iter(fwd[nxt])))
    return cycles


def _bfs(start, adj):
    seen, order, q = {start}, [], deque([start])
    while q:
        cur = q.popleft()
        for nxt in adj[cur]:
            if nxt not in seen:
                seen.add(nxt)
                order.append(nxt)
                q.append(nxt)
    return order


def analyze_network(graph, target):
    """F2：真正的有向图搜索。
    上游 = 从目标沿"反向边"（to->from）BFS 可达的节点；下游 = 沿正向边 BFS 可达；
    对照候选 = 与目标不在同一弱连通分量的节点；坐标从不参与关系判断。"""
    nodes, edges = normalize_graph(graph)
    gid = graph.get("graph_id", "CUSTOM_GRAPH")
    display = {"graph_id": gid, "data_class": DEMO_FLAG,
               "nodes": [{"id": k, "lat": v.get("lat"), "lon": v.get("lon"), "label": v.get("label", k)}
                         for k, v in nodes.items()],
               "edges": edges}
    method = {"algorithm": "reverse BFS over directed edges (to->from) from target for upstream; forward BFS "
                           "for downstream; undirected BFS for weak components; iterative 3-colour DFS for cycles; "
                           "reverse BFS from uncertain edges for path-uncertainty propagation",
              "edge_direction": "from -> to = 沿水流方向（上游 -> 下游）",
              "uses_coordinates_for_relations": False,
              "label": "PROPOSED / SYNTHETIC"}
    base = {"graph_id": gid, "target_station_id": target, "data_class": DEMO_FLAG, "method": method,
            "graph_for_display": display}
    if target not in nodes:
        base.update({"connection_status": "NOT_IN_NETWORK", "upstream_nodes": [], "downstream_nodes": [],
                     "same_system_not_upstream": [], "nonconnected_control_candidates": [], "cycles": [],
                     "uncertain_edges_in_upstream_subgraph": [], "display_roles": {},
                     "topology": {"status": "UNKNOWN", "reasons": ["目标站不在该合成有向图中，无法判断上下游"]}})
        return base
    fwd = {n: [] for n in nodes}
    rev = {n: [] for n in nodes}
    und = {n: set() for n in nodes}
    for e in sorted(edges, key=lambda x: x["id"]):
        fwd[e["from"]].append(e)
        rev[e["to"]].append(e)
        und[e["from"]].add(e["to"])
        und[e["to"]].add(e["from"])
    # 反向 BFS：上游
    parent, hops, order, q = {target: None}, {target: 0}, [], deque([target])
    while q:
        cur = q.popleft()
        for e in rev[cur]:
            u = e["from"]
            if u not in parent:
                parent[u], hops[u] = e, hops[cur] + 1
                order.append(u)
                q.append(u)
    upstream = set(order)
    downstream_order = _bfs(target, {n: [e["to"] for e in fwd[n]] for n in nodes})
    downstream = set(downstream_order) - {target}
    comp_order = _bfs(target, {n: sorted(und[n]) for n in nodes})
    component = set(comp_order) | {target}
    cycles = find_cycles(nodes, edges, restrict=component)
    cycle_nodes = set(x for c in cycles for x in c)
    reach_target = upstream | {target}
    sub_edges = [e for e in edges if e["from"] in reach_target and e["to"] in reach_target]
    uncertain = [e for e in sub_edges if edge_flags(e)]
    # 不确定性传播：凡存在一条经过不确定边通向目标的路径的节点，都标记
    rev_nodes = {n: [e["from"] for e in rev[n]] for n in nodes}
    tainted = {}
    for e in uncertain:
        for n in [e["from"]] + _bfs(e["from"], rev_nodes):
            tainted.setdefault(n, set()).add(e["id"])
    up_list = []
    for u in sorted(order, key=lambda x: (hops[x], x)):
        path_edges, cur = [], u
        while cur != target:
            pe = parent[cur]
            path_edges.append(pe)
            cur = pe["to"]
        flags = sorted(set(f for pe in path_edges for f in edge_flags(pe)))
        reasons = ["合成有向路径存在（%d 跳），关系只来自有向边" % hops[u]]
        if cycles:
            status = "BLOCKED"
            reasons.append("目标所在水系检测到环路，拓扑无效")
        elif u in tainted:
            status = "CONDITIONAL"
            reasons.append("至少一条通向目标的路径经过不确定边：%s" % ", ".join(sorted(tainted[u])))
        else:
            status = "PASS"
            reasons.append("所有通向目标的路径边均为 natural/CERTIFIED（仅在合成图内成立）")
        up_list.append({"station_id": u, "hops": hops[u],
                        "path_nodes": [u] + [pe["to"] for pe in path_edges],
                        "path_edge_ids": [pe["id"] for pe in path_edges],
                        "path_edges": [{"id": pe["id"], "from": pe["from"], "to": pe["to"], "kind": pe["kind"],
                                        "snap_status": pe["snap_status"]} for pe in path_edges],
                        "path_flags": flags,
                        "uncertain_edges_on_any_path": sorted(tainted.get(u, [])),
                        "also_downstream_of_target": u in downstream,
                        "relation_status": {"status": status, "reasons": reasons}})
    down_list = [{"station_id": d, "reason": "沿流向可从目标到达（下游），不能算上游"}
                 for d in sorted(downstream - upstream)]
    same_sys = []
    for n in sorted(component - upstream - downstream - {target}):
        same_sys.append({"station_id": n, "reason": "与目标同属一个弱连通水系（经下游汇合或人工输水边相连），"
                                                    "既不在上游，也不是独立的不连通对照"})
    # 其余弱连通分量编号
    comp_id, other = {}, sorted(set(nodes) - component)
    k = 0
    for n in other:
        if n in comp_id:
            continue
        k += 1
        for m in [n] + _bfs(n, {x: sorted(und[x]) for x in nodes}):
            comp_id[m] = "SYN_COMPONENT_%d" % k
    controls = [{"station_id": n, "component_id": comp_id[n],
                 "reason": "与目标不存在任何有向或无向连通（不同弱连通分量）",
                 "relation_status": {"status": "CONDITIONAL",
                                     "reasons": ["拓扑不连通（合成图内成立）",
                                                 "未做属性/气候共同支持匹配（S0D 不做匹配）"]}}
                for n in other]
    if cycles:
        conn, topo = "CYCLE_DETECTED", {"status": "BLOCKED", "reasons": [
            "检测到环路：" + " -> ".join(c) for c in cycles] + ["有向河网不应含环；需修正拓扑后才能判断上游"]}
    elif not up_list:
        conn, topo = "NO_UPSTREAM", {"status": "PASS" if not uncertain else "CONDITIONAL",
                                     "reasons": ["目标在合成图中无上游节点（源头或孤立节点）"]}
    else:
        conn = "HAS_UPSTREAM"
        if uncertain:
            topo = {"status": "CONDITIONAL", "reasons": ["上游子图含不确定边：" + ", ".join(
                "%s(%s)" % (e["id"], "+".join(edge_flags(e))) for e in uncertain)]}
        else:
            topo = {"status": "PASS", "reasons": ["上游子图全部为 natural/CERTIFIED 边（合成）"]}
    roles = {target: "TARGET"}
    for u in up_list:
        roles[u["station_id"]] = "UPSTREAM_" + u["relation_status"]["status"]
    for d in down_list:
        roles[d["station_id"]] = "DOWNSTREAM"
    for s in same_sys:
        roles[s["station_id"]] = "SAME_SYSTEM_NOT_UPSTREAM"
    for c in controls:
        roles[c["station_id"]] = "NONCONNECTED_CONTROL"
    for n in cycle_nodes:
        roles[n] = "CYCLE" if n != target else "TARGET_IN_CYCLE"
    base.update({"connection_status": conn, "upstream_nodes": up_list, "downstream_nodes": down_list,
                 "same_system_not_upstream": same_sys, "nonconnected_control_candidates": controls,
                 "cycles": cycles,
                 "uncertain_edges_in_upstream_subgraph": [{"id": e["id"], "flags": edge_flags(e),
                                                           "note": e.get("note", "")} for e in uncertain],
                 "display_roles": roles, "topology": topo})
    return base


def check_network_invariants(res):
    """供测试与运行期自检：上游/下游/对照互斥性。返回违规描述列表。"""
    up = {u["station_id"] for u in res["upstream_nodes"]}
    ctrl = {c["station_id"] for c in res["nonconnected_control_candidates"]}
    down = {d["station_id"] for d in res["downstream_nodes"]}
    same = {s["station_id"] for s in res["same_system_not_upstream"]}
    bad = []
    if up & ctrl:
        bad.append("upstream overlaps controls: %s" % sorted(up & ctrl))
    if down & ctrl or same & ctrl:
        bad.append("same-system node listed as control")
    if up & down and res["connection_status"] != "CYCLE_DETECTED":
        bad.append("node both upstream and downstream without cycle")
    if res["target_station_id"] in up | ctrl | down:
        bad.append("target listed in its own relations")
    return bad


# ------------------------------------------------------------------ F3 合成准入规则表
KNOWN_QC_FIELDS = ("completeness_class", "qc_flags_reviewed", "metadata_fields_complete", "source")
RULE_TABLE_VERSION = "S0D-SYNTHETIC-ADMISSION-RULES-0.1 (PROPOSED / SYNTHETIC，非真实阈值)"
# 显式规则表：(rule_id, 名称, 输入取值 -> (元数据展示结论, 科学准入结论, 原因))
RULE_TABLE = {
    "R01_QC_RECORD_PRESENT": {
        "PRESENT": ("PASS", "PASS", "QC 元数据记录存在（合成）"),
        "MISSING": ("CONDITIONAL", "UNKNOWN", "QC 元数据缺失：站点元数据仍可查看，科学准入无法判断"),
    },
    "R02_QC_COMPLETENESS_CLASS": {
        "COMPLETE": ("PASS", "PASS", "合成完整性类别 COMPLETE"),
        "PARTIAL_GAPS": ("PASS", "CONDITIONAL", "存在缺测（合成类别标记）；不影响元数据查询，科学使用需另行评估"),
        "UNKNOWN": ("PASS", "UNKNOWN", "完整性类别未知或未提供"),
    },
    "R03_LICENSE_STATUS": {
        "PERMITTED": ("PASS", "PASS", "合成许可状态 PERMITTED"),
        "RESTRICTED": ("CONDITIONAL", "CONDITIONAL", "许可受限：仅限内部展示"),
        "UNKNOWN": ("CONDITIONAL", "UNKNOWN", "许可未知：不得自动升为 PASS；元数据仅限本地合成演示"),
        "DENIED": ("BLOCKED", "BLOCKED", "许可拒绝"),
    },
    "R04_TOPOLOGY_CERTIFICATION": {
        "CERTIFIED": ("PASS", "PASS", "合成拓扑认证 CERTIFIED"),
        "PATH_OK_SNAP_UNCERTIFIED": ("PASS", "CONDITIONAL", "有向路径通过，但站点 snapping 未认证"),
        "NOT_CERTIFIED": ("PASS", "UNKNOWN", "拓扑未认证"),
        "FAILED": ("PASS", "BLOCKED", "拓扑认证失败"),
    },
    "R05_NETWORK_GRAPH_CHECK": {
        "PASS": ("PASS", "PASS", "F2 有向图检查通过（合成）"),
        "CONDITIONAL": ("PASS", "CONDITIONAL", "F2 发现上游路径含人工输水/snapping 不确定边"),
        "UNKNOWN": ("PASS", "UNKNOWN", "站点不在合成有向图中"),
        "BLOCKED": ("PASS", "BLOCKED", "F2 检测到环路等拓扑错误"),
    },
    "R06_TARGET_Q_ACCESS": {
        "SEALED": ("PASS", "BLOCKED", "目标 Q 封存：禁止用于预测/训练/评分，本模块不读取；元数据查询不需要 Q"),
        "NOT_APPLICABLE_SYNTHETIC": ("PASS", "PASS", "合成站点不存在任何 Q 序列"),
        "UNKNOWN": ("PASS", "UNKNOWN", "目标序列访问角色未知"),
    },
    "R07_UNKNOWN_QC_FIELDS": {
        "NONE": ("PASS", "PASS", "QC 记录无未知字段"),
        "PRESENT": ("PASS", "UNKNOWN", "QC 记录含未登记字段：不予信任，科学准入判为 UNKNOWN"),
        "NOT_APPLICABLE": ("PASS", "UNKNOWN", "QC 记录缺失，无法检查字段"),
    },
    "R08_EVIDENCE_REFS": {
        "PRESENT": ("PASS", "PASS", "存在证据引用（合成，等级 PROPOSED）"),
        "MISSING": ("CONDITIONAL", "UNKNOWN", "缺少证据引用"),
    },
}
RULE_NAMES = {
    "R01_QC_RECORD_PRESENT": "QC 元数据记录是否存在",
    "R02_QC_COMPLETENESS_CLASS": "QC 完整性类别（类别型，无数值阈值）",
    "R03_LICENSE_STATUS": "数据许可状态",
    "R04_TOPOLOGY_CERTIFICATION": "拓扑认证状态（输入）",
    "R05_NETWORK_GRAPH_CHECK": "有向图检查（来自 F2）",
    "R06_TARGET_Q_ACCESS": "目标 Q 访问角色",
    "R07_UNKNOWN_QC_FIELDS": "QC 未知字段",
    "R08_EVIDENCE_REFS": "证据引用",
}


def _rule(rule_id, key):
    table = RULE_TABLE[rule_id]
    if key not in table:
        return {"rule_id": rule_id, "name": RULE_NAMES[rule_id], "input": "UNRECOGNIZED",
                "metadata_display": "UNKNOWN", "science_admission": "UNKNOWN",
                "reason": "输入取值未在合成规则表中登记 -> UNKNOWN", "label": "PROPOSED / SYNTHETIC"}
    md, sc, why = table[key]
    return {"rule_id": rule_id, "name": RULE_NAMES[rule_id], "input": key, "metadata_display": md,
            "science_admission": sc, "reason": why, "label": "PROPOSED / SYNTHETIC"}


def audit_station(rec, net):
    qc = rec.get("qc")
    rules = [_rule("R01_QC_RECORD_PRESENT", "PRESENT" if isinstance(qc, dict) else "MISSING")]
    if isinstance(qc, dict):
        rules.append(_rule("R02_QC_COMPLETENESS_CLASS", qc.get("completeness_class") or "UNKNOWN"))
        unknown = [k for k in qc if k not in KNOWN_QC_FIELDS]
        r7 = _rule("R07_UNKNOWN_QC_FIELDS", "PRESENT" if unknown else "NONE")
        if unknown:
            shown, hidden = safe_field_names(unknown)
            r7["unknown_field_names"] = shown
            r7["unknown_field_hidden_count"] = hidden
    else:
        rules.append(_rule("R02_QC_COMPLETENESS_CLASS", "UNKNOWN"))
        r7 = _rule("R07_UNKNOWN_QC_FIELDS", "NOT_APPLICABLE")
    rules.append(_rule("R03_LICENSE_STATUS", rec.get("license_status") or "UNKNOWN"))
    rules.append(_rule("R04_TOPOLOGY_CERTIFICATION", rec.get("topology_certification") or "NOT_CERTIFIED"))
    rules.append(_rule("R05_NETWORK_GRAPH_CHECK", net["topology"]["status"]))
    rules.append(_rule("R06_TARGET_Q_ACCESS", rec.get("target_q_access") or "UNKNOWN"))
    rules.append(r7)
    rules.append(_rule("R08_EVIDENCE_REFS", "PRESENT" if rec.get("evidence_refs") else "MISSING"))
    rules.sort(key=lambda r: r["rule_id"])
    md = worst(r["metadata_display"] for r in rules)
    sc = worst(r["science_admission"] for r in rules)
    return {
        "rule_table_version": RULE_TABLE_VERSION,
        "precedence": "BLOCKED > UNKNOWN > CONDITIONAL > PASS（取最差）；仅当全部规则为 PASS 才得 PASS",
        "metadata_display": {"status": md, "reasons": [r["rule_id"] + ": " + r["reason"] for r in rules
                                                        if r["metadata_display"] != "PASS"]},
        "science_admission": {"status": sc, "reasons": [r["rule_id"] + ": " + r["reason"] for r in rules
                                                         if r["science_admission"] != "PASS"]},
        "prediction_authorization": {"status": "NOT_AUTHORIZED",
                                     "reason": "R09: S0D 阶段任何科学准入结论（含 PASS）都不构成预测授权"},
        "rules": rules,
        "label": "PROPOSED / SYNTHETIC：规则与取值为演示用合成规则，不是真实科学阈值，未使用任何真实 Q",
    }


# ------------------------------------------------------------------ 合成演示序列（非预测）
def synthetic_series(station_id, start, end):
    seed = int(hashlib.sha256(("S0D|" + station_id).encode("utf-8")).hexdigest()[:8], 16)
    times, values = [], []
    d = start
    while d <= end:
        doy = d.timetuple().tm_yday
        rng = random.Random(seed ^ d.toordinal())
        v = 50.0 + 20.0 * math.sin(2 * math.pi * (doy - 80) / 366.0) + 5.0 * math.sin(2 * math.pi * (d.toordinal() % 7) / 7.0) \
            + rng.uniform(-3.0, 3.0)
        times.append(d.isoformat())
        values.append(round(v, 3))
        d += datetime.timedelta(days=1)
    return {
        "data_class": DEMO_FLAG,
        "banner": "SYNTHETIC_DEMO_ONLY —— 确定性公式生成的合成信号，不是流量、不是预测，不得用于任何决策或科研结论",
        "series_kind": "SYNTHETIC_SIGNAL_NOT_DISCHARGE",
        "is_prediction": False,
        "unit": "SYN_UNIT",
        "unit_note": "任意合成单位（arbitrary synthetic unit）；不是 m3/s，不代表任何物理量",
        "time_resolution": "P1D",
        "time_zone": "UTC",
        "time_index": times,
        "values": values,
        "generator": {
            "formula": "v = 50 + 20*sin(2*pi*(doy-80)/366) + 5*sin(2*pi*(ordinal mod 7)/7) + u;  u ~ Uniform(-3,3) "
                       "from random.Random(seed XOR date.toordinal())",
            "seed_basis": "int(sha256('S0D|' + station_id)[:8], 16)",
            "inputs": "仅 station_id 与日期；不读取任何文件、不使用任何真实数据",
        },
    }


# ------------------------------------------------------------------ 响应组装
def _relations(net):
    donors = []
    for u in net["upstream_nodes"]:
        donors.append({"station_id": u["station_id"], "relation": "CONNECTED_UPSTREAM",
                       "relation_status": u["relation_status"], "evidence_level": "PROPOSED",
                       "path_ref": "S0D_PATH:" + ">".join(u["path_edge_ids"]),
                       "reach_distance_km": None, "area_ratio": None,
                       "data_role": "AUTHORIZED_DONOR_Q_FUTURE", "access_status": {"status": "NOT_AUTHORIZED"},
                       "synthetic": True})
    controls = []
    for c in net["nonconnected_control_candidates"]:
        controls.append({"station_id": c["station_id"], "relation": "NONCONNECTED_CONTROL",
                         "relation_status": c["relation_status"], "evidence_level": "PROPOSED",
                         "dependency_group": c["component_id"], "match_basis": [],
                         "data_role": "AUTHORIZED_DONOR_Q_FUTURE", "access_status": {"status": "NOT_AUTHORIZED"},
                         "synthetic": True})
    return donors, controls


def build_envelope(rec, net, aud, function, rid, science_stage="METADATA_ONLY"):
    lat, lon = rec["coordinates_lat_lon"]
    donors, controls = _relations(net)
    r = {x["rule_id"]: x for x in aud["rules"]}
    topo_status = worst([r["R04_TOPOLOGY_CERTIFICATION"]["science_admission"], net["topology"]["status"]])
    ready_rules = [r["R01_QC_RECORD_PRESENT"], r["R02_QC_COMPLETENESS_CLASS"], r["R07_UNKNOWN_QC_FIELDS"]]
    env = {
        "api_version": vc.API_VERSION,
        "response_type": "virtual_station_status",
        "request_id": rid,
        "dataset_id": dd.DATASET_ID,
        "dataset_version": dd.DATASET_VERSION,
        "target_station_id": rec["station_id"],
        "target_station_name": rec["station_name"],
        "region_scope": dd.REGION_SCOPE,
        "coordinate_reference_system": {
            "epsg": 4326, "name": "WGS 84", "units": "degree",
            "epsg_authority_axis_order": ["latitude", "longitude"],
            "coordinate_axis_order_in_payload": ["latitude", "longitude"],
            "coordinates": [lat, lon],
            "note": "SYNTHETIC 坐标（虚构）；EPSG:4326，载荷轴序为 [纬度, 经度]，单位为度；坐标仅用于示意图，不用于判断上下游"},
        "catchment_area_km2": {"value": rec["catchment_area_km2"], "status": "CONDITIONAL",
                               "source": "SYNTHETIC_DEMO_ONLY 虚构数值（demo_data.py）"},
        "river_network_ref": {"network_id": net["graph_id"], "reach_id": None, "snap_distance_m": None,
                              "snap_status": {"CERTIFIED": "CERTIFIED", "PATH_OK_SNAP_UNCERTIFIED": "UNCERTIFIED"}
                              .get(rec.get("topology_certification"), "UNKNOWN")},
        "topology_status": {"status": topo_status,
                            "reasons": [r["R04_TOPOLOGY_CERTIFICATION"]["reason"]] + net["topology"]["reasons"]},
        "upstream_donors": donors,
        "nonconnected_controls": controls,
        "control_status": ({"status": "CONDITIONAL", "reasons": ["存在拓扑不连通候选，但未做共同支持匹配（合成）"]}
                           if controls else {"status": "BLOCKED", "reasons": ["无拓扑不连通对照候选"]}),
        "data_readiness": {"status": worst(x["science_admission"] for x in ready_rules),
                           "reasons": [x["rule_id"] + ": " + x["reason"] for x in ready_rules],
                           "forcing": {"role": "OPEN_FORCING", "status": "UNKNOWN"},
                           "target_series_access": {"role": "SEALED_TARGET_Q" if rec.get("target_q_access") == "SEALED"
                                                    else "UNKNOWN", "exposed": False}},
        "license_status": {"status": r["R03_LICENSE_STATUS"]["science_admission"],
                           "reasons": [r["R03_LICENSE_STATUS"]["reason"]]},
        "science_stage": science_stage,
        "admission_status": aud["science_admission"],
        "prediction_authorized": {"status": "NOT_AUTHORIZED", "authorization_ref": None,
                                  "reason": "S0D 阶段：任何真实流量预测均未授权"},
        "prediction": None,
        "evidence_refs": list(rec.get("evidence_refs") or []),
        "warnings": ["SYNTHETIC_DEMO_ONLY：全部站点、坐标、河网、面积与状态均为虚构，不代表任何真实水文站",
                     "PROPOSED：S0D 本地原型接口，非 DeepBas 官方协议；未完成平台集成",
                     "prediction 恒为 null；合成演示序列只出现在 synthetic_display_data"],
    }
    env.update(common_meta(function))
    return env


def _station_context(params, allowed):
    check_params(params, allowed)
    sid = check_station_id(params.get("station_id"))
    check_dataset(params.get("dataset_id"), params.get("dataset_version"))
    rec = get_station(sid)
    net = analyze_network(dd.GRAPHS[rec["graph_id"]], sid)
    aud = audit_station(rec, net)
    return sid, rec, net, aud


STATION_PARAMS = ("station_id", "dataset_id", "dataset_version")
DEMO_PARAMS = STATION_PARAMS + ("start", "end")


def handle(function, params):
    """统一入口：返回 (http_status, response_dict)。function ∈ station/network/audit/demo。"""
    rid = request_id(function, params)
    try:
        if function == "demo":
            sid, rec, net, aud = _station_context(params, DEMO_PARAMS)
            s, e = parse_time_range(params.get("start"), params.get("end"))
        else:
            sid, rec, net, aud = _station_context(params, STATION_PARAMS)
    except RequestError as err:
        resp, status = error_response(err, function, rid)
        return status, resp
    if function == "station":
        env = build_envelope(rec, net, aud, function, rid)
        env["s0d_status"] = aud["science_admission"]["status"]
        env["s0d"] = {"station": {
            "station_id": sid, "station_name": rec["station_name"],
            "dataset_id": dd.DATASET_ID, "dataset_version": dd.DATASET_VERSION,
            "crs": {"epsg": 4326, "axis_order_in_payload": ["latitude", "longitude"], "units": "degree",
                    "coordinates": rec["coordinates_lat_lon"],
                    "explain": "EPSG:4326 (WGS 84)；权威轴序 纬度,经度；本载荷同序；单位：度"},
            "basin": {"basin_id": rec["basin_id"], "basin_name": rec["basin_name"], "network_id": rec["graph_id"],
                      "catchment_area_km2": rec["catchment_area_km2"], "catchment_area_status": "CONDITIONAL (SYNTHETIC)"},
            "data_source": {"source": "demo_data.py 内置合成登记表", "data_class": DEMO_FLAG,
                            "real_data_used": False},
            "admission": {"status": aud["science_admission"]["status"],
                          "blocking_reasons": aud["science_admission"]["reasons"],
                          "metadata_display_status": aud["metadata_display"]["status"],
                          "evidence_level": "PROPOSED (SYNTHETIC)"},
        }}
    elif function == "network":
        env = build_envelope(rec, net, aud, function, rid)
        env["s0d_status"] = net["topology"]["status"]
        env["s0d"] = {"network": net}
    elif function == "audit":
        env = build_envelope(rec, net, aud, function, rid, science_stage="ADMISSION_REVIEW")
        env["s0d_status"] = aud["science_admission"]["status"]
        env["s0d"] = {"audit": aud}
    elif function == "demo":
        env = build_envelope(rec, net, aud, function, rid, science_stage="SYNTHETIC_DEMO_ONLY")
        env["s0d_status"] = DEMO_FLAG
        env["synthetic_display_data"] = synthetic_series(sid, s, e)
        env["s0d"] = {"demo": {"note": "合成演示数据只在 synthetic_display_data；prediction 仍为 null",
                               "requested_range": [s.isoformat(), e.isoformat()]}}
    else:
        err = RequestError("ROUTE_NOT_FOUND", "VHS-E011", "UNKNOWN_FUNCTION", "unknown function", 404)
        resp, status = error_response(err, function, rid)
        return status, resp
    ok, out = finalize(env, function, rid)
    return (200 if ok else 500), out


def handle_predict(body):
    """F4：任何预测请求一律 NOT_AUTHORIZED，prediction=null；请求字段不能改变授权。"""
    rid = request_id("predict", body if isinstance(body, dict) else repr(type(body)))
    try:
        if not isinstance(body, dict):
            raise RequestError("INVALID_REQUEST", "VHS-E011", "BODY_NOT_OBJECT", "request body must be a JSON object")
        sid = body.get("target_station_id", body.get("station_id"))
        check_station_id(sid)
        check_dataset(body.get("dataset_id"), body.get("dataset_version"))
        rec = get_station(sid)
    except RequestError as err:
        resp, status = error_response(err, "predict", rid, predict=True)
        return (403 if status == 200 else status), resp
    net = analyze_network(dd.GRAPHS[rec["graph_id"]], sid)
    aud = audit_station(rec, net)
    env = build_envelope(rec, net, aud, "predict", rid)
    shown, hidden = safe_field_names(body.keys())
    overrides = sorted(k for k in body if str(k).lower() in OVERRIDE_KEYS)
    checks = []
    if body.get("start") is not None or body.get("end") is not None:
        try:
            parse_time_range(body.get("start"), body.get("end"))
            checks.append("time_range: syntactically valid (still NOT_AUTHORIZED)")
        except RequestError as err:
            checks.append("time_range: " + err.reason_code)
    env["s0d_status"] = "NOT_AUTHORIZED"
    env["s0d"] = {"predict": {
        "decision": "NOT_AUTHORIZED",
        "prediction_field": "null（强制，S0D 出口闸门再次校验）",
        "reasons": ["S0D 阶段没有任何真实流量预测授权（prediction_authorized=NOT_AUTHORIZED）",
                    "目标 Q 封存或无授权；本模块不读取任何真实 Q，也不运行任何模型",
                    "没有冻结的预测协议与独立验证",
                    "请求中的 authorized / mode / model / force 等字段不能改变授权状态"],
        "override_attempts_ignored": [k for k in overrides if k in shown],
        "received_field_names": shown,
        "received_field_hidden_count": hidden,
        "request_checks": checks,
        "science_admission_status": aud["science_admission"]["status"],
        "hint": "纯合成展示请用 GET /api/vhs/synthetic-demo；结果在 synthetic_display_data，不在 prediction",
    }}
    ok, out = finalize(env, "predict", rid)
    return (403 if ok else 500), out


def offline_snapshot():
    """生成离线预览快照（全部由本程序计算，SYNTHETIC_DEMO_ONLY）。"""
    snap = {"data_class": DEMO_FLAG, "protocol_status": PROTOCOL_STATUS, "stage": STAGE,
            "stations": [{"station_id": s["station_id"], "station_name": s["station_name"], "role": s["role"]}
                         for s in dd.STATION_LIST],
            "default_range": list(dd.DEFAULT_DEMO_RANGE), "responses": {}}
    a, b = dd.DEFAULT_DEMO_RANGE
    for s in dd.STATION_LIST:
        sid = s["station_id"]
        for fn in ("station", "network", "audit"):
            snap["responses"]["%s|%s" % (fn, sid)] = handle(fn, {"station_id": sid})
        snap["responses"]["demo|%s" % sid] = handle("demo", {"station_id": sid, "start": a, "end": b})
        snap["responses"]["predict|%s" % sid] = handle_predict({"target_station_id": sid})
    for fn in ("station", "network", "audit"):
        snap["responses"]["%s|DEMO_NOT_EXIST" % fn] = handle(fn, {"station_id": "DEMO_NOT_EXIST"})
    snap["responses"]["demo|DEMO_NOT_EXIST"] = handle("demo", {"station_id": "DEMO_NOT_EXIST", "start": a, "end": b})
    snap["responses"]["predict|DEMO_NOT_EXIST"] = handle_predict({"target_station_id": "DEMO_NOT_EXIST"})
    return snap
