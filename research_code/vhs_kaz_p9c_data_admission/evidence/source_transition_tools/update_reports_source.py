from pathlib import Path
p=Path('.p9c_work/reports.py');s=p.read_text(encoding='utf-8')
replacements=[
 ("met=read(ROOT/'driver/LONG1964_1978_NUMERIC_VALIDATION.json')","met=read(ROOT/'driver/QALIGNED2000_2015_NUMERIC_VALIDATION.json')"),
 ('actual_target_complete_months=655','actual_target_complete_months=705'),('ACTUAL_180MONTHS_VALIDATED_EXPLORATORY','ACTUAL_Q_ALIGNED192MONTHS_VALIDATED_EXPLORATORY'),
 ("first_month='1964-01'","first_month='2000-01'"),("last_month='1978-12'","last_month='2015-12'"),('actual_complete_months=180','actual_complete_months=192'),('actual_complete_days=5479','actual_complete_days=5844'),
 ('TRUE1964-12availablefor1965-01;1964-01L1unsupported','TRUE2000-12availablefor2001-01;2000-01L1unsupported'),
 ('655个完整站月、40个完整站年','705个完整站月、57个完整站年'),('655完整站月/40数值完整站年','705完整站月/57数值完整站年'),
 ('1964–1978已有180月P/T','2000–2015已有192月P/T'),('180月真实ERA5-Land驱动','192月与Q年代对齐的真实ERA5-Land驱动'),
 ('训练1965–1972（96月）/评价1973–1977（60月）','训练2001–2011（131个完整月，2003-07缺8天不插补）/评价2012–2015（48月）'),
 ('两模型120预测','两模型96条有效预测'),('不得把本轮单站3%增益写成全国方法精度','不得把本轮单站气象对照写成全国方法精度'),
 ('76个有名数值列另有1匿名导出列，30001缺目录，不冒称77个正式站','76个具名Q列及漏表头的午夜时间字段，30001缺目录；末尾空表头吸收了这一偏移，不能把时间或末列另当一个站'),
 ('10014 SARYTOGAI 132完整月/10完整年；2314400 TALGAR 246月/9年；2314600 TEKELI 105月/8年；10195 Tauturgen172月/13年。共655站月/40站年','10014 SARYTOGAI 286完整月/23完整年；2314400 TALGAR 120月/10年；2314600 TEKELI 120月/10年；10195 Tauturgen179月/14年。共705站月/57站年'),
 ('官方CDS正常API凭据只在内存使用，未写入项目。1965试点1235135bytes通过后，同一14格点1964–1978档17929781bytes下载；官方MD5均通过。131,520源小时覆盖边界、5,479完整日/180月，4闰日。',
  '官方CDS正常API凭据只在内存使用，未写入项目。1965试点1235135bytes与1964–1978档17929781bytes是实际取得的历史气象，但不对应正确10195Q年代，保留不用于有效拟合。随后取得2000–2015档19121321bytes，官方MD5通过：140,280源小时、5,844完整日/192月、4闰日。两段合计372个唯一实际气象月，1965试点重叠不另加。'),
 ('1965年1月前月1964年12月真实存在，1964年1月前月缺口单列','2001年1月前月2000年12月真实存在，2000年1月前月缺口单列'),
 ('训练1965–1972各96月，评价1973–1977各60月，120预测','训练2001–2011各131个完整月，评价2012–2015各48月，共96条有效预测'),
 ('数值指标复核49通过/0失败','数值指标复核41通过/0失败'),('并非“准确率3%”','这不是百分比准确率'),
 ('绝对表现弱、总体高估约19%；不能把小增益称稳定普遍有效','总体高估约20%，且本例气象增强MSE退步；不能宣称气象增益'),
 ('先预测封存及49项独立复核','先预测封存及41项独立复核'),
 ('numeric_complete_station_months=655,numeric_complete_station_years=40','numeric_complete_station_months=705,numeric_complete_station_years=57'),
 ('actual_driver_months=180,raw_hourly_source=131520,full_days=5479','actual_driver_months=192,raw_hourly_source=140280,full_days=5844'),
 ('E2_prediction_records=120,E2_train_months_per_model=96,E2_test_months_per_model=60','E2_prediction_records=96,E2_train_months_per_model=131,E2_test_months_per_model=48'),
 ('real_known_gauge_predictions=120','real_known_gauge_predictions=96'),
 ('→aggregate_driver.py LONG1964_1978→prepare_e2_protocol.py','→aggregate_driver.py LONG1964_1978→纠正源time字段→QALIGNED2000_2015下载/聚合→prepare_e2_protocol.py')]
for old,new in replacements:
 if old not in s:raise RuntimeError('Missing report-source replacement: '+old[:90])
 s=s.replace(old,new)
marker=" event(stage='P9C_reports_complete'"
assert marker in s
extra='''
 erratum="""# 重要更正与有效版本

初次将CSV日期后的00.00时间字段误作第一站Q，导致整列错位；原655站月/40站年、120预测和旧分数全部撤回，不可引用。旧代码、缓存、参数与run及其SHA原样保留于evidence/rejected_column_alignment和exploratory_temporal_REJECTED_COLUMN_ALIGNMENT，状态INVALID_SOURCE_COLUMN_ALIGNMENT。

现统一按date+source_midnight_time+76站Q读取：31047个日期行第二字段均为00.00，末列有有效流量，原始字节不改。结构证据支持归一化，但仍待源方正式字段确认。有效数据为4站705完整站月/57数值完整站年；10195真实Q是2001–2015，2003-07缺8天，不插补。

有效E2在新分数前按覆盖冻结：最后4完整年2012–2015评价48月，此前2001–2011全部完整月训练131月；alpha100不变、不调参。2个有效模型96预测；错列2模型120预测明确作废。实际Ridge.fit总计2次、气候态估计总计2次，其中各1次属于作废尝试；不能把全部216记录合并成成果。旧1964–1978气象仍真实，但不用于有效拟合。有效结果不支持本例气象增益，保留负技能。

本轮最高是E2探索开发、带源字段/身份/日界/QC限制，不是P10、严格PUB、盲测或业务认证；新虚拟站预测数仍0。

"""
 for name in ['P9C_COMPLETION_REPORT_ZH.md','P9C_P10_READINESS.md','P9C_SCI_EVIDENCE_UPDATE.md','P9C_REPRODUCTION_GUIDE.md']:
  file=ROOT/name;file.write_text(erratum+file.read_text(encoding='utf-8'),encoding='utf-8')
 state=read(ROOT/'P9C_FINAL_STATUS.json');state.update(data_level='E2_EXPLORATORY_TEMPORAL_READY_SCHEMA_NORMALIZED_QC_LIMITED',source_schema_normalized=True,publisher_schema_confirmation=False,rejected_schema_models=2,rejected_schema_predictions=120,total_Ridge_fit_method_calls=2,total_climatology_estimates=2,other_actual_met_months=180,unique_actual_met_months=372)
 js(ROOT/'P9C_FINAL_STATUS.json',state)
 with (ROOT/'P9C_NCDC_AND_OFFICIAL_DATA_REQUEST_ZH.md').open('a',encoding='utf-8') as f:
  f.write('\\n世界银行字段核验草稿（未发送）：官方目录data@worldbank.org，询问0064229v2日CSV漏time表头/午夜00.00字段/末空表头、System.IO.MemoryStream尾串、30001缺目录、逐站机构QC和日界。当前按结构统一归一化，源方字段确认尚待；不将之伪装为正式认证。\\n')
'''
s=s.replace(marker,extra+marker)
p.write_text(s,encoding='utf-8')
import ast;ast.parse(s);print('Corrected report source updated; previous exact source archived')
