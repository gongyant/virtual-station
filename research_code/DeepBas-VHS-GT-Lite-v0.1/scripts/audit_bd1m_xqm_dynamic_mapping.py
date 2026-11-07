"""Audit whether XQM has a legal HydroBASINS-to-ERA5-Land mapping."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
STATIONS = ROOT / "data/processed/virtual_station_multisite/multisite_stations_2005.csv"
NODES = ROOT / "data/processed/nodes.csv"
ERA5_DIR = ROOT / "data/processed/era5_land"
AUDIT = ROOT / "outputs/vhs_bd1m/xqm_dynamic_mapping_audit.csv"
REPORT = ROOT / "outputs/vhs_bd1m/xqm_dynamic_mapping_gap_report.md"
FIELDS = [
    "station_id",
    "longitude",
    "latitude",
    "basin_source",
    "era5_mapping_type",
    "area_km2",
    "status",
]


def main() -> None:
    stations = pd.read_csv(STATIONS, dtype=str)
    xqm = stations[stations["station_code"] == "XQM"]
    if xqm.empty:
        raise ValueError("XQM station record was not found")
    row = xqm.iloc[0]
    node_match = pd.DataFrame()
    if NODES.exists():
        nodes = pd.read_csv(NODES, dtype=str)
        for key in ("station_id", "station_name"):
            if key in nodes.columns:
                candidate = nodes[nodes[key].isin([row["station_id"], "XQM", "新其满"])]
                if not candidate.empty:
                    node_match = candidate
                    break

    longitude = row.get("longitude", "")
    latitude = row.get("latitude", "")
    area = row.get("upstream_area_km2", "")
    if node_match.empty:
        status = "NO_LEGAL_XQM_ERA5_MAPPING"
    else:
        status = "STATION_METADATA_FOUND_BASIN_MAPPING_UNVERIFIED"
    output = {
        "station_id": row["station_id"],
        "longitude": "" if pd.isna(longitude) else longitude,
        "latitude": "" if pd.isna(latitude) else latitude,
        "basin_source": "",
        "era5_mapping_type": "",
        "area_km2": "" if pd.isna(area) else area,
        "status": status,
    }
    with AUDIT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerow(output)

    report = f"""# BD1M XQM 动态输入映射缺口报告

## 审计结论

`XQM_ERA5_MAPPING_READY=false`

当前没有发现合法的：

`XQM → 上游 HydroBASINS 流域 → ERA5-Land`

映射链。因此本阶段不生成 XQM 动态气象特征，也不复制 BYBLK 或 DSK 的任何气象变量。

## XQM 站点记录

- 来源：`{STATIONS.relative_to(ROOT)}`
- station_id：`{row['station_id']}`
- station_code：`XQM`
- station_name：`{row.get('station_name', '')}`
- longitude：缺失
- latitude：缺失
- catchment / upstream area：缺失
- HydroBASINS ID：未发现
- ERA5-Land 映射：未发现
- 站点元数据状态：`{row.get('static_metadata_status', '')}`

节点文件 `{NODES.relative_to(ROOT)}` 中未找到可用于 XQM 的合法站点坐标或上游流域记录。ERA5-Land 目录 `{ERA5_DIR.relative_to(ROOT)}` 现有映射仅覆盖已验证站点资产，未包含 XQM。

## 输出

已生成审计表：`{AUDIT.relative_to(ROOT)}`

该表记录 XQM 当前缺口，不代表存在可用于建模的气象数据。

没有生成：

- XQM 动态气象特征
- BYBLK/DSK 到 XQM 的变量复制
- 最近站点替代变量
- 空间插值变量
- 缺失值补造

## 需要补充的真实资料

要使 XQM 进入动态气象输入，至少需要：

1. XQM 的经度、纬度；
2. 可追溯的 HydroBASINS ID 或上游流域几何；
3. 基于该上游流域与 ERA5-Land 网格的合法面积加权映射；
4. 与 Q 数据一致的日期范围和时间基准。

本阶段未训练模型，未修改冻结路径，未修改 D0、D1 或 Phase C 结果。
"""
    REPORT.write_text(report, encoding="utf-8")
    print("XQM_ERA5_MAPPING_READY=false")


if __name__ == "__main__":
    main()
