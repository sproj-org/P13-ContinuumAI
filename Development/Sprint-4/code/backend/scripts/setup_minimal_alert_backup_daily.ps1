param(
    [string]$DatasetId = "silkroute",
    [string]$Time = "09:00",
    [string]$TaskName = "ContinuumAI-MinimalAlert-BackupDaily"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $scriptDir "run_minimal_alert_scheduled.ps1"
if (-not (Test-Path $runner)) {
    throw "Scheduled runner not found: $runner"
}

$resolvedTaskName = "$TaskName-$DatasetId"
$taskCommand = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$runner`" -DatasetId $DatasetId"

Write-Host "Creating/updating daily backup task: $resolvedTaskName"
Write-Host "Time: $Time"
Write-Host "Command: $taskCommand"

schtasks /Create /TN $resolvedTaskName /TR $taskCommand /SC DAILY /ST $Time /F | Out-String | Write-Host
if ($LASTEXITCODE -ne 0) {
    throw "Failed to create/update daily backup task '$resolvedTaskName'"
}

Write-Host "\nDaily backup task created/updated successfully."
Write-Host "Validate with: schtasks /Query /TN $resolvedTaskName /FO LIST /V"
