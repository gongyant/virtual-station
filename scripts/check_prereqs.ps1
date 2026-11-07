$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$need = @(
  'website\kaz_n1_candidate\web_candidate\host\server.py',
  'website\kaz_n1_candidate\web_candidate\host\static\index.html',
  'website\kaz_n1_candidate\web_candidate\host\static\view_p89.js',
  'website\kaz_n1_candidate\web_candidate\host\p89_evidence.py',
  'results\p8\P8_FINAL_STATUS.json',
  'results\p9a\P9A_FINAL_STATUS.json',
  'results\p9b\P9B_FINAL_STATUS.json',
  'results\p9c\P9C_FINAL_STATUS.json',
  'results\p9c\e2_valid\E2_TEMPORAL_METRICS.csv'
)
$miss = @()
foreach ($r in $need) {
  if (-not (Test-Path -LiteralPath (Join-Path $Root $r))) { $miss += $r }
}
if ($miss.Count) {
  Write-Output 'PREREQ_FAIL'
  $miss | ForEach-Object { Write-Output $_ }
  exit 1
}
Write-Output 'PREREQ_OK'
Write-Output ("ROOT={0}" -f $Root)
exit 0
