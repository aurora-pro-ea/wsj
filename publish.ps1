param(
    [string]$Message = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

Write-Host "[1/5] Building site..."
python .\build_site.py
Assert-LastExitCode "Site build"

Write-Host "[2/5] Validating generated files..."
python .\validate_site.py .\dist
Assert-LastExitCode "Site validation"

Write-Host "[3/5] Staging changes..."
git add --all
Assert-LastExitCode "Git add"

git diff --cached --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "No changes to publish."
    exit 0
}
if ($LASTEXITCODE -ne 1) {
    Assert-LastExitCode "Git diff"
}

if ([string]::IsNullOrWhiteSpace($Message)) {
    $Message = "Update archive " + (Get-Date -Format "yyyy-MM-dd HH:mm")
}

Write-Host "[4/5] Creating commit..."
git commit -m $Message
Assert-LastExitCode "Git commit"

Write-Host "[5/5] Pushing to GitHub..."
git push origin main
Assert-LastExitCode "Git push"

Write-Host "Published. GitHub Actions will deploy the site to Cloudflare Pages."
