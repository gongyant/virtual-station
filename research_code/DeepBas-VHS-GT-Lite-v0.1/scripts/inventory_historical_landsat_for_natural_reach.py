from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd


MATCHES = Path("data/processed/natural_width/station_sword_width_matches.csv")
OUTPUT = Path(
    "outputs/virtual_station_mainline/natural_historical_landsat_inventory_round"
)
STATION_ID = "00705600"
YEARS = list(range(1978, 1984))
MAX_CLOUD_PERCENT = 25.0
COLLECTIONS = ["landsat-c2-l1", "landsat-c2-l2"]
STAC_SEARCH_URL = "https://planetarycomputer.microsoft.com/api/stac/v1/search"


def search_catalog(year: int, bbox: list[float], collection: str) -> list[dict]:
    payload = json.dumps(
        {
            "collections": [collection],
            "bbox": bbox,
            "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z",
            "limit": 1000,
        }
    ).encode("utf-8")
    request = Request(
        STAC_SEARCH_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "DeepBas-VHS-GT-Lite/0.1"},
        method="POST",
    )
    with urlopen(request, timeout=90) as response:
        result = json.load(response)
    return result.get("features", [])


def main() -> None:
    matches = pd.read_csv(MATCHES, dtype={"station_id": str})
    station = matches.loc[matches.station_id.eq(STATION_ID)]
    if len(station) != 1:
        raise ValueError(f"Expected one station match for {STATION_ID}, found {len(station)}")
    station = station.iloc[0]
    longitude = float(station.longitude)
    latitude = float(station.latitude)
    bbox = [longitude - 0.025, latitude - 0.025, longitude + 0.025, latitude + 0.025]

    rows: list[dict] = []
    for year in YEARS:
        for collection in COLLECTIONS:
            items = search_catalog(year, bbox, collection)
            for item in items:
                properties = item.get("properties", {})
                assets = set(item.get("assets", {}))
                cloud = float(properties.get("eo:cloud_cover", float("nan")))
                has_mndwi_assets = {"green", "swir16", "qa_pixel"}.issubset(assets)
                has_ndwi_assets = {"green", "nir08", "qa_pixel"}.issubset(assets)
                rows.append(
                    {
                        "collection": collection,
                        "year": year,
                        "date": properties["datetime"][:10],
                        "item_id": item["id"],
                        "platform": properties.get("platform"),
                        "instrument": ",".join(properties.get("instruments", [])),
                        "cloud_percent": cloud,
                        "under_cloud_gate": bool(pd.notna(cloud) and cloud <= MAX_CLOUD_PERCENT),
                        "has_mndwi_assets": has_mndwi_assets,
                        "has_ndwi_assets": has_ndwi_assets,
                        "asset_keys": ",".join(sorted(assets)),
                    }
                )

    columns = [
        "collection",
        "year",
        "date",
        "item_id",
        "platform",
        "instrument",
        "cloud_percent",
        "under_cloud_gate",
        "has_mndwi_assets",
        "has_ndwi_assets",
        "asset_keys",
    ]
    inventory = pd.DataFrame(rows, columns=columns)
    if len(inventory):
        inventory = inventory.sort_values(["date", "cloud_percent", "item_id"])

    yearly = []
    for year in YEARS:
        subset = inventory.loc[inventory.year.eq(year)] if len(inventory) else inventory
        clear = subset.loc[subset.under_cloud_gate.eq(True)] if len(subset) else subset
        yearly.append(
            {
                "year": year,
                "catalog_scenes": int(len(subset)),
                "level1_scenes": int(subset.collection.eq("landsat-c2-l1").sum())
                if len(subset)
                else 0,
                "level2_scenes": int(subset.collection.eq("landsat-c2-l2").sum())
                if len(subset)
                else 0,
                "missing_cloud_metadata": int(subset.cloud_percent.isna().sum())
                if len(subset)
                else 0,
                "scenes_under_25pct_cloud": int(len(clear)),
                "mndwi_compatible_clear_scenes": int(clear.has_mndwi_assets.sum())
                if len(clear)
                else 0,
                "ndwi_compatible_clear_scenes": int(clear.has_ndwi_assets.sum())
                if len(clear)
                else 0,
                "platforms": sorted(subset.platform.dropna().astype(str).unique().tolist())
                if len(subset)
                else [],
            }
        )

    total_mndwi = sum(row["mndwi_compatible_clear_scenes"] for row in yearly)
    total_ndwi = sum(row["ndwi_compatible_clear_scenes"] for row in yearly)
    years_with_mndwi = sum(row["mndwi_compatible_clear_scenes"] > 0 for row in yearly)
    summary = {
        "status": "completed_historical_landsat_inventory",
        "station_id": STATION_ID,
        "sword_reach_id": int(station.sword_reach_id),
        "period": [str(YEARS[0]), str(YEARS[-1])],
        "cloud_gate_percent": MAX_CLOUD_PERCENT,
        "yearly": yearly,
        "totals": {
            "catalog_scenes": int(len(inventory)),
            "level1_scenes": int(inventory.collection.eq("landsat-c2-l1").sum())
            if len(inventory)
            else 0,
            "level2_scenes": int(inventory.collection.eq("landsat-c2-l2").sum())
            if len(inventory)
            else 0,
            "scenes_under_25pct_cloud": int(inventory.under_cloud_gate.sum())
            if len(inventory)
            else 0,
            "mndwi_compatible_clear_scenes": int(total_mndwi),
            "ndwi_compatible_clear_scenes": int(total_ndwi),
            "years_with_mndwi_compatible_clear_scenes": int(years_with_mndwi),
        },
        "decision": (
            "proceed_to_historical_multitransect_extraction"
            if total_mndwi >= 10 and years_with_mndwi >= 2
            else "do_not_start_supervised_inversion_from_this_archive_alone"
        ),
        "scientific_note": (
            "MSS-only scenes without SWIR1 are inventoried but are not silently mixed with "
            "the existing MNDWI width product. A separate sensor-harmonisation experiment "
            "is required before they can enter a shared rating curve."
        ),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(OUTPUT / "historical_landsat_scene_inventory_1978_1983.csv", index=False)
    (OUTPUT / "historical_landsat_inventory_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
