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

function Push-ToGithub {
    param([int]$Attempts = 3)
    for ($i = 1; $i -le $Attempts; $i++) {
        Write-Host "Pushing to GitHub (attempt $i/$Attempts)..."
        git push origin main 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        if ($i -lt $Attempts) {
            Write-Host "Push attempt $i failed (exit $LASTEXITCODE), retrying in 3 seconds..."
            Start-Sleep -Seconds 3
        }
    }
    Write-Host ""
    Write-Host "Push failed after $Attempts attempts. 常见原因与处理："
    Write-Host "  1) 远端有本地没有的提交 -> 先执行: git pull --rebase origin main，再重试本脚本"
    Write-Host "  2) TLS/网络握手失败(schannel) -> 直接重试，或执行: git config --global http.sslBackend openssl"
    Write-Host "  3) 登录失效 -> 在 Git Credential Manager 弹出的窗口完成登录后重试"
    return $false
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
$hasChanges = ($LASTEXITCODE -eq 1)
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) {
    Assert-LastExitCode "Git diff"
}

if ($hasChanges) {
    if ([string]::IsNullOrWhiteSpace($Message)) {
        $Message = "Update archive " + (Get-Date -Format "yyyy-MM-dd HH:mm")
    }
    Write-Host "[4/5] Creating commit..."
    git commit -m $Message
    Assert-LastExitCode "Git commit"
}
else {
    Write-Host "[4/5] No working-tree changes to commit (will still push pending commits)."
}

Write-Host "[5/5] Pushing to GitHub..."
if (-not (Push-ToGithub)) {
    exit 1
}

Write-Host "Published. GitHub Actions will deploy the site to Cloudflare Pages."