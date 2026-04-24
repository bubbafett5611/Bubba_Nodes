param(
    [string]$ComfyUiRoot = "C:\StabilityMatrix\Data\Packages\ComfyUI"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$pythonExe = Join-Path $ComfyUiRoot "venv\Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
    throw "ComfyUI venv python not found: $pythonExe"
}

Push-Location $projectRoot
try {
    & $pythonExe -m pytest
}
finally {
    Pop-Location
}

