"""Audit and freeze the Phase C BD1M river path using tabular topology only."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs" / "vhs_bd1m"
CANDIDATE = OUTPUT_DIR / "bd1m_river_path_candidate.csv"
FREEZE = OUTPUT_DIR / "bd1m_river_path_freeze.csv"
REPORT = OUTPUT_DIR / "bd1m_river_path_freeze_report.md"


def has_cycle(rows: list[dict[str, str]]) -> bool:
    graph = {row["reach_id"]: row["downstream_id"] for row in rows}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited or node not in graph:
            return False
        visiting.add(node)
        if visit(graph[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def main() -> None:
    with CANDIDATE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("Candidate path is empty")

    source = rows[0]["source"]
    byblk_match = re.search(r"BYBLK\(([^)]+)\)", source)
    dsk_match = re.search(r"DSK\(([^)]+)\)", source)
    byblk = byblk_match.group(1) if byblk_match else "unknown"
    dsk = dsk_match.group(1) if dsk_match else "unknown"

    continuity_failures: list[str] = []
    topology_failures: list[str] = []
    direction_failures: list[str] = []
    frozen_rows: list[dict[str, str]] = []

    for index, row in enumerate(rows):
        next_row = rows[index + 1] if index + 1 < len(rows) else None
        expected_next = next_row["upstream_id"] if next_row else dsk
        continuity_ok = row["downstream_id"] == expected_next
        topology_ok = continuity_ok
        direction_ok = row["upstream_id"] == row["reach_id"] and (
            next_row is None or int(row["order"]) < int(next_row["order"])
        )
        if not continuity_ok:
            continuity_failures.append(
                f"{row['reach_id']} -> {row['downstream_id']} (expected {expected_next})"
            )
        if not topology_ok:
            topology_failures.append(row["reach_id"])
        if not direction_ok:
            direction_failures.append(row["reach_id"])
        frozen_rows.append(
            {
                "reach_id": row["reach_id"],
                "river_id": row["river_id"],
                "upstream_id": row["upstream_id"],
                "downstream_id": row["downstream_id"],
                "length_km": row["length_km"],
                "order": row["order"],
                "continuity_check": "PASS" if continuity_ok else "FAIL",
                "source": row["source"],
            }
        )

    reach_ids = [row["reach_id"] for row in rows]
    duplicate_reaches = sorted(
        {reach_id for reach_id in reach_ids if reach_ids.count(reach_id) > 1}
    )
    total_length = sum(float(row["length_km"]) for row in rows)
    cycle = has_cycle(rows)
    continuity_ok = not continuity_failures
    topology_ok = not topology_failures
    direction_ok = not direction_failures
    no_breaks = continuity_ok
    no_duplicates = not duplicate_reaches
    path_freeze_ready = all(
        [bool(rows), continuity_ok, topology_ok, not cycle, no_duplicates, direction_ok]
    )

    with FREEZE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "reach_id",
                "river_id",
                "upstream_id",
                "downstream_id",
                "length_km",
                "order",
                "continuity_check",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(frozen_rows)

    report = f"""# VHS-BD1M Phase C 路径冻结审计报告

## 结论

`PATH_FREEZE_READY={'true' if path_freeze_ready else 'false'}`

本审计仅使用 `bd1m_river_path_candidate.csv` 的 reach 标识、`NEXT_DOWN` 对应字段和长度字段；不使用 DEM、不计算坡降、不训练模型。

## 路径概况

| 项目 | 值 |
|---|---:|
| BYBLK river_id | `{byblk}` |
| DSK river_id | `{dsk}` |
| reach 数量 | {len(rows)} |
| 总河长（km） | {total_length:.2f} |

## 拓扑与方向审计

| 检查项 | 结果 | 说明 |
|---|---|---|
| reach 连续性检查 | {'PASS' if continuity_ok else 'FAIL'} | 相邻行的 `downstream_id` 与下一行 `upstream_id` 对齐；末行与 DSK 对齐 |
| NEXT_DOWN 拓扑检查 | {'PASS' if topology_ok else 'FAIL'} | 每条 reach 的下游连接按候选路径顺序闭合 |
| 是否存在断裂 | {'否' if no_breaks else '是'} | {len(continuity_failures)} 个断裂 |
| 是否存在环 | {'是' if cycle else '否'} | 有向 `reach_id -> downstream_id` 图检查 |
| 是否存在重复 reach | {'是' if duplicate_reaches else '否'} | {', '.join(duplicate_reaches) if duplicate_reaches else '无'} |
| 路径方向是否满足上游→下游 | {'是' if direction_ok else '否'} | `order` 单调递增且 `upstream_id = reach_id` |

## 异常明细

- 连续性异常：{'; '.join(continuity_failures) if continuity_failures else '无'}
- NEXT_DOWN 异常：{'; '.join(topology_failures) if topology_failures else '无'}
- 方向异常：{'; '.join(direction_failures) if direction_failures else '无'}

## 输出

- 冻结路径：`bd1m_river_path_freeze.csv`
- 审计报告：`bd1m_river_path_freeze_report.md`
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"PATH_FREEZE_READY={'true' if path_freeze_ready else 'false'}")
    print(f"reach_count={len(rows)} total_length_km={total_length:.2f}")


if __name__ == "__main__":
    main()
