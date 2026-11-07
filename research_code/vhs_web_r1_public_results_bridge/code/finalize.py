"""Document and freeze a working, non-deployed public-results candidate."""
from core import *
import ast
tests=jl(BASE/"INTEGRATION_TEST_RESULTS.json");assert tests["all_pass"] and tests["count"]==60
bundle=jl(BASE/"data/bundle.json");contract=jl(BASE/"PUBLIC_RESULTS_CONTRACT.json");registry=jl(BASE/"PUBLIC_MODEL_REGISTRY.json")
properties={}
bools={"evaluation_eligible"};ints={"gauge_id","year","month"}
nullable_number={"qsim_raw","qsim_nonnegative","interval_80_lower","interval_80_upper","interval_90_lower","interval_90_upper"}
nullable={"evaluation_run_id","reach_id","geometry"}
for key in contract["required_prediction_fields"]:
 properties[key]={"type":"boolean" if key in bools else "integer" if key in ints else ["number","null"] if key in nullable_number else ["string","null"] if key in nullable else "string"}
properties["dataset_id"]={"const":DS};properties["model_id"]={"enum":["C0+PT","P2-L1"]};properties["prediction_kind"]={"enum":["TEMPORAL_HOLDOUT","FINAL_MODEL_APPLICATION","MASKED_GAP_EVALUATION","TRUE_GAP_RECONSTRUCTION"]};properties["month"]={"type":"integer","minimum":1,"maximum":12};properties["reach_id"]={"type":"null"};properties["geometry"]={"type":"null"}
schema={"$schema":"https://json-schema.org/draft/2020-12/schema","title":"VHS public station prediction result record v1","type":"object","required":contract["required_prediction_fields"],"properties":properties,"additionalProperties":False,"allOf":[{"if":{"properties":{"prediction_kind":{"const":"FINAL_MODEL_APPLICATION"}}},"then":{"properties":{"evaluation_eligible":{"const":False},"evaluation_run_id":{"type":"null"}}}}]}
jw(BASE/"PUBLIC_RESULTS_SCHEMA.json",schema)
for r in bundle["predictions"]:
 assert set(r)==set(contract["required_prediction_fields"]) and r["dataset_id"]==DS
 assert r["geometry"] is None and r["reach_id"] is None and 1<=r["month"]<=12
 for k in nullable_number:assert r[k] is None or isinstance(r[k],(float,int)) and math.isfinite(r[k])
for path in (BASE/"code").glob("*.py"):ast.parse(path.read_text(encoding="utf-8"))
for r in jl(BASE/"evidence/FINAL_ADDITIONAL_ACCEPTANCE.json")["checks"]:assert r["pass"]
after=history();before=jl(BASE/"evidence/HISTORY_BEFORE.json");assert after==before
jw(BASE/"evidence/HISTORY_FINAL.json",after)
permission="""# 正式发布权限需求
## 已有本轮授权范围
用户本轮明确要求在独立目录读取合法公开P4/P5产物、完成只读本地预览、隔离验证已有P5 CLI。已据此实现，不创建虚构审批人、签名、GRANTED记录。
本地预览 http://127.0.0.1:8791 仅提供既有封存结果，网页执行与Qobs导出持续403。此次CLI隔离验证使用既有公开推理授权范围，不构成生产网页执行许可。

## 部署前需实际负责人批准的最小范围
1. 确认实际部署工程与运维负责人；候选v0.6代码已核对，但8775当前拒绝连接，未能证明有活跃实例或其运行路径。不可把候选路径直接当运行目录。
2. 允许在明确访问范围展示LAMAH_CE_PUBLIC_V1的27站/54模型目录、V1的25站899站月独立评分与1798预测、V2的648应用预测、ID2人工遮蔽24预测，以及对应站点坐标、报告、许可署名。明确观众、服务地址/端口及导出范围。审批应绑定PUBLIC_MODEL_REGISTRY、RESULT_PROVENANCE、代码与产物哈希。
3. 新增独立公开科研快照入口；不能把原LAMAHCE的OPEN_METADATA_ONLY快照直接改名为公开科研快照，更不能扩展到SYRDARYA。
4. 审核公开来源署名和许可条件，保留P4来源记录采用的较严格CC BY-SA 4.0及提供者署名；网页展示不等于授权批量导出原始Qobs。
5. 若之后需要生产网页推理，需另行明确已发布站点/模型、合法P/T来源及单位、日期、输出保存与展示范围，并通过现有可信授权机制核验。当前没有这项生产许可，仍403。无需为只读结果展示解除任何旧执行403。

## 候选钩子如何遵守原权限
code/bridge.py提供V06PublicResultsHook，默认无宿主验证过的display callback即403。普通JSON的authorized或GRANTED不能批准请求。
生产宿主完成实际审批后，才能由其原有可信权限系统提供verified_display_permission。此钩子仅接管/api/v6/public/，旧/api/v6/results/与SYRDARYA路径不改。
不创建新的审批系统，不在交付中伪造正式批准。
"""
(BASE/"WEB_PERMISSION_REQUIREMENTS.md").write_text(permission,encoding="utf-8")
guide=r"""# 候选接入与复用
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
"""
(BASE/"INTEGRATION_GUIDE.md").write_text(guide,encoding="utf-8")
report=f"""# WEB-R1公开真实结果接入报告
## 交付状态
已实现且运行的独立候选预览：http://127.0.0.1:8791/。已接入真实封存模型目录、站点曲线、模型评价、站点空间图和科研报告。不是只交设计文档。
旧生产网站实际显示功能新增=0：候选v0.6路径已核对，8775连接拒绝，不能认定它为活跃实例。本轮未启动、停止或修改旧站，未将预览冒称生产发布。
LAMAHCE原站仍OPEN_METADATA_ONLY，原执行403未改变。生产展示审批尚未取得；公开数据只读本地预览由本轮用户任务授权。

## 产物身份核验与导入
27站54个正式保存V2模型，全部实际加载验证；另外54个V1原模型仅作独立评分关联，人工遮蔽2模型独立关联，不重复计入54发布模型。
V1原模型2015–2017：25站、899个站月、1798条TEMPORAL_HOLDOUT预测，导入50条原始主评价及150条逐年评价。
V2：P5已有648条FINAL_MODEL_APPLICATION，27站×2×12月；2016已经参与V2训练，evaluation_eligible=false，不冒称独立OOF。
人工遮蔽24条MASKED_GAP_EVALUATION，仅ID2/2016的真正排除标签模型；TRUE_GAP_RECONSTRUCTION=0，NO_ELIGIBLE_TRUE_GAPS。
P5-SHRINK内部探索不注册为发布模型。不重新训练、不重跑P0–P5、不重新计算指标。
新结果数据不包含Qobs数值，只读复制已有Qsim/区间与评分，不读取公开日Q或教师Q。

## 页面实际可用功能
1. 站点结果：27站选择，两固定模型，三种预测类别，原始/非负展示，90%经验带；当前来源快照、发布与模型哈希、训练截止明确显示。
2. 模型评价：25站真实V1评分，NSE/KGE/RMSE/MAE/PBIAS，C0+PT与L1并列，逐年2015/2016/2017；V1覆盖与平均宽度在站点页可查。
3. 611/688明确NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT，数值null；378/383/455等负NSE原样保留，未以0替换。
4. 空间：27站模型分布、25站独立误差、区间覆盖/宽度、站点适用状态、合法月份Qsim五类可切换点图层。误差与Qsim来自不同源时逐字段标识快照，不混为同一实验。
5. 科研报告：P4/P5真实报告、模型卡、许可与署名可读，内容哈希可见。
6. 网页模型执行明确MODEL_EXECUTION_NOT_AUTHORIZED；点击测试真实403。独立CLI用保存模型生成12条验证预测，fit调用0，不注册为新独立实验。

## 空间真实性边界
官方站点原位置为EPSG3035米坐标，使用pyproj转WGS84写标准GeoJSON；现有投影画布直接消费保留的coordinates_epsg3035。27点往返误差<0.02m。
这些是站点点结果，不是连续适用区域/全河网预测。reach_id、预测记录geometry、reach_geometry为空并给NO_CERTIFIED_REACH_MAPPING。
REACH_PREDICTION_NOT_AVAILABLE保持；没有把站点Qsim赋给相邻河段或绘制虚假河流断面结果。

## 权限与隔离
本地预览和生产展示分开。没有伪造审批人、签名或GRANTED记录，没有更改旧NOT_AUTHORIZED。
默认拒绝的v0.6候选钩子需宿主原可信权限callback才可展示正式公开科研入口；不接管旧结果或教师路由。网页执行许可独立，仍403。
错误dataset/station/snapshot、V2冒充独立评价、Qobs导出、恶意Host/Origin均拒绝。切换数据集立即清空内容并阻止旧异步响应回写。
普通JSON授权字符串不能打开模型执行；未读取私有隔离数据。

## 验收
最终{tests['count']}项检查通过，12张真实Chrome截图。包括54/54加载、27/27站码、25站评价、899/1798精确计数、快照/发布外键、投影、无河段Qsim、无fit推理、403、无Qobs、许可页面、数据集切换、N/A及负值。
最终页面还逐个驱动Qsim/覆盖/宽度/适用状态图层，全部27点正常渲染。
附加浏览器测试曾因等待表达式返回DOM节点而非布尔值失败，修正测试表达式后通过；科研数据/模型未因测试修改，记录在ADDITIONAL_HARNESS_CORRECTION.json。
P0–P5及原v0.6共1305项历史列出文件哈希前后相同，无历史不一致。runtime和Chrome临时profile是运行期文件，不列入不可变交付SHA。
源码、API、注册表和截图封存，运行日志/进程身份另存runtime。

## 正式部署仍待完成
实际负责人确认活跃工程与运维位置，批准准确公开结果/坐标/报告/署名展示范围，然后在新候选checkout挂载现有hook与公开结果页面，经平台原合法机制部署。
无需解除旧403。生产动态推理还需单独批准模型/站点/输入/年月/保存范围，本轮不授予。
已实现待批准：候选结果API、前端、空间点图层、报告入口。缺产物不能展示：真实全缺档结果、河段Qsim、河段误差、连续适用区域、新P6独立评分。

## 完整河段预测缺什么
需要稳定reach_id及真实河段几何、认证拓扑、站点—河段物理映射；需要侧向入流、调水/水库及传播时间等边界和经校准的河道演算或守恒模型；需要独立河段尺度观测/误差及区间验证、来源许可与执行批准。单点月回归与站点插色不能替代这些条件。

## 恢复与回滚
旧站未改变，无需回滚旧文件。stop_preview.ps1仅停止本轮记录且启动时间匹配的预览进程；重新启动start_preview.ps1仍只用8791。
未来生产部署应在单独checkout，保存部署前哈希及配置，回滚到原发布并卸载公开hook/入口；不得删除P4/P5或修改教师授权。
P6复用方式与精确外键扩展见INTEGRATION_GUIDE.md。
"""
(BASE/"WEB_R1_INTEGRATION_REPORT_ZH.md").write_text(report,encoding="utf-8")
jw(BASE/"evidence/FINAL_DELIVERY_STATUS.json",{"UTC":now(),"preview_url":"http://127.0.0.1:8791/","production_deployed":False,"formal_production_permission":"NOT_GRANTED","historical_files_unchanged":1305,"integration_tests":60,"browser_screenshots":12,"public_result_records":2470,"Qobs_exported":0,"models_trained":0,"isolated_CLI_predictions":12,"teacher_data_read":False,"reach_predictions":0,"P6_evaluation_performed":False})
n=seal(BASE);v=verify(BASE);assert not v["mismatches"]
print(json.dumps({"sealed_files":n,"hash_manifest":sha(BASE/"SHA256SUMS.txt"),"tests":60,"preview":"http://127.0.0.1:8791/","production_deployed":False}))
