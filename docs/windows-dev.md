# Windows Dev Setup

This project is designed to be developed with the same Python environment used by ComfyUI.

## Interpreter

Use:

`C:\StabilityMatrix\Data\Packages\ComfyUI\venv\Scripts\python.exe`

Using the runtime interpreter avoids version drift between development and node execution.

## Quick start

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\dev_setup.ps1
```

## Run tests

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_tests.ps1
```

## Launch ComfyUI

```powershell
.\launch_comfy.bat
```

## Optional overrides

Each helper script accepts `-ComfyUiRoot` if your ComfyUI folder is not `C:\StabilityMatrix\Data\Packages\ComfyUI`.

