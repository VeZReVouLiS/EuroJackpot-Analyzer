# Keeps the Home Assistant integration repo (EuroJackpot-Analyzer-HA) in step with this app:
# copies the shared core (rules / stats / generators) + the history snapshot, runs the HA tests,
# then commits and pushes the HA repo. Called by the post-commit hook when shared files change.
# Usage:  powershell -ExecutionPolicy Bypass -File tools\sync_ha.ps1 [-NoPush]
param([string]$HaRepo = "C:\Users\DimitrisSarlis\Projects\EuroJackpot-Analyzer-HA", [switch]$NoPush)
$ErrorActionPreference = "Stop"
$app = Split-Path $PSScriptRoot -Parent
Set-Location $app
if (-not (Test-Path $HaRepo)) { Write-Host "HA repo not found: $HaRepo"; exit 0 }

& "$app\.venv\Scripts\python.exe" -m tools.sync_ha_core $HaRepo
if ($LASTEXITCODE -ne 0) { throw "sync_ha_core failed" }

Set-Location $HaRepo
if (-not (git status --porcelain)) { Write-Host "HA repo already up to date"; exit 0 }

$haPy = "$HaRepo\.venv\Scripts\python.exe"
if (Test-Path $haPy) {
    & $haPy -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "HA tests failed - not committing the sync" }
}
$sha = (git -C $app rev-parse --short HEAD)
git add -A
git commit -q -m "Sync core from EuroJackpot-Analyzer $sha"
if (-not $NoPush -and (git remote)) { git push origin HEAD }
Write-Host "HA repo synced ($sha)"
