"""Build validated station-level dynamic hydro features without imputation."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
ERA5 = ROOT / "data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc"
Q_SOURCE = ROOT / "data/processed/timeseries.csv"
XQM_SOURCE = ROOT / "data/processed/virtual_station_multisite/multisite_discharge_2005.csv"
OUTPUT = ROOT / "outputs/vhs_bd1m/bd1m_dynamic_hydro_features.csv"
REPORT = ROOT / "outputs/vhs_bd1m/bd1m_dynamic_feature_report.md"
STATIONS = {"00705600": "BYBLK", "00705700": "DSK"}
FEATURES = [
    "Q_observed",
    "P_antecedent_3d",
    "P_antecedent_7d",
    "P_antecedent_30d",
    "T_antecedent_7d",
    "T_antecedent_30d",
]


def main() -> None:
    ds = xr.open_dataset(ERA5)
    available_station_ids = {str(value) for value in ds.station.values}
    q = pd.read_csv(Q_SOURCE, dtype={"station_id": str}, parse_dates=["date"])
    output_frames: list[pd.DataFrame] = []

    for numeric_id, code in STATIONS.items():
        if numeric_id not in available_station_ids:
            continue
        forcing = ds.sel(station=numeric_id)[["precipitation_mm", "temperature_c"]].to_dataframe().reset_index()
        forcing = forcing.rename(columns={"time": "date"}).sort_values("date")
        precipitation = forcing["precipitation_mm"]
        temperature = forcing["temperature_c"]
        forcing["P_antecedent_3d"] = precipitation.rolling(3, min_periods=3).sum()
        forcing["P_antecedent_7d"] = precipitation.rolling(7, min_periods=7).sum()
        forcing["P_antecedent_30d"] = precipitation.rolling(30, min_periods=30).sum()
        forcing["T_antecedent_7d"] = temperature.rolling(7, min_periods=7).mean()
        forcing["T_antecedent_30d"] = temperature.rolling(30, min_periods=30).mean()
        observed = q[q["station_id"] == numeric_id][["date", "obs_q"]].rename(columns={"obs_q": "Q_observed"})
        merged = forcing.merge(observed, on="date", how="left", validate="one_to_one")
        merged.insert(1, "station_id", code)
        merged = merged[["date", "station_id", *FEATURES]]
        missing_columns = merged[FEATURES].isna()
        merged["source"] = (
            "Q:data/processed/timeseries.csv; "
            "P,T:data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc; "
            f"spatial_mapping:HydroBASINS_L12_upstream_basin({numeric_id})"
        )
        merged["version"] = "ERA5-Land processed 1978-1983; UTC daily"
        merged["missing_flag"] = missing_columns.apply(
            lambda row: "NONE" if not row.any() else "MISSING:" + "|".join(row.index[row]), axis=1
        )
        output_frames.append(merged)

    result = pd.concat(output_frames, ignore_index=True)
    result["date"] = result["date"].dt.strftime("%Y-%m-%d")
    result.to_csv(OUTPUT, index=False, na_rep="")

    inventory = []
    for feature in FEATURES:
        missing = int(result[feature].isna().sum())
        inventory.append((feature, missing, missing / len(result)))
    rows_with_missing = int((result["missing_flag"] != "NONE").sum())

    xqm = pd.read_csv(XQM_SOURCE, dtype={"station_id": str})
    xqm_rows = int((xqm["station_code"] == "XQM").sum())
    table_lines = "\n".join(
        f"| `{feature}` | {missing} | {ratio:.6%} |"
        for feature, missing, ratio in inventory
    )
    report = f"""# BD1M 动态水文特征报告

## 结论

- 输出：`{OUTPUT.relative_to(ROOT)}`
- 记录数：{len(result)}
- 时间范围：{result['date'].min()} 至 {result['date'].max()}
- 合法空间映射站点：BYBLK、DSK
- 未纳入站点：XQM
- 未插值、未补造数据、未训练模型

## ERA5-Land 检查

源文件 `{ERA5.relative_to(ROOT)}` 不含预先命名的 `P_3d`、`P_7d`、`P_15d`、`P_30d`、`T_3d`、`T_7d`、`T_15d`、`T_30d` 字段；它包含经过流域面积加权的逐日 `precipitation_mm` 和 `temperature_c`。

本阶段仅根据明确要求，从已有逐日变量计算输出所需窗口：

- `P_antecedent_3d`、`P_antecedent_7d`、`P_antecedent_30d`：当日及此前窗口内降水总量，单位 mm。
- `T_antecedent_7d`、`T_antecedent_30d`：当日及此前窗口内日均温平均值，单位 °C。
- 不输出未要求的 15 日窗口或 3 日温度窗口。
- 所有窗口使用完整窗口；开头不足窗口长度的记录保持缺失。

版本与处理元数据：ERA5-Land；UTC 日界；降水累积字段按源文件约定由 00 UTC 累积量回移一天；空间聚合为 HydroBASINS level 12 上游流域与 ERA5 网格精确相交面积加权。

## 站点及空间映射

| 站点 | 内部 ID | ERA5 上游流域映射 | Q 数据 | 处理结果 |
|---|---|---|---|---|
| BYBLK | `00705600` | 存在，HydroBASINS L12，面积 6773.1 km² | 1978–1983 完整日序列 | 纳入 |
| DSK | `00705700` | 存在，HydroBASINS L12，面积 18641.1 km² | 1978–1983 完整日序列 | 纳入 |
| XQM | `TARIM_XQM` | 当前 ERA5 资产中不存在；站点清单坐标和面积为空 | 2005 数据 {xqm_rows} 条 | 不纳入，避免复制错误空间变量 |

XQM 既无可验证的 ERA5 上游流域映射，也与现有 1978–1983 ERA5 时段不重叠，因此没有将 BYBLK 或 DSK 的气象变量复制给 XQM。

## 缺失统计

| 字段 | 缺失数量 | 缺失比例 |
|---|---:|---:|
{table_lines}

- 含任一缺失字段的记录：{rows_with_missing}
- `missing_flag` 逐行列出实际缺失字段；完整记录标记为 `NONE`。
- 缺失主要来自滚动窗口起始期，不进行回填或插值。

## 来源

- 观测流量：`{Q_SOURCE.relative_to(ROOT)}` 中的 `obs_q`，输出重命名为 `Q_observed`。
- 降水与温度：`{ERA5.relative_to(ROOT)}`。
- 空间映射：同一 NetCDF 的 station 坐标、HydroBASINS ID、上游面积和面积加权元数据。
- XQM 核查：`{XQM_SOURCE.relative_to(ROOT)}` 与 `data/processed/virtual_station_multisite/multisite_stations_2005.csv`。

## 限制

- 当前动态资产仅覆盖 1978–1983，并仅覆盖 BYBLK 和 DSK。
- 前期窗口为基于现有日值的确定性滚动统计，不代表额外下载或新观测变量。
- 未生成 XQM 的 ERA5 特征，因为不存在合法空间映射。
- 未插值、未填补、未训练模型。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={len(result)} stations={result.station_id.nunique()} missing_rows={rows_with_missing}")


if __name__ == "__main__":
    main()
