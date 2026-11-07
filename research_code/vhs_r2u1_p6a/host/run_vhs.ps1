# R2 candidate wrapper; original release launcher is preserved in its historical directory.
param([int]$Port=8793)
if($Port -ne 8793){throw 'This candidate is restricted to 8793.'}
& (Join-Path (Split-Path -Parent $PSScriptRoot) 'start_host.ps1')
