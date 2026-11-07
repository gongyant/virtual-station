"""
vhs_core.py  --  VHS v0.3 data layer
=====================================================================

Read-only access to the AUTHORIZED sandbox metadata. No network, no Q, no
GIS geometry, standard library only.

Design rules
------------
1. Station-level grouping comes ONLY from group_membership.csv.
2. Gauge_hierarchy.NEXTUPID = 0 is a sentinel, not a station id.
3. lon/lat are EPSG:3035 PROJECTED METRES, not degrees.
4. Every derived value carries an explicit evidence grade.
5. Nothing here can produce a prediction.
"""

import csv
import hashlib
import json
import os
import time
from collections import Counter, defaultdict, deque

try:
    from gis_adapter import GISAdapter
except Exception:                                    # pragma: no cover
    GISAdapter = None

APP_VERSION = "0.6.0"
BUILD_ID = "v0.6.0-20261024-four-layer"
DATASET_VERSION = "VHS-NEXT-B1A"

OBSERVED = "OBSERVED"
DERIVED = "DERIVED"
TENTATIVE = "TENTATIVE"
UNKNOWN = "UNKNOWN"
NOT_RUN = "NOT_RUN"

SNAP_LIMIT_M = 500.0

# Status label translations (Chinese + English code)
STATUS_LABELS = {
    "GRAPH_TENTATIVE":       ("图级暂定关系", "GRAPH_TENTATIVE"),
    "ISOLATED_OR_UNMAPPED":  ("孤立或未映射", "ISOLATED_OR_UNMAPPED"),
    "HAS_CANDIDATES":        ("有图级W候选", "HAS_CANDIDATES"),
    "NOT_IN_GRAPH":          ("不在观测图中（无有向边）", "NOT_IN_GRAPH"),
    "NOT_EVALUATED":         ("未评估为目标站", "NOT_EVALUATED"),
    "NO_GRAPH_CANDIDATE":    ("已评估·无图级W候选", "NO_GRAPH_CANDIDATE"),
    "PASS":                  ("通过", "PASS"),
    "FAIL":                  ("未通过", "FAIL"),
    "UNKNOWN":               ("未知", "UNKNOWN"),
    "NOT_RUN":               ("未执行", "NOT_RUN"),
    "BLOCKED":               ("受阻", "BLOCKED"),
    "CONDITIONAL":           ("有条件通过", "CONDITIONAL"),
    "MISSING":               ("缺失", "MISSING"),
    "WARN":                  ("警告", "WARN"),
    "NOT_APPLICABLE":        ("不适用", "NOT_APPLICABLE"),
    "NOT_AUTHORIZED":        ("未授权", "NOT_AUTHORIZED"),
}


def _as_bool(v):
    return str(v).strip().lower() == "true"


def _fnum(v):
    v = (v or "").strip()
    if v in ("", "-", "NA", "NULL", "None"):
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _safe_year(v):
    """Parse a year field; treat 0 and empty as None (sentinel)."""
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "0", "-", "NA", "NULL", "None"):
        return None
    try:
        yr = int(float(s))
        return yr if yr > 0 else None
    except (ValueError, TypeError):
        return None


def _sha256_prefix(path, n=16):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


class VHSStore:
    """In-memory index of the authorized metadata."""

    def __init__(self, sandbox_root):
        self.root = sandbox_root
        self.paths = {
            "gauges": os.path.join(
                sandbox_root, "input", "c1", "batch2a", "open_metadata",
                "D_gauges", "1_attributes", "Gauge_attributes.csv"),
            "hierarchy": os.path.join(
                sandbox_root, "input", "c1", "batch2a", "open_metadata",
                "B_basins_intermediate_all", "1_attributes",
                "Gauge_hierarchy.csv"),
            "groups": os.path.join(sandbox_root, "input", "c1", "batch2a",
                                   "group_membership.csv"),
            "snap": os.path.join(sandbox_root, "input", "c1", "batch2a",
                                 "evidence", "station_reach_distances.csv"),
            "topology": os.path.join(sandbox_root, "input", "c1", "batch2a",
                                     "evidence", "topology_summary.json"),
            "pairs": os.path.join(sandbox_root, "input",
                                  "connected_candidates.csv"),
            "triplets": os.path.join(sandbox_root, "output",
                                     "03_candidate_triplets.csv"),
        }
        self.stations = {}
        self.out_edges = defaultdict(set)
        self.in_edges = defaultdict(set)
        self.hierarchy = {}
        self.pair_rows = []
        self.cand_by_target = defaultdict(list)
        self.cand_by_w = defaultdict(list)
        self.junction_pairs = Counter()
        self.topo_summary = {}
        self._cand_seen = set()
        self.loaded_at = None
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.manifest_sha = ""
        self.gis = GISAdapter(sandbox_root) if GISAdapter else None
        self.pilot_pairs = []
        self._load()
        self._load_pilot()

    def _load(self):
        t0 = time.time()

        # compute manifest hash
        manifest_path = os.path.join(
            self.root, "input", "c1", "manifest", "integrity_manifest.json")
        if os.path.isfile(manifest_path):
            self.manifest_sha = _sha256_prefix(manifest_path)
        else:
            self.manifest_sha = "not_available"

        # 1) gauge attributes
        with open(self.paths["gauges"], encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                sid = int(r["ID"])
                self.stations[sid] = {
                    "id": sid,
                    "govnr": (r["govnr"] or "").strip(),
                    "name": (r["name"] or "").strip(),
                    "river": (r["river"] or "").strip(),
                    "area_gov_km2": _fnum(r["area_gov"]),
                    "elev_m": _fnum(r["elev"]),
                    "x_epsg3035": _fnum(r["lon"]),
                    "y_epsg3035": _fnum(r["lat"]),
                    "country": (r["country"] or "").strip(),
                    "fedstate": (r["fedstate"] or "").strip(),
                    "region": (r["region"] or "").strip(),
                    "obsbeg_day": (r["obsbeg_day"] or "").strip() or None,
                    "obsbeg_hr": (r["obsbeg_hr"] or "").strip() or None,
                    "obsend_day": _safe_year(r.get("obsend_day") or r.get("obsend")),
                    "obsend_hr": _safe_year(r.get("obsend_hr")),
                    "gaps_pre": _fnum(r["gaps_pre"]),
                    "gaps_post": _fnum(r["gaps_post"]),
                    "area_ratio": _fnum(r["area_ratio"]),
                    "nrs_euhyd": (r["nrs_euhyd"] or "").strip(),
                    "nrs_rivat": (r["nrs_rivat"] or "").strip(),
                    "typimpact": (r["typimpact"] or "").strip(),
                    "diur_art": (r["diur_art"] or "").strip(),
                    "diur_glac": (r["diur_glac"] or "").strip(),
                    "degimpact": (r["degimpact"] or "").strip(),
                }

        # 2) hierarchy -> directed edges
        with open(self.paths["hierarchy"], encoding="utf-8-sig",
                  newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                sid = int(r["ID"])
                ups = [int(x) for x in (r["NEXTUPID"] or "").split(",")
                       if x.strip() and int(x) != 0]
                self.hierarchy[sid] = {
                    "level": int(r["HIERARCHY"] or 0),
                    "nextup": ups,
                    "nextdown": int(r["NEXTDOWNID"] or 0),
                }
                for u in ups:
                    self.out_edges[u].add(sid)
                    self.in_edges[sid].add(u)

        # 3) group membership
        with open(self.paths["groups"], encoding="utf-8-sig",
                  newline="") as f:
            for r in csv.DictReader(f):
                sid = int(r["ID"])
                st = self.stations.setdefault(sid, {"id": sid})
                st["component_id"] = (r["gauge_graph_component"] or "").strip()
                st["natural_root"] = (r["natural_MAIN_RIV"] or "").strip()
                st["operational_group"] = (r["operational_transfer_group"]
                                           or "").strip()
                st["region_is_independence_unit"] = _as_bool(
                    r["region_is_independence_unit"])
                st["group_certification"] = (r["group_certification"]
                                             or "").strip()

        # 4) snapping diagnostics
        with open(self.paths["snap"], encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                sid = int(r["ID"])
                st = self.stations.setdefault(sid, {"id": sid})
                st["snap_distance_m"] = _fnum(r["distance_m"])
                st["snap_status"] = (r["status"] or "").strip()
                st["snap_competing_reviewed"] = _as_bool(
                    r["competing_candidates_reviewed"])

        # 5) pair table
        with open(self.paths["pairs"], encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                self.pair_rows.append(r)
        # evaluated target pool = stations that appear as target_id in the
        # authorized pair table (417 of 882).
        self.target_pool = set(int(r["target_id"]) for r in self.pair_rows)

        # Qualified tentative target pool = target stations whose pair carries
        # provisional_primary_eligible = True (92 of 882, from 141 pairs).
        # This is the authoritative definition used by P0 (87 with W + 5
        # without W: 429, 432, 456, 463, 609). Historical P0 counts are NOT
        # modified here; this only classifies the query layer.
        self.tentative_target_pool = set()
        for r in self.pair_rows:
            if str(r.get("provisional_primary_eligible", "")).strip().lower() \
                    == "true":
                self.tentative_target_pool.add(int(r["target_id"]))

        # 6) topology summary
        with open(self.paths["topology"], encoding="utf-8") as f:
            self.topo_summary = json.load(f)

        # 7) triplet candidates
        with open(self.paths["triplets"], encoding="utf-8-sig",
                  newline="") as f:
            for r in csv.DictReader(f):
                T = int(r["target_id"])
                W = int(r["parallel_candidate_id"])
                J = int(r["w_confluence_node"])
                key = (T, W)
                if key not in self._cand_seen:
                    self._cand_seen.add(key)
                    item = {"w": W, "confluence": J,
                            "n_upstream_donors": 0,
                            "certification": r["triplet_certification"]}
                    self.cand_by_target[T].append(item)
                    self.cand_by_w[W].append(T)
                    self.junction_pairs[J] += 1
                else:
                    for item in self.cand_by_target[T]:
                        if item["w"] == W:
                            item["n_upstream_donors"] += 1
                            break

        # 8) derived
        self.components = self._weak_components()
        self.comp_of = {}
        for i, comp in enumerate(self.components):
            for n in comp:
                self.comp_of[n] = i

        pair_nodes = set()
        for r in self.pair_rows:
            pair_nodes.add(int(r["donor_id"]))
            pair_nodes.add(int(r["target_id"]))
        basin_nodes = set(self.hierarchy)
        self.comp_in_graph = self._components_on(pair_nodes)
        self.comp_basin = self._components_on(basin_nodes)
        self._finalize_station_flags()

        # unique regions for filter
        self.all_regions = sorted({st.get("region", "") for st in
                                   self.stations.values() if st.get("region")})

        self.loaded_at = {
            "seconds": round(time.time() - t0, 3),
            "stations": len(self.stations),
            "edges": sum(len(v) for v in self.out_edges.values()),
            "components": len(self.components),
            "targets_with_candidates": len(self.cand_by_target),
            "candidate_pairs": sum(len(v) for v in
                                   self.cand_by_target.values()),
        }

    def _load_pilot(self):
        """Load the frozen C1-S2B 20-pair pilot selection (read-only reuse)."""
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "pilot", "pilot_pairs.csv")
        if not os.path.isfile(p):
            return
        with open(p, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                self.pilot_pairs.append({
                    "stratum": r["stratum"],
                    "target_id": int(r["target_id"]),
                    "w_id": int(r["w_id"]),
                    "confluence_node": int(r["confluence_node"]),
                    "junction_pair_count": int(r["junction_pair_count"]),
                    "hops_T_to_confluence": int(r["hops_T_to_confluence"]),
                    "w_snap_distance_m": _fnum(r["w_snap_distance_m"]),
                    "w_nrs_rivat": r["w_nrs_rivat"] or None,
                    "w_natural_root": r["w_natural_root"] or None,
                    "in_p0_output": _as_bool(r["in_p0_output"]),
                    "note": r.get("note", ""),
                })

    # -- graph helpers --
    def _weak_components(self):
        seen, comps = set(), []
        for n in self.stations:
            if n in seen:
                continue
            comp, q = {n}, deque([n])
            seen.add(n)
            while q:
                x = q.popleft()
                for y in list(self.out_edges[x]) + list(self.in_edges[x]):
                    if y not in seen:
                        seen.add(y)
                        comp.add(y)
                        q.append(y)
            comps.append(comp)
        return comps

    def _components_on(self, node_set):
        seen, comps = set(), 0
        for n in node_set:
            if n in seen:
                continue
            comps += 1
            seen.add(n)
            q = deque([n])
            while q:
                x = q.popleft()
                for y in list(self.out_edges[x]) + list(self.in_edges[x]):
                    if y in node_set and y not in seen:
                        seen.add(y)
                        q.append(y)
        return comps

    def ancestors_with_depth(self, sid):
        depth = {}
        q = deque([(sid, 0)])
        while q:
            x, d = q.popleft()
            for p in self.in_edges[x]:
                if p not in depth:
                    depth[p] = d + 1
                    q.append((p, d + 1))
        return depth

    def descendants_with_depth(self, sid):
        depth = {}
        q = deque([(sid, 0)])
        while q:
            x, d = q.popleft()
            for s in self.out_edges[x]:
                if s not in depth:
                    depth[s] = d + 1
                    q.append((s, d + 1))
        return depth

    def path_to(self, a, b):
        if a == b:
            return [a]
        prev, q = {a: None}, deque([a])
        while q:
            x = q.popleft()
            for y in self.out_edges[x]:
                if y in prev:
                    continue
                prev[y] = x
                if y == b:
                    path = [b]
                    while prev[path[-1]] is not None:
                        path.append(prev[path[-1]])
                    return list(reversed(path))
                q.append(y)
        return None

    # -- candidate status --
    def _candidate_status(self, sid):
        """Four distinct states (never conflated):

        HAS_CANDIDATES      : a qualified tentative target WITH W candidates
                              (87 stations; all relations GRAPH_TENTATIVE)
        NO_GRAPH_CANDIDATE  : a qualified tentative target with NO W candidate
                              (5 stations: 429, 432, 456, 463, 609)
        NOT_EVALUATED       : in graph, but not a qualified tentative target
                              (not in the 92-station pool)
        NOT_IN_GRAPH        : no directed edge at all

        The qualified tentative target pool is defined by
        provisional_primary_eligible == True (92 stations). Ordinary stations
        that merely appear as a target_id in the raw pair table are NOT
        reported as NO_GRAPH_CANDIDATE.
        """
        n = len(self.cand_by_target.get(sid, []))
        if n > 0:
            return n, "HAS_CANDIDATES"
        st = self.stations.get(sid, {})
        if not st.get("in_graph"):
            return 0, "NOT_IN_GRAPH"
        if sid in self.tentative_target_pool:
            return 0, "NO_GRAPH_CANDIDATE"
        return 0, "NOT_EVALUATED"

    # -- station flags --
    def _finalize_station_flags(self):
        pair_nodes = set()
        for r in self.pair_rows:
            pair_nodes.add(int(r["donor_id"]))
            pair_nodes.add(int(r["target_id"]))

        euhyd_use = Counter()
        for st in self.stations.values():
            if st.get("nrs_euhyd"):
                euhyd_use[st["nrs_euhyd"]] += 1

        w_targets = Counter()
        for W, ts in self.cand_by_w.items():
            w_targets[W] = len(ts)
        conf_use = Counter()
        for T, lst in self.cand_by_target.items():
            for it in lst:
                conf_use[it["confluence"]] += 1

        incident = defaultdict(set)
        for r in self.pair_rows:
            if r["RiverATLAS_path"] != "PASS":
                incident[int(r["donor_id"])].add(r["RiverATLAS_path"])
                incident[int(r["target_id"])].add(r["RiverATLAS_path"])

        for sid, st in self.stations.items():
            st["in_graph"] = sid in pair_nodes
            st["in_degree"] = len(self.in_edges[sid])
            st["out_degree"] = len(self.out_edges[sid])
            st["component_id_from_graph"] = self.comp_of.get(sid)
            st["component_size"] = (len(self.components[
                self.comp_of[sid]]) if sid in self.comp_of else 0)
            st["n_upstream"] = len(self.ancestors_with_depth(sid))
            st["n_downstream"] = len(self.descendants_with_depth(sid))
            st["as_parallel_candidate_for"] = w_targets.get(sid, 0)
            st["as_confluence_for_pairs"] = conf_use.get(sid, 0)
            st["euhyd_reach_shared_with"] = (euhyd_use[st.get("nrs_euhyd")]
                                             - 1) if st.get("nrs_euhyd") else 0
            st["incident_nonPASS_edges"] = sorted(incident.get(sid, ()))
            st["audit_flags"] = self._flags(st)
            st["audit_state"] = self._state(st)

    def _flags(self, st):
        f = []
        if not st["in_graph"]:
            f.append("NOT_IN_OBSERVED_GRAPH")
        if st["component_size"] == 1:
            f.append("ISOLATED_SINGLETON")
        d = st.get("snap_distance_m")
        if d is None:
            f.append("SNAP_DISTANCE_NOT_TESTABLE")
        elif d > SNAP_LIMIT_M:
            f.append("SNAP_OVER_500M")
        if not st.get("nrs_rivat"):
            f.append("REACH_KEY_RIVAT_MISSING")
        if not st.get("nrs_euhyd"):
            f.append("REACH_KEY_EUHYD_MISSING")
        if st.get("euhyd_reach_shared_with", 0) > 0:
            f.append("EUHYD_REACH_SHARED")
        if not st.get("natural_root"):
            f.append("GROUP_NATURAL_UNKNOWN")
        if not st.get("operational_group"):
            f.append("GROUP_OPERATIONAL_UNKNOWN")
        if st.get("incident_nonPASS_edges"):
            f.append("INCIDENT_EDGE_NOT_VERIFIED")
        return f

    def _state(self, st):
        if not st["in_graph"]:
            return "ISOLATED_OR_UNMAPPED"
        return "GRAPH_TENTATIVE"

    # -- public API --
    def health(self):
        gis_mode = "STAGE_A_NO_GIS"
        if self.gis:
            gis_mode = self.gis.status()["data_mode"]
        return {
            "status": "ok",
            "app_version": APP_VERSION,
            "build_id": BUILD_ID,
            "dataset_version": DATASET_VERSION,
            "dataset_manifest_sha256": self.manifest_sha,
            "server_started_at": self.started_at,
            "data_mode": "STATIC_METADATA_ONLY",
            "gis_mode": gis_mode,
            "loaded": self.loaded_at,
        }

    def gis_status(self):
        if not self.gis:
            return {"data_mode": "ADAPTER_MISSING", "geometry_checks": "UNKNOWN"}
        st = self.gis.status()
        st["pilot_pairs"] = len(self.pilot_pairs)
        return st

    def gis_layers(self):
        return {"layers": self.gis.layers_public() if self.gis else []}

    def pilot(self):
        """20-pair pilot replay (geometry verdict = UNKNOWN until Stage B)."""
        out = []
        for pp in self.pilot_pairs:
            ws = self.stations.get(pp["w_id"], {})
            ts = self.stations.get(pp["target_id"], {})
            out.append({
                **pp,
                "w_name": ws.get("name"),
                "w_area_gov_km2": ws.get("area_gov_km2"),
                "t_name": ts.get("name"),
                "t_river": ts.get("river"),
                # geometry verdicts are UNKNOWN until GIS layers are staged
                "reach_path": "UNKNOWN",
                "first_confluence": "UNKNOWN",
                "catchment_relation": "UNKNOWN",
                "snapping_review": "UNKNOWN",
                "verdict": "UNKNOWN",
                "reason": "GIS layers not staged (Stage B pending authorization)",
                "rules_version": (self.gis.rules_version if self.gis
                                  else "n/a"),
            })
        return {"n": len(out), "pairs": out,
                "note": "No geometry verdict is produced in Stage A. "
                        "Every row is UNKNOWN by construction, not by "
                        "computation."}

    def meta(self):
        return {
            "service": "VHS v0.6 four-layer research platform",
            "app_version": APP_VERSION,
            "build_id": BUILD_ID,
            "sandbox_root": self.root,
            "loaded": self.loaded_at,
            "counts": {
                "stations_total": len(self.stations),
                "stations_in_graph": sum(1 for s in self.stations.values()
                                         if s["in_graph"]),
                "directed_edges": sum(len(v) for v in
                                      self.out_edges.values()),
                "weak_components_all_882_nodes": len(self.components),
                "weak_components_in_graph_850": self.comp_in_graph,
                "weak_components_basin_stations_859": self.comp_basin,
                "targets_with_candidates": len(self.cand_by_target),
                "qualified_tentative_targets": len(self.tentative_target_pool),
                "raw_pair_target_pool": len(self.target_pool),
                "stations_not_evaluated": sum(
                    1 for s in self.stations.values()
                    if s["in_graph"] and
                    s["id"] not in self.tentative_target_pool),
                "stations_no_graph_candidate": sum(
                    1 for sid in self.tentative_target_pool
                    if sid not in self.cand_by_target),
                "candidate_pairs": sum(len(v) for v in
                                       self.cand_by_target.values()),
                "stations_snap_over_500m": sum(
                    1 for s in self.stations.values()
                    if (s.get("snap_distance_m") or 0) > SNAP_LIMIT_M),
                "stations_snap_not_testable": sum(
                    1 for s in self.stations.values()
                    if s.get("snap_distance_m") is None),
            },
            "regions": self.all_regions,
            "authorization": {
                "MULTISYSTEM_BENCHMARK": "NO_GO",
                "MODEL_EXECUTION": "NOT_AUTHORIZED",
                "GEOMETRY_VERIFIED": 0,
                "CONTROL_CERTIFIED": 0,
                "FULLY_ADMITTED": 0,
                "GIS_GEOMETRY": "NOT_RUN",
            },
            "coordinate_reference": {
                "epsg": 3035,
                "unit": "metre",
                "note": "lon/lat columns are EPSG:3035 projected metres; "
                        "exposed as x/y.",
            },
            "data_version": {
                "stage": DATASET_VERSION,
                "manifest_sha256_prefix": self.manifest_sha,
            },
            "gis": self.gis_status(),
            "pilot_pairs": len(self.pilot_pairs),
        }

    def station_public(self, sid):
        st = self.stations.get(sid)
        if st is None:
            return None
        keep = ("id", "govnr", "name", "river", "country", "fedstate",
                "region", "area_gov_km2", "elev_m", "x_epsg3035",
                "y_epsg3035", "obsbeg_day", "obsend_day", "gaps_pre",
                "gaps_post", "area_ratio", "nrs_euhyd", "nrs_rivat",
                "typimpact", "diur_art", "diur_glac", "degimpact",
                "snap_distance_m", "snap_status", "snap_competing_reviewed",
                "natural_root", "operational_group", "component_id",
                "component_size", "group_certification",
                "region_is_independence_unit", "in_graph", "in_degree",
                "out_degree", "n_upstream", "n_downstream",
                "as_parallel_candidate_for", "as_confluence_for_pairs",
                "euhyd_reach_shared_with", "incident_nonPASS_edges",
                "audit_flags", "audit_state")
        out = {k: st.get(k) for k in keep}
        n_cand, cand_status = self._candidate_status(sid)
        out["n_candidates"] = n_cand
        out["candidate_status"] = cand_status
        out["evidence"] = {
            "identity": OBSERVED,
            "coordinates": "OBSERVED (EPSG:3035 metres, not independently "
                           "re-surveyed)",
            "graph_relations": TENTATIVE,
            "grouping": OBSERVED,
            "snapping": ("OBSERVED (distance only, not adjudicated)"
                         if st.get("snap_distance_m") is not None
                         else UNKNOWN),
            "geometry": NOT_RUN,
            "control": "NOT_ASSESSED",
            "license": "BLOCKED_CLAUSE_COMPARISON_NOT_PERFORMED",
        }
        return out

    def network(self, sid, depth=4):
        if sid not in self.stations:
            return None
        up = self.ancestors_with_depth(sid)
        down = self.descendants_with_depth(sid)
        up_lim = {k: v for k, v in up.items() if v <= depth}
        down_lim = {k: v for k, v in down.items() if v <= depth}
        comp = self.comp_of.get(sid)
        return {
            "station": sid,
            "component_index": comp,
            "component_size": (len(self.components[comp])
                               if comp is not None else 0),
            "upstream_count": len(up),
            "downstream_count": len(down),
            "upstream_within_depth": len(up_lim),
            "downstream_within_depth": len(down_lim),
            "immediate_upstream": sorted(self.in_edges[sid]),
            "immediate_downstream": sorted(self.out_edges[sid]),
            "hierarchy": self.hierarchy.get(sid),
            "upstream": [{"id": k, "hops": v,
                          "name": self.stations.get(k, {}).get("name"),
                          "river": self.stations.get(k, {}).get("river"),
                          "x": self.stations.get(k, {}).get("x_epsg3035"),
                          "y": self.stations.get(k, {}).get("y_epsg3035")}
                         for k, v in sorted(up_lim.items(),
                                            key=lambda kv: (kv[1], kv[0]))],
            "downstream": [{"id": k, "hops": v,
                            "name": self.stations.get(k, {}).get("name"),
                            "river": self.stations.get(k, {}).get("river"),
                            "x": self.stations.get(k, {}).get("x_epsg3035"),
                            "y": self.stations.get(k, {}).get("y_epsg3035")}
                           for k, v in sorted(down_lim.items(),
                                              key=lambda kv: (kv[1], kv[0]))],
            "edge_evidence": self._edge_evidence(sid),
            "evidence_grade": TENTATIVE,
            "note": "Observed gauge-to-gauge topology only (GRAPH_TENTATIVE). "
                    "Absence of a path is NOT proof of disconnection; the "
                    "river-reach graph has not been checked.",
        }

    def _edge_evidence(self, sid):
        out = []
        for r in self.pair_rows:
            d, t = int(r["donor_id"]), int(r["target_id"])
            if d == sid or t == sid:
                out.append({
                    "donor": d, "target": t, "hops": int(r["hops"]),
                    "path": r["directed_path"],
                    "riveratlas": r["RiverATLAS_path"],
                    "snap_both_le500m": _as_bool(
                        r["both_endpoint_snap_le500m"]),
                    "note": "RiverATLAS PASS = station-relation path "
                            "evidence, NOT physical certification",
                })
        return out

    def audit(self, sid):
        st = self.stations.get(sid)
        if st is None:
            return None
        checks = []

        def add(check, status, detail, grade=OBSERVED, zh=None):
            label = STATUS_LABELS.get(status, ("", status))
            checks.append({"check": check, "status": status,
                           "status_zh": label[0],
                           "detail": detail, "evidence": grade,
                           "zh": zh or ""})

        add("identity", "PASS",
            "station id present in Gauge_attributes.csv",
            zh="站点 ID 存在于已授权元数据")
        add("coordinates",
            "PASS" if st.get("x_epsg3035") is not None else "UNKNOWN",
            "EPSG:3035 metres; not independently re-surveyed",
            zh="坐标为 EPSG:3035 投影米，未独立复核")
        add("graph_membership",
            "PASS" if st["in_graph"] else "NOT_APPLICABLE",
            ("in observed gauge graph, component size %d"
             % st["component_size"]) if st["in_graph"]
            else "no directed edge in the 834-edge table",
            zh="图成员状态（站级观测拓扑，非物理认证）")
        add("snapping",
            "FAIL" if (st.get("snap_distance_m") is None
                       or st["snap_distance_m"] > SNAP_LIMIT_M) else "PASS",
            ("distance_m = %.2f (status %s)"
             % (st["snap_distance_m"], st.get("snap_status")))
            if st.get("snap_distance_m") is not None
            else "distance_m missing (status %s)" % st.get("snap_status"),
            zh="站点到河段的几何吸附距离")
        add("reach_key_euhyd",
            "PASS" if st.get("nrs_euhyd") else "MISSING",
            st.get("nrs_euhyd") or "empty",
            OBSERVED if st.get("nrs_euhyd") else UNKNOWN,
            zh="EU-Hydro 河段编号")
        add("reach_key_rivat",
            "PASS" if st.get("nrs_rivat") else "MISSING",
            st.get("nrs_rivat") or "empty",
            OBSERVED if st.get("nrs_rivat") else UNKNOWN,
            zh="RiverATLAS 河段编号")
        add("reach_key_shared",
            "WARN" if st.get("euhyd_reach_shared_with") else "PASS",
            ("shares EU-Hydro reach with %d other station(s)"
             % st["euhyd_reach_shared_with"])
            if st.get("euhyd_reach_shared_with") else "unique within dataset",
            zh="EU-Hydro 河段是否被多站共享")
        add("group_natural",
            "PASS" if st.get("natural_root") else "UNKNOWN",
            st.get("natural_root") or "natural_MAIN_RIV empty",
            OBSERVED if st.get("natural_root") else UNKNOWN,
            zh="自然水系归属")
        add("group_operational",
            "PASS" if st.get("operational_group") else "UNKNOWN",
            st.get("operational_group") or "operational_transfer_group empty",
            OBSERVED if st.get("operational_group") else UNKNOWN,
            zh="运营依赖组归属")
        add("group_certification", "CONDITIONAL",
            st.get("group_certification") or "n/a",
            zh="分组认证状态")
        add("geometry_g1_mapping", NOT_RUN,
            "needs RiverATLAS + Gauge geometry (not authorized yet)", NOT_RUN,
            zh="G1 几何映射（需 GIS 数据，未授权）")
        add("geometry_g3_downstream", NOT_RUN,
            "needs RiverATLAS NEXT_DOWN chain", NOT_RUN,
            zh="G3 下游链验证（需 GIS 数据）")
        add("geometry_g4_basin_overlap", NOT_RUN,
            "needs Basins_A polygons", NOT_RUN,
            zh="G4 流域重叠验证（需 GIS 数据）")
        add("geometry_g4b_intermediate", NOT_RUN,
            "needs Basins_B polygons (diagnostic only)", NOT_RUN,
            zh="G4b 中间流域诊断（需 GIS 数据）")
        add("control_transfer", "UNKNOWN",
            "impact codes present (%s) but code semantics are undefined"
            % (st.get("typimpact") or "-"),
            UNKNOWN, zh="调水影响评估（语义未定义）")
        add("license", "BLOCKED",
            "clause-level comparison not performed", UNKNOWN,
            zh="许可条款比对（未执行）")
        add("prediction", "NOT_AUTHORIZED",
            "model execution not authorized; prediction = null",
            zh="流量预测（未授权，prediction=null）")

        return {
            "station": sid,
            "audit_state": st["audit_state"],
            "audit_state_zh": STATUS_LABELS.get(
                st["audit_state"], ("", ""))[0],
            "flags": st["audit_flags"],
            "checks": checks,
            "counts": {
                "pass": sum(1 for c in checks if c["status"] == "PASS"),
                "fail": sum(1 for c in checks if c["status"] == "FAIL"),
                "unknown": sum(1 for c in checks
                               if c["status"] == "UNKNOWN"),
                "not_run": sum(1 for c in checks
                               if c["status"] == NOT_RUN)},
            "summary_note": "PASS counts reflect individual check items "
                            "only and do NOT imply scientific certification. "
                            "GEOMETRY_VERIFIED=0, CONTROL_CERTIFIED=0, "
                            "FULLY_ADMITTED=0.",
            "summary_note_zh": "PASS 计数仅为单项检查结果，不代表科学认证通过。"
                               "几何验证=0，控制认证=0，完全准入=0。",
            "authorization": {
                "GEOMETRY_VERIFIED": 0,
                "CONTROL_CERTIFIED": 0,
                "FULLY_ADMITTED": 0,
                "MODEL_EXECUTION": "NOT_AUTHORIZED"},
        }

    def candidates(self, sid):
        if sid not in self.stations:
            return None
        lst = sorted(self.cand_by_target.get(sid, []),
                     key=lambda x: (x["confluence"], x["w"]))
        out = []
        for it in lst:
            W = it["w"]
            ws = self.stations.get(W, {})
            path = self.path_to(sid, it["confluence"])
            out.append({
                "w": W,
                "w_name": ws.get("name"),
                "w_river": ws.get("river"),
                "w_area_gov_km2": ws.get("area_gov_km2"),
                "w_region": ws.get("region"),
                "confluence_node": it["confluence"],
                "confluence_pairs_in_pool": self.junction_pairs[
                    it["confluence"]],
                "hops_target_to_confluence": (len(path) - 1) if path else None,
                "w_snap_distance_m": ws.get("snap_distance_m"),
                "w_snap_status": ws.get("snap_status"),
                "w_nrs_rivat": ws.get("nrs_rivat") or None,
                "w_natural_root": ws.get("natural_root") or None,
                "w_operational_group": ws.get("operational_group") or None,
                "w_x": ws.get("x_epsg3035"),
                "w_y": ws.get("y_epsg3035"),
                "n_upstream_donors": it["n_upstream_donors"],
                "certification": it["certification"],
                "evidence": TENTATIVE,
            })
        _, cand_status = self._candidate_status(sid)
        return {
            "station": sid,
            "n_candidates": len(out),
            "candidate_status": cand_status,
            "candidate_status_zh": STATUS_LABELS.get(
                cand_status, ("", ""))[0],
            "distinct_confluence_nodes": len({o["confluence_node"]
                                              for o in out}),
            "candidates": out,
            "note": "Graph-level parallel candidates only (GRAPH_TENTATIVE). "
                    "'confluence_node' is an observed gauge LCA, NOT a "
                    "verified river-reach junction.",
        }

    def served_targets(self, sid):
        ts = sorted(self.cand_by_w.get(sid, []))
        return {"station": sid, "n_targets": len(ts), "targets": ts}

    def utw_linkage(self, target_id, w_id=None):
        """U-T-W linkage for a target station."""
        if target_id not in self.stations:
            return None
        st = self.stations[target_id]
        # All upstream (U) stations
        up = self.ancestors_with_depth(target_id)
        immediate_u = sorted(self.in_edges[target_id])
        u_list = []
        for uid, hops in sorted(up.items(), key=lambda kv: (kv[1], kv[0])):
            us = self.stations.get(uid, {})
            u_list.append({
                "id": uid, "hops": hops,
                "name": us.get("name"), "river": us.get("river"),
                "area_gov_km2": us.get("area_gov_km2"),
                "snap_distance_m": us.get("snap_distance_m"),
                "natural_root": us.get("natural_root") or None,
                "operational_group": us.get("operational_group") or None,
                "x": us.get("x_epsg3035"), "y": us.get("y_epsg3035"),
                "is_direct": uid in immediate_u,
            })

        # W candidates
        _, cand_status = self._candidate_status(target_id)
        w_list = self.candidates(target_id)

        # Selected W detail
        w_detail = None
        if w_id is not None and w_id in self.stations:
            ws = self.stations[w_id]
            # find common downstream observation nodes
            t_desc = set(self.descendants_with_depth(target_id))
            w_desc = set(self.descendants_with_depth(w_id))
            common = sorted(t_desc & w_desc)
            path_t_to_w = self.path_to(target_id, w_id)
            path_w_to_t = self.path_to(w_id, target_id)
            w_detail = {
                "w_id": w_id,
                "w_name": ws.get("name"),
                "w_river": ws.get("river"),
                "w_area_gov_km2": ws.get("area_gov_km2"),
                "w_snap_distance_m": ws.get("snap_distance_m"),
                "w_snap_status": ws.get("snap_status"),
                "w_natural_root": ws.get("natural_root") or None,
                "w_operational_group": ws.get("operational_group") or None,
                "w_nrs_rivat": ws.get("nrs_rivat") or None,
                "w_x": ws.get("x_epsg3035"),
                "w_y": ws.get("y_epsg3035"),
                "path_t_to_w": path_t_to_w,
                "path_w_to_t": path_w_to_t,
                "common_downstream_nodes": common[:20],
                "evidence": TENTATIVE,
            }

        return {
            "target": target_id,
            "target_name": st.get("name"),
            "target_river": st.get("river"),
            "target_audit_state": st.get("audit_state"),
            "candidate_status": cand_status,
            "candidate_status_zh": STATUS_LABELS.get(
                cand_status, ("", ""))[0],
            "upstream_stations": u_list,
            "n_upstream": len(u_list),
            "n_w_candidates": w_list["n_candidates"] if w_list else 0,
            "w_candidates_summary": {
                "n": w_list["n_candidates"] if w_list else 0,
                "distinct_confluences": (w_list["distinct_confluence_nodes"]
                                         if w_list else 0),
            },
            "selected_w": w_detail,
            "evidence_grade": TENTATIVE,
            "note": "All relationships are GRAPH_TENTATIVE. This is "
                    "station-level observed topology, not physical "
                    "certification.",
        }

    def search(self, q, limit=25, region=None, targets_only=False):
        q = (q or "").strip().lower()
        hits = []
        for st in self.stations.values():
            if region and st.get("region") != region:
                continue
            if targets_only and st["id"] not in self.cand_by_target:
                continue
            if q:
                hay = " ".join(str(st.get(k) or "") for k in
                               ("id", "govnr", "name", "river", "region",
                                "country", "nrs_euhyd", "nrs_rivat")).lower()
                if q not in hay:
                    continue
            hits.append(st)
        hits.sort(key=lambda s: s["id"])
        results = []
        for s in hits[:limit]:
            n_cand, cand_status = self._candidate_status(s["id"])
            results.append({
                "id": s["id"], "name": s.get("name"),
                "river": s.get("river"), "region": s.get("region"),
                "area_gov_km2": s.get("area_gov_km2"),
                "audit_state": s.get("audit_state"),
                "n_candidates": n_cand,
                "candidate_status": cand_status,
                "candidate_status_zh": STATUS_LABELS.get(
                    cand_status, ("", ""))[0],
                "x": s.get("x_epsg3035"),
                "y": s.get("y_epsg3035"),
            })
        return results

    def map_points(self, max_points=900):
        pts = []
        for st in self.stations.values():
            if st.get("x_epsg3035") is None:
                continue
            n_cand, cand_status = self._candidate_status(st["id"])
            pts.append({
                "id": st["id"], "x": st["x_epsg3035"],
                "y": st["y_epsg3035"],
                "name": st.get("name"),
                "river": st.get("river"),
                "state": st.get("audit_state"),
                "candidate_status": cand_status,
                "flags": st.get("audit_flags", []),
            })
            if len(pts) >= max_points:
                break
        xs = [p["x"] for p in pts]
        ys = [p["y"] for p in pts]
        return {"crs": "EPSG:3035", "unit": "metre",
                "bounds": {"xmin": min(xs), "xmax": max(xs),
                           "ymin": min(ys), "ymax": max(ys)},
                "n": len(pts), "points": pts,
                "map_note_zh": "仅投影站点坐标散点。无真实河流底图、"
                               "无认证河段、无流域边界多边形。坐标为 "
                               "EPSG:3035 投影米，不是经纬度。",
                "note": "Projected station positions only; no basemap, no "
                        "basin polygons, no certified reaches. Coordinates "
                        "are EPSG:3035 metres, NOT lat/lon degrees."}

    def export_table(self, what):
        if what == "stations":
            cols = ["id", "govnr", "name", "river", "region", "country",
                    "area_gov_km2", "elev_m", "x_epsg3035", "y_epsg3035",
                    "nrs_euhyd", "nrs_rivat", "snap_distance_m",
                    "snap_status", "natural_root", "operational_group",
                    "component_id", "component_size", "in_graph",
                    "n_upstream", "n_downstream",
                    "as_parallel_candidate_for", "as_confluence_for_pairs",
                    "audit_state", "audit_flags"]
            rows = []
            for st in sorted(self.stations.values(), key=lambda x: x["id"]):
                r = {c: st.get(c) for c in cols}
                r["audit_flags"] = "|".join(st.get("audit_flags") or [])
                rows.append(r)
            return rows, cols
        cols = ["target_id", "w_id", "confluence_node",
                "hops_target_to_confluence", "w_snap_distance_m",
                "w_nrs_rivat", "w_natural_root", "n_upstream_donors",
                "certification"]
        rows = []
        for T in sorted(self.cand_by_target):
            for it in self.cand_by_target[T]:
                path = self.path_to(T, it["confluence"])
                ws = self.stations.get(it["w"], {})
                rows.append({
                    "target_id": T, "w_id": it["w"],
                    "confluence_node": it["confluence"],
                    "hops_target_to_confluence": (len(path) - 1)
                    if path else None,
                    "w_snap_distance_m": ws.get("snap_distance_m"),
                    "w_nrs_rivat": ws.get("nrs_rivat") or "",
                    "w_natural_root": ws.get("natural_root") or "",
                    "n_upstream_donors": it["n_upstream_donors"],
                    "certification": it["certification"]})
        return rows, cols

    def predict(self):
        return {
            "status": "NOT_AUTHORIZED",
            "prediction": None,
            "model_version": None,
            "data_version": DATASET_VERSION,
            "reason": "MODEL_EXECUTION = NOT_AUTHORIZED. No Q data may be "
                      "read and no model may be run.",
            "required_inputs": [
                "Q time series for donor and target (sealed_runoff, "
                "currently quarantined)",
                "Model weights (not trained, not authorized)",
                "GIS geometry verification (GEOMETRY_VERIFIED=0)",
                "License clause comparison (BLOCKED)",
            ],
            "blocking_reasons": [
                "MODEL_EXECUTION = NOT_AUTHORIZED",
                "GEOMETRY_VERIFIED = 0",
                "CONTROL_CERTIFIED = 0",
                "FULLY_ADMITTED = 0",
                "sealed_runoff access not granted",
            ],
            "blocking_reasons_zh": [
                "模型执行未授权",
                "几何验证未通过 (=0)",
                "控制认证未通过 (=0)",
                "完全准入未通过 (=0)",
                "封存流量数据未开放",
            ],
        }
