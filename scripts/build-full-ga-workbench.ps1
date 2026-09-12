param(
  [string]$ProjectRoot = "C:\dev\NH_FAMILY_LAW_LLM",
  [string]$DataRoot = "C:\dev\NH_FAMILY_LAW_LLM_data",
  [string]$Output = "docs/sample-evidence/full_ga_workbench_report.json",
  [switch]$AllowFailReport
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $ProjectRoot

$argsList = @("scripts\build-full-ga-workbench.py", "--data-root", $DataRoot, "--output", $Output)
if ($AllowFailReport) { $argsList += "--allow-fail-report" }
python @argsList
