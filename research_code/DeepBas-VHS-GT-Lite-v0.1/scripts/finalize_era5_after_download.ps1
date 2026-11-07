param(
    [Parameter(Mandatory = $true)]
    [int]$DownloadProcessId,
    [string]$PythonExe = "E:\mamba_envs\myenv2\python.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot

$downloadProcess = Get-Process -Id $DownloadProcessId -ErrorAction SilentlyContinue
if ($null -ne $downloadProcess) {
    Write-Output "Waiting for ERA5-Land downloader PID $DownloadProcessId"
    Wait-Process -Id $DownloadProcessId
}

Write-Output "Downloader has stopped; starting strict full-period validation and daily processing"
& $PythonExe "scripts\prepare_era5_land_daily.py" `
    --start "1978-01-01" `
    --end "1983-12-31" `
    --output "data\processed\era5_land\era5land_daily_gridded_1978_1983.nc" `
    --report "outputs\era5_land_validation\validation_report.json"

if ($LASTEXITCODE -ne 0) {
    throw "ERA5-Land full validation or daily processing failed with exit code $LASTEXITCODE"
}

Write-Output "Full validation passed and the 2191-day gridded dataset was created"

Write-Output "Starting exact-area-weighted aggregation for BYBLK and DSK"
& $PythonExe "scripts\area_weight_era5_land.py" `
    --input "data\processed\era5_land\era5land_daily_gridded_1978_1983.nc" `
    --output "data\processed\era5_land\era5land_daily_basin_weighted_1978_1983.nc" `
    --weights-output "data\processed\era5_land\basin_grid_weights.csv" `
    --basins-output "data\processed\era5_land\target_upstream_basins.geojson"

if ($LASTEXITCODE -ne 0) {
    throw "ERA5-Land basin area weighting failed with exit code $LASTEXITCODE"
}

Write-Output "Basin area weighting passed for BYBLK and DSK"

Write-Output "Building BYBLK-to-DSK incremental-basin forcing"
& $PythonExe "scripts\area_weight_incremental_era5.py" `
    --input "data\processed\era5_land\era5land_daily_gridded_1978_1983.nc" `
    --output "data\processed\era5_land\era5land_incremental_byblk_to_dsk_1978_1983.nc" `
    --weights-output "data\processed\era5_land\incremental_grid_weights.csv" `
    --basin-output "data\processed\era5_land\incremental_basin.geojson"
if ($LASTEXITCODE -ne 0) { throw "Incremental-basin forcing failed" }

Write-Output "Preparing leakage-free formal virtual-station bundle"
& $PythonExe "scripts\prepare_virtual_station_bundle.py" `
    --basin-era5 "data\processed\era5_land\era5land_daily_basin_weighted_1978_1983.nc" `
    --incremental-era5 "data\processed\era5_land\era5land_incremental_byblk_to_dsk_1978_1983.nc" `
    --output "data\processed\virtual_station\virtual_station_bundle_1978_1983.npz" `
    --metadata "data\processed\virtual_station\bundle_metadata.json"
if ($LASTEXITCODE -ne 0) { throw "Virtual-station bundle preparation failed" }

Write-Output "Evaluating formal physical routing baselines"
& $PythonExe "scripts\evaluate_strict_baselines.py" `
    --bundle "data\processed\virtual_station\virtual_station_bundle_1978_1983.npz" `
    --train-end-date "1981-12-31" `
    --validation-end-date "1982-12-31" `
    --diagnostic-lags "1,3,5,7,14" `
    --gnn-predictions "outputs\virtual_station_mainline\formal\not_available.csv" `
    --output-dir "outputs\virtual_station_mainline\formal\strict_physical_baselines"
if ($LASTEXITCODE -ne 0) { throw "Formal physical baselines failed" }

Write-Output "Calibrating donor-only conceptual runoff model and transferring it to the incremental basin"
& $PythonExe "scripts\evaluate_donor_physical_model.py" `
    --basin-era5 "data\processed\era5_land\era5land_daily_basin_weighted_1978_1983.nc" `
    --incremental-era5 "data\processed\era5_land\era5land_incremental_byblk_to_dsk_1978_1983.nc" `
    --train-end "1981-12-31" `
    --validation-end "1982-12-31" `
    --output-dir "outputs\virtual_station_mainline\formal\donor_physical_model"
if ($LASTEXITCODE -ne 0) { throw "Formal donor physical model failed" }

Write-Output "Training formal no-graph, directed, climate, routed, and physics models"
$formalConfigs = @(
    "configs\mainline_formal_nograph.yaml",
    "configs\mainline_formal_graph.yaml",
    "configs\mainline_formal_graph_climate.yaml",
    "configs\mainline_formal_routed.yaml",
    "configs\mainline_formal_physics.yaml"
)
foreach ($config in $formalConfigs) {
    & $PythonExe -m vhs.train --config $config
    if ($LASTEXITCODE -ne 0) { throw "Formal model training failed: $config" }
}

& $PythonExe "scripts\summarize_virtual_station_mainline.py" `
    --root "outputs\virtual_station_mainline\formal" `
    --train-start "1978-01-31" `
    --train-end "1981-12-31" `
    --validation-start "1982-01-01" `
    --validation-end "1982-12-31"
if ($LASTEXITCODE -ne 0) { throw "Formal mainline summary failed" }
Write-Output "Formal strict virtual-station mainline completed"

Write-Output "Starting auxiliary hydrometeorological snowmelt diagnostic (not a virtual-station ranking experiment)"
& $PythonExe "scripts\evaluate_era5_snowmelt_ablation.py" `
    --era5 "data\processed\era5_land\era5land_daily_basin_weighted_1978_1983.nc" `
    --flows "data\processed\timeseries.csv" `
    --station-id "00705700" `
    --train-end "1981-12-31" `
    --validation-end "1982-12-31" `
    --output-dir "outputs\auxiliary_era5_snowmelt_ablation"

if ($LASTEXITCODE -ne 0) {
    throw "Auxiliary ERA5-Land snowmelt diagnostic failed with exit code $LASTEXITCODE"
}

Write-Output "Auxiliary snowmelt diagnostic completed"
