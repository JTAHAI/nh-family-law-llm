param([switch]$Offline)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "store-build-workspace.ps1")
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$baseline = "ec48c11eae9448c8c6e7739d93e06fa2433aa95f"
$version = "5.5.4"
$cache = Resolve-RepoBuildDirectory (Join-Path $repo "dist\ocr") $repo
$runtime = Resolve-RepoBuildDirectory (Join-Path $cache "runtime-5.5.4") $repo
$receiptPath = Join-Path $cache "receipt.json"
$manifest = Join-Path $repo "store\native\tesseract"
$triplets = Join-Path $repo "store\native\triplets"
$triplet = "x64-windows-static-release"
$env:VCPKG_DISABLE_METRICS = "1"

function Assert-RegularInput([string]$Path) {
  $item = Get-Item -LiteralPath $Path -Force
  if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw "OCR build inputs must be regular files."
  }
}

# Reuse only a completed, hash-bound generated runtime. No host installation is
# accepted as an implicit dependency, and offline execution cannot download.
if (Test-Path -LiteralPath $receiptPath -PathType Leaf) {
  Assert-RegularInput $receiptPath
  $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
  if ($receipt.version -cne $version -or $receipt.vcpkg_baseline -cne $baseline -or
      -not $receipt.files -or $receipt.files.Count -lt 5) {
    throw "Cached OCR build receipt is not the pinned runtime."
  }
  $expectedNames = @()
  foreach ($entry in $receipt.files) {
    $relative = [string]$entry.path
    if (-not $relative -or $relative.Contains('..') -or $relative.Contains(':') -or
        $relative.StartsWith('/') -or $relative.StartsWith('\')) { throw "Unsafe OCR inventory path." }
    $path = Join-Path $runtime $relative
    $null = Resolve-RepoBuildDirectory (Split-Path -Parent $path) $repo
    Assert-RegularInput $path
    if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.sha256) {
      throw "Cached OCR runtime digest mismatch."
    }
    $expectedNames += $relative.Replace('\','/')
  }
  $actualNames = @(Get-ChildItem -LiteralPath $runtime -Recurse -File | ForEach-Object {
    $_.FullName.Substring($runtime.Length + 1).Replace('\','/')
  })
  if (@(Compare-Object ($expectedNames | Sort-Object) ($actualNames | Sort-Object)).Count) {
    throw "Cached OCR runtime inventory mismatch."
  }
  Write-Output $runtime
  return
}
if ($Offline) { throw "Pinned OCR source build is unavailable; offline builds never download." }
if (Test-Path -LiteralPath $runtime) { throw "Incomplete OCR staging exists; preserve it for diagnosis before retrying." }
Assert-StoreBuildDiskSpace $cache 6GB
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$toolRoot = Resolve-RepoBuildDirectory (Join-Path $cache "vcpkg") $repo
if (-not (Test-Path -LiteralPath $toolRoot)) {
  & git init $toolRoot | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "OCR dependency tool initialization failed." }
  & git -C $toolRoot remote add origin https://github.com/microsoft/vcpkg.git | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "OCR dependency tool origin setup failed." }
  & git -C $toolRoot fetch --depth 1 origin $baseline | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Pinned OCR dependency tool acquisition failed." }
  & git -C $toolRoot checkout --detach $baseline | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "Pinned OCR dependency tool checkout failed." }
}
$head = (& git -C $toolRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -cne $baseline) { throw "OCR tool source identity mismatch." }
$dirty = @(& git -C $toolRoot status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0 -or $dirty.Count) { throw "Modified OCR tool source refused." }
$env:VCPKG_ROOT = $toolRoot
& (Join-Path $toolRoot "bootstrap-vcpkg.bat") -disableMetrics | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Pinned OCR dependency tool bootstrap failed." }
$installed = Join-Path $cache "installed"
& (Join-Path $toolRoot "vcpkg.exe") install "--x-manifest-root=$manifest" `
  "--x-install-root=$installed" "--x-buildtrees-root=$cache\b" `
  "--x-packages-root=$cache\p" "--downloads-root=$cache\downloads" `
  "--overlay-triplets=$triplets" "--triplet=$triplet" "--binarysource=clear" --disable-metrics | Out-Host
if ($LASTEXITCODE -ne 0) { throw "Pinned security-fixed OCR source build failed." }
$prefix = Join-Path $installed $triplet
$exe = Join-Path $prefix "tools\tesseract\tesseract.exe"
Assert-RegularInput $exe
$reportedVersion = (& $exe --version) -join "`n"
if ($LASTEXITCODE -ne 0 -or $reportedVersion -notmatch 'tesseract 5\.5\.4') {
  throw "Built OCR executable version check failed."
}
New-Item -ItemType Directory -Path $runtime | Out-Null
Copy-Item -LiteralPath $exe -Destination (Join-Path $runtime "tesseract.exe")
# vcpkg's source archive hashes authenticate these installed configuration files.
$config = @(Get-ChildItem -LiteralPath (Join-Path $prefix "share") -Recurse -File -Filter hocr |
  Where-Object { $_.Directory.Name -eq 'configs' })
if ($config.Count -ne 1) { throw "Expected exactly one built OCR runtime configuration tree." }
$data = Join-Path $runtime "tessdata"
New-Item -ItemType Directory -Path $data | Out-Null
foreach ($name in @("configs", "tessconfigs")) {
  $source = Join-Path $config[0].Directory.Parent.FullName $name
  if (-not (Test-Path -LiteralPath $source -PathType Container)) { throw "Built OCR configuration is incomplete." }
  Copy-Item -LiteralPath $source -Destination (Join-Path $data $name) -Recurse
}
$modelsCommit = "87416418657359cb625c412a48b6e1d6d41c29bd"
$models = @{
  "eng.traineddata" = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"
  "osd.traineddata" = "9cf5d576fcc47564f11265841e5ca839001e7e6f38ff7f7aacf46d15a96b00ff"
}
foreach ($name in $models.Keys) {
  $target = Join-Path $data $name
  Invoke-WebRequest -Uri "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/$modelsCommit/$name" -OutFile $target -UseBasicParsing
  Assert-RegularInput $target
  if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -cne $models[$name]) {
    throw "Pinned OCR language-data SHA-256 mismatch."
  }
}
$licenses = Join-Path $runtime "licenses"
New-Item -ItemType Directory -Path $licenses | Out-Null
foreach ($copyright in @(Get-ChildItem -LiteralPath (Join-Path $prefix "share") -Recurse -File -Filter copyright)) {
  Copy-Item -LiteralPath $copyright.FullName -Destination (Join-Path $licenses ($copyright.Directory.Name + '.md'))
}
if (-not (Test-Path -LiteralPath (Join-Path $licenses "tesseract.md"))) { throw "OCR license is missing." }
Copy-Item -LiteralPath (Join-Path $licenses "tesseract.md") -Destination (Join-Path $licenses "tessdata-fast-Apache-2.0.md")
$files = @(Get-ChildItem -LiteralPath $runtime -Recurse -File | ForEach-Object {
  Assert-RegularInput $_.FullName
  if ($_.Extension -in @('.ttf','.otf','.woff','.woff2')) { throw "Unexpected font in OCR runtime." }
  @{path=$_.FullName.Substring($runtime.Length + 1).Replace('\','/');
    sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
@{schema="nhfl.native_build_input.v2"; version=$version; vcpkg_baseline=$baseline;
  model_commit=$modelsCommit; files=$files; source_built=$true; native_url_reading=$false;
  installer_executed=$false; runtime_downloads=$false; legal_review_verified=$false} |
  ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
Write-Output $runtime
