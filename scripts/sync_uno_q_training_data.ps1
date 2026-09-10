[CmdletBinding()]
param(
    [string]$Device = "",
    [string]$OutputRoot = "data\raw\mpu9250_uno_q"
)

$ErrorActionPreference = "Stop"
$repoRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputRoot))
$repoPrefix = $repoRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if (-not $resolvedOutput.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "OutputRoot must be inside the repository: $resolvedOutput"
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
$snapshot = Join-Path $resolvedOutput "snapshots\$stamp"
$latest = Join-Path $resolvedOutput "latest"
New-Item -ItemType Directory -Path (Join-Path $snapshot "training") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $snapshot "captures") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $snapshot "model") -Force | Out-Null

$remoteRoot = "/home/arduino/ArduinoApps/acrylic-pan-dummy"
$items = @(
    @{ Remote = "$remoteRoot/data/training/mpu9250_events.jsonl"; Local = "training\mpu9250_events.jsonl"; Required = $true },
    @{ Remote = "$remoteRoot/data/captures/mpu9250_events.jsonl"; Local = "captures\mpu9250_events.jsonl"; Required = $false },
    @{ Remote = "$remoteRoot/python/mpu9250_models.npz"; Local = "model\mpu9250_models.npz"; Required = $false },
    @{ Remote = "$remoteRoot/python/mpu9250_model_metadata.json"; Local = "model\mpu9250_model_metadata.json"; Required = $false }
)

foreach ($item in $items) {
    & $adb @adbArgs shell "test -f '$($item.Remote)'"
    if ($LASTEXITCODE -ne 0) {
        if ($item.Required) { throw "No labeled training data exists yet: $($item.Remote)" }
        continue
    }
    $destination = Join-Path $snapshot $item.Local
    & $adb @adbArgs pull $item.Remote $destination
    if ($LASTEXITCODE -ne 0) { throw "Failed to pull $($item.Remote)" }
}

New-Item -ItemType Directory -Path $latest -Force | Out-Null
Copy-Item -Path (Join-Path $snapshot "*") -Destination $latest -Recurse -Force
$trainingPath = Join-Path $snapshot "training\mpu9250_events.jsonl"
$lineCount = (Get-Content -LiteralPath $trainingPath | Measure-Object -Line).Lines
$manifest = [ordered]@{
    captured_at = (Get-Date).ToString("o")
    device = if ($Device) { $Device } else { "default-adb-device" }
    remote_root = $remoteRoot
    labeled_event_count = $lineCount
    snapshot = $snapshot
}
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $snapshot "snapshot.json") -Encoding utf8
$manifest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $latest "snapshot.json") -Encoding utf8

Write-Host "UNO Q training data synchronized."
Write-Host "Snapshot: $snapshot"
Write-Host "Latest:   $latest"
Write-Host "Labeled events: $lineCount"
