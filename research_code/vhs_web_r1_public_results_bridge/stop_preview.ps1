$ErrorActionPreference='Stop'
$bridgeRoot=$PSScriptRoot
$record=Get-Content -LiteralPath "$bridgeRoot\runtime\server_identity.json" -Raw|ConvertFrom-Json
if($record.port -in @(8772,8773,8774,8775)){throw 'Original site ports are protected'}
if($record.script -ne "$bridgeRoot\code\server.py"){throw 'Preview identity path mismatch'}
$proc=Get-Process -Id $record.pid -ErrorAction SilentlyContinue
if(-not $proc){Write-Output 'Preview process is not running';exit 0}
if($proc.StartTime.ToUniversalTime().Ticks -ne $record.start_ticks){throw 'PID reused; refusing to stop'}
Stop-Process -Id $record.pid
Write-Output 'Only the WEB-R1 preview process was stopped.'
