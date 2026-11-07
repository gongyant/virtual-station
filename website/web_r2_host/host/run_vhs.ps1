# R2 candidate wrapper; original release launcher is preserved in its historical directory.
param([int]$Port=8792)
if($Port -ne 8792){throw 'This candidate is restricted to 8792.'}
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'start_host.ps1')
