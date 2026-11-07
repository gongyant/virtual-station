# VHS-NEXT-S0｜数据来源清单与检查范围


审计日期：2026-10-11（Asia/Singapore）。阶段：Physics-Guided and Transferable Virtual Hydrological Station Reconstruction。
本轮仅执行文件读取、确定性来源/拓扑核对、CPU 合成单元测试与协议设计；没有真实流量拟合、参数搜索、真实模型预测重跑、GPU 任务或论文装配。
`AUDITED=true` 表示已完成本报告明确列出的检查，不表示来源独立性或零泄漏全部通过。`UNVERIFIED` 不自动转为 PASS。
所有相对路径均相对于项目根目录 `E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1`。


## 核心资产

1. **1978–1983 日流量**：`data/raw/runoff/BYBLK-DSK日数据.xlsx/Sheet1`，日期列 Q，BYBLK→00705600（巴音布鲁克）、DSK→00705700（大山口）。首个非日期行为 OQ 标记，作为说明行剔除，不是缺测插补。两站各2191日、1978-01-01至1983-12-31，无重复、无日历缺日、无 Q 缺值。两站4382个站日与 `timeseries.csv`、E0 数据集逐值差为0；基础NPZ的 obs_q/y 与原值转float32后完全一致。原始单位打印、水文日界、官方供数者和原始整编历史仍未核实；OQ只是文件内语义标记。
2. **2005 OQ/MQ**：`data/raw/runoff/Q-新疆.xls`；支流sheet index9（2005-支流），干流index11（2005-干流）。BYBLK/DSK各184日（2005-05-01..10-31），ALAR/XQM/AQK各300日（01-02..10-28），每站自身范围内无缺测。合并张量303日×5站×2字段，缺测期间保持NaN和可用性标志。五站所有已导入 OQ/MQ 值、日期行号与工作簿一致，最大差0；这证明复制链，不证明MQ生成链或观测独立性。
3. **外部月序列**：`data/raw/runoff/Q-dsk-byblk.xlsx/DSK` A列年月、B列候选流量，另有BYBLK/Sheet3。文件creator刘铁、2018-06-09创建，仅是文件属性。官方提供者、单位、观测/模拟身份和与日序列共同来源关系仍未核实。E4D仅允许称 external monthly-series consistency evaluation。
4. **ERA5-Land**：下载脚本 `scripts/download_era5_land.py` 的CDS dataset为reanalysis-era5-land；`prepare_era5_land_daily.py`做00 UTC累计量前移一天、m→mm、K→°C；之后 `area_weight_era5_land.py` 与 `area_weight_incremental_era5.py` 面积加权。已读取1978–1983上游流域与增量流域NetCDF的实际变量、单位、时间及非有限值；均2191日。E4B0五个t−1滚动字段确定性重算最大绝对差<5.01e−9，缺失掩码一致。没有重跑原始逐小时下载/完整网格加权流程，原始下载证据以本地原文件哈希及历史审计为限。再分析不是实时预报。
5. **河网**：`data/raw/hydrorivers/HydroRIVERS_v10_as.*`、`data/raw/hydrobasins/hybas_as_lev12_v1c.*`、站点KMZ及 `src/vhs/graph.py`。实际DBF重新读出68条HYRIV_ID/NEXT_DOWN/LENGTH_KM，67条链内边与原始指针吻合；长度212.61 km，末reach40282031的NEXT_DOWN=DSK匹配reach40282189。HydroBASINS几何和站点原始身份未全面复核，文件名/本地存在不能替代官方下载认证。
6. **地形/宽度**：本地 `data/raw/dem/FABDEM_BYBLK_DSK.tif` 与 `data/raw/sword_v2`，衍生 `channel_slope_final.csv`、`channel_width_final.csv`、物理特征表。历史报告提供DEM覆盖和SWORD最近几何匹配；本轮对相关资产做哈希并读取代码/报告，没有重新生成坡度或宽度。现代地形/宽度用于历史时期是静态近似，不能认作1978–1983同步观测。
7. **另一个参考流量**：基础bundle的wg_dis来自本地WaterGAP `dis` NetCDF最近站点采样；面积比lag3参考来自上游Q与UP_AREA；两者均不同于MQ导入字段，也不同于E4线性水库输出。WaterGAP外部率定是否含目标站信息本轮未核实。

## 源码和冻结证据

- 日流量配置：[configs/real_data.yaml:39](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/configs/real_data.yaml:39) (`- path: data/raw/runoff/BYBLK-DSK日数据.xlsx`)
- 导入规则：[scripts/prepare_timeseries.py:30](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/prepare_timeseries.py:30) (`flows = pd.concat(flow_frames, ignore_index=True).groupby(["date", "station_id"], as_index=False).obs_q.mean()`)
- MQ字段赋值：[scripts/extract_multisite_runoff_2005.py:180](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/extract_multisite_runoff_2005.py:180) (`"physical_reference_q_m3s": reference,`)
- E0目标映射：[scripts/build_bd1m_model_dataset_audit.py:40](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/scripts/build_bd1m_model_dataset_audit.py:40) (`dynamic["Q_target_dsk"] = q["00705700"].reindex(dynamic.date).to_numpy()`)
- E4/E5A冻结：[outputs/vhs_bd1m/experiments/e4b3_method_freeze.json](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/vhs_bd1m/experiments/e4b3_method_freeze.json)；[outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json](E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/outputs/vhs_bd1m/paper/e5a_reproducibility_manifest.json)。
- 已审查D5四轮分支，特别保留M1/M2拒绝与M2C开发评价的限制，避免重复造轮子。

## 可复核清单

`data_audit/source_manifest.json`含866个机器读取/索引资产的绝对路径、字节数、SHA-256；这不是声称逐篇人工精读866文件。`data_audit/code_evidence.txt`保存相关源码/报告匹配行及行号；深读范围在各专题报告明确引用。`live_audit_facts.json`记录全量逐值检查、日期范围、NetCDF元数据、边和原始DBF核验。`historical_before.json`还覆盖全部本地raw/processed以及scripts/src/configs/tests/reports/outputs的2398文件。
可确认本地加工链一致；不能由哈希确认第三方科学真实性。更早未被当前脚本保留的插补/整编过程标记UNVERIFIED。
