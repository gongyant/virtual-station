$ErrorActionPreference='Stop'
$dest='E:\VHS_Public_Baseline_Lab\vhs_p6b_external_validation\external'
$jobs=@(
 @{url='https://ehyd.gv.at/';name='ehyd_home.html'},
 @{url='https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048&file=1';name='ehyd_200048_file1.txt'},
 @{url='https://ehyd.gv.at/services/MessstellenExtraData/owf?id=200048';name='ehyd_200048_listing.txt'},
 @{url='https://wasser.gv.at/hydjb/';name='hydjb.html'}
)
$receipts=foreach($job in $jobs){
 try{$path=Join-Path $dest $job.name; $res=Invoke-WebRequest -Uri $job.url -OutFile $path -PassThru -TimeoutSec 30; [pscustomobject]@{url=$job.url;file=$job.name;status=[int]$res.StatusCode;bytes=(Get-Item -LiteralPath $path).Length;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash;tls='Windows default certificate validation'}}
 catch{[pscustomobject]@{url=$job.url;status='FAILED';error=$_.Exception.Message}}
}
$receipts|ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $dest 'WINDOWS_TLS_PROBE.json') -Encoding utf8
$receipts|ConvertTo-Json -Depth 5
