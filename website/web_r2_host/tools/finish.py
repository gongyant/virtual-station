"""Finalize R2 candidate implementation and operational guides; never writes historical roots."""
import difflib,hashlib,json,time
from pathlib import Path
R=Path(r'E:\VHS_Public_Baseline_Lab\vhs_web_r2_host_integration');H=R/'host'
W=Path(r'E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.6_four_layer_platform')
PY=r'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
def write(p,s): (R/p).write_text(s,encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=H/'static/view_public_results.js';s=p.read_text(encoding='utf-8')
s=s.replace("return x===null||x===undefined?'N/A':Number(x).toFixed", "return x===null||x===undefined||!Number.isFinite(Number(x))?'N/A':Number(x).toFixed")
old="function X(x){return 55+(x-xmin)*875/(xmax-xmin);}function Y(y){return 500-(y-ymin)*435/(ymax-ymin);}"
new="var scale=Math.min(875/(xmax-xmin),435/(ymax-ymin)),ox=55+(875-(xmax-xmin)*scale)/2,oy=65+(435-(ymax-ymin)*scale)/2;function X(x){return ox+(x-xmin)*scale;}function Y(y){return oy+(ymax-y)*scale;}"
s=s.replace(old,new)
s=s.replace("s+='<circle class=\"r2-mapdot ","s+='<circle data-epsg-x=\"'+p.coordinates_epsg3035[0]+'\" data-epsg-y=\"'+p.coordinates_epsg3035[1]+'\" class=\"r2-mapdot ")
# Preserve independent evaluation context even when V2 application is selected.
s=s.replace("['输入支持',cur.input_support_status||'NO_RESULTS_FOR_SELECTION']", "['V1评价状态',cur.NSE===null?'NOT_EVALUATED / NO_ELIGIBLE_TEST_SUPPORT':'GAUGE_EVALUATION_AVAILABLE'],['V1误差风险',cur.NSE!==null&&cur.NSE<0?'NEGATIVE_NSE':'未额外认证'],['输入支持',cur.input_support_status||'NO_RESULTS_FOR_SELECTION']")
p.write_text(s,encoding='utf-8')
p=H/'r2_public.py';s=p.read_text(encoding='utf-8').replace('import sys,json,os','import sys').replace('PublicResultsBridge,V06PublicResultsHook','PublicResultsBridge,V06PublicResultsHook,Refused')
while 'V06PublicResultsHook,Refused,Refused' in s:s=s.replace('V06PublicResultsHook,Refused,Refused','V06PublicResultsHook,Refused')
block='  try:self.bridge.validate_sources()\n  except Refused as e:return e.status,{"status":e.code,"prediction":None}\n'
while block+block in s:s=s.replace(block+block,block)
if 'try:self.bridge.validate_sources()' not in s:
    s=s.replace('  st,data=self.bridge.handle(', '  try:self.bridge.validate_sources()\n  except Refused as e:return e.status,{"status":e.code,"prediction":None}\n  st,data=self.bridge.handle(')
p.write_text(s,encoding='utf-8')
p=H/'server.py';s=p.read_text(encoding='utf-8')
if '"server_pid":' not in s:s=s.replace('"host_root":HERE,', '"host_root":HERE,"server_pid":os.getpid(),')
p.write_text(s,encoding='utf-8')
write('start_host.ps1',r'''# Starts only the R2 original-host candidate. No production port or teacher source.
param([string]$Python='__PY__')
$ErrorActionPreference='Stop'
$R2Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$R2Host=Join-Path $R2Root 'host'
$R2Identity=Join-Path $R2Root 'runtime\host_identity.json'
$R2Server=Join-Path $R2Host 'server.py'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Set -Python to the existing environment containing numpy and pyproj. Do not install or retrain.' }
$R2Socket=[Net.Sockets.TcpClient]::new()
try { $R2Busy=$R2Socket.ConnectAsync('127.0.0.1',8792).Wait(500) -and $R2Socket.Connected } catch { $R2Busy=$false } finally { $R2Socket.Dispose() }
if($R2Busy){
  $R2Live=Invoke-RestMethod 'http://127.0.0.1:8792/api/vhs/health' -TimeoutSec 3
  if($R2Live.r2_candidate.host_root -eq $R2Host -and $R2Live.r2_candidate.candidate_local){ 'R2 candidate already running: http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1'; exit 0 }
  throw '8792 is occupied by another service. Nothing was stopped.'
}
New-Item -ItemType Directory -Force -Path (Join-Path $R2Root 'runtime'),(Join-Path $R2Host 'logs'),(Join-Path $R2Host 'tmp') | Out-Null
$R2Stamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
$R2Proc=Start-Process -FilePath $Python -ArgumentList @('-B',('"'+$R2Server+'"'),'--port','8792','--candidate-public-preview') -WorkingDirectory $R2Host -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $R2Host "logs\host_$R2Stamp.out.log") -RedirectStandardError (Join-Path $R2Host "logs\host_$R2Stamp.err.log")
$R2Proc.Refresh()
@{launcher_pid=$R2Proc.Id;launcher_start_utc_ticks=$R2Proc.StartTime.ToUniversalTime().Ticks;port=8792;script=$R2Server;status='STARTING'} | ConvertTo-Json | Set-Content -LiteralPath $R2Identity -Encoding UTF8
$R2Ready=$false
for($R2Index=0;$R2Index -lt 40;$R2Index++){
  Start-Sleep -Milliseconds 250
  try{$R2Live=Invoke-RestMethod 'http://127.0.0.1:8792/api/vhs/health' -TimeoutSec 1;if($R2Live.r2_candidate.host_root -eq $R2Host -and -not $R2Live.r2_candidate.teacher_source_mounted){$R2Ready=$true;break}}catch{}
}
if(-not $R2Ready){throw 'Candidate failed its health check. Inspect host/logs; no unrelated service was stopped.'}
if(-not $R2Live.r2_candidate.server_pid){throw 'Server health lacks process identity. Inspect logs before stopping any process.'}
$R2Listener=Get-Process -Id ([int]$R2Live.r2_candidate.server_pid)
@{pid=$R2Listener.Id;start_utc_ticks=$R2Listener.StartTime.ToUniversalTime().Ticks;launcher_pid=$R2Proc.Id;launcher_start_utc_ticks=$R2Proc.StartTime.ToUniversalTime().Ticks;port=8792;script=$R2Server;status='RUNNING'} | ConvertTo-Json | Set-Content -LiteralPath $R2Identity -Encoding UTF8
@{event='R2_CANDIDATE_START';pid=$R2Listener.Id;launcher_pid=$R2Proc.Id;UTC=[DateTime]::UtcNow.ToString('o');port=8792;teacher_Q_mounted=$false} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $R2Root 'runtime\HOST_ATTEMPTS.jsonl') -Encoding UTF8
'R2 original v0.6 candidate: http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1'
'''.replace('__PY__',PY))
write('stop_host.ps1',r'''# Stop only the process recorded by this candidate, checking PID reuse and host identity.
$ErrorActionPreference='Stop'
$R2Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$R2Identity=Join-Path $R2Root 'runtime\host_identity.json'
if(-not(Test-Path -LiteralPath $R2Identity)){throw 'No candidate identity record; nothing stopped.'}
$R2Saved=Get-Content -LiteralPath $R2Identity -Raw | ConvertFrom-Json
$R2Expected=Join-Path $R2Root 'host\server.py'
if($R2Saved.port -ne 8792 -or $R2Saved.script -ne $R2Expected){throw 'Identity belongs to another server; refusing.'}
$R2Proc=Get-Process -Id ([int]$R2Saved.pid) -ErrorAction SilentlyContinue
if(-not $R2Proc){'Recorded R2 process is no longer running. Nothing stopped.';exit 0}
if($R2Proc.StartTime.ToUniversalTime().Ticks -ne [long]$R2Saved.start_utc_ticks){throw 'PID was reused. Refusing to stop it.'}
$R2Live=Invoke-RestMethod 'http://127.0.0.1:8792/api/vhs/health' -TimeoutSec 3
if($R2Live.r2_candidate.host_root -ne (Join-Path $R2Root 'host') -or $R2Live.r2_candidate.server_pid -ne $R2Saved.pid){throw 'Health endpoint is another host; refusing.'}
Stop-Process -Id $R2Proc.Id
$R2Launcher=Get-Process -Id ([int]$R2Saved.launcher_pid) -ErrorAction SilentlyContinue
if($R2Launcher -and $R2Launcher.Id -ne $R2Saved.pid -and $R2Launcher.StartTime.ToUniversalTime().Ticks -eq [long]$R2Saved.launcher_start_utc_ticks){Stop-Process -Id $R2Launcher.Id}
@{event='R2_CANDIDATE_STOP';pid=$R2Proc.Id;UTC=[DateTime]::UtcNow.ToString('o');port=8792} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $R2Root 'runtime\HOST_ATTEMPTS.jsonl') -Encoding UTF8
'Stopped only R2 candidate on 8792. Original 8775 and WEB-R1 8791 were not touched.'
''')
write('host/run_vhs.ps1',"# R2 candidate wrapper; original release launcher is preserved in its historical directory.\nparam([int]$Port=8792)\nif($Port -ne 8792){throw 'This candidate is restricted to 8792.'}\n& (Join-Path (Split-Path -Parent $PSScriptRoot) 'start_host.ps1')\n")
write('host/stop_vhs.ps1',"# R2 candidate wrapper; never stops a historical release.\nparam([int]$Port=8792)\nif($Port -ne 8792){throw 'This candidate is restricted to 8792.'}\n& (Join-Path (Split-Path -Parent $PSScriptRoot) 'stop_host.ps1')\n")
write('R2_ROUTE_AND_COMPONENT_MAPPING.md',r'''# 原主站中的组件与路由映射

沿用原 `host/static/index.html` 的品牌、五项一级导航、`#view`/`#side`、页面路由、卡片、表格和状态管理。没有 iframe、R1 首页复制或第二套站点选择状态。

- 研究概览 `#/overview?dataset=LAMAH_CE_PUBLIC_V1`：原概览位置显示公开成果概况和所选站点曲线。
- 模型层 `#/model?...`：54个V2保存模型及站点、版本、训练截止、参数哈希；动态执行仍走原403门禁。
- 结果层 `#/results?...`：V1/V2/人工遮蔽曲线，选定站点原V1评分与逐年结果。日期范围仅过滤曲线，不把整期评分冒称筛选期评分。
- 模型评价 `#/results/evaluation?...`：27行对照，25站有真实V1评分，611/688为N/A。
- 空间层 `#/layers?...` 或原结果层空间子页：官方EPSG:3035站点点图、V1误差/区间诊断、选定类别和月份的Qsim。点位纵横采用相同投影比例；无河段值。
- 科研报告 `#/results/report?...`：原结果层报告子页展示P4/P5报告、模型卡和许可署名。
- 数据层 `#/data?...`：三种结果来源的精确快照和发布身份。

`static/view_public_results.js` 是原 `VHS.views` 的数据集分派扩展。SYRDARYA与旧LAMAHCE仍使用原视图；候选未挂载教师源时显示明确说明。站点、模型、类别、起止月、地图模式和报告ID由同一个 `VHS.state` 与hash路由控制。

`r2_public.py` 导入冻结R1 `PublicResultsBridge` 与 `V06PublicResultsHook`。本地候选只读接口为 `/api/v6/candidate-public/catalog` 及 `/results/{station,evaluation,spatial,report}`；必须显式带 `--candidate-public-preview`，不是生产授权。正式 `/api/v6/public/*` 继续由无审批回调的原hook返回403。旧 `/api/v6/*`、`/api/vhs/*` 不由公开适配器接管。

身份为 dataset + exact snapshot + model release + station + model + prediction kind + year/month。V1评价只接受V1快照，V2应用不能送入独立评价入口。数据集切换立即清除缓存、曲线、侧栏和地图，异步响应按token和dataset双重检查后才缓存和渲染。
''')
write('R2_RUN_GUIDE.md',f'''# 运行候选主站

当前地址：http://127.0.0.1:8792/#/overview?dataset=LAMAH_CE_PUBLIC_V1

```powershell
& '{R}/start_host.ps1'
& '{PY}' -B '{R}/tools/acceptance.py'
& '{R}/stop_host.ps1'
```

8792为原v0.6候选副本的端口，不使用生产8775，也不重新制作8791预览。启动脚本只连接127.0.0.1，已运行同目录候选时直接返回；停止脚本核对PID、启动时刻、脚本路径和health主站路径，拒绝误杀其他服务。

依赖为现有Python环境（numpy、pyproj）、已安装Chrome、相邻的冻结WEB-R1代码与数据，以及P4/P5封存模型文件。模型加载验证调用既有 `p5_cli.py verify-release`，不会fit或生成新预测。测试用Chrome临时profile保存在runtime。所有原数据路径只读。

候选默认不加载教师六份CSV。SYRDARYA页说明教师源未挂载；旧适配器、权限和页面文件保留，146项原有合成回归通过。旧LAMAHCE仍展示882站元数据，不接收公开Qsim。

本地候选显示范围来自本轮用户明确指令。它没有生产display许可、签名或verified callback。普通JSON中的GRANTED/verified字段不起作用。未授权执行和Qobs导出仍403。
''')
write('R2_ROLLBACK_GUIDE.md',f'''# 恢复与回滚

本轮没有替换原发布目录，没有修改8775监听服务、R1的8791进程或P0–P5。候选运行于 `{R}/host`，因此当前回滚只需执行独立的 `stop_host.ps1`；原工程无需恢复文件。

停止脚本仅处理runtime/host_identity.json指定且启动时刻、端口和health路径均匹配的R2进程。身份不匹配会拒绝；不要使用全局按Python进程名结束命令。

未来如获准正式发布，先保存实际生产目录、启动命令、文件哈希、可信display审批记录和上一版发布指针。以独立版本切换部署，失败时切回旧指针与原启动命令。当前未确认8775活跃发布目录，因此不得把候选路径推定成生产目录，也不得直接覆盖候选原v0.6。

`evidence/HISTORY_BEFORE.json` 与 `HISTORY_AFTER.json` 记录历史封存文件哈希；`R2_DEPLOYMENT_DIFF.md` 与 `evidence/HOST_SOURCE_DIFF.patch` 是最小改动清单。候选内旧SHA256SUMS_v0.6.txt仅作原版参考，候选自身以根目录SHA256SUMS.txt为准。
''')
write('R2_PRODUCTION_PERMISSION_REQUIREMENTS.md',r'''# 尚需实际负责人确认的生产范围

1. 确认真正生产主机、发布目录、维护负责人和部署窗口；当前8775没有监听，不能证明候选路径就是实际发布路径。
2. 由有权负责人批准仅只读展示 `LAMAH_CE_PUBLIC_V1` 精确来源快照、V1独立评分、V2应用预测、ID2人工遮蔽预测、模型元数据、经验区间、站点坐标及报告署名；不包括教师Q、Qobs批量导出或模型动态执行。
3. 通过平台受信任的display机制提供可核验审批证据。当前原站只有平面权限策略，未发现已配置的公开成果可信display回调，R1 hook为None。必须由实际平台负责人提供或绑定真实审批实现；不能把普通JSON布尔、演示回调或候选命令行开关当审批。
4. 审批函数经平台校验后，才能绑定到 `V06PublicResultsHook` 的 `verified_display_permission`，只覆盖上述精确只读成果范围；生产前端API前缀才可改为 `/api/v6/public/`。本轮没有创建该回调、没有GRANTED授权。
5. 正式发布中禁用 `/api/v6/candidate-public/*`（不传本地候选开关）；继续403保护执行、教师资料和Qobs导出。模型动态推理须另行授权，不能复用display许可。

当前已获准：本轮用户要求的隔离候选本地只读验收。当前未获准：正式生产展示、生产部署及动态模型执行。
''')

def deployment_diff():
    modified=[];new=[];patch=[]
    excluded={'logs','tmp','var','__pycache__','.git'}
    for p in sorted(H.rglob('*')):
        if not p.is_file() or any(k in excluded for k in p.relative_to(H).parts):continue
        rel=p.relative_to(H);old=W/rel
        if old.is_file() and sha(old)!=sha(p):
            modified.append(rel.as_posix())
            if p.suffix in {'.py','.js','.css','.html','.ps1'}:
                patch.extend(difflib.unified_diff(old.read_text(encoding='utf-8-sig').splitlines(True),p.read_text(encoding='utf-8-sig').splitlines(True),fromfile='original/'+rel.as_posix(),tofile='candidate/'+rel.as_posix()))
        elif not old.exists():new.append(rel.as_posix())
    write('evidence/HOST_SOURCE_DIFF.patch',''.join(patch))
    write('evidence/HOST_SOURCE_DIFF.json',json.dumps({'modified':modified,'new':new,'original_files_written':0},ensure_ascii=False,indent=2))
    write('R2_DEPLOYMENT_DIFF.md','# 精确发布差异\n\n基线：'+str(W)+'\n\n候选：'+str(H)+'\n\n修改的原文件（仅候选副本）：\n\n'+''.join('- `'+p+'`\n' for p in modified)+'\n新增主站文件：\n\n'+''.join('- `'+p+'`\n' for p in new)+r'''

原始视图、平台API、教师适配器、旧权限策略均没有改写。server只增加公开模块分派与候选安全启动、教师源不挂载处理；app只扩展公开选择状态和缓存隔离；index增加第三数据集按钮与模块脚本；CSS仅加模块布局。原启动/停止脚本在候选中改为安全8792包装。

冻结R1为只读外部依赖，未复制其首页或启动8791。P4/P5代码与参数不变。补丁详见 evidence/HOST_SOURCE_DIFF.patch。

正式部署步骤：先完成R2_PRODUCTION_PERMISSION_REQUIREMENTS.md中的实际审批与生产目录确认；在独立正式版本中使用真实受信任display回调和正式API前缀，禁用候选命名空间；执行相同来源、身份与UI验收；最后由实际负责人切换正式发布指针。当前没有替生产填写回调或启动8775。
''')
deployment_diff()
print('R2 implementation and operational guides finalized')
