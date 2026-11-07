param([string]$Root='E:\VHS_Public_Baseline_Lab\vhs_p6c_2020_validation')
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$driver=Join-Path $Root 'driver'
$configFields=@{}
foreach($line in (Get-Content -LiteralPath (Join-Path $env:USERPROFILE '.cdsapirc'))){if($line -match '^([^:]+):\s*(.*)$'){$configFields[$Matches[1].Trim()]=$Matches[2].Trim()}}
$headers=@{'PRIVATE-TOKEN'=$configFields['key']}
$api=$configFields['url'].TrimEnd('/')+'/retrieve/v1'
$tiles=Get-Content -LiteralPath (Join-Path $driver 'DOWNLOAD_TILES_FROZEN.json') -Raw|ConvertFrom-Json
foreach($tile in $tiles){
 $id=$tile.tile_id;$jobFile=Join-Path $driver ($id+'_JOB.json');$receiptFile=Join-Path $driver ($id+'_DOWNLOAD.json');$target=Join-Path $driver ($id+'_ARCO_2015_2020.zip')
 if(Test-Path -LiteralPath $receiptFile){$old=Get-Content -LiteralPath $receiptFile -Raw|ConvertFrom-Json;if($old.completed -eq $true -and (Test-Path -LiteralPath $target)){if((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -eq $old.sha256){Write-Output "$id EXISTING_VERIFIED";continue}else{throw 'EXISTING_HASH_MISMATCH'}}}
 try{
 if(-not(Test-Path -LiteralPath $jobFile)){
  $payload=@{inputs=@{variable=@('2m_temperature','total_precipitation');date=@('2015-01-01/2021-01-01');area=@($tile.area);data_format='netcdf'}}
  $body=$payload|ConvertTo-Json -Depth 8 -Compress
  $submission=Invoke-RestMethod -Uri ($api+'/processes/reanalysis-era5-land-timeseries/execution') -Method Post -Headers $headers -ContentType 'application/json' -Body $body -TimeoutSec 50
  @{tile_id=$id;submitted_utc=[DateTime]::UtcNow.ToString('o');request=$payload;submission=$submission;credential_logged=$false}|ConvertTo-Json -Depth 16|Set-Content -LiteralPath $jobFile -Encoding utf8
 }else{$submission=(Get-Content -LiteralPath $jobFile -Raw|ConvertFrom-Json).submission}
 $jobID=$submission.jobID;Write-Output "$id SUBMITTED $jobID"
 $deadline=[DateTime]::UtcNow.AddMinutes(12)
 do{
  $status=Invoke-RestMethod -Uri ($api+'/jobs/'+$jobID) -Headers $headers -TimeoutSec 40
  @{tile_id=$id;utc=[DateTime]::UtcNow.ToString('o');status=$status.status;job_id=$jobID}|ConvertTo-Json -Compress|Add-Content -LiteralPath (Join-Path $driver 'CDS_ATTEMPTS.jsonl') -Encoding utf8
  if($status.status -eq 'failed'){throw ($status|ConvertTo-Json -Depth 8 -Compress)}
  if($status.status -ne 'successful'){if([DateTime]::UtcNow -gt $deadline){throw 'CDS_POLL_DEADLINE'};Start-Sleep -Seconds 10}
 }while($status.status -ne 'successful')
 $result=Invoke-RestMethod -Uri ($api+'/jobs/'+$jobID+'/results') -Headers $headers -TimeoutSec 40
 $result|ConvertTo-Json -Depth 12|Set-Content -LiteralPath (Join-Path $driver ($id+'_RESULT.json')) -Encoding utf8
 $officialRaw=[string]$result.asset.value.'file:checksum'
 if($officialRaw -notmatch '^[0-9a-fA-F]{1,32}$'){throw 'INVALID_OFFICIAL_MD5_FORMAT'}
 $officialMd5=$officialRaw.ToLowerInvariant().PadLeft(32,'0')
 $existingValid=(Test-Path -LiteralPath $target) -and ((Get-Item -LiteralPath $target).Length -eq $result.asset.value.'file:size') -and ((Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLowerInvariant() -eq $officialMd5)
 if(-not $existingValid){
  & curl.exe --fail --silent --show-error --connect-timeout 20 --max-time 180 --output $target $result.asset.value.href
  if($LASTEXITCODE -ne 0){throw ('NATIVE_CURL_DOWNLOAD_FAILED_'+$LASTEXITCODE)}
 }
 $md5=(Get-FileHash -LiteralPath $target -Algorithm MD5).Hash.ToLowerInvariant()
 if($md5 -ne $officialMd5){throw 'OFFICIAL_MD5_MISMATCH'}
 $receipt=@{tile_id=$id;completed=$true;utc=[DateTime]::UtcNow.ToString('o');job_id=$jobID;bytes=(Get-Item -LiteralPath $target).Length;md5=$md5;sha256=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant();credential_logged=$false;standard_TLS_validation=$true;file=$target;official_result_checksum=$officialRaw;official_md5_normalized=$officialMd5;checksum_normalization='128bit hex leftpad zeros; numeric equality, not tolerance'}
 $receipt|ConvertTo-Json -Depth 12|Set-Content -LiteralPath $receiptFile -Encoding utf8
 Write-Output "$id COMPLETE $($receipt.bytes) $($receipt.sha256)"
 }catch{
 $message=$_.Exception.Message.Replace($configFields['key'],'[REDACTED]')
 @{tile_id=$id;completed=$false;utc=[DateTime]::UtcNow.ToString('o');error=$message}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $receiptFile -Encoding utf8
 Write-Output "$id BLOCKED $message";throw
 }
}
