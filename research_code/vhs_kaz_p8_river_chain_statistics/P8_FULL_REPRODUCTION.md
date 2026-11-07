# P8复核、命令与文件映射

解释器：`E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`；交付根：`E:\VHS_Public_Baseline_Lab\vhs_kaz_p8_river_chain_statistics`。不安装新依赖，不读教师Q，不改任何网站。环境、磁盘和初始历史检查见evidence/DISCOVERY.json。

本轮实际入口：acquire.py→freeze.py→river_statistics.py→gauges_candidates.py→verify.py→figures.py；独立source_discovery.py与source_audit.py读取正常公开页面/公开WFS及官方Q入口；sourceID/boundary检查在scope_and_boundary.py；图面发现国家要素遗漏后，boundary_v2.py保留初版、修正同源主权边界并冻结V2，再按原GIS和匹配规则重算。所有入口调用格式为`& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p8_river_chain_statistics/code/<entry>.py'`，RUN_ATTEMPTS.jsonl记录真实阶段和失败、更正，不捏造下载或评分。

主源：Zenodo17077776/ver.2.zip，官方MD5及ZIP CRC验证；HydroRIVERS官方全球ZIP全部成员CRC/路径配额检查。source/ACCESS_LOG和FETCH_*含实际HTTP、时间、字节及SHA256。主权国界来源为旧N1合法NaturalEarth全球快照的KAZ+KAB；原N1不改。P8国家边界与协议SHA在evidence/COUNTRY_BOUNDARY_AMENDMENT.json和PROTOCOL_FREEZE.json。

GPkg层：national_reaches（唯一来源ID的国内几何及原属性）、basin_fragments（切分片段ID、来源HYRIV_ID、序级、流域、测地长度）、basins_source、country_boundary。SOURCE_REACH_LENGTH_KM保留原整段长度，length_km为裁剪后重算值，后者是唯一统计分母。不要用原长度按国家比例猜测裁剪长度。生产脚本不能覆盖已有主GPkg/跨表；正式封存后勿直接重跑会写QA的verify.py，应先复制输出到新工作根。

封存后只读检验：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p8_river_chain_statistics/code/verify_delivery.py'
```

该入口只比较当前SHA256和2741历史清单，无网络/拟合/评分。字节清单包含原始下载、解包数据、GeoPackage、所有代码、图和报告，操作日志runtime除外。完整GPKG不含任何新Q观测列。

配置其他六水系：新JSON需有basin_names（6个不同且存在的英文名称）。

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p8_river_chain_statistics/code/derive_six_scope.py' --config '<新配置JSON>' --output 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p8_river_chain_statistics/P8_CUSTOM_SIX.csv'
```

输出必须在P8且不存在；八流域数据不变。默认配置已真实调用并和原六子集表相等。

核验独立性：verify.py不导入生产长度函数，单独持久化几何重算并独立逐段Vincenty反算1035个样本；包含全球唯一ID、三大来源区、分级和全网长度守恒、密度算式、虚拟准入0、未对齐官方密度N/A及历史hash。图的显示简化150m不用于长度计算；原始几何在GPKG。

文件：P8_RIVER_LENGTH_BY_BASIN_ORDER.csv和P8_CLASSICAL_VS_STRAHLER.csv均为明确标order_system的长表，后者保留全等级平行对照；P8_EIGHT_BASIN_SUMMARY/SIX_BASIN_SUMMARY为宽表；P8_OFFICIAL_GAUGE_CROSSWALK含334原始身份和匹配状态；P8_REAL_GAUGE_DENSITY将临时子集与完整官方N/A字段分开；KAZ_P8_Q_SOURCE_AUDIT.csv是P8_Q_SOURCE_AUDIT.csv的相同内容别名；图在figures，有脚本和source契约；P8_FINAL_STATUS逐项门槛不全设PASS。
