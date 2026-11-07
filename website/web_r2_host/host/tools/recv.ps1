param([Parameter(Mandatory=$true)][string]$Rel, [Parameter(Mandatory=$true)][string]$B64File)
# Receive a gzip+base64 payload and write it inside W only (UTF-8 bytes as sent).
$ErrorActionPreference = 'Stop'
$WRoot = 'E:\VHS_WorkBuddy_S1T_Sandbox\output\sprint_w2_vhs_query_app\v0.5.1_codex_fixes'
if ([string]::IsNullOrWhiteSpace($Rel)) { throw 'empty Rel refused' }
if ([IO.Path]::IsPathRooted($Rel) -or $Rel.Contains('..') -or $Rel.Contains(':')) { throw "bad Rel $Rel" }
$dst = [IO.Path]::GetFullPath((Join-Path $WRoot $Rel))
if (-not $dst.StartsWith($WRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "outside W: $dst" }
$src = [IO.Path]::GetFullPath($B64File)
if (-not $src.StartsWith($WRoot + '\tmp\', [StringComparison]::OrdinalIgnoreCase)) { throw "b64 must be in W\tmp" }
$b = [Convert]::FromBase64String(([IO.File]::ReadAllText($src)).Trim())
$ms = New-Object IO.MemoryStream(,$b); $gz = New-Object IO.Compression.GZipStream($ms, [IO.Compression.CompressionMode]::Decompress)
$out = New-Object IO.MemoryStream; $gz.CopyTo($out); $gz.Close()
$dir = Split-Path -Parent $dst; if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null }
[IO.File]::WriteAllBytes($dst, $out.ToArray())
Remove-Item -LiteralPath $src
$sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $dst).Hash.ToLower()
"$sha  $Rel"