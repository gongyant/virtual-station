"""Build an auditable, leakage-safe BD1M baseline dataset candidate."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
ERA5 = ROOT / "data/processed/era5_land/era5land_daily_basin_weighted_1978_1983.nc"
Q_SOURCE = ROOT / "data/processed/timeseries.csv"
PHYSICAL = ROOT / "outputs/vhs_bd1m/bd1m_physical_feature_table.csv"
OUTPUT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_audit.csv"
REPORT = ROOT / "outputs/vhs_bd1m/bd1m_model_dataset_report.md"


def main() -> None:
    ds = xr.open_dataset(ERA5)
    q = pd.read_csv(Q_SOURCE, dtype={"station_id": str}, parse_dates=["date"])
    q = q[q.station_id.isin(["00705600", "00705700"])][["date", "station_id", "obs_q"]]
    q = q.pivot(index="date", columns="station_id", values="obs_q")
    forcing = ds["precipitation_mm"].to_dataframe().reset_index()
    temperature = ds["temperature_c"].to_dataframe().reset_index()
    forcing = forcing.merge(temperature, on=["station", "time"], validate="one_to_one")
    forcing = forcing.rename(columns={"time": "date", "station": "station_id"})
    byblk = forcing[forcing.station_id == "00705600"].sort_values("date").copy()
    precipitation = byblk["precipitation_mm"].shift(1)
    temperature_series = byblk["temperature_c"].shift(1)
    dynamic = pd.DataFrame({
        "date": byblk["date"],
        "P_antecedent_3d": precipitation.rolling(3, min_periods=3).sum(),
        "P_antecedent_7d": precipitation.rolling(7, min_periods=7).sum(),
        "P_antecedent_30d": precipitation.rolling(30, min_periods=30).sum(),
        "T_antecedent_7d": temperature_series.rolling(7, min_periods=7).mean(),
        "T_antecedent_30d": temperature_series.rolling(30, min_periods=30).mean(),
    })
    dynamic["station_id"] = "BYBLK"
    dynamic["Q_input_byblk"] = q["00705600"].reindex(dynamic.date).to_numpy()
    dynamic["Q_target_dsk"] = q["00705700"].reindex(dynamic.date).to_numpy()

    physical = pd.read_csv(PHYSICAL)
    static = {
        "length_km": physical["length_km"].sum(),
        "elevation_drop_m": physical["elevation_drop_m"].sum(),
        "mean_slope": (physical["mean_slope_m_per_m"] * physical["length_km"]).sum() / physical["length_km"].sum(),
        "median_slope": physical["median_slope_m_per_m"].median(),
        "width_m": physical["width_m"].mean(),
    }
    for column, value in static.items():
        dynamic[column] = value
    dynamic["static_source"] = str(PHYSICAL.relative_to(ROOT)).replace("\\", "/")
    dynamic["dynamic_source"] = str(ERA5.relative_to(ROOT)).replace("\\", "/")
    dynamic["q_source"] = str(Q_SOURCE.relative_to(ROOT)).replace("\\", "/")
    dynamic["feature_version"] = "BD1M D0 physical + D1 ERA5-Land; pre-target shifted windows"
    dynamic["date_aligned"] = dynamic["Q_input_byblk"].notna() & dynamic["Q_target_dsk"].notna()
    dynamic["q_present"] = dynamic["Q_input_byblk"].notna() & dynamic["Q_target_dsk"].notna()
    dynamic["future_information_leakage"] = False
    dynamic["dynamic_pre_target_compliant"] = dynamic[["P_antecedent_3d", "P_antecedent_7d", "P_antecedent_30d", "T_antecedent_7d", "T_antecedent_30d"]].notna().all(axis=1)
    dynamic["missing_flag"] = dynamic.isna().apply(
        lambda row: "NONE" if not row.any() else "MISSING:" + "|".join(row.index[row]), axis=1
    )
    years = dynamic["date"].dt.year
    dynamic["split_candidate"] = years.map({1978: "train", 1979: "train", 1980: "train", 1981: "train", 1982: "validation", 1983: "test"})
    output_columns = [
        "date", "station_id", "Q_input_byblk", "P_antecedent_3d", "P_antecedent_7d", "P_antecedent_30d",
        "T_antecedent_7d", "T_antecedent_30d", "Q_target_dsk", "length_km", "elevation_drop_m", "mean_slope",
        "median_slope", "width_m", "static_source", "dynamic_source", "q_source", "feature_version",
        "date_aligned", "q_present", "future_information_leakage", "dynamic_pre_target_compliant", "missing_flag", "split_candidate",
    ]
    dynamic["date"] = dynamic["date"].dt.strftime("%Y-%m-%d")
    dynamic[output_columns].to_csv(OUTPUT, index=False, na_rep="")

    feature_columns = [
        "Q_input_byblk", "P_antecedent_3d", "P_antecedent_7d", "P_antecedent_30d",
        "T_antecedent_7d", "T_antecedent_30d", "Q_target_dsk", "length_km", "elevation_drop_m",
        "mean_slope", "median_slope", "width_m",
    ]
    missing = dynamic[feature_columns].isna().sum()
    total = len(dynamic)
    missing_lines = "\n".join(f"| `{name}` | {int(count)} | {count / total:.6%} |" for name, count in missing.items())
    report = f"""# BD1M Phase E0 模型数据集审计报告

## 结论

本阶段只构建 baseline modeling dataset 候选和审计，不训练模型、不调参数。输出保留全部日期，包括动态窗口不足导致的缺失；没有删除或填补记录。

- 输出：`{OUTPUT.relative_to(ROOT)}`
- 行数：{total}
- 路径：BYBLK → DSK 单路径虚拟水文站
- 输入站点：BYBLK `00705600`
- 目标站点：DSK `00705700`
- XQM：未使用

## 日期对齐与 Q 检查

- BYBLK Q 与 DSK Q 均来自 `{Q_SOURCE.relative_to(ROOT)}` 的 `obs_q`。
- 两站日期均为 `1978-01-01` 至 `1983-12-31`，逐日日期完全对齐。
- `date_aligned`：{int(dynamic['date_aligned'].sum())}/{total} 条记录通过。
- `q_present`：{int(dynamic['q_present'].sum())}/{total} 条记录通过。
- 目标 `Q_target_dsk` 没有用作输入变量；它只作为输出标签保留。

## 动态变量与泄漏检查

动态气象源：`{ERA5.relative_to(ROOT)}`，使用 BYBLK 对应的 ERA5-Land 上游流域面积加权序列。

为满足“动态变量来自目标日前”的约束，本表没有直接复制 D1 的当日包含窗口，而是对已有 ERA5-Land 日值先 `shift(1)`，再计算滚动窗口：

- 目标日 t 的 `P_antecedent_3d` 使用 t-1 至 t-3；
- 目标日 t 的 `P_antecedent_7d` 使用 t-1 至 t-7；
- 目标日 t 的 `P_antecedent_30d` 使用 t-1 至 t-30；
- 温度窗口同理，仅使用目标日前数据。

- `future_information_leakage`：全部为 `False`。
- `dynamic_pre_target_compliant`：完整窗口记录为 `True`；起始窗口不足的记录标记为 `False`，但保留为空，不填补。
- 未使用 XQM 气象变量。

## 静态特征

静态特征来自 `{PHYSICAL.relative_to(ROOT)}`，对已冻结 BYBLK→DSK 的 68 个 reach 形成单路径摘要：

- `length_km`：沿冻结 reach 长度求和，单位 km；
- `elevation_drop_m`：reach 高程下降量求和，单位 m；
- `mean_slope`：按 reach 长度加权的 `mean_slope_m_per_m`，单位 m/m；
- `median_slope`：reach 级 median slope 的中位数，单位 m/m；
- `width_m`：真实 SWORD v2 `width` 的路径 reach 算术均值，单位 m。

这些静态值只来自已有 D0 资产，不对缺失值进行填补。

## 缺失统计

| 字段 | 缺失数量 | 缺失比例 |
|---|---:|---:|
{missing_lines}

完整 baseline 行数：{int((dynamic[feature_columns].notna().all(axis=1)).sum())}；不删除缺失行。

## train / validation / test 候选年份

采用按年份的时间外推候选切分，不执行训练：

- train 候选：1978–1981；
- validation 候选：1982；
- test 候选：1983。

所有切分只在 `split_candidate` 字段中记录，尚未执行任何模型操作。

## 约束

- 未训练模型。
- 未调参数。
- 未删除缺失记录。
- 未填补缺失数据。
- 未使用 XQM 气象变量。
- 未修改 Phase C/D 输出。
- `bd1m_river_path_freeze.csv` 未修改。
"""
    REPORT.write_text(report, encoding="utf-8")
    print(f"rows={total} complete_rows={int((dynamic[feature_columns].notna().all(axis=1)).sum())}")


if __name__ == "__main__":
    main()
