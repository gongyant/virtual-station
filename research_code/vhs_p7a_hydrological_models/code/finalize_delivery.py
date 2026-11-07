"""One-time P7A + WEB-S1 scientific delivery seals; operational logs excluded explicitly."""
from common import *
import collections,shutil
def main():
 for root in [ROOT,WEB]:assert not (root/'SHA256SUMS.txt').exists(),'Already sealed; use read-only verify_delivery.py'
 history=readj(ROOT/'evidence/HISTORY_BEFORE.json');check=verify_history(history);assert not check['failed'],check['failed'][:3]
 for root in [ROOT,WEB]:put(root/'evidence/HISTORY_FINAL_CHECK.json',check)
 indep=readj(ROOT/'evidence/INDEPENDENT_NUMERICAL_VERIFICATION.json');extra=readj(ROOT/'evidence/ADDITIONAL_INDEPENDENT_VERIFICATION.json');unit=readj(ROOT/'P7A_UNIT_TEST_RESULTS.json');entry=readj(ROOT/'evidence/SAVED_PREDICTION_ENTRY_TESTS.json');web=readj(WEB/'WEB_S1_ACCEPTANCE.json');browser=readj(WEB/'evidence/BROWSER_ACCEPTANCE.json')
 assert not any(v['failed'] for v in [indep,extra,unit,entry,web,browser])
 # Calendar-driver identity check across the frozen exposed period, no fitting/selection.
 w={int(g):{} for g in GAUGES}
 for r in rows(P4/'source/weather.csv'):
  g=int(r['gauge_id'])
  if g in w and r['date']<='2017-12' and r['P']:w[g][r['date']]=float(r['P'])
 de=rows(LAB/'vhs_p6d_failure_diagnostics/P6D_PREDICTION_DECOMPOSITION.csv')
 for r in de:
  if r['model_id']=='P2-L1':w[int(r['gauge_id'])][r['date']]=float(r['P_raw'])
 lag_checks=[]
 for r in de:
  if r['model_id']!='P2-L1':continue
  g=int(r['gauge_id']);delta=abs(w[g][prev(r['date'])]-float(r['lag_P_raw']));ok=delta<1e-8 and prev(r['date'])==r['lag_date'];assert ok,(g,r['date'],delta)
  lag_checks.append({'gauge_id':g,'date':r['date'],'lag_date':r['lag_date'],'absolute_P_difference_mm':delta,'passed':ok})
 csvout(ROOT/'evidence/HISTORICAL_CALENDAR_LAG_VERIFICATION.csv',lag_checks)
 fits=rows(ROOT/'evidence/FIT_CALLS.csv');cost=[]
 for m in MODELS:
  rr=[r for r in fits if r['model_id']==m and r['level']=='outer'];elapsed=[float(r['elapsed_s']) for r in rr]
  cost.append({'model_id':m,'outer_fits':len(rr),'meteorological_beta_n':{'C0':0,'C0+PT':2,'P2-L1':3,'P7-SL':4,'P7-MEM':3}[m],'unpenalized_month_means':12,'rho_candidates':3 if m=='P7-MEM' else 0,'inner_fits_per_outer':45 if m=='P7-MEM' else 0 if m=='C0' else 15,'outer_fit_predict_median_ms':float(np.median(elapsed))*1000,'outer_fit_predict_total_s':sum(elapsed),'timing_caveat':'CPU fit+predict only, not total tuning/I-O wall time; no inference service benchmark'})
 csvout(ROOT/'P7A_MODEL_COMPLEXITY_AND_COST.csv',cost)
 registry=readj(ROOT/'P7A_MODEL_REGISTRY.json');counter=collections.Counter((r['model_id'],r['alpha'],r['rho']) for r in registry['research_models']);rho_half=[r['gauge_id'] for r in registry['research_models'] if r['model_id']=='P7-MEM' and r['rho']==.5]
 put(ROOT/'P7A_MODEL_CONTRACT.json',{'experiment_spec_version':'PUBLIC_P7A_CANDIDATE_1','solver_source':'immutable P2 MonthlyWeatherRidge fixed-alpha AUGMENTED_SVD','serialization_version_note':'Existing version field PUBLIC_P2_MONTHLY_RIDGE_1 identifies reused solver serialization; new model_id plus this P7A spec/protocol identifies SL and MEM formula. No old artifact edited.','fields':{'C0':[],'C0+PT':['P','T'],'P2-L1':['P','T','L1'],'P7-SL':['P','T','L1','COLD_L1'],'P7-MEM':['P','T','MEM']},'cold_interaction':'month-wise standardized COLD_L1 exactly equals I_cold*z(L1); warm months zero, synthetic proof saved','memory':'feature at t is state at end of previous actual calendar month; continuous external weather; 24 prior months required; never updated using Q','predict_entry':'code/predict_saved.py:predict_weather(model, weather, dates, units=...)','predict_signature_has_Q':False,'intervals':'NO_P7_INTERVAL_RECALIBRATION_OR_NEW_COVERAGE_CLAIM','final_parameter_counts':[{'model_id':m,'alpha':a,'rho':rho,'station_n':n} for (m,a,rho),n in counter.items()],'model_registry_sha256':sha(ROOT/'P7A_MODEL_REGISTRY.json')})
 status=readj(ROOT/'P7A_FINAL_STATUS.json');status.update(status='COMPLETED_DEVELOPMENT_AND_EXPOSED_DESCRIPTION_NOT_FINAL_INDEPENDENT_VALIDATION',delivery_utc=utc(),cv_train_max_date='2015-12',final_train_max_date='2017-12',training_future_Q_reads=0,future_Q_reads_field_scope='TRAINING_AND_SELECTION_ONLY; independent scoring legitimately used exposed2018-2020Q',independent_numeric_checks=indep['passed']+extra['passed'],calendar_lag_checks=len(lag_checks),unit_and_saved_entry_checks=unit['passed']+entry['passed'],historical_files_unchanged=check['passed'],web_api_checks=web['passed'],web_browser_checks=browser['passed'],all_checks_failed=0,code_sha256={p.name:sha(p) for p in (ROOT/'code').glob('*.py')})
 put(ROOT/'P7A_FINAL_STATUS.json',status);put(WEB/'research/P7A_SUMMARY.json',status)
 contract=readj(WEB/'WEB_S1_DATA_CONTRACT.json');contract['source_pins'][str(WEB/'research/P7A_SUMMARY.json')]=sha(WEB/'research/P7A_SUMMARY.json');put(WEB/'WEB_S1_DATA_CONTRACT.json',contract);put(WEB/'evidence/WEB_SOURCE_PINS.json',contract['source_pins'])
 acceptance=readj(WEB/'WEB_S1_ACCEPTANCE.json');acceptance['browser_passed']=browser['passed'];acceptance['browser_failed']=browser['failed'];acceptance['history_files_unchanged']=check['passed'];put(WEB/'WEB_S1_ACCEPTANCE.json',acceptance)
 appendix=f'''\n## 最终交付复核（本次实际执行）\n独立数值检查{status['independent_numeric_checks']}项、实际日历前月驱动身份{len(lag_checks)}项、合成及已保存推理入口{status['unit_and_saved_entry_checks']}项通过，最终失败0。历史保护清单{check['checked']}个文件全部哈希一致。网站接口{web['passed']}项、浏览器{browser['passed']}项通过，均无fit及新评分。\n最终72模型的alpha全部为100；MEM的rho在23站为0.25，在{rho_half}为0.50，未采用0.75。该选择只来自<=2017内部向前验证，未据历史对照调整。新模型契约将P7公式版本与复用P2求解器序列化版本明确分开。\n原27站54模型身份见P7A_ORIGINAL_27_MODEL_IDENTITIES.csv；24站才进入本轮拟合。模型复杂度和实际CPU fit+predict时间见P7A_MODEL_COMPLEXITY_AND_COST.csv，未把计时当业务服务性能。\n交付目录SHA256SUMS.txt对代码、协议、模型、预测、报告和证据封存；runtime/logs为明确排除的可变操作日志。完成后训练入口拒绝原地重拟合/覆盖。\n'''
 with (ROOT/'P7A_RESEARCH_REPORT_ZH.md').open('a',encoding='utf-8') as f:f.write(appendix)
 (ROOT/'P7A_REPRODUCTION_GUIDE.md').write_text(r'''# P7A复现与只读核验
本次目录已封存，禁止覆盖。首先运行只读验证（无fit、无新评分）：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\code\verify_delivery.py'
```

若需完整复现实验，复制code至新的独立输出目录，设置VHS_P7A_OUTPUT及VHS_WEB_S1_OUTPUT为尚无协议/清单的新目录。不能指向任何P0–P7旧目录。运行该副本的prepare.py → engine.py → final_train.py → historical_predict.py → score_verify_report.py → verify_extra.py。prepare先封存协议；engine训练期评分后才可晋升；final_train仅使用<=2017Q；historical_predict不导入fit，不读同期Q；独立score最后才关联P6D已暴露标签。所有过程沿用原公开资料，无需下载或安装。

本次实际首次engine运行数值训练已完成但自输出哈希读取被拒，使用 --resume-summary-only 恢复汇总，未重训。final_train首个ID2 C0+PT已完成，恢复复用了保存参数及内层选择，16次拟合的原耗时不可恢复，未伪造。见evidence/RECOVERY_AND_ATTEMPTS.json和RUN_ATTEMPTS.jsonl。

已保存模型推理入口（weather-csv必须仅含date,P,T，且有真实前月/记忆初始化历史，不接受Q）：

```powershell
& 'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe' -B 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\code\predict_saved.py' --model 'E:\VHS_Public_Baseline_Lab\vhs_p7a_hydrological_models\models\ID_2\P7-MEM\model.json' --weather-csv '<经过准入的date_P_T文件.csv>' --dates 'YYYY-MM' --output '<新的输出路径.json>'
```

此模板不代表已获得未来Q或完成新独立评分；MEM目前仅研究候选。执行命令记录见evidence/ACTUAL_EXECUTION_COMMANDS.json。全部样本/折/模型参数、内层损失、最终alpha/rho、支持限制均可回溯。训练cache只含2017及以前Q。训练读取审计、原P4标签哈希、模型/预测封存分别保存；不通过synthetic布尔值变更来源。
''',encoding='utf-8')
 commands=[{'command':str(pathlib.Path(__import__('sys').executable))+' -B '+str(ROOT/'code'/name),'role':role,'executed':True} for name,role in [('prepare.py','<=2017 source admission and pre-score protocol freeze'),('engine.py','CV numerical training completed; seal bookkeeping failed'),('engine.py --resume-summary-only','no-refit summary recovery'),('final_train.py','<=2017 final candidate and matched baselines, one saved-model recovery'),('historical_predict.py','weather-only prediction no fit or external Q'),('score_verify_report.py','independent exposed-label scoring after prediction seal'),('verify_extra.py','independent numerical reconstruction no fit'),('test_saved_predict.py','no-fit saved-model entry checks'),('web_accept.py','HTTP/source identity acceptance, no fitting/scoring')]]
 put(ROOT/'evidence/ACTUAL_EXECUTION_COMMANDS.json',{'recorded_from_actual_session':True,'commands':commands,'note':'shell Copy-Item/launch commands and review interruptions preserved in session; timestamp not reconstructed'})
 with (ROOT/'RUN_ATTEMPTS.jsonl').open('a',encoding='utf-8') as f:
  for event in [{'event':'FINAL_TRAINING_COMPLETED','fits':1872,'models':72,'includes_recovered_saved_model_fits':16},{'event':'EXPOSED_PREDICTION_AND_SCORING_COMPLETED','prediction_records':2592,'fit_calls_in_predict_or_score':0},{'event':'DELIVERY_COMPLETED','total_real_fit_calls':13082,'future_Q_in_training':0}]:f.write(json.dumps({**event,'recorded_utc':utc()})+'\n')
 (ROOT/'P7A_COMPLETION_REPORT_ZH.md').write_text(f'''# P7A完成状态\n真实完成24站五模型训练期时序验证，118合格站点折，590外层、10620内层拟合，14160条验证预测、2832唯一站月。2覆盖失败折保留。\nSL未晋升：−0.3428%等权技能，14/24站改善。MEM通过研究门槛：+3.5563%，22/24站改善，但最后2016–2017块−2.3559%。\n最终MEM与公平基线72模型、1872次额外拟合；总13082次真实拟合。原P4-V2未改。先封存2592条无Qobs预测，独立进程用864个已暴露站月评分。\nMEM对同支持L1的2018–2020后验技能+5.9515%，23/24站改善，ID512为负；DJF+5.1021%，但13站冬季绝对NSE仍负。ID343合并绝对NSE仍负。并非新盲测、业务预报或物理机制认证。\n{appendix}\n已完成：协议/准入/真实拟合/共同样本消融/参数和日期复核/已暴露时期独立流程评分/WEB只读集成。\n受阻：FUTURE_HOLDOUT_NOT_AVAILABLE，暂无未经接触并由独立保管人锁定的新Q与同质驱动。\n未执行：P7B训练/新盲测、SL后验晋升、原P4替换、网站生产发布、教师Q、区间重校准、河段传播预测。\n建议下一轮仅推进P7B独立数据准入与锁定；新独立验证完成前不进行最终模型定型和生产替换。\n''',encoding='utf-8')
 (WEB/'WEB_S1_INTEGRATION_REPORT_ZH.md').write_text(f'''# WEB-S1原v0.6候选科研证据集成\n\n已运行地址：http://127.0.0.1:8794/#/results/research?dataset=LAMAH_CE_PUBLIC_V1&station=LAMAH_CE_PUBLIC_V1:171&researchPeriod=2020&start=2020-01&end=2020-12\n\n以R2U1/host为起点，仅复制代码、static、research代码和必要manifest；不复制teacher/research_ready或旧日志。保留原首页、六层导航、共享站点/模型/年月状态及数据集切换token缓存保护。不是8791另做独立首页。\n\n已接通：原27站54模型，V1原25站899站月及1798预测；P5 648条应用仍归原类别；新研究页可选择P6B 2018–19（24站576站月）、P6C 2020（24站288站月）、P6D 36月合并后验诊断（864站月/1728预测），不把重复展示计作新观测。P6模型均绑定原P4-V2 release/snapshot和P6来源文件哈希；V1仍使用P4-V1，不合并元数据快照。新派生证据snapshot在contract中标明精确父来源。\n\n每站曲线、绝对NSE/KGE和增量技能、前1/前3月损失占比、季节、原经验区间、特征可加贡献、输入支持及P6原报告均真实可读。默认不返回Qobs，当前用户授权的受控本地单站视图可显式显示公开Qobs；无批量导出接口，format/export/download被403拒绝。缺少该24站共同外部支持的611/688/818显示NOT_EVALUATED，不填零；818单站历史并未伪称不存在。\n\n原空间点图、V1评分、许可与模型文件仍保留；右侧P6状态已对24站更新，业务认证仍NOT_CERTIFIED，REACH_PREDICTION_NOT_AVAILABLE不变。P7单列研究页，SL失败保留，MEM仅达到训练期候选门槛；P7协议/模型注册来源与P4来源分离，默认仍P2-L1。\n\n权限：仅用户要求的本地候选展示；生产display permission=NOT_GRANTED，动态执行/公开production hook/教师预测仍403。启动器拒绝教师source mount，旧权限文件未改。未伪造签名、审批者或verified callback。\n\n接口与身份验收{web['passed']}项、实际浏览器{browser['passed']}项通过。54个原模型JSON哈希和npz数组合法加载；P6三时期逐月预测、分解和指标逐项对源，未在网页重评分或fit。截图和AX记录在evidence/browser。验收中发现并修复combined-period下划线解析、P7旧来源侧栏；载入中检查保留为中间观察，最终就绪状态验证通过。\n\n历史保护{check['checked']}文件全部一致。无生产部署许可，原网站目录及8775/8791/8792/8793未改；仅管理本轮8794候选PID。仍不可用：真正河段传播预测、业务风险认证、新独立P7确认集、教师Q及在线模型执行。软件验收不等于水文科学验证。\n''',encoding='utf-8')
 (WEB/'WEB_S1_RUN_AND_ROLLBACK.md').write_text(r'''# 运行、接口与回滚
在PowerShell执行：
```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_web_s1_research_integration\start_host.ps1'
```
只启动127.0.0.1:8794，检查现有进程身份，不替换其他占用者。明确未挂载教师源，不占用8775/8791/8792/8793。原主站API与导航保留，新增GET /api/v6/candidate-public/research/catalog|station|report|p7。station请求必须携带dataset、精确period/snapshot、命名空间station和合法model。source contract精确关联P6源与P4-V2模型，默认无Qobs。

```powershell
& 'E:\VHS_Public_Baseline_Lab\vhs_web_s1_research_integration\stop_host.ps1'
```
停止脚本核对自己的PID、启动时间及host_root，只停止本候选。回滚无需恢复旧文件：旧R2/R2U1/v0.6和端口未修改。停止8794后返回原版本URL/原启动器，不能删除旧结果或修改权限。

只读核验两套交付：运行P7A/code/verify_delivery.py。SHA排除runtime、host/logs、host/tmp、host/var及__pycache__这类可变操作目录；其余已封存文件应保持哈希一致。运行服务只读科研源，不重新训练或评分。source hash不一致时拒绝，不自动回退到锡尔河或旧metadata snapshot。

正式生产接入仍需原平台有权负责人批准精确结果展示范围及原可信display callback；本轮未授予生产、在线执行或教师数据权限。P6新Q接口复用同一source/run/station/model/period外键，先独立封存科学结果，再增加新的证据snapshot，不能回写旧成绩。
''',encoding='utf-8')
 # Actual candidate delta, no changes to historical source paths.
 delta=[];u=LAB/'vhs_r2u1_p6a/host'
 for p in (WEB/'host').rglob('*'):
  if not p.is_file() or any(k in p.parts for k in ['logs','tmp','var','__pycache__']):continue
  rel=p.relative_to(WEB/'host');src=u/rel
  if not src.exists() or sha(src)!=sha(p):delta.append({'path':str(rel),'change':'ADDED' if not src.exists() else 'MODIFIED_IN_NEW_CANDIDATE_ONLY','historical_sha256':sha(src) if src.exists() else None,'candidate_sha256':sha(p)})
 put(WEB/'evidence/CANDIDATE_CODE_DIFF.json',delta)
 for root in [ROOT,WEB]:
  put(root/'evidence/SEAL_POLICY.json',{'frozen':'code, protocol, parameters, science tables, evidence and reports','mutable_excluded':['runtime','logs','host/logs','host/tmp','host/var','__pycache__'],'SHA256SUMS_excludes_itself':True,'history_scope':'2222 individually enumerated protected files; not a claim of hashing every byte in all source archives','no_production_or_teacher_permission_changes':True})
  files=[]
  for p in sorted(root.rglob('*')):
   if not p.is_file() or any(k in p.relative_to(root).parts for k in ['runtime','logs','tmp','var','__pycache__']) or p.name=='SHA256SUMS.txt':continue
   files.append((p,sha(p)))
  (root/'SHA256SUMS.txt').write_text(''.join(h+'  '+str(p.relative_to(root)).replace('\\','/')+'\n' for p,h in files),encoding='utf-8')
  print('SEALED',root,'files',len(files),'manifest_sha256',sha(root/'SHA256SUMS.txt'),flush=True)
 print('history unchanged',check['passed'],'numeric',status['independent_numeric_checks'],'calendar',len(lag_checks),'unit',status['unit_and_saved_entry_checks'],'API',web['passed'],'browser',browser['passed'],flush=True)
if __name__=='__main__':main()
