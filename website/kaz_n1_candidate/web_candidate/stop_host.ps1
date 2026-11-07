# Stop only the process recorded by this candidate, checking PID reuse and host identity.
$ErrorActionPreference='Stop'
$R2Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$R2Identity=Join-Path $R2Root 'runtime\host_identity.json'
if(-not(Test-Path -LiteralPath $R2Identity)){throw 'No candidate identity record; nothing stopped.'}
$R2Saved=Get-Content -LiteralPath $R2Identity -Raw | ConvertFrom-Json
$R2Expected=Join-Path $R2Root 'host\server.py'
if($R2Saved.port -ne 8795 -or $R2Saved.script -ne $R2Expected){throw 'Identity belongs to another server; refusing.'}
$R2Proc=Get-Process -Id ([int]$R2Saved.pid) -ErrorAction SilentlyContinue
if(-not $R2Proc){'Recorded R2 process is no longer running. Nothing stopped.';exit 0}
if($R2Proc.StartTime.ToUniversalTime().Ticks -ne [long]$R2Saved.start_utc_ticks){throw 'PID was reused. Refusing to stop it.'}
$R2Live=Invoke-RestMethod 'http://127.0.0.1:8795/api/vhs/health' -TimeoutSec 3
if($R2Live.r2_candidate.host_root -ne (Join-Path $R2Root 'host') -or $R2Live.r2_candidate.server_pid -ne $R2Saved.pid){throw 'Health endpoint is another host; refusing.'}
Stop-Process -Id $R2Proc.Id
$R2Launcher=Get-Process -Id ([int]$R2Saved.launcher_pid) -ErrorAction SilentlyContinue
if($R2Launcher -and $R2Launcher.Id -ne $R2Saved.pid -and $R2Launcher.StartTime.ToUniversalTime().Ticks -eq [long]$R2Saved.launcher_start_utc_ticks){Stop-Process -Id $R2Launcher.Id}
@{event='R2_CANDIDATE_STOP';pid=$R2Proc.Id;UTC=[DateTime]::UtcNow.ToString('o');port=8795} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $R2Root 'runtime\HOST_ATTEMPTS.jsonl') -Encoding UTF8
'Stopped only R2 candidate on 8795. Original 8775 and WEB-R1 8791 were not touched.'
