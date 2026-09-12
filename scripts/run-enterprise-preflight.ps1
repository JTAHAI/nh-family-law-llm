param(
  [string]$RepoRoot = "C:\dev\NH_FAMILY_LAW_LLM",
  [string]$DataRoot = "C:\dev\NH_FAMILY_LAW_LLM_data",
  [string]$Output = "docs/sample-evidence/enterprise_preflight_report.json"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
python "$RepoRoot\scripts\run-enterprise-preflight.py" --repo-root $RepoRoot --data-root $DataRoot --output $Output
