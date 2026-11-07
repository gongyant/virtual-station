# P6C来源与许可

LamaH-CE v1.0：Klingler, Schulz, Herrnegger (2021), DOI10.5281/zenodo.5153305 / 10.5194/essd-13-4529-2021，CC BY-SA4.0；合法独立快照、官方全上游流域、网格及原R处理代码从P6B只读复用，保留作者署名和直接移植代码适用的共享条件。

Copernicus Climate Change Service / ECMWF：ERA5-Land hourly time-series，DOI10.24381/ee82e357，CC-BY。官方目录https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land-timeseries?tab=overview 。16个紧凑矩形的实际请求、job ID、下载URL、版本响应、MD5/SHA256和原始NetCDF成员均在driver中。来源生成/下载为2026-11-02，历史时段2015–2020加真实2021边界；不隐瞒这是现行版本回取。仅获取P/T，不下载欧洲全变量包。CDS本机凭据仅内存使用，不在项目/日志/交付包保存。

Hydrographie Österreichs / BMLUK / Hydrographische Landesdienste：24站日均Abfluss归档及站点说明复用P6B合法eHYD来源，未重复下载Q。官方入口https://ehyd.gv.at/ ，https://wasser.gv.at/hydjb/index.xhtml 。原来源/下载/非商业署名使用限制见P6B/SOURCE_LICENSE_AND_DOWNLOADS.md及归档eHYD版权说明；没有将eHYD误标为CC-BY或允许无限商业再分发。原始Q保留在已有本地源，不批量复制到P6C输出。

所有对应原文件路径与哈希见P6C_ADMISSION_FROZEN.json、P6C_STATION_ADMISSION.csv。P4模型的正式来源、代码和参数哈希保留；无教师锡尔河数据，无跨数据集混用。
