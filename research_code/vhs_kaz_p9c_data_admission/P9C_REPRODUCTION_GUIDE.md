# 重要更正与有效版本

初次将CSV日期后的00.00时间字段误作第一站Q，导致整列错位；原655站月/40站年、120预测和旧分数全部撤回，不可引用。旧代码、缓存、参数与run及其SHA原样保留于evidence/rejected_column_alignment和exploratory_temporal_REJECTED_COLUMN_ALIGNMENT，状态INVALID_SOURCE_COLUMN_ALIGNMENT。

现统一按date+source_midnight_time+76站Q读取：31047个日期行第二字段均为00.00，末列有有效流量，原始字节不改。结构证据支持归一化，但仍待源方正式字段确认。有效数据为4站705完整站月/57数值完整站年；10195真实Q是2001–2015，2003-07缺8天，不插补。

有效E2在新分数前按覆盖冻结：最后4完整年2012–2015评价48月，此前2001–2011全部完整月训练131月；alpha100不变、不调参。2个有效模型96预测；错列2模型120预测明确作废。实际Ridge.fit总计2次、气候态估计总计2次，其中各1次属于作废尝试；不能把全部216记录合并成成果。旧1964–1978气象仍真实，但不用于有效拟合。有效结果不支持本例气象增益，保留负技能。

本轮最高是E2探索开发、带源字段/身份/日界/QC限制，不是P10、严格PUB、盲测或业务认证；新虚拟站预测数仍0。

# 复现与交付映射

原环境 `E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe`，Python -B -X utf8；仅官方PDF的只读解析使用现有bundled pypdf，未安装依赖。源目录有原文件、SHA256及官方下载记录；P9B/P8不被覆盖。所有新脚本在code。

只读验证（不重新下载、拟合、评分或修改封存）：
```powershell
& 'E:/CodexProject/CodexProject/DeepBas-VHS-GT-Lite-v0.1/.venv/Scripts/python.exe' -B -X utf8 'E:/VHS_Public_Baseline_Lab/vhs_kaz_p9c_data_admission/code/verify_delivery.py'
```

实际依赖顺序：acquire.py→wb_discover.py/wb_fetch.py→download_resources.py→q_admission.py；extract_report.py使用bundledPython；hydro_sources.py→hydro_tiles.py→download_rasters.py→catchment.py→weights_repair.py（本轮初版修复，未来新目录的已修正catchment.py不需此修复）→cds_driver.py submit/poll PILOT1965→aggregate_driver.py PILOT1965→cds_driver.py submit/poll LONG1964_1978→aggregate_driver.py LONG1964_1978→纠正源time字段→QALIGNED2000_2015下载/聚合→prepare_e2_protocol.py（实际已在评分前冻结）→e2_prepare.py→e2_predict.py→e2_score.py→auxiliary.py/reports.py→verify_science.py→seal.py。执行时间与失败恢复见RUN_ATTEMPTS.jsonl，不建议在旧目录顺序盲重跑。

新计算必须设置VHS_P9C_OUTPUT到同一公开根目录下新的独立目录，复制已获合法来源及哈希、保留协议，再有意重算；不应原地改封存。CDS凭据仅从用户本地标准配置在内存读取，项目无私钥/口令；没有权限会保留拒绝，不绕过或伪造授权。世界银行API预览返回HTTP200但资源无效，真实Q来自官方页面嵌入元数据的明确CSV下载链接；不是猜测受限API。

关键文件：P9C_NEW_Q_SOURCE_RESULTS是来源及取得状态；P9C_GAUGE_Q_ADMISSION区分数值完整/描述性/E2/P10；P9C_MONTHLY_Q_QC保留所有4站年月和缺失状态；crosswalk保留冲突与备选对应，49原点状态见data/P9C_EXISTING49_LINK_STATUS.csv；catchment CSV+GIS为新点位与旧代理分级；driver结果及driver/真实日月CSV为ERA5实际数值，不是代理权重。SourceNames、CODE与跨境身份未认证的不强行合并。

exploratory_temporal/run为唯一新拟合产物：MODEL_PARAMETERS、E2_PREDICTIONS、逐年/总体E2_TEMPORAL_METRICS、角色审计、先预测封存及41项独立复核和单独SHA。评分标签与预测输入在不同cache文件；P9C整体和单站run分别封存。没有重新运行P0–P7或P10。

所有历史SHA检验为只读，源表错误和初版失败并未当作通过。NCDC文件、其他3站驱动、正式8站PUB、未来盲测、现场精确边界和全国虚拟站预测仍NOT_AVAILABLE。
