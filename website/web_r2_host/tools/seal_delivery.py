"""Write the final evidence-backed R2 report and delivery hashes."""
import hashlib,json,time
from pathlib import Path
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration')
def jl(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,t):(R/n).write_text(t,encoding='utf-8')
def jw(n,v):write(n,json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False))
tests=jl(R/'R2_INTEGRATION_TEST_RESULTS.json');assert tests['failed']==0
before=jl(R/'evidence/HISTORY_BEFORE.json');manifests=[]
for root,v in before.items():
    root=Path(root);name='SHA256SUMS_v0.6.txt' if root.name=='v0.6_four_layer_platform' else 'SHA256SUMS.txt'
    assert sha(root/name)==v['manifest_sha256'],root
    manifests.append({'root':str(root),'manifest':name,'sha256':v['manifest_sha256'],'unchanged':True})
jw('evidence/R2_HISTORY_MANIFEST_VERIFICATION.json',{'UTC':time.strftime('%Y-%m-%dT%H:%M:%S%z'),'manifests':manifests,'all_unchanged':True})
identity=jl(R/'runtime/host_identity.json')
discovery=jl(R/'R2_ACTIVE_HOST_DISCOVERY.json');discovery['final_candidate_identity']=identity;discovery['final_URL']='http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1';discovery['production_deployment_performed']=False
jw('R2_ACTIVE_HOST_DISCOVERY.json',discovery)
write('R2_HOST_INTEGRATION_REPORT_ZH.md',f'''# WEB-R2：原v0.6四层平台候选集成完成

完成时间：{time.strftime('%Y-%m-%dT%H:%M:%S%z')}。

候选主站：http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1

本轮把WEB-R1接入原v0.6代码副本的导航、路由、统一状态和页面位置。没有制作第二套首页，没有iframe，没有重新启动或修改8791。54个模型、站点曲线、独立成绩、空间点结果与报告已经在同一原主站中实际运行。

## 已接通的候选功能

- 原五项导航与三数据集切换：SYRDARYA、旧LAMAHCE元数据、新LAMAH_CE_PUBLIC_V1。
- 模型层：27站54个P4-V2模型。54/54通过既有P5磁盘加载/哈希验证；默认P2-L1，C0+PT保留基线；没有升级SHRINK。
- 结果层：P4-V1时间外1798条预测（25站、899站月）；P5-V2应用648条预测；ID2人工遮蔽24条；真实缺档0条。精确快照与发布身份不合并。
- 模型评价：25站的原冻结V1指标、2015–2017逐年成绩和80%/90%区间诊断。全部25站的NSE/KGE/RMSE/MAE/PBIAS与封存导入逐值一致，未重新评分。611/688为NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT；378/383/455负NSE可见。
- 空间层：27个官方EPSG:3035站点，25站独立误差与区间诊断，可选月份Qsim。坐标回投影误差小于0.02米，图中x/y使用相同投影比例。只显示站点点结果，没有河段Qsim。
- 科研报告：P4/P5报告、模型卡、公开许可与署名，来源文件哈希可核验。
- 原模型/站点/类别/年月在VHS.state和hash中共享；切换数据集清空页面与缓存，并阻断旧异步响应回写。

## 当前许可与运行边界

**正式生产发布：未执行，NOT_GRANTED。** 8775核查无监听，无法确认活跃生产目录与候选目录一致。原候选v0.6路径已验证为四层版本，但不能把它冒认成正在运行的发布实例。

已获准范围仅为本轮明确要求的隔离候选本地测试。候选接口 `/api/v6/candidate-public/*` 需显式本地启动参数；未启用时403。正式 `/api/v6/public/*` 保留R1 V06PublicResultsHook的默认403，没有伪造verified callback、审批人、签名、公钥或GRANTED。普通JSON授权字符串不能改变结果。

教师六份CSV未挂载、未读取。原教师适配器、权限策略与页面代码保留；候选教师页明确显示SOURCE_NOT_MOUNTED，原功能以合成夹具回归检验，不能声称实际教师数值页面已验收。旧LAMAHCE的882站元数据与原API正常。原SYRDARYA执行、公开模型动态执行、Qobs导出仍拒绝。

正式部署仍需负责人确认实际生产目录，并批准精确快照/模型发布绑定的只读展示范围，通过真实受信任display机制绑定审批回调；详见R2_PRODUCTION_PERMISSION_REQUIREMENTS.md。动态执行不在display批准范围内。

## 实际验收

- R2集成检查：**{tests['passed']}/{tests['total']}通过**，包含HTTP拒绝、跨数据集/快照、来源损坏拒绝、真实封存数字一致性、54模型加载、同一主站浏览器操作、缓存竞争与窄屏检查。
- 原有纯合成回归：**146/146通过**（谱系53、教师合成38、GIS合成23、快照32）；没有运行会读取真实教师源的旧测试套件。
- 模型层、站点结果、模型评价、空间层、科研报告、许可页、V2应用和旧元数据页面共9张浏览器截图，详见evidence/R2_BROWSER_EVIDENCE.json。
- P0–P5、WEB-R1与原v0.6共**1360个历史封存文件无变化**，八份manifest自身哈希也一致。记录位于evidence/HISTORY_BEFORE.json、HISTORY_AFTER.json与R2_HISTORY_MANIFEST_VERIFICATION.json。
- 已实际验证候选启动→精确停止→重启。Windows虚拟环境的启动器和实际监听子进程分别记录，使用UTC启动时刻防PID误认；未触及8791和8775。
- 本轮fit调用0、新推理预测0、重新评分0。只读加载已保存模型并显示已有2470条结果。

## 尚不能展示的科研内容

真实缺档重建仍为NO_ELIGIBLE_TRUE_GAPS，数量0。河段级预测为REACH_PREDICTION_NOT_AVAILABLE，reach_id/geometry保持空；不能把站点Qsim赋给相邻河段。完整河网预测还需要认证的站点—河段映射、河网拓扑与控制边界、真实河段算法输出、源快照和逐河段不确定性。

仅为公开流域有历史Q校准的月尺度径流重建，不代表无资料站预测、提前流量预报或业务级预警。V2的2016应用不是新的独立OOF；人工遮蔽不是真正历史缺档。教师锡尔河研究主线仍不具有真实训练授权。

## 发布、回滚与P6复用

完整候选代码在host/；精确差异为六个原文件的候选修改与两个新增主站模块，见R2_DEPLOYMENT_DIFF.md与evidence/HOST_SOURCE_DIFF.patch。没有覆盖历史发布。当前回滚仅需stop_host.ps1，原站不需恢复文件。

P6新Q到来时，先依法形成新的独立数据快照和run，不修改旧V1/V2成绩。复用现有统一结果契约、精确来源外键、站点模型映射、prediction_kind、公开适配器和原站视图。若新增评价，须由科研流程产生冻结指标后导入；网页不重新评分。真正缺档只有在合法模型输入、执行授权和真实run俱备时才能另注册TRUE_GAP_RECONSTRUCTION。

操作命令见R2_RUN_GUIDE.md；停止与未来发布回滚见R2_ROLLBACK_GUIDE.md。运行目录runtime与host/logs/tmp/var为可变测试运行区，不属于发布封存；其关键验收证据已经保存到evidence。
''')
write('tools/verify_delivery.py',r'''"""Verify immutable delivery files without starting services or loading observations."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parents[1];bad=[];n=0
for line in (root/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    expected,rel=line.split('  ',1);p=root/rel;n+=1
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:bad.append(rel)
print(json.dumps({'listed_files':n,'mismatches':bad,'status':'PASS' if not bad else 'FAIL'}))
raise SystemExit(bool(bad))
''')
excluded={'runtime','logs','tmp','var','__pycache__','.git'}
entries=[]
for p in sorted(R.rglob('*')):
    rel=p.relative_to(R)
    if not p.is_file() or any(part in excluded for part in rel.parts) or p==R/'SHA256SUMS.txt':continue
    entries.append((sha(p),rel.as_posix()))
write('SHA256SUMS.txt',''.join(h+'  '+n+'\n' for h,n in entries))
print(json.dumps({'sealed_files':len(entries),'tests_passed':tests['passed'],'production_display':'NOT_GRANTED','trained':0,'rescored':0},ensure_ascii=False))
