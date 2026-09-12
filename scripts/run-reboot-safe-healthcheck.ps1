param(
  [string]$RepoRoot = "C:\dev\NH_FAMILY_LAW_LLM",
  [string]$DataRoot = "C:\dev\NH_FAMILY_LAW_LLM_data",
  [string]$Output = "docs/sample-evidence/reboot_recovery_healthcheck.json"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $RepoRoot
py -3.11 scripts\run-reboot-safe-healthcheck.py --repo-root $RepoRoot --data-root $DataRoot --output $Output
