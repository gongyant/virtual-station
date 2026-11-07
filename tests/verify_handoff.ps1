param([int]$Port = 8805)
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
$log = Join-Path $Root 'acceptance\verify_handoff.log'
New-Item -ItemType Directory -Path (Split-Path $log) -Force | Out-Null
function L($m){ $m | Tee-Object -FilePath $log -Append }

L ("VERIFY_START {0}" -f (Get-Date).ToString('o'))
$base = "http://127.0.0.1:$Port"
$fail = 0
try {
  $h = Invoke-RestMethod "$base/api/vhs/health" -TimeoutSec 5
  L ("health status={0} teacher_mounted={1}" -f $h.status, $h.r2_candidate.teacher_source_mounted)
  if ($h.status -ne 'ok') { $fail++ }
} catch { L ("health FAIL $_"); $fail++ }

foreach ($path in @('/','/static/index.html','/static/view_p89.js','/static/app.js')) {
  try {
    $r = Invoke-WebRequest -Uri ($base+$path) -UseBasicParsing -TimeoutSec 5
    L ("GET {0} -> {1} len={2}" -f $path, $r.StatusCode, $r.Content.Length)
    if ($r.StatusCode -ne 200) { $fail++ }
  } catch { L ("GET $path FAIL $_"); $fail++ }
}

foreach ($leaf in @('catalog','p8','p9a','p9b','p9c','withdrawn')) {
  try {
    $r = Invoke-RestMethod "$base/api/v6/p89/$leaf" -TimeoutSec 10
    L ("p89/$leaf keys=$([string]::Join(',', @($r.PSObject.Properties.Name | Select-Object -First 8)))")
  } catch { L ("p89/$leaf FAIL $_"); $fail++ }
}

# numeric checks
try {
  $p8 = Invoke-RestMethod "$base/api/v6/p89/p8" -TimeoutSec 10
  $len = [double]$p8.national_length_km
  L ("P8 length=$len")
  if ([math]::Abs($len - 659769.8483656237) -gt 0.01) { L 'P8_LENGTH_MISMATCH'; $fail++ }
} catch { $fail++ }

try {
  $a = Invoke-RestMethod "$base/api/v6/p89/p9a" -TimeoutSec 10
  L ("P9A 334/237/519 = {0}/{1}/{2}" -f $a.QazSu_records,$a.provisional_gauges,$a.topology_geometry_qualified)
  if ($a.QazSu_records -ne 334 -or $a.provisional_gauges -ne 237 -or $a.topology_geometry_qualified -ne 519) { $fail++ }
} catch { $fail++ }

try {
  $b = Invoke-RestMethod "$base/api/v6/p89/p9b" -TimeoutSec 10
  L ("P9B 20+10 = {0}+{1}" -f $b.original_engineering_candidates,$b.alternate_engineering_candidates)
  if ($b.original_engineering_candidates -ne 20 -or $b.alternate_engineering_candidates -ne 10) { $fail++ }
} catch { $fail++ }

try {
  $c = Invoke-RestMethod "$base/api/v6/p89/p9c" -TimeoutSec 10
  L ("P9C months={0} C0_NSE={1}" -f $c.numeric_complete_station_months,$c.E2_C0_NSE)
  if ($c.numeric_complete_station_months -ne 705) { $fail++ }
  if ([math]::Abs([double]$c.E2_C0_NSE - 0.695836401015) -gt 1e-9) { $fail++ }
} catch { $fail++ }

# restricted routes should 403
foreach ($u in @('/api/vhs/predict','/api/v6/p89/predict')) {
  try {
    $resp = Invoke-WebRequest -Uri ($base+$u) -UseBasicParsing -TimeoutSec 5 -Method GET
    L ("RESTRICT $u unexpectedly $($resp.StatusCode)"); $fail++
  } catch {
    $code = $_.Exception.Response.StatusCode.value__
    L ("RESTRICT $u -> $code")
    if ($code -ne 403 -and $code -ne 404 -and $code -ne 405) { $fail++ }
  }
}

# must not reference old ports in new pages as live redirects — soft check on index
try {
  $idx = (Invoke-WebRequest -Uri "$base/" -UseBasicParsing -TimeoutSec 5).Content
  if ($idx -match '127\.0\.0\.1:8794|127\.0\.0\.1:8795') { L 'WARN index mentions old ports (check soft)'; }
} catch {}

L ("VERIFY_FAILS=$fail")
if ($fail -eq 0) { L 'VERIFY_OK'; exit 0 } else { L 'VERIFY_BAD'; exit 2 }
