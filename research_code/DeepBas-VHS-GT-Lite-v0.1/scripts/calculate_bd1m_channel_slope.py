"""Calculate reach-wise slopes from adjacent DEM profile samples."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "outputs/vhs_bd1m/channel_elevation_profile.csv"
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
OUTPUT = ROOT / "outputs/vhs_bd1m/channel_slope_final.csv"
REPORT = ROOT / "outputs/vhs_bd1m/channel_slope_report.md"


def percentile(values: list[float], probability: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=float), probability * 100))


def main() -> None:
    with PROFILE.open("r", encoding="utf-8-sig", newline="") as handle:
        profile = list(csv.DictReader(handle))
    with FREEZE.open("r", encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    if not profile or not frozen:
        raise ValueError("Profile or frozen path is empty")

    grouped: dict[str, list[dict[str, str]]] = {}
    for row in profile:
        grouped.setdefault(row["reach_id"], []).append(row)

    output_rows: list[dict[str, str]] = []
    negative_segments = 0
    valid_segments = 0
    invalid_points = 0
    missing_points = 0
    for frozen_row in frozen:
        samples = grouped.get(frozen_row["reach_id"], [])
        samples.sort(key=lambda row: float(row["distance_km"]))
        elevations: list[float] = []
        distances: list[float] = []
        for sample in samples:
            try:
                elevation = float(sample["elevation_m"])
                distance = float(sample["distance_km"])
                if not math.isfinite(elevation) or not math.isfinite(distance):
                    raise ValueError
                if elevation < -500 or elevation > 9000:
                    invalid_points += 1
                    continue
                elevations.append(elevation)
                distances.append(distance)
            except (TypeError, ValueError):
                missing_points += 1

        slopes: list[float] = []
        for index in range(len(elevations) - 1):
            distance_km = distances[index + 1] - distances[index]
            if distance_km <= 0:
                continue
            slope = (elevations[index] - elevations[index + 1]) / (distance_km * 1000)
            if math.isfinite(slope):
                slopes.append(slope)
                valid_segments += 1
                if slope < 0:
                    negative_segments += 1

        if slopes:
            elevation_drop = elevations[0] - elevations[-1]
            quality = "PASS" if len(slopes) >= 2 else "LOW_SAMPLE_COUNT"
            values = {
                "elevation_drop_m": f"{elevation_drop:.3f}",
                "mean_slope": f"{float(np.mean(slopes)):.8f}",
                "median_slope": f"{float(np.median(slopes)):.8f}",
                "slope_p10": f"{percentile(slopes, 0.10):.8f}",
                "slope_p90": f"{percentile(slopes, 0.90):.8f}",
                "negative_slope_ratio": f"{sum(s < 0 for s in slopes) / len(slopes):.8f}",
                "quality_flag": quality,
            }
        else:
            values = {
                "elevation_drop_m": "",
                "mean_slope": "",
                "median_slope": "",
                "slope_p10": "",
                "slope_p90": "",
                "negative_slope_ratio": "",
                "quality_flag": "NO_VALID_SEGMENTS",
            }
        output_rows.append(
            {
                "reach_id": frozen_row["reach_id"],
                "river_id": frozen_row["river_id"],
                "length_km": frozen_row["length_km"],
                **values,
            }
        )

    fields = [
        "reach_id",
        "river_id",
        "length_km",
        "elevation_drop_m",
        "mean_slope",
        "median_slope",
        "slope_p10",
        "slope_p90",
        "negative_slope_ratio",
        "quality_flag",
    ]
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    negative_ratio = negative_segments / valid_segments if valid_segments else float("nan")
    report = f"""# BD1M 沿河道坡度计算报告

## 方法

对每个冻结 reach 内按 `distance_km` 排序的相邻采样点计算：

` slope_i = (elevation_i - elevation_i+1) / distance_i `

其中 `distance_i` 为相邻采样点间距离，单位为米；输出坡度为无量纲 `m/m`。本计算不使用 BYBLK 与 DSK 的站点高程差，也不使用 `212.61 km` 作为分母。

`elevation_drop_m` 为该 reach 内首个有效采样点与末个有效采样点的高程差，仅用于记录，不替代相邻点坡度统计。

## 数据与采样

- 高程剖面：`{PROFILE.relative_to(ROOT)}`
- DEM 来源：`data/raw/dem/FABDEM_BYBLK_DSK.tif`
- DEM 分辨率：约 30.92 m
- 采样间距：100 m
- 路径：BYBLK `40255730` → DSK `40282189`
- 冻结路径：`{FREEZE.relative_to(ROOT)}`

## 异常处理

- 空值、非有限值和超出 `[-500, 9000] m` 的高程不参与相邻点计算。
- 非正相邻距离不生成坡度样本。
- `negative_slope_ratio` 按每个 reach 的负坡度段数除以有效坡度段数计算。
- `slope_p10` 与 `slope_p90` 为有效相邻坡度的 10% 与 90% 分位数。
- 全局有效相邻坡度段：{valid_segments}
- 全局负坡度段：{negative_segments}
- 全局负坡度比例：{negative_ratio:.6%}
- 缺失高程点：{missing_points}
- 异常高程点：{invalid_points}

## 局限性

- FABDEM 是栅格 DEM，30 m 级分辨率可能无法代表实际河槽高程；采样值更接近地表/地形代理值。
- 100 m 采样间距与栅格分辨率、河道中心线几何误差会影响局部坡度。
- 本阶段未进行水库掩膜或水面校正，因此水库、坝前回水和桥梁附近的异常需结合水体或水库数据复核。
- 未进行平滑、单调约束或模型拟合，保留了相邻样点的原始起伏。
- 本阶段未训练模型。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"reaches={len(output_rows)} valid_segments={valid_segments} negative_ratio={negative_ratio:.6%}")


if __name__ == "__main__":
    main()
