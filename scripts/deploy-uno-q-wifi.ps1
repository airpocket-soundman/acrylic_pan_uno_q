[CmdletBinding()]
param(
    [string]$Target = "arduino@uno-q.local",
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
foreach ($file in "acrylic_pan_fft_hybrid_large_fp16.tflite", "acrylic_pan_fft_hybrid_standard_fp16.tflite", "acrylic_pan_temporal_fft_ensemble_fp16.tflite", "parity_cases.npz", "evaluation_report.json") {
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

# The Arduino Python base image intentionally stays small. GeneralUser GS is
# rendered through pyFluidSynth, so provision its native ARM64 runtime in the
# newly created main container and restart only that service.
& ssh.exe @sshArgs $Target "docker exec -u 0 acrylic-pan-dummy-main-1 sh -lc 'apt-get update >/dev/null && apt-get install -y --no-install-recommends libfluidsynth3 >/dev/null && ldconfig && python -m pip install --no-cache-dir pyfluidsynth==1.4.0 >/dev/null && rm -rf /var/lib/apt/lists/*' && docker restart acrylic-pan-dummy-main-1 >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to provision the FluidSynth runtime." }

# App Lab records the camera's current /dev/videoN number in its generated
# container. Recreate only the camera service with an auto-selecting command so
# USB enumeration changes after a cold boot cannot break streaming.
$remoteCompose = "docker compose -f '$remoteApp/.cache/app-compose.yaml' -f '$remoteApp/.cache/app-compose-overrides.yaml' -f '$remoteApp/camera-autoselect.compose.yaml'"
& ssh.exe @sshArgs $Target "$remoteCompose up -d --force-recreate --no-deps ei-video-obj-detection-runner >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to enable USB camera auto-selection." }

# App Lab creates these containers with restart=no. Keep the complete appliance
# (web/inference/audio plus USB-camera stream) alive across UNO Q power cycles.
& ssh.exe @sshArgs $Target "docker update --restart unless-stopped acrylic-pan-dummy-main-1 acrylic-pan-dummy-ei-video-obj-detection-runner-1 >/dev/null"
if ($LASTEXITCODE -ne 0) { throw "Failed to enable Acrylic Pan boot autostart." }

if (-not $KeepStaging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Write-Host "Acrylic Pan deployed over Wi-Fi to $Target"
Write-Host "Web UI: http://$($Target.Split('@')[-1]):8765/"
Write-Host "Camera: http://$($Target.Split('@')[-1]):4912/embed"
Write-Host "Logs: ssh $Target arduino-app-cli app logs $remoteApp"
