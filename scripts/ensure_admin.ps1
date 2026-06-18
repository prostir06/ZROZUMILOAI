# Локальний скрипт (Windows): завантажує .env, відновлює БД (за потреби) і створює адміна.
$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $ProjectDir ".env"
$BackendDir = Join-Path $ProjectDir "backend"

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

Set-Location $BackendDir

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
$Python = if (Test-Path $VenvPython) { $VenvPython } else { "python" }

$ForceRestore = [Environment]::GetEnvironmentVariable("FORCE_DB_RESTORE", "Process")
if ($ForceRestore -eq "1") {
    Write-Host "FORCE_DB_RESTORE=1 — перевірка теки backup..."
    & $Python manage.py restore_backup
}

& $Python manage.py migrate --noinput
& $Python manage.py ensure_admin
