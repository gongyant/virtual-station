# 候选接入与复用
## 独立预览
.\start_preview.ps1（默认8791，仅127.0.0.1）；.\stop_preview.ps1只停止本目录记录的PID且校验进程启动时间，拒绝PID复用。
启动或停止不涉及8775，不初始化教师数据适配器，不访问sealed_runoff。
原站当前没有可连8775；本轮没有尝试启动它。

## API（均为真实已实现接口）
/api/public/catalog
/api/public/results?dataset=LAMAH_CE_PUBLIC_V1&kind=TEMPORAL_HOLDOUT&snapshot=<catalog给出的精确快照>&station=LAMAH_CE_PUBLIC_V1:2&model=P2-L1
/api/public/evaluation 使用同样作用域；FINAL_MODEL_APPLICATION禁止查询独立评分。
/api/public/spatial 使用同样作用域，date=2016-01；返回RFC7946 WGS84点GeoJSON，properties.coordinates_epsg3035用于现有投影画布。
/api/public/report?dataset=LAMAH_CE_PUBLIC_V1&id=license
/api/v6/public/results/station|evaluation|spatial|report为候选v0.6路由别名。
所有POST、/api/v6/model/execute、/api/vhs/predict仍403；无Qobs导出。
没有使用静态路径通配符或任意文件下载。

## 获准后接入已有v0.6的最小改动
在新的候选checkout中导入PublicResultsBridge与V06PublicResultsHook。正式宿主通过原可信权限检查提供display callback。
在server.py调用原PLAT.handle之前，对/api/v6/public/调用hook.handle；返回None才继续旧分发。
不要更改PlatformApi._ds默认值、LAMAHCE元数据授权、SYRDARYA适配器或原execute403。
将本候选static页面作为单独公开科研结果入口接入原静态白名单（或在已有view_results组件中消费该API），增加显式“公开科研快照”选择项。当前独立页面已经复用了原四层信息架构及四个结果子页名称，不依赖旧教师数据服务。
该描述不是已部署证明；生产权限未获准，原站文件完全未改。候选钩子本身有默认拒绝测试。

## P6复用
沿用PUBLIC_RESULTS_SCHEMA、逐预测provenance与PredictionKey，P4-V2模型参数与模型发布ID保持不变。
P6新输入/标签必须注册新的source_snapshot_id、source_run_id及evaluation_run_id，不能向旧V1快照追加2018数据。
新增显式model_training_snapshot_id、meteorology_snapshot_id、evaluation_label_snapshot_id；用经过核验的运行外键关联新评价源和旧模型训练源，不能强行要求它们相同。
当前R1每prediction_kind只有一个历史run，因此P6接入时将API选择器扩展为kind+run_id，并按完整源/发布/站点键过滤，勿仅用kind或LAMAHCE名称覆盖历史。
预测文件先封存再连接新Q评分；导入冻结指标，不在桥接层重新评分或训练。外部新数据仍需其真实许可和身份/气象版本核验。
