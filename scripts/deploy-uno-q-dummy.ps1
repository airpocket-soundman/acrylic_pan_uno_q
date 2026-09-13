[CmdletBinding()]
param(
    [string]$Device = "",
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$appSource = Join-Path $repoRoot "uno_q_app"
$positionModelRoot = Join-Path $repoRoot "data\position_model_400x300"
$fftModelRoot = Join-Path $repoRoot "uno_q_fft_candidates"
$cnnModelRoot = Join-Path $repoRoot "uno_q_model_candidates"

$adb = (Get-Command adb.exe -ErrorAction SilentlyContinue).Source
if (-not $adb) {
    $localPlatformTools = Join-Path $env:USERPROFILE "platform-tools\adb.exe"
    if (Test-Path -LiteralPath $localPlatformTools) { $adb = $localPlatformTools }
}
if (-not $adb) {
    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $adb = Get-ChildItem -LiteralPath $wingetRoot -Recurse -Filter adb.exe -File -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $adb) { throw "adb.exe not found. Install Google.PlatformTools first." }

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$staging = [System.IO.Path]::GetFullPath((Join-Path $tempRoot "acrylic-pan-uno-q-dummy"))
if (-not $staging.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe staging path: $staging"
}
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Copy-Item -LiteralPath $appSource -Destination $staging -Recurse
Copy-Item -LiteralPath (Join-Path $positionModelRoot "model.npz") -Destination (Join-Path $staging "python\position_model.npz")
Copy-Item -LiteralPath (Join-Path $positionModelRoot "parity_cases.npz") -Destination (Join-Path $staging "python\position_parity.npz")
Copy-Item -LiteralPath (Join-Path $positionModelRoot "model_metadata.json") -Destination (Join-Path $staging "python\position_metadata.json")
$tfliteDestination = Join-Path $staging "python\tflite_models"
New-Item -ItemType Directory -Path $tfliteDestination -Force | Out-Null
foreach ($file in "acrylic_pan_fft_hybrid_large_fp16.tflite", "acrylic_pan_fft_hybrid_standard_fp16.tflite", "acrylic_pan_temporal_fft_ensemble_fp16.tflite", "parity_cases.npz", "evaluation_report.json") {
    Copy-Item -LiteralPath (Join-Path $fftModelRoot $file) -Destination $tfliteDestination
}
Copy-Item -LiteralPath (Join-Path $cnnModelRoot "acrylic_pan_xy_gpu_fp16.tflite") -Destination $tfliteDestination
Copy-Item -LiteralPath (Join-Path $cnnModelRoot "evaluation_report.json") -Destination (Join-Path $tfliteDestination "cnn_evaluation_report.json")

$adbArgs = @()
if ($Device) { $adbArgs += @("-s", $Device) }
& $adb @adbArgs "get-state" | Out-Null

$remoteStage = "/tmp/acrylic-pan-uno-q-dummy"
$remoteApp = "/home/arduino/ArduinoApps/acrylic-pan-dummy"
& $adb @adbArgs shell "rm -rf '$remoteStage'"
& $adb @adbArgs push $staging $remoteStage
if ($LASTEXITCODE -ne 0) { throw "Failed to upload the App." }

$exists = (& $adb @adbArgs shell "if test -d '$remoteApp'; then echo yes; else echo no; fi").Trim()
if ($exists -eq "yes") {
    & $adb @adbArgs shell "TMPDIR=/tmp arduino-app-cli app stop '$remoteApp'" | Out-Null
    & $adb @adbArgs push "$staging\." "$remoteApp/"
    if ($LASTEXITCODE -ne 0) { throw "Failed to update the existing Arduino App files." }
} else {
    & $adb @adbArgs shell "TMPDIR=/tmp arduino-app-cli app new acrylic-pan-dummy --from-app '$remoteStage' --format json"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the Arduino App." }
}
& $adb @adbArgs shell "TMPDIR=/tmp arduino-app-cli app start '$remoteApp' --format json"
if ($LASTEXITCODE -ne 0) { throw "Failed to start the Arduino App." }

& $adb @adbArgs shell "docker exec -u 0 acrylic-pan-dummy-main-1 sh -lc 'apt-get update >/dev/null && apt-get install -y --no-install-recommends libfluidsynth3 >/dev/null && ldconfig && python -m pip install --no-cache-dir pyfluidsynth==1.4.0 >/dev/null && rm -rf /var/lib/apt/lists/*' && docker restart acrylic-pan-dummy-main-1 >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to provision the FluidSynth runtime." }

& $adb @adbArgs shell "docker compose -f '$remoteApp/.cache/app-compose.yaml' -f '$remoteApp/.cache/app-compose-overrides.yaml' -f '$remoteApp/camera-autoselect.compose.yaml' up -d --force-recreate --no-deps ei-video-obj-detection-runner >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to enable USB camera auto-selection." }

& $adb @adbArgs shell "docker update --restart unless-stopped acrylic-pan-dummy-main-1 acrylic-pan-dummy-ei-video-obj-detection-runner-1 >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to enable Acrylic Pan boot autostart." }

if (-not $KeepStaging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Write-Host "Acrylic Pan XY Instrument App deployed."
Write-Host "Web UI: http://<UNO-Q-IP>:8765/"
Write-Host "Logs: adb shell 'TMPDIR=/tmp arduino-app-cli app logs /home/arduino/ArduinoApps/acrylic-pan-dummy'"
