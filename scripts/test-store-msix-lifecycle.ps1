[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$PackagePath,
  [Parameter(Mandatory=$true)][string]$WorkRoot,
  [switch]$IsolatedTestEnvironment
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'store-build-workspace.ps1')
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = Resolve-RepoBuildDirectory $WorkRoot $repo
if (-not $IsolatedTestEnvironment -or $env:GITHUB_ACTIONS -ne 'true' -or
    $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
  throw 'This certificate/install qualification is restricted to disposable GitHub-hosted Windows runners.'
}
if (Test-Path -LiteralPath $work) { throw 'Qualification workspace must be new.' }
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$null = Resolve-RepoBuildDirectory (Split-Path -Parent $package) $repo
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Ephemeral QA certificate trust requires an elevated disposable runner.'
}
Import-Module Appx -ErrorAction Stop
New-Item -ItemType Directory -Path $work | Out-Null
$evidence = Join-Path $work 'evidence'
New-Item -ItemType Directory -Path $evidence | Out-Null
function Find-SdkTool([string]$Name) {
  $found = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Recurse -File -Filter $Name |
    Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $found) { throw "SDK tool missing: $Name" }
  return $found.FullName
}
function Hash([string]$Path) { return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Payload-Inventory([string]$Root) {
  $map = @{}
  Get-ChildItem -LiteralPath $Root -Recurse -File | ForEach-Object {
    $name = $_.FullName.Substring($Root.Length + 1).Replace('\','/')
    if ($name -notin @('AppxManifest.xml','AppxBlockMap.xml','AppxSignature.p7x','[Content_Types].xml')) {
      if ($_.Extension -in @('.ttf','.otf','.woff','.woff2','.pfx','.p12')) { throw 'Forbidden distributable payload.' }
      $map[$name] = Hash $_.FullName
    }
  }
  return $map
}
$realName = 'TAHAIWebServices.NewHampshireFamilyLawLLM'
$realBefore = @(Get-AppxPackage -Name $realName | ForEach-Object { $_.PackageFullName })
$nonce = [Guid]::NewGuid().ToString('N').Substring(0, 6)
$qaName = $realName + '.QA' + $nonce
$publisher = 'CN=NHFL.IsolatedQA.' + $nonce
$cert = $null
$installed = $null
$unpacked = Join-Path $work 'payload'
$profile = Join-Path $work 'profile'
$qaPackage = Join-Path $work 'isolated-qa.msix'
$checks = [Collections.Generic.List[object]]::new()
$report = [ordered]@{
  schema='nhfl.msix_installed_lifecycle.v1'; status='fail';
  candidate_sha256=(Hash $package); qa_identity=$qaName;
  production_identity_installed=$false; store_submission=$false;
  legal_review_verified=$false; wack_qualified=$false; production_ready=$false;
  checks=$checks; cleanup_complete=$false; error=$null
}
function Assert-InstalledBytes($Registration, $Expected) {
  $count = 0
  foreach ($name in $Expected.Keys) {
    $target = Join-Path $Registration.InstallLocation $name
    if (-not (Test-Path -LiteralPath $target -PathType Leaf) -or (Hash $target) -cne $Expected[$name]) {
      throw 'Installed application bytes differ from the candidate.'
    }
    $count++
  }
  return $count
}
function Invoke-PackageSmoke($Registration, [string]$Label, [switch]$Gui) {
  $result = Join-Path $evidence ($Label + '-smoke.json')
  $wrapperResult = Join-Path $evidence ($Label + '-process.json')
  $wrapper = Join-Path $work ($Label + '-probe.ps1')
  $exe = Join-Path $Registration.InstallLocation 'NHFamilyLawLLM.exe'
  # The helper is a qualification command, not modified application code.
  # PreventBreakaway keeps its launched child in the registered package context.
  $template = @'
$ErrorActionPreference = 'Stop'
$env:LOCALAPPDATA = '__PROFILE__'
$env:HOME = '__PROFILE__'
$env:USERPROFILE = '__PROFILE__'
$env:TEMP = '__TEMP__'
$env:TMP = '__TEMP__'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$exitCode = -1
$packageFullName = $null
try {
  Add-Type -TypeDefinition 'using System; using System.Text; using System.Runtime.InteropServices; public class PackageToken { [DllImport("kernel32.dll", CharSet=CharSet.Unicode)] public static extern int GetCurrentPackageFullName(ref uint n, StringBuilder value); }'
  [uint32]$length = 0
  $rc = [PackageToken]::GetCurrentPackageFullName([ref]$length, $null)
  if ($rc -ne 122 -or $length -lt 2) { throw 'Package identity unavailable in qualification context.' }
  $buffer = New-Object Text.StringBuilder ([int]$length)
  if ([PackageToken]::GetCurrentPackageFullName([ref]$length, $buffer) -ne 0) { throw 'Cannot read package identity.' }
  $packageFullName = $buffer.ToString()
  if ($packageFullName -cne '__PACKAGE_FULL_NAME__') { throw 'Qualification token has the wrong package identity.' }
  if ('__GUI__' -eq 'true') {
    $child = Start-Process -FilePath '__EXE__' -PassThru
    try {
      $deadline = [DateTime]::UtcNow.AddSeconds(90)
      do {
        Start-Sleep -Milliseconds 300
        $child.Refresh()
        if ($child.HasExited) { throw 'Installed graphical launcher exited before displaying its window.' }
      } while ($child.MainWindowHandle -eq 0 -and [DateTime]::UtcNow -lt $deadline)
      if ($child.MainWindowHandle -eq 0 -or -not $child.Responding -or
          $child.MainWindowTitle -notlike '*New Hampshire*') { throw 'Installed graphical launcher is not responsive.' }
      Add-Type -AssemblyName System.Drawing
      Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class WindowProbe { [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; } [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r); [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags); }'
      $rect = New-Object WindowProbe+RECT
      if (-not [WindowProbe]::GetWindowRect($child.MainWindowHandle,[ref]$rect)) { throw 'Cannot inspect launcher window.' }
      $width=$rect.Right-$rect.Left; $height=$rect.Bottom-$rect.Top
      if ($width -lt 900 -or $height -lt 600 -or $width -gt 5000 -or $height -gt 5000) { throw 'Launcher window is missing or replaced by an error dialog.' }
      Start-Sleep -Seconds 2
      $image=New-Object Drawing.Bitmap $width,$height
      $graphics=[Drawing.Graphics]::FromImage($image)
      $dc=$graphics.GetHdc()
      try { $painted=[WindowProbe]::PrintWindow($child.MainWindowHandle,$dc,2) }
      finally { $graphics.ReleaseHdc($dc); $graphics.Dispose() }
      try {
        if (-not $painted) { throw 'Launcher rendering capture failed.' }
        $image.Save('__RESULT__.png',[Drawing.Imaging.ImageFormat]::Png)
      } finally { $image.Dispose() }
      @{status='pass'; title=$child.MainWindowTitle; width=$width; height=$height;
        responding=$true; review_required=$true} | ConvertTo-Json | Set-Content '__RESULT__' -Encoding UTF8
      if (-not $child.CloseMainWindow() -or -not $child.WaitForExit(30000)) { throw 'Graphical launcher did not close normally.' }
      $exitCode=$child.ExitCode
    } finally {
      $child.Refresh()
      if (-not $child.HasExited) { $child.Kill(); $child.WaitForExit(10000) | Out-Null }
    }
  } else {
    $child = Start-Process -FilePath '__EXE__' -ArgumentList @('--smoke-test','--smoke-json','"__RESULT__"') -PassThru
    if (-not $child.WaitForExit(600000)) { $child.Kill(); throw 'Installed smoke timed out.' }
    $exitCode = $child.ExitCode
  }
} finally {
  @{exit_code=$exitCode; process_id=$PID; package_full_name=$packageFullName} | ConvertTo-Json | Set-Content -LiteralPath '__WRAPPER_RESULT__.tmp' -Encoding UTF8
  Move-Item -LiteralPath '__WRAPPER_RESULT__.tmp' -Destination '__WRAPPER_RESULT__'
}
'@
  foreach ($replacement in @{
    '__PROFILE__'=$profile; '__TEMP__'=(Join-Path $work 'tmp');
    '__EXE__'=$exe; '__RESULT__'=$result; '__WRAPPER_RESULT__'=$wrapperResult;
    '__PACKAGE_FULL_NAME__'=$Registration.PackageFullName; '__GUI__'=([string][bool]$Gui).ToLowerInvariant()
  }.GetEnumerator()) { $template = $template.Replace($replacement.Key, $replacement.Value.Replace("'", "''")) }
  $template | Set-Content -LiteralPath $wrapper -Encoding UTF8
  Invoke-CommandInDesktopPackage -PackageFamilyName $Registration.PackageFamilyName -AppId 'NHFamilyLawLLM' `
    -Command "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Args ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $wrapper + '"') -PreventBreakaway
  $deadline = [DateTime]::UtcNow.AddSeconds(630)
  while (-not (Test-Path -LiteralPath $wrapperResult)) {
    if ([DateTime]::UtcNow -gt $deadline) { throw 'Package-context qualification timed out.' }
    Start-Sleep -Milliseconds 300
  }
  $completion = Get-Content -LiteralPath $wrapperResult -Raw | ConvertFrom-Json
  if ($completion.exit_code -ne 0 -or $completion.package_full_name -cne $Registration.PackageFullName -or -not (Test-Path -LiteralPath $result)) { throw 'Installed application smoke failed.' }
  $smoke = Get-Content -LiteralPath $result -Raw | ConvertFrom-Json
  if ($Gui) {
    if ($smoke.status -ne 'pass' -or $smoke.responding -ne $true -or -not (Test-Path -LiteralPath ($result + '.png'))) {
      throw 'Installed graphical launcher qualification failed.'
    }
  } else {
    $answerBlocked = $smoke.answer_grounded -eq $false -and $smoke.answer_failure_class -eq 'official_authority_product_unavailable'
    $answerGrounded = $smoke.answer_grounded -eq $true -and $smoke.answer_failure_class -eq 'none'
    if ($smoke.launch_result -ne 'pass' -or $smoke.api_health_result -ne $true -or
        $smoke.fictional_sample_workflow_result -ne $true -or $smoke.bundled_ocr_available -ne $true -or
        $smoke.external_data_boundary_verification -ne $true -or (-not $answerBlocked -and -not $answerGrounded)) {
      throw 'Installed application did not pass its runtime acceptance checks.'
    }
  }
  $checks.Add(@{name=$Label; status='pass'; package_context=$true; smoke_sha256=(Hash $result)})
}
try {
  if (Get-AppxPackage -Name $qaName) { throw 'QA identity is already installed.' }
  Assert-StoreBuildDiskSpace $work 2GB
  $makeappx = Find-SdkTool 'makeappx.exe'
  $signtool = Find-SdkTool 'signtool.exe'
  & $makeappx unpack /p $package /d $unpacked /o | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Candidate unpack failed.' }
  $payloadHashes = Payload-Inventory $unpacked
  [xml]$manifest = Get-Content -LiteralPath (Join-Path $unpacked 'AppxManifest.xml') -Raw
  if ([string]$manifest.Package.Identity.Name -cne $realName) { throw 'Unexpected candidate identity.' }
  $manifest.Package.Identity.Name = $qaName
  $manifest.Package.Identity.Publisher = $publisher
  $protocols = $manifest.SelectNodes("//*[local-name()='Protocol']")
  foreach ($protocol in $protocols) { $protocol.SetAttribute('Name', 'nhflqa-' + $nonce) }
  $manifest.Save((Join-Path $unpacked 'AppxManifest.xml'))
  foreach ($name in @('AppxBlockMap.xml','AppxSignature.p7x','[Content_Types].xml')) {
    $generated = Join-Path $unpacked $name
    if (Test-Path -LiteralPath $generated) { Remove-Item -LiteralPath $generated -Force }
  }
  & $makeappx pack /d $unpacked /p $qaPackage /o | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'QA package creation failed.' }
  $cert = New-SelfSignedCertificate -Type Custom -Subject $publisher -KeyAlgorithm RSA -KeyLength 2048 `
    -HashAlgorithm SHA256 -KeyUsage DigitalSignature -KeyExportPolicy NonExportable `
    -CertStoreLocation 'Cert:\CurrentUser\My' -NotAfter (Get-Date).AddDays(1) `
    -TextExtension @('2.5.29.37={text}1.3.6.1.5.5.7.3.3','2.5.29.19={text}')
  $publicCert = Join-Path $work 'temporary-public-certificate.cer'
  Export-Certificate -Cert $cert -FilePath $publicCert | Out-Null
  Import-Certificate -FilePath $publicCert -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null
  & $signtool sign /fd SHA256 /sha1 $cert.Thumbprint /s My $qaPackage | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Isolated QA package signing failed.' }
  & $signtool verify /pa /v $qaPackage | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'QA package signature verification failed.' }
  $report.qa_sha256 = Hash $qaPackage
  New-Item -ItemType Directory -Path $profile,(Join-Path $work 'tmp') | Out-Null
  $marker = Join-Path $profile 'synthetic-owner-preservation.txt'
  'Fictional qualification marker; not a user record.' | Set-Content -LiteralPath $marker
  $markerHash = Hash $marker
  Add-AppxPackage -Path $qaPackage -ErrorAction Stop
  $installed = Get-AppxPackage -Name $qaName -ErrorAction Stop
  if (-not $installed -or $installed.SignatureKind -eq 'None') { throw 'Signed QA registration not found.' }
  $report.installed_payload_files_verified = Assert-InstalledBytes $installed $payloadHashes
  Invoke-PackageSmoke $installed 'clean-install'
  Invoke-PackageSmoke $installed 'graphical-launcher' -Gui
  Invoke-PackageSmoke $installed 'restart'
  Remove-AppxPackage -Package $installed.PackageFullName -Confirm:$false -ErrorAction Stop
  $installed = $null
  if (Get-AppxPackage -Name $qaName) { throw 'QA uninstall did not complete.' }
  if ((Hash $marker) -cne $markerHash) { throw 'External synthetic owner marker changed on uninstall.' }
  $checks.Add(@{name='uninstall'; status='pass'; external_marker_preserved=$true})
  Add-AppxPackage -Path $qaPackage -ErrorAction Stop
  $installed = Get-AppxPackage -Name $qaName -ErrorAction Stop
  $null = Assert-InstalledBytes $installed $payloadHashes
  Invoke-PackageSmoke $installed 'reinstall'
  if ((Hash $marker) -cne $markerHash) { throw 'External synthetic owner marker changed on reinstall.' }
  if ((Hash $package) -cne $report.candidate_sha256) { throw 'Original candidate changed during qualification.' }
  $report.status = 'pass'
} catch {
  $report.error = $_.Exception.Message
} finally {
  # Remove only the unique QA identity and certificate created by this run.
  try {
    $registration = Get-AppxPackage -Name $qaName -ErrorAction Stop
    if ($registration) {
      Get-Process -ErrorAction SilentlyContinue | Where-Object {
        try { $_.Path -and $_.Path.StartsWith($registration.InstallLocation + '\', [StringComparison]::OrdinalIgnoreCase) } catch { $false }
      } | Stop-Process -Force -ErrorAction Stop
      Remove-AppxPackage -Package $registration.PackageFullName -Confirm:$false -ErrorAction Stop
    }
    if ($cert) {
      foreach ($store in @('Cert:\LocalMachine\TrustedPeople','Cert:\CurrentUser\My')) {
        $path = Join-Path $store $cert.Thumbprint
        if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force -ErrorAction Stop }
      }
    }
    $realAfter = @(Get-AppxPackage -Name $realName | ForEach-Object { $_.PackageFullName })
    if (($realBefore -join '|') -cne ($realAfter -join '|')) { throw 'Production registration changed.' }
    if (Get-AppxPackage -Name $qaName) { throw 'QA registration cleanup incomplete.' }
    $report.cleanup_complete = $true
  } catch { $report.status='fail'; $report.cleanup_error=$_.Exception.Message }
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'installed-lifecycle.json') -Encoding UTF8
}
if ($report.status -ne 'pass') { throw 'Installed MSIX qualification failed; inspect the retained receipt.' }
Write-Host 'Signed isolated QA install, package-context launch, restart, uninstall and reinstall passed. This is not Store approval.'
