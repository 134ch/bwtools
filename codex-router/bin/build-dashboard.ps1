param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ToolRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
$FrontendRoot = Join-Path $ToolRoot "upstream\frontend"
$StaticRoot = Join-Path $ToolRoot "upstream\app\static"

function Resolve-Npm {
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($npm) {
        return $npm.Source
    }

    $defaultNpm = "C:\Program Files\nodejs\npm.cmd"
    if (Test-Path $defaultNpm) {
        return $defaultNpm
    }

    throw "npm.cmd was not found. Install Node.js, then rerun this script."
}

$npmPath = Resolve-Npm
$nodeModules = Join-Path $FrontendRoot "node_modules"

if (-not $SkipInstall -and -not (Test-Path $nodeModules)) {
    Write-Output "Installing frontend dependencies..."
    & $npmPath install --no-package-lock --prefix $FrontendRoot
}

Write-Output "Building dashboard assets..."
Push-Location $FrontendRoot
try {
    & $npmPath exec vite build
} finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $StaticRoot "index.html"))) {
    throw "Dashboard build completed without producing $StaticRoot\index.html"
}

Write-Output "Dashboard assets are ready at $StaticRoot"
