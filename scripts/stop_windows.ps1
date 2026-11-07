$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$identPath = Join-Path $Root 'acceptance\running_server.json'
if (Test-Path -LiteralPath $identPath) {
  $j = Get-Content -LiteralPath $identPath -Raw -Encoding utf8 | ConvertFrom-Json
  if ($j.pid) {
    Stop-Process -Id ([int]$j.pid) -Force -ErrorAction SilentlyContinue
    Write-Output ("STOPPED pid={0}" -f $j.pid)
  }
  Remove-Item -LiteralPath $identPath -Force -ErrorAction SilentlyContinue
} else {
  Write-Output 'No acceptance/running_server.json; nothing stopped.'
}
