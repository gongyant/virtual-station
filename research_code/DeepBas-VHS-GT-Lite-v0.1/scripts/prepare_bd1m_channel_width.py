"""Prepare the SWORD width output without inventing unavailable widths."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FREEZE = ROOT / "outputs/vhs_bd1m/bd1m_river_path_freeze.csv"
AUDIT = ROOT / "outputs/vhs_bd1m/bd1m_sword_match_audit.csv"
OUTPUT = ROOT / "outputs/vhs_bd1m/channel_width_final.csv"
REPORT = ROOT / "outputs/vhs_bd1m/channel_width_report.md"
FIELDS = [
    "hydrorivers_id",
    "sword_reach_id",
    "width_m",
    "width_source",
    "match_distance_km",
    "quality_flag",
]


def main() -> None:
    with FREEZE.open("r", encoding="utf-8-sig", newline="") as handle:
        frozen = list(csv.DictReader(handle))
    with AUDIT.open("r", encoding="utf-8-sig", newline="") as handle:
        audit = list(csv.DictReader(handle))

    accepted = {
        row["hydrorivers_id"]: row
        for row in audit
        if row.get("accepted", "").lower() == "true"
    }
    output_rows = []
    for row in frozen:
        match = accepted.get(row["reach_id"])
        output_rows.append(
            {
                "hydrorivers_id": row["reach_id"],
                "sword_reach_id": match["sword_reach_id"] if match else "",
                "width_m": "",
                "width_source": "",
                "match_distance_km": match["match_distance"] if match else "",
                "quality_flag": "SWORD_WIDTH_UNAVAILABLE",
            }
        )

    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(output_rows)

    matched = sum(bool(row["sword_reach_id"]) for row in output_rows)
    report = f"""# BD1M 沿程河道宽度报告

## 结论

`WIDTH_READY=false`

当前工作区未发现 `data/raw/sword_v2/` 目录或其中的 SWORD v2 几何/属性文件，无法读取 SWORD 沿程宽度字段。因此本次不填补 `width_m`，也不将 DSK 现场 48 次宽度替代为沿程宽度。

## 输入与版本

- 冻结路径：`{FREEZE.relative_to(ROOT)}`
- 目标路径：HydroRIVERS BYBLK `40255730` → DSK `40282189`
- SWORD 版本：`SWORD v2`（目标版本；实际数据文件未在当前工作区提供）
- 既有匹配审计：`{AUDIT.relative_to(ROOT)}`
- 冻结 reach 数量：{len(frozen)}
- 通过既有匹配审计的 HydroRIVERS reach：{matched}

## 匹配方法

沿用既有 SWORD 匹配审计中的 `hydrorivers_id`、`sword_reach_id` 和 `match_distance`。本输出仅保留 `accepted=True` 的候选匹配距离；未通过或不存在的匹配不填入 SWORD reach ID。

- 接受阈值：既有审计的 `accepted` 标志；审计表中未记录数值阈值
- 未匹配 HydroRIVERS reach：{len(frozen) - matched}
- 已匹配但无宽度字段：{matched}

## 宽度统计

由于 SWORD v2 宽度属性文件缺失：

- 有效宽度数量：0
- 平均宽度：不可计算
- 中位宽度：不可计算
- 最小/最大宽度：不可计算

`channel_width_final.csv` 保留匹配距离和质量标志，但 `width_m`、`width_source` 有意留空；这不是插值、填补或现场宽度替代。

## 质量标志

所有冻结 reach 标记为 `SWORD_WIDTH_UNAVAILABLE`，表示当前只有匹配审计信息，缺少可追溯的 SWORD v2 宽度值。获得 SWORD v2 数据后，应重新读取宽度属性、核对单位和字段定义，再更新宽度结果。

## 限制与约束

- 未使用 DSK 现场 48 次宽度替代沿程宽度。
- 未填补不存在的宽度。
- 未修改冻结路径。
- 未训练模型。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(output_rows)} matched={matched} width_values=0 WIDTH_READY=false")


if __name__ == "__main__":
    main()
