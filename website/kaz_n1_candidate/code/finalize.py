"""Finish KAZ-N1 evidence, reports and one-time delivery seal; no modeling."""
from intake import *
import shutil,sys,platform,importlib.metadata,ast

def textfile(name,s):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8')

def main():
 if (ROOT/'SHA256SUMS.txt').exists():raise FileExistsError('DELIVERY_ALREADY_SEALED')
 viz=pathlib.Path(r'C:\Users\Administrator\.codex\visualizations\2026\10\25\01a17144-342b-7e92-8b56-e799369fc9fa')
 browser=ROOT/'evidence/browser';browser.mkdir(exist_ok=True)
 for p in viz.glob('KAZ_N1_*'):
  if p.suffix in ['.png','.txt','.json']:shutil.copy2(p,browser/p.name)
 ui=readj(browser/'KAZ_N1_BROWSER_ACCEPTANCE.json');assert ui['failed']==0
 hist=readj(ROOT/'evidence/HISTORY_BEFORE.json');bad=[p for p,h in hist.items() if not pathlib.Path(p).is_file() or sha(p)!=h]
 hcheck={'checked':len(hist),'passed':len(hist)-len(bad),'failed':len(bad),'failures':bad,'teacher_Q_hashed_or_read':False,'scope':'previous public research and website source manifests; no new claim about unmanifested files'}
 put(ROOT/'evidence/HISTORY_FINAL_CHECK.json',hcheck);assert not bad,bad
 gis=readj(ROOT/'evidence/GIS_SOURCE_HASHES.json');gbad=[p for p,h in gis.items() if sha(p)!=h];assert not gbad
 put(ROOT/'evidence/GIS_SOURCE_FINAL_CHECK.json',{'checked':len(gis),'passed':len(gis),'failed':len(gbad)})
 # Inspect only the regional meteorological file schema/coordinates, never runoff data.
 import xarray as xr
 met=REPO/'data/processed/era5_land/era5land_incremental_byblk_to_dsk_1978_1983.nc'
 with xr.open_dataset(met) as ds:
  info={'path':str(met),'sha256':sha(met),'sizes':dict(ds.sizes),'attributes':dict(ds.attrs),'coordinates':{k:{'dims':list(v.dims),'first':str(v.values.flat[0]),'last':str(v.values.flat[-1])} for k,v in ds.coords.items()},'variables':{k:{'dims':list(v.dims),'units':v.attrs.get('units')} for k,v in ds.data_vars.items()},'numeric_Q_read':False,'national_drivers_available':False}
 put(ROOT/'evidence/REGIONAL_MET_METADATA_CHECK.json',info)
 env={'python':sys.version,'executable':sys.executable,'platform':platform.platform(),'packages':{p:importlib.metadata.version(p) for p in ['numpy','scipy','geopandas','shapely','pyproj','pyogrio','xarray']},'new_dependencies_installed':False}
 put(ROOT/'evidence/ENVIRONMENT.json',env)
 put(ROOT/'KAZ_N1_PROVENANCE.json',{'protocol_sha256':sha(ROOT/'KAZ_N1_FROZEN_PROTOCOL.json'),'predictions_sha256':sha(ROOT/'KAZ_N1_UG_PREDICTIONS.csv'),'prediction_seal':readj(ROOT/'pub/PREDICTIONS_SEALED.json'),'input_pins':readj(ROOT/'pub/CACHE_SOURCE_PINS.json'),'code_hash_capture':'delivery seal after execution; training-time source hash was not separately captured','post_execution_code_changes':'existing-output refusal guards, provisional density text correction, per-heldout mask scope docstring, UI aria selection; model formulas and numeric results unchanged and independently reconstructed','environment':env,'GIS_input_pins':gis})
 parsed=[]
 for p in (ROOT/'code').glob('*.py'):ast.parse(p.read_text(encoding='utf-8'));parsed.append(p.name)
 put(ROOT/'evidence/CODE_PARSE_CHECK.json',{'passed':len(parsed),'failed':0,'files':parsed})
 num=readj(ROOT/'evidence/INDEPENDENT_NUMERICAL_VERIFICATION.json');api=readj(ROOT/'evidence/WEB_API_ACCEPTANCE.json');pub=readj(ROOT/'pub/EU_PUB_FINAL_STATUS.json');counts=readj(ROOT/'KAZ_N1_COUNTS.json')
 assert num['failed']==api['failed']==0
 # Final candidate URL only; this does not change any historical launch script.
 launch=ROOT/'web_candidate/start_host.ps1';s=launch.read_text(encoding='utf-8-sig').replace('#/overview?dataset=LAMAH_CE_PUBLIC_V1','#/overview?dataset=KAZAKHSTAN_PUBLIC_NETWORK');launch.write_text(s,encoding='utf-8-sig')
 textfile('KAZ_N1_Q_MASK_SCOPE_CLARIFICATION.md','''# PUB目标Q隔离字段的精确定义

`target_Q_reads=0` / `prediction_process_target_Q_reads=0`指每个当前留出任务：该任务目标站的所有日期Q被文件访问守卫拒绝，目标Q不参与供体拟合、目标季节Q模板、尺度拟合或参数选择。它不表示整个交叉验证进程从未读取任何参评站的Q：某站作为其他折的合法供体时可以读取其≤2013 Q；每任务重新拟合，不复用跨折拟合状态。所有任务的2014–2017测试Q读取均为0，评分角色在预测封存后另行读取。

原保存状态字段和预测未改写。`pub/TARGET_MASK_AUDIT.json`包含48任务的移除/允许站点，`pub/PREDICTIONS_SEALED.json`包含预测角色实际读文件集合与96次有意拒绝测试。静态特征及目标站气象气候态只依赖合法元数据和≤2013外生P/T。旧项目已暴露目标期标签，空间遮蔽不能恢复完全盲测。
''')
 textfile('KAZ_N1_REPRODUCTION_GUIDE.md',rf'''# KAZ-N1复核与运行

现有环境：`{sys.executable}`；新目录：`{ROOT}`。不安装依赖。所有命令使用`-B`避免在冻结目录产生字节码。

## 已实际运行的计算入口

执行顺序为`intake.py`（官方快照/历史初检）→`assets.py`（资产/协议冻结）→`gis_candidates.py`（真实GIS）→`pub_prepare.py`（训练/评分角色分离缓存）→`pub_train_predict.py`（126次回归拟合/48次气候态估计及9216条预测封存）→`pub_score.py`（独立评分）→`results.py`（导师答案/密度/缺口）→`web_prepare.py`（复制原主站候选）→`verify.py`（独立数值重构）→`web_verify.py`（实际HTTP验收）→浏览器页面验收→`finalize.py`。

实际脚本调用形式为`& '{sys.executable}' -B '{ROOT}\code\<入口>.py'`。源码根常量在`code/intake.py`，缓存源路径与哈希在`pub/CACHE_SOURCE_PINS.json`。旧文件只读。

## 本次封存后的只读复核命令

```powershell
& '{sys.executable}' -B '{ROOT}\code\verify_delivery.py'
```

该命令只计算交付、历史、GIS及WEB输入SHA256，不fit、不评分、不联网。`verify.py`可以用保存参数重构全部预测和直接核算指标，但会覆盖本轮已有数值复核JSON，故正式封存后应在另一个输出副本中运行；不应在本run中重跑完整流水线。训练和评分入口已增加已有封存产物拒绝规则。日后复现实验须复制代码/来源证据到新根目录并修改副本的ROOT，使用相同冻结协议和输入哈希；不得覆盖本目录，也不得据此扩大教师/GRDC权限。

## 数据与分析口径

官方网络442、河流394为现页事实；统计年未注明。国土面积2,724,900 km²固定。GIS用真实AS瓦片、NaturalEarth概化边界、LAEA48N68E，固定25km河网距离、保守上游面积≥1000km²、2km边界缓冲、3km节点分隔；1230点只属初筛，无当前实站去重/完整汇水区/8大管理流域归属，正式N_candidate=0。

欧洲PUB按两种空间遮蔽方案，各24站×48测试月。供体Q≤2013，目标评分2014–2017，所有候选均固定Ridge100，无事后筛选。目标Q隔离的逐任务定义见`KAZ_N1_Q_MASK_SCOPE_CLARIFICATION.md`。两方案、四方法和同水系站点不是独立重复；所有负NSE及原始负预测保留，非负为次分析。常数预测导致不可定义的KGE以空值及原因码表示。

## 核心文件映射

导师四问：`KAZ_N1_SUPERVISOR_ANSWER_ZH.md`；组会科学结果：`KAZ_N1_GROUP_MEETING_SUMMARY.md`；官方证据：`source/SOURCE_LOG.json`及HTML；合法性/缺口：`KAZ_N1_DATA_READINESS.csv`；真实几何：`KAZ_N1_PRELIMINARY_GEOMETRY_POOL.geojson`；全部预测/指标：`KAZ_N1_UG_PREDICTIONS.csv`、`KAZ_N1_UG_VALIDATION_METRICS.csv`；逐年/冬季/5–6月与水系：`pub/EU_PUB_*METRICS.csv`、`pub/EU_PUB_MACRO_SUMMARY.csv`；每折模型参数：`pub/models`；真实拟合：`pub/FIT_CALLS.csv`；缺失交付原因：`KAZ_N1_DELIVERABLE_AVAILABILITY.json`；页面截图/AX：`evidence/browser`。
''')
 textfile('KAZ_N1_WEB_RUN_AND_ROLLBACK.md',rf'''# 原主站候选运行及回滚

入口：http://127.0.0.1:8795/#/overview?dataset=KAZAKHSTAN_PUBLIC_NETWORK

```powershell
& '{ROOT}\web_candidate\start_host.ps1'
& '{ROOT}\web_candidate\stop_host.ps1'
```

当前8795已实际运行并经HTTP和浏览器检查。启动器仅接受8795空闲或该候选健康身份；停止器核对该候选PID和启动时间。不要直接kill任意端口进程。原8775/8791/8792/8793/8794不占用、不停止。

新增在原WEB-S1复制版的四层导航与共享选择状态中：官方四问、真实部分河网及1230初筛点、3个状态独立图层、8大流域名称及几何缺口、实际密度、欧洲PUB完整负结果。真实物理站当前坐标0、可预测虚拟站0，地图为空图层有明确原因。欧洲指标以外国数据集命名，不写入KAZ/SYRDARYA成绩。

候选新增`host/kaz_national.py`、`static/view_kaz_national.js`；原复制版`r2_public.py`/`server.py`/`index.html`接入只读路由、数据集页签。`WEB_KAZ_SOURCE_PINS.json`严格绑定来源；请求跨快照拒绝，训练/推理/导出Qobs及正式生产公开端点403。新页签选中状态也同步ARIA。旧默认P2-L1及54个公开模型身份保持；旧教师源未挂载。

本次仅本地候选，生产发布仍NOT_GRANTED，没有伪造审批或改原服务。回滚只停止本候选并使用原历史主站入口；没有覆盖旧目录，无需恢复旧文件。不需要删科研产物。若未来发布，应由有权负责人按旧可信展示许可机制批准新数据集/快照/来源范围；展示许可不能替代执行许可。
''')
 textfile('KAZ_N1_NEXT_DATA_MINIMUM.md','''# 下一轮必要数据，不追加大规模模型搜索

1. 从Kazhydromet取得有版本及使用条件的现行站点目录：官方ID、河/站名、经纬度/CRS、启停及迁站、机构及年份。先解决394河流点的身份/吸附/5km排重，不能将站数当流量序列。
2. 补齐覆盖全国的HydroRIVERS/HydroBASINS流域瓦片，取得经核实的8大管理流域多边形；同一规则再算候选/跨境拓扑和全上游集水区。当前48.59%是已有L12对概化国界的面积覆盖，不是有Q或有模型覆盖。
3. 最小一批可合法建模及评分的哈萨克斯坦日/月Q与QC、日界、单位、源机构及数据许可；GRDC须实际负责人完成数据请求及条件接受，不推定已有权限。保留独立未暴露时段或水系；先锁定再预测后评分。
4. 与每一目标全上游汇水区对应的同质P/T及静态属性。现有本地NetCDF只含1978–1983 BYBLK-DSK增量区，非全国驱动；不能替代全上游输入。metadata-only实查见evidence/REGIONAL_MET_METADATA_CHECK.json。
5. 先完成少量KAZ跨站遮蔽及整水系遮蔽，完整保留失败，再判断能否给适用域及可信数量；欧洲24站结果只作方法学开发依据，不能作为每个新点的“已验证NSE”。
''')
 # Reconstructed execution index: distinguish source event times from index creation.
 attempts=[]
 for script,artifact,outcome in [('intake.py','KAZ_N1_OFFICIAL_BASELINE.json','OFFICIAL_BASELINE_COMPUTED'),('assets.py','KAZ_N1_FROZEN_PROTOCOL.json','PROTOCOL_FROZEN_BEFORE_SCORE'),('gis_candidates.py','KAZ_N1_GIS_EXECUTION.json','1230_REAL_PRELIMINARY_POINTS'),('pub_prepare.py','pub/CACHE_SOURCE_PINS.json','PUBLIC_ROLE_SPLIT_CACHES'),('pub_train_predict.py','pub/PREDICTIONS_SEALED.json','126_REGRESSION_FITS_9216_PREDICTIONS'),('pub_score.py','pub/EU_PUB_FINAL_STATUS.json','EUROPEAN_REAL_LABEL_SCORING'),('results.py','KAZ_N1_GROUP_MEETING_SUMMARY.md','MEETING_RESULTS'),('web_prepare.py','data/NATIONAL_WEB_BUNDLE.json','ORIGINAL_HOST_CANDIDATE'),('verify.py','evidence/INDEPENDENT_NUMERICAL_VERIFICATION.json','FINAL_16629_PASS_0_FAIL'),('web_verify.py','evidence/WEB_API_ACCEPTANCE.json','1256_PASS_0_FAIL')]:
  p=ROOT/artifact;attempts.append({'record_kind':'EXECUTED_COMMAND_INDEX_RECONSTRUCTED_FROM_SAVED_OUTPUT','command':f'& "{sys.executable}" -B "{ROOT / "code" / script}"','output':artifact,'output_sha256':sha(p),'output_mtime_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),'outcome':outcome,'not_a_claim_of_original_attempt_start_time':True})
 attempts.extend([{'record_kind':'OBSERVED_FAILURE','stage':'NaturalEarth_download','outcome':'official page malformed href HTTP406; canonical public NaturalEarth S3 distribution then succeeded','evidence':'source/NATURALEARTH_DOWNLOAD_FAILURE.json'}, {'record_kind':'OBSERVED_SOURCE_BLOCKS','stage':'official_map_Q_GRDC','outcome':'map connection refused/timeout, Q portal timeout, local GRDC TLS failure; no security relaxation or Q acquired'}, {'record_kind':'OBSERVED_VERIFIER_FAILURE_FIXED','stage':'first verify.py','outcome':'float(empty) on correctly undefined KGE caused verifier failure; corrected verifier to accept explicit N/A reason; no model/prediction/score changed'}, {'record_kind':'BROWSER_OPERATOR_CORRECTION','stage':'tab selection','outcome':'AX indices changed on reload; inspected wrong selected public tab then selected KAZ; 8 final assertions pass'}])
 textfile('RUN_ATTEMPTS.jsonl','\n'.join(json.dumps(r,ensure_ascii=False) for r in attempts)+'\n')
 put(ROOT/'KAZ_N1_FINAL_STATUS.json',{'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'BASELINE_GIS_SCREENING_AND_EU_PUB_COMPLETED_KAZ_MODELS_NOT_AVAILABLE','counts':counts,'European_PUB':pub,'target_Q_mask_scope':'per current heldout task; a station may be donor in other tasks; all test-period Q denied in predictor','numerical_checks':{'passed':num['passed'],'failed':num['failed']},'API_checks':{'passed':api['passed'],'failed':api['failed']},'browser_checks':{'passed':ui['passed'],'failed':ui['failed']},'historical_hash_check':hcheck,'GIS_hashes_checked':len(gis),'Kazakhstan_fit_calls':0,'Kazakhstan_prediction_records':0,'teacher_Q_reads':0,'website_production_release':'NOT_GRANTED','new_candidate_url':'http://127.0.0.1:8795/#/overview?dataset=KAZAKHSTAN_PUBLIC_NETWORK','no_historical_model_or_permission_change':True,'future_Kazakhstan_capacity_count':'UNKNOWN_NOT_ESTIMATED'})
 textfile('KAZ_N1_COMPLETION_REPORT_ZH.md',f'''# KAZ-N1实际完成结果

{(ROOT/'KAZ_N1_SUPERVISOR_ANSWER_ZH.md').read_text(encoding='utf-8')}

## 执行与核验

完成官方页面快照及许可/访问日志、真实GIS和初筛、欧洲24站两种空间遮蔽下四种轻量方法训练/预测/评分、原主站8795候选集成。实际回归拟合126次，供体气候态估计48次，预测9216条，每方案唯一1152站月；不是9216个独立测站。所有负结果保存。中位数并非均值：最近邻留一站平均NSE仍为−0.608；留宏观水系时区域共享模型中位NSE−10.849，不能只报道较好的最近邻结果。完整逐站/逐年/季节/水系在CSV。

数值/GIS/指标独立复核{num['passed']}通过/{num['failed']}失败；预测最大参数重构误差{num['max_PUB_prediction_reconstruction_error_m3s']:.15g}m³/s。API实际验收{api['passed']}通过/{api['failed']}失败；浏览器{ui['passed']}通过/{ui['failed']}失败，截图及AX已保存。历史哈希终检{len(hist)}通过/0失败，原GIS8个组件也一致。该保护覆盖冻结清单中的文件，不把它夸大为全磁盘审计。软件通过不代表哈萨克斯坦科学模型已验证。

首次独立复核脚本遇到空KGE数值转换错误，已改为检查N/A和原因码后通过，真实指标未改。下载原链接格式错误、官方源连接限制及浏览器一次索引变化均如实记录。命令、环境、来源、拟合参数、封存预测与各角色访问守卫证据均交付；运行索引明确为据保存输出整理，不伪造原始开始时间。

## 已验证/已有数据未验证/理论与不可评估

已验证：官方当前网页基数、固定密度算式；部分覆盖1230真实几何；欧洲PUB真实观测标签结果；候选主站可见/API隔离。

已有但未准入：旧KMZ坐标结构，因来源、现行身份和再发布许可不清而未用于现行站图层；现有区域气象NetCDF经实查仅一处11888km²增量区，1978–1983 UTC日序列，非全国P/T。

尚无法评估：全国潜在虚拟站总量、正式逐8大流域候选数、哈萨克斯坦无资料站NSE/KGE。官方实站坐标未获得，不能做合法完整排重；河网/子流域AS瓦片不完整、缺管理流域多边形和全上游点位驱动；无本任务合格KAZ Q。其余国家数据和欧洲能力不能填补此缺口。

纯情景：本轮未用理论目标数量制造新增密度。实际正式N_candidate、预测与研究准入都是0，实际密度未提升；这不等于全国没有可建虚拟站，也不否定初筛1230点的几何存在。

## 主站交付与停止点

保留原四层导航和P7/P6D结果。新dataset精确区分KAZ官方基线与欧洲开发实验，3类图层独立，未取得的实站坐标及虚拟预测显示空状态及原因。教师源未挂载，训练、动态模型推理及正式公开路由403。仅候选，无业务认证或正式发布批准。见WEB运行回滚指南与截图。

下一步只补齐现行官方坐标、全国流域拓扑/8大流域边界、许可及QC明确的KAZ Q和同质驱动，再冻结KAZ空间遮蔽验证。没有开展新一轮P7搜索，也未读取教师受限Q。
''')
 # Bind source/code/environment and every newly generated scientific artifact, excluding runtime logs.
 excluded={'runtime','logs','tmp','var','__pycache__'}
 files=[p for p in ROOT.rglob('*') if p.is_file() and not (set(p.relative_to(ROOT).parts)&excluded) and p.name!='SHA256SUMS.txt']
 textfile('SHA256SUMS.txt','\n'.join(f'{sha(p)}  {p.relative_to(ROOT).as_posix()}' for p in sorted(files))+'\n')
 print(json.dumps({'sealed_files':len(files),'SHA256SUMS_sha256':sha(ROOT/'SHA256SUMS.txt'),'history_passed':len(hist),'numerical_passed':num['passed'],'API_passed':api['passed'],'browser_passed':ui['passed']},ensure_ascii=False))
if __name__=='__main__':main()
