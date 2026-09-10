[CmdletBinding()]
param(
    [string]$Device = "",
    [string]$ModelDirectory = "artifacts\mpu9250_real\latest",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$source = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $ModelDirectory))
$repoPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $source.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "ModelDirectory must be inside the repository: $source"
}
$model = Join-Path $source "mpu9250_models.npz"
$metadata = Join-Path $source "mpu9250_model_metadata.json"
if (-not (Test-Path -LiteralPath $model) -or -not (Test-Path -LiteralPath $metadata)) {
    throw "Trained model files are missing in $source"
}
$report = Get-Content -LiteralPath $metadata -Raw | ConvertFrom-Json
if (-not $Force) {
    if ($null -eq $report.validation -or
        $null -eq $report.validation.position_top1_accuracy -or
        $null -eq $report.validation.pseudo_xy_mae_mm) {
        throw "Validation metrics are missing. Use only a model produced by train_mpu9250_real_data.py."
    }
    if ($report.validation.position_top1_accuracy -lt 0.60 -or $report.validation.pseudo_xy_mae_mm -gt 60.0) {
        throw "Validation gate failed. Use -Force only after reviewing training_report.json."
    }
}

$adb = (Get-Command adb.exe -ErrorAction SilentlyContinue).Source
if (-not $adb) {
    $candidate = Join-Path $env:USERPROFILE "platform-tools\adb.exe"
    if (Test-Path -LiteralPath $candidate) { $adb = $candidate }
}
if (-not $adb) { throw "adb.exe not found" }
$adbArgs = @()
if ($Device) { $adbArgs += @("-s", $Device) }
& $adb @adbArgs get-state | Out-Null

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backup = Join-Path $repoRoot "artifacts\mpu9250_model_backups\$stamp"
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$remoteRoot = "/home/arduino/ArduinoApps/acrylic-pan-dummy"
& $adb @adbArgs shell "test -f '$remoteRoot/python/mpu9250_models.npz'"
if ($LASTEXITCODE -eq 0) {
    & $adb @adbArgs pull "$remoteRoot/python/mpu9250_models.npz" (Join-Path $backup "mpu9250_models.npz") | Out-Null
}
& $adb @adbArgs shell "test -f '$remoteRoot/python/mpu9250_model_metadata.json'"
if ($LASTEXITCODE -eq 0) {
    & $adb @adbArgs pull "$remoteRoot/python/mpu9250_model_metadata.json" (Join-Path $backup "mpu9250_model_metadata.json") | Out-Null
}

$appModel = Join-Path $repoRoot "uno_q_app\python\mpu9250_models.npz"
$appMetadata = Join-Path $repoRoot "uno_q_app\python\mpu9250_model_metadata.json"
Copy-Item -LiteralPath $appModel -Destination (Join-Path $backup "repo_mpu9250_models.npz")
Copy-Item -LiteralPath $appMetadata -Destination (Join-Path $backup "repo_mpu9250_model_metadata.json")
Copy-Item -LiteralPath $model -Destination $appModel -Force
Copy-Item -LiteralPath $metadata -Destination $appMetadata -Force

& $adb @adbArgs shell arduino-app-cli app stop $remoteRoot | Out-Null
& $adb @adbArgs push $appModel "$remoteRoot/python/mpu9250_models.npz" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to push the trained model" }
& $adb @adbArgs push $appMetadata "$remoteRoot/python/mpu9250_model_metadata.json" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Failed to push the trained model metadata" }
& $adb @adbArgs shell env -u TMPDIR arduino-app-cli app start $remoteRoot --format json
if ($LASTEXITCODE -ne 0) { throw "Failed to restart the UNO Q App" }

Write-Host "Validated real-MPU9250 model deployed."
Write-Host "Backup: $backup"
Write-Host "Model:  $($report.model)"
