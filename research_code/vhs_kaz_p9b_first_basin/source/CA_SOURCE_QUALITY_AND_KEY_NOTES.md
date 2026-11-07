# CA-discharge源契约实查

下载24,576,000字节GPKG的官方MD5匹配e0ba6664aaec3e0b27138abdfd4ba263，Zenodo v1.0明示CC-BY4.0。实际297gauges/295唯一站点、136个time-series CODE/134个规范化地点，244632行。网页称135个时序地点与本文件实际计数仍有差异，原因未确认，不把说明数当实际抽取数。

gauges.CODE对16070、17050各重复两行，分辨率不同；时序CODE用16070d(day)/16070m(decade)、17050d(decade)/17050m(month)。必须以原站CODE+res解析到时序CODE，不能简单rawCODE直接连接或无条件删除后缀。全部本国6站及唯一16390时序不受这个别名问题影响。

16390有492条1980-2020月记录，单位m³/s已由数据论文Discharge time series章节核实，均有限非负且年月唯一。但源qual_duplicates=0及qual_wb=0要求复查，不等于本轮发现每条观测都是假的；qual_consistency=0表示统计持久性，qual_order=0不适用，qual_regime为分类，不是所有0都失败或所有1都业务认证。源曾对孤立单点缺口插补而未给逐条原始/插补标记，不把492条全部称作未经处理的原始逐日观测。

六个KAZ点都在Arys，首流域0点/0时序。其492个月不用于替换巴尔喀什—阿拉湖目标样本。原始文件使用SQLite immutable=1/GDAL IMMUTABLE=YES，只读并保留原MD5；不修改WAL头或源表。两个冰川变薄字段按发布者警告排除，不用于特征。
