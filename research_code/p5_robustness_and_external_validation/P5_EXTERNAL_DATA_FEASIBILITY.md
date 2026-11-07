# 外部资料可行性
当前只取得新目录元数据，未取得独立数值Q或匹配的2018年后ERA5-Land流域驱动。本轮不生成外部冻结/评分文件。
从[EStreams v1.4官方记录](https://zenodo.org/records/17598150)取得约2.86MB README、许可附录及测站目录，官方MD5及本地SHA256均核验，未下载Q或大气象包。
27站全部按官方编号、国别匹配，并将LamaH EPSG3035转换至WGS84核对位置与官方上游面积；最大距离0.543km、面积差≤5%。这是强元数据身份，不自动授权拼接新Q。
24站AT_EHYD目录终点2021-12-31，许可字段“-”；[eHYD官方说明](https://ehyd.gv.at/assets/eHYD/pdf/eHYD_Allgemein.pdf)存在使用与再分发条件，不能套用其它OGD站的一般CC许可。
1站CH_CAMELS终点2020-12-31，目录CC-BY-4.0；[Swiss官方数据服务](https://www.bafu.admin.ch/en/hydrological-data-service-for-watercourses-and-lakes)需进一步核对所取得实际版本与日值/QC。
2站DE_BY终点2023-08-19、目录Redistribution allowed；[Stegen官方站页](https://m.hnd.bayern.de/pegel.php?pgnr=16602303)可核对编号，但即时水位/瞬时Q不等于多年日均Q。
新Q单位、日/月聚合定义、时区、QC、缺失码仍NOT_VERIFIED_AT_NUMERIC_SOURCE。目录终点不是本地实得Q。
EStreams v1.4采用E-OBS0.1°，P4采用LamaH ERA5-Land流域聚合，不能直接换驱动后宣称纯时间验证。没有取得同几何/生产方式的2018年后驱动。
[Caravan原始论文](https://www.nature.com/articles/s41597-023-01975-w)包含479个LamaH流域，因此重复下载不成为独立Q；[官方代码库](https://github.com/kratzert/Caravan)也要求核对来源许可与时间基准。MultiMet不自动延长观测Q。
下一步优先小规模核验同站后2017日Q及匹配ERA5-Land驱动，再在未评分前冻结；若换全新站并用其历史Q校准，属于新流域重复，不是零目标Q泛化。
