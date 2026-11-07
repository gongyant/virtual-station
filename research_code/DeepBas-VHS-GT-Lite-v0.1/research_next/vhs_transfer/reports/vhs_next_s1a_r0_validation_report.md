# VHS-NEXT-S1A-R0 验证与准入报告

阶段仅方法修订、新代码与CPU人工合成信号。真实模型拟合/预测/开发评分、真实placebo、GPU与E5I1均未执行。用户中途确认继续完成R0，仍只运行CPU合成测试。

## 设计与代码验证

综合检查：PASS，21/21项文档/配置/代码/完整性门槛通过。原S0.1训练折、源hash与映射、完整支持、主两模型、窗口、决策规则、bootstrap规则及R1参考边界均逐字段比较一致；原文件字节未变。主公式另以独立展开式逐值核对。

机器记录：[r0_validation.json](../experiments/s1a/r0_validation.json)、[protocol_v2.json](../experiments/s1a/protocol_v2.json)。数值模块只导入NumPy/dataclasses，没有I/O/GPU/历史模型导入；真实适配器在R0先拒绝，再谈文件读取。此项静态检查不是对未来任意Python脚本的权限证明。

## CPU合成测试：22/22通过

Python 3.14.7，NumPy 2.5.3，无GPU。日志：[逐项日志](../experiments/s1a/synthetic_test_log.txt)、[完整数值记录](../experiments/s1a/synthetic_test_results.json)。合成信号明确标记ARTIFICIAL_CPU_SIGNALS_ONLY_NOT_OBSERVATIONS，没有保存为虚构观测或写入原数据目录。

覆盖：严格独立噪声无固定高增益；已知1日信号对齐检出；已知4日延迟在预定k=+3响应；打乱对应关系削弱；past-only不访问t/未来；负k只能非因果诊断；开发标签扰动预测不变；未来上游不改变train尺度/beta；所有k同train/dev支持；边界不环绕；使用源月份；bootstrap不跨年、配对与seed；固定F2与主模型隔离；共线指标不改beta；缺值/零尺度/错日停止；指标边界；真实数据入口提前拒绝；实践阈值与代价；共享平滑季节性反例；原主OLS公式一致；安慰剂汇总拒绝日期/角色不一致。

以下数字只属于预先固定的人工信号，绝非真实流量性能：6个独立噪声种子的开发相对RMSE增益范围为-0.548%至0.055%；已知1日联系k=0增益为81.675%，打乱后为0.069%。这些有限合成场景不估计普遍误报率，不保证实际数据必然检出或无假阳性。

特别反例：只有共享平滑季节、无日级联系时，月阶梯对照增益3.265%，固定F2对照增益-0.162%。这说明小幅主增益可来自残留日历信息，不能单凭2%或同步峰确认传播。保留原阈值而增加解释层检验，不能追溯换判定。

10000次/seed20261011/30与60日的配对bootstrap已在人工同预测对照上执行，增益CI为0；这验证同索引配对与规则，不是实际研究CI。非环绕块索引也检查在年内，原circular方法的年内首尾连接风险仍需披露。

## 泄漏与识别边界

已检查实现路径未发现开发标签进入主拟合/尺度/特征；负位移训练源没有越过该折截止，开发所有k同275日mask。API类型/配置不等于OS隔离；共享CSV拆分层、手工改配置、将own-past冒作上游以及观察结果后调整协议仍是可绕过路径。未来执行器须审查这些路径，并在打开开发评分标签前保存预测、config、code和环境hash；本轮没有真实执行器CLI，也没有打开真实目标值用于建模。

当前没有真实L1/L2结果。未来最多按实际主结果支持条件性L1，并按固定placebo模式讨论描述性L2；两站Q不能单独确认L3/L4。供数来源、单位/日均/日界/发布时间、MQ原生成和新独立盲测证据继续未解决。

## 历史保护

定向SHA-256核查130个已知历史及S0/S0.1文件，前后差异0；包括继承S0.1的107文件保护清单及新增保护的S0/S0.1交付文件。未重新扫描全部历史；S0的2398文件记录复用，大型图/模型未全量重哈希。哈希读取真实数据字节不解析流量值。E4/E5与论文、原S0.1协议和契约未改。

[前记录](../experiments/s1a/integrity_before.json)、[后记录](../experiments/s1a/integrity_after.json)。执行命令为项目.venv Python -B运行integrity_r0.py before/after、test_synthetic_v2.py、build_r0_artifacts.py、validate_r0.py；不安装依赖、不载入历史checkpoint、不重新执行S0/S0.1审计。

## 完成与执行审查

S1A_R0_READY_FOR_S1A_EXECUTION_REVIEW=true。其含义是方法补充及测试可提交执行审查，**不是自动批准真实S1A**。受限S1A仍CONDITIONAL，S1B/S1C仍BLOCKED。实际执行前需单独用户批准、冻结执行器及环境、在可信拆分层验证源hash/日期/角色和评分预测SHA；发现源漂移、缺值、rank或mask异常立即阻断。

本轮已按要求停止，未执行真实S1A或真实placebo评价。
