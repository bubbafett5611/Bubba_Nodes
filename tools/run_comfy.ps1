param(
    [string]$ComfyUiRoot = "C:\StabilityMatrix\Data\Packages\ComfyUI",
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ComfyArgs
)

$ErrorActionPreference = "Stop"
$pythonExe = Join-Path $ComfyUiRoot "venv\Scripts\python.exe"
$mainPy = Join-Path $ComfyUiRoot "main.py"

if (-not (Test-Path $pythonExe)) {
    throw "ComfyUI venv python not found: $pythonExe"
}

if (-not (Test-Path $mainPy)) {
    throw "ComfyUI main.py not found: $mainPy"
}

& $pythonExe $mainPy @ComfyArgs

