from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import xarray as xr


def inspect_file(path: Path) -> dict[str, object]:
    with xr.open_dataset(path) as ds:
        time_name = "valid_time" if "valid_time" in ds.coords else "time"
        if time_name not in ds.coords:
            raise ValueError(f"No time coordinate found in {path}")

        times = ds[time_name]
        variables: dict[str, object] = {}
        for name, data in ds.data_vars.items():
            values = np.asarray(data.values)
            finite = np.isfinite(values)
            variables[name] = {
                "long_name": data.attrs.get("long_name"),
                "units": data.attrs.get("units"),
                "step_type": data.attrs.get("GRIB_stepType"),
                "shape": list(values.shape),
                "finite_count": int(finite.sum()),
                "missing_count": int((~finite).sum()),
                "min": float(np.nanmin(values)) if finite.any() else None,
                "max": float(np.nanmax(values)) if finite.any() else None,
                "mean": float(np.nanmean(values)) if finite.any() else None,
            }

        result: dict[str, object] = {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "dimensions": dict(ds.sizes),
            "time_coordinate": time_name,
            "time_start": str(times.values[0]),
            "time_end": str(times.values[-1]),
            "time_count": int(times.size),
            "variables": variables,
        }
        if "latitude" in ds.coords:
            result["latitude"] = {
                "min": float(ds.latitude.min()),
                "max": float(ds.latitude.max()),
                "count": int(ds.latitude.size),
            }
        if "longitude" in ds.coords:
            result["longitude"] = {
                "min": float(ds.longitude.min()),
                "max": float(ds.longitude.max()),
                "count": int(ds.longitude.size),
            }
        return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an ERA5-Land NetCDF file")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()

    if not args.path.is_file():
        raise SystemExit(f"File not found: {args.path}")
    report = inspect_file(args.path)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
