param(
    [string]$DatasetId = "silkroute"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Split-Path -Parent $scriptDir

Set-Location $backendRoot
python scripts/run_minimal_alert.py --dataset-id $DatasetId
