from __future__ import annotations

import argparse
from pathlib import Path

from vhs.io import inspect_excel, inspect_netcdf, print_json, read_station_kmz


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect raw hydrological input structure")
    parser.add_argument("path")
    args = parser.parse_args()
    path = Path(args.path)
    suffix = path.suffix.lower()
    if suffix in {".xls", ".xlsx"}:
        print_json(inspect_excel(path))
    elif suffix == ".kmz":
        frame = read_station_kmz(path)
        print_json({"path": str(path), "shape": list(frame.shape), "columns": list(frame.columns), "head": frame.head(10).to_dict("records")})
    elif suffix in {".nc", ".nc4", ".cdf"}:
        print_json(inspect_netcdf(path))
    else:
        raise SystemExit(f"Unsupported input type: {suffix}")


if __name__ == "__main__":
    main()

