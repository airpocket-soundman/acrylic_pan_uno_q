[CmdletBinding()]
param(
    [int]$Port = 8765,
    [switch]$NoBrowser
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$arguments = @("-m", "pc.uno_q_web", "--port", $Port)
if ($NoBrowser) { $arguments += "--no-browser" }
Push-Location $repoRoot
try {
    & python @arguments
} finally {
    Pop-Location
}
