# R2 candidate wrapper; never stops a historical release.
param([int]$Port=8792)
if($Port -ne 8792){throw 'This candidate is restricted to 8792.'}
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'stop_host.ps1')
