# Builds the portable Windows app -> dist\EuroJackpotApp\EuroJackpotApp.exe
# Usage (from project root):  powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { python -m venv .venv; & $py -m pip install -r requirements.txt }

# PyInstaller empties dist\EuroJackpotApp. If the app is run from there (as developers do), its data folder (settings, tokens, tickets)
# must survive the build: keep a copy and put it back afterwards.
$dataDir = "dist\EuroJackpotApp\data"
$keep = Join-Path $env:TEMP "ejp_data_keep"
if (Test-Path $keep) { Remove-Item $keep -Recurse -Force }
if (Test-Path $dataDir) { Copy-Item $dataDir $keep -Recurse -Force }

& $py -m PyInstaller --noconfirm --clean --windowed --name EuroJackpotApp `
    --icon "$PWD\build\icon.ico" `
    --distpath dist --workpath build\work --specpath build\work `
    --add-data "$PWD\app\ui;app\ui" `
    --add-data "$PWD\app\locales;app\locales" `
    --add-data "$PWD\app\seed;app\seed" `
    --collect-submodules webview `
    --paths "$PWD" `
    run.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
if (Test-Path $keep) {
    New-Item -ItemType Directory -Force $dataDir | Out-Null
    Copy-Item "$keep\*" $dataDir -Recurse -Force
    Remove-Item $keep -Recurse -Force
}
Write-Host "Done: dist\EuroJackpotApp\EuroJackpotApp.exe"
