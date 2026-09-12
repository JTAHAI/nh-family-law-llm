param(
  [string]$RepoRoot = "C:\dev\NH_FAMILY_LAW_LLM",
  [string]$DataRoot = "C:\dev\NH_FAMILY_LAW_LLM_data",
  [string]$HostName = "127.0.0.1",
  [int]$Port = 8000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

& (Join-Path $PSScriptRoot "run-local-api.ps1") `
  -RepoRoot $RepoRoot `
  -DataRoot $DataRoot `
  -HostName $HostName `
  -Port $Port
