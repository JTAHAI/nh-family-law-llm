[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$PackagePath,
  [Parameter(Mandatory=$true)][string]$WorkRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'store-build-workspace.ps1')
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work = Resolve-RepoBuildDirectory $WorkRoot $repo
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
  throw 'This synthetic qualification requires a disposable GitHub-hosted Windows runner.'
}
if (Test-Path -LiteralPath $work) { throw 'Refusing to reuse a native qualification workspace.' }
$package = (Resolve-Path -LiteralPath $PackagePath).Path
$null = Resolve-RepoBuildDirectory (Split-Path -Parent $package) $repo
$expected = '69a6f22ef6d45c8a85498c5ac5ac780c21302bf4df7b9d227c23a0e0b7916937'
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant() -cne $expected) {
  throw 'Native qualification candidate digest mismatch.'
}
New-Item -ItemType Directory -Path $work | Out-Null
$evidence = Join-Path $work 'evidence'
$profile = Join-Path $work 'profile'
$tmp = Join-Path $work 'tmp'
New-Item -ItemType Directory -Path $evidence,$profile,$tmp | Out-Null
$checks = [Collections.Generic.List[object]]::new()
$report = [ordered]@{schema='nhfl.frozen_native_qualification.v1'; status='fail';
  candidate_sha256=$expected; uses_synthetic_input_only=$true; checks=$checks;
  legal_review_verified=$false; production_ready=$false; wack_qualified=$false; error=$null}
$before = @{}
foreach ($name in @('LOCALAPPDATA','USERPROFILE','HOME','TMP','TEMP','HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE')) {
  $before[$name] = [Environment]::GetEnvironmentVariable($name,'Process')
}
function Invoke-OwnedProcess([string]$Exe,[string[]]$Arguments,[string]$Label,[int]$Seconds=120) {
  $process = Start-Process -FilePath $Exe -ArgumentList $Arguments -PassThru -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $evidence ($Label+'.stdout.log')) `
    -RedirectStandardError (Join-Path $evidence ($Label+'.stderr.log'))
  try {
    if (-not $process.WaitForExit($Seconds * 1000)) { throw "$Label timed out." }
    if ($process.ExitCode -ne 0) { throw "$Label returned a failing exit code." }
  } finally {
    $process.Refresh()
    if (-not $process.HasExited) { $process.Kill(); $process.WaitForExit(10000) | Out-Null }
  }
}
try {
  foreach ($name in @('LOCALAPPDATA','USERPROFILE','HOME')) { [Environment]::SetEnvironmentVariable($name,$profile,'Process') }
  foreach ($name in @('TMP','TEMP')) { [Environment]::SetEnvironmentVariable($name,$tmp,'Process') }
  $env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'
  $makeappx=Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Recurse -File -Filter makeappx.exe |
    Where-Object { $_.FullName -match '\\x64\\' } | Sort-Object FullName -Descending | Select-Object -First 1
  if (-not $makeappx) { throw 'MakeAppx is unavailable.' }
  $payload=Join-Path $work 'portable'
  & $makeappx.FullName unpack /p $package /d $payload /o | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Native candidate unpack failed.' }
  # A portable delivery uses identical application bytes, without MSIX container metadata.
  foreach ($name in @('AppxManifest.xml','AppxBlockMap.xml','AppxSignature.p7x','[Content_Types].xml')) {
    $path=Join-Path $payload $name
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  }
  if (@(Get-ChildItem -LiteralPath $payload -Recurse -File | Where-Object { $_.Extension -in @('.ttf','.otf','.woff','.woff2','.pfx','.p12') }).Count) {
    throw 'Unexpected font or private-key file in candidate.'
  }
  $smokePath=Join-Path $evidence 'portable-smoke.json'
  Invoke-OwnedProcess (Join-Path $payload 'NHFamilyLawLLM.exe') @('--smoke-test','--smoke-json',('"'+$smokePath+'"')) 'portable' 600
  $smoke=Get-Content -LiteralPath $smokePath -Raw | ConvertFrom-Json
  if ($smoke.launch_result -ne 'pass' -or $smoke.api_health_result -ne $true -or
      $smoke.fictional_sample_workflow_result -ne $true -or $smoke.external_data_boundary_verification -ne $true) {
    throw 'Portable application acceptance failed.'
  }
  $checks.Add(@{name='portable-frozen-application';status='pass';python_installation_required=$false})
  Add-Type -AssemblyName System.Drawing
  $png=Join-Path $work 'fictional-ocr-input.png'
  $image=New-Object Drawing.Bitmap 1500,250
  $graphics=[Drawing.Graphics]::FromImage($image)
  $font=New-Object Drawing.Font 'Arial',42
  try {
    $graphics.Clear([Drawing.Color]::White)
    $graphics.DrawString('SYNTHETIC NH RECORD 2468',$font,[Drawing.Brushes]::Black,40,70)
    $image.Save($png,[Drawing.Imaging.ImageFormat]::Png)
  } finally { $font.Dispose(); $graphics.Dispose(); $image.Dispose() }
  $ocr=Join-Path $payload 'store\tesseract\tesseract.exe'
  $textRoot=Join-Path $work 'fictional-ocr-output'
  Invoke-OwnedProcess $ocr @(('"'+$png+'"'),('"'+$textRoot+'"'),'--tessdata-dir',('"'+(Join-Path $payload 'store\tesseract\tessdata')+'"'),'-l','eng','--psm','7') 'ocr' 120
  $recognized=(Get-Content -LiteralPath ($textRoot+'.txt') -Raw).Trim()
  if ($recognized -cne 'SYNTHETIC NH RECORD 2468') { throw 'Synthetic OCR recognition did not match its known text.' }
  $checks.Add(@{name='native-ocr';status='pass';expected='SYNTHETIC NH RECORD 2468';observed=$recognized;
    input_sha256=(Get-FileHash -LiteralPath $png -Algorithm SHA256).Hash.ToLowerInvariant()})
  Add-Type -AssemblyName System.Speech
  $wav=Join-Path $work 'fictional-audio.wav'
  $speech=New-Object Speech.Synthesis.SpeechSynthesizer
  try {
    $voices=@($speech.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Culture.Name -like 'en-*' })
    if (-not $voices.Count) { throw 'No English synthetic speech voice is available; no inference pass can be claimed.' }
    $speech.SelectVoice($voices[0].VoiceInfo.Name)
    $format=New-Object Speech.AudioFormat.SpeechAudioFormatInfo 16000,([Speech.AudioFormat.AudioBitsPerSample]::Sixteen),([Speech.AudioFormat.AudioChannel]::Mono)
    $speech.SetOutputToWaveFile($wav,$format)
    $speech.Speak('This is a fictional recording for a New Hampshire family record test.')
    $speech.SetOutputToNull()
  } finally { $speech.Dispose() }
  $whisper=Join-Path $payload 'store\whisper\whisper-cli.exe'
  $model=Join-Path $payload 'store\whisper\ggml-tiny.en-q5_1.bin'
  $transcriptRoot=Join-Path $work 'fictional-transcript'
  Invoke-OwnedProcess $whisper @('-m',('"'+$model+'"'),'-f',('"'+$wav+'"'),'-l','en','-t','2','-otxt','-of',('"'+$transcriptRoot+'"')) 'whisper' 180
  $transcript=(Get-Content -LiteralPath ($transcriptRoot+'.txt') -Raw).Trim()
  if ($transcript -notmatch '(?i)fictional' -or $transcript -notmatch '(?i)new hampshire' -or $transcript -notmatch '(?i)record') {
    throw 'Synthetic native transcription did not preserve its required fixture phrases.'
  }
  $checks.Add(@{name='native-transcription';status='pass';observed=$transcript;
    input_sha256=(Get-FileHash -LiteralPath $wav -Algorithm SHA256).Hash.ToLowerInvariant();
    human_review_required=$true;legal_accuracy_claim=$false})
  $report.status='pass'
} catch { $report.error=$_.Exception.Message }
finally {
  # This inventory is diagnostic only; presence of an SDK is not a WACK pass.
  $appcert=@(Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10' -Recurse -File -Filter appcert.exe -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName })
  @{schema='nhfl.certification_host_probe.v1';status='not_run';appcert_paths=$appcert;
    operating_system=[Environment]::OSVersion.VersionString;session_id=(Get-Process -Id $PID).SessionId;
    wack_qualified=$false;reason='Independent client-Windows certification run remains required.'} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidence 'certification-host.json') -Encoding UTF8
  foreach ($name in $before.Keys) { [Environment]::SetEnvironmentVariable($name,$before[$name],'Process') }
  $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $evidence 'native-functional.json') -Encoding UTF8
}
if ($report.status -ne 'pass') { throw 'Synthetic native qualification failed; inspect its receipt.' }
