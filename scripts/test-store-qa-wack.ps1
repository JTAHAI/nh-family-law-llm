[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$WorkRoot)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'store-build-workspace.ps1')
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=Resolve-RepoBuildDirectory $WorkRoot $repo
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
  throw 'QA WACK is restricted to disposable GitHub-hosted Windows runners.'
}
$receipt=Get-Content -LiteralPath (Join-Path $work 'evidence\installed-lifecycle.json') -Raw | ConvertFrom-Json
if ($receipt.status -ne 'pass' -or $receipt.cleanup_complete -ne $true -or
    $receipt.production_identity_installed -ne $false -or
    $receipt.candidate_sha256 -cne '69a6f22ef6d45c8a85498c5ac5ac780c21302bf4df7b9d227c23a0e0b7916937' -or
    $receipt.qa_identity -notmatch '^TAHAIWebServices\.NewHampshireFamilyLawLLM\.QA[0-9a-f]{6}$') {
  throw 'A passing exact isolated installation receipt is required before QA WACK.'
}
$package=Join-Path $work 'isolated-qa.msix'
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant() -cne $receipt.qa_sha256) {
  throw 'QA package differs from its installed qualification receipt.'
}
$certificate=New-Object Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $work 'temporary-public-certificate.cer')
if ($certificate.HasPrivateKey -or $certificate.Subject -notmatch '^CN=NHFL\.IsolatedQA\.[0-9a-f]{6}$') {
  throw 'Unexpected QA signing certificate.'
}
$out=Join-Path $work 'evidence\wack'
if (Test-Path -LiteralPath $out) { throw 'WACK output must be new; old reports cannot qualify another attempt.' }
New-Item -ItemType Directory -Path $out | Out-Null
$report=[ordered]@{schema='nhfl.qa_wack_attempt.v1';status='blocked';execution_status='not_run';
  candidate_sha256=$receipt.candidate_sha256;qa_sha256=$receipt.qa_sha256;qa_identity=$receipt.qa_identity;
  production_identity_tested=$false;microsoft_certified=$false;client_windows_qualified=$false;
  operating_system=[Environment]::OSVersion.VersionString;session_id=(Get-Process -Id $PID).SessionId;
  cleanup_complete=$false;error=$null}
$before=@{}
foreach ($name in @('LOCALAPPDATA','USERPROFILE','HOME','TMP','TEMP')) {
  $before[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
$trustPath=Join-Path 'Cert:\LocalMachine\TrustedPeople' $certificate.Thumbprint
$trustAttempted=$false; $installAttempted=$false
try {
  Import-Module Appx -ErrorAction Stop
  if (Get-AppxPackage -Name $receipt.qa_identity) { throw 'QA identity must not already be installed.' }
  if (Test-Path -LiteralPath $trustPath) { throw 'QA trust must not preexist this attempt.' }
  $appcert='C:\Program Files (x86)\Windows Kits\10\App Certification Kit\appcert.exe'
  if (-not (Test-Path -LiteralPath $appcert) -or $report.session_id -eq 0) { throw 'WACK tool and an interactive user session are required.' }
  foreach ($name in @('LOCALAPPDATA','USERPROFILE','HOME')) { [Environment]::SetEnvironmentVariable($name,(Join-Path $work 'profile'),'Process') }
  foreach ($name in @('TMP','TEMP')) { [Environment]::SetEnvironmentVariable($name,(Join-Path $work 'tmp'),'Process') }
  $trustAttempted=$true
  Import-Certificate -FilePath (Join-Path $work 'temporary-public-certificate.cer') -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null
  $installAttempted=$true
  Add-AppxPackage -Path $package -ErrorAction Stop
  $installed=Get-AppxPackage -Name $receipt.qa_identity -ErrorAction Stop
  if (-not $installed) { throw 'QA registration failed before WACK.' }
  & $appcert reset | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'WACK reset failed.' }
  $nativeReport=Join-Path $out 'native-report.xml'
  $start=New-Object Diagnostics.ProcessStartInfo
  $start.FileName=$appcert
  $start.Arguments='test -packagefullname "'+$installed.PackageFullName+'" -reportoutputpath "'+$nativeReport+'"'
  $start.UseShellExecute=$false
  $start.RedirectStandardOutput=$true; $start.RedirectStandardError=$true
  $process=New-Object Diagnostics.Process
  $process.StartInfo=$start
  $started=$false
  try {
    if (-not $process.Start()) { throw 'WACK process did not start.' }
    $started=$true
    $stdout=$process.StandardOutput.ReadToEndAsync();$stderr=$process.StandardError.ReadToEndAsync()
    $report.execution_status='started'
    if (-not $process.WaitForExit(900000)) { throw 'WACK timed out; no certification pass is established.' }
    $report.exit_code=$process.ExitCode
    if (-not $stdout.Wait(10000) -or -not $stderr.Wait(10000)) { throw 'WACK output capture incomplete.' }
    $stdout.Result | Set-Content -LiteralPath (Join-Path $out 'stdout.log') -Encoding UTF8
    $stderr.Result | Set-Content -LiteralPath (Join-Path $out 'stderr.log') -Encoding UTF8
    $report.execution_status=if ($process.ExitCode -eq 0) {'completed'} else {'failed'}
  } finally {
    if ($started -and -not $process.HasExited) { $process.Kill();$process.WaitForExit(10000) | Out-Null }
    $process.Dispose()
  }
  & python -B (Join-Path $PSScriptRoot 'parse-wack-report.py') --package $package --output-root $out --execution-status $report.execution_status --output (Join-Path $out 'parsed-result.json')
  $parsed=Get-Content -LiteralPath (Join-Path $out 'parsed-result.json') -Raw | ConvertFrom-Json
  $report.status=$parsed.status
  if (Test-Path -LiteralPath $nativeReport) {
    $report.native_report_sha256=(Get-FileHash -LiteralPath $nativeReport -Algorithm SHA256).Hash.ToLowerInvariant()
  }
} catch { $report.error=$_.Exception.Message }
finally {
  try {
    $registered=$null
    if ($installAttempted) { $registered=Get-AppxPackage -Name $receipt.qa_identity -ErrorAction Stop }
    if ($registered) {
      Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($registered.InstallLocation+'\',[StringComparison]::OrdinalIgnoreCase) } catch {$false}
      } | Stop-Process -Force -ErrorAction Stop
      Remove-AppxPackage -Package $registered.PackageFullName -Confirm:$false -ErrorAction Stop
    }
    if ($trustAttempted -and (Test-Path -LiteralPath $trustPath)) { Remove-Item -LiteralPath $trustPath -Force -ErrorAction Stop }
    if (Get-AppxPackage -Name $receipt.qa_identity) { throw 'QA WACK registration cleanup incomplete.' }
    $report.cleanup_complete=$true
  } catch { $report.status='blocked';$report.cleanup_error=$_.Exception.Message }
  foreach ($name in $before.Keys) { [Environment]::SetEnvironmentVariable($name,$before[$name],'Process') }
  $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out 'attempt.json') -Encoding UTF8
}
if ($report.status -ne 'pass') { throw 'QA WACK did not qualify; preserved evidence must be reviewed.' }
