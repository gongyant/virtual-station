# WEB-S1原v0.6候选科研证据集成

已运行地址：http://127.0.0.1:8794/#/results/research?dataset=LAMAH_CE_PUBLIC_V1&station=LAMAH_CE_PUBLIC_V1:171&researchPeriod=2020&start=2020-01&end=2020-12

以R2U1/host为起点，仅复制代码、static、research代码和必要manifest；不复制teacher/research_ready或旧日志。保留原首页、六层导航、共享站点/模型/年月状态及数据集切换token缓存保护。不是8791另做独立首页。

已接通：原27站54模型，V1原25站899站月及1798预测；P5 648条应用仍归原类别；新研究页可选择P6B 2018–19（24站576站月）、P6C 2020（24站288站月）、P6D 36月合并后验诊断（864站月/1728预测），不把重复展示计作新观测。P6模型均绑定原P4-V2 release/snapshot和P6来源文件哈希；V1仍使用P4-V1，不合并元数据快照。新派生证据snapshot在contract中标明精确父来源。

每站曲线、绝对NSE/KGE和增量技能、前1/前3月损失占比、季节、原经验区间、特征可加贡献、输入支持及P6原报告均真实可读。默认不返回Qobs，当前用户授权的受控本地单站视图可显式显示公开Qobs；无批量导出接口，format/export/download被403拒绝。缺少该24站共同外部支持的611/688/818显示NOT_EVALUATED，不填零；818单站历史并未伪称不存在。

原空间点图、V1评分、许可与模型文件仍保留；右侧P6状态已对24站更新，业务认证仍NOT_CERTIFIED，REACH_PREDICTION_NOT_AVAILABLE不变。P7单列研究页，SL失败保留，MEM仅达到训练期候选门槛；P7协议/模型注册来源与P4来源分离，默认仍P2-L1。

权限：仅用户要求的本地候选展示；生产display permission=NOT_GRANTED，动态执行/公开production hook/教师预测仍403。启动器拒绝教师source mount，旧权限文件未改。未伪造签名、审批者或verified callback。

接口与身份验收2654项、实际浏览器13项通过。54个原模型JSON哈希和npz数组合法加载；P6三时期逐月预测、分解和指标逐项对源，未在网页重评分或fit。截图和AX记录在evidence/browser。验收中发现并修复combined-period下划线解析、P7旧来源侧栏；载入中检查保留为中间观察，最终就绪状态验证通过。

历史保护2222文件全部一致。无生产部署许可，原网站目录及8775/8791/8792/8793未改；仅管理本轮8794候选PID。仍不可用：真正河段传播预测、业务风险认证、新独立P7确认集、教师Q及在线模型执行。软件验收不等于水文科学验证。
