# VHS-NEXT-B1A｜标签盲受限读取验证

日期：2026-10-16（Asia/Singapore）。本阶段仅官方数据清点、元数据/拓扑和受限日期-QC扫描；没有真实训练、性能评分或GPU任务。


两个合成测试层均在真实Q读取前完成：通用缺失/QC输出不变性，以及真实YYYY/MM/DD/qobs/ckhs/qceq/qcol schema、逐年checked mask不变性。替换所有非缺失Q为数量级或符号完全不同字符串，输出完全一致；修改缺失token或QC可改变计数；未知schema/QC值拒绝。结果见blind_coverage_synthetic.json、actual_schema_synthetic.json。

实际程序scan_coverage.py仅读sealed_runoff中的882份日文件，日期转datetime，qobs只做字符串缺失比较，QC只读取代码；不执行float(qobs)、求和、均值、方差、最大、分位、相关、图或评分。输出29775行日期/QC覆盖计数及checked日期位掩码。签名表仅表头识别，签名数值和COSERO输出未解码；气象仅读表头。

零真实Q数值统计不等于零接触字节：下载、哈希、提取和受限解析均访问含Q文件；非缺失Q字符串只用于存在性测试，没有记录。交互工具未打印真实Q行；不把允许的checked/缺失比例当水文签名。

隔离级别：同Windows账户目录+程序政策，**不是OS访问隔离、沙箱账户或密码学封存**。完整archive仍含标签。未来模型开发前需冻结读取入口、权限/角色分离、日志与泄漏测试；本B1A程序性通过不能替代独立评分器部署。

输出机读表禁止Q数值列，station_metadata的coverage为ELIGIBILITY_ONLY；impact/QC既有字段可能源于目标Q，不能用于模型。B0历史汇总显示例外保留在冻结B0验证报告，本轮未重复该访问。
