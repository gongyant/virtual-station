$ErrorActionPreference='Stop'
$p6bRoot='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation'
$driver=Join-Path $p6bRoot 'driver'
$configFields=@{}
foreach($line in (Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cdsapirc'))){
 if($line -match '^([^:]+):\s*(.*)$'){$configFields[$Matches[1].Trim()]=$Matches[2].Trim()}
}
$job=Get-Content -LiteralPath (Join-Path $driver 'CDS_ARCO_EXACT_FOUR_GRID_JOB.json') -Raw|ConvertFrom-Json
$jobID=$job.submission.body.jobID
$base=$configFields['url'].TrimEnd('/')+'/retrieve/v1/jobs/'+$jobID
$receipt=@{client='Windows default HTTP/TLS';utc=[DateTime]::UtcNow.ToString('o');jobID=$jobID;credential_logged=$false}
try{
 $status=Invoke-RestMethod -Uri $base -Headers @{'PRIVATE-TOKEN'=$configFields['key']} -TimeoutSec 35
 $receipt.status=$status
 if($status.status -eq 'successful'){
  $result=Invoke-RestMethod -Uri ($base+'/results') -Headers @{'PRIVATE-TOKEN'=$configFields['key']} -TimeoutSec 35
  $result|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $driver 'CDS_ARCO_EXACT_FOUR_GRID_RESULT_WINDOWS.json') -Encoding utf8
  $target=Join-Path $driver 'ERA5L_ARCO_EXACT_FOUR_GRID_2015_2020.zip'
  if(-not (Test-Path -LiteralPath $target)){
   Invoke-WebRequest -Uri $result.asset.value.href -OutFile $target -TimeoutSec 60
  }
  $actual=(Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLowerInvariant()
  if($actual -ne $result.asset.value.'file:checksum'){throw 'OFFICIAL_MD5_MISMATCH'}
  $receipt.download=@{file=$target;bytes=(Get-Item -LiteralPath $target).Length;MD5=$actual;sha256=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash}
 }
}catch{$receipt.error=$_.Exception.Message.Replace($configFields['key'],'[REDACTED]')}
$receipt|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $driver 'CDS_ARCO_WINDOWS_POLL_RESULT.json') -Encoding utf8
$receipt|ConvertTo-Json -Depth 12
