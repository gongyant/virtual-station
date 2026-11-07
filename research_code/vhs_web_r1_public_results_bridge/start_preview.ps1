param([int]$Port=8791)
$ErrorActionPreference='Stop'
if($Port -in @(8772,8773,8774,8775)){throw 'Original site ports are protected'}
$bridgeRoot=$PSScriptRoot
$bridgePy='E:\CodexProject\CodexProject\DeepBas-VHS-GT-Lite-v0.1\.venv\Scripts\python.exe'
if(Test-Path -LiteralPath "$bridgeRoot\runtime\server_identity.json"){
 $prior=Get-Content -LiteralPath "$bridgeRoot\runtime\server_identity.json" -Raw|ConvertFrom-Json
 $old=Get-Process -Id $prior.pid -ErrorAction SilentlyContinue
 if($old -and $old.StartTime.ToUniversalTime().Ticks -eq $prior.start_ticks){throw 'Preview is already running; use stop_preview.ps1 first'}
}
$bridgeSocket=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
try{$bridgeSocket.Start()}finally{$bridgeSocket.Stop()}
$proc=Start-Process -FilePath $bridgePy -ArgumentList @('-B',"$bridgeRoot\code\server.py",'--port',[string]$Port) -WorkingDirectory $bridgeRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput "$bridgeRoot\runtime\server.stdout.log" -RedirectStandardError "$bridgeRoot\runtime\server.stderr.log"
$identity=@{pid=$proc.Id;start_ticks=$proc.StartTime.ToUniversalTime().Ticks;port=$Port;script="$bridgeRoot\code\server.py"}
[IO.File]::WriteAllText("$bridgeRoot\runtime\server_identity.json",($identity|ConvertTo-Json),[Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText("$bridgeRoot\runtime\server.pid",[string]$proc.Id)
Write-Output "http://127.0.0.1:$Port/"
