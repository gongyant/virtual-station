"""Update BD1M channel widths from the discovered SWORD v2 reach tables."""

from __future__ import annotations

import csv
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
AUDIT = ROOT / "outputs/vhs_bd1m/bd1m_sword_match_audit.csv"
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


def clean_id(value: object) -> str:
    return str(value).split(".", maxsplit=1)[0]


def main() -> None:
    if not SWORD_FILES:
        raise FileNotFoundError("No SWORD v2 shapefiles found")
    with FREEZE.open("r", encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    with AUDIT.open("r", encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))

    accepted = {
        clean_id(row["hydrorivers_id"]): row
        for row in audit
        if row.get("accepted", "").lower() == "true"
    }
    sword_by_id: dict[str, dict[str, object]] = {}
    field_names: set[str] = set()
    for path in SWORD_FILES:
        info = gpd.read_file(path, engine="pyogrio", columns=["reach_id", "width"])
        for _, row in info.iterrows():
            sword_by_id[clean_id(row["reach_id"])] = {
                "width": row["width"],
                "source": str(path.relative_to(ROOT)).replace("\\", "/"),
            }
        field_names.update(info.columns)

    output_rows: list[dict[str, str]] = []
    width_values: list[float] = []
    unmatched = 0
    missing_width = 0
    for row in frozen:
        hydro_id = clean_id(row["reach_id"])
        match = accepted.get(hydro_id)
        sword_id = clean_id(match["sword_reach_id"]) if match else ""
        sword = sword_by_id.get(sword_id) if sword_id else None
        width = sword.get("width") if sword else None
        try:
            width_value = float(width)
            has_width = width_value > 0
        except (TypeError, ValueError):
            width_value = None
            has_width = False
        if has_width:
            width_values.append(width_value)
            quality = "PASS"
        elif match and sword:
            missing_width += 1
            quality = "SWORD_WIDTH_MISSING"
        else:
            unmatched += 1
            quality = "NO_ACCEPTED_MATCH"
        output_rows.append(
            {
                "hydrorivers_id": hydro_id,
                "sword_reach_id": sword_id if sword else "",
                "width_m": "" if width_value is None else f"{width_value:.3f}",
                "width_source": sword["source"] if sword and has_width else "",
                "version": "SWORD v2",
                "match_distance_km": match["match_distance"] if match else "",
                "quality_flag": quality,
            }
        )

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    mean_width = sum(width_values) / len(width_values) if width_values else float("nan")
    sorted_widths = sorted(width_values)
    median_width = (
        sorted_widths[len(sorted_widths) // 2]
        if sorted_widths and len(sorted_widths) % 2
        else (sorted_widths[len(sorted_widths) // 2 - 1] + sorted_widths[len(sorted_widths) // 2]) / 2
        if sorted_widths
        else float("nan")
    )
    report = f"""# BD1M 沿程河道宽度报告

## 结论

`WIDTH_READY={'true' if len(width_values) == len(frozen) else 'false'}`

本次使用发现的真实 SWORD v2 属性表中的 `width` 字段，单位按 SWORD 数据定义记录为米。未使用 DSK 现场 48 次宽度，未进行插值或缺失值填补，未修改冻结路径。

## SWORD 数据

- 版本：`SWORD v2`
- 数据目录：`{SWORD_DIR.relative_to(ROOT)}`
- 发现的 SWORD Shapefile 数量：{len(SWORD_FILES)}
- 参与匹配文件：{', '.join(str(path.relative_to(ROOT)).replace('\\', '/') for path in SWORD_FILES)}
- 宽度字段：`width`
- 伴随字段：`width_var`, `max_width`

## 匹配方法

- HydroRIVERS 输入：`{FREEZE.relative_to(ROOT)}`，共 {len(frozen)} 个冻结 reach
- SWORD 匹配审计：`{AUDIT.relative_to(ROOT)}`
- 使用既有审计中的 `accepted=True` 和 `sword_reach_id`
- 保留既有 `match_distance`，输出字段名为 `match_distance_km`
- 未使用 DSK 现场宽度替代 SWORD 沿程宽度
- 未匹配或没有有效 SWORD 宽度的记录保持空值

## 结果统计

| 项目 | 数量/值 |
|---|---:|
| 冻结 HydroRIVERS reach | {len(frozen)} |
| 有效 SWORD 宽度 | {len(width_values)} |
| 未接受匹配或未找到记录 | {unmatched} |
| 匹配记录但宽度缺失/无效 | {missing_width} |
| 宽度均值（m） | {mean_width:.3f} |
| 宽度中位数（m） | {median_width:.3f} |
| 最小宽度（m） | {min(width_values) if width_values else float('nan'):.3f} |
| 最大宽度（m） | {max(width_values) if width_values else float('nan'):.3f} |

## 质量标志

- `PASS`：width 字段为真实 SWORD v2 有效正值。
- `NO_ACCEPTED_MATCH`：既有匹配审计没有接受的 SWORD 匹配，保持空值。
- `SWORD_WIDTH_MISSING`：已有 SWORD reach 记录，但 width 无有效正值，保持空值。

## 约束

- 没有使用 DSK 现场 48 次宽度。
- 没有插值、外推或填补不存在的宽度。
- 没有训练模型。
- 没有修改 `bd1m_river_path_freeze.csv`。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(output_rows)} valid_widths={len(width_values)} unmatched={unmatched}")


if __name__ == "__main__":
    main()
