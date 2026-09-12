[CmdletBinding()]
param(
    [string]$Python = "python",
    [switch]$LiveBrowser
)
# Execute on Windows, explicitly. All installations and intermediates are repo-local.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$Work = Join-Path $Root "dist\pass08-host"
$Receipt = Join-Path $Root "artifacts\pass-08\windows-host.json"
New-Item -ItemType Directory -Force -Path $Work, (Split-Path $Receipt) | Out-Null
$Results = [System.Collections.Generic.List[object]]::new()
$EnvironmentBefore = @{}
foreach ($Key in @("TEMP", "TMP", "PIP_CACHE_DIR", "PYTHONDONTWRITEBYTECODE", "HOME", "USERPROFILE", "LOCALAPPDATA", "XDG_CACHE_HOME")) {
    $EnvironmentBefore[$Key] = [Environment]::GetEnvironmentVariable($Key, "Process")
}
function Invoke-Checked([string]$Name, [string]$Exe, [string[]]$Arguments) {
    $Log = Join-Path $Work ($Name + ".log")
    & $Exe @Arguments *> $Log
    $Code = $LASTEXITCODE
    $Results.Add(@{ check = $Name; exit_code = $Code; log = $Log })
    if ($Code -ne 0) { throw "$Name failed (exit $Code). See $Log" }
}
$Success = $false
$Failure = $null
Push-Location $Root
try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw "This qualifier requires Windows." }
    $Temp = Join-Path $Work "tmp"
    New-Item -ItemType Directory -Force -Path $Temp | Out-Null
    $env:TEMP = $Temp; $env:TMP = $Temp
    foreach ($Key in @("HOME", "USERPROFILE", "LOCALAPPDATA", "XDG_CACHE_HOME")) {
        $Owned = Join-Path $Work $Key.ToLowerInvariant()
        New-Item -ItemType Directory -Force -Path $Owned | Out-Null
        [Environment]::SetEnvironmentVariable($Key, $Owned, "Process")
    }
    $env:PIP_CACHE_DIR = Join-Path $Work "pip-cache"
    $env:PYTHONDONTWRITEBYTECODE = "1"
    $Venv = Join-Path $Work "source-venv"
    Invoke-Checked "venv" $Python @("-m", "venv", $Venv)
    $Py = Join-Path $Venv "Scripts\python.exe"
    Invoke-Checked "declared-dependencies" $Py @("-m", "pip", "install", "build", "wheel", ".[api,dev]")
    Invoke-Checked "dependency-consistency" $Py @("-m", "pip", "check")
    Invoke-Checked "focused-tests" $Py @("-m", "pytest", "tests/test_pass08_desktop_release.py", "tests/test_pass07_nh_evaluation_hardening.py", "tests/test_pass06_nh_legal_behavior.py", "--basetemp", (Join-Path $Work "pytest"), "-ra")
    $WheelDir = Join-Path $Work "wheels"
    Invoke-Checked "wheel-build" $Py @("-m", "build", "--wheel", "--outdir", $WheelDir)
    $Wheel = Get-ChildItem -Path $WheelDir -Filter "nh_family_law_llm-8.0.10-*.whl" | Select-Object -First 1
    if (-not $Wheel) { throw "Current wheel was not built." }
    Invoke-Checked "source-wheel-gate" $Py @("scripts/verify_pass_08.py", "--wheel", $Wheel.FullName)
    $Isolated = Join-Path $Work "installed-venv"
    Invoke-Checked "isolated-venv" $Py @("-m", "venv", $Isolated)
    $InstalledPy = Join-Path $Isolated "Scripts\python.exe"
    Invoke-Checked "wheel-dependencies" $InstalledPy @("-m", "pip", "install", ($Wheel.FullName + "[api]"))
    Invoke-Checked "wheel-pip-check" $InstalledPy @("-m", "pip", "check")
    $JourneyArgs = @("scripts/qualify_nh_desktop.py", "--installed", "--python", $InstalledPy, "--work-dir", (Join-Path $Work "installed-journey"), "--output", (Join-Path $Work "installed-journey.json"))
    if ($LiveBrowser) {
        Invoke-Checked "browser-tools" $Py @("-m", "pip", "install", "playwright")
        # Requires an already approved/installed Chromium browser on this host.
        $JourneyArgs += "--browser"
    }
    Invoke-Checked "installed-live-http" $Py $JourneyArgs
    $Success = $true
} catch {
    $Failure = $_.Exception.Message
} finally {
    Pop-Location
    foreach ($Key in $EnvironmentBefore.Keys) {
        [Environment]::SetEnvironmentVariable($Key, $EnvironmentBefore[$Key], "Process")
    }
    @{
        status = $(if ($Success) { "pass" } else { "fail" })
        scope = "Windows source/wheel qualification; not frozen EXE, MSIX, signing or WACK"
        platform = [Environment]::OSVersion.VersionString
        generated_at = (Get-Date).ToUniversalTime().ToString("o")
        checks = $Results.ToArray()
        error = $Failure
        frozen_executable_qualified = $false
        msix_qualified = $false
        signing_qualified = $false
        wack_qualified = $false
        live_browser_requested = [bool]$LiveBrowser
    } | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $Receipt
}
if (-not $Success) { Write-Error $Failure; exit 1 }
Write-Host "Windows source/wheel checks passed. Frozen package gates still require their own evidence."
