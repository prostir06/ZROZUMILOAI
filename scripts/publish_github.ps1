# Publish project to a private GitHub repository
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")

function Get-GhExe {
    if (Get-Command gh -ErrorAction SilentlyContinue) {
        return "gh"
    }
    $candidates = @(
        "$env:ProgramFiles\GitHub CLI\gh.exe",
        "${env:ProgramFiles(x86)}\GitHub CLI\gh.exe",
        "$env:LOCALAPPDATA\Programs\GitHub CLI\gh.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) {
            return $path
        }
    }
    throw "GitHub CLI (gh) not found. Install: winget install GitHub.cli"
}

function Test-GhRepoExists {
    param([string]$Name)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $gh repo view $Name --json name -q .name *>$null
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $prev
    }
}

$gh = Get-GhExe

$authOk = $false
try {
    & $gh auth status *>$null
    $authOk = ($LASTEXITCODE -eq 0)
} catch {
    $authOk = $false
}

if (-not $authOk) {
    Write-Host "Sign in to GitHub (browser will open)..."
    & $gh auth login -h github.com -p https -w
}

$repoName = "ZROZUMILOAI"
$repoExists = Test-GhRepoExists -Name $repoName

if ($repoExists) {
    Write-Host "Repository $repoName already exists - pushing..."
    git remote remove origin 2>$null
    & $gh repo set-default $repoName
    $login = & $gh api user -q .login
    git remote add origin "https://github.com/$login/$repoName.git"
    git push -u origin main
} else {
    Write-Host "Creating private repository $repoName..."
    & $gh repo create $repoName --private --source=. --remote=origin --push
}

$login = & $gh api user -q .login
Write-Host "Done: https://github.com/$login/$repoName"
