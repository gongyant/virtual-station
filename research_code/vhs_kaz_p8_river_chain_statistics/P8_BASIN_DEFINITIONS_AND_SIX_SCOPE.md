# 八流域与六子集定义

完整8组为Aral-Syr Darya、Balkhash-Alakol、Ertis、Yesil、Zhaiyk-Caspian、Nura-Sarysu、Tobyl-Torgai、Shu-Talas。边界是Yapiyev等发布的研究数据v2，DOI10.5281/zenodo.17077776，CC BY4.0，8个EPSG4326有效多边形，不冒充政府法定测绘。

本轮六子集：Shu-Talas、Tobyl-Torgai、Ertis、Balkhash-Alakol、Yesil、Zhaiyk-Caspian。来源为2025-10-03 Kazinform报道当时数字平台已覆盖的六流域，不能推定为导师正式六水系定义；Aral-Syr Darya与Nura-Sarysu独立保留。历史新闻不表示2026年现状仍只覆盖六区。

研究数据源id与QazSu系统basin_id不是同一命名空间，例如Ertis为研究id3、QazSu id7。`BASIN_SCOPE_CROSSWALK.csv`按名称核验两套编号，并将尚未核实的全国统一官方代码留空。

`ORD_CLAS`沿用全球原值：1为每个连接河网的源至汇主干，2汇入1，3汇入2；包括许多内流小网络的主干，不是国家行政河流等级，也不是按河宽排序。`ORD_STRA`1为源头小溪、同级汇合才升一级；`ORD_FLOW`原值保留但不参加导师三级分类。境外上游等级不因裁剪而重新计算。

河链总长定义为各唯一HYRIV_ID裁剪几何的各片段测地长度之和，不把每条支流到出口的公共路径重复累加。等级4+和未分类独立列出。

六水系后续可配置：编辑新的JSON并调用`code/derive_six_scope.py --config <新JSON> --output <P8内新CSV>`，必须6个不同且已存在的名称，拒绝覆盖；不修改任何八流域片段与原统计。当前配置实测与六子集主表一致。
