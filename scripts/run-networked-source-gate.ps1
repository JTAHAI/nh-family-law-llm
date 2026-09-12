param(
    [string]$DataRoot = "C:\dev\NH_FAMILY_LAW_LLM_data",
    [string]$Output = "docs/sample-evidence/networked_source_gate_report.json",
    [switch]$AllowFailReport
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RepoRoot
$argsList = @("scripts\run-networked-source-gate.py", "--data-root", $DataRoot, "--output", $Output)
if ($AllowFailReport) { $argsList += "--allow-fail-report" }
python @argsList
