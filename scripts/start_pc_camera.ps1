$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$server = Join-Path $PSScriptRoot "pc_camera_server.py"
$state = Join-Path $root ".local\pc-camera"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Camera environment is missing. Create .venv and install opencv-python first."
}
New-Item -ItemType Directory -Force -Path $state | Out-Null
$pidPath = Join-Path $state "server.pid"
if (Test-Path -LiteralPath $pidPath) {
    $existingPid = [int](Get-Content -LiteralPath $pidPath)
    if (Get-Process -Id $existingPid -ErrorAction SilentlyContinue) {
        Write-Output "PC camera server is already running (PID $existingPid)."
        exit 0
    }
}
$process = Start-Process -FilePath $python -ArgumentList @($server, "--port", "8878") `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $state "stdout.log") `
    -RedirectStandardError (Join-Path $state "stderr.log")
Set-Content -LiteralPath $pidPath -Value $process.Id
Write-Output "PC camera server started: http://192.168.50.177:8878/ (PID $($process.Id))"
