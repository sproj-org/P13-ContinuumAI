param(
    [string]$DatasetId = "silkroute",
    [int]$EveryMinutes = 60,
    [string]$TaskName = "ContinuumAI-MinimalAlert"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($EveryMinutes -lt 1) {
    throw "EveryMinutes must be >= 1"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendRoot = Split-Path -Parent $scriptDir
$scheduledRunner = Join-Path $scriptDir "run_minimal_alert_scheduled.ps1"

if (-not (Test-Path $scheduledRunner)) {
    throw "Scheduled runner script not found: $scheduledRunner"
}

$resolvedTaskName = "$TaskName-$DatasetId"

# Run without --force so email is sent only when there is a true critical status transition.
$taskCommand = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$scheduledRunner`" -DatasetId $DatasetId"

Write-Host "Creating/updating scheduled task: $resolvedTaskName"
Write-Host "Interval (minutes): $EveryMinutes"
Write-Host "Command: $taskCommand"

schtasks /Create /TN $resolvedTaskName /TR $taskCommand /SC MINUTE /MO $EveryMinutes /F | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create/update task '$resolvedTaskName'"
}

Write-Host "\nTask created/updated successfully."
Write-Host "Validate with: schtasks /Query /TN $resolvedTaskName /FO LIST /V"
