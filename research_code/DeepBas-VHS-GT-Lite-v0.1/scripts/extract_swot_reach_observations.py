from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests


REACH_ID = "48220900311"
SERVICE = (
    "https://gis.earthdata.nasa.gov/image/rest/services/"
    "C3233944997_POCLOUD/SWOT_L2_HR_RiverSP_reach_vD/FeatureServer/1/query"
)
OUTPUT = Path("data/processed/natural_width/swot_byblk_reach")
DISCHARGE_ALGORITHMS = ["m", "b", "h", "o", "s", "i"]
FIELDS = [
    "reach_id",
    "date_time",
    "time_str",
    "p_lat",
    "p_lon",
    "wse",
    "wse_u",
    "slope",
    "slope_u",
    "width",
    "width_u",
    "dschg_c",
    "dschg_c_u",
    "dschg_c_q",
    *[field for code in DISCHARGE_ALGORITHMS for field in [f"dschg_{code}", f"dschg_{code}_u", f"dschg_{code}_q"]],
    "reach_q",
    "dark_frac",
    "ice_clim_f",
    "ice_dyn_f",
    "partial_f",
    "n_good_nod",
    "obs_frac_n",
    "layovr_val",
    "xtrk_dist",
    "p_wse",
    "p_width",
    "p_maf",
]


def main() -> None:
    response = requests.get(
        SERVICE,
        params={
            "where": f"reach_id='{REACH_ID}'",
            "outFields": ",".join(FIELDS),
            "returnGeometry": "false",
            "f": "json",
        },
        timeout=120,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        raise RuntimeError(payload["error"])
    raw = pd.DataFrame([feature["attributes"] for feature in payload.get("features", [])])
    raw["date"] = pd.to_datetime(raw["time_str"], errors="coerce", utc=True).dt.tz_convert(None)
    numeric = [column for column in raw.columns if column not in {"reach_id", "time_str", "date"}]
    raw[numeric] = raw[numeric].apply(pd.to_numeric, errors="coerce")
    raw[numeric] = raw[numeric].mask(raw[numeric] <= -1e10)
    raw["duplicate_observation"] = raw.duplicated(
        subset=["reach_id", "time_str", "wse", "width"], keep="first"
    )

    deduplicated = raw.loc[~raw.duplicate_observation].copy()
    deduplicated["geometry_quality_pass"] = (
        deduplicated.date.notna()
        & deduplicated.date.dt.month.between(5, 10)
        & deduplicated.wse.gt(0)
        & deduplicated.width.gt(0)
        & deduplicated.slope.gt(0)
        & deduplicated.reach_q.le(1)
        & deduplicated.n_good_nod.ge(3)
        & deduplicated.obs_frac_n.ge(0.50)
        & deduplicated.dark_frac.le(0.50)
        & deduplicated.partial_f.eq(0)
    )

    consensus_values = []
    consensus_iqr = []
    consensus_count = []
    for _, row in deduplicated.iterrows():
        values = []
        for code in DISCHARGE_ALGORITHMS:
            value = row.get(f"dschg_{code}")
            quality = row.get(f"dschg_{code}_q")
            if pd.notna(value) and float(value) > 0 and pd.notna(quality) and float(quality) <= 1:
                values.append(float(value))
        consensus_values.append(float(np.median(values)) if values else np.nan)
        consensus_iqr.append(
            float(np.percentile(values, 75) - np.percentile(values, 25)) if values else np.nan
        )
        consensus_count.append(len(values))
    deduplicated["unconstrained_algorithm_median_q_m3s"] = consensus_values
    deduplicated["unconstrained_algorithm_iqr_q_m3s"] = consensus_iqr
    deduplicated["unconstrained_algorithms_available"] = consensus_count
    deduplicated["discharge_quality_pass"] = (
        deduplicated.geometry_quality_pass
        & deduplicated.unconstrained_algorithms_available.ge(3)
    )
    accepted = deduplicated.loc[deduplicated.geometry_quality_pass].copy()
    if len(accepted):
        accepted["relative_wse_m"] = accepted.wse - accepted.wse.median()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    raw.to_csv(OUTPUT / "swot_reach_observations_raw.csv", index=False)
    deduplicated.to_csv(OUTPUT / "swot_reach_observations_quality_audit.csv", index=False)
    accepted.to_csv(OUTPUT / "swot_reach_observations_accepted.csv", index=False)
    summary = {
        "status": "completed_swot_reach_extraction",
        "source": {
            "dataset": "SWOT Level 2 River Single-Pass Vector Data Product, Version D",
            "feature_service": SERVICE.rsplit("/query", 1)[0],
            "reach_id": REACH_ID,
        },
        "raw_records": int(len(raw)),
        "duplicate_records": int(raw.duplicate_observation.sum()),
        "unique_records": int(len(deduplicated)),
        "accepted_geometry_records": int(len(accepted)),
        "accepted_discharge_records": int(deduplicated.discharge_quality_pass.sum()),
        "accepted_date_range": (
            [accepted.date.min().isoformat(), accepted.date.max().isoformat()]
            if len(accepted)
            else None
        ),
        "quality_gate": {
            "reach_q_max": 1,
            "minimum_good_nodes": 3,
            "minimum_observed_node_fraction": 0.50,
            "maximum_dark_fraction": 0.50,
            "warm_season_months": [5, 10],
            "dynamic_ice_flag": "unavailable (-999), so warm-season filtering is used",
            "partial_reach_flag": 0,
            "minimum_unconstrained_discharge_algorithms": 3,
        },
        "discharge_role": (
            "SWOT algorithm ensemble diagnostic only; not in-situ discharge and not a "
            "substitute for BYBLK gauge labels. Gauge-constrained algorithm fields are "
            "excluded from the ensemble. This reach currently has no usable unconstrained "
            "algorithm discharge records."
        ),
    }
    (OUTPUT / "swot_reach_extraction_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
