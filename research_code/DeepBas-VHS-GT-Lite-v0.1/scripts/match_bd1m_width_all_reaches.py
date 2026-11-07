"""Match all frozen HydroRIVERS reaches to real SWORD v2 widths."""

from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
SWORD_DIR = ROOT / "data/raw/sword_v2"
OUTPUT = ROOT / "outputs/vhs_bd1m/channel_width_final.csv"
REPORT = ROOT / "outputs/vhs_bd1m/channel_width_report.md"
SWORD_FILES = sorted(SWORD_DIR.glob("hb*/as_sword_reaches_hb*_v2.shp"))
FIELDS = [
    "hydrorivers_id",
    "sword_reach_id",
    "width_m",
    "width_source",
    "version",
    "match_distance_km",
    "quality_flag",
]
ACCEPTANCE_THRESHOLD_KM = 3.0


def clean_id(value: object) -> str:
    return str(value).split(".", maxsplit=1)[0]


def main() -> None:
    with FREEZE.open("r", encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    hydro = gpd.read_file(ROOT / "data/raw/hydrorivers/HydroRIVERS_v10_as.shp", engine="pyogrio")
    hydro["hydro_id"] = hydro["HYRIV_ID"].map(clean_id)
    hydro = hydro.set_index("hydro_id").loc[[row["reach_id"] for row in frozen]].reset_index()

    frames = []
    for path in SWORD_FILES:
        frame = gpd.read_file(path, engine="pyogrio")
        frame = frame[["reach_id", "width", "geometry"]].copy()
        frame["sword_reach_id"] = frame["reach_id"].map(clean_id)
        frame["width_source"] = str(path.relative_to(ROOT)).replace("\\", "/")
        frames.append(frame)
    sword = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    projected_crs = "EPSG:32645"
    hydro_p = hydro.to_crs(projected_crs)
    sword_p = sword.to_crs(projected_crs).reset_index(drop=True)
    index = sword_p.sindex

    matches = []
    for _, row in hydro_p.iterrows():
        candidate = int(index.nearest(row.geometry, return_all=False)[1][0])
        target = sword_p.iloc[candidate]
        distance_km = row.geometry.distance(target.geometry) / 1000
        matches.append((row["hydro_id"], target["sword_reach_id"], float(distance_km), target["width"], target["width_source"]))

    values = {item[0]: item for item in matches}
    output_rows = []
    valid = 0
    unmatched = 0
    for row in frozen:
        hydro_id = row["reach_id"]
        _, sword_id, distance_km, width, source = values[hydro_id]
        try:
            width_value = float(width)
            width_ok = width_value > 0
        except (TypeError, ValueError):
            width_value = None
            width_ok = False
        accepted = distance_km <= ACCEPTANCE_THRESHOLD_KM
        if accepted and width_ok:
            quality = "PASS"
            valid += 1
        elif accepted:
            quality = "SWORD_WIDTH_MISSING"
        else:
            quality = "MATCH_DISTANCE_OVER_THRESHOLD"
            unmatched += 1
        output_rows.append({
            "hydrorivers_id": hydro_id,
            "sword_reach_id": sword_id if accepted else "",
            "width_m": f"{width_value:.3f}" if accepted and width_ok else "",
            "width_source": source if accepted and width_ok else "",
            "version": "SWORD v2",
            "match_distance_km": f"{distance_km:.3f}",
            "quality_flag": quality,
        })

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    widths = [float(row["width_m"]) for row in output_rows if row["width_m"]]
    report = f"""# BD1M 沿程河道宽度报告

## 结论

`WIDTH_READY={'true' if valid == len(frozen) else 'false'}`

本次重新读取真实 SWORD v2 数据，并对冻结路径全部 {len(frozen)} 个 HydroRIVERS reach 执行几何最近匹配。`width_m` 仅来自真实 SWORD 属性字段 `width`，不使用 DSK 现场 48 次宽度，不进行插值或缺失值填补。

## SWORD 数据与字段

- 版本：`SWORD v2`
- 数据目录：`{SWORD_DIR.relative_to(ROOT)}`
- Shapefile 数量：{len(SWORD_FILES)}
- 宽度字段：`width`（米）
- 伴随字段：`width_var`、`max_width`
- 参与文件：{', '.join(str(path.relative_to(ROOT)).replace('\\', '/') for path in SWORD_FILES)}

## 匹配方法

- HydroRIVERS 几何：`data/raw/hydrorivers/HydroRIVERS_v10_as.shp`
- SWORD 几何：上述 SWORD v2 reach Shapefile
- 方法：将两类线几何转换到 `EPSG:32645`，对每个冻结 HydroRIVERS reach 进行最近 SWORD reach 匹配
- 距离：最近线几何距离，单位 km
- 接受阈值：`<= {ACCEPTANCE_THRESHOLD_KM:.1f} km`；该阈值与既有匹配审计的 accepted/false 分界一致（既有审计中 2.429 km 为 accepted、5.451 km 为 false）
- 未接受的最近候选不写入 `sword_reach_id` 或 `width_m`，仅保留距离和质量标志

## 结果统计

| 项目 | 数量/值 |
|---|---:|
| 冻结 HydroRIVERS reach | {len(frozen)} |
| 通过距离和宽度检查 | {valid} |
| 超过距离阈值 | {unmatched} |
| 缺少有效 width | {len(frozen) - valid - unmatched} |
| 宽度均值（m） | {sum(widths) / len(widths) if widths else float('nan'):.3f} |
| 宽度中位数（m） | {pd.Series(widths).median() if widths else float('nan'):.3f} |
| 最小宽度（m） | {min(widths) if widths else float('nan'):.3f} |
| 最大宽度（m） | {max(widths) if widths else float('nan'):.3f} |

## 质量标志

- `PASS`：最近 SWORD v2 reach 距离在阈值内，且真实 `width` 为有效正值。
- `MATCH_DISTANCE_OVER_THRESHOLD`：最近候选超出接受阈值，未填入宽度。
- `SWORD_WIDTH_MISSING`：匹配在阈值内但 width 无有效值，保持空值。

## 约束

- 没有使用 DSK 现场 48 次宽度。
- 没有插值、外推或填补不存在的宽度。
- 没有训练模型。
- 没有修改 `bd1m_river_path_freeze.csv`。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"reaches={len(frozen)} valid_widths={valid} over_threshold={unmatched}")


if __name__ == "__main__":
    main()
