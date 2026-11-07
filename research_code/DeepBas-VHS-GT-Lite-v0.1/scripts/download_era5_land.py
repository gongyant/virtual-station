from __future__ import annotations

import argparse
import calendar
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_AREA = (44.5, 82.0, 41.0, 87.0)  # north, west, south, east
MONTHS = [f"{month:02d}" for month in range(1, 13)]
DAYS = [f"{day:02d}" for day in range(1, 32)]


@dataclass(frozen=True)
class DownloadJob:
    label: str
    dataset: str
    request: dict[str, Any]
    target: Path


def hourly_request(
    variables: list[str], year: int, area: tuple[float, float, float, float]
) -> dict[str, Any]:
    return {
        "variable": variables,
        "year": [str(year)],
        "month": MONTHS,
        "day": DAYS,
        "time": ["00:00"],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": list(area),
    }


def hourly_temperature_request(
    year: int, month: int, area: tuple[float, float, float, float]
) -> dict[str, Any]:
    days_in_month = calendar.monthrange(year, month)[1]
    return {
        "variable": ["2m_temperature"],
        "year": [str(year)],
        "month": [f"{month:02d}"],
        "day": [f"{day:02d}" for day in range(1, days_in_month + 1)],
        "time": [f"{hour:02d}:00" for hour in range(24)],
        "data_format": "netcdf",
        "download_format": "unarchived",
        "area": list(area),
    }


def build_jobs(
    root: Path,
    start_year: int,
    end_year: int,
    area: tuple[float, float, float, float],
    groups: set[str],
) -> list[DownloadJob]:
    jobs: list[DownloadJob] = []
    hourly_dataset = "reanalysis-era5-land"

    if "accumulated" in groups:
        out = root / "hourly_00utc" / "accumulated"
        for year in range(start_year, end_year + 1):
            jobs.append(
                DownloadJob(
                    label=f"accumulated {year}",
                    dataset=hourly_dataset,
                    request=hourly_request(
                        ["total_precipitation", "snowmelt", "total_evaporation"],
                        year,
                        area,
                    ),
                    target=out / f"era5land_accumulated_{year}_00utc.nc",
                )
            )

        # The 00 UTC value is the total for the preceding day. This extra sample
        # is therefore required to recover 31 December of the final study year.
        supplement_request = {
            "variable": ["total_precipitation", "snowmelt", "total_evaporation"],
            "year": [str(end_year + 1)],
            "month": ["01"],
            "day": ["01"],
            "time": ["00:00"],
            "data_format": "netcdf",
            "download_format": "unarchived",
            "area": list(area),
        }
        jobs.append(
            DownloadJob(
                label=f"accumulated supplement {end_year + 1}-01-01",
                dataset=hourly_dataset,
                request=supplement_request,
                target=out / f"era5land_accumulated_{end_year + 1}0101_00utc.nc",
            )
        )

    if "state" in groups:
        out = root / "hourly_00utc" / "state"
        for year in range(start_year, end_year + 1):
            jobs.append(
                DownloadJob(
                    label=f"state {year}",
                    dataset=hourly_dataset,
                    request=hourly_request(
                        ["snow_depth_water_equivalent", "volumetric_soil_water_layer_1"],
                        year,
                        area,
                    ),
                    target=out / f"era5land_state_{year}_00utc.nc",
                )
            )

    if "temperature" in groups:
        # The CDS derived daily-statistics service may queue for a long time
        # because it performs aggregation during retrieval. Downloading the
        # archived hourly temperature is more reliable; daily UTC means are
        # calculated locally with xarray after validation.
        out = root / "hourly_temperature"
        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                jobs.append(
                    DownloadJob(
                        label=f"hourly temperature {year}-{month:02d}",
                        dataset=hourly_dataset,
                        request=hourly_temperature_request(year, month, area),
                        target=out / f"era5land_t2m_hourly_{year}{month:02d}.nc",
                    )
                )

    return jobs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plan or download ERA5-Land forcing for the BYBLK-DSK study area."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/raw/era5_land"),
        help="Raw ERA5-Land output directory.",
    )
    parser.add_argument("--start-year", type=int, default=1978)
    parser.add_argument("--end-year", type=int, default=1983)
    parser.add_argument(
        "--area",
        type=float,
        nargs=4,
        metavar=("NORTH", "WEST", "SOUTH", "EAST"),
        default=DEFAULT_AREA,
    )
    parser.add_argument(
        "--group",
        action="append",
        choices=("accumulated", "state", "temperature", "all"),
        help="Repeat to select groups; defaults to all groups.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually submit requests. Without this flag, only print the plan.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing non-empty target files.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent CDS requests (1-4). Use more than one only for small chunked jobs.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=30,
        help="Retries for temporary queue, throttling, connection, or server errors.",
    )
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=60,
        help="Seconds to wait between retries after a temporary CDS error.",
    )
    return parser.parse_args()


def execute_job(
    job: DownloadJob,
    overwrite: bool,
    max_retries: int,
    retry_delay: int,
) -> tuple[str, str, int]:
    job.target.parent.mkdir(parents=True, exist_ok=True)
    if job.target.is_file() and job.target.stat().st_size > 0 and not overwrite:
        return "skipped", str(job.target), job.target.stat().st_size

    import cdsapi

    transient_markers = (
        "temporarily limited",
        "too many requests",
        "429",
        "500 server error",
        "502 server error",
        "503 server error",
        "504 server error",
        "connection error",
        "connection aborted",
        "connection reset",
        "timed out",
        "sslerror",
        "ssl: unexpected_eof_while_reading",
        "eof occurred in violation of protocol",
        "max retries exceeded",
    )
    for attempt in range(max_retries + 1):
        try:
            client = cdsapi.Client()
            client.retrieve(job.dataset, job.request, str(job.target))
            break
        except Exception as exc:
            message = str(exc).lower()
            temporary = any(marker in message for marker in transient_markers)
            if not temporary or attempt >= max_retries:
                raise
            print(
                f"retry {job.label} after temporary CDS error "
                f"({attempt + 1}/{max_retries}); waiting {retry_delay}s",
                flush=True,
            )
            time.sleep(retry_delay)
    if not job.target.is_file() or job.target.stat().st_size == 0:
        raise RuntimeError(f"Download did not create a non-empty file: {job.target}")
    return "complete", str(job.target), job.target.stat().st_size


def main() -> None:
    args = parse_args()
    if args.start_year > args.end_year:
        raise SystemExit("--start-year must be no later than --end-year")
    if not 1 <= args.workers <= 4:
        raise SystemExit("--workers must be between 1 and 4")

    area = tuple(args.area)
    north, west, south, east = area
    if not (north > south and east > west):
        raise SystemExit("Area must be ordered as NORTH WEST SOUTH EAST")

    selected = set(args.group or ["all"])
    groups = {"accumulated", "state", "temperature"} if "all" in selected else selected
    jobs = build_jobs(
        root=args.output_root,
        start_year=args.start_year,
        end_year=args.end_year,
        area=area,
        groups=groups,
    )

    print(
        json.dumps(
            {
                "execute": args.execute,
                "years": [args.start_year, args.end_year],
                "area_north_west_south_east": list(area),
                "groups": sorted(groups),
                "job_count": len(jobs),
                "targets": [str(job.target) for job in jobs],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not args.execute:
        print("Plan only. Add --execute after reviewing the request plan.")
        return

    credentials = Path.home() / ".cdsapirc"
    if not credentials.is_file():
        raise SystemExit(
            f"CDS credentials are missing: {credentials}. "
            "Create this file from the signed-in CDS 'How to use the API' page; "
            "do not paste the token into the project or terminal output."
        )

    try:
        import cdsapi
    except ImportError as exc:
        raise SystemExit(
            "cdsapi is not installed. Install the project climate extra or cdsapi>=0.7.7."
        ) from exc

    if args.workers == 1:
        for index, job in enumerate(jobs, start=1):
            print(f"[{index}/{len(jobs)}] start {job.label}: {job.target}", flush=True)
            status, target, size = execute_job(
                job, args.overwrite, args.max_retries, args.retry_delay
            )
            print(f"[{index}/{len(jobs)}] {status}: {target} ({size} bytes)", flush=True)
        return

    failures: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = {
            executor.submit(
                execute_job,
                job,
                args.overwrite,
                args.max_retries,
                args.retry_delay,
            ): job
            for job in jobs
        }
        for completed_count, future in enumerate(as_completed(pending), start=1):
            job = pending[future]
            try:
                status, target, size = future.result()
                print(
                    f"[{completed_count}/{len(jobs)}] {status} {job.label}: "
                    f"{target} ({size} bytes)",
                    flush=True,
                )
            except Exception as exc:
                failures.append((job.label, str(exc)))
                print(
                    f"[{completed_count}/{len(jobs)}] failed {job.label}: {exc}",
                    flush=True,
                )
    if failures:
        rendered = "; ".join(f"{label}: {message}" for label, message in failures)
        raise SystemExit(f"{len(failures)} download job(s) failed: {rendered}")


if __name__ == "__main__":
    main()
