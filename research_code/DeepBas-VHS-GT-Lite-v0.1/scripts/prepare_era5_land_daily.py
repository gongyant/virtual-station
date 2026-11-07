from __future__ import annotations

import argparse
import calendar
import json
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


EXPECTED_AREA = {
    "latitude_min": 41.0,
    "latitude_max": 44.5,
    "latitude_count": 36,
    "longitude_min": 82.0,
    "longitude_max": 87.0,
    "longitude_count": 51,
}


def month_starts(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    return list(pd.date_range(start.to_period("M").start_time, end, freq="MS"))


def expected_temperature_paths(
    raw_root: Path, start: pd.Timestamp, end: pd.Timestamp
) -> list[Path]:
    return [
        raw_root / "hourly_temperature" / f"era5land_t2m_hourly_{stamp:%Y%m}.nc"
        for stamp in month_starts(start, end)
    ]


def expected_state_paths(
    raw_root: Path, start: pd.Timestamp, end: pd.Timestamp
) -> list[Path]:
    return [
        raw_root / "hourly_00utc" / "state" / f"era5land_state_{year}_00utc.nc"
        for year in range(start.year, end.year + 1)
    ]


def expected_accumulated_paths(
    raw_root: Path, start: pd.Timestamp, end: pd.Timestamp
) -> list[Path]:
    validity_start = start + pd.Timedelta(days=1)
    validity_end = end + pd.Timedelta(days=1)
    paths: list[Path] = []
    # Accumulated fields valid at 00 UTC are assigned to the previous day.
    # Annual files cover every validity date in their year. If the requested
    # period ends on 31 December, one extra 1 January validity record is needed.
    # The old 1983-specific upper bound silently returned an empty list for the
    # external 1999-2001 experiment.
    for year in range(validity_start.year, end.year + 1):
        paths.append(
            raw_root
            / "hourly_00utc"
            / "accumulated"
            / f"era5land_accumulated_{year}_00utc.nc"
        )
    if validity_end.year > end.year:
        paths.append(
            raw_root
            / "hourly_00utc"
            / "accumulated"
            / f"era5land_accumulated_{validity_end:%Y%m%d}_00utc.nc"
        )
    return paths


def time_name(ds: xr.Dataset) -> str:
    for candidate in ("valid_time", "time"):
        if candidate in ds.coords:
            return candidate
    raise ValueError("No valid_time or time coordinate")


def coordinate_signature(ds: xr.Dataset) -> dict[str, float | int]:
    return {
        "latitude_min": float(ds.latitude.min()),
        "latitude_max": float(ds.latitude.max()),
        "latitude_count": int(ds.latitude.size),
        "longitude_min": float(ds.longitude.min()),
        "longitude_max": float(ds.longitude.max()),
        "longitude_count": int(ds.longitude.size),
    }


def expected_times(path: Path, kind: str) -> pd.DatetimeIndex:
    stem = path.stem
    if kind == "temperature":
        ym = stem.rsplit("_", 1)[-1]
        year, month = int(ym[:4]), int(ym[4:])
        days = calendar.monthrange(year, month)[1]
        return pd.date_range(
            f"{year:04d}-{month:02d}-01",
            periods=days * 24,
            freq="h",
        )
    date_token = stem.split("_")[-2]
    if len(date_token) == 8:
        return pd.DatetimeIndex([pd.Timestamp(date_token)])
    year = int(date_token)
    return pd.date_range(f"{year}-01-01", f"{year}-12-31", freq="D")


def validate_file(
    path: Path,
    kind: str,
    expected_variables: set[str],
) -> dict[str, object]:
    result: dict[str, object] = {
        "path": str(path),
        "kind": kind,
        "exists": path.is_file(),
    }
    if not path.is_file():
        result["errors"] = ["missing file"]
        return result
    if path.stat().st_size == 0:
        result["errors"] = ["empty file"]
        return result

    errors: list[str] = []
    try:
        with xr.open_dataset(path) as ds:
            tname = time_name(ds)
            actual_times = pd.DatetimeIndex(ds[tname].values)
            wanted_times = expected_times(path, kind)
            actual_variables = set(ds.data_vars)
            signature = coordinate_signature(ds)
            missing = {
                name: int(np.isnan(ds[name].values).sum()) for name in expected_variables
                if name in ds.data_vars
            }

            if not actual_times.equals(wanted_times):
                errors.append(
                    f"time mismatch: got {len(actual_times)}, expected {len(wanted_times)}"
                )
            if actual_variables != expected_variables:
                errors.append(
                    f"variable mismatch: got {sorted(actual_variables)}, "
                    f"expected {sorted(expected_variables)}"
                )
            if signature != EXPECTED_AREA:
                errors.append(f"coordinate mismatch: {signature}")
            if any(count != 0 for count in missing.values()):
                errors.append(f"missing values: {missing}")

            result.update(
                {
                    "size_bytes": path.stat().st_size,
                    "time_start": str(actual_times[0]),
                    "time_end": str(actual_times[-1]),
                    "time_count": len(actual_times),
                    "variables": sorted(actual_variables),
                    "missing_values": missing,
                    "coordinates": signature,
                }
            )
    except Exception as exc:
        errors.append(f"cannot open: {exc}")
    result["errors"] = errors
    return result


def validate_collection(
    raw_root: Path, start: pd.Timestamp, end: pd.Timestamp
) -> dict[str, object]:
    groups = [
        (
            "temperature",
            expected_temperature_paths(raw_root, start, end),
            {"t2m"},
        ),
        (
            "accumulated",
            expected_accumulated_paths(raw_root, start, end),
            {"tp", "smlt", "e"},
        ),
        (
            "state",
            expected_state_paths(raw_root, start, end),
            {"sd", "swvl1"},
        ),
    ]
    files: list[dict[str, object]] = []
    for kind, paths, variables in groups:
        files.extend(validate_file(path, kind, variables) for path in paths)

    errors = [
        {"path": item["path"], "errors": item["errors"]}
        for item in files
        if item.get("errors")
    ]
    temperature_hours = sum(
        int(item.get("time_count", 0))
        for item in files
        if item["kind"] == "temperature" and not item.get("errors")
    )
    expected_days = len(pd.date_range(start, end, freq="D"))
    return {
        "status": "passed" if not errors else "failed",
        "study_start": str(start.date()),
        "study_end": str(end.date()),
        "expected_days": expected_days,
        "expected_temperature_hours": expected_days * 24,
        "valid_temperature_hours": temperature_hours,
        "file_count": len(files),
        "valid_file_count": len(files) - len(errors),
        "error_count": len(errors),
        "errors": errors,
        "files": files,
    }


def open_clean(path: Path, variables: list[str]) -> xr.Dataset:
    with xr.open_dataset(path) as source:
        tname = time_name(source)
        selected = source[variables]
        if tname != "time":
            selected = selected.rename({tname: "time"})
        drop_coords = [
            name
            for name in selected.coords
            if name not in {"time", "latitude", "longitude"}
        ]
        if drop_coords:
            selected = selected.drop_vars(drop_coords)
        return selected.load()


def build_daily_dataset(
    raw_root: Path, start: pd.Timestamp, end: pd.Timestamp
) -> xr.Dataset:
    temperature_daily: list[xr.DataArray] = []
    for path in expected_temperature_paths(raw_root, start, end):
        hourly = open_clean(path, ["t2m"])
        temperature_daily.append(hourly.t2m.resample(time="1D").mean())
    t2m = xr.concat(temperature_daily, dim="time").sortby("time").sel(time=slice(start, end))

    accumulated = xr.concat(
        [open_clean(path, ["tp", "smlt", "e"]) for path in expected_accumulated_paths(raw_root, start, end)],
        dim="time",
    ).sortby("time")
    accumulated = accumulated.assign_coords(time=accumulated.time - np.timedelta64(1, "D"))
    accumulated = accumulated.sel(time=slice(start, end))

    state = xr.concat(
        [open_clean(path, ["sd", "swvl1"]) for path in expected_state_paths(raw_root, start, end)],
        dim="time",
    ).sortby("time").sel(time=slice(start, end))

    daily = xr.Dataset(
        {
            "temperature_c": (t2m - 273.15).astype("float32"),
            "precipitation_mm": (accumulated.tp * 1000.0).astype("float32"),
            "snowmelt_mm": (accumulated.smlt * 1000.0).astype("float32"),
            "evaporation_signed_mm": (accumulated.e * 1000.0).astype("float32"),
            "evaporation_loss_mm": (-accumulated.e * 1000.0).astype("float32"),
            "swe_mm": (state.sd.clip(min=0.0) * 1000.0).astype("float32"),
            "soil_water_layer1": state.swvl1.astype("float32"),
        },
        attrs={
            "title": "ERA5-Land daily gridded forcing for BYBLK-DSK study area",
            "daily_boundary": "UTC+00:00",
            "accumulation_convention": (
                "ERA5-Land 00 UTC accumulated fields shifted back one day"
            ),
            "temperature_aggregation": "mean of 24 hourly samples",
            "area_north_west_south_east": "44.5, 82.0, 41.0, 87.0",
        },
    )

    variable_attrs = {
        "temperature_c": {
            "long_name": "daily mean 2 metre air temperature",
            "units": "degC",
        },
        "precipitation_mm": {
            "long_name": "daily total precipitation",
            "units": "mm day-1",
        },
        "snowmelt_mm": {
            "long_name": "daily snowmelt water equivalent",
            "units": "mm day-1",
        },
        "evaporation_signed_mm": {
            "long_name": "daily ERA5-Land signed total evaporation",
            "units": "mm day-1",
            "sign_convention": "upward evaporation is usually negative",
        },
        "evaporation_loss_mm": {
            "long_name": "daily evaporation loss",
            "units": "mm day-1",
            "sign_convention": "positive values denote water loss",
        },
        "swe_mm": {
            "long_name": "daily snow water equivalent state at 00 UTC",
            "units": "mm",
        },
        "soil_water_layer1": {
            "long_name": "volumetric soil water layer 1 at 00 UTC",
            "units": "m3 m-3",
        },
    }
    for name, attrs in variable_attrs.items():
        daily[name].attrs = attrs

    expected_index = pd.date_range(start, end, freq="D")
    actual_index = pd.DatetimeIndex(daily.time.values)
    if not actual_index.equals(expected_index):
        raise ValueError(
            f"Daily time axis mismatch: got {len(actual_index)}, expected {len(expected_index)}"
        )
    for name, data in daily.data_vars.items():
        missing = int(np.isnan(data.values).sum())
        if missing:
            raise ValueError(f"{name} contains {missing} missing values")
    return daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate ERA5-Land raw files and create a strict daily gridded dataset."
    )
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw/era5_land"))
    parser.add_argument("--start", default="1978-01-01")
    parser.add_argument("--end", default="1983-12-31")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/era5_land/era5land_daily_gridded_1978_1983.nc"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("outputs/era5_land_validation/validation_report.json"),
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    if start > end:
        raise SystemExit("--start must be no later than --end")

    report = validate_collection(args.raw_root, start, end)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "files"},
            ensure_ascii=False,
            indent=2,
        )
    )
    if report["status"] != "passed":
        raise SystemExit(
            f"Validation failed with {report['error_count']} error(s); "
            f"see {args.report}"
        )
    if args.validate_only:
        return

    daily = build_daily_dataset(args.raw_root, start, end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".part")
    encoding = {
        name: {"zlib": True, "complevel": 4, "dtype": "float32"}
        for name in daily.data_vars
    }
    daily.to_netcdf(temporary, engine="netcdf4", encoding=encoding)
    temporary.replace(args.output)
    print(
        json.dumps(
            {
                "status": "created",
                "output": str(args.output),
                "size_bytes": args.output.stat().st_size,
                "days": int(daily.sizes["time"]),
                "latitude": int(daily.sizes["latitude"]),
                "longitude": int(daily.sizes["longitude"]),
                "variables": list(daily.data_vars),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
