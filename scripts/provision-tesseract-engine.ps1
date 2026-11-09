param([switch]$Offline)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "store-build-workspace.ps1")
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
# Upstream release, independently published in Microsoft's WinGet manifest:
# manifests/t/tesseract-ocr/tesseract/5.5.0.20241111/*.installer.yaml
$url = "https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe"
$expected = "f3fc4236425b690c8be756f35793f77394ee004be0a6460a440c754d892f68bc"
$cache = Resolve-RepoBuildDirectory (Join-Path $repo "dist\build-cache\tesseract\5.5.0.20241111") $repo
$expanded = Resolve-RepoBuildDirectory (Join-Path $cache "expanded") $repo
$archive = Join-Path $cache "tesseract-installer.exe"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
  if ($Offline) { throw "Pinned OCR archive is unavailable; offline builds never download." }
  Invoke-WebRequest -Uri $url -OutFile $archive -UseBasicParsing
}
if ((Get-Item -LiteralPath $archive -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
  throw "OCR archive must not be a link or reparse point."
}
$actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -cne $expected) { throw "Pinned OCR archive SHA-256 mismatch." }
$seven = Get-Command 7z.exe -ErrorAction SilentlyContinue
if (-not $seven) { throw "7-Zip is required to extract the verified OCR archive without running its installer." }
# Re-extract the verified archive. Never trust a previously expanded cache.
# This location contains generated build inputs only, never user records.
if (Test-Path -LiteralPath $expanded) {
  $null = Resolve-RepoBuildDirectory $expanded $repo
  Remove-Item -LiteralPath $expanded -Recurse -Force
}
New-Item -ItemType Directory -Path $expanded | Out-Null
& $seven.Source x -y "-o$expanded" $archive | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Verified OCR archive extraction failed." }
$executables = @(Get-ChildItem -LiteralPath $expanded -Recurse -File -Filter tesseract.exe)
if ($executables.Count -ne 1) { throw "Expected exactly one OCR runtime in the verified archive." }
$root = $executables[0].Directory.FullName
foreach ($relative in @("tesseract.exe", "tessdata\eng.traineddata", "tessdata\osd.traineddata", "tessdata\configs\hocr")) {
  if (-not (Test-Path -LiteralPath (Join-Path $root $relative) -PathType Leaf)) {
    throw "Verified OCR archive is missing a required runtime component."
  }
}
@{ schema = "nhfl.native_build_input.v1"; source = $url; sha256 = $actual;
   version = "5.5.0.20241111"; installer_executed = $false;
   runtime_downloads = $false; legal_review_verified = $false } |
  ConvertTo-Json | Set-Content -LiteralPath (Join-Path $cache "receipt.json") -Encoding UTF8
Write-Output $root
