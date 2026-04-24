param(
    [int]$ProcessId
)

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$RuntimeRoot = Join-Path $ToolRoot "codex-lb-data"
$PidFile = Join-Path $RuntimeRoot "codex-lb.pid"

if (-not $ProcessId -and (Test-Path $PidFile)) {
    $pidText = (Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    [void][int]::TryParse($pidText, [ref]$ProcessId)
}

if (-not $ProcessId) {
    Write-Output "No codex-lb PID file found. Nothing stopped."
    exit 0
}

$process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
    Write-Output "codex-lb launcher PID $ProcessId is not running."
    exit 0
}

taskkill /PID $ProcessId /T /F | Out-Null
Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
Write-Output "Stopped codex-lb process tree for launcher PID $ProcessId."
