[CmdletBinding()]
param(
    [string]$Target = "arduino@192.168.101.85",
    [string]$IdentityFile = "$env:USERPROFILE\.ssh\id_ed25519",
    [switch]$SkipCameraCheck,
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$appSource = Join-Path $repoRoot "uno_q_app"
$positionModelRoot = Join-Path $repoRoot "data\position_model_400x300"
$fftModelRoot = Join-Path $repoRoot "uno_q_fft_candidates"
$cnnModelRoot = Join-Path $repoRoot "uno_q_model_candidates"
$remoteApp = "/home/arduino/ArduinoApps/acrylic-pan-dummy"

foreach ($command in "ssh.exe", "scp.exe") {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command not found. Install the Windows OpenSSH client."
    }
}
if (-not (Test-Path -LiteralPath $IdentityFile)) { throw "SSH identity file not found: $IdentityFile" }

$sshArgs = @("-i", $IdentityFile, "-o", "BatchMode=yes", "-o", "ConnectTimeout=8")
& ssh.exe @sshArgs $Target "true"
if ($LASTEXITCODE -ne 0) { throw "UNO Q Wi-Fi SSH connection failed: $Target" }

if (-not $SkipCameraCheck) {
    $cameraNames = & ssh.exe @sshArgs $Target "v4l2-ctl --list-devices 2>/dev/null | grep -v 'Qualcomm Venus' | grep -E 'USB|Camera|Webcam|UVC' || true"
    if (-not ($cameraNames -join "").Trim()) {
        throw "No UVC camera was found on the UNO Q. Connect the externally powered USB-C hub and camera, then retry."
    }
}

$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$staging = [System.IO.Path]::GetFullPath((Join-Path $tempRoot "acrylic-pan-uno-q-wifi"))
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
foreach ($file in "acrylic_pan_fft_hybrid_standard_fp16.tflite", "acrylic_pan_temporal_fft_ensemble_fp16.tflite", "parity_cases.npz", "evaluation_report.json") {
    Copy-Item -LiteralPath (Join-Path $fftModelRoot $file) -Destination $tfliteDestination
}
Copy-Item -LiteralPath (Join-Path $cnnModelRoot "acrylic_pan_xy_gpu_fp16.tflite") -Destination $tfliteDestination
Copy-Item -LiteralPath (Join-Path $cnnModelRoot "evaluation_report.json") -Destination (Join-Path $tfliteDestination "cnn_evaluation_report.json")

& ssh.exe @sshArgs $Target "mkdir -p '$remoteApp' && arduino-app-cli app stop '$remoteApp' >/dev/null 2>&1 || true"
foreach ($item in Get-ChildItem -LiteralPath $staging) {
    & scp.exe -i $IdentityFile -o BatchMode=yes -r -- $item.FullName "${Target}:$remoteApp/"
    if ($LASTEXITCODE -ne 0) { throw "Failed to upload $($item.Name)." }
}

# Starting also compiles/uploads the STM32 sketch and provisions the official
# camera brick. Keep this foreground operation alive until App Lab reports done.
& ssh.exe @sshArgs $Target "env -u TMPDIR arduino-app-cli app start '$remoteApp' --format json"
if ($LASTEXITCODE -ne 0) { throw "Failed to start the Acrylic Pan app." }

if (-not $KeepStaging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Write-Host "Acrylic Pan deployed over Wi-Fi to $Target"
Write-Host "Web UI: http://$($Target.Split('@')[-1]):8765/"
Write-Host "Camera: http://$($Target.Split('@')[-1]):4912/embed"
Write-Host "Logs: ssh $Target arduino-app-cli app logs $remoteApp"
