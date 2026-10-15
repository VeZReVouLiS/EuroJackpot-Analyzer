# Builds a release and publishes it on GitHub (needs: gh auth login, GITHUB_REPO set in app\version.py).
# Usage (project root):  powershell -ExecutionPolicy Bypass -File build\release.ps1 [-SkipSeed] [-NoPublish]
param([switch]$SkipSeed, [switch]$NoPublish)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$py = ".\.venv\Scripts\python.exe"
$gh = if (Get-Command gh -ErrorAction SilentlyContinue) { "gh" } else { "C:\Program Files\GitHub CLI\gh.exe" }

$version = (& $py -c "from app.version import __version__ as v; print(v)").Trim()
$repo = (& $py -c "from app.version import GITHUB_REPO as r; print(r)").Trim()
if (-not $repo) { throw "Set GITHUB_REPO in app\version.py first" }
$tag = "v$version"
Write-Host "Releasing $tag to $repo"

& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }
if (-not $SkipSeed) { & $py -m tools.make_seed; if ($LASTEXITCODE -ne 0) { throw "seed failed" } }
powershell -ExecutionPolicy Bypass -File build\build_windows.ps1
if ($LASTEXITCODE -ne 0) { throw "build failed" }

$zip = "dist\EuroJackpotApp-portable-win.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\EuroJackpotApp -DestinationPath $zip
$hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
"$hash  EuroJackpotApp-portable-win.zip" | Set-Content -Encoding ascii "$zip.sha256"
Write-Host "sha256 $hash"
if ($NoPublish) { Write-Host "Built (not published): $zip"; exit 0 }

# release notes = the CHANGELOG section of this version
$log = [System.IO.File]::ReadAllText((Resolve-Path CHANGELOG.md), [System.Text.Encoding]::UTF8)   # explicit UTF-8 (PS 5.1 defaults to ANSI -> mojibake)
$m = [regex]::Match($log, "(?ms)^## \[?$([regex]::Escape($version))\]?.*?\r?\n(.*?)(?=^## |\z)")
$notes = if ($m.Success) { $m.Groups[1].Value.Trim() } else { "Release $version" }
$notesFile = New-TemporaryFile
[System.IO.File]::WriteAllText($notesFile.FullName, $notes, (New-Object System.Text.UTF8Encoding($false)))

git push origin HEAD
if (-not (git tag -l $tag)) { git tag -a $tag -m "Release $tag" }
git push origin $tag
& $gh release create $tag $zip "$zip.sha256" --repo $repo --title "EuroJackpot Analyzer $version" --notes-file $notesFile
Write-Host "Published: https://github.com/$repo/releases/tag/$tag"
