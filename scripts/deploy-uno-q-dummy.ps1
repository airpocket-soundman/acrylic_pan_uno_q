[CmdletBinding()]
param(
    [string]$Device = "",
    [switch]$KeepStaging
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$appSource = Join-Path $repoRoot "uno_q_app"
$modelSource = Join-Path $repoRoot "data\dummy_model_12class\model.npz"
$goldenSource = Join-Path $repoRoot "data\dummy_model_12class\golden_outputs.json"

$adb = (Get-Command adb.exe -ErrorAction SilentlyContinue).Source
if (-not $adb) {
    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    $adb = Get-ChildItem -LiteralPath $wingetRoot -Recurse -Filter adb.exe -File -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $adb) { throw "adb.exe not found. Install Google.PlatformTools first." }

$staging = Join-Path ([System.IO.Path]::GetTempPath()) "acrylic-pan-uno-q-dummy"
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Copy-Item -LiteralPath $appSource -Destination $staging -Recurse
Copy-Item -LiteralPath $modelSource -Destination (Join-Path $staging "python\model.npz")
Copy-Item -LiteralPath $goldenSource -Destination (Join-Path $staging "python\golden_outputs.json")

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
    & $adb @adbArgs shell arduino-app-cli app stop $remoteApp | Out-Null
    & $adb @adbArgs push "$staging\." "$remoteApp/"
    if ($LASTEXITCODE -ne 0) { throw "Failed to update the existing Arduino App files." }
} else {
    & $adb @adbArgs shell "arduino-app-cli app new acrylic-pan-dummy --from-app '$remoteStage' --format json"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create the Arduino App." }
}
& $adb @adbArgs shell env -u TMPDIR arduino-app-cli app start $remoteApp --format json
if ($LASTEXITCODE -ne 0) { throw "Failed to start the Arduino App." }

if (-not $KeepStaging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Write-Host "Acrylic Pan dummy App deployed."
Write-Host "Logs: adb shell env -u TMPDIR arduino-app-cli app logs /home/arduino/ArduinoApps/acrylic-pan-dummy"
