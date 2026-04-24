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
    & $pythonExe -m pip install --upgrade pip
    & $pythonExe -m pip install -e ".[dev]"
    & $pythonExe -m pre_commit install
    Write-Host "Dev setup complete using $pythonExe"
}
finally {
    Pop-Location
}

