param(
    [string]$Message = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Prevent concurrent publish instances (avoids git index.lock conflicts)
$running = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match "-File.*publish\.ps1" -and $_.ProcessId -ne $PID })
if ($running.Count -gt 0) {
    Write-Host "publish.ps1 is already running. Close other publish windows first."
    exit 1
}

function Assert-LastExitCode([string]$Step) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed with exit code $LASTEXITCODE"
    }
}

function Clear-StaleGitLock {
    $lock = Join-Path $PSScriptRoot ".git\index.lock"
    if (Test-Path -LiteralPath $lock) {
        try {
            $ageSec = [Math]::Round(((Get-Date) - (Get-Item -LiteralPath $lock -Force).CreationTime).TotalSeconds, 0)
        }
        catch { $ageSec = 999 }
        if ($ageSec -gt 5) {
            try {
                Remove-Item -LiteralPath $lock -Force -ErrorAction Stop
                Write-Host "Removed stale .git/index.lock (age ${ageSec}s)"
            }
            catch {
                Write-Host "Could not remove .git/index.lock: $($_.Exception.Message)"
            }
        }
        else {
            Write-Host "index.lock is fresh (age ${ageSec}s); will retry git add shortly."
        }
    }
}

function Invoke-GitAddWithRetry {
    param([int]$Attempts = 5)
    for ($i = 1; $i -le $Attempts; $i++) {
        Clear-StaleGitLock
        git add --all
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        if ($i -lt $Attempts) {
            Write-Host "git add failed (exit $LASTEXITCODE), retrying in 3 seconds..."
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

function Push-ToGithub {
    param([int]$Attempts = 3)
    for ($i = 1; $i -le $Attempts; $i++) {
        Write-Host "Pushing to GitHub (attempt $i/$Attempts)..."
        git push origin main
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
        if ($i -lt $Attempts) {
            Write-Host "Push attempt $i failed (exit $LASTEXITCODE), retrying in 3 seconds..."
            Start-Sleep -Seconds 3
        }
    }
    Write-Host ""
    Write-Host "Push failed after $Attempts attempts. Common fixes:"
    Write-Host "  1) Remote has commits you don't have -> run: git pull --rebase origin main, then retry"
    Write-Host "  2) TLS handshake error (schannel) -> retry, or run: git config --global http.sslBackend openssl"
    Write-Host "  3) Login expired -> complete the Git Credential Manager window, then retry"
    return $false
}

Write-Host "[1/5] Building site..."
python .\build_site.py
Assert-LastExitCode "Site build"

Write-Host "[2/5] Validating generated files..."
python .\validate_site.py .\dist
Assert-LastExitCode "Site validation"

Write-Host "[3/5] Staging changes..."
if (-not (Invoke-GitAddWithRetry)) {
    throw "Git add failed after retries"
}

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