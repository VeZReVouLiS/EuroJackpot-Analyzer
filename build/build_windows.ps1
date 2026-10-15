# Builds the portable Windows app -> dist\EuroJackpotApp\EuroJackpotApp.exe
# Usage (from project root):  powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv .venv; & $py -m pip install -r requirements.txt }

& $py -m PyInstaller --noconfirm --clean --windowed --name EuroJackpotApp `
    --distpath dist --workpath build\work --specpath build\work `
    --add-data "$PWD\app\ui;app\ui" `
    --add-data "$PWD\app\locales;app\locales" `
    --collect-submodules webview `
    --paths "$PWD" `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Write-Host "Done: dist\EuroJackpotApp\EuroJackpotApp.exe"
