"""
gis_adapter.py  --  VHS v0.4 real-GIS data adapter (Stage A, pure stdlib)
=========================================================================

Provides a *real* GIS interface without any third-party dependency and
without reading any not-yet-authorized file.

What is real here (verified by tests/test_gis_synthetic.py):
  * EPSG:3035 <-> EPSG:4326 coordinate transform (ellipsoidal LAEA Europe,
    GRS80), implemented from the projection definition. Round-trip tested
    and checked against the projection origin.
  * Pure-Python geometry primitives: point, polyline, polygon, bbox,
    point-in-polygon, polyline length, segment distance, snapping distance.
  * A LayerRegistry that declares, for every GIS layer needed by Stage B,
    its exact sandbox-relative path, expected bytes, expected SHA-256
    (from the B1A integrity manifest / C1-S2B access request) and the
    *field whitelist* allowed to be read.

What is NOT here (Stage B, needs your approval + staging):
  * No shapefile bytes are read. If a layer file is absent, the adapter
    reports status NOT_STAGED and geometry checks return UNKNOWN.
  * No Q, no network, no installs.

Rule version: RULES_V0_4 = "GIS-RULES-0.4.0". Thresholds below are
PLACEHOLDERS pending your pre-registration (see GIS_ACCESS_REQUEST.md).
"""

import hashlib
import math
import os

RULES_VERSION = "GIS-RULES-0.4.0"
ADAPTER_VERSION = "0.4.0-stageA"

# ---------------------------------------------------------------------------
# EPSG:3035  (ETRS89 / LAEA Europe)  <->  EPSG:4326 (WGS84 lon/lat)
# ---------------------------------------------------------------------------
# Projection parameters (EPSG:3035):
#   +proj=laea +lat_0=52 +lon_0=10 +x_0=4321000 +y_0=3210000
#   +ellps=GRS80 +units=m
_A = 6378137.0                 # GRS80 semi-major axis
_INV_F = 298.257222101         # GRS80 inverse flattening
_LAT0 = math.radians(52.0)
_LON0 = math.radians(10.0)
_X0 = 4321000.0
_Y0 = 3210000.0

_F = 1.0 / _INV_F
_E2 = 2 * _F - _F * _F        # first eccentricity squared
_E = math.sqrt(_E2)


def _q(phi):
    """Authalic helper q(phi) for the ellipsoid (Snyder 3-12)."""
    sinp = math.sin(phi)
    es = _E * sinp
    return (1 - _E2) * (sinp / (1 - es * es)
                        - (1 / (2 * _E)) * math.log((1 - es) / (1 + es)))


_QP = _q(math.pi / 2)
_RQ = _A * math.sqrt(_QP / 2)
_BETA1 = math.asin(_q(_LAT0) / _QP)
_M1 = math.cos(_LAT0) / math.sqrt(1 - _E2 * math.sin(_LAT0) ** 2)
_D = _A * _M1 / (_RQ * math.cos(_BETA1))


def _authalic_to_geographic(beta):
    """Inverse authalic latitude beta -> geographic phi (Newton iteration).

    Solves q(phi) = _QP * sin(beta) for phi.
    """
    target = _QP * math.sin(beta)
    phi = beta
    for _ in range(50):
        sinp = math.sin(phi)
        es = _E * sinp
        q = (1 - _E2) * (sinp / (1 - es * es)
                         - (1 / (2 * _E)) * math.log((1 - es) / (1 + es)))
        # dq/dphi = 2 (1-e^2) cos(phi) / (1 - e^2 sin^2 phi)^2
        dq = 2 * (1 - _E2) * math.cos(phi) / (1 - es * es) ** 2
        if abs(dq) < 1e-15:
            break
        dphi = (q - target) / dq
        phi -= dphi
        if abs(dphi) < 1e-13:
            break
    return phi


def laea_forward(lon_deg, lat_deg):
    """EPSG:4326 (lon,lat degrees) -> EPSG:3035 (x,y metres)."""
    lam = math.radians(lon_deg)
    phi = math.radians(lat_deg)
    beta = math.asin(_q(phi) / _QP)
    dlam = lam - _LON0
    denom = 1 + math.sin(_BETA1) * math.sin(beta) + \
        math.cos(_BETA1) * math.cos(beta) * math.cos(dlam)
    B = _RQ * math.sqrt(2.0 / denom)
    x = _X0 + B * _D * math.cos(beta) * math.sin(dlam)
    y = _Y0 + (B / _D) * (math.cos(_BETA1) * math.sin(beta)
                          - math.sin(_BETA1) * math.cos(beta) * math.cos(dlam))
    return x, y


def laea_inverse(x, y):
    """EPSG:3035 (x,y metres) -> EPSG:4326 (lon,lat degrees)."""
    xp = (x - _X0) / _D
    yp = _D * (y - _Y0)
    rho = math.hypot(xp, yp)
    if rho < 1e-12:
        return math.degrees(_LON0), math.degrees(_LAT0)
    ce = 2.0 * math.asin(min(1.0, rho / (2.0 * _RQ)))
    sinc = math.sin(ce)
    cosc = math.cos(ce)
    beta = math.asin(cosc * math.sin(_BETA1)
                     + (yp * sinc * math.cos(_BETA1)) / rho)
    lam = _LON0 + math.atan2(xp * sinc,
                             rho * math.cos(_BETA1) * cosc
                             - yp * math.sin(_BETA1) * sinc)
    phi = _authalic_to_geographic(beta)
    return math.degrees(lam), math.degrees(phi)


# ---------------------------------------------------------------------------
# Pure-Python geometry primitives
# ---------------------------------------------------------------------------
def seg_distance(px, py, ax, ay, bx, by):
    """Perpendicular/endpoint distance from point P to segment AB."""
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return math.hypot(px - cx, py - cy)


def polyline_length(pts):
    return sum(math.hypot(pts[i + 1][0] - pts[i][0],
                          pts[i + 1][1] - pts[i][1])
               for i in range(len(pts) - 1))


def point_to_polyline_distance(px, py, pts):
    if len(pts) == 1:
        return math.hypot(px - pts[0][0], py - pts[0][1])
    return min(seg_distance(px, py, pts[i][0], pts[i][1],
                            pts[i + 1][0], pts[i + 1][1])
               for i in range(len(pts) - 1))


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def point_in_polygon(px, py, ring):
    """Ray-casting. ring = [(x,y), ...], open or closed."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if ((yi > py) != (yj > py)) and \
           (px < (xj - xi) * (py - yi) / (yj - yi + 1e-300) + xi):
            inside = not inside
        j = i
    return inside


def polygon_area(ring):
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def overlap_ratio(ring_a, ring_b, samples=64):
    """Rough symmetric overlap: fraction of A's bbox grid cells inside both.

    Deterministic, dependency-free diagnostic only (Stage B replaces this
    with a proper polygon-intersection when the real polygons are staged).
    """
    ax0, ay0, ax1, ay1 = bbox(ring_a)
    inside_both = 0
    inside_a = 0
    for i in range(samples):
        for j in range(samples):
            x = ax0 + (ax1 - ax0) * (i + 0.5) / samples
            y = ay0 + (ay1 - ay0) * (j + 0.5) / samples
            ia = point_in_polygon(x, y, ring_a)
            if ia:
                inside_a += 1
                if point_in_polygon(x, y, ring_b):
                    inside_both += 1
    return (inside_both / inside_a) if inside_a else 0.0


# ---------------------------------------------------------------------------
# GIS layer registry (declared from B1A manifest + C1-S2B access request)
# ---------------------------------------------------------------------------
# Field whitelist: only these columns may ever be read from each .dbf.
# Everything else (esp. DIS_AV_CMS = Q-derived) is forbidden.
FIELD_WHITELIST = {
    "Gauges": ["ID", "govnr", "name", "river", "area_gov", "elev",
               "lon", "lat", "country", "fedstate", "region",
               "nrs_euhyd", "nrs_rivat"],
    "Basins_A": [],        # structure unknown until header screening
    "Basins_B": [],        # 64 declared fields; screened in Stage B
    "Impacts": [],         # structure unknown until header screening
    "RiverATLAS": ["HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM",
                   "DIST_DN_KM", "UPLAND_SKM"],
}

# Hard-reject patterns: if any of these appear in a .dbf header, STOP (S6).
FIELD_HARD_REJECT = ["dis_av_cms", "q_", "_cms", "discharge", "runoff",
                     "cms", "qmean", "q_mean", "q5", "q95"]

# Declared layers. Paths are sandbox-relative, kept identical to the
# manifest so hashes can be reconciled file-by-file.
LAYERS = [
    # (name, role, relative path, bytes, sha256_prefix, kind)
    ("Gauges", "station_points",
     "input/c1/batch2b/open_metadata/D_gauges/3_shapefiles/Gauges.shp",
     24796, "902be60a44d9a4be", "point"),
    ("Gauges", "station_points",
     "input/c1/batch2b/open_metadata/D_gauges/3_shapefiles/Gauges.dbf",
     1897262, "0517ef78f5f60995", "dbf"),
    ("Gauges", "station_points",
     "input/c1/batch2b/open_metadata/D_gauges/3_shapefiles/Gauges.prj",
     372, "1fb8a9c4eb5c8c90", "prj"),
    ("Basins_A", "total_upstream_catchment",
     "input/c1/batch2b/open_metadata/A_basins_total_upstrm/3_shapefiles/Basins_A.shp",
     10346972, "774eb0ebabcd97f0", "polygon"),
    ("Basins_A", "total_upstream_catchment",
     "input/c1/batch2b/open_metadata/A_basins_total_upstrm/3_shapefiles/Basins_A.dbf",
     294110, "afbe84354a6b664f", "dbf"),
    ("Basins_A", "total_upstream_catchment",
     "input/c1/batch2b/open_metadata/A_basins_total_upstrm/3_shapefiles/Basins_A.prj",
     372, "1fb8a9c4eb5c8c90", "prj"),
    ("Basins_B", "intermediate_catchment",
     "input/c1/batch2b/open_metadata/B_basins_intermediate_all/3_shapefiles/Basins_B.shp",
     4687004, "6b50406822a331f5", "polygon"),
    ("Basins_B", "intermediate_catchment",
     "input/c1/batch2b/open_metadata/B_basins_intermediate_all/3_shapefiles/Basins_B.dbf",
     297578, "40e4e1948f3ef1f7", "dbf"),
    ("Basins_B", "intermediate_catchment",
     "input/c1/batch2b/open_metadata/B_basins_intermediate_all/3_shapefiles/Basins_B.prj",
     372, "1fb8a9c4eb5c8c90", "prj"),
    ("RiverATLAS", "stream_network",
     "input/c1/batch2b/open_metadata/E_stream_network/RiverATLAS.shp",
     1858828, None, "polyline"),
    ("RiverATLAS", "stream_network",
     "input/c1/batch2b/open_metadata/E_stream_network/RiverATLAS.prj",
     372, "1fb8a9c4eb5c8c90", "prj"),
    ("RiverATLAS", "stream_network",
     "input/c1/batch2b/derived/RiverATLAS_topo6.csv",
     None, None, "topo_csv"),
    ("Impacts", "appendix_transfer",
     "input/c1/batch2b/open_metadata/G_appendix/3_shapefiles/Impacts.shp",
     17264, "df7ee5fc57330ab4", "point"),
    ("Impacts", "appendix_transfer",
     "input/c1/batch2b/open_metadata/G_appendix/3_shapefiles/Impacts.dbf",
     18584, "c13b9d30b3be6c2f", "dbf"),
]

EXPECTED_CRS_EPSG = 3035


class LayerNotStagedError(RuntimeError):
    """Raised when geometry work is requested but the layer is not staged."""


class LayerStatus:
    """Staging status of one declared GIS file (read-only, no bytes read)."""

    def __init__(self, sandbox_root, name, role, rel, exp_bytes,
                 exp_sha_prefix, kind):
        self.name = name
        self.role = role
        self.rel = rel
        self.exp_bytes = exp_bytes
        self.exp_sha_prefix = exp_sha_prefix
        self.kind = kind
        self.abs = os.path.join(sandbox_root, rel.replace("/", os.sep))

    def status(self):
        if not os.path.isfile(self.abs):
            return "NOT_STAGED"
        actual_bytes = os.path.getsize(self.abs)
        rec = {"actual_bytes": actual_bytes}
        if self.exp_bytes is not None and actual_bytes != self.exp_bytes:
            rec["size_match"] = False
            rec["status"] = "SIZE_MISMATCH"
        else:
            rec["size_match"] = True
            rec["status"] = "STAGED"
        if self.exp_sha_prefix:
            h = hashlib.sha256()
            with open(self.abs, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 16), b""):
                    h.update(chunk)
            rec["sha256"] = h.hexdigest()
            rec["sha256_match"] = h.hexdigest().startswith(self.exp_sha_prefix)
            if not rec["sha256_match"]:
                rec["status"] = "HASH_MISMATCH"
        return rec["status"]

    def public(self):
        st = self.status()
        return {
            "layer": self.name,
            "role": self.role,
            "path": self.rel,
            "kind": self.kind,
            "expected_bytes": self.exp_bytes,
            "expected_sha256_prefix": self.exp_sha_prefix,
            "field_whitelist": FIELD_WHITELIST.get(self.name, []),
            "status": st,
            "evidence": ("OBSERVED" if st == "STAGED" else "NOT_STAGED"),
        }


class GISAdapter:
    """Real-GIS adapter. Reads nothing until layers are STAGED."""

    def __init__(self, sandbox_root):
        self.root = sandbox_root
        self.layers = [LayerStatus(sandbox_root, *spec) for spec in LAYERS]
        self.rules_version = RULES_VERSION

    # -- status ----------------------------------------------------------
    def status(self):
        by_layer = {}
        for ls in self.layers:
            by_layer.setdefault(ls.name, []).append(ls.status())
        all_staged = all(
            s == "STAGED" for sts in by_layer.values() for s in sts)
        return {
            "adapter_version": ADAPTER_VERSION,
            "rules_version": RULES_VERSION,
            "expected_crs_epsg": EXPECTED_CRS_EPSG,
            "layers_staged": sum(1 for ls in self.layers
                                 if ls.status() == "STAGED"),
            "layers_total": len(self.layers),
            "all_layers_staged": all_staged,
            "data_mode": ("FULL_GIS" if all_staged else "STAGE_A_NO_GIS"),
            "layer_status": {k: v for k, v in by_layer.items()},
            "geometry_checks": "NOT_RUN" if not all_staged else "READY",
            "note": "No GIS bytes are read until all layers are STAGED. "
                    "Until then every geometry check returns UNKNOWN.",
        }

    def layers_public(self):
        return [ls.public() for ls in self.layers]

    # -- Stage B entry point (guarded) ----------------------------------
    def read_layer(self, name):
        """Read a staged layer's geometry.

        Stage A: always raises LayerNotStagedError because no GIS file is
        present. Stage B implements the actual .shp/.shx reader here.
        """
        specs = [ls for ls in self.layers if ls.name == name]
        if not specs:
            raise KeyError("unknown layer %r" % name)
        staged = [ls for ls in specs if ls.status() == "STAGED"]
        if len(staged) != len(specs) or not staged:
            raise LayerNotStagedError(
                "layer %r is not fully staged (%d/%d files present)"
                % (name, len(staged), len(specs)))
        raise LayerNotStagedError(
            "Stage B shapefile reader not enabled in this build")

    # -- field safety ----------------------------------------------------
    def screen_dbf_header(self, name, columns):
        """Return (ok, offending_columns). Hard-reject on Q-like names."""
        cols = [str(c).strip().lower() for c in columns]
        bad = [c for c in cols
               if any(p in c for p in FIELD_HARD_REJECT)]
        return (len(bad) == 0), bad

    # -- coordinate helpers ---------------------------------------------
    @staticmethod
    def to_wgs84(x, y):
        return laea_inverse(x, y)

    @staticmethod
    def to_epsg3035(lon, lat):
        return laea_forward(lon, lat)
