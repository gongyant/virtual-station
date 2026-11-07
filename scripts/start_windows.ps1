param(
  [int]$Port = 8805,
  [string]$Python = ''
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$HostDir = Join-Path $Root 'website\kaz_n1_candidate\web_candidate\host'
$Server = Join-Path $HostDir 'server.py'
if (-not (Test-Path -LiteralPath $Server)) { throw "server.py missing: $Server" }

if (-not $Python) {
  $candidates = @(
    (Join-Path $Root 'tools\python\python.exe'),
    'E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
  )
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { $candidates += $cmd.Source }
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) { $Python = $c; break }
  }
}
if (-not $Python) { throw 'Python not found. Pass -Python path to an existing interpreter.' }
if ($Port -in 8794,8795) { throw "Refuse port $Port (reserved for original lab hosts). Use 8805+." }

$sock = New-Object System.Net.Sockets.TcpClient
try {
  $busy = $sock.ConnectAsync('127.0.0.1', $Port).Wait(400) -and $sock.Connected
} catch { $busy = $false } finally { $sock.Dispose() }
if ($busy) { throw "Port $Port busy on 127.0.0.1" }

New-Item -ItemType Directory -Path (Join-Path $HostDir 'logs') -Force | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$outLog = Join-Path $HostDir "logs\handoff_$stamp.out.log"
$errLog = Join-Path $HostDir "logs\handoff_$stamp.err.log"
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:VHS_SYR_SOURCE = ''
$sandbox = Join-Path $Root 'demo_data\runtime_sandbox'
$env:VHS_SANDBOX = $sandbox

$argList = @('-B', $Server, '--port', "$Port", '--sandbox', $sandbox, '--candidate-public-preview')
$proc = Start-Process -FilePath $Python -ArgumentList $argList -WorkingDirectory $HostDir -WindowStyle Hidden -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$ready = $false
for ($i = 0; $i -lt 50; $i++) {
  Start-Sleep -Milliseconds 400
  try {
    $h = Invoke-RestMethod "http://127.0.0.1:$Port/api/vhs/health" -TimeoutSec 2
    if ($h.status -eq 'ok') { $ready = $true; break }
  } catch {}
}
if (-not $ready) {
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  throw "Server failed to become ready. See $errLog"
}

$ident = @{
  pid = $proc.Id
  port = $Port
  url = "http://127.0.0.1:$Port/"
  host_dir = $HostDir
  started_local = (Get-Date).ToString('o')
  out_log = $outLog
  err_log = $errLog
}
$identPath = Join-Path $Root 'acceptance\running_server.json'
New-Item -ItemType Directory -Path (Split-Path $identPath) -Force | Out-Null
$ident | ConvertTo-Json | Set-Content -LiteralPath $identPath -Encoding utf8
Write-Output ("STARTED pid={0} url=http://127.0.0.1:{1}/" -f $proc.Id, $Port)
Write-Output ("LOG_OUT={0}" -f $outLog)
