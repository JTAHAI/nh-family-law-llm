param(
  [string]$Owner = "JTAHAI",
  [string]$Repository = "nh-family-law-llm",
  [ValidateSet("public","private")][string]$Visibility = "public"
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) is required." }
gh auth status | Out-Host
if (-not (Test-Path .git)) {
  git init -b main
  git config user.name "Justin"
  git config user.email "43018008+JTAHAI@users.noreply.github.com"
  git add -A
  git commit -m "feat: initialize New Hampshire Family Law LLM"
}
$full = "$Owner/$Repository"
gh repo view $full *> $null
if ($LASTEXITCODE -ne 0) {
  gh repo create $full "--$Visibility" --description "Source-grounded legal AI workbench for New Hampshire family law" --source . --remote origin --push
} else {
  if (-not (git remote | Select-String '^origin$')) { git remote add origin "https://github.com/$full.git" }
  git push -u origin main
}
Write-Host "Published: https://github.com/$full"
