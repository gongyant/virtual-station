# Starts only the WEB-S1 original-host candidate. No production port or teacher source.
param([string]$Python='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe')
$ErrorActionPreference='Stop'
$R2Root=Split-Path -Parent $MyInvocation.MyCommand.Path
$R2Host=Join-Path $R2Root 'host'
$R2Identity=Join-Path $R2Root 'runtime\host_identity.json'
$R2Server=Join-Path $R2Host 'server.py'
if (-not (Test-Path -LiteralPath $Python)) { throw 'Set -Python to the existing environment containing numpy and pyproj. Do not install or retrain.' }
$R2Socket=[Net.Sockets.TcpClient]::new()
try { $R2Busy=$R2Socket.ConnectAsync('127.0.0.1',8794).Wait(500) -and $R2Socket.Connected } catch { $R2Busy=$false } finally { $R2Socket.Dispose() }
if($R2Busy){
  $R2Live=Invoke-RestMethod 'http://127.0.0.1:8794/api/vhs/health' -TimeoutSec 3
  if($R2Live.r2_candidate.host_root -eq $R2Host -and $R2Live.r2_candidate.candidate_local){ 'R2 candidate already running: http://127.0.0.1:8794/#/overview?dataset=LAMAH_CE_PUBLIC_V1'; exit 0 }
  throw '8794 is occupied by another service. Nothing was stopped.'
}
New-Item -ItemType Directory -Force -Path (Join-Path $R2Root 'runtime'),(Join-Path $R2Host 'logs'),(Join-Path $R2Host 'tmp') | Out-Null
$R2Stamp=Get-Date -Format 'yyyyMMddTHHmmssfff'
$R2Proc=Start-Process -FilePath $Python -ArgumentList @('-B',('"'+$R2Server+'"'),'--port','8794','--candidate-public-preview') -WorkingDirectory $R2Host -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $R2Host "logs\host_$R2Stamp.out.log") -RedirectStandardError (Join-Path $R2Host "logs\host_$R2Stamp.err.log")
$R2Proc.Refresh()
@{launcher_pid=$R2Proc.Id;launcher_start_utc_ticks=$R2Proc.StartTime.ToUniversalTime().Ticks;port=8794;script=$R2Server;status='STARTING'} | ConvertTo-Json | Set-Content -LiteralPath $R2Identity -Encoding UTF8
$R2Ready=$false
for($R2Index=0;$R2Index -lt 40;$R2Index++){
  Start-Sleep -Milliseconds 250
  try{$R2Live=Invoke-RestMethod 'http://127.0.0.1:8794/api/vhs/health' -TimeoutSec 1;if($R2Live.r2_candidate.host_root -eq $R2Host -and -not $R2Live.r2_candidate.teacher_source_mounted){$R2Ready=$true;break}}catch{}
}
if(-not $R2Ready){throw 'Candidate failed its health check. Inspect host/logs; no unrelated service was stopped.'}
if(-not $R2Live.r2_candidate.server_pid){throw 'Server health lacks process identity. Inspect logs before stopping any process.'}
$R2Listener=Get-Process -Id ([int]$R2Live.r2_candidate.server_pid)
@{pid=$R2Listener.Id;start_utc_ticks=$R2Listener.StartTime.ToUniversalTime().Ticks;launcher_pid=$R2Proc.Id;launcher_start_utc_ticks=$R2Proc.StartTime.ToUniversalTime().Ticks;port=8794;script=$R2Server;status='RUNNING'} | ConvertTo-Json | Set-Content -LiteralPath $R2Identity -Encoding UTF8
@{event='R2_CANDIDATE_START';pid=$R2Listener.Id;launcher_pid=$R2Proc.Id;UTC=[DateTime]::UtcNow.ToString('o');port=8794;teacher_Q_mounted=$false} | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $R2Root 'runtime\HOST_ATTEMPTS.jsonl') -Encoding UTF8
'WEB-S1 original v0.6 candidate: http://127.0.0.1:8794/#/overview?dataset=LAMAH_CE_PUBLIC_V1'
