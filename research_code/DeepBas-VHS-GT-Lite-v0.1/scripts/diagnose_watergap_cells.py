from __future__ import annotations

import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlambda / 2.0) ** 2
    return float(2.0 * radius * np.arcsin(np.sqrt(a)))


def normalized_dates(values: np.ndarray) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(
        [pd.Timestamp(year=int(v.year), month=int(v.month), day=int(v.day)) for v in values]
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose WaterGAP river cells around gauging stations."
    )
    parser.add_argument(
        "--files",
        default="data/raw/watergap/obs_1978_1983/*.nc",
    )
    parser.add_argument("--variable", default="dis")
    parser.add_argument("--nodes", default="data/processed/nodes.csv")
    parser.add_argument("--timeseries", default="data/processed/timeseries.csv")
    parser.add_argument("--stations", default="00705600,00705700")
    parser.add_argument("--radius-cells", type=int, default=3)
    parser.add_argument("--start", default="1978-01-01")
    parser.add_argument("--end", default="1983-12-31")
    parser.add_argument(
        "--output", default="outputs/watergap_cell_diagnostic/candidates.csv"
    )
    args = parser.parse_args()

    files = sorted(glob.glob(args.files))
    if not files:
        raise FileNotFoundError(f"No files match {args.files}")
    nodes = pd.read_csv(args.nodes, dtype={"station_id": str}).set_index("station_id")
    observed = pd.read_csv(
        args.timeseries, usecols=["date", "station_id", "obs_q"], dtype={"station_id": str}
    )
    observed["date"] = pd.to_datetime(observed["date"])

    ds = xr.open_mfdataset(files, combine="by_coords")
    data = ds[args.variable].sel(time=slice(args.start, args.end))
    lat_values = np.asarray(ds["lat"].values, dtype=float)
    lon_values = np.asarray(ds["lon"].values, dtype=float)
    dates = normalized_dates(np.asarray(data["time"].values))

    rows: list[dict[str, float | int | str]] = []
    for station_id in [s.strip() for s in args.stations.split(",") if s.strip()]:
        station = nodes.loc[station_id]
        station_lat = float(station["latitude"])
        station_lon = float(station["longitude"])
        lat_center = int(np.argmin(np.abs(lat_values - station_lat)))
        lon_center = int(np.argmin(np.abs(lon_values - station_lon)))
        lat_start = max(0, lat_center - args.radius_cells)
        lat_stop = min(len(lat_values), lat_center + args.radius_cells + 1)
        lon_start = max(0, lon_center - args.radius_cells)
        lon_stop = min(len(lon_values), lon_center + args.radius_cells + 1)
        # Load the small neighborhood once. Re-reading the global NetCDF for
        # every candidate cell is prohibitively slow on chunked files.
        block = np.asarray(
            data.isel(
                lat=slice(lat_start, lat_stop),
                lon=slice(lon_start, lon_stop),
            ).load().values,
            dtype=float,
        )
        station_obs = (
            observed[(observed["station_id"] == station_id) & observed["obs_q"].notna()]
            .set_index("date")["obs_q"]
            .astype(float)
        )

        for lat_idx in range(lat_start, lat_stop):
            for lon_idx in range(lon_start, lon_stop):
                values = block[:, lat_idx - lat_start, lon_idx - lon_start]
                distance = haversine_km(
                    station_lon, station_lat, lon_values[lon_idx], lat_values[lat_idx]
                )
                finite = np.isfinite(values)
                valid_values = values[finite]
                mean_dis = float(np.mean(valid_values)) if valid_values.size else float("nan")
                maximum = float(np.max(valid_values)) if valid_values.size else float("nan")
                p95 = float(np.quantile(valid_values, 0.95)) if valid_values.size else float("nan")
                zero_fraction = (
                    float(np.mean(valid_values <= 1e-8)) if valid_values.size else float("nan")
                )
                # Selection score uses only WaterGAP magnitude and station distance.
                # Observations below are diagnostic and never enter this score.
                mainstem_score = mean_dis / (1.0 + distance / 50.0)

                candidate = pd.Series(values, index=dates)
                joined = pd.concat(
                    [station_obs.rename("obs"), candidate.rename("wg")], axis=1, join="inner"
                ).dropna()
                corr = (
                    float(joined.corr().iloc[0, 1])
                    if len(joined) > 1 and joined["wg"].std() > 0
                    else float("nan")
                )
                rmse = (
                    float(np.sqrt(np.mean((joined["wg"] - joined["obs"]) ** 2)))
                    if len(joined)
                    else float("nan")
                )
                rows.append(
                    {
                        "station_id": station_id,
                        "station_name": str(station["station_name"]),
                        "station_lon": station_lon,
                        "station_lat": station_lat,
                        "grid_lon": float(lon_values[lon_idx]),
                        "grid_lat": float(lat_values[lat_idx]),
                        "distance_km": distance,
                        "mean_dis": mean_dis,
                        "p95_dis": p95,
                        "max_dis": maximum,
                        "zero_fraction": zero_fraction,
                        "mainstem_score": mainstem_score,
                        "diagnostic_corr_obs": corr,
                        "diagnostic_rmse_raw": rmse,
                        "observed_days": int(len(joined)),
                    }
                )

    ds.close()
    result = pd.DataFrame(rows)
    result["mainstem_rank"] = result.groupby("station_id")["mainstem_score"].rank(
        method="first", ascending=False
    )
    result["distance_rank"] = result.groupby("station_id")["distance_km"].rank(
        method="first", ascending=True
    )
    result = result.sort_values(["station_id", "mainstem_rank"])

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(
        result[result["mainstem_rank"] <= 10][
            [
                "station_id",
                "station_name",
                "grid_lon",
                "grid_lat",
                "distance_km",
                "mean_dis",
                "p95_dis",
                "zero_fraction",
                "mainstem_score",
                "diagnostic_corr_obs",
                "diagnostic_rmse_raw",
                "mainstem_rank",
                "distance_rank",
            ]
        ].to_string(index=False)
    )
    print(f"\nSaved: {output}")


if __name__ == "__main__":
    main()
