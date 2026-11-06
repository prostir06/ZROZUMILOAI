# Windows-friendly backup (Task Scheduler or manual). Prefer backup-cron.sh on Linux VPS.
# Usage (repo root):
#   .\scripts\backup-cron.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$compose = @("docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.prod.yml")
$keepDays = if ($env:BACKUP_KEEP_DAYS) { [int]$env:BACKUP_KEEP_DAYS } else { 14 }

Write-Host "[$(Get-Date -Format o)] backup start"
$filename = & $compose exec -T backend python manage.py create_backup
Write-Host "[$(Get-Date -Format o)] created: $filename"

# Prune local files older than KEEP_DAYS (off-box copies are the source of truth).
$backupDir = Join-Path $Root "backup"
if (Test-Path $backupDir) {
    $cutoff = (Get-Date).AddDays(-$keepDays)
    $extensions = @("*.tar.gz", "*.sql", "*.sqlite3", "*.db")
    Get-ChildItem -Path $backupDir -File | Where-Object {
        $file = $_
        $matchesExt = $false
        foreach ($pattern in $extensions) {
            if ($file.Name -like $pattern) {
                $matchesExt = $true
                break
            }
        }
        $matchesExt -and ($file.LastWriteTime -lt $cutoff)
    } | ForEach-Object {
        Write-Host "Pruning old backup: $($_.Name)"
        Remove-Item $_.FullName -Force
    }
}

Write-Host "[$(Get-Date -Format o)] backup done — copy ./backup off-box"
