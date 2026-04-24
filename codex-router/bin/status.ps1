param(
    [int]$Port = 2455
)

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$RuntimeRoot = Join-Path $ToolRoot "codex-lb-data"
$PidFile = Join-Path $RuntimeRoot "codex-lb.pid"

$pidText = $null
if (Test-Path $PidFile) {
    $pidText = (Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
}

if ($pidText) {
    Write-Output "PID file: $pidText"
    $process = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
    if ($process) {
        Write-Output "Launcher process: running"
    } else {
        Write-Output "Launcher process: not found"
    }
} else {
    Write-Output "PID file: missing"
}

try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/health/live" -TimeoutSec 3
    Write-Output "Health: $($response.StatusCode)"
} catch {
    Write-Output "Health: unavailable"
}

Write-Output "Local URL: http://127.0.0.1:$Port"
