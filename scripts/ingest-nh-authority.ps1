param(
    [string[]]$Args
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $Root
try {
    python scripts/ingest-nh-authority.py @Args
}
finally {
    Pop-Location
}
