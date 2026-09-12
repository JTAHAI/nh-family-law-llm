[CmdletBinding()]
param(
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
  [string]$PackagePath
)
$ErrorActionPreference = "Stop"
$failures = [System.Collections.Generic.List[string]]::new()
function Require-Text([string]$Path,[string]$Pattern) {
  if (-not (Test-Path $Path)) { $failures.Add("Missing: $Path"); return }
  if (-not (Select-String -Path $Path -Pattern $Pattern -Quiet)) {
    $failures.Add("Pattern '$Pattern' missing from $Path")
  }
}
Require-Text (Join-Path $RepositoryRoot "config\product_identity.json") '"jurisdiction":'
Require-Text (Join-Path $RepositoryRoot "packaging\windows\app-identity.json") 'JTAHAI.NHFamilyLawLLM'
Require-Text (Join-Path $RepositoryRoot "packaging\windows\AppxManifest.template.xml") 'Protocol Name="nhfl"'
if ($PackagePath) {
  if (-not (Test-Path $PackagePath)) { $failures.Add("Package not found: $PackagePath") }
  else {
    $sig = Get-AuthenticodeSignature -FilePath $PackagePath
    Write-Host "Signature status: $($sig.Status)"
  }
}
if ($failures.Count) {
  $failures | ForEach-Object { Write-Error $_ }
  exit 1
}
Write-Host "NH Windows source identity checks passed."
Write-Host "Frozen executable, MSIX packaging, signing, WACK, clean-machine install, protocol activation, and uninstall remain Windows-host gates."
