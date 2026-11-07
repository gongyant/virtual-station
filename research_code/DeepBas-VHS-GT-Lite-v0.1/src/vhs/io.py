from __future__ import annotations

import glob
import json
import zipfile
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET

import numpy as np
import pandas as pd


KML_NS = {"k": "http://www.opengis.net/kml/2.2"}


def read_station_kmz(path: str | Path) -> pd.DataFrame:
    """Read station point geometry and ExtendedData from a KMZ.

    Point coordinates are authoritative. This avoids the known issue where some
    station files place longitude in LAT1 and latitude in LON1.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"KMZ is missing or empty: {path}")
    with zipfile.ZipFile(path) as zf:
        kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
        if not kml_names:
            raise ValueError(f"No KML found inside {path}")
        root = ET.fromstring(zf.read(kml_names[0]))

    rows: list[dict[str, object]] = []
    for placemark in root.findall(".//k:Placemark", KML_NS):
        coord_text = placemark.findtext(".//k:Point/k:coordinates", default="", namespaces=KML_NS)
        if not coord_text.strip():
            continue
        first = coord_text.strip().split()[0]
        parts = first.split(",")
        if len(parts) < 2:
            continue
        attrs = {
            item.attrib.get("name", ""): (item.text or "").strip()
            for item in placemark.findall(".//k:SimpleData", KML_NS)
        }
        name = placemark.findtext("k:name", default="", namespaces=KML_NS).strip()
        row: dict[str, object] = {
            "station_name": name,
            "station_id": attrs.get("CZID") or attrs.get("ID") or name,
            "longitude": float(parts[0]),
            "latitude": float(parts[1]),
            "source_file": path.name,
        }
        row.update({f"kmz_{k}": v for k, v in attrs.items()})
        rows.append(row)
    if not rows:
        raise ValueError(f"No point placemarks found in {path}")
    return pd.DataFrame(rows)


def inspect_excel(path: str | Path, head: int = 5) -> dict[str, object]:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"Excel file is missing or empty: {path}")
    book = pd.ExcelFile(path)
    result: dict[str, object] = {"path": str(path), "sheets": {}}
    for sheet in book.sheet_names:
        frame = pd.read_excel(path, sheet_name=sheet)
        result["sheets"][sheet] = {
            "shape": list(frame.shape),
            "columns": [str(c) for c in frame.columns],
            "head": frame.head(head).astype(object).where(pd.notna(frame.head(head)), None).to_dict("records"),
        }
    return result


def read_flow_source(spec: dict) -> pd.DataFrame:
    """Convert a long or wide Excel sheet to date, station_id, obs_q."""
    path = Path(spec["path"])
    if not path.exists() or path.stat().st_size == 0:
        raise ValueError(f"Flow file is missing or empty: {path}")
    frame = pd.read_excel(path, sheet_name=spec.get("sheet", 0))
    date_col = spec["date_column"]
    if date_col not in frame:
        raise KeyError(f"Date column {date_col!r} not found in {path}; columns={list(frame.columns)}")

    if spec.get("wide_station_columns"):
        pieces = []
        for col, station_id in spec["wide_station_columns"].items():
            if col not in frame:
                raise KeyError(f"Wide flow column {col!r} not found in {path}")
            piece = frame[[date_col, col]].copy()
            piece.columns = ["date", "obs_q"]
            piece["station_id"] = str(station_id)
            pieces.append(piece)
        out = pd.concat(pieces, ignore_index=True)
    else:
        station_col = spec["station_column"]
        value_col = spec["value_column"]
        out = frame[[date_col, station_col, value_col]].copy()
        out.columns = ["date", "station_id", "obs_q"]
        mapping = spec.get("station_name_to_id", {})
        out["station_id"] = out["station_id"].astype(str).replace(mapping)

    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out["obs_q"] = pd.to_numeric(out["obs_q"], errors="coerce")
    out["station_id"] = out["station_id"].astype(str)
    out = out.dropna(subset=["date"]).sort_values(["date", "station_id"])
    return out[["date", "station_id", "obs_q"]]


def _coordinate_name(ds, candidates: Iterable[str]) -> str:
    lower = {str(name).lower(): str(name) for name in list(ds.coords) + list(ds.dims)}
    for candidate in candidates:
        if candidate in lower:
            return lower[candidate]
    raise KeyError(f"None of coordinate names {list(candidates)} found; coords={list(ds.coords)}")


def inspect_netcdf(path: str | Path) -> dict[str, object]:
    import xarray as xr

    with xr.open_dataset(path) as ds:
        return {
            "path": str(path),
            "dims": {str(k): int(v) for k, v in ds.sizes.items()},
            "coords": list(map(str, ds.coords)),
            "variables": {
                str(k): {"dims": list(map(str, v.dims)), "units": v.attrs.get("units")}
                for k, v in ds.data_vars.items()
            },
        }


def extract_netcdf_nearest(
    file_pattern: str,
    variable: str,
    stations: pd.DataFrame,
    feature_name: str,
) -> pd.DataFrame:
    import xarray as xr

    files = sorted(glob.glob(file_pattern))
    if not files:
        raise FileNotFoundError(f"No NetCDF files match: {file_pattern}")
    ds = xr.open_mfdataset(files, combine="by_coords")
    if variable not in ds:
        raise KeyError(f"Variable {variable!r} not in dataset; variables={list(ds.data_vars)}")
    lat_name = _coordinate_name(ds, ["lat", "latitude", "y"])
    lon_name = _coordinate_name(ds, ["lon", "longitude", "x"])
    time_name = _coordinate_name(ds, ["time"])
    lon_values = ds[lon_name]
    uses_360 = float(lon_values.max()) > 180.0

    pieces = []
    for row in stations.itertuples(index=False):
        lon = float(row.longitude)
        if uses_360 and lon < 0:
            lon += 360.0
        arr = ds[variable].sel({lat_name: float(row.latitude), lon_name: lon}, method="nearest")
        frame = arr.to_dataframe(name=feature_name).reset_index()
        frame = frame.rename(columns={time_name: "date"})
        frame["station_id"] = str(row.station_id)
        pieces.append(frame[["date", "station_id", feature_name]])
    ds.close()
    out = pd.concat(pieces, ignore_index=True)
    # out["date"] = pd.to_datetime(out["date"])
    out["date"] = out["date"].map(
        lambda value: pd.Timestamp(
            year=int(value.year),
            month=int(value.month),
            day=int(value.day),
        )
        if all(hasattr(value, field) for field in ("year", "month", "day"))
        else pd.to_datetime(value, errors="coerce")
    )
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out = out.dropna(subset=["date"])
    return out


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))
