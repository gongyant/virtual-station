# VHS-NEXT-S1A-R3｜气象强迫来源与准入

身份：RETROSPECTIVE_POST_EXPOSURE_EXPLORATORY_ANALYSIS。R3_DATA_GATE=PASS，仅限项目数值级探索，不是独立气象过程认证。

实际读取NetCDF：data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc，SHA256=b007596bb57c47a2f5237a99736f1389f03122760487297f5c7fd0da4b1500c2。实际2191个连续UTC午夜日期，1978-01-01至1983-12-31；precipitation_mm为日总降水mm day-1，temperature_c为24小时平均2m温度degC，均无非有限值。未凭文件名推断。

生成链：download_era5_land.py请求reanalysis-era5-land的tp与逐小时t2m；prepare_era5_land_daily.py将00UTC累计值移至前一日，tp×1000(m→mm)，t2m按UTC日取24小时均值后−273.15(K→°C)；area_weight_incremental_era5.py使用HydroBASINS拓扑及站点ID定义DSK上游集水区减BYBLK上游集水区，按EPSG:6933交叠面积加权。面积=11888.134690km²，175权重和为1。新独立重算已有日网格P/T与加权NetCDF的最大差为{'precipitation_mm': 1.687140311901203e-06, 'temperature_c': 9.4681502460503e-07}，符合float32保存精度；没有重新生成或写入气象文件。

指定生成器没有DSK观测Q输入或按Q调参/筛选路径；station nodes仅使用站号、HYBAS_ID和面积。上下游流域定义与S0/E4B0记录一致。原finalizer之后还有历史模型训练步骤，本轮仅阅读源码、不执行finalizer。旧D5有全时期目标参与特征选择污染，但不从D5选择结果/派生表读取特征；本轮P7/T7由当前用户固定，不宣称从未受历史Q观察启发。

差异明示：旧P_inc_7d=sum(P[t−7..t−1])；本轮P7=mean同七日，即旧数值/7；T7同旧7日均温。只从日P/T新建本轮固定平均特征，未改变窗口或旧表。各折1978-01-31起训练1066/1431/1796日，开发各365日。P/T与上游日键逐日一致，全部t−7..t−1窗口可用，无填补、删日或替代变量。

来源代码/数据与S0 source_manifest内已有SHA逐一核对，详见data_gate.json。历史原始85文件验证记录PASS仅作继承证据，没有重扫逐小时文件或全项目。强迫UTC日界为项目内部可核对约定；Q日界和实际供数时刻未正式认证，t−1仅为名义日期过去。ERA5再分析可能利用后验观测，不能视作实时可获取强迫。强迫独立于项目目标Q生成的结论限所查本地生成链，不等于已穷尽供应商全部同化来源。

合成窗口/同日扰动/秩/闰年检查通过。开发评分标签尚未由R3执行器打开；随后固定全部代码、配置、输入、环境和日期再拟合。数据、代码及历史哈希漂移/缺日/秩不足均立即停止，不自动修复。
