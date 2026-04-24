param(
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 2455,
    [switch]$Public,
    [switch]$NoWait
)

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$UpstreamRoot = Join-Path $ToolRoot "upstream"
$RuntimeRoot = Join-Path $ToolRoot "codex-lb-data"
$PidFile = Join-Path $RuntimeRoot "codex-lb.pid"
$OutLog = Join-Path $RuntimeRoot "codex-lb.out.log"
$ErrLog = Join-Path $RuntimeRoot "codex-lb.err.log"

if ($Public) {
    $HostAddress = "0.0.0.0"
}

New-Item -ItemType Directory -Force -Path $RuntimeRoot | Out-Null

function Resolve-Uv {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        return $uv.Source
    }

    $userUv = Join-Path $env:APPDATA "Python\Python314\Scripts\uv.exe"
    if (Test-Path $userUv) {
        return $userUv
    }

    throw "uv.exe was not found. Install it with: python -m pip install --user uv"
}

function Test-ProcessAlive {
    param([int]$ProcessId)
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

if (Test-Path $PidFile) {
    $existingPidText = (Get-Content -Path $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
    $existingPid = 0
    if ([int]::TryParse($existingPidText, [ref]$existingPid) -and (Test-ProcessAlive -ProcessId $existingPid)) {
        Write-Output "codex-lb already appears to be running with launcher PID $existingPid."
        Write-Output "Use codex-router\bin\stop.ps1 before starting another instance."
        exit 0
    }
}

$uvPath = Resolve-Uv
$dbPath = (Join-Path $RuntimeRoot "store.db").Replace("\", "/")
$keyPath = Join-Path $RuntimeRoot "encryption.key"

$env:CODEX_LB_DATABASE_URL = "sqlite+aiosqlite:///$dbPath"
$env:CODEX_LB_ENCRYPTION_KEY_FILE = $keyPath
$env:UV_FROZEN = "1"

$process = Start-Process `
    -FilePath $uvPath `
    -ArgumentList @("run", "--frozen", "codex-lb", "--host", $HostAddress, "--port", "$Port") `
    -WorkingDirectory $UpstreamRoot `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -PassThru

Set-Content -Path $PidFile -Value $process.Id -Encoding ASCII

if (-not $NoWait) {
    $ready = $false
    $healthUrl = "http://127.0.0.1:$Port/health/live"
    for ($i = 0; $i -lt 40; $i++) {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) {
            break
        }
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $healthUrl -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # Keep waiting until the server is ready or the process exits.
        }
    }

    if (-not $ready) {
        Write-Output "Started codex-lb launcher PID $($process.Id), but health was not ready yet."
        Write-Output "Check logs under $RuntimeRoot."
        exit 1
    }
}

Write-Output "codex-lb is running."
Write-Output "Launcher PID: $($process.Id)"
Write-Output "Local URL: http://127.0.0.1:$Port"
if ($HostAddress -eq "0.0.0.0") {
    Write-Output "Tailnet/LAN URL: http://<this-machine-ip>:$Port"
}
Write-Output "Logs: $RuntimeRoot"
