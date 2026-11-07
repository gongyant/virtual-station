# VHS-NEXT-B1A｜归档与安全分类

日期：2026-10-16（Asia/Singapore）。本阶段仅官方数据清点、元数据/拓扑和受限日期-QC扫描；没有真实训练、性能评分或GPU任务。


实际完整成员4356项，其中4312普通文件、44目录，总展开5,169,337,364字节（约5.17GB）。最大成员141,356,400字节；各成员≤256MiB，总大小≤12GiB，数量≤100000，实际解包前余量充足。路径/特殊类型/链接/大小写重复/父子冲突检查无拒绝项；仅去除显式开头`./`，不放行内部`..`。

拒绝路径穿越、绝对盘符、ADS、控制字符、Windows保留名和尾随点空格、软/硬链接及特殊类型；resolve必须留在分类根下，所有输出用xb独占创建，未调用extractall、未覆盖旧资产。实际展开和磁盘配额检查通过；所有缓存/临时文件在E盘。清单见evidence/archive_members.csv，提取SHA-256见extraction_manifest.csv。

分类后的实际文件数：{"STATIC_ADMISSIBLE_PENDING_FIELD_REVIEW": 3, "TOPOLOGY": 23, "LABEL_DERIVED": 3, "FORCING": 2172, "GEOMETRY_PENDING_FIELD_REVIEW": 36, "ELIGIBILITY_ONLY": 12, "SEALED_Q_DATA": 1112, "MODEL_OUTPUT": 887, "UNKNOWN": 56, "DOCUMENTATION": 8}。

其中SEALED_Q_DATA的1112文件包括882份日径流和230份插补前缺口日期文件；不等于1112站。FORCING最终为2172份A/B/C日气象CSV；一个路径初分为FORCING的附录R源码已改为UNKNOWN并移入quarantine，未执行。修订后的分类见extraction_summary.json及correction_log.json，初始清单仍保留。MODEL_OUTPUT的887文件是整个F_hydrol_model隔离资产，包含输入、率定结果和输出，不称887条观测。

RiverATLAS是含丰富属性的混合容器，只读取HYRIV_ID/NEXT_DOWN/MAIN_RIV/LENGTH_KM/UPLAND_SKM以及选择性的几何；其余字段默认UNKNOWN，不把整张表当输入。A5、A10整表隔离，字典仅查看表头。UNKNOWN文件只复制/哈希，不执行其代码或用作输入。外部R/Python源码仅读指定QC说明；没有执行原作者处理/率定程序。

目录隔离仅同账户程序策略；sealed_runoff并非密码学封存。完整archive也含Q字节，未来开发者不得任意绕过受限程序读取它。
