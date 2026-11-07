# 真实公开数据来源、许可与署名

实验统一标记 PUBLIC_DATA_REAL_EXPERIMENT；绝不标记SYRDARYA_REAL_EXPERIMENT。独立下载，不读取原工程sealed_runoff或教师Q。

- 官方数据集：[LamaH-CE v1.0](https://zenodo.org/records/5153305)，DOI 10.5281/zenodo.5153305。
- 数据集署名：Klingler, Christoph; Kratzert, Frederik; Schulz, Karsten; Herrnegger, Mathew (2021), LamaH-CE, version1.0。
- 数据论文：Klingler, C., Schulz, K., and Herrnegger, M. (2021), Earth System Science Data13,4529–4565，[DOI10.5194/essd-13-4529-2021](https://doi.org/10.5194/essd-13-4529-2021)。
- 实际文件：2_LamaH-CE_daily.tar.gz，1,477,248,617 bytes；只下载日尺度包，未下载14.8GB小时包。
- 官方公布MD5：69fd2733e969513403f923ecc5eaa3dc；本次下载实算匹配。
- 本次实算SHA256：b692afc817fc7d92c003b3203fa04def9bbc04c3db39fa58b94c37f8d5376dd0。
- 气象使用 A_basins_total_upstrm/2_timeseries/daily/ID_*.csv 的ERA5-Land全上游流域加权平均；Q使用D_gauges/2_timeseries/daily/ID_*.csv的水文部门观测，**没有使用F_hydrol_model模拟输出**。
- 所选ID2/6/9均为AUT，原始水文来源按Info归属HZB (2020)；ERA5-Land引用Muñoz Sabater (2019a)/Muñoz Sabater et al. (2021)，完整官方要求的附加来源保留在ATTRIBUTION_ORIGINAL.txt。

## 许可差异如实保留

官网描述为CC BY-SA4.0；本次API metadata和包内Info_english/4_Creative_commons_license_4.txt为CC BY4.0。三份原始证据均已保存，没有宣称完全一致或只选宽松版本。两者均允许带署名的本地研究和改编；本实验对派生月数据、结果、图表遵循更严格的CC BY-SA4.0条件，注明来源、版本和修改，并附同许可链接。尚未对外发布，也未取得任何教师数据许可。不是向外部机构发出的法律认证。

许可：[CC BY-SA4.0](https://creativecommons.org/licenses/by-sa/4.0/)。保留免责声明和原参考文献，不将研究输出用于运行性预警。

## 修改与时间/单位定义

只在新目录中把完整UTC日序列聚合为完整自然月，筛选固定实验年；不填缺、不平移月份、不根据成绩改值。Q为日平均的月平均，m³/s；prec为日累计降水的月累计，mm/月；2m_temp_mean为日平均气温的月平均，°C，源数据已为°C，未错误减273.15。

Info明确所有时间序列UTC无夏令时；论文4.1说明AUT等国日Q与气象按00:00–23:59UTC汇总。本实验只用原生日尺度，无小时包。源方LamaH在日汇总前可能线性填补不超过6小时的小缺口；所以这是水文部门观测经公开数据集处理后的日Q，不声称每个原始小时都无处理。本实验没有新增插值。

ckhs=1为水文部门已检查，不等于所有误差已消失。qceq/qcol分别为重复值和离群诊断，原规则仅统计不自动删除，避免把合法极端值或真实恒流当作错误；ID2/6/9在16个联合年份分别有0/51/0个qceq日和1/0/0个qcol日。本结论以此公开QC规则为条件。

源API JSON、官网HTML、论文HTML、原Info八文件、TableA1/A2截图和下载哈希均在source保存，来源URL见ACQUISITION.json。初次尝试论文外置supplement.pdf得到404，实际使用包内官方Info文本完成核实，没有制造补充材料。
