param([Parameter(Mandatory=$true)][string]$Uri,[Parameter(Mandatory=$true)][string]$OutputFile)
$ErrorActionPreference='Stop'
try { $r=Invoke-WebRequest -Uri $Uri -OutFile $OutputFile -PassThru -TimeoutSec 40; @{status=[int]$r.StatusCode;bytes=(Get-Item -LiteralPath $OutputFile).Length;url=$Uri;file=$OutputFile;sha256=(Get-FileHash -LiteralPath $OutputFile -Algorithm SHA256).Hash;tls='Windows certificate validation'}|ConvertTo-Json -Compress }
catch { @{status='FAILED';url=$Uri;error=$_.Exception.Message}|ConvertTo-Json -Compress;exit 1 }
