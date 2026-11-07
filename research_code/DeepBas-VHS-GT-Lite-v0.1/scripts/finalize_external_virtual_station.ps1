param(
    [Parameter(Mandatory = $true)]
    [string]$DownloaderPid
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = 'E:\mamba_envs\myenv2\python.exe'
$env:PYTHONPATH = 'src;scripts'
Set-Location $projectRoot

$processIds = $DownloaderPid.Split(',') | ForEach-Object { [int]$_.Trim() }
Write-Output "Waiting for external ERA5-Land downloaders: $($processIds -join ', ')"
foreach ($processId in $processIds) {
    Wait-Process -Id $processId -ErrorAction SilentlyContinue
}

$processedRoot = 'data\processed\era5_land_external'
New-Item -ItemType Directory -Force $processedRoot | Out-Null

Write-Output 'Validating and preparing the 1999-2001 daily ERA5-Land cube'
& $python scripts\prepare_era5_land_daily.py `
    --raw-root data\raw\era5_land_external_2000_2001 `
    --start 1999-01-01 `
    --end 2001-12-01 `
    --output "$processedRoot\era5land_daily_gridded_1999_2001.nc" `
    --report "$processedRoot\validation_1999_2001.json"
if ($LASTEXITCODE -ne 0) { throw 'External ERA5-Land validation/preparation failed' }

Write-Output 'Creating cumulative BYBLK and DSK basin forcings'
& $python scripts\area_weight_era5_land.py `
    --input "$processedRoot\era5land_daily_gridded_1999_2001.nc" `
    --output "$processedRoot\era5land_daily_basin_weighted_1999_2001.nc" `
    --weights-output "$processedRoot\basin_grid_weights.csv" `
    --basins-output "$processedRoot\target_upstream_basins.geojson"
if ($LASTEXITCODE -ne 0) { throw 'External cumulative basin aggregation failed' }

Write-Output 'Creating the BYBLK-to-DSK incremental-basin forcing'
& $python scripts\area_weight_incremental_era5.py `
    --input "$processedRoot\era5land_daily_gridded_1999_2001.nc" `
    --output "$processedRoot\era5land_incremental_byblk_to_dsk_1999_2001.nc" `
    --weights-output "$processedRoot\incremental_grid_weights.csv" `
    --basin-output "$processedRoot\incremental_basin.geojson"
if ($LASTEXITCODE -ne 0) { throw 'External incremental basin aggregation failed' }

Write-Output 'Creating frozen external virtual-station predictions without target labels'
& $python scripts\predict_external_virtual_station.py `
    --upstream-input data\processed\virtual_station_external\external_input_byblk_2000_2001.csv `
    --incremental-era5 "$processedRoot\era5land_incremental_byblk_to_dsk_1999_2001.nc" `
    --parameter-summaries `
        outputs\virtual_station_mainline\next_round\donor_rolling_validation\summary.json `
        outputs\virtual_station_mainline\next_round\donor_rolling_validation_seed7\summary.json `
        outputs\virtual_station_mainline\next_round\donor_rolling_validation_seed101\summary.json `
    --evaluation-start 2000-01-01 `
    --evaluation-end 2001-12-01 `
    --output-dir outputs\virtual_station_mainline\external_2000_2001\frozen_predictions
if ($LASTEXITCODE -ne 0) { throw 'Frozen external prediction generation failed' }

Write-Output 'External prediction file is frozen. DSK labels have not been loaded.'
