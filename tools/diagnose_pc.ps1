# Diagnoses why EuroJackpotApp's native window cannot start on a PC
# ("Failed to resolve Python.Runtime.Loader.Initialize"). Read-only: changes nothing.
# Usage:  powershell -ExecutionPolicy Bypass -File diagnose_pc.ps1 -AppFolder "C:\path\to\EuroJackpotApp"
# The report is printed, saved to the Desktop (ejp-diagnose.txt) and copied to the clipboard.
param([string]$AppFolder = (Get-Location).Path)
$ErrorActionPreference = 'SilentlyContinue'
$out = New-Object System.Collections.Generic.List[string]
function H($t) { $out.Add(""); $out.Add("=== $t") }
function L($t) { $out.Add("$t") }

H 'Windows'
Get-CimInstance Win32_OperatingSystem | ForEach-Object { L "$($_.Caption) | version $($_.Version) | build $($_.BuildNumber) | $($_.OSArchitecture)" }
L ("PowerShell: " + $PSVersionTable.PSVersion + " | user: " + $env:USERNAME + " | domain-joined: " + (Get-CimInstance Win32_ComputerSystem).PartOfDomain)

H '.NET Framework (Release >= 461808 means 4.7.2 or newer; 528040+ = 4.8)'
L ("Release = " + (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\v4\Full').Release)

H 'WebView2 runtime'
$wv = @('HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
        'HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}',
        'HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}')
foreach ($k in $wv) { $v = (Get-ItemProperty $k).pv; if ($v) { L "$k -> $v" } }

H 'App folder'
L "path: $AppFolder"
$drive = (Get-Item $AppFolder).PSDrive
L ("exists: " + (Test-Path $AppFolder) + " | drive: " + $drive.Name + " | DisplayRoot: " + $drive.DisplayRoot)
L ("inside OneDrive: " + ($AppFolder -match 'OneDrive') + " | inside Downloads: " + ($AppFolder -match 'Downloads'))
$dll = Join-Path $AppFolder '_internal\pythonnet\runtime\Python.Runtime.dll'
$exe = Join-Path $AppFolder 'EuroJackpotApp.exe'
L ("exe present: " + (Test-Path $exe) + " | Python.Runtime.dll present: " + (Test-Path $dll))

H 'Blocked files (Mark of the Web / Zone.Identifier)'
$all = Get-ChildItem $AppFolder -Recurse -File
$blocked = $all | Where-Object { (Get-Item $_.FullName -Stream *).Stream -contains 'Zone.Identifier' }
L ("files: " + $all.Count + " | blocked: " + ($blocked | Measure-Object).Count)
L ("Python.Runtime.dll blocked: " + ((Get-Item $dll -Stream *).Stream -contains 'Zone.Identifier'))
L ("EuroJackpotApp.exe blocked: " + ((Get-Item $exe -Stream *).Stream -contains 'Zone.Identifier'))
L ("ZoneId: " + (Get-Content $dll -Stream Zone.Identifier | Out-String).Trim().Replace("`r`n", ' '))

H 'Python.Runtime.dll integrity / signature'
L ("SHA256: " + (Get-FileHash $dll -Algorithm SHA256).Hash + " | size: " + (Get-Item $dll).Length)
L ("Authenticode: " + (Get-AuthenticodeSignature $dll).Status)

H 'Direct load test of the DLL in this PC''s .NET Framework (what pythonnet does)'
try { [System.Reflection.Assembly]::LoadFrom($dll) | Out-Null; L 'LoadFrom: OK' }
catch { L ("LoadFrom FAILED: " + $_.Exception.Message); if ($_.Exception.InnerException) { L ("  inner: " + $_.Exception.InnerException.Message) } }

H 'Security software / policies'
$sac = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy').VerifiedAndReputablePolicyState
L "Smart App Control state (0=off, 1=on, 2=evaluation): $sac"
$mp = Get-MpComputerStatus
L ("Defender realtime: " + $mp.RealTimeProtectionEnabled + " | AV enabled: " + $mp.AntivirusEnabled)
$pref = Get-MpPreference
L ("Controlled folder access: " + $pref.EnableControlledFolderAccess + " | ASR rules: " + (($pref.AttackSurfaceReductionRules_Ids | Measure-Object).Count))
Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct | ForEach-Object { L ("AV product: " + $_.displayName) }
L ("AppLocker/SRP policy keys: " + (Test-Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\SrpV2'))
L ("VC++ runtime (vcruntime140.dll): " + (Test-Path "$env:SystemRoot\System32\vcruntime140.dll"))

H 'Existing startup log of the app'
$log = Join-Path $AppFolder 'data\startup.log'
if (Test-Path $log) { Get-Content $log -Tail 12 | ForEach-Object { L $_ } } else { L '(no data\startup.log yet)' }

$text = $out -join "`r`n"
$text | Write-Host
$desktop = [Environment]::GetFolderPath('Desktop')
$file = Join-Path $desktop 'ejp-diagnose.txt'
$text | Set-Content -Path $file -Encoding UTF8
try { $text | Set-Clipboard } catch {}
Write-Host "`nReport saved to $file and copied to the clipboard." -ForegroundColor Green
