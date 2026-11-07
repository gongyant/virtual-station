# R2 candidate wrapper; never stops a historical release.
param([int]$Port=8793)
if($Port -ne 8793){throw 'This candidate is restricted to 8793.'}
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'stop_host.ps1')
