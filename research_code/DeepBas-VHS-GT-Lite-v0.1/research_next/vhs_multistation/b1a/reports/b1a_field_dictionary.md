# VHS-NEXT-B1A｜实际字段与白黑名单

日期：2026-10-16（Asia/Singapore）。本阶段仅官方数据清点、元数据/拓扑和受限日期-QC扫描；没有真实训练、性能评分或GPU任务。


机器字典field_dictionary.csv含584个来源字段条目，不只按字段名猜测。来源按论文及实际目录记录：A1站点/层级，A2气象，A3地形，A4气候，A6地类，A7植被，A8土壤，A9地质。公开静态属性仍须在B2冻结适用时间与单位，不因这份白名单自动进入训练。

- 实际层级字段：ID、HIERARCHY、NEXTUPID、NEXTDOWNID；NEXTUPID为逗号分隔多上游，0为空，不把字符串当单个站。
- Gauge_attributes实际包含govnr/name/river、area_gov/area_ratio、nrs_euhyd/nrs_rivat和degimpact/typimpact/diur_art/diur_glac。area_calc在A/B/C Catchment_attributes；不是猜测替代字段。
- CSV名为lon/lat的两列实际是EPSG:3035米坐标，与Gauges.shp逐点一致；station_metadata明确coordinate_crs，另列转换后的WGS84经纬度。禁止直接把原字段当度数。
- 日径流真实表头为YYYY;MM;DD;qobs;ckhs;qceq;qcol。qobs仅用于识别缺失token；ckhs/qceq/qcol为ELIGIBILITY_ONLY。ckhs=1的语义经官方源码的checked/ja/validierte映射核实，未执行该源码。
- **整表黑名单**：Table A5的两个Hydro_indices文件、Table A10的Water_balance.csv、整个F_hydrol_model。即使A10含气象字段也不从目标Q依赖表中偷选“看起来合法”的列。
- degimpact/typimpact/diur_art/diur_glac可能依赖人工过程线判断，限预设资格/敏感性，不作无资料模型特征。qceq/qcol本身也是已由Q计算的标记，允许本轮统计其现成代码，禁止将其作为预测输入。
- RiverATLAS未知丰富属性不默认合法；流量相关列未读取数值。UNKNOWN全部拒绝未来输入。
- Crossbasin_water_transfers的ID、To_ID只用于依赖合并；model/estimated标记不作真值认证，阈值不作为目标Q输入。

气象2172文件均核对实际表头，未读数值或扫描全日期；实际逐站可用时刻、气象QA和单位完整字典尚待协议冻结。允许回顾性重建与实时预测须分轨，归档UTC日期不等于发布时刻。
