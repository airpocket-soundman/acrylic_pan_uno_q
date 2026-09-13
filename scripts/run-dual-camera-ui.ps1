[CmdletBinding()]
param(
    [string]$Target = "arduino@uno-q.local",
    [int]$WebPort = 8765,
    [int]$CameraPort = 4912,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$ssh = Get-Command ssh.exe -ErrorAction Stop
$arguments = @(
    "-N",
    "-o", "BatchMode=yes",
    "-o", "ExitOnForwardFailure=yes",
    "-o", "ServerAliveInterval=15",
    "-o", "ServerAliveCountMax=3",
    "-L", "${WebPort}:127.0.0.1:8765",
    "-L", "${CameraPort}:127.0.0.1:4912",
    $Target
)

$tunnel = Start-Process -FilePath $ssh.Source -ArgumentList $arguments `
    -WindowStyle Hidden -PassThru

try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 50; $attempt++) {
        if ($tunnel.HasExited) {
            throw "Could not start the UNO Q Wi-Fi tunnel. Check the SSH connection and target address."
        }
        $client = [System.Net.Sockets.TcpClient]::new()
        try {
            $client.Connect("127.0.0.1", $WebPort)
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 200
        } finally {
            $client.Dispose()
        }
    }
    if (-not $ready) {
        throw "The UNO Q Web UI did not respond through the tunnel."
    }

    $url = "http://127.0.0.1:${WebPort}/instrument-probability.html"
    Write-Output "Dual camera UI: $url"
    Write-Output "Select either This PC camera or UNO Q USB camera on the page."
    if (-not $NoBrowser) { Start-Process $url }
    Wait-Process -Id $tunnel.Id
} finally {
    if (-not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id }
}
