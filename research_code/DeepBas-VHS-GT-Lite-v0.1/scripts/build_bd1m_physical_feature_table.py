"""Build the validated, non-imputed BD1M physical feature asset table."""

from __future__ import annotations

import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
SLOPE = ROOT / "outputs/vhs_bd1m/channel_slope_final.csv"
WIDTH = ROOT / "outputs/vhs_bd1m/channel_width_final.csv"
OUTPUT = ROOT / "outputs/vhs_bd1m/bd1m_physical_feature_table.csv"
REPORT = ROOT / "outputs/vhs_bd1m/bd1m_feature_inventory_report.md"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def missing(value: str | None) -> bool:
    if value is None or not value.strip():
        return True
    try:
        return not math.isfinite(float(value))
    except ValueError:
        return False


def main() -> None:
    frozen = read_csv(FREEZE)
    slopes = {row["reach_id"]: row for row in read_csv(SLOPE)}
    widths = {row["hydrorivers_id"]: row for row in read_csv(WIDTH)}
    if not frozen:
        raise ValueError("Frozen path is empty")

    fields = [
        "reach_id",
        "river_id",
        "order",
        "length_km",
        "elevation_drop_m",
        "mean_slope_m_per_m",
        "median_slope_m_per_m",
        "slope_p10_m_per_m",
        "slope_p90_m_per_m",
        "negative_slope_ratio",
        "width_m",
        "sword_reach_id",
        "width_match_distance_km",
        "path_source",
        "length_source",
        "slope_source",
        "width_source",
        "width_version",
    ]
    rows: list[dict[str, str]] = []
    for path_row in frozen:
        reach_id = path_row["reach_id"]
        slope = slopes.get(reach_id, {})
        width = widths.get(reach_id, {})
        rows.append(
            {
                "reach_id": reach_id,
                "river_id": path_row["river_id"],
                "order": path_row["order"],
                "length_km": path_row["length_km"],
                "elevation_drop_m": slope.get("elevation_drop_m", ""),
                "mean_slope_m_per_m": slope.get("mean_slope", ""),
                "median_slope_m_per_m": slope.get("median_slope", ""),
                "slope_p10_m_per_m": slope.get("slope_p10", ""),
                "slope_p90_m_per_m": slope.get("slope_p90", ""),
                "negative_slope_ratio": slope.get("negative_slope_ratio", ""),
                "width_m": width.get("width_m", ""),
                "sword_reach_id": width.get("sword_reach_id", ""),
                "width_match_distance_km": width.get("match_distance_km", ""),
                "path_source": str(FREEZE.relative_to(ROOT)).replace("\\", "/"),
                "length_source": "HydroRIVERS v10_as; frozen path length_km",
                "slope_source": str(SLOPE.relative_to(ROOT)).replace("\\", "/"),
                "width_source": width.get("width_source", ""),
                "width_version": width.get("version", ""),
            }
        )

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    feature_fields = [
        "length_km",
        "elevation_drop_m",
        "mean_slope_m_per_m",
        "median_slope_m_per_m",
        "slope_p10_m_per_m",
        "slope_p90_m_per_m",
        "negative_slope_ratio",
        "width_m",
        "width_match_distance_km",
    ]
    missing_lines = []
    for feature in feature_fields:
        count = sum(missing(row[feature]) for row in rows)
        missing_lines.append(
            f"| `{feature}` | {count} | {count / len(rows):.6%} |"
        )

    unavailable = {
        "upstream_area_km2": "未发现可按 68 个冻结 reach 对齐的已验证面积特征文件",
        "drainage_density_km_per_km2": "未发现可按 68 个冻结 reach 对齐的已验证河网密度特征文件",
        "era5_precipitation": "未发现可按 68 个冻结 reach 对齐的 ERA5 前期 reach 特征文件",
        "era5_temperature": "未发现可按 68 个冻结 reach 对齐的 ERA5 前期 reach 特征文件",
    }
    report = f"""# VHS-BD1M Phase D0 物理特征资产清单

## 状态

- 资产表：`{OUTPUT.relative_to(ROOT)}`
- 冻结路径：`{FREEZE.relative_to(ROOT)}`
- 冻结 reach 数量：{len(rows)}
- 合并方式：按 `reach_id` / `hydrorivers_id` 精确键合并
- 缺失值处理：不填补；原样保留为空值
- 模型训练：未执行
- 冻结路径：未修改
- Phase C 结果：未修改

## 已纳入特征

| 特征 | 单位 | 来源 | 模型可用性 |
|---|---|---|---|
| `length_km` | km | HydroRIVERS 冻结路径 | 可以进入模型 |
| `elevation_drop_m` | m | FABDEM 相邻采样点坡度资产 | 可以进入模型；需注意与坡度的共线性 |
| `mean_slope_m_per_m` | m/m | FABDEM | 可以进入模型 |
| `median_slope_m_per_m` | m/m | FABDEM | 可以进入模型 |
| `slope_p10_m_per_m` | m/m | FABDEM | 可以进入模型 |
| `slope_p90_m_per_m` | m/m | FABDEM | 可以进入模型 |
| `negative_slope_ratio` | ratio | FABDEM | 可以进入模型；应作为质量/地形起伏诊断变量 |
| `width_m` | m | SWORD v2 `width` 字段 | 可以进入模型 |
| `width_match_distance_km` | km | SWORD v2 几何匹配 | 可以进入模型；建议作为质量控制变量，不作为物理宽度替代 |

每条记录同时保留 `path_source`、`length_source`、`slope_source`、`width_source` 和 `width_version`。

## 缺失统计

| 特征 | 缺失数量 | 缺失比例 |
|---|---:|---:|
{chr(10).join(missing_lines)}

## 未纳入变量

下列变量在当前工作区没有发现能按 68 个冻结 reach 精确对齐且验证通过的输入资产，因此没有生成列、没有从其他任务结果推断、没有填补：

| 变量 | 状态 |
|---|---|
""" + "\n".join(f"| `{name}` | {reason} |" for name, reason in unavailable.items()) + f"""

## 数据来源与单位说明

- 路径和长度：`{FREEZE.relative_to(ROOT)}`；`length_km` 单位 km。
- 坡度：`{SLOPE.relative_to(ROOT)}`；坡度字段是相邻 DEM 采样点计算的无量纲 m/m。
- 河宽：`{WIDTH.relative_to(ROOT)}`；`width_m` 来自 SWORD v2 的真实 `width` 字段，单位 m。
- 宽度匹配距离：单位 km；不是宽度估计值。
- 当前表没有把 DSK 现场宽度、旧模型特征、站点级面积或无法按 reach 对齐的 ERA5 文件写入物理特征表。

## 模型准入结论

当前表中已验证且无缺失的特征可以作为候选模型输入，但本报告不是模型训练许可，也没有执行训练、标准化、插值、特征选择或预测。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(rows)} features={len(feature_fields)}")


if __name__ == "__main__":
    main()
