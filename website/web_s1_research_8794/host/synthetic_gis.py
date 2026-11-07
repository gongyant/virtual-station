"""
synthetic_gis.py  --  VHS v0.4 Stage-B website interface preview
================================================================

Deterministic SYNTHETIC GIS layers used ONLY to exercise the website's
layer interface, interaction buttons and evidence display *before* the real
GIS files are staged.

*** THIS IS NOT REAL GEOGRAPHY. ***
The network lives in a private local coordinate box (0..100) and is
explicitly labelled SYNTHETIC everywhere. It is never overlaid on the real
station map and never used to claim any geometry certification.

Every layer carries source="SYNTHETIC" and a content hash so the evidence
panel can show provenance exactly as it will for the real layers.
"""

import hashlib
import json

RULES_VERSION = "GIS-RULES-0.4.0"
SOURCE = "SYNTHETIC"

# --- synthetic network geometry (local box 0..100) ------------------------
_W_TRIB = [[8, 86], [18, 74], [26, 64], [32, 58]]
_U_TRIB = [[44, 90], [42, 76], [38, 66], [32, 58]]
_MAIN = [[32, 58], [44, 44], [58, 30], [74, 16], [90, 8]]

_CONFLUENCE = [32, 58]
_T_POS = [44, 44]
_U_POS = [42, 76]
_W_POS = [18, 74]
_COMMON_DOWNSTREAM = [58, 30]

# synthetic catchment polygons (deliberately simple rings)
_BASIN_A_T = [[6, 92], [46, 92], [46, 60], [50, 40], [36, 40], [30, 56],
              [6, 60]]                       # total upstream of T
_BASIN_B_W = [[6, 88], [30, 88], [30, 58], [6, 58]]   # intermediate, W side
_BASIN_B_U = [[32, 92], [48, 92], [48, 58], [32, 58]]  # intermediate, U side


def _sha(obj):
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True).encode()).hexdigest()


def build():
    """Return the synthetic layer bundle (GeoJSON-like, stdlib only)."""
    layers = []

    def add(name, role, geometry_type, coords, **extra):
        fc = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": geometry_type,
                                             "coordinates": coords},
             "properties": {"synthetic": True}}]}
        rec = {
            "layer": name, "role": role, "geometry_type": geometry_type,
            "source": SOURCE,
            "sha256": _sha(fc),
            "feature_count": len(coords) if isinstance(coords, list) else 1,
            "geojson": fc,
            "status": "SYNTHETIC",
            "evidence": "SYNTHETIC (not real GIS; interface preview only)",
        }
        rec.update(extra)
        layers.append(rec)

    # real-layer *interfaces* (names/roles/hashes) previewed with synthetic
    # geometry so the UI wiring is identical to Stage B.
    add("RiverATLAS", "stream_network", "MultiLineString",
        [_W_TRIB, _U_TRIB, _MAIN],
        field_whitelist=["HYRIV_ID", "NEXT_DOWN", "MAIN_RIV", "LENGTH_KM",
                         "DIST_DN_KM", "UPLAND_SKM"])
    add("Basins_A", "total_upstream_catchment", "Polygon", [_BASIN_A_T])
    add("Basins_B", "intermediate_catchment", "MultiPolygon",
        [[_BASIN_B_W], [_BASIN_B_U]])

    stations = [
        {"id": "T", "role": "target", "pos": _T_POS},
        {"id": "U", "role": "upstream", "pos": _U_POS},
        {"id": "W", "role": "donor", "pos": _W_POS},
        {"id": "J", "role": "confluence", "pos": _CONFLUENCE},
    ]

    return {
        "synthetic": True,
        "rules_version": RULES_VERSION,
        "note": "SYNTHETIC preview network — NOT real geography. Used only "
                "to validate the Stage-B layer interface and interactions.",
        "crs": "LOCAL_SYNTHETIC_BOX_0_100",
        "layers": layers,
        "stations": stations,
        "reach_paths": {
            "T_to_J": [_T_POS, _CONFLUENCE],
            "W_to_J": [_W_POS, [26, 64], _CONFLUENCE],
            "U_to_J": [_U_POS, [38, 66], _CONFLUENCE],
        },
        "confluence_node": _CONFLUENCE,
        "common_downstream_node": _COMMON_DOWNSTREAM,
        "evidence_rows": [
            {"relation": "T–J reach path", "verdict": "SYNTHETIC",
             "reason": "interface preview only; real verdict requires RiverATLAS"},
            {"relation": "W–J reach path", "verdict": "SYNTHETIC",
             "reason": "interface preview only"},
            {"relation": "A(T) ⊇ A(U)", "verdict": "SYNTHETIC",
             "reason": "interface preview only; real check requires Basins_A"},
            {"relation": "A(T) ∩ A(W) ≤ ε", "verdict": "SYNTHETIC",
             "reason": "interface preview only; real check requires Basins_A"},
            {"relation": "snapping ≤ τ_snap", "verdict": "SYNTHETIC",
             "reason": "interface preview only"},
        ],
    }


if __name__ == "__main__":
    print(json.dumps(build(), indent=1, ensure_ascii=False)[:800])
